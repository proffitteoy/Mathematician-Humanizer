#!/usr/bin/env python3
"""Typed RS3 identity-bridge quotient; stdlib only; aggregate-only replay.
Private cache and original artifacts are read-only. The program writes no source,
per-document scores, graph, hash of sentence text, or reconstructed annotation.
This is retrospective feature development, not a parser or held-out benchmark.
"""
import argparse
import collections
import copy
import hashlib
import itertools
import json
import pathlib
import re
import resource
import statistics
import sys
import time
import unittest
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = pathlib.Path('/tmp/gcdt-validation-private')
RUN = ROOT / 'discourse_validation_run'
mean = statistics.mean


def normalized(text):
    return ''.join(text.split())


def spans(parts):
    output, start = [], 0
    for part in parts:
        end = start + len(normalized(part))
        output.append((start, end))
        start = end
    return output


def source_layout(xml_bytes, sentence_text):
    """Keep interval overlays, XML tag hierarchy and attrs; infer no block roles."""
    root = ET.fromstring(xml_bytes)
    raw = ''.join(root.itertext())
    text = normalized(raw)
    blocks = spans([p for p in re.split(r'\n\s*\n', raw) if normalized(p)])
    sentences = spans([p for p in sentence_text.splitlines() if normalized(p)])
    assert text == normalized(sentence_text), 'Source/sentence alignment failed'
    position = 0
    tags = []

    def walk(element, path):
        nonlocal position
        start = position
        ix = len(tags)
        tags.append(None)
        position += len(normalized(element.text or ''))
        for child_index, child in enumerate(element):
            walk(child, path + (child_index,))
            position += len(normalized(child.tail or ''))
        tags[ix] = (path, element.tag, start, position,
                    tuple(sorted(element.attrib.items())))

    walk(root, ())
    assert position == len(text)
    return {'text': text, 'blocks': blocks, 'sentences': sentences,
            'typed_xml_overlays': tags}


def read_rs3(raw):
    root = ET.fromstring(raw)
    assert root.tag == 'rst' and not root.attrib, 'Unsupported RS3 document metadata'
    assert [e.tag for e in root] == ['header', 'body'], 'Unsupported RS3 document structure'
    header, body = root.find('header'), root.find('body')
    assert not header.attrib and not body.attrib, 'Unsupported RS3 container metadata'
    assert [e.tag for e in header] == ['relations'], 'Unsupported RS3 header metadata'
    relation_elements = header.find('relations')
    assert all(not normalized(e.text or '') and
               all(not normalized(child.tail or '') for child in e)
               for e in (root, header, relation_elements, body)), 'Unsupported RS3 container text'
    assert not relation_elements.attrib, 'Unsupported RS3 inventory metadata'
    assert all(r.tag == 'rel' and set(r.attrib) == {'name', 'type'} and len(r) == 0 and not normalized(r.text or '')
               for r in relation_elements), 'Unsupported RS3 relation metadata'
    relations = {r.attrib['name']: r.attrib['type'] for r in relation_elements}
    assert len(relations) == len(relation_elements), 'Duplicate relation names'
    nodes, order, edu_text = {}, [], []
    for element in root.find('body'):
        assert element.tag in ('segment', 'group') and len(element) == 0, 'Unsupported RS3 node markup'
        if element.tag == 'group':
            assert not normalized(element.text or ''), 'Unsupported RS3 group text'
        attrs = dict(element.attrib)
        node_id = attrs.pop('id')
        assert node_id not in nodes
        nodes[node_id] = {'kind': element.tag, **attrs}
        if element.tag == 'segment':
            order.append(node_id)
            edu_text.append(normalized(''.join(element.itertext())))
    graph = {'nodes': nodes, 'edu_order': order, 'edu_spans': spans(edu_text),
             'text': ''.join(edu_text), 'relations': relations}
    structure(graph)
    return graph


def role(node, relations):
    if 'parent' not in node:
        return 'ROOT'
    rel = node.get('relname')
    if rel == 'span' or relations.get(rel) == 'multinuc':
        return 'N'
    if relations.get(rel) == 'rst':
        return 'S'
    return 'unknown'


