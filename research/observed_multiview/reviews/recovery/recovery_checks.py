"""Read-only metadata/hash verification and independent synthetic DSU checks.

No corpus bodies, parser inputs, predictions or fitted artifacts are opened.
"""
import collections
import hashlib
import importlib.util
import json
import pathlib
import random
import sys

BASE = pathlib.Path('/workspace/shared')
OUT = BASE / 'style-scale10-recovery-audit-20261001/public'
PLAN = BASE / 'style-learning-pilot/scale10-plan-v03'
DIRECTORIES = [
    BASE / 'style-scale10-plan-review/public',
    BASE / 'style-fingerprint-review/public',
    PLAN,
    BASE / 'style-learning-pilot/exposure-fingerprints-v01',
]

def filehash(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')

manifest_checks = []
for directory in DIRECTORIES:
    manifest = json.loads((directory / 'FILE_HASHES.json').read_text())
    entries = manifest if isinstance(manifest, list) else [
        dict(file=k, **v) for k, v in manifest.items()]
    for entry in entries:
        path = directory / entry['file']
        assert path.stat().st_size == entry['bytes']
        assert filehash(path) == entry['sha256']
    manifest_checks.append(dict(directory=str(directory), entries=len(entries),
                                sha256=filehash(directory / 'FILE_HASHES.json')))

spec = importlib.util.spec_from_file_location('recovered_allocator', PLAN / 'sample_metadata.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
rng = random.Random(711092026)
trials = 300
for trial in range(trials):
    nodes = [m.wiki_member_key('wikimedia', ['zhwiki', 'zhwikinews', 'zhwikivoyage'][i % 3], str(i))
             for i in range(25)]
    edges = [(nodes[i], nodes[j]) for i in range(len(nodes))
             for j in range(i) if rng.random() < 0.035]
    hard, unresolved = edges[::2], edges[1::2]
    exposed = set(rng.sample(nodes, 4))
    graph = {n: set() for n in nodes}
    for a, b in edges:
        graph[a].add(b)
        graph[b].add(a)
    seen, expected_mapping, expected_exclusions = set(), {}, set()
    for node in nodes:
        if node in seen:
            continue
        queue, group = [node], {node}
        while queue:
            current = queue.pop()
            for neighbor in graph[current] - group:
                group.add(neighbor)
                queue.append(neighbor)
        seen.update(group)
        cid = hashlib.sha256(canonical(sorted(group))).hexdigest()
        expected_mapping.update({member: cid for member in group})
        if group & exposed:
            expected_exclusions.add(cid)
    # Every input may be one-shot; each execution receives a fresh iterable.
    for constructor in (list, set, lambda xs: (x for x in xs)):
        ordered = nodes[:]
        rng.shuffle(ordered)
        result = m.freeze_components(constructor(ordered), constructor(hard),
                                     constructor(unresolved), constructor(exposed))
        assert result == (expected_mapping, expected_exclusions)

wiki7 = m.wiki_member_key('wikiconv', 'zhwiki', '0007')
assert wiki7 == m.wiki_member_key('discussion', 'zhwiki', '7')
assert wiki7 == m.wiki_member_key('mediawiki', 'zhwiki', '07')
assert wiki7 != m.wiki_member_key('wikimedia', 'zhwikinews', '7')
try:
    m.wiki_member_key('unknown-alias', 'zhwiki', '7')
except ValueError:
    pass
else:
    raise AssertionError('unknown_alias_accepted')
new8 = m.wiki_member_key('mediawiki', 'zhwiki', '8')
new9 = m.wiki_member_key('mediawiki', 'zhwiki', '9')
old_map, _ = m.freeze_components([wiki7], [], [], [])
new_map, excluded = m.freeze_components([wiki7, new8, new9], iter([(wiki7, new8)]),
                                      iter([(new8, new9)]), iter([wiki7]))
assert old_map[wiki7] != new_map[wiki7]
assert len(set(new_map.values())) == 1 and excluded == {new_map[new9]}
try:
    m.freeze_components([new8], [], [], iter([wiki7]))
except ValueError:
    pass
else:
    raise AssertionError('missing_excluded_ancestor_accepted')

proposal = json.loads((PLAN / 'experiment-proposal.json').read_text())
assert proposal['schema_version'] == 'observed-multiview-scale10-proposal/0.3'
quotas = proposal['data']['quotas']
assert [sum(q[k] for q in quotas.values()) for k in ('train', 'development', 'test')] == [1280, 320, 320]
assert sum(proposal['data']['candidate_record_caps'].values()) == 6000
assert proposal['optimization']['fits'] == 18
assert proposal['optimization']['updates_max'] == 18 * 30 * (1280 // 32) == 21600
assert proposal['budgets']['parse_units_max'] == 1920 * 32 == 61440

result = {
    'schema_version': 'scale10-recovery-independent-checks/1',
    'verified_manifest_entries': sum(x['entries'] for x in manifest_checks),
    'manifests': manifest_checks,
    'independent_graph_trials': trials,
    'iterable_variants_per_graph': 3,
    'independent_graph_calls': trials * 3,
    'graph_failures': 0,
    'alias_namespace_changed_component_id_and_multihop_checks': 'pass',
    'missing_excluded_ancestor_rejected': True,
    'exact_protocol_version': proposal['schema_version'],
    'proposal_sha256': filehash(PLAN / 'experiment-proposal.json'),
    'protocol_sha256': filehash(PLAN / 'protocol.zh.md'),
    'fixed_training_record_target': 1280,
    'quota_guaranteed': False,
    'source_body_reads': 0,
    'parser_calls': 0,
    'fits': 0,
    'remote_writes': 0,
}
with (OUT / 'recovery-checks.aggregate.json').open('x') as f:
    f.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
