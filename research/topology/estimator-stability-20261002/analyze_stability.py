"""Frozen planned analysis; complete cohorts only; no classifier metrics."""
import csv, json
import numpy as np
from scipy.stats import spearmanr
Q=[0,.025,.25,.5,.75,.975,1]
SEEDS=list(range(20261010,20261030))

def distribution(values):
    vals=[float(x) for x in values if x is not None and np.isfinite(x)]
    out={'n_total':len(values),'n_defined':len(vals),'n_undefined':len(values)-len(vals)}
    if len(vals)!=len(values) or not vals:
        out['status']='undefined_without_complete_case_filtering'
        out['defined_values']=vals
        return out
    a=np.array(vals)
    return dict(out,status='complete',mean=float(a.mean()),median=float(np.median(a)),sample_sd=float(a.std(ddof=1)) if len(a)>1 else None,min=float(a.min()),max=float(a.max()),quantile_probabilities=Q,quantiles=np.quantile(a,Q).tolist())

def per_cell(c):
    slopes=[r['mean_slope'] for r in c['reports']];dims=[r['dimension'] for r in c['reports']]
    runslopes=[r['slope'] for s in c['reports'] for r in s['runs']]
    slope=distribution(slopes);dim=distribution(dims)
    x={k:c[k] for k in ['domain','source_index','label','condition','n','cloud_sha256','measurement_source']}
    x.update(slope=slope,dimension=dim,individual_rerun_slopes=distribution(runslopes),mean_slope_outside_0_1=sum(v is not None and not 0<=v<1 for v in slopes),individual_rerun_slope_outside_0_1=sum(v is not None and not 0<=v<1 for v in runslopes),dimension_outside_2_18=sum(v is not None and not 2<=v<=18 for v in dims),negative_dimension_count=sum(v is not None and v<0 for v in dims),undefined_dimensions=sum(v is None for v in dims),minimum_abs_distance_mean_slope_to_1=min([abs(1-v) for v in slopes if v is not None],default=None),scale_span_log=float(np.log(max(c['reports'][0]['sample_sizes'])/min(c['reports'][0]['sample_sizes']))))
    if slope['status']=='complete' and dim['status']=='complete':
        mean=slope['mean'];den=1-mean
        x['transform_of_seed_mean_slope']=None if den==0 else float(1/den)
        x['delta_method_predicted_dimension_sd']=None if den==0 else float(slope['sample_sd']/den**2)
        pred=x['delta_method_predicted_dimension_sd']
        x['observed_to_delta_sd_ratio']=None if pred is None or pred==0 else float(dim['sample_sd']/pred)
        x['seed_mean_slopes_cross_one']=slope['min']<1<=slope['max']
    return x

def corr(x,y):
    if any(v is None for v in x+y) or len(x)<3 or len(set(x))<2 or len(set(y))<2:return None
    return float(spearmanr(x,y).statistic)

