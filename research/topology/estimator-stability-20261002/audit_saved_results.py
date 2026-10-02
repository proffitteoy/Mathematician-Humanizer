"""Independent read-only audit of saved scalar measurements; no new cloud estimates."""
import hashlib, json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent/'topology-replication-20261002'

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1<<20),b''):h.update(block)
 return h.hexdigest()

def main():
 man=json.loads((ROOT/'run-manifest.json').read_text());assert man['status']=='completed'
 assert sha(ROOT/'STABILITY_PROTOCOL.md')==man['protocol_sha256']
 for name,digest in man['script_hashes'].items():assert sha(ROOT/name)==digest
 base=json.loads((ROOT/'pilot-baseline-hashes.json').read_text())
 for name,digest in base.items():assert sha(PILOT/name)==digest
 rows=[json.loads(line) for line in (ROOT/'measurements.jsonl').read_text().splitlines()]
 summ=json.loads((ROOT/'stability-summary.json').read_text())
 assert len(rows)==128
 old=json.loads((PILOT/'paired-pilot-results.json').read_text())
 saved={(r['domain'],r['source_index']):r for r in old['records']}
 maxerr=0.;nslope=0;dimensions=0;negative=0;outbounds=0;notdefined=0
 for row in rows:
  prior=saved[row['domain'],row['source_index']]['texts'][row['label']]['conditions'][row['condition']]
  assert prior['content_tokens']==row['n'] and prior['cloud_float32_c_order_sha256']==row['cloud_sha256']
  assert [r['seed'] for r in row['reports']]==list(range(20261010,20261030))
  n=row['n'];step=(n-40)//7;grid=list(range(40,n-step,step))
  for r in row['reports']:
   assert r['sample_sizes']==grid and len(r['runs'])==3
   xs=np.log(grid);slopes=[]
   for run in r['runs']:
    assert all(len(v)==(3 if n<=2*s else 9) for v,s in zip(run['draw_energies'],grid))
    meds=np.array([np.median(v) for v in run['draw_energies']]);assert np.array_equal(meds,run['median_energies'])
    # Independent centered regression, compared to saved upstream arithmetic.
    yy=np.log(meds);expected=float(np.cov(xs,yy,ddof=0)[0,1]/np.var(xs))
    err=abs(expected-run['slope']);maxerr=max(maxerr,err);assert err<1e-10
    slopes.append(run['slope']);nslope+=1
   assert np.mean(slopes)==r['mean_slope']
   expected=None if r['mean_slope']==1 else 1/(1-r['mean_slope'])
   assert expected==r['dimension']
   dimensions+=1;negative+=expected is not None and expected<0;notdefined+=expected is None
   outbounds+=expected is not None and not 2<=expected<=18
 lookup={(r['domain'],r['source_index'],r['label'],r['condition']):r for r in rows}
 pairs=list(dict.fromkeys((r['domain'],r['source_index']) for r in rows))
 for cond,metrics in summ['conditions'].items():
  for metric,groups in metrics.items():
   for group,a in groups.items():
    pp=[p for p in pairs if group=='pooled' or p[0]==group]
    matrix=np.array([[lookup[d,i,'human',cond]['reports'][s][metric]-lookup[d,i,'ai',cond]['reports'][s][metric] for s in range(20)] for d,i in pp])
    np.testing.assert_allclose(matrix.mean(axis=0),a['fixed_cohort_seed_means'],rtol=0,atol=1e-12)
    assert np.isclose(matrix.mean(),a['mean_gap'])
    assert np.isclose(matrix.mean(axis=0).var(ddof=1),a['single_schedule_mc_variance'])
    parts=a['fixed_empirical_resampling']['variance_decomposition']
    assert np.isclose(parts['total'],sum(parts[x] for x in ['pair_composition_main','seed_main','interaction']))
 checks=summ['checks']
 assert checks['negative_dimensions_with_duplicate_conditions']==negative
 assert checks['undefined_dimensions_with_duplicate_conditions']==notdefined
 assert checks['dimensions_outside_2_18_with_duplicate_conditions']==outbounds
 result={'status':'passed','audit_scope':'Read-only saved-energy/formula/provenance/statistical checks, no estimator rerun','original_pilot_files_verified_unchanged':len(base),'all_128_cloud_hashes_match_pilot':True,'saved_rerun_slopes_audited':nslope,'saved_dimensions_audited':dimensions,'negative_dimensions_retained':negative,'undefined_dimensions_retained':notdefined,'dimensions_outside_2_18_retained':outbounds,'maximum_independent_centered_slope_absolute_error':maxerr,'all_cohort_means_and_mc_variances_reproduced':True,'variance_decompositions_sum_to_total':True}
 (ROOT/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
