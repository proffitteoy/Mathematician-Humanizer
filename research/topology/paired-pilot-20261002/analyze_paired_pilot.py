"""Paired, domain-stratified summaries; never an optimized detector score."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
BOOTSTRAPS = 10000

def auc(h, a):
    return float(((h[:, None] > a[None, :]) + .5 * (h[:, None] == a[None, :])).mean())

def summarize(records, condition, profile, domain):
    all_rows = records if domain == 'pooled' else [r for r in records if r['domain'] == domain]
    pairs, excluded = [], []
    for r in all_rows:
        ds = [r['texts'][l]['conditions'][condition]['phd'][profile] for l in ('human', 'ai')]
        if any(d['status'] != 'ok' for d in ds):
            excluded.append({'domain': r['domain'], 'index': r['source_index'], 'reasons': [d.get('reason') for d in ds]})
        else:
            pairs.append((ds[0]['dimension'], ds[1]['dimension'], r['domain']))
    if not pairs:
        return {'n_selected': len(all_rows), 'n_available_pairs': 0, 'excluded': excluded}
    h = np.array([p[0] for p in pairs]); a = np.array([p[1] for p in pairs]); dif = h-a
    groups = [np.array([i for i,p in enumerate(pairs) if p[2] == d]) for d in sorted(set(p[2] for p in pairs))]
    rng = np.random.default_rng(20261004)
    ids = np.concatenate([g[rng.integers(0,len(g),size=(BOOTSTRAPS,len(g)))] for g in groups],axis=1)
    means = dif[ids].mean(axis=1)
    aa, hh = a[ids], h[ids]
    aucs = ((hh[:,:,None] > aa[:,None,:]) + .5*(hh[:,:,None] == aa[:,None,:])).mean(axis=(1,2))
    return {'n_selected': len(all_rows), 'n_available_pairs': len(pairs), 'excluded': excluded,
            'human_mean': float(h.mean()), 'ai_mean': float(a.mean()),
            'human_sd': float(h.std(ddof=1)), 'ai_sd': float(a.std(ddof=1)),
            'paired_mean_difference_human_minus_ai': float(dif.mean()),
            'paired_median_difference_human_minus_ai': float(np.median(dif)),
            'paired_difference_95pct_bootstrap': np.quantile(means,[.025,.975]).tolist(),
            'human_gt_ai_pairs': int((dif>0).sum()), 'ties': int((dif==0).sum()),
            'human_gt_ai_fraction': float((dif>0).mean()),
            'descriptive_human_positive_auroc': auc(h,a),
            'auroc_95pct_paired_bootstrap': np.quantile(aucs,[.025,.975]).tolist()}

def main():
    assert auc(np.array([3,5]),np.array([2,4])) == .75
    raw = (ROOT/'paired-pilot-results.json').read_bytes(); results = json.loads(raw)
    assert results['status'] == 'completed' and len(results['records']) == 32
    records = results['records']
    selection = json.loads((ROOT/'selection-manifest.json').read_text())
    expected = {(d['domain'],r['index'],r['prefix_sha256']) for d in selection['domains'] for r in d['selected']}
    assert {(r['domain'],r['source_index'],r['prefix_sha256']) for r in records} == expected
    for r in records:
        assert r['texts']['human']['conditions']['matched_reencoded']['content_tokens'] == r['texts']['ai']['conditions']['matched_reencoded']['content_tokens'] == r['matched_n']
    out = {'results_sha256': hashlib.sha256(raw).hexdigest(), 'bootstrap_replicates': BOOTSTRAPS,
        'bootstrap_seed': 20261004, 'bootstrap_unit': 'source prompt-pair, stratified by domain for pooled summaries',
        'primary': 'original_window/notebook_seed_20261002', 'summaries': {}, 'lengths': {}}
    conditions = [('original_window','notebook_seed_20261002'),('original_window','notebook_seed_20261003'),('original_window','paper_prose_seed_20261002'),('matched_reencoded','notebook_seed_20261002'),('matched_reencoded','notebook_seed_20261003')]
    for condition,profile in conditions:
        out['summaries'][condition+'/'+profile] = {d:summarize(records,condition,profile,d) for d in ['wikip','reddit','pooled']}
    for domain in ['wikip','reddit','pooled']:
        rs = records if domain == 'pooled' else [r for r in records if r['domain']==domain]
        out['lengths'][domain] = {}
        for label in ['human','ai']:
            lens = np.array([r['texts'][label]['untruncated_content_tokens'] for r in rs])
            out['lengths'][domain][label] = {'n':len(rs),'min':int(lens.min()),'median':float(np.median(lens)),'mean':float(lens.mean()),'max':int(lens.max()),
                'truncated':sum(r['texts'][label]['original_window_truncated'] for r in rs),
                'internal_special_tokens':sum(r['texts'][label]['contains_internal_special_ids'] for r in rs)}
    out['max_seed_dimension_abs_difference'] = max(abs(t['conditions'][c]['phd']['notebook_seed_20261002']['dimension'] - t['conditions'][c]['phd']['notebook_seed_20261003']['dimension']) for r in records for t in r['texts'].values() for c in ['original_window','matched_reencoded'] if all(t['conditions'][c]['phd']['notebook_seed_'+str(s)]['status']=='ok' for s in [20261002,20261003]))
    out['max_seed_dimension_abs_difference_scope'] = 'conditional on both estimates passing the per-rerun guard; not the full cohort'
    out['post_hoc_full_cohort_max_seed_algebraic_difference'] = max(abs(1/(1-t['conditions'][c]['phd']['notebook_seed_20261002']['mean_slope']) - 1/(1-t['conditions'][c]['phd']['notebook_seed_20261003']['mean_slope'])) for r in records for t in r['texts'].values() for c in ['original_window','matched_reencoded'])
    (ROOT/'paired-pilot-summary.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    for key,val in out['summaries'].items():
        print(key)
        for d,s in val.items():
            print(d, json.dumps(s))
    print('LENGTHS',json.dumps(out['lengths']))

if __name__ == '__main__': main()