def matrix_summary(matrix,pairs,condition,metric):
    out={'condition':condition,'metric':metric,'pair_count':len(pairs),'seed_count':len(SEEDS),'seeds':SEEDS}
    if np.any(~np.isfinite(matrix)):
        return dict(out,status='undefined_without_complete_case_filtering',undefined_cells=int(np.sum(~np.isfinite(matrix))))
    n,k=matrix.shape;meanpairs=matrix.mean(axis=1);seedmeans=matrix.mean(axis=0)
    cov=np.cov(matrix,ddof=1)
    mcvar=float(cov.sum()/n**2)
    independent=float(np.trace(cov)/n**2)
    correction=float((np.trace(cov)-cov.sum()/n)/(k*(n-1)))
    s2=float(meanpairs.var(ddof=1))
    out.update(status='complete',mean_gap=float(matrix.mean()),fixed_cohort_seed_means=seedmeans.tolist(),fixed_cohort_seed_distribution=distribution(seedmeans.tolist()),seed_averaged_pair_distribution=distribution(meanpairs.tolist()),single_schedule_mc_variance=mcvar,twenty_schedule_mean_mc_variance=mcvar/k,hypothetical_independent_pair_mc_variance=independent,seed_mean_between_pair_sample_variance=s2,finite_mc_heterogeneity_correction=correction,corrected_fixed_pair_heterogeneity_variance=s2-correction,pairs_positive_every_seed=int(np.sum(np.all(matrix>0,axis=1))),pairs_negative_every_seed=int(np.sum(np.all(matrix<0,axis=1))),pairs_with_seed_range_spanning_zero=int(np.sum((matrix.min(axis=1)<=0)&(matrix.max(axis=1)>=0))),positive_pair_counts_per_seed=np.sum(matrix>0,axis=0).tolist())
    out['pairs']=[{'domain':d,'source_index':idx,'mean_gap':float(matrix[i].mean()),'seed_sd':float(matrix[i].std(ddof=1)),'min_gap':float(matrix[i].min()),'max_gap':float(matrix[i].max()),'positive_seed_count':int(np.sum(matrix[i]>0)),'values':matrix[i].tolist()} for i,(d,idx) in enumerate(pairs)]
    rng=np.random.default_rng(20261030)
    groups=[np.array([i for i,p in enumerate(pairs) if p[0]==d]) for d in sorted(set(x[0] for x in pairs))]
    ids=np.concatenate([g[rng.integers(0,len(g),size=(10000,len(g)))] for g in groups],axis=1)
    table=matrix[ids].mean(axis=1)
    overall=float(table.mean());rows=table.mean(axis=1);cols=table.mean(axis=0)
    interaction=table-rows[:,None]-cols[None,:]+overall
    parts={'pair_composition_main':float(rows.var()),'seed_main':float(cols.var()),'interaction':float(np.mean(interaction**2)),'total':float(table.var())}
    assert np.isclose(sum(parts[z] for z in ['pair_composition_main','seed_main','interaction']),parts['total'],rtol=1e-12,atol=1e-12)
    parts['fractions']={z:parts[z]/parts['total'] if parts['total'] else None for z in ['pair_composition_main','seed_main','interaction']}
    out['fixed_empirical_resampling']={'scope':'Descriptive empirical composition/seed sensitivity on these fixed pairs and seeds; not population inference','analysis_seed':20261030,'pair_compositions':10000,'seed_vectors':k,'variance_decomposition':parts,'pair_composition_mean_empirical_95pct_range':np.quantile(rows,[.025,.975]).tolist(),'fixed_cohort_seed_mean_empirical_95pct_range':np.quantile(seedmeans,[.025,.975]).tolist(),'joint_empirical_95pct_range':np.quantile(table,[.025,.975]).tolist()}
    return out

