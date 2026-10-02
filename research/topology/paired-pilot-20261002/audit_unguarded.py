"""Post-hoc source-formula audit; reuses saved slopes without new measurements."""
import copy
import json
from pathlib import Path
from analyze_paired_pilot import summarize

root = Path(__file__).resolve().parent
saved = json.loads((root/'paired-pilot-results.json').read_text())
rows = copy.deepcopy(saved['records'])
for row in rows:
    for text in row['texts'].values():
        for condition in text['conditions'].values():
            for report in condition['phd'].values():
                if report['status'] != 'ok' and report.get('mean_slope') is not None and report['mean_slope'] != 1:
                    report['status'] = 'ok'
                    report['dimension'] = 1/(1-report['mean_slope'])
out = {'label': 'post_hoc_method_audit_only',
       'reason': 'released source returns the transform of the mean slope without our per-rerun stability guard; compute algebra from saved slopes, no new model run, sample selection, or retries',
       'summaries': {}}
for condition in ['original_window','matched_reencoded']:
    out['summaries'][condition] = {domain: summarize(rows,condition,'notebook_seed_20261002',domain)
                                  for domain in ['wikip','reddit','pooled']}
(root/'unguarded-method-audit.json').write_text(json.dumps(out,indent=2)+'\n')
