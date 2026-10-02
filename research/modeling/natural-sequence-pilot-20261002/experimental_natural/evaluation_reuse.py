"""Experimental evaluation-only reuse; not yet wired into the scored study.

Every prepare call receives only the current owned prefix. Online statistics
and neural states contain past observations only. Heads can be batched after
causal features have been fixed. There is no padding or document metadata.
"""
import hashlib
import torch
from .schema import PrefixPacket
from .models import PrefixModel, IndependentFamilies


def _reference_compatible_head(head, rows):
    """Keep the large first projection's reference GEMV reduction order.

    A single float32 GEMM can exceed the fixed 1e-6 prediction tolerance for
    17k-input heads. Smaller remaining layers are still batched.
    """
    hidden=torch.stack([head[0](row) for row in rows])
    for layer in list(head)[1:]:hidden=layer(hidden)
    return hidden


class OnlineMoments:
    """Float64 pairwise Welford co-moments with pair-specific means."""
    def __init__(self, dimensions):
        self.dimensions = dimensions
        self.t = 0
        self.count = torch.zeros(dimensions, dtype=torch.float64)
        self.value_sum = torch.zeros_like(self.count)
        self.known_count = torch.zeros_like(self.count)
        self.opportunity_log32_sum = torch.zeros_like(self.count)
        self.opportunity_log64_sum = torch.zeros_like(self.count)
        self.pair_count = torch.zeros((dimensions, dimensions), dtype=torch.float64)
        self.pair_mean = torch.zeros_like(self.pair_count)
        self.pair_comoment = torch.zeros_like(self.pair_count)
        self._content_digest = hashlib.sha256()
        self.content_dtypes = None

    def append(self, values, observed, opportunity, known):
        dtypes=tuple(str(x.dtype) for x in (values,observed,opportunity,known))
        if self.content_dtypes is not None and self.content_dtypes != dtypes:
            raise ValueError('Coordinate dtypes cannot change within a prefix')
        self.content_dtypes=dtypes
        packed=torch.cat([x.detach().double() for x in (values,observed,opportunity,known)])
        self._content_digest.update(packed.numpy().tobytes())
        x, mask, k = values.double(), observed.double(), known.double()
        self.t += 1
        self.count += mask
        self.value_sum += x * mask
        self.known_count += k
        # Preserve the reference encoder's two explicit opportunity pathways.
        self.opportunity_log32_sum += torch.log1p(opportunity).double() * k
        self.opportunity_log64_sum += torch.log1p(opportunity.double()) * k
        joint = mask[:, None] * mask[None, :]
        new_count = self.pair_count + joint
        delta = x[:, None] - self.pair_mean
        new_mean = self.pair_mean + joint * delta / new_count.clamp_min(1)
        self.pair_comoment += joint * delta * (x[None, :] - new_mean.T)
        self.pair_mean = new_mean
        self.pair_count = new_count

    def summary(self, view, include_covariance):
        ix = torch.tensor(view.indices, dtype=torch.long)
        count, known_count = self.count[ix], self.known_count[ix]
        parts = []
        if view.active_local:
            parts.append((self.value_sum[ix] / count.clamp_min(1))[list(view.active_local)])
        parts.extend([count/self.t, torch.log1p(count)])
        if view.mode != 'length':
            if view.has_opportunity:
                parts.append(self.opportunity_log32_sum[ix] / known_count.clamp_min(1))
            parts.extend([known_count/self.t, torch.log1p(known_count)])
        ij = torch.triu_indices(view.n, view.n)
        a, b = ix[ij[0]], ix[ij[1]]
        n = self.pair_count[a, b]
        parts.extend([n/self.t, torch.log1p(n), (n >= 1).double(), (n >= 2).double()])
        if view.has_values:
            active = torch.tensor([i in view.active_local for i in range(view.n)])
            parts.extend([self.pair_mean[a, b][active[ij[0]]],
                          self.pair_mean[b, a][active[ij[1]]]])
            if include_covariance:
                selected = active[ij[0]] & active[ij[1]]
                covariance = self.pair_comoment[a, b] / (n-1).clamp_min(1)
                parts.append(torch.where(n >= 2, covariance, torch.zeros_like(covariance))[selected])
        parts.append(torch.tensor([float(self.t)], dtype=torch.float64).log1p())
        if view.nuisance_indices:
            ni = torch.tensor(view.nuisance_indices, dtype=torch.long)
            nc, kn = self.count[ni], self.known_count[ni]
            parts.extend([nc/self.t, torch.log1p(nc), self.opportunity_log64_sum[ni]/kn.clamp_min(1),
                          kn/self.t, torch.log1p(kn)])
        return torch.cat(parts).float()


