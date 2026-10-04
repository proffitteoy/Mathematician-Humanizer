#!/usr/bin/env python3
"""Strict final gate: pinned measurements, semantic review, fresh lint and warning dispositions."""
import argparse
import hashlib
import json
from pathlib import Path
from check_revision import check
from prose_lint import lint

def warning_id(warning):
    return hashlib.sha256(json.dumps(warning,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def editorial_check(before,after,original,candidate,review,locks=()):
    base=check(before,after,original,candidate,review)
    fresh=lint(original,candidate,locks)
    problems=list(base.get('blockers',[]))
    if fresh['blockers']:problems.append('protected_content_changed')
    if not isinstance(review,dict):review={}
    rows=review.get('editorial_review',[])
    if not isinstance(rows,list):rows=[]
    dispositions={r.get('warning_id'):r for r in rows if isinstance(r,dict)}
    for warning in fresh['warnings']:
        key=warning_id(warning);warning['warning_id']=key
        d=dispositions.get(key,{})
        if d.get('decision') not in ('retain_for_meaning_or_voice','reviewed_no_semantic_change') or not isinstance(d.get('reason'),str) or not d['reason'].strip():
            problems.append('unreviewed_lint_warning:'+key)
    if review.get('editorial_context') not in ('essay','technical','mathematical','procedural','other'):
        problems.append('editorial_context_missing')
    if review.get('protected_literals') != list(locks): problems.append('protected_literals_not_bound_to_review')
    if review.get('unchanged_content_reviewed') is not True:problems.append('unchanged_content_not_reviewed')
    if review.get('unsupported_stance_or_experience') is not False:problems.append('stance_or_experience_not_reviewed')
    return {'schema':'integrated-editorial-check/1','status':'MEASURED_AND_EDITORIALLY_REVIEWED' if not problems and base['status']=='MEASURED_AND_REVIEWED' else 'NEEDS_REVISION_OR_REVIEW',
            'measurement_and_semantic_check':base,'fresh_lint':fresh,'blockers':problems,
            'interpretation':'Exact-byte workflow and explicit self-review only. Not semantic proof, independent quality validation, or an authorship score.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('original_measurement',type=Path);p.add_argument('candidate_measurement',type=Path)
    p.add_argument('--original-text',required=True,type=Path);p.add_argument('--candidate-text',required=True,type=Path);p.add_argument('--review',required=True,type=Path);p.add_argument('--locks',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():p.error('Output exists; use a new receipt')
    read=lambda path:json.loads(path.read_text(encoding='utf-8'))
    locks=read(a.locks) if a.locks else []
    if not isinstance(locks,list):p.error('Locks must be array')
    result=editorial_check(read(a.original_measurement),read(a.candidate_measurement),a.original_text.read_bytes(),a.candidate_text.read_bytes(),read(a.review),locks)
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'status':result['status'],'blockers':result['blockers']},ensure_ascii=False))
    return 0 if result['status']=='MEASURED_AND_EDITORIALLY_REVIEWED' else 2
if __name__=='__main__':raise SystemExit(main())
