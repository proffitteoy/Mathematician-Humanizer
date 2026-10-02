"""Independent aggregate-only audit of retained PHD stability evidence.

Reads local saved numbers and provenance. Never imports either study script,
loads a model, reads source texts, computes MSTs, or writes into the study/pilot.
The only replay of randomness is the declared subset-index plan and empirical
composition table, not additional estimator measurements. Outputs contain no
document identifiers, individual cloud hashes, or per-document numerical rows.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

SEEDS = list(range(20261010, 20261030))
Q = [0, .025, .25, .5, .75, .975, 1]
CHECKS = Counter()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def close(actual, expected, label, atol=3e-11):
    assert np.allclose(actual, expected, rtol=3e-11, atol=atol), label
    CHECKS[label] += 1


def dist(values, saved):
    x = np.asarray(values, dtype=float)
    assert np.isfinite(x).all(), 'nonfinite input unexpectedly omitted'
    assert saved['status'] == 'complete'
    assert saved['n_total'] == saved['n_defined'] == x.size
    assert saved['n_undefined'] == 0
    for key, value in [('mean', x.mean()), ('median', np.median(x)),
                       ('sample_sd', x.std(ddof=1)), ('min', x.min()),
                       ('max', x.max())]:
        close(saved[key], value, 'distribution scalar replay')
    assert saved['quantile_probabilities'] == Q
    close(saved['quantiles'], np.quantile(x, Q), 'distribution quantile replay')


def safe_scan(obj):
    forbidden = {'per_cell', 'pairs', 'source_index', 'source_sha256',
                 'cloud_sha256', 'prefix_sha256', 'draw_energies',
                 'median_energies', 'runs', 'reports', 'defined_values',
                 'text', 'prefix', 'gold_completion', 'gen_completion'}
    if isinstance(obj, dict):
        assert not set(obj).intersection(forbidden), 'private row key in aggregate'
        for value in obj.values():
            safe_scan(value)
    elif isinstance(obj, list):
        for value in obj:
            safe_scan(value)


def main(root, output):
    pilot = root.parent / 'topology-replication-20261002'
    man = json.loads((root / 'run-manifest.json').read_text())
    assert man['status'] == 'completed' and man['seeds'] == SEEDS
    assert sha(root / 'STABILITY_PROTOCOL.md') == man['protocol_sha256']
    assert sha(pilot / 'selection-manifest.json') == man['selection_sha256']
    for name, digest in man['script_hashes'].items():
        assert sha(root / name) == digest, 'frozen source hash mismatch'
    baseline = json.loads((root / 'pilot-baseline-hashes.json').read_text())
    assert len(baseline) == 47
    assert all(sha(pilot / name) == digest for name, digest in baseline.items())
    selection = json.loads((pilot / 'selection-manifest.json').read_text())
    selected = [(d['domain'], x['index']) for d in selection['domains']
                for x in d['selected']]
    assert Counter(d for d, _ in selected) == {'wikip': 16, 'reddit': 16}
    old = json.loads((pilot / 'paired-pilot-results.json').read_text())
    model = json.loads((pilot / 'model-manifest.json').read_text())
    assert model['revision'] == man['model_revision'] == 'e2da8e2f811d1448a5b465c236feacd80ffbac7b'
    for file in model['files']:
        path = pilot/'roberta-base'/file['path']
        assert path.stat().st_size == file['bytes'] and sha(path) == file['sha256']
    oldrows = {(x['domain'], x['source_index']): x for x in old['records']}
    rows = [json.loads(x) for x in (root / 'measurements.jsonl').read_text().splitlines()]
    summary = json.loads((root / 'stability-summary.json').read_text())
    assert len(rows) == len(summary['per_cell']) == 128
    key = lambda x: (x['domain'], x['source_index'], x['label'], x['condition'])
    lookup = {key(x): x for x in rows}
    summaries = {key(x): x for x in summary['per_cell']}
    pairs = list(dict.fromkeys((x['domain'], x['source_index']) for x in rows))
    assert pairs == selected
    assert set(lookup) == set(summaries) == {
        (*p, label, cond) for p in pairs for label in ['human', 'ai']
        for cond in ['original_window', 'matched_reencoded']}
    assert len(lookup) == 128
    plans = {}
    unique = {}
    max_ols_error = 0.0
    for row in rows:
        saved = summaries[key(row)]
        prior = oldrows[row['domain'], row['source_index']]['texts'][row['label']]
        priorcond = prior['conditions'][row['condition']]
        assert priorcond['content_tokens'] == row['n']
        assert priorcond['cloud_float32_c_order_sha256'] == row['cloud_sha256']
        assert prior['source_sha256'] == row['source_sha256']
        for field in ['domain', 'source_index', 'label', 'condition', 'n',
                      'cloud_sha256', 'measurement_source']:
            assert row[field] == saved[field]
        assert [r['seed'] for r in row['reports']] == SEEDS
        n = row['n']
        step = (n - 40) // 7
        sizes = list(range(40, n - step, step))
        x = np.log(sizes)
        for report in row['reports']:
            assert report['sample_sizes'] == sizes and len(report['runs']) == 3
            plan_key = (n, report['seed'])
            if plan_key not in plans:
                plan = []
                for child in np.random.SeedSequence(report['seed']).spawn(3):
                    rng = np.random.default_rng(child)
                    plan.append([[rng.choice(n, size=s, replace=False).tolist()
                                  for _ in range(9 if n > 2*s else 3)] for s in sizes])
                plans[plan_key] = hashlib.sha256(json.dumps(plan, separators=(',', ':')).encode()).hexdigest()
            assert report['plan_sha256'] == plans[plan_key]
            slopes = []
            for run in report['runs']:
                assert len(run['draw_energies']) == len(sizes)
                assert all(len(v) == (9 if n > 2*s else 3)
                           for s, v in zip(sizes, run['draw_energies']))
                assert all(np.isfinite(v).all() and np.min(v) > 0
                           for v in run['draw_energies'])
                medians = np.asarray([np.median(v) for v in run['draw_energies']])
                assert np.array_equal(medians, run['median_energies'])
                y = np.log(medians)
                xc, yc = x - x.mean(), y - y.mean()
                centered = float(xc.dot(yc) / xc.dot(xc))
                upstream = float((len(x)*sum(x*y)-sum(x)*sum(y)) /
                                 (len(x)*sum(x*x)-sum(x)**2))
                close(run['slope'], upstream, 'upstream OLS arithmetic replay')
                close(run['slope'], centered, 'independent centered OLS replay')
                close(run['centered_slope'], centered, 'saved centered OLS replay')
                max_ols_error = max(max_ols_error, abs(centered - run['slope']))
                close(run['dimension'], 1/(1-run['slope']), 'individual reciprocal replay')
                assert run['slope_outside_0_1'] == (not 0 <= run['slope'] < 1)
                close(run['intercept'], y.mean()-run['slope']*x.mean(), 'intercept replay')
                resid = y - (run['intercept'] + run['slope']*x)
                close(run['r_squared'], 1-resid.dot(resid)/yc.dot(yc), 'fit diagnostic replay')
                slopes.append(run['slope'])
            assert np.mean(slopes) == report['mean_slope']
            assert report['dimension'] == 1/(1-report['mean_slope'])
            assert report['status'] == 'defined'
            assert report['mean_slope_outside_0_1'] == (not 0 <= report['mean_slope'] < 1)
            assert report['dimension_outside_2_18'] == (not 2 <= report['dimension'] <= 18)
        if row['cloud_sha256'] in unique:
            assert row['reports'] == unique[row['cloud_sha256']]['reports']
        else:
            unique[row['cloud_sha256']] = row
        s = np.asarray([r['mean_slope'] for r in row['reports']])
        d = np.asarray([r['dimension'] for r in row['reports']])
        r = np.asarray([z['slope'] for q in row['reports'] for z in q['runs']])
        dist(s, saved['slope']); dist(d, saved['dimension'])
        dist(r, saved['individual_rerun_slopes'])
        counts = {'mean_slope_outside_0_1': np.sum((s < 0) | (s >= 1)),
                  'individual_rerun_slope_outside_0_1': np.sum((r < 0) | (r >= 1)),
                  'dimension_outside_2_18': np.sum((d < 2) | (d > 18)),
                  'negative_dimension_count': np.sum(d < 0), 'undefined_dimensions': 0}
        assert all(saved[k] == v for k, v in counts.items())
        close(saved['minimum_abs_distance_mean_slope_to_1'], np.min(abs(1-s)), 'pole distance replay')
        close(saved['scale_span_log'], np.log(max(sizes)/min(sizes)), 'scale span replay')
        close(saved['transform_of_seed_mean_slope'], 1/(1-s.mean()), 'transform order replay')
        pred = s.std(ddof=1) / (1-s.mean())**2
        close(saved['delta_method_predicted_dimension_sd'], pred, 'delta method replay')
        close(saved['observed_to_delta_sd_ratio'], d.std(ddof=1)/pred, 'delta ratio replay')
        assert saved['seed_mean_slopes_cross_one'] == (s.min() < 1 <= s.max())
    assert len(unique) == 102
    assert Counter(r['measurement_source'] for r in rows) == {
        'same_token_ids_reused': 26, 'deterministically_reencoded_hash_verified': 102}
    for p in pairs:
        prior = oldrows[p]
        assert prior['matched_n'] == min(256, *(lookup[*p, lab, 'original_window']['n'] for lab in ['human', 'ai']))
        for lab in ['human', 'ai']:
            a, b = lookup[*p, lab, 'original_window'], lookup[*p, lab, 'matched_reencoded']
            assert b['n'] == prior['matched_n']
            if a['n'] == b['n']:
                assert a['cloud_sha256'] == b['cloud_sha256'] and a['reports'] == b['reports']
    aggregates = {}
    for condition in ['original_window', 'matched_reencoded']:
        aggregates[condition] = {}
        for metric in ['mean_slope', 'dimension']:
            aggregates[condition][metric] = {}
            for group in ['pooled', 'wikip', 'reddit']:
                pp = [p for p in pairs if group == 'pooled' or p[0] == group]
                matrix = np.asarray([[lookup[*p, 'human', condition]['reports'][s][metric] -
                                      lookup[*p, 'ai', condition]['reports'][s][metric]
                                      for s in range(20)] for p in pp])
                a = summary['conditions'][condition][metric][group]
                assert np.isfinite(matrix).all() and a['status'] == 'complete'
                assert a['pair_count'] == len(pp) and a['seed_count'] == 20 and a['seeds'] == SEEDS
                n, k = matrix.shape
                pairmeans, seedmeans = matrix.mean(1), matrix.mean(0)
                residuals = matrix - pairmeans[:, None]
                covariance = residuals.dot(residuals.T)/(k-1)
                av = np.ones(n)/n
                mc = float(av.dot(covariance).dot(av))
                indep = float(np.trace(covariance)/n**2)
                pmat = np.eye(n)-np.ones((n,n))/n
                correction = float(np.trace(pmat.dot(covariance))/(k*(n-1)))
                close(a['mean_gap'], matrix.mean(), 'cohort mean replay')
                close(a['fixed_cohort_seed_means'], seedmeans, 'cohort seed mean replay')
                dist(seedmeans, a['fixed_cohort_seed_distribution'])
                dist(pairmeans, a['seed_averaged_pair_distribution'])
                for field, value in [('single_schedule_mc_variance', mc),
                                     ('twenty_schedule_mean_mc_variance', mc/20),
                                     ('hypothetical_independent_pair_mc_variance', indep),
                                     ('seed_mean_between_pair_sample_variance', pairmeans.var(ddof=1)),
                                     ('finite_mc_heterogeneity_correction', correction),
                                     ('corrected_fixed_pair_heterogeneity_variance', pairmeans.var(ddof=1)-correction)]:
                    close(a[field], value, 'covariance and heterogeneity replay')
                close(mc, seedmeans.var(ddof=1), 'cohort variance identity')
                pos, neg = np.all(matrix > 0, axis=1), np.all(matrix < 0, axis=1)
                vary = (matrix.min(1) <= 0) & (matrix.max(1) >= 0)
                assert a['pairs_positive_every_seed'] == int(pos.sum())
                assert a['pairs_negative_every_seed'] == int(neg.sum())
                assert a['pairs_with_seed_range_spanning_zero'] == int(vary.sum())
                assert a['positive_pair_counts_per_seed'] == (matrix > 0).sum(0).tolist()
                assert len(a['pairs']) == n
                for i, p in enumerate(pp):
                    entry = a['pairs'][i]
                    assert (entry['domain'], entry['source_index']) == p
                    close(entry['values'], matrix[i], 'private paired evidence replay')
                    for field, val in [('mean_gap', matrix[i].mean()), ('seed_sd', matrix[i].std(ddof=1)),
                                       ('min_gap', matrix[i].min()), ('max_gap', matrix[i].max())]:
                        close(entry[field], val, 'private paired scalar replay')
                    assert entry['positive_seed_count'] == int((matrix[i] > 0).sum())
                # Reconstruct the bootstrap via composition counts and matrix
                # multiplication, independently of the author's indexed averaging.
                rng = np.random.default_rng(20261030)
                weights = np.zeros((10000, n), dtype=int)
                for domain in sorted(set(p[0] for p in pp)):
                    g = np.asarray([i for i, p in enumerate(pp) if p[0] == domain])
                    draws = rng.integers(0, len(g), size=(10000, len(g)))
                    for j, col in enumerate(g):
                        weights[:, col] = (draws == j).sum(1)
                    assert np.all(weights[:, g].sum(1) == len(g))
                table = weights.dot(matrix)/n
                roweff = table.mean(1)-table.mean()
                coleff = table.mean(0)-table.mean()
                interaction = table-table.mean()-roweff[:, None]-coleff[None, :]
                parts = {'pair_composition_main': float(np.mean(roweff**2)),
                         'seed_main': float(np.mean(coleff**2)),
                         'interaction': float(np.mean(interaction**2)),
                         'total': float(table.var())}
                close(sum(parts[z] for z in ['pair_composition_main', 'seed_main', 'interaction']), parts['total'], 'exact variance decomposition identity')
                close(interaction.mean(0), 0, 'zero interaction column means')
                close(interaction.mean(1), 0, 'zero interaction row means')
                bs = a['fixed_empirical_resampling']
                assert bs['analysis_seed'] == 20261030 and bs['pair_compositions'] == 10000 and bs['seed_vectors'] == 20
                for field, value in parts.items():
                    close(bs['variance_decomposition'][field], value, 'empirical variance component replay')
                for field in ['pair_composition_main', 'seed_main', 'interaction']:
                    close(bs['variance_decomposition']['fractions'][field], parts[field]/parts['total'], 'variance fraction replay')
                for field, values in [('pair_composition_mean_empirical_95pct_range', table.mean(1)),
                                      ('fixed_cohort_seed_mean_empirical_95pct_range', seedmeans),
                                      ('joint_empirical_95pct_range', table)]:
                    close(bs[field], np.quantile(values, [.025, .975]), 'empirical range replay')
                aggregates[condition][metric][group] = {
                    'mean_gap': float(matrix.mean()), 'seed_sd': float(seedmeans.std(ddof=1)),
                    'full_seed_range': [float(seedmeans.min()), float(seedmeans.max())],
                    'negative_seed_means': int((seedmeans < 0).sum()),
                    'pairs_with_seed_sign_variation': int(vary.sum()),
                    'single_schedule_mc_variance': mc,
                    'hypothetical_independent_pair_mc_variance': indep,
                    'cross_pair_covariance_variance_contribution': mc-indep,
                    'variance_ratio_covariance_aware_to_independent': mc/indep,
                    'finite_mc_heterogeneity_correction': correction,
                    'corrected_fixed_pair_heterogeneity_variance': float(pairmeans.var(ddof=1)-correction),
                    'empirical_variance_decomposition': parts}
        for group, rel in summary['length_relations'][condition].items():
            domain, label = group.split('/')
            cs = [c for c in summary['per_cell'] if c['condition'] == condition
                  and (domain == 'pooled' or c['domain'] == domain)
                  and (label == 'pooled' or c['label'] == label)]
            assert rel['n_cells'] == len(cs)
            for prefix, xfield in [('n', 'n'), ('span', 'scale_span_log')]:
                for metric in ['slope', 'dimension']:
                    xv = [c[xfield] for c in cs]
                    yv = [c[metric]['sample_sd'] for c in cs]
                    target = rel['spearman_'+prefix+'_'+metric+'_sd']
                    if len(set(xv)) < 2 or len(set(yv)) < 2:
                        assert target is None
                    else:
                        close(target, spearmanr(xv, yv).statistic, 'length correlation replay')
        for binrow, bounds in zip(summary['length_bins'][condition], [(50,79),(80,159),(160,255),(256,510)]):
            assert binrow['n_range'] == list(bounds)
            cs = [c for c in summary['per_cell'] if c['condition'] == condition and bounds[0] <= c['n'] <= bounds[1]]
            assert binrow['n_cells'] == len(cs)
            dist([c['slope']['sample_sd'] for c in cs], binrow['slope_sd'])
            dist([c['dimension']['sample_sd'] for c in cs], binrow['dimension_sd'])
            for dest, source in [('mean_slope_outside_0_1_count','mean_slope_outside_0_1'),
                                 ('individual_rerun_slope_outside_0_1_count','individual_rerun_slope_outside_0_1'),
                                 ('negative_dimension_count','negative_dimension_count')]:
                assert binrow[dest] == sum(c[source] for c in cs)
    # Verify CSV copies of the already-audited private per-cell statistics.
    with (root/'per-text-stability.csv').open() as f:
        csvrows = list(csv.DictReader(f))
    assert len(csvrows) == 128
    for rec in csvrows:
        ck = (rec['domain'], int(rec['source_index']), rec['label'], rec['condition'])
        c = summaries[ck]
        for field, value in rec.items():
            if field in c:
                if isinstance(c[field], (int, float)):
                    close(float(value), c[field], 'CSV scalar replay')
                else:
                    assert value == c[field]
            elif field.startswith(('slope_', 'dimension_')):
                metric, stat = field.split('_', 1)
                close(float(value), c[metric]['sample_sd' if stat == 'sd' else stat], 'CSV distribution replay')
    allreports = [r for c in rows for r in c['reports']]
    allruns = [r for c in allreports for r in c['runs']]
    ureports = [r for c in unique.values() for r in c['reports']]
    uruns = [r for c in ureports for r in c['runs']]
    assert len(allreports) == 2560 and len(allruns) == 7680
    assert len(ureports) == 2040 and len(uruns) == 6120
    assert sum(r['slope'] >= 1 for r in allruns) == 20
    assert sum(r['slope'] >= 1 for r in uruns) == 12
    assert sum(r['dimension'] > 18 for r in allreports) == 22
    assert sum(r['dimension'] > 18 for r in ureports) == 13
    assert all(0 <= r['mean_slope'] < 1 and np.isfinite(r['dimension']) for r in allreports)
    assert all(r['dimension'] >= 2 for r in allreports)
    assert all(r['slope'] >= 0 and np.isfinite(r['dimension']) for r in allruns)
    assert sum(r['dimension'] < 0 for r in allruns) == 20
    assert all(c['n'] < 80 for c in rows if any(r['slope'] >= 1 for s in c['reports'] for r in s['runs']))
    expected_checks = {'distinct_cloud_hashes':102,'all_duplicate_cloud_reports_equal':True,
                       'maximum_upstream_vs_centered_slope_absolute_error':max_ols_error,
                       'total_cloud_seed_reports':2560,'distinct_cloud_seed_reports':2040,
                       'total_rerun_slopes_with_duplicate_conditions':7680,
                       'undefined_dimensions_with_duplicate_conditions':0,
                       'negative_dimensions_with_duplicate_conditions':0,
                       'out_of_0_1_mean_slopes_with_duplicate_conditions':0,
                       'out_of_0_1_rerun_slopes_with_duplicate_conditions':20,
                       'dimensions_outside_2_18_with_duplicate_conditions':22}
    assert set(summary['checks']) == set(expected_checks)
    for field, value in expected_checks.items():
        close(summary['checks'][field], value, 'summary integrity check replay', atol=1e-15)
    assert man['analysis'] == summary['checks']
    # Positive-slope-domain monotonicity holds for each pair, not cohort averages.
    for p in pairs:
        for cond in ['original_window', 'matched_reencoded']:
            for i in range(20):
                h, a = (lookup[*p, label, cond]['reports'][i] for label in ['human', 'ai'])
                assert np.sign(h['mean_slope']-a['mean_slope']) == np.sign(h['dimension']-a['dimension'])
    pubroot = root/'aggregate-release'
    release = json.loads((pubroot/'RELEASE_MANIFEST.json').read_text())
    assert set(p.name for p in pubroot.iterdir() if p.is_file()) == set(release['file_allowlist'])
    assert len(release['file_allowlist']) == release['release_file_count'] == 11
    for file in release['files']:
        path = pubroot/file['path']
        assert path.stat().st_size == file['bytes'] and sha(path) == file['sha256']
    for name in ['STABILITY_PROTOCOL.md','run_stability.py','analyze_stability.py','audit_saved_results.py','prepare_aggregate_release.py','run-manifest.json','verification.json']:
        assert (pubroot/name).read_bytes() == (root/name).read_bytes()
    pub = json.loads((pubroot/'aggregate-results.json').read_text())
    safe_scan(pub)
    for name in ['scope','length_relations','length_bins','checks']:
        assert pub[name] == summary[name]
    for cond, metrics in summary['conditions'].items():
        for metric, groups in metrics.items():
            for domain, vals in groups.items():
                assert pub['conditions'][cond][metric][domain] == {k:v for k,v in vals.items() if k != 'pairs'}
    for condition in ['original_window','matched_reencoded']:
        cc = [c for c in summary['per_cell'] if c['condition'] == condition]
        out = pub['within_text_distribution_aggregates'][condition]
        assert out['n_text_cells'] == 64 and out['n_seed_reports'] == 1280 and out['n_individual_reruns'] == 3840
        for field in ['mean_slope_outside_0_1','individual_rerun_slope_outside_0_1','dimension_outside_2_18','negative_dimension_count','undefined_dimensions']:
            assert out[field] == sum(c[field] for c in cc)
        for metric in ['slope','dimension']:
            vals = [c[metric]['sample_sd'] for c in cc]
            for name, v in [('min', min(vals)),('median',np.median(vals)),('max',max(vals))]:
                close(out[metric+'_within_text_sd'][name],v,'released within-text aggregate replay')
            close(out[metric+'_all_seed_value_range'],[min(c[metric]['min'] for c in cc),max(c[metric]['max'] for c in cc)],'released value range replay')
        ratios = [c['observed_to_delta_sd_ratio'] for c in cc]
        for name,v in [('min',min(ratios)),('median',np.median(ratios)),('max',max(ratios))]:
            close(out['observed_dimension_sd_to_delta_method_ratio'][name],v,'released delta ratio replay')
        diagnostic = sum((1 if c['label']=='human' else -1)*c['transform_of_seed_mean_slope'] for c in cc)/32
        close(out['paired_gap_transform_of_each_text_seed_mean_slope_diagnostic_only'],diagnostic,'released transform order replay')
    # Audit all headline count keys, rather than trusting release-builder copies.
    ac = pub['all_128_cell_aggregate_counts']; uc = pub['unique_cloud_aggregate_counts']
    expected_ac = {'condition_cells':128,'distinct_clouds':102,'seeds_per_cell':20,
                   'final_mean_slopes':2560,'individual_rerun_slopes':7680,
                   'nonfinite_or_undefined_mean_slopes':0,'nonfinite_or_undefined_individual_slopes':0,
                   'mean_slopes_below_zero':0,'mean_slopes_at_or_above_one':0,
                   'individual_slopes_below_zero':0,'individual_slopes_at_or_above_one':20,
                   'nonfinite_or_undefined_final_dimensions':0,'negative_final_dimensions':0,
                   'final_dimensions_below_two':0,'final_dimensions_above_eighteen':22,
                   'nonfinite_or_undefined_individual_transforms':0,'negative_individual_transforms':20,
                   'condition_counts_include_26_identical_window_reuses':True}
    assert ac == expected_ac
    assert uc == {'clouds':102,'seed_reports':2040,'individual_reruns':6120,
                  'individual_rerun_slopes_outside_0_1':12,'individual_rerun_negative_transforms':12,
                  'final_dimensions_outside_2_18':13,'final_negative_dimensions':0,'final_undefined_dimensions':0}
    assert man['elapsed_seconds'] < 1800 and man['peak_rss_kib'] < 3*1024**2
    assert man['new_derived_bytes'] < 500*1024**2
    assert man['baseline_working_bytes']+man['new_derived_bytes'] < 3_000_000_000
    assert len(man['cpu_affinity']) == 2
    assert man['completed_cells'] == 128 and man['computed_distinct_clouds'] == 102 and man['reused_cells'] == 26
    assert all(sha(pilot/name) == digest for name,digest in baseline.items()), 'pilot changed during audit'
    result = {
        'status':'passed', 'scope':'Independent local saved-number/provenance replay; aggregate-only output',
        'new_encoder_or_estimator_measurements':0, 'remote_writes':0,
        'audit_script_sha256':sha(Path(__file__)),
        'frozen_protocol_and_two_script_hashes_match':True,
        'baseline_pilot_files_reverified_unchanged':47,
        'complete_cells':128, 'unique_clouds':102, 'identical_window_reuses':26,
        'seed_count':20, 'saved_three_rerun_estimates_audited':2560,
        'saved_individual_slopes_audited':7680,
        'subset_plan_hashes_independently_replayed':len(plans),
        'all_same_n_same_seed_plan_hashes_agree':True,
        'all_saved_cloud_hashes_match_pilot':True,
        'maximum_centered_vs_saved_slope_absolute_error':max_ols_error,
        'all_per_text_distributions_and_csv_reproduced':True,
        'all_12_cohort_metric_domain_covariance_and_composition_tables_reproduced':True,
        'release_allowlist_files_verified':11,
        'release_aggregate_schema_and_no_private_rows_verified':True,
        'all_outcomes':ac, 'distinct_cloud_outcomes':uc,
        'aggregate_results':aggregates, 'arithmetic_check_counts':dict(CHECKS),
        'limits':[
            'This audit verifies saved cloud-hash correspondence and encoder hash-checking code, not newly materialized cloud bytes; no re-encoding was authorized or done.',
            'Stored hashes verify current content identity. Chronology, absence of unrecorded earlier runs, and original resource/network history rely on retained run records and inspected code, not external attestation.',
            'Only the exposed fixed cohort and declared schedules are covered. Seed spread and empirical composition ranges are not population confidence intervals or a calibrated reversal probability.',
            'The twenty-schedule MC variance division and finite-MC correction use the declared random-schedule model; twenty schedules do not establish rare-tail or finite-moment behavior.',
            'Equal-length re-encoding changes context as well as N. Finite-N bias and encoder, generator, source and domain shifts are not identified.',
            'The public aggregate-only bundle cannot reconstruct withheld per-text measurements by itself.'
        ]}
    safe_scan(result)
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'output':str(output),'numeric_checks':sum(CHECKS.values()),'plan_hashes':len(plans),'release_files':11},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--study', type=Path, default=Path(__file__).parent/'topology-estimator-stability-20261002')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent/'independent-phd-stability-audit.json')
    args = parser.parse_args()
    main(args.study, args.output)