class CausalEvaluationState:
    """One document and one immutable evaluation model, reset between documents."""
    def __init__(self, model, summary_cache=None):
        if type(model) not in (PrefixModel, IndependentFamilies):
            raise TypeError('Only the registered prefix architectures are supported')
        if model.training:
            raise ValueError('Evaluation reuse requires model.eval()')
        self.model = model
        self.branches = list(model.models) if type(model) is IndependentFamilies else [model]
        self.versions = tuple(p._version for p in model.parameters())
        self.moments = OnlineMoments(self.branches[0].view.dimensions)
        self.last_packet = None
        self.sums = [None] * len(self.branches)
        self.hidden = [None] * len(self.branches)
        self.summary_cache = summary_cache

    def prepare(self, packet):
        if torch.is_grad_enabled():
            raise RuntimeError('This path is evaluation-only; use torch.no_grad()')
        return self._prepare_impl(packet)

    def _prepare_impl(self, packet):
        """Autograd-capable kernel exposed privately for equivalence tests only."""
        if self.model.training or self.versions != tuple(p._version for p in self.model.parameters()):
            raise RuntimeError('Cached neural states cannot survive parameter updates or training-mode changes')
        if type(packet) is not PrefixPacket:
            raise TypeError('Only an owned prefix packet is accepted')
        packet.validate(self.moments.dimensions)
        if packet.prefix_unit_count != self.moments.t + 1:
            raise ValueError('Supply consecutive current prefixes; reset between documents')
        if self.last_packet is not None:
            for field in ('prefix_values', 'prefix_observed', 'prefix_opportunity', 'prefix_opportunity_known'):
                if not torch.equal(getattr(packet, field)[:-1], getattr(self.last_packet, field)):
                    raise ValueError('Earlier observations changed; reset causal state')
        last = PrefixPacket(packet.prefix_values[-1:].clone(), packet.prefix_observed[-1:].clone(),
                            packet.prefix_opportunity[-1:].clone(), packet.prefix_opportunity_known[-1:].clone(), 1)
        self.moments.append(last.prefix_values[0], last.prefix_observed[0],
                            last.prefix_opportunity[0], last.prefix_opportunity_known[0])
        canonical = (self.summary_cache.get(packet, online=self.moments)
                     if self.summary_cache is not None else None)
        features = []
        for i, branch in enumerate(self.branches):
            summary = (self.summary_cache.project(canonical, branch.view, branch.include_covariance)
                       if canonical is not None else self.moments.summary(branch.view, branch.include_covariance))
            parts = [summary]
            if branch.name in ('F2', 'F3', 'F4'):
                local = branch.view.local(last)
                embedding = branch.phi(local)[0].double()
                self.sums[i] = embedding if self.sums[i] is None else self.sums[i] + embedding
                parts.extend([self.sums[i].float(), (self.sums[i]/self.moments.t).float()])
                if branch.name == 'F3':
                    parts.append(local[0])
                if branch.name == 'F4':
                    _, self.hidden[i] = branch.gru(local.unsqueeze(0), self.hidden[i])
                    parts.append(self.hidden[i][0, 0])
            features.append(torch.cat(parts))
        # Own the identity anchor; caller mutation must not hide a changed past.
        self.last_packet = PrefixPacket(*(getattr(packet, field).clone() for field in
            ('prefix_values', 'prefix_observed', 'prefix_opportunity', 'prefix_opportunity_known')),
            packet.prefix_unit_count)
        return features

    def heads(self, prepared):
        if not prepared:
            return torch.empty((0, self.moments.dimensions))
        outputs = torch.zeros((len(prepared), self.moments.dimensions))
        for i, branch in enumerate(self.branches):
            learned = _reference_compatible_head(branch.head,[item[i] for item in prepared])
            indices = (torch.tensor(self.model.target_indices[i]) if type(self.model) is IndependentFamilies
                       else branch.output_indices)
            outputs = outputs.scatter(1, indices[None, :].expand(len(prepared), -1), learned)
        if not torch.isfinite(outputs).all():
            raise FloatingPointError('Nonfinite evaluation output')
        return outputs


