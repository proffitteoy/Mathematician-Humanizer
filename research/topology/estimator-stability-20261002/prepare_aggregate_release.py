"""Aggregate-only release builder. Private cell/seed rows are never copied."""
import copy, hashlib, json, math, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PUB=ROOT/'aggregate-release'
PUB.mkdir(exist_ok=True)
s=json.loads((ROOT/'stability-summary.json').read_text())
manifest=json.loads((ROOT/'run-manifest.json').read_text())
verification=json.loads((ROOT/'verification.json').read_text())
raw=[json.loads(line) for line in (ROOT/'measurements.jsonl').read_text().splitlines()]
pub={k:copy.deepcopy(v) for k,v in s.items() if k!='per_cell'}
for cond,metrics in pub['conditions'].items():
 for metric,domains in metrics.items():
  for domain,data in domains.items():data.pop('pairs',None)
pub['release_scope']='Aggregate-only: no raw text, embeddings, per-text results, per-pair results, source indices, or individual cloud hashes.'
pub['within_text_distribution_aggregates']={}
for cond in ['original_window','matched_reencoded']:
 cells=[c for c in s['per_cell'] if c['condition']==cond]
 out={'n_text_cells':len(cells),'n_seed_reports':len(cells)*20,'n_individual_reruns':len(cells)*60}
 for k in ['mean_slope_outside_0_1','individual_rerun_slope_outside_0_1','dimension_outside_2_18','negative_dimension_count','undefined_dimensions']:
  out[k]=sum(c[k] for c in cells)
 for metric in ['slope','dimension']:
  vals=[c[metric]['sample_sd'] for c in cells]
  out[metric+'_within_text_sd']={'min':min(vals),'median':statistics.median(vals),'max':max(vals)}
  out[metric+'_all_seed_value_range']=[min(c[metric]['min'] for c in cells),max(c[metric]['max'] for c in cells)]
 ratios=[c['observed_to_delta_sd_ratio'] for c in cells]
 out['observed_dimension_sd_to_delta_method_ratio']={'min':min(ratios),'median':statistics.median(ratios),'max':max(ratios)}
 out['paired_gap_transform_of_each_text_seed_mean_slope_diagnostic_only']=sum((1 if c['label']=='human'else -1)*c['transform_of_seed_mean_slope'] for c in cells)/32
 pub['within_text_distribution_aggregates'][cond]=out
uniq={r['cloud_sha256']:r for r in raw}
reports=[rep for r in uniq.values() for rep in r['reports']]
runs=[run for r in reports for run in r['runs']]
all_reports=[rep for row in raw for rep in row['reports']]
all_runs=[run for rep in all_reports for run in rep['runs']]
pub['all_128_cell_aggregate_counts']={
 'condition_cells':128,'distinct_clouds':len(uniq),'seeds_per_cell':20,'final_mean_slopes':len(all_reports),'individual_rerun_slopes':len(all_runs),
 'nonfinite_or_undefined_mean_slopes':sum(rep['mean_slope'] is None or not math.isfinite(rep['mean_slope']) for rep in all_reports),
 'nonfinite_or_undefined_individual_slopes':sum(run['slope'] is None or not math.isfinite(run['slope']) for run in all_runs),
 'mean_slopes_below_zero':sum(rep['mean_slope']<0 for rep in all_reports),'mean_slopes_at_or_above_one':sum(rep['mean_slope']>=1 for rep in all_reports),
 'individual_slopes_below_zero':sum(run['slope']<0 for run in all_runs),'individual_slopes_at_or_above_one':sum(run['slope']>=1 for run in all_runs),
 'nonfinite_or_undefined_final_dimensions':sum(rep['dimension'] is None or not math.isfinite(rep['dimension']) for rep in all_reports),
 'negative_final_dimensions':sum(rep['dimension']<0 for rep in all_reports),'final_dimensions_below_two':sum(rep['dimension']<2 for rep in all_reports),'final_dimensions_above_eighteen':sum(rep['dimension']>18 for rep in all_reports),
 'nonfinite_or_undefined_individual_transforms':sum(run['dimension'] is None or not math.isfinite(run['dimension']) for run in all_runs),
 'negative_individual_transforms':sum(run['dimension']<0 for run in all_runs),
 'condition_counts_include_26_identical_window_reuses':True}
pub['unique_cloud_aggregate_counts']={'clouds':len(uniq),'seed_reports':len(reports),'individual_reruns':len(runs),'individual_rerun_slopes_outside_0_1':sum(not 0<=r['slope']<1 for r in runs),'individual_rerun_negative_transforms':sum(r['dimension'] is not None and r['dimension']<0 for r in runs),'final_dimensions_outside_2_18':sum(not 2<=r['dimension']<=18 for r in reports),'final_negative_dimensions':sum(r['dimension']<0 for r in reports),'final_undefined_dimensions':sum(r['dimension'] is None for r in reports)}
# Explicit content/schema check before any release file is written.
forbidden={'per_cell','pairs','source_index','source_sha256','cloud_sha256','prefix_sha256','draw_energies','median_energies','runs','reports','defined_values','text','prefix','gold_completion','gen_completion'}
def scan(obj):
 if isinstance(obj,dict):
  assert not (set(obj)&forbidden),set(obj)&forbidden
  for value in obj.values():scan(value)
 elif isinstance(obj,list):
  for value in obj:scan(value)
scan(pub)
(PUB/'aggregate-results.json').write_text(json.dumps(pub,indent=2,allow_nan=False)+'\n')
for name in ['STABILITY_PROTOCOL.md','run_stability.py','analyze_stability.py','audit_saved_results.py','prepare_aggregate_release.py']:
 (PUB/name).write_bytes((ROOT/name).read_bytes())
(PUB/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
(PUB/'run-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(pub['unique_cloud_aggregate_counts'],indent=2))
print(json.dumps(pub['within_text_distribution_aggregates'],indent=2))
