"""Replay complete reviewed synthetic-development examples; no text generation."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from bridge import ROOT, Analyzer, DEFAULT_RESEARCH, evaluate, read, write
from contrast import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--examples',type=Path,default=ROOT/'examples')
    p.add_argument('--domain',default='web')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--research',type=Path,default=DEFAULT_RESEARCH)
    args=p.parse_args();evidence=read(args.evidence);analyzer=Analyzer(args.research)
    summary={'schema_version':'development-demonstration/0.1',
             'role':'synthetic_development_demonstration_not_blind_human_validation',
             'evidence_sha256':digest(evidence),'results':[],
             'training_or_test_data_rewritten':False,'paid_generation_calls':0,
             'learned_generator_used':False,'acceptance':'owner judgment pending'}
    prose=['# Actual development rewrites','',
           'These new inputs are synthetic development demonstrations, not natural human reference texts or held-out tests. Initial edits preceded the corpus cards. Feature deltas are descriptive; no reader benefit is established. All failures are retained.','']
    for path in sorted(args.examples.glob('*.json')):
        job=read(path)
        if job.get('schema_version')!='writing-job/0.1':
            continue
        result=evaluate(job,analyzer,evidence,args.domain)
        write(args.output/(job['id']+'.result.json'),result)
        (args.output/(job['id']+'.txt')).write_text(result['final_text'] or result['rollback_text'])
        summary['results'].append({'id':job['id'],'status':result['status'],
          'selected':result['selected_candidate_id'],'candidates':[
            {'id':c['id'],'mechanical':c['mechanical_checks']['status'],'semantic_review':c['semantic_review']['status'],
             'strict_checks':c['strict_checks']['status'],'eligible_for_user_test':c['eligible_for_user_test'],
             'style_observations':c['style_observations']} for c in result['candidates']]})
        prose+=['## '+job['id'],'','### Original','',job['original'],'']
        for candidate in result['candidates']:
            prose+=['### '+candidate['id'], '',candidate['text'],'',
                    'Recorded semantic review: '+candidate['semantic_review']['status']+'. Strict checks: '+candidate['strict_checks']['status']+'. Eligible only for owner testing: '+str(candidate['eligible_for_user_test'])+'.','']
        prose+=['Selected: '+str(result['selected_candidate_id'])+'. No claim of human indistinguishability.','']
    write(args.output/'DEVELOPMENT_RESULTS.json',summary)
    (args.output/'BEFORE_AFTER.md').write_text('\n'.join(prose)+'\n')
    print(json.dumps({'examples':len(summary['results']),'output':str(args.output),
                      'status':'demonstration_replayed_not_acceptance'},ensure_ascii=False))


if __name__=='__main__':
    main()