def evaluate_prefix_stream(model, packets, head_batch_size=32, summary_cache=None):
    """Yield causal outputs with bounded head batches and no padded raw inputs."""
    if type(head_batch_size) is not int or head_batch_size < 1:
        raise ValueError('Positive head batch size required')
    state = CausalEvaluationState(model, summary_cache)
    prepared = []
    for packet in packets:
        outputs = None
        with torch.no_grad():
            prepared.append(state.prepare(packet))
            if len(prepared) == head_batch_size:
                outputs = state.heads(prepared)
                prepared.clear()
        if outputs is not None:
            yield from outputs.unbind(0)
    if prepared:
        with torch.no_grad():
            outputs = state.heads(prepared)
        yield from outputs.unbind(0)


def evaluate_permutations(model, packet, permutations, summary_cache=None):
    """Share set/moment features, batch equal-length shuffled GRUs, return each prediction.

    The caller must average separate losses, never average these predictions
    before scoring. This helper is not wired into the scientific evaluator yet.
    """
    if type(model) is not PrefixModel or model.name != 'F4' or model.training:
        raise ValueError('An evaluation-mode registered F4 is required')
    packet.validate(model.view.dimensions)
    n = packet.prefix_unit_count
    if not permutations:
        raise ValueError('At least one declared permutation required')
    if any(type(x) is not torch.Tensor or x.ndim != 1 or len(x) != n or
           x.dtype not in (torch.int32,torch.int64) or x.device.type != 'cpu' for x in permutations):
        raise ValueError('Each order must be a one-dimensional CPU integer-index tensor')
    if any(sorted(x.tolist()) != list(range(n)) for x in permutations):
        raise ValueError('Each order must permute precisely the current prefix')
    with torch.no_grad():
        summary = (summary_cache.project(summary_cache.get(packet), model.view, model.include_covariance)
                   if summary_cache is not None else model.view.summarize(packet, model.include_covariance))
        local = model.view.local(packet)
        embedded = model.phi(local)
        summed, mean = embedded.double().sum(0).float(), embedded.double().mean(0).float()
        _, hidden = model.gru(torch.stack([local[order] for order in permutations]))
        features = torch.stack([torch.cat([summary, summed, mean, hidden[0, i]]) for i in range(len(permutations))])
        learned = _reference_compatible_head(model.head,features)
        outputs = learned.new_zeros((len(permutations), model.targets)).scatter(1,
            model.output_indices[None, :].expand(len(permutations), -1), learned)
        if not torch.isfinite(outputs).all():
            raise FloatingPointError('Nonfinite shuffled evaluation output')
        return outputs


def _cached_batch_impl(model, packets, summary_cache):
    """Static summaries plus a batched head; mathematical kernel for regression tests."""
    if type(model) is IndependentFamilies:
        out=torch.zeros((len(packets),model.dimensions))
        for branch,indices in zip(model.models,model.target_indices):
            out=out.scatter(1,torch.tensor(indices)[None,:].expand(len(packets),-1),
                            _cached_batch_impl(branch,packets,summary_cache))
        return out
    if type(model) is not PrefixModel:raise TypeError('Registered prefix model required')
    parts=[]
    for packet in packets:
        if type(packet) is not PrefixPacket:raise TypeError('Owned current-prefix packets required')
        canonical=summary_cache.get(packet)
        row=[summary_cache.project(canonical,model.view,model.include_covariance)]
        if model.name in ('F2','F3','F4'):
            local=model.view.local(packet);embedding=model.phi(local)
            row.extend([embedding.double().sum(0).float(),embedding.double().mean(0).float()])
            if model.name=='F3':row.append(local[-1])
            if model.name=='F4':row.append(model.gru(local.unsqueeze(0))[1][0,0])
        parts.append(torch.cat(row))
    learned=_reference_compatible_head(model.head,parts)
    out=learned.new_zeros((len(packets),model.targets)).scatter(1,model.output_indices[None,:].expand(len(packets),-1),learned)
    if not torch.isfinite(out).all():raise FloatingPointError('Nonfinite cached-batch output')
    return out


def evaluate_cached_batch(model, packets, summary_cache):
    """Evaluate a bounded list of current prefixes, without raw-sequence padding."""
    if model.training:raise ValueError('Cached evaluation requires model.eval()')
    if not 1 <= len(packets) <= 32:raise ValueError('Evaluation head batches are bounded at 32 prefixes')
    with torch.no_grad():return _cached_batch_impl(model,packets,summary_cache)
