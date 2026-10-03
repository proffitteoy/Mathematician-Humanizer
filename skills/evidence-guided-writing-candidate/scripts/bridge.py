"""Evidence-guided host-LLM candidate workflow, with separated safety/style axes.

Generation and semantic review are performed by the invoking assistant. This
runner never invents review judgments, calls an API, or ranks by a style proxy.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, re, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'style-writing-prototype'
sys.path.insert(0,str(BASE/'scripts'))
from analyze import Analyzer, DEFAULT_RESEARCH
from workflow import binding, finalize, read, write, diagnose
from contrast import digest, finite

SURFACE_IDS={'F002','F003','F013','F014','F015','F016','F024','F025'}
SURFACE_PROFILE={'version':'source-units-gap-safe/0.1.0',
 'segmenter_version':'punctuation-lines/1.0.0','operational_feature_version':'character-core/1.0.0',
 'offset_unit':'unicode_codepoint','normalization':'none',
 'unit_policy':'segment_full_source_then_select_complete_units',
 'pair_policy':'original_consecutive_sentences_in_one_target_component'}
INSTRUMENT_FILES={'research/surface/adapter.py','src/style_compiler/contracts.py',
                  'src/style_compiler/features.py','src/style_compiler/segmentation.py'}


def validate_evidence(evidence):
    model=evidence.get('model',{});audit=evidence.get('development_audit',{})
    if model.get('schema_version')!='paired-style-evidence/0.1' or audit.get('schema_version')!='paired-style-dev-audit/0.1':
        raise ValueError('Unsupported evidence schema')
    if audit.get('model_sha256')!=digest(model):
        raise ValueError('Evidence model/audit binding mismatch')
    cards=model.get('features',[]);audits=audit.get('features',[])
    if len({c['feature_id'] for c in cards})!=len(cards) or {c['feature_id'] for c in cards}!={c['feature_id'] for c in audits} or len(cards)!=len(audits):
        raise ValueError('Evidence feature inventory mismatch')
    if model.get('fit_split')!='TRAIN' or audit.get('test_opened') is not False:
        raise ValueError('Evidence must be TRAIN-fitted / DEV-audited only')
    if not isinstance(model.get('measurement_profile'),dict) or model.get('measurement_profile_sha256')!=digest(model['measurement_profile']):
        raise ValueError('Evidence profile hash mismatch')
    return model,{c['feature_id']:c for c in audits}


def verify_instrument(analyzer,model):
    hashes=model.get('provenance',{}).get('instrument_source_sha256')
    if not hashes:
        if model.get('input_role')=='observational_train_dev':
            raise ValueError('Observed-corpus evidence must pin instrument source hashes')
        return False
    if set(hashes)!=INSTRUMENT_FILES or not hasattr(analyzer,'repo'):
        raise ValueError('Incomplete or unknown instrument implementation binding')
    for name,expected in hashes.items():
        path=Path(analyzer.repo)/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Instrument implementation changed: '+name)
    return True


def values(analysis):
    return {k:v for k,v in analysis['summary']['surface_values'].items() if k in SURFACE_IDS}


def evidence_cards(analysis,evidence,domain):
    model,audits=validate_evidence(evidence)
    source=values(analysis);out=[]
    for card in model['features']:
        f=card['feature_id'];v=source.get(f)
        support=audits[f]['inspection_supported'] and domain in model['domains']
        ref=card['train_domains'].get(domain,card['train'])
        # Training and candidate measurements must use an identical declared profile.
        instrument_match=(model['measurement_identity']==analysis.get('evidence_measurement_identity')
                          and model['measurement_profile_sha256']==analysis['surface'].get('measurement_profile_sha256')
                          and model['measurement_profile']==analysis['surface'].get('measurement_profile'))
        out.append({'feature_id':f,'observed':v,'train_human_median':ref['human_median'],
                    'paired_human_minus_ai':ref['human_minus_ai'],
                    'train_human_q10_q90':ref['human_q10_q90'],
                    'dev_direction_reproduced':audits[f]['dev_direction_reproduced'],
                    'instrument_comparison_eligible':analysis['surface']['target_projection']['features'].get(f,{}).get('eligible_for_comparison',False),
                    'comparison_status':'Exploratory inspection only; instrument validation is not established',
                    'input_transport_validated':False,
                    'available_for_inspection':bool(support and finite(v) and instrument_match),
                    'unavailable_reason':None if support and finite(v) and instrument_match else
                     ('instrument_mismatch' if not instrument_match else 'unsupported_domain_direction_or_missing_value'),
                    'instruction':'Inspect this source choice in context; preserve it unless a concrete, source-grounded writing problem is found. Do not optimize toward a number.'})
    return out


def strict_checks(job,candidate):
    source,text=job['original'],candidate['text'];issues=[]
    # Count repeated tokens and signs/units. This is still not semantic equivalence.
    token=r'(?<![A-Za-z\d])[-+−]?\d+(?:\.\d+)?(?:%|％|℃|°C|kg|mg|km|cm|mm|ms|秒|分钟|小时|天|元|万元|人|次|个)?'
    before=collections.Counter(re.findall(token,source));after=collections.Counter(re.findall(token,text))
    if before!=after:
        issues.append({'code':'numeric_multiset_changed','removed':list((before-after).elements()),'added':list((after-before).elements())})
    for protected in job.get('protected',[]):
        if source.count(protected)!=text.count(protected):
            issues.append({'code':'protected_span_count_changed','span':protected})
    review=candidate.get('review',{})
    if review.get('ledger_completeness')!='checked_no_omissions':
        issues.append({'code':'ledger_completeness_not_reviewed'})
    if review.get('relations_and_scope')!='checked_preserved':
        issues.append({'code':'relations_and_scope_not_reviewed'})
    return {'status':'pass' if not issues else 'fail','issues':issues,
            'warning':'Role swaps with the same numeric tokens can pass mechanical checks; independent review is still required'}


def measured(analyzer,text,label,identity):
    a=analyzer.analyze(text,label)
    # Only one known profile may be bound here; never relabel parser summaries.
    if identity=='surface-source-units-gap-safe/0.1.0':
        surface=a.get('surface',{});profile=surface.get('measurement_profile',{})
        if any(profile.get(k)!=v for k,v in SURFACE_PROFILE.items()) or not isinstance(profile.get('unicode_version'),str):
            raise ValueError('Actual analyzer profile is missing or incompatible')
        if surface.get('measurement_profile_sha256')!=digest(profile):
            raise ValueError('Actual analyzer profile hash is inconsistent')
        a['evidence_measurement_identity']=identity
    else:
        raise ValueError('No candidate extractor for this evidence instrument')
    return a


def evaluate(job,analyzer,evidence,domain):
    model,_=validate_evidence(evidence)
    implementation_verified=verify_instrument(analyzer,model)
    if domain not in model['domains']:
        raise ValueError('Unsupported evidence domain; do not relabel the input')
    if job.get('evidence_sha256')!=digest(evidence):
        raise ValueError('Job evidence hash missing or stale; prepare and inspect again')
    if job.get('evidence_domain')!=domain:
        raise ValueError('Prepared evidence domain changed; prepare and inspect again')
    identity=model['measurement_identity']
    source=measured(analyzer,job['original'],job.get('id','job'),identity)
    if source['surface']['measurement_profile_sha256']!=model['measurement_profile_sha256']:
        raise ValueError('Source and training instrument differ')
    cards=evidence_cards(source,evidence,domain)
    lookup={c['feature_id']:c for c in cards}
    for c in job.get('candidates',[]):
        for f in c.get('evidence_card_ids',[]):
            if f not in lookup or not lookup[f]['available_for_inspection']:
                raise ValueError('Candidate cites unsupported evidence card: '+str(f))
        if c.get('evidence_card_ids') and not c.get('source_problem_evidence'):
            raise ValueError('A measured association alone is not a source writing problem')
        if c.get('source_problem_evidence') and c['source_problem_evidence'] not in job['original']:
            raise ValueError('Source problem evidence must be an exact excerpt')
    result=finalize(job,analyzer)
    candidate_by_id={c['id']:c for c in job['candidates']}
    for row in result['candidates']:
        c=candidate_by_id[row['id']];checks=strict_checks(job,c)
        row['strict_checks']=checks
        row['evidence_card_ids']=c.get('evidence_card_ids',[])
        row['source_problem_evidence']=c.get('source_problem_evidence')
        row['eligible_for_user_test']=row['eligible_for_user_test'] and checks['status']=='pass'
        candidate_analysis=measured(analyzer,c['text'],c['id'],identity)
        if candidate_analysis['surface']['measurement_profile_sha256']!=model['measurement_profile_sha256']:
            raise ValueError('Candidate and training instrument differ')
        candidate_values=values(candidate_analysis)
        comparisons=[]
        for card in cards:
            f=card['feature_id'];v=candidate_values.get(f);ref=card['train_human_median']
            if not (card['available_for_inspection'] and finite(v) and finite(ref)):
                continue
            comparisons.append({'feature_id':f,'source':card['observed'],'candidate':v,'raw_delta':v-card['observed'],
                                'change_in_distance_to_train_human_median':abs(v-ref)-abs(card['observed']-ref),
                                'interpretation':'Descriptive movement only, not benefit, identity probability, or semantic credit'})
        row['style_observations']=comparisons
        row['review_provenance']=c.get('review',{}).get('reviewer_type')
    eligible={r['id']:r for r in result['candidates'] if r['eligible_for_user_test']}
    selected=next((eligible[x] for x in job.get('selection_preference',[]) if x in eligible),None)
    # No fallback to best feature score, and no automatic eligibility promotion.
    result.update({'schema_version':'evidence-guided-writing-result/0.1',
                   'status':'reviewed_candidate_for_user_test' if selected else 'abstained',
                   'selected_candidate_id':selected['id'] if selected else None,
                   'final_text':selected['text'] if selected else None,
                   'evidence_sha256':digest(evidence),'evidence_cards':cards,
                   'evidence_role':model['input_role'],
                   'instrument_implementation_verified':implementation_verified,
                   'reference_applicability':job.get('reference_applicability',{'status':'unvalidated_transport_hypothesis'}),
                   'candidate_timing':job.get('initial_candidate_timing','not independently established'),
                   'generation_method':'Host language model; no project-trained generator',
                   'semantic_equivalence':'provisionally reviewed, not proved',
                   'style_benefit':'unvalidated; feature change is not reader judgment',
                   'personal_stage_enabled':False,
                   'abstention_reason':None if selected else 'No explicitly preferred candidate passed all fidelity/review gates'})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('input',type=Path);a.add_argument('--genre',default='general')
    b=sub.add_parser('evaluate');b.add_argument('job',type=Path)
    for s in (a,b):
        s.add_argument('--evidence',type=Path,required=True);s.add_argument('--domain',required=True)
        s.add_argument('--research',type=Path,default=DEFAULT_RESEARCH);s.add_argument('--output',type=Path,required=True)
        s.add_argument('--models',type=Path)
    args=p.parse_args();evidence=read(args.evidence);model,_=validate_evidence(evidence)
    analyzer=Analyzer(args.research,args.models)
    verify_instrument(analyzer,model)
    if args.command=='prepare':
        if args.domain not in model['domains']:
            raise ValueError('Unsupported evidence domain; do not relabel the input')
        text=args.input.read_text();analysis=measured(analyzer,text,args.input.stem,model['measurement_identity'])
        if analysis['surface']['measurement_profile_sha256']!=model['measurement_profile_sha256']:
            raise ValueError('Source and training instrument differ')
        job={'schema_version':'writing-job/0.1','id':args.input.stem,'original':text,'genre':args.genre,
             'claims':[],'protected':[],'candidates':[],'selection_preference':[],
             'source_declaration':'user_supplied_input','length_ratio_bounds':[.4,1.8],
             'evidence_sha256':digest(evidence),'evidence_domain':args.domain}
        job['reference_applicability']={'status':'unvalidated_transport_hypothesis',
          'reason':'Reference domain is a source collection; selecting its label does not establish corpus-to-input genre transport'}
        write(args.output,job)
        write(args.output.with_suffix('.diagnosis.json'),{'diagnosis':diagnose(text,args.genre,analysis),
              'evidence_cards':evidence_cards(analysis,evidence,args.domain)})
        print('Prepared evidence-guided job. Read SKILL.md and draft/review actual candidates before evaluate.')
    else:
        result=evaluate(read(args.job),analyzer,evidence,args.domain);write(args.output,result)
        args.output.with_suffix('.txt').write_text(result['final_text'] or result['rollback_text'])
        print(json.dumps({'status':result['status'],'selected_candidate':result['selected_candidate_id']},ensure_ascii=False))
        return 0 if result['final_text'] else 2


if __name__=='__main__':
    raise SystemExit(main())
