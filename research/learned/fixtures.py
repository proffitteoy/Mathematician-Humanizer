"""Deterministic toy observations and labels; none represent natural language."""
from dataclasses import replace
import math
from .contracts import (Measurement, Observation, Node, Edge, GraphSnapshot,
                        Document, Episode, SupportRef, NextActionTarget)


def measure(values, *, missing_index=None):
    vals = list(map(float, values))
    opp = [1.0 + (i % 2) for i in range(len(vals))]
    reasons = [None] * len(vals)
    if missing_index is not None:
        vals[missing_index] = None
        opp[missing_index] = None
        reasons[missing_index] = 'annotation_unresolved'
    return Measurement(tuple(vals), tuple(opp), tuple(reasons))


def toy_document(key, *, author='toy_author_A', topic='topic_A', steps=5,
                 released_at=10, phase=0.0):
    rows = tuple(Observation(t, t, measure(
        [math.sin(t + phase), t / 6, (-1) ** t * 0.3, math.cos(t * 0.4 + phase)],
        missing_index=3 if t == 2 else None)) for t in range(1, steps + 1))
    snapshots = []
    for t in range(1, steps + 1):
        # Each snapshot is independently built from this exact prefix. Dense IDs
        # are local; no author/entity string becomes a tensor.
        nodes = tuple(Node(j, j % 3, j + 1, rows[j].features) for j in range(t))
        edges = tuple(Edge(j - 1, j, (j - 1) % 2, j + 1) for j in range(1, t))
        snapshots.append(GraphSnapshot(t, t, 'prefix_recomputed', nodes, edges))
    return Document(key, 'lineage_' + key, 'content_' + key, author, topic, 'synthetic_train',
                    released_at, 'synthetic-prefix/0.1',
                    tuple(f'toy:channel_{i}' for i in range(4)), rows, tuple(snapshots))


def toy_episode(*, cutoff=3, with_topology=False):
    query = toy_document('query', topic='topic_B', released_at=30)
    support1 = toy_document('support1', topic='topic_A', released_at=10, phase=0.4)
    support2 = toy_document('support2', topic='topic_C', released_at=20, phase=0.9)
    if with_topology:
        from .topology_adapter import from_phd_report
        from research.topology.phd import estimate, Config as PHDConfig
        import numpy as np
        points = np.random.default_rng(937).uniform(size=(80, 3))
        report = estimate(points, PHDConfig(reruns=2))
        topology = from_phd_report(report, prefix_end=cutoff, input_prefix_end=cutoff,
                                  representation_id='synthetic-independent-cube/seed937')
        query = replace(query, topology_snapshots=(topology,))
    episode = Episode(query, cutoff, 40,
                      (SupportRef(support1, 4), SupportRef(support2, 4)), (0.25, -0.75))
    target = NextActionTarget(query.work_id, cutoff + 1, (1.0, 1.0, 0.0, None))
    return episode, target
