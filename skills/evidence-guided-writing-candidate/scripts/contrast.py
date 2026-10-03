"""Exploratory paired TRAIN contrasts and strictly separate DEV audit.

No raw corpus access, detector probability, rewrite utility, or TEST evaluation.
The paired component is the resampling unit. All inspected features are retained.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, math, random, statistics
from pathlib import Path

VERSION = 'paired-style-evidence/0.1'


def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    at = (len(xs)-1)*p
    lo, hi = math.floor(at), math.ceil(at)
    return xs[lo] + (at-lo)*(xs[hi]-xs[lo])


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def validate(data):
    if data.get('schema_version') != 'paired-style-observations/0.1':
        raise ValueError('Unsupported observation schema')
    if data.get('role') not in {'synthetic_mechanism_fixture', 'observational_train_dev'}:
        raise ValueError('Declare actual input role')
    if not data.get('measurement_identity') or not data.get('provenance'):
        raise ValueError('Measurement identity and provenance required')
    profile=data.get('measurement_profile')
    if not isinstance(profile,dict) or data.get('measurement_profile_sha256')!=digest(profile):
        raise ValueError('Full measurement profile and matching hash required')
    rows = data.get('rows', [])
    if not rows:
        raise ValueError('No observations')
    seen, components, pairs = set(), {}, {}
    for row in rows:
        if row.get('split') not in {'TRAIN', 'DEV'}:
            raise ValueError('Only explicitly exposed TRAIN/DEV rows are allowed')
        if row.get('condition') not in {'HUMAN', 'CHATGPT'}:
            raise ValueError('Only HUMAN/CHATGPT arms; no held-out generator')
        for key in ('pair_id', 'component_id', 'domain'):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError('Missing '+key)
        key = (row['pair_id'], row['condition'])
        if key in seen:
            raise ValueError('Duplicate pair/arm')
        seen.add(key)
        for ids, key in ((components, row['component_id']), (pairs, row['pair_id'])):
            if key in ids and ids[key] != row['split']:
                raise ValueError('Cross-split lineage/pair leakage')
            ids[key] = row['split']
        if not isinstance(row.get('features'), dict) or not row['features']:
            raise ValueError('Explicit feature map required')
        if any(v is not None and not finite(v) for v in row['features'].values()):
            raise ValueError('Finite feature values or explicit null only')
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row['pair_id']].append(row)
    for pair in grouped.values():
        if len(pair) != 2 or {r['condition'] for r in pair} != {'HUMAN', 'CHATGPT'}:
            raise ValueError('Complete paired arms required')
        if any(pair[0][k] != pair[1][k] for k in ('component_id', 'domain', 'split')):
            raise ValueError('Pair metadata disagreement')
    return grouped


def pairs_for(grouped, split, feature, domain=None):
    out = []
    for pair in grouped.values():
        a = {r['condition']: r for r in pair}
        h, ai = a['HUMAN'], a['CHATGPT']
        if h['split'] != split or (domain is not None and h['domain'] != domain):
            continue
        hv, av = h['features'].get(feature), ai['features'].get(feature)
        if finite(hv) and finite(av):
            out.append((h['component_id'], hv, av))
    return out


def summarize_pairs(pairs, bootstrap=0, seed=0):
    if not pairs:
        return {'pairs': 0, 'components': 0, 'human_minus_ai': None, 'ci95': None,
                'human_median': None, 'human_q10_q90': None, 'human_sd': None}
    by_component = collections.defaultdict(list)
    for component, h, a in pairs:
        by_component[component].append(h-a)
    # Each independent component has equal weight, not every sentence/view.
    diffs = [statistics.mean(v) for _, v in sorted(by_component.items())]
    hs = [p[1] for p in pairs]
    ci = None
    if bootstrap and len(diffs) >= 2:
        rng = random.Random(seed)
        draws = [statistics.mean(rng.choices(diffs, k=len(diffs))) for _ in range(bootstrap)]
        ci = [q(draws, .025), q(draws, .975)]
    return {'pairs': len(pairs), 'components': len(diffs),
            'human_minus_ai': statistics.mean(diffs), 'ci95': ci,
            'human_median': statistics.median(hs), 'human_q10_q90': [q(hs,.1),q(hs,.9)],
            'human_sd': statistics.stdev(hs) if len(hs)>1 else None}


def fit(data, bootstrap=400):
    grouped = validate(data)
    # Definition, reference ranges, directions and uncertainty use TRAIN only.
    features = sorted({f for r in data['rows'] if r['split']=='TRAIN' for f in r['features']})
    domains = sorted({r['domain'] for r in data['rows'] if r['split']=='TRAIN'})
    train_rows = [r for r in data['rows'] if r['split']=='TRAIN']
    cards = []
    for i, f in enumerate(features):
        train = summarize_pairs(pairs_for(grouped,'TRAIN',f), bootstrap, 1729+i)
        by_domain = {d:summarize_pairs(pairs_for(grouped,'TRAIN',f,d),bootstrap,1729+i)
                     for d in domains}
        diff, ci = train['human_minus_ai'], train['ci95']
        direction = 0 if diff in (0,None) else (1 if diff>0 else -1)
        stable = bool(ci and ci[0]*ci[1]>0 and train['components']>=8)
        domain_agreement = all(v['components']>=4 and v['human_minus_ai'] is not None
                               and v['human_minus_ai']*direction>0 for v in by_domain.values())
        cards.append({'feature_id':f, 'train':train, 'train_domains':by_domain,
                      'direction':direction,
                      'train_inspection_eligible':stable and domain_agreement,
                      'eligibility_note':'Engineering screening rule, not multiplicity-adjusted confirmatory inference or an editing-effect estimate'})
    return {'schema_version':VERSION,'input_role':data['role'],
            'train_sha256':digest(train_rows),'measurement_identity':data['measurement_identity'],
            'measurement_profile':data['measurement_profile'],
            'measurement_profile_sha256':data['measurement_profile_sha256'],
            'provenance':data['provenance'],'bootstrap_draws':bootstrap,'fit_split':'TRAIN',
            'features':cards,'domains':domains,'human_quality_probability':None,
            'learned_object':'Paired observational feature contrasts and TRAIN reference summaries; not a learned rewrite policy',
            'limitations':['Dataset human label is not independently verified unassisted authorship',
                           'All coordinates are exploratory; correlated features and multiple inspection are uncorrected',
                           'Prompt, length, genre and collection can explain contrasts; they are not causal style effects',
                           'Moving a candidate toward a human median does not establish writing benefit']}


def audit(model, data):
    grouped = validate(data)
    if model['train_sha256'] != digest([r for r in data['rows'] if r['split']=='TRAIN']):
        raise ValueError('TRAIN binding changed')
    if model['measurement_identity'] != data['measurement_identity'] or model['measurement_profile_sha256'] != data['measurement_profile_sha256']:
        raise ValueError('Instrument mismatch')
    cards = []
    for card in model['features']:
        f = card['feature_id']
        dev = summarize_pairs(pairs_for(grouped,'DEV',f))
        by_domain = {d:summarize_pairs(pairs_for(grouped,'DEV',f,d)) for d in model['domains']}
        ok = dev['components']>=4 and dev['human_minus_ai'] is not None and dev['human_minus_ai']*card['direction']>0
        ok = ok and all(v['components']>=2 and v['human_minus_ai'] is not None and v['human_minus_ai']*card['direction']>0
                        for v in by_domain.values())
        cards.append({'feature_id':f,'dev':dev,'dev_domains':by_domain,
                      'dev_direction_reproduced':bool(ok),
                      'inspection_supported':bool(ok and card['train_inspection_eligible'])})
    return {'schema_version':'paired-style-dev-audit/0.1','model_sha256':digest(model),
            'dev_sha256':digest([r for r in data['rows'] if r['split']=='DEV']),
            'features':cards,'test_opened':False,'status':'exploratory_development_audit',
            'selection_warning':'Any subsequent use is development-adapted, not held-out confirmation'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('observations',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();data=json.loads(args.observations.read_text())
    model=fit(data);result={'model':model,'development_audit':audit(model,data)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'features':len(model['features']),'supported_inspections':sum(c['inspection_supported'] for c in result['development_audit']['features']), 'output':str(args.output)}))


if __name__=='__main__':
    main()
