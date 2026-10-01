"""Trainable synthetic mechanics, not a fitted or identified style model.

Binary straight-through gates use a biased sigmoid surrogate, not a claim of
hard-concrete/L0 inference. Explicit values, presence and opportunity channels
share each gate across the global, sequence and node-feature paths. Typed graph
structure remains a separate information path and is disclosed in outputs.
"""
from dataclasses import dataclass
import math
import torch
from torch import nn
from torch.nn import functional as F
from .contracts import Episode, NextActionTarget, require, MAX_TOY_ABS_VALUE


@dataclass(frozen=True)
class Config:
    channels: int = 4
    hidden: int = 16
    latent: int = 16
    context_dim: int = 2
    actions: int = 4
    relation_types: int = 2
    node_types: int = 3
    heads: int = 2
    max_steps: int = 64
    use_topology: bool = True
    entry_column_bound: float = 1.0
    measurement_profile: str = 'synthetic-prefix/0.1'
    topology_representation: str = 'synthetic-independent-cube/seed937'
    topology_profile: str = 'paper_prose_v1'

    def validate(self):
        for field in ('channels', 'hidden', 'latent', 'context_dim', 'actions',
                      'relation_types', 'node_types', 'heads', 'max_steps'):
            require(type(getattr(self, field)) is int and getattr(self, field) > 0,
                    'invalid_config_' + field)
        require(self.hidden % self.heads == 0, 'head_width')
        require(math.isfinite(self.entry_column_bound) and self.entry_column_bound > 0,
                'entry_bound')


class BoundedLinear(nn.Module):
    """Differentiable effective column norm cap; raw weights are not importance."""
    def __init__(self, inputs, outputs, bound=1.0, bias=True):
        super().__init__()
        self.weight = nn.Parameter(torch.empty(outputs, inputs))
        self.bias = nn.Parameter(torch.zeros(outputs)) if bias else None
        self.bound = bound
        nn.init.xavier_uniform_(self.weight)

    def effective_weight(self):
        scale = (self.weight.norm(dim=0, keepdim=True) / self.bound).clamp_min(1.0)
        return self.weight / scale

    def forward(self, x):
        return F.linear(x, self.effective_weight(), self.bias)


class BinaryGroupGates(nn.Module):
    """Exactly binary forward; biased straight-through derivative while trainable."""
    def __init__(self, groups):
        super().__init__()
        self.logits = nn.Parameter(torch.full((groups,), 1.0))
        self.register_buffer('fixed', torch.full((groups,), -1.0))

    def forward(self):
        probability = self.logits.sigmoid()
        hard = (probability >= 0.5).to(probability.dtype)
        trainable = hard + (probability - probability.detach())
        return torch.where(self.fixed >= 0, self.fixed, trainable)

    def expected_active_surrogate(self):
        return torch.where(self.fixed >= 0, self.fixed, self.logits.sigmoid()).sum()

    def freeze(self, mask):
        mask = torch.as_tensor(mask, dtype=self.fixed.dtype, device=self.fixed.device)
        require(mask.shape == self.fixed.shape and bool(((mask == 0) | (mask == 1)).all()),
                'binary_gate_mask_required')
        self.fixed.copy_(mask)


def measurement_tensor(measurements, channels, device):
    """Four explicit fields per channel; missing is never silently a true zero."""
    rows = []
    for measurement in measurements:
        measurement.validate(channels)
        vals = [0.0 if v is None else float(v) for v in measurement.values]
        present = [float(v is not None) for v in measurement.values]
        opp = [0.0 if n is None else math.log1p(n) for n in measurement.opportunities]
        opp_known = [float(n is not None) for n in measurement.opportunities]
        rows.append([vals, present, opp, opp_known])
    return torch.tensor(rows, dtype=torch.float32, device=device)