def structure(graph):
    nodes = graph['nodes']
    edu_spans = graph['edu_spans']
    assert len(edu_spans) == len(graph['edu_order']) and edu_spans
    assert edu_spans[0][0] == 0 and edu_spans[-1][1] == len(graph['text'])
    assert all(a < b for a, b in edu_spans), 'Nonpositive EDU width'
    assert all(edu_spans[i][1] == edu_spans[i + 1][0]
               for i in range(len(edu_spans) - 1)), 'Nonpartition EDU coordinates'
    children = {k: [] for k in nodes}
    roots = []
    for key, node in nodes.items():
        if 'parent' not in node:
            assert 'relname' not in node, 'Unsupported incoming relation on root'
            roots.append(key)
        else:
            assert node['parent'] in nodes
            children[node['parent']].append(key)
    assert len(roots) == 1
    anchor = {key: i for i, key in enumerate(graph['edu_order'])}
    assert len(anchor) == len(graph['edu_order'])
    assert {k for k, n in nodes.items() if n['kind'] == 'segment'} == set(anchor)
    yields, paths, depth, seen = {}, {}, {}, set()

    def walk(key, path):
        assert key not in seen, 'Cycle or repeated tree vertex'
        seen.add(key)
        paths[key] = path + (key,)
        depth[key] = len(path)
        result = {anchor[key]} if key in anchor else set()
        for child in children[key]:
            new_yield = walk(child, path + (key,))
            assert not result.intersection(new_yield)
            result.update(new_yield)
        assert result, 'Empty carrier'
        yields[key] = tuple(sorted(result))
        return result

    assert walk(roots[0], ()) == set(range(len(anchor)))
    assert seen == set(nodes), 'Disconnected graph'
    for key in children:
        children[key].sort(key=lambda child: min(yields[child]))
    return {'root': roots[0], 'children': children, 'yields': yields,
            'paths': paths, 'depth': depth, 'anchor': anchor}


def identity_candidates(graph, st=None):
    st = st or structure(graph)
    allowed = {'kind', 'type', 'parent', 'relname'}
    return {key for key, node in graph['nodes'].items()
            if node['kind'] == 'group' and node.get('type') == 'span'
            and not (set(node) - allowed)
            and len(st['children'][key]) == 1
            and graph['nodes'][st['children'][key][0]].get('relname') == 'span'}


def quotient(graph):
    """One pass removes exactly the certified maximal identity chains."""
    st = structure(graph)
    removable = identity_candidates(graph, st)
    result = copy.deepcopy(graph)
    old = graph['nodes']
    result['nodes'] = {}
    projection = {}
    for key in old:
        endpoint = key
        while endpoint in removable:
            endpoint = st['children'][endpoint][0]
        projection[key] = endpoint
    for key, original in old.items():
        if key in removable:
            continue
        node = dict(original)
        parent = node.get('parent')
        incoming = node.get('relname')
        while parent in removable:
            incoming = old[parent].get('relname')
            parent = old[parent].get('parent')
        for field in ('parent', 'relname'):
            node.pop(field, None)
        if parent is not None:
            node['parent'] = parent
            if incoming is not None:
                node['relname'] = incoming
        result['nodes'][key] = node
    reduced = structure(result)
    assert not identity_candidates(result, reduced)
    assert all(st['yields'][key] == reduced['yields'][projection[key]] for key in old)
    return result, projection, len(removable)


def canonical(graph, layout=None):
    """Full typed quotient key, with ID-free deterministic root-path IDs."""
    graph = quotient(graph)[0]
    st = structure(graph)
    records = []

    def walk(key, path):
        node = graph['nodes'][key]
        attrs = tuple(sorted((k, v) for k, v in node.items()
                             if k not in ('parent', 'relname')))
        records.append((path, attrs, st['anchor'].get(key),
                        node.get('relname'), role(node, graph['relations'])))
        for index, child in enumerate(st['children'][key]):
            walk(child, path + (index,))

    walk(st['root'], ())
    result = (tuple(records), tuple(graph['edu_spans']), graph['text'],
              tuple(sorted(graph['relations'].items())))
    # Source layer can be large/private. It is compared in memory, never exported.
    return result + (json.dumps(layout, sort_keys=True),) if layout is not None else result


