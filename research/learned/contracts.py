"""Fail-closed synthetic prefix/episode contracts, not provenance verification.

These contracts refuse empirical/personal data. They cannot establish that an
upstream producer truthfully used the declared prefix: real extraction requires
an independently audited producer and a separate empirical admission policy.
"""
from dataclasses import dataclass
import math
from typing import Optional


class ContractError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise ContractError(code)


def finite(x):
    return isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)


MAX_DOCUMENT_STEPS = 256
MAX_GRAPH_NODES = 512
MAX_GRAPH_EDGES = 4096
MAX_SUPPORT_DOCUMENTS = 32
MAX_TOY_ABS_VALUE = 10000.0  # Engineering guard, not a linguistic bound.


MISSING_REASONS = frozenset({
    'zero_denominator', 'dependency_unavailable', 'parse_failed',
    'annotation_unresolved', 'insufficient_support', 'numerical_unavailable',
})


@dataclass(frozen=True)
class Measurement:
    values: tuple[Optional[float], ...]
    opportunities: tuple[Optional[float], ...]
    missing_reasons: tuple[Optional[str], ...]

    def validate(self, channels):
        require(len(self.values) == len(self.opportunities) ==
                len(self.missing_reasons) == channels, 'measurement_shape')
        for value, opp, reason in zip(self.values, self.opportunities, self.missing_reasons):
            require(opp is None or (finite(opp) and opp >= 0), 'invalid_opportunity')
            if value is None:
                require(reason in MISSING_REASONS, 'missing_reason_required')
                if reason == 'zero_denominator':
                    require(opp == 0, 'zero_denominator_mismatch')
            else:
                require(finite(value), 'nonfinite_measurement')
                require(abs(value) <= MAX_TOY_ABS_VALUE, 'toy_value_out_of_range')
                require(opp is not None and opp > 0, 'observed_without_opportunity')
                require(reason is None, 'observed_with_missing_reason')


@dataclass(frozen=True)
class Observation:
    step: int
    source_prefix_end: int
    features: Measurement


@dataclass(frozen=True)
class Node:
    local_id: int
    kind: int
    available_step: int
    features: Measurement


@dataclass(frozen=True)
class Edge:
    source: int
    target: int
    relation: int
    available_step: int


@dataclass(frozen=True)
class GraphSnapshot:
    prefix_end: int
    input_prefix_end: int
    provenance: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    missing_reason: Optional[str] = None

    def validate(self, channels, relation_types, node_types):
        require(type(self.prefix_end) is int and self.prefix_end > 0, 'graph_prefix')
        require(type(self.input_prefix_end) is int and self.input_prefix_end == self.prefix_end and
                self.provenance == 'prefix_recomputed', 'retrospective_graph_forbidden')
        require(self.missing_reason is None or self.missing_reason in MISSING_REASONS,
                'graph_missing_reason')
        require(self.missing_reason is None or not (self.nodes or self.edges),
                'unavailable_graph_has_content')
        require(len(self.nodes) <= MAX_GRAPH_NODES and len(self.edges) <= MAX_GRAPH_EDGES,
                'graph_resource_limit')
        ids = [n.local_id for n in self.nodes]
        require(all(type(i) is int for i in ids) and ids == list(range(len(ids))), 'graph_ids_must_be_document_local_dense')
        for node in self.nodes:
            require(type(node.kind) is int and 0 <= node.kind < node_types, 'node_kind')
            require(type(node.available_step) is int and
                    1 <= node.available_step <= self.prefix_end, 'future_node')
            node.features.validate(channels)
        for edge in self.edges:
            require(type(edge.source) is int and type(edge.target) is int and
                    edge.source in ids and edge.target in ids, 'unknown_edge_endpoint')
            require(type(edge.relation) is int and 0 <= edge.relation < relation_types,
                    'edge_type')
            require(type(edge.available_step) is int and
                    max(self.nodes[edge.source].available_step,
                        self.nodes[edge.target].available_step) <= edge.available_step <=
                    self.prefix_end, 'future_or_premature_edge')
        keys = [(e.source, e.target, e.relation) for e in self.edges]
        require(len(keys) == len(set(keys)), 'duplicate_typed_edge')


@dataclass(frozen=True)
class TopologySnapshot:
    prefix_end: int
    input_prefix_end: int
    representation_id: str
    estimator_profile: str
    features: Measurement
    status: str
    reason: Optional[str]

    def validate(self):
        require(type(self.prefix_end) is int and self.prefix_end > 0 and
                type(self.input_prefix_end) is int and self.input_prefix_end == self.prefix_end, 'future_topology')
        require(bool(self.representation_id) and bool(self.estimator_profile),
                'topology_identity_missing')
        require(self.status in {'ok', 'unavailable'}, 'topology_status')
        require((self.reason is None) == (self.status == 'ok'), 'topology_reason')
        self.features.validate(5)
        if self.status == 'unavailable':
            require(all(v is None for v in self.features.values),
                    'unavailable_topology_has_values')


