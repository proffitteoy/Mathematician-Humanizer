"""Standard-library scientific aggregate/allowlist check; no private inputs or models."""
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALLOWLIST = {
    'CHINESE_PILOT_REPORT.md', 'METHODS.md', 'README.md',
    'source/pilot_core.py', 'source/pilot_measure.py', 'source/pilot_evaluation.py',
    'source/test_scientific.py', 'source/MODEL_LOCK.json',
    'source/DEPENDENCY_LOCK.json', 'source/INSTRUMENT_LOCK.json',
    'results/DEV_AGGREGATE.json', 'results/DEV_MEASUREMENT.json',
    'results/TRAIN_MEASUREMENT.json', 'results/SELECTION_AGGREGATE.json',
    'verify_aggregate_release.py', 'RELEASE_MANIFEST.json',
}
SCIENTIFIC_HASHES = {
    'pilot_core.py': '15bf4d2f99417844f12350bea5987853bf5b0b1ae185835d74aa3f8de05e659c',
    'pilot_measure.py': '6a9060bff251b16f8c3ade911759e65a63f0daaf64bd840993bb6ab96bd60144',
    'pilot_evaluation.py': 'c956c32401534ce532baddd8cbb8086b05b05278253bf05f0c639c7e910ae8ae',
    'MODEL_LOCK.json': '8241b3b803c4b59ffb8879f5b4878063ab5e903921856993a89428a6bfad213e',
    'DEPENDENCY_LOCK.json': '366e53caa8c5a5e68b85302b9d268d6640b0524029c4c338b3787e9a568cbfe1',
    'INSTRUMENT_LOCK.json': 'c358b899b98167fd544e51e941c37b12ed3b0732a21c410780af448ae16e79c8',
}

def read(name):
    return json.loads((ROOT / name).read_bytes())

def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12), (a, b)

def main():
    actual = {str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file()}
    assert actual == ALLOWLIST, (actual - ALLOWLIST, ALLOWLIST - actual)
    manifest = read('RELEASE_MANIFEST.json')
    assert {i['path'] for i in manifest['files']} == ALLOWLIST - {'RELEASE_MANIFEST.json'}
    for item in manifest['files']:
        path = ROOT / item['path']
        assert not path.is_symlink()
        data = path.read_bytes()
        assert len(data) == item['bytes']
        assert hashlib.sha256(data).hexdigest() == item['sha256']
    for name, expected in SCIENTIFIC_HASHES.items():
        assert hashlib.sha256((ROOT / 'source' / name).read_bytes()).hexdigest() == expected
    result = read('results/DEV_AGGREGATE.json')
    selection = read('results/SELECTION_AGGREGATE.json')
    assert selection == {'audit': {'conflicting_source_components_excluded': 1,
        'selected_counts': {'dev|baike': 8, 'dev|web': 8, 'train|baike': 16, 'train|web': 16}}}
    assert result['dev_pairs'] == 16 and result['usable_dev_pairs'] == 16
    arms = {'baseline', 'baseline_slope', 'baseline_sd', 'baseline_slope_sd', 'length_source'}
    assert set(result['metrics']) == arms
    assert set(result['improvement']) == arms - {'baseline'}
    baseline = result['metrics']['baseline']['pooled']['log_loss']
    for arm, groups in result['metrics'].items():
        assert set(groups) == {'pooled', 'baike', 'web'}
        for measure in ('log_loss', 'brier'):
            close(groups['pooled'][measure], (groups['baike'][measure] + groups['web'][measure]) / 2)
        for group in groups.values():
            assert 0 <= group['auroc'] <= 1 and 0 <= group['brier'] <= 1 and group['log_loss'] >= 0
        if arm != 'baseline':
            gain = result['improvement'][arm]
            close(gain['mean'], baseline - groups['pooled']['log_loss'])
            close(gain['mean'], sum(gain['by_source'].values()) / 2)
            lo, hi = gain['fixed_train_pair_composition_95pct_range']
            assert lo <= hi
            for domain in ('baike', 'web'):
                close(gain['by_source'][domain], result['metrics']['baseline'][domain]['log_loss'] - groups[domain]['log_loss'])
    numeric = result['numerical_sensitivity']
    assert numeric['seeds'] == list(range(20261100, 20261120)) and len(numeric['gains']) == 20
    close(numeric['sd'], statistics.stdev(numeric['gains']))
    assert numeric['range'] == [min(numeric['gains']), max(numeric['gains'])]
    assert sum(x < 0 for x in numeric['gains']) == 1
    for phase, count, finite in (('TRAIN', 32, 31), ('DEV', 16, 16)):
        measured = read('results/' + phase + '_MEASUREMENT.json')
        assert measured['selected_pairs'] == count and measured['records'] == 2 * count
        assert measured['all_alignment_verified']
        assert sum(v['finite_topology_pairs'] for v in measured['paired_coverage'].values()) == finite
        for domain in ('baike', 'web'):
            key = phase.lower() + '|' + domain
            pair = measured['paired_coverage'][key]
            assert pair['selected_pairs'] == count // 2 and pair['verified_alignment_pairs'] == count // 2
            human = measured['groups'][key + '|human']; machine = measured['groups'][key + '|chatgpt']
            assert human['token_count'] == machine['token_count']
            for group in (human, machine):
                assert group['selected_arms'] == count // 2
                assert group['topology_available_arms'] == pair['finite_topology_pairs']
                assert group['distinct_scale_count_distribution'] == {'7': count // 2}
                assert sum(group['topology_reasons'].values()) == count // 2
    forbidden = {
        'window_text', 'encoded_input_ids', 'encoded_special_tokens_mask', 'aligned_content_ids',
        'rerun_slopes', 'schedule_means', 'coefficients', 'intercept', 'train_components', 'pair_id',
        'component_id', 'window_sha256', 'selection_sha256', 'selected_components_sha256',
        'protocol_sha256', 'wall_seconds', 'cpu_seconds', 'peak_tree_rss_bytes', 'approval',
        'resource_receipts', 'computed_asset_sha256_receipts', 'fit_sha256',
    }
    def check(value):
        if isinstance(value, dict):
            assert not (forbidden & set(value)), forbidden & set(value)
            for v in value.values(): check(v)
        elif isinstance(value, list):
            for v in value: check(v)
    for path in (ROOT / 'results').glob('*.json'):
        check(json.loads(path.read_bytes()))
    return {'status': 'PASS', 'scope': 'Scientific allowlist, source hashes and public aggregate arithmetic only',
            'private_measurements_or_coefficients_reconstructed': False}

if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