def expand_identity_bridges(graph, repeats=1):
    """Deterministic stress encoding, not a new semantic annotation."""
    result = copy.deepcopy(graph)
    counter = 0
    for _ in range(repeats):
        originals = list(result['nodes'])
        for key in originals:
            child = result['nodes'][key]
            new_id = '__identity_%s' % counter
            counter += 1
            assert new_id not in result['nodes']
            wrapper = {'kind': 'group', 'type': 'span'}
            for field in ('parent', 'relname'):
                if field in child:
                    wrapper[field] = child[field]
            child['parent'] = new_id
            child['relname'] = 'span'
            result['nodes'][new_id] = wrapper
    return result


def relabel_and_reorder(graph):
    result = copy.deepcopy(graph)
    old = graph['nodes']
    names = {key: 'renamed_%d' % i for i, key in enumerate(reversed(list(old)))}
    result['nodes'] = {}
    for key in reversed(list(old)):
        node = dict(old[key])
        if 'parent' in node:
            node['parent'] = names[node['parent']]
        result['nodes'][names[key]] = node
    result['edu_order'] = [names[key] for key in graph['edu_order']]
    return result


def nonspan_labels(graph):
    return collections.Counter((n.get('relname'), graph['relations'].get(n.get('relname')),
                                role(n, graph['relations']))
                               for n in graph['nodes'].values()
                               if 'parent' in n and n.get('relname') != 'span')


def carrier_type(node, anchor):
    # Extra attrs deliberately remain semantic and inhibit identity contraction.
    attrs = tuple(sorted((k, v) for k, v in node.items()
                         if k not in ('parent', 'relname')))
    return attrs, anchor


def counters(graph):
    st = structure(graph)
    typed = {key: (st['yields'][key], carrier_type(node, st['anchor'].get(key)))
             for key, node in graph['nodes'].items()}
    carriers = collections.Counter(typed.values())
    scopes = collections.Counter()
    for key, node in graph['nodes'].items():
        if 'parent' not in node or node.get('relname') == 'span':
            continue
        scopes[(typed[key], typed[node['parent']], node.get('relname'),
                graph['relations'].get(node.get('relname')), role(node, graph['relations']))] += 1
    return {'typed_carrier': carriers, 'relation_scope': scopes}


def lca(st, left, right):
    common = [a for a, b in itertools.takewhile(lambda ab: ab[0] == ab[1],
                                                zip(st['paths'][left], st['paths'][right]))]
    assert common
    return common[-1]


def features(graph, layout):
    st = structure(graph)
    nodes = graph['nodes']
    n = len(graph['edu_order'])
    groups = [k for k, node in nodes.items() if node['kind'] == 'group']
    def crosses(key):
        return sum(any(a < graph['edu_spans'][i][1] and graph['edu_spans'][i][0] < b
                       for i in st['yields'][key]) for a, b in layout['blocks']) > 1
    depth = [st['depth'][key] for key in graph['edu_order']]
    boundary_depth, merge_fraction, straddles = [], [], 0
    for _, boundary in layout['blocks'][:-1]:
        left = max(i for i, (a, b) in enumerate(graph['edu_spans']) if a < boundary)
        right = min(i for i, (a, b) in enumerate(graph['edu_spans']) if b > boundary)
        if left == right:
            straddles += 1
            continue
        parent = lca(st, graph['edu_order'][left], graph['edu_order'][right])
        boundary_depth.append(st['depth'][parent])
        merge_fraction.append(len(st['yields'][parent]) / n)
    labelled = [node for node in nodes.values()
                  if 'parent' in node and node.get('relname') != 'span'
                  and graph['relations'].get(node.get('relname')) in ('rst', 'multinuc')]
    unknown = sum('parent' in node and role(node, graph['relations']) == 'unknown'
                  for node in nodes.values())
    measured = {
        'mean_edu_attachment_depth': mean(depth),
        'mean_block_boundary_lca_depth': mean(boundary_depth) if boundary_depth else None,
        'group_source_block_crossing_fraction': sum(crosses(k) for k in groups) / len(groups) if groups else None,
        'mean_block_boundary_lca_yield_fraction': mean(merge_fraction) if merge_fraction else None,
        'labelled_attachment_satellite_share': sum(role(node, graph['relations']) == 'S' for node in labelled) / len(labelled) if labelled else None,
    }
    diagnostics = {'nodes': len(nodes), 'groups': len(groups),
                   'nonspan_known_type_edges': len(labelled), 'unknown_role_edges': unknown,
                   'block_boundaries': len(layout['blocks']) - 1,
                   'aligned_block_boundaries': len(merge_fraction),
                   'straddled_block_boundaries': straddles}
    return measured, diagnostics