def analyze(cells,root):
    assert len(cells)==128 and all([r['seed'] for r in c['reports']]==SEEDS for c in cells)
    summaries=[per_cell(c) for c in cells]
    pairorder=list(dict.fromkeys((c['domain'],c['source_index']) for c in cells))
    assert len(pairorder)==32
    lookup={(c['domain'],c['source_index'],c['label'],c['condition']):c for c in cells}
    results={'scope':'Reliability of fixed notebook estimator on the original fixed 32 pairs; all seeds retained','conditions':{},'per_cell':summaries,'length_relations':{},'length_bins':{},'checks':{}}
    for cond in ['original_window','matched_reencoded']:
        results['conditions'][cond]={}
        for metric in ['mean_slope','dimension']:
            matrix=np.array([[lookup[(d,idx,'human',cond)]['reports'][j][metric]-lookup[(d,idx,'ai',cond)]['reports'][j][metric] if lookup[(d,idx,'human',cond)]['reports'][j][metric] is not None and lookup[(d,idx,'ai',cond)]['reports'][j][metric] is not None else np.nan for j in range(20)] for d,idx in pairorder])
            results['conditions'][cond][metric]={}
            for domain in ['pooled','wikip','reddit']:
                inds=[i for i,(d,idx) in enumerate(pairorder) if domain=='pooled' or d==domain]
                results['conditions'][cond][metric][domain]=matrix_summary(matrix[inds],[pairorder[i] for i in inds],cond,metric)
        results['length_relations'][cond]={}
        for domain in ['pooled','wikip','reddit']:
            for label in ['pooled','human','ai']:
                cs=[c for c in summaries if c['condition']==cond and (domain=='pooled' or c['domain']==domain) and (label=='pooled' or c['label']==label)]
                ns=[c['n'] for c in cs];span=[c['scale_span_log'] for c in cs]
                ss=[c['slope'].get('sample_sd') for c in cs];ds=[c['dimension'].get('sample_sd') for c in cs]
                results['length_relations'][cond][domain+'/'+label]={'n_cells':len(cs),'spearman_n_slope_sd':corr(ns,ss),'spearman_n_dimension_sd':corr(ns,ds),'spearman_span_slope_sd':corr(span,ss),'spearman_span_dimension_sd':corr(span,ds)}
        bins=[]
        for lo,hi in [(50,79),(80,159),(160,255),(256,510)]:
            cs=[c for c in summaries if c['condition']==cond and lo<=c['n']<=hi]
            bins.append({'n_range':[lo,hi],'n_cells':len(cs),'slope_sd':distribution([c['slope'].get('sample_sd') for c in cs]),'dimension_sd':distribution([c['dimension'].get('sample_sd') for c in cs]),'mean_slope_outside_0_1_count':sum(c['mean_slope_outside_0_1'] for c in cs),'individual_rerun_slope_outside_0_1_count':sum(c['individual_rerun_slope_outside_0_1'] for c in cs),'negative_dimension_count':sum(c['negative_dimension_count'] for c in cs)})
        results['length_bins'][cond]=bins
    grouped={}
    for c in cells:
        if c['cloud_sha256'] in grouped:
            assert grouped[c['cloud_sha256']]==c['reports']
        else:grouped[c['cloud_sha256']]=c['reports']
    results['checks']={'distinct_cloud_hashes':len(grouped),'all_duplicate_cloud_reports_equal':True,'maximum_upstream_vs_centered_slope_absolute_error':max(r['slope_formula_abs_error'] for c in cells for s in c['reports'] for r in s['runs'] if 'slope_formula_abs_error'in r),'total_cloud_seed_reports':len(cells)*20,'distinct_cloud_seed_reports':len(grouped)*20,'total_rerun_slopes_with_duplicate_conditions':len(cells)*60,'undefined_dimensions_with_duplicate_conditions':sum(c['undefined_dimensions'] for c in summaries),'negative_dimensions_with_duplicate_conditions':sum(c['negative_dimension_count'] for c in summaries),'out_of_0_1_mean_slopes_with_duplicate_conditions':sum(c['mean_slope_outside_0_1'] for c in summaries),'out_of_0_1_rerun_slopes_with_duplicate_conditions':sum(c['individual_rerun_slope_outside_0_1'] for c in summaries),'dimensions_outside_2_18_with_duplicate_conditions':sum(c['dimension_outside_2_18'] for c in summaries)}
    (root/'stability-summary.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
    fields=['domain','source_index','label','condition','n','slope_mean','slope_sd','slope_min','slope_max','dimension_mean','dimension_median','dimension_sd','dimension_min','dimension_max','transform_of_seed_mean_slope','delta_method_predicted_dimension_sd','observed_to_delta_sd_ratio','negative_dimension_count','undefined_dimensions','mean_slope_outside_0_1','individual_rerun_slope_outside_0_1','dimension_outside_2_18','cloud_sha256']
    with (root/'per-text-stability.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in summaries:
            row={k:c[k] for k in fields if k in c}
            for label in ['slope','dimension']:
                for stat in ['mean','median','sd','min','max']:
                    key=label+'_'+stat
                    if key in fields:row[key]=c[label].get('sample_sd' if stat=='sd' else stat)
            w.writerow(row)
    return results['checks']
