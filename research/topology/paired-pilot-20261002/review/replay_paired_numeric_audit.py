#!/usr/bin/env python3
"""Read-only replay of saved paired-pilot numeric outputs.

No text, tokenizer, encoder, model weights, embedding arrays, estimator subset
sampling, replacement observations, or classifier fitting is required. The only
bootstrap is deterministic replay of the original seed and 10,000 replicates.
Output contains aggregate diagnostics, never per-document IDs or source hashes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

BOOTSTRAPS = 10000
BOOTSTRAP_SEED = 20261004
PROFILES = [
    ('original_window', 'notebook_seed_20261002'),
    ('original_window', 'notebook_seed_20261003'),
    ('original_window', 'paper_prose_seed_20261002'),
    ('matched_reencoded', 'notebook_seed_20261002'),
    ('matched_reencoded', 'notebook_seed_20261003'),
]

def check_equal(actual, expected):
    assert np.allclose(actual, expected, rtol=1e-12, atol=1e-12), (actual, expected)

def value(report):
    return 1.0 / (1.0 - report['mean_slope'])

def select(records, condition, profile, domain='pooled', guard='saved', margin=.001, eligible=None):
    rows = []
    for index, record in enumerate(records):
        if domain != 'pooled' and record['domain'] != domain:
            continue
        if eligible is not None and index not in eligible:
            continue
        reports = [record['texts'][label]['conditions'][condition]['phd'][profile]
                   for label in ('human', 'ai')]
        def valid(report):
            if guard == 'saved':
                return report['status'] == 'ok'
            if guard == 'none':
                return True
            mean = report['mean_slope']
            slopes = np.array([run['slope'] for run in report['runs']])
            return (0 <= mean < 1 - margin and
                    (guard == 'mean' or bool(np.all((slopes >= 0) & (slopes < 1 - margin)))))
        if all(valid(report) for report in reports):
            rows.append((index, record['domain'], value(reports[0]), value(reports[1])))
    return rows

def summarize(rows, bootstrap=False):
    human = np.array([row[2] for row in rows])
    ai = np.array([row[3] for row in rows])
    diff = human - ai
    result = {
        'n_pairs': len(rows), 'human_mean': float(human.mean()), 'ai_mean': float(ai.mean()),
        'paired_mean_gap': float(diff.mean()), 'paired_median_gap': float(np.median(diff)),
        'human_gt_ai_pairs': int((diff > 0).sum()),
        'human_positive_auroc': float(((human[:, None] > ai[None, :]) +
                                      .5 * (human[:, None] == ai[None, :])).mean()),
    }
    if bootstrap:
        # Recreate exactly the original pair-unit/domain-stratified index schedule.
        groups = [np.array([i for i, row in enumerate(rows) if row[1] == domain])
                  for domain in sorted({row[1] for row in rows})]
        rng = np.random.default_rng(BOOTSTRAP_SEED)
        ids = np.concatenate([group[rng.integers(0, len(group), size=(BOOTSTRAPS, len(group)))]
                              for group in groups], axis=1)
        result['paired_gap_95pct_percentile_interval'] = np.quantile(diff[ids].mean(axis=1), [.025, .975]).tolist()
        h, a = human[ids], ai[ids]
        aucs = ((h[:, :, None] > a[:, None, :]) + .5 * (h[:, :, None] == a[:, None, :])).mean(axis=(1, 2))
        result['auroc_95pct_percentile_interval'] = np.quantile(aucs, [.025, .975]).tolist()
    return result

def compare_summary(got, expected):
    mapping = {
        'n_pairs': 'n_available_pairs', 'human_mean': 'human_mean', 'ai_mean': 'ai_mean',
        'paired_mean_gap': 'paired_mean_difference_human_minus_ai',
        'paired_median_gap': 'paired_median_difference_human_minus_ai',
        'human_gt_ai_pairs': 'human_gt_ai_pairs',
        'human_positive_auroc': 'descriptive_human_positive_auroc',
        'paired_gap_95pct_percentile_interval': 'paired_difference_95pct_bootstrap',
        'auroc_95pct_percentile_interval': 'auroc_95pct_paired_bootstrap',
    }
    for actual_key, expected_key in mapping.items():
        check_equal(got[actual_key], expected[expected_key])

def audit(source, expected_summary=None, expected_unguarded=None):
    raw = source.read_bytes()
    result = json.loads(raw)
    records = result['records']
    if expected_summary is not None:
        assert expected_summary['results_sha256'] == hashlib.sha256(raw).hexdigest()
    assert result['status'] == 'completed' and len(records) == 32
    assert sorted(record['domain'] for record in records).count('wikip') == 16
    assert sorted(record['domain'] for record in records).count('reddit') == 16
    errors = dict(median=0., slope=0., dimension=0.)
    reports_replayed, unavailable_reports = 0, 0
    failure_token_counts = []
    for record in records:
        assert record['matched_n'] == min(256, *(record['texts'][label]['untruncated_content_tokens'] for label in ('human', 'ai')))
        for text in record['texts'].values():
            assert text['conditions']['matched_reencoded']['content_tokens'] == record['matched_n']
            for condition, metadata in text['conditions'].items():
                for profile, report in metadata['phd'].items():
                    reports_replayed += 1
                    n = report['n_points']
                    assert n == metadata['content_tokens'] and report['ambient_dimension'] == 768
                    if profile.startswith('notebook'):
                        step = (n - 40) // 7
                        grid = list(range(40, n - step, step))
                    else:
                        grid = np.rint(np.linspace(40, n, 8)).astype(int).tolist()
                    assert report['sample_sizes'] == grid and len(report['runs']) == 3
                    x = np.log(np.array(grid)); centered = x - x.mean()
                    slopes = []
                    for run in report['runs']:
                        for size, energies in zip(grid, run['draw_energies']):
                            expected_draws = 7 if profile.startswith('paper') else (3 if n <= 2 * size else 9)
                            assert len(energies) == expected_draws
                        medians = np.array([np.median(energies) for energies in run['draw_energies']])
                        check_equal(medians, run['median_energies'])
                        errors['median'] = max(errors['median'], float(np.max(np.abs(medians - run['median_energies']))))
                        y = np.log(medians)
                        slope = float(centered @ (y - y.mean()) / (centered @ centered))
                        check_equal(slope, run['slope'])
                        check_equal(float(y.mean() - slope * x.mean()), run['intercept'])
                        errors['slope'] = max(errors['slope'], abs(slope - run['slope']))
                        slopes.append(slope)
                    check_equal(np.mean(slopes), report['mean_slope'])
                    passes = 0 <= np.mean(slopes) < .999 and min(slopes) >= 0 and max(slopes) < .999
                    assert passes == (report['status'] == 'ok')
                    if passes:
                        check_equal(value(report), report['dimension'])
                        errors['dimension'] = max(errors['dimension'], abs(value(report) - report['dimension']))
                    else:
                        unavailable_reports += 1
                        failure_token_counts.append(n)
    guarded, unguarded = {}, {}
    for condition, profile in PROFILES:
        key = condition + '/' + profile
        guarded[key] = {domain: summarize(select(records, condition, profile, domain), True)
                        for domain in ('wikip', 'reddit', 'pooled')}
        if expected_summary is not None:
            for domain, row in guarded[key].items():
                compare_summary(row, expected_summary['summaries'][key][domain])
    guard_diagnostics, seed_diagnostics = {}, {}
    for condition in ('original_window', 'matched_reencoded'):
        unguarded[condition] = {domain: summarize(select(records, condition, 'notebook_seed_20261002', domain, 'none'), True)
                               for domain in ('wikip', 'reddit', 'pooled')}
        if expected_unguarded is not None:
            for domain, row in unguarded[condition].items():
                compare_summary(row, expected_unguarded['summaries'][condition][domain])
        guard_diagnostics[condition] = {
            guard: {str(margin): summarize(select(records, condition, 'notebook_seed_20261002', guard=guard, margin=margin))
                    for margin in (0, .0001, .001, .005, .01, .02, .05)}
            for guard in ('any', 'mean')
        }
        one = select(records, condition, 'notebook_seed_20261002')
        two = select(records, condition, 'notebook_seed_20261003')
        common = {row[0] for row in one} & {row[0] for row in two}
        a = select(records, condition, 'notebook_seed_20261002', eligible=common)
        b = select(records, condition, 'notebook_seed_20261003', eligible=common)
        shifts, passing_shifts, maximum = [], [], None
        for record in records:
            for label, text in record['texts'].items():
                p = text['conditions'][condition]['phd']['notebook_seed_20261002']
                q = text['conditions'][condition]['phd']['notebook_seed_20261003']
                shift = abs(value(p) - value(q)); shifts.append(shift)
                if p['status'] == q['status'] == 'ok':
                    passing_shifts.append(shift)
                if maximum is None or shift > maximum['absolute_shift']:
                    maximum = {'domain': record['domain'], 'label': label, 'content_tokens': p['n_points'],
                               'absolute_shift': shift, 'seed_one_value': value(p), 'seed_two_value': value(q)}
        seed_diagnostics[condition] = {
            'common_passing_pairs': len(common), 'seed_one_common_pairs': summarize(a),
            'seed_two_common_pairs': summarize(b),
            'max_passing_both_seeds_text_shift': max(passing_shifts),
            'max_all_algebraic_text_shift': maximum,
            'all_algebraic_absolute_shift_quantiles_0_50_90_95_100': np.quantile(shifts, [0, .5, .9, .95, 1]).tolist(),
            'common_pair_gap_sign_changes': int(sum(np.sign(x[2] - x[3]) != np.sign(y[2] - y[3]) for x, y in zip(a, b))),
        }
    return {
        'schema': 'paired-pilot-independent-audit/1.0', 'source_numeric_results_sha256': hashlib.sha256(raw).hexdigest(),
        'scope': 'Saved numeric replay only; no new inference, estimator subset draws, sample replacement, or classifier fitting. Existing bootstrap schedule replayed exactly.',
        'bootstrap_replicates': BOOTSTRAPS, 'bootstrap_seed': BOOTSTRAP_SEED,
        'bootstrap_unit': 'Whole human/AI prompt-pair; fixed domain counts',
        'reports_replayed': reports_replayed, 'unavailable_estimator_reports': unavailable_reports,
        'failure_content_token_counts_with_repeated_conditions': sorted(failure_token_counts),
        'max_numeric_replay_absolute_errors': errors,
        'provided_guarded_summary_matches': expected_summary is not None,
        'provided_unguarded_summary_matches': expected_unguarded is not None,
        'guarded': guarded, 'unguarded': unguarded,
        'posthoc_guard_diagnostics_not_selection': guard_diagnostics,
        'seed_diagnostics': seed_diagnostics,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    parser.add_argument('--summary', type=Path)
    parser.add_argument('--unguarded', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Never overwrite any supplied frozen input.
    for path in (args.results, args.summary, args.unguarded):
        if path is not None and path.resolve() == args.output.resolve():
            parser.error('Output must differ from all frozen inputs')
    read = lambda path: None if path is None else json.loads(path.read_text())
    result = audit(args.results, read(args.summary), read(args.unguarded))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print('Passed:', result['reports_replayed'], 'numeric reports; aggregate audit written to', args.output)

if __name__ == '__main__':
    main()