def overlap(a, b):
    na, nb = sum(a.values()), sum(b.values())
    matched = sum((a & b).values())
    return {'reference_count': na, 'alternate_count': nb, 'matched': matched,
            'f1': 2 * matched / (na + nb) if na + nb else 1.0}


def rank_changes(pairs):
    result = collections.Counter(flips=0, tie_changes=0, unchanged=0)
    for (a, b), (c, d) in itertools.combinations(pairs, 2):
        x, y = a - c, b - d
        if x * y < 0:
            result['flips'] += 1
        elif (x == 0) != (y == 0):
            result['tie_changes'] += 1
        else:
            result['unchanged'] += 1
    return dict(result)


def toy(nodes, count):
    return {'nodes': nodes, 'edu_order': [str(i) for i in range(count)],
            'edu_spans': [(i, i + 1) for i in range(count)],
            'text': ''.join(chr(65 + i) for i in range(count)),
            'relations': {'evidence': 'rst', 'joint': 'multinuc'}}


def binary_toy():
    return toy({'0': {'kind': 'segment', 'parent': 'r', 'relname': 'span'},
                '1': {'kind': 'segment', 'parent': 'r', 'relname': 'evidence'},
                'r': {'kind': 'group', 'type': 'span'}}, 2)


class QuotientTests(unittest.TestCase):
    def test_identity_invariance_and_idempotence(self):
        g = binary_toy()
        wrapped = expand_identity_bridges(g, 3)
        self.assertEqual(canonical(g), canonical(wrapped))
        q = quotient(wrapped)[0]
        self.assertEqual(q, quotient(q)[0])
        self.assertEqual(nonspan_labels(g), nonspan_labels(wrapped))

    def test_ids_and_node_declaration_order(self):
        g = binary_toy()
        self.assertEqual(canonical(g), canonical(relabel_and_reorder(g)))

    def test_native_depth_is_not_invariant(self):
        g = binary_toy()
        h = expand_identity_bridges(g)
        self.assertEqual([structure(g)['depth'][e] for e in g['edu_order']], [1, 1])
        self.assertEqual([structure(h)['depth'][e] for e in h['edu_order']], [3, 3])
        self.assertEqual(canonical(g), canonical(h))

    def test_group_fraction_is_not_invariant(self):
        g = binary_toy()
        h = copy.deepcopy(g)
        h['nodes']['w'] = {'kind': 'group', 'type': 'span', 'parent': 'r', 'relname': 'evidence'}
        h['nodes']['1'].update(parent='w', relname='span')
        layout = {'blocks': [(0, 1), (1, 2)]}
        self.assertEqual(features(g, layout)[0]['group_source_block_crossing_fraction'], 1.0)
        self.assertEqual(features(h, layout)[0]['group_source_block_crossing_fraction'], 0.5)
        self.assertEqual(canonical(g), canonical(h))

    def test_nuclearity_swap_is_semantic(self):
        g = binary_toy()
        h = copy.deepcopy(g)
        h['nodes']['0']['relname'], h['nodes']['1']['relname'] = 'evidence', 'span'
        self.assertNotEqual(canonical(g), canonical(h))
        self.assertEqual(set(structure(g)['yields'].values()), set(structure(h)['yields'].values()))
        self.assertEqual(nonspan_labels(g), nonspan_labels(h))
        self.assertNotEqual(counters(quotient(g)[0])['relation_scope'], counters(quotient(h)[0])['relation_scope'])

    def test_multinuclear_flattening_is_semantic(self):
        flat = toy({'0': {'kind': 'segment', 'parent': 'r', 'relname': 'joint'},
                    '1': {'kind': 'segment', 'parent': 'r', 'relname': 'joint'},
                    '2': {'kind': 'segment', 'parent': 'r', 'relname': 'joint'},
                    'r': {'kind': 'group', 'type': 'multinuc'}}, 3)
        nested = copy.deepcopy(flat)
        nested['nodes']['m'] = {'kind': 'group', 'type': 'multinuc', 'parent': 'r', 'relname': 'joint'}
        for key in ('0', '1'):
            nested['nodes'][key]['parent'] = 'm'
        self.assertNotEqual(canonical(flat), canonical(nested))
        self.assertEqual(sum(nonspan_labels(flat).values()), 3)
        self.assertEqual(sum(nonspan_labels(nested).values()), 4)
        fs, ns = structure(flat), structure(nested)
        self.assertEqual(len(fs['yields'][lca(fs, '0', '1')]), 3)
        self.assertEqual(len(ns['yields'][lca(ns, '0', '1')]), 2)

    def test_relation_bearing_or_typed_unary_node_stays(self):
        g = binary_toy()
        h = expand_identity_bridges(g)
        for key in list(identity_candidates(h)):
            h['nodes'][key]['semantic_scope'] = 'explicit'
        self.assertEqual(quotient(h)[2], 0)
        h = binary_toy()
        h['nodes']['w'] = {'kind': 'group', 'type': 'span', 'parent': 'r', 'relname': 'span'}
        h['nodes']['0'].update(parent='w', relname='evidence')
        self.assertNotIn('w', identity_candidates(h))

    def test_layout_type_change_is_not_equivalent(self):
        g = binary_toy()
        a = source_layout(b'<text><section>A</section>\n\nB</text>', 'A\nB')
        b = source_layout(b'<text><list>A</list>\n\nB</text>', 'A\nB')
        self.assertEqual(a['text'], b['text'])
        self.assertEqual(a['blocks'], b['blocks'])
        self.assertNotEqual(canonical(g, a), canonical(g, b))

    def test_xml_attribute_order_and_escaping(self):
        a = source_layout(b'<text x="one" y="two">A&amp;B</text>', 'A&B')
        b = source_layout(b'<text y="two" x="one">A&#38;B</text>', 'A&B')
        self.assertEqual(a, b)

    def test_edu_order_not_discarded(self):
        g = binary_toy()
        h = copy.deepcopy(g)
        h['edu_order'] = list(reversed(h['edu_order']))
        self.assertNotEqual(canonical(g), canonical(h))

    def test_segment_anchor_with_dependents_is_retained(self):
        anchored = toy({'0': {'kind': 'segment'},
                        '1': {'kind': 'segment', 'parent': '0', 'relname': 'evidence'}}, 2)
        wrapped = expand_identity_bridges(anchored, 2)
        self.assertEqual(canonical(anchored), canonical(wrapped))
        self.assertEqual(quotient(wrapped)[0]['nodes']['0']['kind'], 'segment')

    def test_unsupported_metadata_and_duplicate_inventory_rejected(self):
        base = '<rst><header><relations><rel name="joint" type="multinuc"/></relations></header><body><segment id="0">A</segment></body></rst>'
        self.assertEqual(len(read_rs3(base.encode())['nodes']), 1)
        bad = [base.replace('<rst>', '<rst custom="role">'),
               base.replace('<relations>', '<metadata/><relations>'),
               base.replace('</relations>', '<rel name="joint" type="rst"/></relations>'),
               base.replace('id="0"', 'id="0" relname="span"'),
               base.replace('>A</segment>', '></segment>')]
        for xml in bad:
            with self.assertRaises(AssertionError):
                read_rs3(xml.encode())

    def test_straddled_boundary_is_missing_not_self_lca(self):
        g = binary_toy()
        g.update(edu_spans=[(0, 2), (2, 4)], text='AABB')
        measured, diag = features(g, {'blocks': [(0, 1), (1, 4)]})
        self.assertIsNone(measured['mean_block_boundary_lca_yield_fraction'])
        self.assertEqual(diag['straddled_block_boundaries'], 1)


