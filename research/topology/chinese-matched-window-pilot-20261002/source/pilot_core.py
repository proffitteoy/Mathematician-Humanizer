"""Model-free Chinese pilot selection, access, alignment, MST and typed features."""
from collections import defaultdict, Counter
from hashlib import sha256
import io,json
from pathlib import Path
import numpy as np

COHORT_SHA='caab83530f309622cbafe95b92e648fc59936435b170f7ef3f38abf23cf3a1ca'
RAW_SHA='cc2fb0d6c2e63f507717835cd20f992a513d098af6259ce888552ddeca79cfee'
SEED='topology-zh-matched-prefix-v1-20261002'
SEEDS=tuple(range(20261100,20261120))
HISTORY={'zh:lexical.content_overlap','zh:lexical.trigram_reuse','zh:syntax.initial_pos_reuse'}


def digest(x):
    return sha256(x if isinstance(x,bytes) else x.encode()).hexdigest()


def serial(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def select_components(rows, counts=None):
    counts=counts or {'train':16,'dev':8}  # count PER source
    components=defaultdict(list)
    for r in rows: components[r['component_id']].append(r)
    representatives=[]; excluded=0
    for component, group in components.items():
        if len({r['split'] for r in group})!=1:
            raise ValueError('Copy component crosses frozen splits')
        if len({r['source'] for r in group})!=1:
            excluded+=1;continue
        r=min(group,key=lambda r:r['pair_id'])
        if r['split'] in counts and r['source'] in ('baike','web'):
            if r['fit_eligible_arms']!=['human','chatgpt']:
                raise ValueError('Frozen fit arms mismatch')
            representatives.append(r)
    chosen=[]
    for split,n in counts.items():
        if split not in ('train','dev') or type(n) is not int or n<1:raise ValueError('Invalid selection scope')
        for source in ('baike','web'):
            group=[r for r in representatives if r['split']==split and r['source']==source]
            group.sort(key=lambda r:digest(SEED+'\0'+split+'\0'+source+'\0'+r['component_id']))
            if len(group)<n:raise ValueError('Insufficient metadata support; no source replacement')
            chosen.extend(group[:n])
    return chosen,{'conflicting_source_components_excluded':excluded,
        'selected_counts':dict(Counter(r['split']+'|'+r['source'] for r in chosen))}


def read_selected(stream,row,selected_ids,phase):
    """Every scope check precedes seek/read. Never opens a second archive."""
    if (phase not in ('train','dev') or row['split']!=phase
            or row['pair_id'] not in selected_ids
            or row['fit_eligible_arms']!=['human','chatgpt']):
        raise PermissionError('Unselected or forbidden split/arm before raw read')
    loc=row['raw_rows']['chatgpt']
    if (Path(stream.name).name!='qazh_chatgpt.jsonl' or loc['file']!='qazh_chatgpt.jsonl'
            or type(loc['offset_bytes']) is not int or loc['offset_bytes']<0
            or type(loc['length_bytes']) is not int or not 0<loc['length_bytes']<1000000):
        raise PermissionError('Raw archive/locator firewall')
    if not isinstance(stream,io.RawIOBase):
        raise PermissionError('Unbuffered raw I/O required before seek/read')
    stream.seek(loc['offset_bytes']); data=stream.read(loc['length_bytes'])
    if len(data)!=loc['length_bytes']:raise ValueError('Short selected row')
    raw=json.loads(data)
    if raw['model']!='chatgpt' or raw['source']!=row['source'] or raw['source_ID']!=row['source_ID']:
        raise ValueError('Selected source identity mismatch')
    family=json.dumps([raw['source'],type(raw['source_ID']).__name__,raw['source_ID']],ensure_ascii=False,separators=(',',':'))
    if family!=row['question_family_id'] or digest(raw['prompt'])!=row['prompt_sha256']:
        raise ValueError('Question identity mismatch')
    if digest(json.dumps([family,raw['prompt'],raw['human_text']],ensure_ascii=False,separators=(',',':')))!=row['pair_id']:
        raise ValueError('Pair identity mismatch')
    for arm,key in [('human','human_text'),('chatgpt','machine_text')]:
        text=raw[key]; expected=row['arms'][arm]
        if (digest(text) if isinstance(text,str) else None)!=expected['original_text_sha256']:
            raise ValueError('Selected text identity mismatch')
        if (len(text) if isinstance(text,str) else None)!=expected['chars']:
            raise ValueError('Selected character count mismatch')
    return raw


def aligned_prefix_pair(a,b,tokenizer):
    if not all(isinstance(s,str) and s.strip() for s in (a,b)):
        return {'available':False,'reason':'blank_or_nonstring_arm','windows':None}
    initial=[]
    for text in (a,b):
        x=tokenizer(text,add_special_tokens=False,return_offsets_mapping=True,truncation=False)
        ids=x['input_ids']; offsets=x['offset_mapping']
        if len(ids)!=len(offsets) or any(not (0<=s<e<=len(text)) for s,e in offsets):
            raise ValueError('Invalid tokenizer Unicode offsets')
        if any(offsets[i][0]<offsets[i-1][0] for i in range(1,len(offsets))):
            raise ValueError('Nonmonotone tokenizer offsets')
        initial.append((ids,offsets))
    maximum=min(256,*(len(x[0]) for x in initial))
    for n in range(maximum,0,-1):
        windows=[]
        for text,(ids,offsets) in zip((a,b),initial):
            end=offsets[n-1][1]; prefix=text[:end]
            again=tokenizer(prefix,add_special_tokens=False,truncation=False)['input_ids']
            if again!=ids[:n]:break
            windows.append({'text':prefix,'ids':again,'end_char':end,'sha256':digest(prefix)})
        if len(windows)==2:
            return {'available':True,'reason':None,'n_tokens':n,'initial_maximum':maximum,
                'alignment_reduction':maximum-n,'windows':windows}
    return {'available':False,'reason':'no_common_roundtrip_prefix','windows':None}


def mst_energy(distance):
    """Dense deterministic Prim; zero-length duplicate edges are genuine edges.

    O(N^2), no epsilon perturbation and no sparse-zero-as-missing convention.
    """
    d=np.asarray(distance,dtype=float); n=len(d)
    if d.shape!=(n,n) or n<2 or not np.isfinite(d).all() or (d<0).any():
        raise ValueError('Finite nonnegative square distance matrix required')
    if not np.allclose(d,d.T,rtol=1e-12,atol=1e-12):raise ValueError('Asymmetric distance')
    used=np.zeros(n,dtype=bool); used[0]=True; best=d[0].copy(); total=0.
    for _ in range(n-1):
        choices=np.where(used,np.inf,best); j=int(np.argmin(choices))
        total+=float(choices[j]); used[j]=True;best=np.minimum(best,d[j])
    return total


def slope_schedules(cloud):
    cloud=np.asarray(cloud,dtype=np.float64); n=len(cloud)
    if cloud.ndim!=2 or not np.isfinite(cloud).all():raise ValueError('Invalid cloud')
    grid=sorted({int(np.floor(n*f)) for f in (.25,.375,.5,.625,.75,.875,1.)})
    if n<50 or len(grid)<4 or min(grid)<2:
        return {'available':False,'reason':'operational_N_or_grid_gate','n':n,'grid':grid}
    # Dense distance construction uses only a single cloud; no whitening/fitting.
    from scipy.spatial.distance import cdist
    d=cdist(cloud,cloud,metric='euclidean'); full=mst_energy(d)
    if full<=0:return {'available':False,'reason':'nonpositive_MST_energy','n':n,'grid':grid}
    x=np.log(grid); xc=x-x.mean(); denom=xc@xc; slopes=[]; saved_energies=[]
    for seed in SEEDS:
        rng=np.random.default_rng(seed); reruns=[]; seed_energies=[]
        for _ in range(3):
            energy=[]
            for k in grid:
                draws=[]
                for _ in range(3):
                    indices=rng.choice(n,k,replace=False)
                    draws.append(full if k==n else mst_energy(d[np.ix_(indices,indices)]))
                energy.append(float(np.mean(draws)))
            if any(e<=0 or not np.isfinite(e) for e in energy):
                return {'available':False,'reason':'nonpositive_MST_energy','n':n,'grid':grid}
            y=np.log(energy);reruns.append(float(xc@(y-y.mean())/denom));seed_energies.append(energy)
        slopes.append(reruns);saved_energies.append(seed_energies)
    a=np.asarray(slopes); means=a.mean(1)
    if not np.isfinite(a).all():return {'available':False,'reason':'nonfinite_slope','n':n,'grid':grid}
    return {'available':True,'reason':None,'n':n,'grid':grid,'seed_ids':list(SEEDS),
        'rerun_slopes':slopes,'mean_MST_energies_by_schedule_rerun_scale':saved_energies,'cloud_float64_sha256':digest(np.ascontiguousarray(cloud).tobytes()),'schedule_means':means.tolist(),'mean':float(means.mean()),
        'sd':float(means.std(ddof=1)),'mc_se':float(means.std(ddof=1)/np.sqrt(20)),
        'out_of_interval_reruns':int(((a<0)|(a>=1)).sum())}


def typed_values(measurements,channels):
    values=[]; observed=[]; opportunities=[]; reasons=[]
    if len(channels)!=68 or len(set(channels))!=68 or set(channels)&HISTORY:
        raise ValueError('Exact 68 non-history channels required')
    for c in channels:
        m=measurements[c]; v=m['value'];o=m['opportunities'];reason=m['missing_reason']
        if m['comparison_eligible'] is not False:raise ValueError('Instrument status promoted')
        if v is None:
            if m['status']!='unavailable' or reason is None:raise ValueError('Malformed unavailable channel')
        elif (not np.isfinite(v) or reason is not None
              or m['status']!=('zero_observed' if v==0 else 'observed')
              or o is None or not np.isfinite(o) or o<=0):
            raise ValueError('Observed value lacks audited opportunity')
        if o is not None and (not np.isfinite(o) or o<0):raise ValueError('Invalid opportunity')
        values.append(v);observed.append(v is not None);opportunities.append(o);reasons.append(reason)
    return {'values':values,'observed':observed,'opportunities':opportunities,'missing_reasons':reasons}


def aggregate_measurements(records,phase,selection_sha):
    """Aggregate coverage/confounds; suppress numeric summaries for tiny cells."""
    def summary(values):
        finite=np.asarray([v for v in values if v is not None and np.isfinite(v)],float)
        result={'n_total':len(values),'n_finite':len(finite),'n_unavailable':len(values)-len(finite)}
        if len(finite)>=5:result.update(mean=float(finite.mean()),median=float(np.median(finite)),min=float(finite.min()),max=float(finite.max()))
        else:result['numeric_summary']='suppressed_below_five'
        return result
    groups=defaultdict(list);pairs=defaultdict(list)
    for r in records:
        if r.get('alignment_verified'):
            ids=r['encoded_input_ids']; mask=r['encoded_special_tokens_mask']
            if (len(ids)!=len(mask) or any(m not in (0,1) for m in mask)
                    or [i for i,m in zip(ids,mask) if m==0]!=r['aligned_content_ids']
                    or len(r['aligned_content_ids'])!=r['content_tokens']
                    or digest(r['window_text'])!=r['window_sha256']
                    or r['linguistic_input_sha256']!=r['window_sha256']):
                raise ValueError('Stored alignment/linguistic integrity mismatch')
        if r['topology']['available']:
            t=r['topology']; slopes=np.asarray(t['rerun_slopes'],float)
            if (slopes.shape!=(20,3) or not np.isfinite(slopes).all() or tuple(t['seed_ids'])!=SEEDS
                    or not np.isfinite([t['mean'],t['sd'],t['mc_se']]).all()):
                raise ValueError('Nonfinite/incomplete available topology')
        groups[r['split']+'|'+r['source']+'|'+r['arm']].append(r);pairs[r['component_id']].append(r)
    cells={}
    for k,rows in sorted(groups.items()):
        cells[k]={'selected_arms':len(rows),'topology_available_arms':sum(r['topology']['available'] for r in rows),
            'alignment_available_arms':sum(r['alignment']['available'] for r in rows),
            'alignment_verified_arms':sum(r.get('alignment_verified',False) for r in rows),
            'topology_reasons':dict(Counter(r['topology'].get('reason') or 'available' for r in rows)),
            'token_count':summary([r['content_tokens'] for r in rows]),'han_count':summary([r.get('han_characters') for r in rows]),
            'unknown_token_rate':summary([r['unknown_token_rate'] for r in rows]),
            'repeated_vector_fraction':summary([r.get('repeated_vector_fraction') for r in rows]),
            'realized_grid_counts':dict(Counter(','.join(map(str,r['topology'].get('grid',[]))) for r in rows)) if len(rows)>=5 else 'suppressed_below_five',
            'typed_missing_linguistic_values':sum(v is None for r in rows for v in r['linguistic']['values'])}
    paired=defaultdict(lambda:{'selected_pairs':0,'finite_topology_pairs':0,'verified_alignment_pairs':0})
    for rows in pairs.values():
        if len(rows)!=2 or {r['arm'] for r in rows}!={'human','chatgpt'}:raise ValueError('Incomplete coverage pair')
        c=paired[rows[0]['split']+'|'+rows[0]['source']];c['selected_pairs']+=1
        c['finite_topology_pairs']+=all(r['topology']['available'] for r in rows)
        c['verified_alignment_pairs']+=all(r.get('alignment_verified',False) for r in rows)
    return {'phase':phase,'selected_pairs':len(pairs),'records':len(records),'selection_sha256':selection_sha,
        'groups':cells,'paired_coverage':dict(paired),'raw_test_bodies_read':0,'davinci_bodies_read':0,
        'all_alignment_verified':all(r.get('alignment_verified',False) for r in records),
        'all_topology_finite':all(r['topology']['available'] for r in records)}