class GlobalEncoder(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.entry = BoundedLinear(cfg.channels * 4, cfg.hidden, cfg.entry_column_bound)
        self.out = BoundedLinear(cfg.hidden, cfg.hidden)

    def forward(self, rows, gates):
        values, present, opp, opp_known = rows.unbind(dim=1)
        count = present.sum(dim=0)
        mean = (values * present).sum(dim=0) / count.clamp_min(1)
        coverage = present.mean(dim=0)
        mean_opp = opp.sum(dim=0) / opp_known.sum(dim=0).clamp_min(1)
        stats = torch.stack((mean, coverage, mean_opp, opp_known.mean(dim=0)))
        return self.out(F.gelu(self.entry((stats * gates).flatten())))


class CausalSequenceEncoder(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.max_steps = cfg.max_steps
        self.entry = BoundedLinear(cfg.channels * 4, cfg.hidden, cfg.entry_column_bound)
        self.position = nn.Embedding(cfg.max_steps, cfg.hidden)
        layer = nn.TransformerEncoderLayer(cfg.hidden, cfg.heads, cfg.hidden * 2,
                                          dropout=0.0, batch_first=True, activation='gelu')
        # One layer: no shared-initialization concern across cloned encoder layers.
        self.encoder = nn.TransformerEncoder(layer, 1, enable_nested_tensor=False)

    def forward(self, rows, gates):
        n = len(rows)
        require(0 < n <= self.max_steps, 'sequence_resource_limit')
        x = self.entry((rows * gates).flatten(start_dim=1))
        x = x + self.position(torch.arange(n, device=x.device))
        mask = torch.ones((n, n), dtype=torch.bool, device=x.device).triu(1)
        return self.encoder(x.unsqueeze(0), mask=mask).squeeze(0)


class TypedGraphEncoder(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.entry = BoundedLinear(cfg.channels * 4, cfg.hidden, cfg.entry_column_bound)
        self.node_types = nn.Embedding(cfg.node_types, cfg.hidden)
        self.self_message = BoundedLinear(cfg.hidden, cfg.hidden)
        self.relations = nn.ModuleList([BoundedLinear(cfg.hidden, cfg.hidden, bias=False)
                                      for _ in range(cfg.relation_types)])
        self.empty = nn.Parameter(torch.zeros(cfg.hidden))
        self.unavailable = nn.Parameter(torch.full((cfg.hidden,), 0.01))

    def forward(self, snapshot, gates):
        if not snapshot.nodes:
            return self.unavailable if snapshot.missing_reason else self.empty
        device = self.entry.weight.device
        measurements = [n.features for n in snapshot.nodes]
        x = measurement_tensor(measurements, self.cfg.channels, device)
        h = self.entry((x * gates).flatten(start_dim=1))
        kinds = torch.tensor([n.kind for n in snapshot.nodes], dtype=torch.long, device=device)
        h = F.gelu(h + self.node_types(kinds))
        messages = torch.zeros_like(h)
        counts = torch.zeros((len(h), 1), device=device)
        for rel, transform in enumerate(self.relations):
            edges = [e for e in snapshot.edges if e.relation == rel]
            if not edges:
                continue
            source = torch.tensor([e.source for e in edges], dtype=torch.long, device=device)
            target = torch.tensor([e.target for e in edges], dtype=torch.long, device=device)
            messages = messages.index_add(0, target, transform(h[source]))
            counts = counts.index_add(0, target, torch.ones((len(edges), 1), device=device))
        return F.gelu(self.self_message(h) + messages / counts.clamp_min(1)).mean(dim=0)


class TopologyEncoder(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.entry = BoundedLinear(20, cfg.hidden, cfg.entry_column_bound)
        self.out = BoundedLinear(cfg.hidden, cfg.hidden)

    def forward(self, snapshot, gate):
        device = self.entry.weight.device
        if snapshot is None:
            features = torch.zeros(20, device=device)
        else:
            snapshot.validate()
            features = measurement_tensor([snapshot.features], 5, device).flatten()
        # Gate the representation after the network too: no bias bypass when off.
        return self.out(F.gelu(self.entry(features * gate))) * gate


class MultiViewDynamics(nn.Module):
    def __init__(self, cfg=Config(), *, reference_contexts=None, reference_weights=None):
        super().__init__()
        cfg.validate()
        self.cfg = cfg
        self.gates = BinaryGroupGates(cfg.channels + 1)
        if not cfg.use_topology:
            self.gates.fixed[-1] = 0
        self.global_branch = GlobalEncoder(cfg)
        self.sequence_branch = CausalSequenceEncoder(cfg)
        self.graph_branch = TypedGraphEncoder(cfg)
        self.topology_branch = TopologyEncoder(cfg)
        self.fusion = BoundedLinear(cfg.hidden * 4, cfg.hidden)
        self.stable_head = BoundedLinear(cfg.hidden, cfg.latent)
        self.prior_stable = nn.Parameter(torch.zeros(cfg.latent))
        self.context_head = nn.Sequential(BoundedLinear(cfg.context_dim, cfg.hidden),
                                          nn.GELU(), BoundedLinear(cfg.hidden, cfg.latent))
        self.residual_head = BoundedLinear(cfg.hidden, cfg.latent)
        self.dynamic_head = BoundedLinear(cfg.hidden + cfg.latent * 2, cfg.hidden)
        self.action_head = BoundedLinear(cfg.hidden, cfg.actions)
        contexts = torch.as_tensor(reference_contexts if reference_contexts is not None else
                                   [[0.0] * cfg.context_dim], dtype=torch.float32)
        require(contexts.ndim == 2 and contexts.shape[1] == cfg.context_dim and
                0 < len(contexts) <= 256 and bool(torch.isfinite(contexts).all()) and
                bool((contexts.abs() <= MAX_TOY_ABS_VALUE).all()), 'reference_contexts')
        weights = torch.as_tensor(reference_weights if reference_weights is not None else
                                  [1.0 / len(contexts)] * len(contexts), dtype=torch.float64)
        require(weights.shape == (len(contexts),) and bool(torch.isfinite(weights).all()) and
                bool((weights > 0).all()), 'reference_weights')
        # Normalize after dividing by the largest weight. Summing finite raw
        # weights can overflow even when every individual value passed validation.
        weights = weights / weights.max()
        weights = (weights / weights.sum()).to(dtype=torch.float32)
        require(bool(torch.isfinite(weights).all()) and bool((weights > 0).all()) and
                bool(torch.isclose(weights.sum(), torch.tensor(1.0), rtol=1e-6, atol=1e-7)),
                'normalized_reference_weights')
        self.register_buffer('reference_contexts', contexts)
        self.register_buffer('reference_weights', weights)

    def centered_context(self, context):
        reference = self.context_head(self.reference_contexts)
        center = (reference * self.reference_weights[:, None]).sum(dim=0)
        return self.context_head(context) - center

    def encode(self, view, gates):
        device = self.prior_stable.device
        rows = measurement_tensor([row.features for row in view.rows], self.cfg.channels, device)
        global_state = self.global_branch(rows, gates[:-1])
        sequence = self.sequence_branch(rows, gates[:-1])
        graph = self.graph_branch(view.graph, gates[:-1])
        topology = (self.topology_branch(view.topology, gates[-1]) if self.cfg.use_topology
                    else torch.zeros_like(global_state))
        fused = F.gelu(self.fusion(torch.cat((global_state, sequence[-1], graph, topology))))
        return fused, {'global': global_state, 'sequence': sequence, 'graph': graph,
                       'topology': topology}

    def forward(self, episode: Episode):
        cfg = self.cfg
        require(episode.query.measurement_profile == cfg.measurement_profile and
                episode.query.channel_ids == tuple(f'toy:channel_{i}' for i in range(cfg.channels)),
                'model_measurement_identity_mismatch')
        require(self.prior_stable.device.type == 'cpu', 'prototype_cpu_only')
        query, support = episode.validate(cfg.channels, cfg.relation_types,
                                           cfg.node_types, cfg.context_dim)
        if cfg.use_topology:
            for view in (query,) + support:
                if view.topology is not None:
                    require(view.topology.representation_id == cfg.topology_representation and
                            view.topology.estimator_profile == cfg.topology_profile,
                            'model_topology_identity_mismatch')
        gates = self.gates()
        query_h, branches = self.encode(query, gates)
        if support:
            support_h = torch.stack([self.encode(view, gates)[0] for view in support]).mean(dim=0)
            stable = self.stable_head(support_h)
            stable_source = 'synthetic_support_only'
        else:
            stable, stable_source = self.prior_stable, 'population_prior_unfitted'
        context = torch.tensor(episode.context, dtype=torch.float32, device=query_h.device)
        adaptation = self.centered_context(context)
        z_context = adaptation + self.residual_head(query_h)
        dynamic = F.gelu(self.dynamic_head(torch.cat((query_h, stable, z_context))))
        return {'action_logits': self.action_head(dynamic), 'z_stable': stable,
                'z_context': z_context, 'context_adaptation': adaptation, 'h_prefix': dynamic,
                'query_branches': branches, 'gate_values': gates,
                'gate_surrogate': self.gates.expected_active_surrogate(),
                'work_id': episode.query.work_id, 'cutoff': episode.cutoff,
                'stable_source': stable_source, 'status': 'synthetic_unvalidated_prototype',
                'selected_interpretable_groups': tuple(channel for channel, selected in
                    zip(episode.query.channel_ids, gates[:-1].detach().tolist()) if selected == 1),
                'topology_group_active': bool(gates[-1].detach() == 1 and cfg.use_topology),
                'remaining_information_paths': ('typed_graph_structure', 'local_node_types',
                                                 'sequence_order', 'declared_context')}


def multilabel_next_action_loss(output, target: NextActionTarget):
    require(target.synthetic is True, 'empirical_target_not_admitted')
    require(target.contiguous is True, 'censored_or_noncontiguous_target')
    require(target.work_id == output['work_id'] and target.step == output['cutoff'] + 1,
            'target_identity_or_horizon')
    logits = output['action_logits']
    require(len(target.actions) == len(logits), 'target_shape')
    require(all(v is None or (type(v) in (int, float) and v in (0.0, 1.0))
                for v in target.actions), 'nonbinary_action_target')
    mask = torch.tensor([v is not None for v in target.actions], device=logits.device)
    require(bool(mask.any()), 'no_observed_target')
    values = torch.tensor([0.0 if v is None else v for v in target.actions],
                          dtype=logits.dtype, device=logits.device)
    # Select before BCE: absent labels have no numeric loss contribution/gradient.
    loss = F.binary_cross_entropy_with_logits(logits[mask], values[mask])
    return loss, {'observed_actions': int(mask.sum()), 'missing_actions': int((~mask).sum()),
                  'objective': 'masked_multilabel_next_action_BCE_not_joint_text_likelihood'}