def run(output):
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (600, 600))
    start, cpu = time.perf_counter(), time.process_time()
    original_dirs = [RUN, ROOT / 'discourse-independent-audit']
    def original_hashes():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in original_dirs for p in folder.rglob('*') if p.is_file()}
    unchanged = original_hashes()
    frozen = json.loads((RUN / 'freeze.json').read_text())
    assert all(hashlib.sha256((RUN / name).read_bytes()).hexdigest() == expected
               for name, expected in frozen['sha256'].items()), 'Original frozen code hash mismatch'
    logs = json.loads((RUN / 'download_log.json').read_text())
    for entry in logs:
        data = (CACHE / entry['path']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry['sha256']
        assert len(data) == entry['bytes']
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == entry['git_blob_sha']
    manifest = json.loads((ROOT / 'research_discourse_validation/minimal_gcdt_manifest.json').read_text())
    synthetic = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(QuotientTests).run(synthetic)
    assert synthetic.wasSuccessful(), str(synthetic.failures + synthetic.errors)
    totals = collections.Counter()
    primary_structure = collections.Counter()
    group_totals = {'primary': collections.Counter(), 'alternate': collections.Counter()}
    sensitivity = collections.defaultdict(list)
    agreements = collections.defaultdict(list)
    primary_ranges = collections.defaultdict(list)
    relations_primary = collections.Counter()
    relation_total_variation = []
    source_tags = collections.Counter()
    equivalence_checks = collections.Counter()
    paired_equality = 0
    for doc in manifest['documents']:
        layout = source_layout((CACHE / doc['files']['xml']['path']).read_bytes(),
                               (CACHE / doc['files']['tokenized']['path']).read_text())
        source_tags.update(record[1] for record in layout['typed_xml_overlays'] if record[0])
        graphs = [read_rs3((CACHE / doc['files']['rs3']['path']).read_bytes())]
        if doc['double_rst_paths']:
            graphs.append(read_rs3((CACHE / doc['double_rst_paths'][0]).read_bytes()))
        totals.update(documents=1, sentences=len(layout['sentences']),
                      source_blocks=len(layout['blocks']), primary_edus=len(graphs[0]['edu_order']))
        qgraphs, measured = [], []
        for index, graph in enumerate(graphs):
            assert graph['text'] == layout['text']
            qgraph, projection, removed = quotient(graph)
            qgraphs.append(qgraph)
            full = canonical(graph, layout)
            assert full == canonical(qgraph, layout)
            assert quotient(qgraph)[0] == qgraph
            assert full == canonical(relabel_and_reorder(graph), layout)
            expanded = expand_identity_bridges(graph, 2)
            assert full == canonical(expanded, layout)
            assert nonspan_labels(graph) == nonspan_labels(qgraph)
            assert graph['edu_spans'] == qgraph['edu_spans']
            assert graph['edu_order'] == qgraph['edu_order']
            assert graph['relations'] == qgraph['relations']
            assert graph['text'] == qgraph['text']
            f, diag = features(qgraph, layout)
            totals.update(unknown_role_edges=diag['unknown_role_edges'])
            assert f == features(quotient(expanded)[0], layout)[0]
            assert counters(qgraph) == counters(quotient(expanded)[0])
            native_f = features(graph, layout)[0]
            assert native_f['mean_block_boundary_lca_yield_fraction'] == f['mean_block_boundary_lca_yield_fraction']
            assert native_f['labelled_attachment_satellite_share'] == f['labelled_attachment_satellite_share']
            measured.append(f)
            totals.update(graphs=1, native_vertices=len(graph['nodes']),
                          quotient_vertices=len(qgraph['nodes']), removed_identity_bridges=removed)
            equivalence_checks.update(idempotence=1, id_and_declaration_order=1,
                                      double_wrapper_expansion=1, complete_source_retention=1,
                                      nonspan_label_and_role_retention=1,
                                      features_and_scope_signatures=1,
                                      surviving_yield_retention=1)
            which = 'primary' if index == 0 else 'alternate'
            if len(graphs) == 2:
                group_totals[which].update(diag)
                group_totals[which].update(removed_identity_bridges=removed)
            if index == 0:
                primary_structure.update(diag)
                relations_primary.update(nonspan_labels(qgraph))
                for key, value in f.items():
                    if value is not None:
                        primary_ranges[key].append(value)
        if len(graphs) == 2:
            totals.update(paired_documents=1)
            assert graphs[0]['edu_spans'] == graphs[1]['edu_spans']
            paired_equality += canonical(qgraphs[0], layout) == canonical(qgraphs[1], layout)
            for key in measured[0]:
                a, b = measured[0][key], measured[1][key]
                if a is not None and b is not None:
                    sensitivity[key].append((a, b))
            cs = [counters(q) for q in qgraphs]
            for key in cs[0]:
                agreements[key].append(overlap(cs[0][key], cs[1][key]))
            histograms = [nonspan_labels(q) for q in qgraphs]
            ha, hb = histograms
            na, nb = sum(ha.values()), sum(hb.values())
            relation_total_variation.append(sum(abs(ha[k] / na - hb[k] / nb)
                                                for k in ha.keys() | hb.keys()) / 2)
    agreement_summary = {}
    for key, scores in agreements.items():
        aggregate = {field: sum(row[field] for row in scores)
                     for field in ('reference_count', 'alternate_count', 'matched')}
        agreement_summary[key] = {
            'paired_documents': len(scores), 'macro_f1': mean(row['f1'] for row in scores),
            'pooled_f1': 2 * aggregate['matched'] / (aggregate['reference_count'] + aggregate['alternate_count']),
            **aggregate}
    paired_summary = {key: {'paired_documents': len(pairs),
                           'macro_absolute_difference': mean(abs(a - b) for a, b in pairs),
                           'maximum_absolute_difference': max(abs(a - b) for a, b in pairs),
                           **rank_changes(pairs)} for key, pairs in sensitivity.items()}
    assert unchanged == original_hashes(), 'Original artifacts changed'
    output_data = {
        'scope': 'Retrospective definition development on 10 already exposed documents; no held-out, quality, parser, or human/AI claim',
        'version': 'typed-identity-bridge-quotient-v1',
        'dataset_commit': manifest['commit'],
        'totals': dict(totals),
        'verification': {'synthetic_tests_passed': synthetic.testsRun,
                         'cached_input_hashes_verified': len(logs),
                         'original_recorded_frozen_hashes_verified': len(frozen['sha256']),
                         'original_artifact_hashes_unchanged': True,
                         'all_graph_checks': dict(equivalence_checks)},
        'primary_quotient_denominators': dict(primary_structure),
        'paired_quotient_denominators': {key: dict(value) for key, value in group_totals.items()},
        'paired_canonical_tree_equal_count': paired_equality,
        'paired_sensitivity': paired_summary,
        'paired_signature_overlap': agreement_summary,
        'nonspan_label_distribution_total_variation': {
            'paired_documents': len(relation_total_variation),
            'macro': mean(relation_total_variation), 'maximum': max(relation_total_variation)},
        'primary_macro_summaries': {key: {'documents': len(values), 'mean': mean(values),
                                        'minimum': min(values), 'maximum': max(values)}
                                    for key, values in primary_ranges.items()},
        'primary_nonspan_relation_events': [{'label': label, 'inventory_type': kind,
                                           'derived_role': nuclearity, 'events': count}
                                          for (label, kind, nuclearity), count in sorted(relations_primary.items())],
        'source_xml_tag_totals': dict(source_tags),
        'resources': {'wall_seconds': time.perf_counter() - start,
                      'cpu_seconds': time.process_time() - cpu,
                      'peak_rss_KiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      'processes': 1, 'external_models': 0},
        'limitations': ['Only five paired documents; ten rank comparisons are dependent',
                        'Contraction justified only under declared identity-bridge convention',
                        'Remaining variation includes annotation and unremoved encoding choices',
                        'Relation scope signature overlap is not graph-isomorphism or Parseval',
                        'Source blocks and tags are not validated semantic paragraph types',
                        'Released paired segmentation is common; zero source-layer difference is not segmenter accuracy'],
        'privacy': 'Aggregate-only; no per-document rows, source text, sentence hashes, full annotations, or paragraph vectors'}
    pathlib.Path(output).write_text(json.dumps(output_data, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({key: output_data[key] for key in ['totals', 'verification', 'paired_sensitivity',
                                                     'paired_signature_overlap', 'resources']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(HERE / 'aggregate_results.json'))
    parser.add_argument('--synthetic-only', action='store_true')
    args = parser.parse_args()
    if args.synthetic_only:
        unittest.main(argv=[sys.argv[0]])
    else:
        run(args.output)
