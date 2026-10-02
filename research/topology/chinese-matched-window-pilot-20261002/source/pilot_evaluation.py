"""TRAIN-only preprocessing/fitting, frozen JSON coefficients, one-shot DEV scoring."""
from collections import Counter,defaultdict
import warnings
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import roc_auc_score
from pilot_core import SEEDS

ARMS=('baseline','baseline_slope','baseline_sd','baseline_slope_sd','length_source')


def validate_records(rows,split):
    if split not in ('train','dev'):raise PermissionError('TEST is closed')
    groups=defaultdict(list)
    for r in rows:
        if r['split']!=split or r['arm'] not in ('human','chatgpt'):
            raise PermissionError('Split/arm boundary')
        groups[r['component_id']].append(r)
    for pair in groups.values():
        if len(pair)!=2 or {r['arm'] for r in pair}!={'human','chatgpt'} or len({r['source'] for r in pair})!=1:
            raise ValueError('Exactly one pair per component/source')
    expected={'train':{'baike':16,'web':16},'dev':{'baike':8,'web':8}}[split]
    if Counter(pair[0]['source'] for pair in groups.values())!=expected:
        raise ValueError('Fixed split/source composition mismatch')
    return groups


def design(rows,arm,seed_index=None):
    groups=defaultdict(list)
    for r in rows:groups[r['component_id']].append(r)
    usable={c:all(r['topology']['available'] for r in pair) for c,pair in groups.items()}
    result=[]
    for r in rows:
        l=r['linguistic']; values=l['values']
        if len(values)!=68 or l['observed']!=[v is not None for v in values]:
            raise ValueError('Typed 68-channel mask mismatch')
        base=list(values)+[np.log1p(r['window_characters']),
            None if r['lexical_tokens'] is None else np.log1p(r['lexical_tokens']),
            np.log1p(r['content_tokens']),r['unknown_token_rate'],int(r['source']=='web')]
        if arm=='length_source': base=base[68:]
        elif arm not in ARMS:raise ValueError('Unregistered arm')
        t=r['topology']; s=u=None
        if usable[r['component_id']]:
            if tuple(t['seed_ids'])!=SEEDS or len(t['schedule_means'])!=20:
                raise ValueError('Schedule identity mismatch')
            s=t['mean'] if seed_index is None else t['schedule_means'][seed_index]
            u=t['sd']
        if arm in ('baseline_slope','baseline_slope_sd'):base.append(s)
        if arm in ('baseline_sd','baseline_slope_sd'):base.append(u)
        result.append([np.nan if x is None else x for x in base])
    a=np.asarray(result,dtype=float)
    if np.isinf(a).any():raise ValueError('Infinite design values')
    return a


def fit_preprocessing(x,split):
    if split!='train':raise PermissionError('Preprocessing is TRAIN only')
    x=np.asarray(x,float);active=np.isfinite(x).any(0)
    med=np.array([np.median(x[np.isfinite(x[:,j]),j]) if active[j] else 0 for j in range(x.shape[1])])
    filled=np.where(np.isfinite(x),x,med);filled[:,~active]=0
    augmented=np.c_[filled,~np.isfinite(x)]
    mean=augmented.mean(0);scale=augmented.std(0);scale[scale==0]=1
    return {'median':med.tolist(),'active':active.tolist(),'mean':mean.tolist(),'scale':scale.tolist(),'fitted_split':'train'}


def transform(x,p):
    if p['fitted_split']!='train':raise ValueError('Frozen TRAIN transform required')
    x=np.asarray(x,float);med=np.asarray(p['median']); active=np.asarray(p['active'])
    if x.ndim!=2 or x.shape[1]!=len(med):raise ValueError('Design width mismatch')
    filled=np.where(np.isfinite(x),x,med);filled[:,~active]=0
    return (np.c_[filled,~np.isfinite(x)]-np.asarray(p['mean']))/np.asarray(p['scale'])


