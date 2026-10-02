#!/usr/bin/env python3
"""Aggregate-only randomized review of the sibling typed quotient module.

Uses synthetic trees only: no cache, corpus, models, network, or per-case output.
The elementary reducer implements the declared eligibility rule separately;
structural validation and canonical serialization use the reviewed module.
Run: python independent_randomized_review.py
"""
import collections
import copy
import hashlib
import json
import pathlib
import random
import resource
import runpy
import sys
import time
import unittest

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
SEED = 9127
CASES = 2000


def eligible_carriers(graph):
    nodes = graph['nodes']
    children = collections.defaultdict(list)
    for key, node in nodes.items():
        if 'parent' in node:
            children[node['parent']].append(key)
    return sorted(key for key, node in nodes.items()
                  if node['kind'] == 'group' and node.get('type') == 'span'
                  and set(node).issubset({'kind', 'type', 'parent', 'relname'})
                  and len(children[key]) == 1
                  and nodes[children[key][0]].get('relname') == 'span')


def sequential_reduce(graph, rng):
    graph = copy.deepcopy(graph)
    while candidates := eligible_carriers(graph):
        wrapper_id = rng.choice(candidates)
        nodes = graph['nodes']
        child_id, = [key for key, node in nodes.items()
                     if node.get('parent') == wrapper_id]
        wrapper, child = nodes[wrapper_id], nodes[child_id]
        child.pop('parent', None)
        child.pop('relname', None)
        if 'parent' in wrapper:
            child['parent'] = wrapper['parent']
            if 'relname' in wrapper:
                child['relname'] = wrapper['relname']
        del nodes[wrapper_id]
    return graph


def synthetic_tree(rng):
    count = rng.randrange(2, 18)
    parents = {str(i): str(rng.randrange(i)) for i in range(1, count)}
    internal = set(parents.values())
    nodes = {}
    for i in range(count):
        key = str(i)
        kind = 'group' if key in internal and rng.random() < .7 else 'segment'
        node = {'kind': kind}
        if kind == 'group':
            node['type'] = rng.choice(['span', 'span', 'multinuc'])
            if rng.random() < .1:
                node['scope'] = 'extra'
        if i:
            node.update(parent=parents[key],
                        relname=rng.choice(['span', 'span', 'evidence', 'joint']))
        nodes[key] = node
    edu_order = [key for key in nodes if nodes[key]['kind'] == 'segment']
    rng.shuffle(edu_order)
    return {'nodes': nodes, 'edu_order': edu_order,
            'edu_spans': [(i, i + 1) for i in range(len(edu_order))],
            'text': 'X' * len(edu_order),
            'relations': {'evidence': 'rst', 'joint': 'multinuc'}}


def main():
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (600, 600))
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    module_path = HERE / 'typed_quotient.py'
    module_hash = hashlib.sha256(module_path.read_bytes()).hexdigest()
    reviewed = runpy.run_path(str(module_path))
    q, structure = reviewed['quotient'], reviewed['structure']
    canonical = reviewed['canonical']
    checks, coverage = collections.Counter(), collections.Counter()
    rng = random.Random(SEED)
    for _ in range(CASES):
        graph = synthetic_tree(rng)
        reduced, projection, removed = q(graph)
        assert set(eligible_carriers(graph)) == reviewed['identity_candidates'](graph)
        checks['independent_eligibility_agreement'] += 1
        assert reduced == sequential_reduce(graph, rng)
        checks['random_sequential_reduction_agreement'] += 1
        assert reduced == q(reduced)[0]
        checks['idempotence'] += 1
        assert canonical(graph) == canonical(reviewed['expand_identity_bridges'](graph, 2))
        checks['double_wrapper_invariance'] += 1
        assert canonical(graph) == canonical(reviewed['relabel_and_reorder'](graph))
        checks['id_and_declaration_invariance'] += 1
        old, new = structure(graph), structure(reduced)
        for key in reduced['nodes']:
            assert old['anchor'].get(key) == new['anchor'].get(key)
            assert old['yields'][key] == new['yields'][key]
            assert len(old['children'][key]) == len(new['children'][key])
            old_attrs = {k: v for k, v in graph['nodes'][key].items()
                         if k not in ('parent', 'relname')}
            new_attrs = {k: v for k, v in reduced['nodes'][key].items()
                         if k not in ('parent', 'relname')}
            assert old_attrs == new_attrs
        checks['retained_anchors_yields_arity_and_attributes'] += 1
        for key, node in graph['nodes'].items():
            if 'parent' in node and node.get('relname') != 'span':
                result_node = reduced['nodes'][projection[key]]
                assert result_node['relname'] == node['relname']
                assert result_node['parent'] == projection[node['parent']]
                assert reviewed['role'](result_node, reduced['relations']) == reviewed['role'](node, graph['relations'])
        checks['nonspan_labels_roles_and_projected_endpoints'] += 1
        for field in ('edu_order', 'edu_spans', 'text', 'relations'):
            assert graph[field] == reduced[field]
        checks['input_anchor_layer_and_inventory_retention'] += 1
        coverage['synthetic_cases'] += 1
        coverage['contracted_vertices'] += removed
        coverage['cases_with_discontinuous_yields'] += any(
            max(y) - min(y) + 1 != len(y) for y in old['yields'].values())
        coverage['cases_with_extra_node_attributes'] += any(
            'scope' in node for node in graph['nodes'].values())
        coverage['cases_with_anchored_internal_vertices'] += any(
            old['children'][key] for key in graph['edu_order'])

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(reviewed['QuotientTests'])
    result = unittest.TestResult()
    suite.run(result)
    assert result.wasSuccessful(), str(result.failures + result.errors)
    assert module_hash == hashlib.sha256(module_path.read_bytes()).hexdigest()
    output = {
        'status': 'passed', 'scope': 'Synthetic implementation review only; no corpus replay or held-out validation',
        'seed': SEED, 'requested_cases': CASES,
        'reviewed_module': module_path.name, 'reviewed_module_sha256': module_hash,
        'coverage': dict(coverage), 'checks_passed': dict(checks),
        'reviewed_module_synthetic_tests_passed': result.testsRun,
        'resources': {
            'processes': 1, 'external_libraries': 0, 'external_models': 0,
            'address_space_limit_bytes': 512 * 1024 * 1024,
            'cpu_limit_seconds': 600,
            'wall_seconds': time.perf_counter() - wall_start,
            'cpu_seconds': time.process_time() - cpu_start,
            'peak_rss_KiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        'privacy': 'Only synthetic inputs and aggregate outcomes; no cache access, corpus rows, source annotations, or network',
        'limitations': [
            'Randomized checks are finite tests, not a proof or estimate of generalization',
            'Canonical comparison and structural validation reuse the reviewed module',
            'Sequential reduction uses a separately implemented eligibility rule and edge rewrite',
            'Seeded tree generation is deterministic; extra checks do not select features or tune rank sensitivity'
        ]}
    output_path = HERE / 'independent_randomized_review_results.json'
    output_path.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