@dataclass(frozen=True)
class Document:
    work_id: str
    lineage_id: str
    content_family: str
    author_key: str
    topic: str
    partition: str
    released_at: int
    measurement_profile: str
    channel_ids: tuple[str, ...]
    observations: tuple[Observation, ...]
    graph_snapshots: tuple[GraphSnapshot, ...]
    topology_snapshots: tuple[TopologySnapshot, ...] = ()
    synthetic: bool = True
    personal: bool = False
    attribution_role: str = 'synthetic_single_producer'
    dependency_groups: tuple[str, ...] = ()

    def validate(self, channels, relation_types, node_types):
        require(self.synthetic is True and self.personal is False,
                'empirical_and_personal_data_not_admitted')
        require(self.attribution_role == 'synthetic_single_producer',
                'single_producer_role_required')
        require(all(isinstance(x, str) and x for x in (
            self.work_id, self.lineage_id, self.content_family, self.author_key,
            self.topic, self.partition, self.measurement_profile)), 'metadata_missing')
        require(type(self.released_at) is int and self.released_at >= 0, 'release_time')
        require(len(self.channel_ids) == channels and len(set(self.channel_ids)) == channels,
                'channel_identity')
        require(all(isinstance(x, str) and x.startswith('toy:') for x in self.channel_ids),
                'only_labeled_toy_channels_admitted')
        require(0 < len(self.observations) <= MAX_DOCUMENT_STEPS, 'document_resource_limit')
        require(len(self.graph_snapshots) <= MAX_DOCUMENT_STEPS and
                len(self.topology_snapshots) <= MAX_DOCUMENT_STEPS, 'snapshot_resource_limit')
        require(all(isinstance(g, str) and bool(g) for g in self.dependency_groups) and
                len(set(self.dependency_groups)) == len(self.dependency_groups), 'dependency_groups')
        for step, row in enumerate(self.observations, 1):
            require(type(row.step) is int and type(row.source_prefix_end) is int and
                    row.step == step and row.source_prefix_end == step,
                    'nonlocal_or_noncontiguous_observation')
            row.features.validate(channels)
        ends = [s.prefix_end for s in self.graph_snapshots]
        require(len(ends) == len(set(ends)), 'duplicate_graph_snapshot')
        for snapshot in self.graph_snapshots:
            snapshot.validate(channels, relation_types, node_types)
            require(snapshot.prefix_end <= len(self.observations), 'graph_beyond_document')
        ends = [s.prefix_end for s in self.topology_snapshots]
        require(len(ends) == len(set(ends)), 'duplicate_topology_snapshot')
        for snapshot in self.topology_snapshots:
            snapshot.validate()
            require(snapshot.prefix_end <= len(self.observations), 'topology_beyond_document')


@dataclass(frozen=True)
class PrefixView:
    document: Document
    cutoff: int
    rows: tuple[Observation, ...]
    graph: GraphSnapshot
    topology: Optional[TopologySnapshot]


def prefix_view(document, cutoff, channels, relation_types, node_types):
    document.validate(channels, relation_types, node_types)
    require(type(cutoff) is int and 1 <= cutoff <= len(document.observations), 'cutoff')
    graphs = [g for g in document.graph_snapshots if g.prefix_end == cutoff]
    require(len(graphs) == 1, 'exact_prefix_graph_required')
    topology = next((s for s in document.topology_snapshots if s.prefix_end == cutoff), None)
    # No global vector accepted: it is recomputed from these exact prefix rows.
    # Full-document graphs are not sliced or relabeled as causal graphs.
    return PrefixView(document, cutoff, document.observations[:cutoff], graphs[0], topology)


@dataclass(frozen=True)
class SupportRef:
    document: Document
    cutoff: int


@dataclass(frozen=True)
class Episode:
    query: Document
    cutoff: int
    as_of: int
    support: tuple[SupportRef, ...]
    context: tuple[float, ...]

    def validate(self, channels, relation_types, node_types, context_dim):
        require(type(self.as_of) is int and self.as_of >= 0, 'as_of')
        require(len(self.context) == context_dim and
                all(finite(v) and abs(v) <= MAX_TOY_ABS_VALUE for v in self.context),
                'context_shape_or_value')
        require(len(self.support) <= MAX_SUPPORT_DOCUMENTS, 'support_resource_limit')
        query = prefix_view(self.query, self.cutoff, channels, relation_types, node_types)
        require(self.query.released_at <= self.as_of, 'query_not_yet_available')
        seen_works, seen_lineages, seen_content = ({self.query.work_id},
            {self.query.lineage_id}, {self.query.content_family})
        seen_dependencies = set(self.query.dependency_groups)
        support_views = []
        for ref in self.support:
            doc = ref.document
            view = prefix_view(doc, ref.cutoff, channels, relation_types, node_types)
            require(doc.work_id not in seen_works, 'support_query_work_overlap')
            require(doc.lineage_id not in seen_lineages, 'support_query_lineage_overlap')
            require(doc.content_family not in seen_content, 'support_query_content_overlap')
            require(not seen_dependencies.intersection(doc.dependency_groups), 'dependency_group_overlap')
            require(doc.partition == self.query.partition, 'cross_partition_episode')
            require(doc.author_key == self.query.author_key, 'support_author_mismatch')
            require(doc.topic != self.query.topic, 'cross_topic_support_required')
            require(doc.released_at <= self.as_of, 'future_support')
            require(doc.measurement_profile == self.query.measurement_profile and
                    doc.channel_ids == self.query.channel_ids, 'measurement_identity_mismatch')
            seen_works.add(doc.work_id)
            seen_lineages.add(doc.lineage_id)
            seen_content.add(doc.content_family)
            seen_dependencies.update(doc.dependency_groups)
            support_views.append(view)
        return query, tuple(support_views)


@dataclass(frozen=True)
class NextActionTarget:
    work_id: str
    step: int
    actions: tuple[Optional[float], ...]
    contiguous: bool = True
    synthetic: bool = True