def fit_one(x,y):
    p=fit_preprocessing(x,'train');model=LogisticRegression(C=1.,penalty='l2',solver='lbfgs',fit_intercept=True,max_iter=2000,tol=1e-9)
    with warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning);model.fit(transform(x,p),y,sample_weight=np.full(len(y),0.5))
    return {'preprocessing':p,'coefficients':model.coef_[0].tolist(),'intercept':float(model.intercept_[0])}


def predict(x,model):
    z=transform(x,model['preprocessing'])@np.asarray(model['coefficients'])+model['intercept']
    # Stable sigmoid, no fitted calibration.
    out=np.empty_like(z);positive=z>=0
    out[positive]=1/(1+np.exp(-z[positive]));ez=np.exp(z[~positive]);out[~positive]=ez/(1+ez)
    return out


def fit_train(rows):
    groups=validate_records(rows,'train')
    usable=sum(all(r['topology']['available'] for r in pair) for pair in groups.values())
    if usable<24:raise ValueError('Fewer than 24 usable TRAIN pairs; coverage-only stop')
    y=np.asarray([r['arm']=='human' for r in rows],int)
    fitted={'status':'frozen_train_only','train_components':sorted(groups),'usable_train_pairs':usable,
        'models':{a:fit_one(design(rows,a),y) for a in ARMS},
        'seed_models':[fit_one(design(rows,'baseline_slope',k),y) for k in range(20)]}
    return fitted


def loss(y,p):
    p=np.clip(p,np.finfo(float).eps,1-np.finfo(float).eps)
    return -(y*np.log(p)+(1-y)*np.log1p(-p))


def score_dev(rows,fit):
    groups=validate_records(rows,'dev')
    if fit['status']!='frozen_train_only' or set(groups)&set(fit['train_components']):
        raise ValueError('TRAIN/DEV leakage or missing frozen fit')
    usable=sum(all(r['topology']['available'] for r in pair) for pair in groups.values())
    if usable<12:return {'status':'coverage_only','usable_dev_pairs':usable,'required':12}
    y=np.asarray([r['arm']=='human' for r in rows],int)
    preds={a:predict(design(rows,a),fit['models'][a]) for a in ARMS}
    ids=np.array([r['component_id'] for r in rows]); sources=np.array([r['source'] for r in rows])
    pair_ids=sorted(groups);pair_sources=np.array([groups[p][0]['source'] for p in pair_ids])
    rng=np.random.default_rng(20261120)
    weights=np.concatenate([rng.choice(np.flatnonzero(pair_sources==s),size=(10000,8),replace=True) for s in ('baike','web')],1)
    out={'status':'development_evidence_not_independent_validation','dev_pairs':16,'usable_dev_pairs':usable,'metrics':{},'improvement':{}}
    for a,p in preds.items():
        out['metrics'][a]={}
        for s in ('pooled','baike','web'):
            mask=np.ones(len(y),bool) if s=='pooled' else sources==s
            out['metrics'][a][s]={'log_loss':float(loss(y[mask],p[mask]).mean()),'brier':float(np.mean((y[mask]-p[mask])**2)),'auroc':float(roc_auc_score(y[mask],p[mask]))}
        if a!='baseline':
            diff=loss(y,preds['baseline'])-loss(y,p)
            per=np.array([diff[ids==c].mean() for c in pair_ids])
            out['improvement'][a]={'mean':float(per.mean()),'fixed_train_pair_composition_95pct_range':np.quantile(per[weights].mean(1),[.025,.975]).tolist(),
                'by_source':{s:float(per[pair_sources==s].mean()) for s in ('baike','web')}}
    base=loss(y,preds['baseline']).mean()
    gains=[float(base-loss(y,predict(design(rows,'baseline_slope',k),m)).mean()) for k,m in enumerate(fit['seed_models'])]
    out['numerical_sensitivity']={'seeds':list(SEEDS),'gains':gains,'sd':float(np.std(gains,ddof=1)),'range':[min(gains),max(gains)]}
    out['interpretation']='No independent detector validation; fixed TRAIN fits, exposed DEV, conditional pair-composition and numerical sensitivity only'
    return out
