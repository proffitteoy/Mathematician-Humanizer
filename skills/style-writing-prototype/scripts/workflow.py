"""Executable orchestration for an explicitly provisional host-LLM writing skill.
No LLM API, fitted style ranker, corpus access, or downloads are hidden here.
"""
from __future__ import annotations
import argparse, collections, difflib, hashlib, json, re
from pathlib import Path
from analyze import Analyzer,DEFAULT_RESEARCH,ROOT,sha
VERSION='writing-workflow/0.1'
GENRES={
 'mathematical_explanation':('hypothesis → construction → quantifier/tail argument → conclusion', 'Keep the hypothesis and every quantified dependency attached to the inference that uses it; distinguish one witness from all later terms.'),
 'technical_commentary':('failure scenario → mechanism → preconditions → guarantee boundary', 'Make the state transition and guarantee boundary explicit; never replace an association, atomicity condition or modal claim with a vague verb.'),
 'everyday_reflection':('recognizable situation → distinction → action boundary → limitation', 'Ground the distinction in objects already present; preserve may/usually and responsibility exceptions without inventing an author’s experience.'),
 'blog_argument':('claim → concrete consequence → proposed test → scope limit → conclusion', 'Expose the reasoning and carry the scope of the evidence through the conclusion; do not turn one illustrative migration path into universal proof.'),
 'general':('input-specific discourse structure', 'Revise the actual obstruction to understanding; do not impose a preselected rhythm, personal voice or genre template.')}


def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def binding(job,candidate):
    return sha(canonical({'original':job['original'],'genre':job['genre'],'claims':job['claims'],'protected':job.get('protected',[]),'candidate':candidate['text']}))
def read(path):return json.loads(Path(path).read_text())
def write(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def require(ok,msg):
    if not ok:raise ValueError(msg)

def validate_job(job):
    require(job.get('schema_version')=='writing-job/0.1','unsupported job schema')
    require(isinstance(job.get('original'),str) and bool(job['original'].strip()),'nonempty input required')
    require(len(job['original'])<=20000,'prototype limits input to 20000 codepoints; use a coherent excerpt')
    require(job.get('genre') in GENRES,'unknown genre')
    require(isinstance(job.get('claims'),list) and len(job['claims'])>0,'claim ledger required before finalization')
    seen=set()
    for claim in job['claims']:
        require(isinstance(claim.get('id'),str) and claim['id'] not in seen,'unique claim IDs required');seen.add(claim['id'])
        require(isinstance(claim.get('commitment'),str) and bool(claim['commitment'].strip()),'claim statement required')
        require(bool(claim.get('source_evidence')) and claim['source_evidence'] in job['original'],'source evidence must be an exact input excerpt')
    protected=job.get('protected',[])
    require(isinstance(protected,list) and all(isinstance(p,str) and p and p in job['original'] for p in protected),'protected spans must come from input')
    seen=set()
    require(isinstance(job.get('candidates'),list) and len(job['candidates'])>0,'at least one candidate required')
    for c in job['candidates']:
        require(isinstance(c.get('id'),str) and c['id'] not in seen,'unique candidate IDs required');seen.add(c['id'])
        require(isinstance(c.get('text'),str) and c['text'].strip(),'empty candidate')
        require(len(c['text'])<=20000,'candidate exceeds 20000-codepoint prototype bound')
    bounds=job.get('length_ratio_bounds',[0.4,1.8])
    require(len(bounds)==2 and all(type(v) in (int,float) for v in bounds) and 0<bounds[0]<=bounds[1],'invalid length bounds')

def diagnose(text,genre,analysis):
    t=analysis['surface']['target_projection'];rows=[]
    linguistic=analysis['linguistic']
    seq=linguistic.get('bundle',{}).get('target',{}).get('sequence',[])
    for s in t['sentences']:
        local=next((r for r in seq if r['source_sentence_index']==s['index']),None)
        keys=['zh:dependency.span_mean','zh:syntax.subordinate_arcs','zh:syntax.nominal_modifier_size','zh:lexical.content_overlap','zh:syntax.initial_pos_reuse']
        rows.append({'index':s['index'],'start':s['start'],'end':s['end'],'text':text[s['start']:s['end']], 'content_chars':s['content_chars'],
          'local_linguistic_observations':{k:local['measurements'][k] for k in keys} if local else None})
    # Relative inspection priority within this exact text, never a learned norm.
    longest=sorted(rows,key=lambda x:x['content_chars'],reverse=True)[:min(2,len(rows))]
    return {'status':'descriptive_diagnosis_with_provisional_interventions',
       'observations':analysis['summary'],'ordered_source_units':rows,
       'linguistic_sequence_available':bool(seq),
       'attention_sites':[{'source_sentence_index':s['index'],'source_evidence':s['text'],'basis':'one of the longest operational units in this input; length alone does not establish a defect',
                          'question':'Does this unit contain distinct logical steps whose ordering or scope is hard to follow? Keep it intact if splitting weakens the reasoning.'} for s in longest],
       'genre_path_hypothesis':GENRES[genre][0],
       'provisional_plan':[GENRES[genre][1],
         'Inspect adjacent units for premise/conclusion and referent continuity using their actual words. A low content-word overlap is only a prompt to inspect, not a continuity diagnosis.',
         'Inspect parser subordination, nominal modifier size and dependency span at the exact sentence. Only intervene if manual reading identifies an attachment or packing problem.',
         'Draft a light edit and a structural alternative. Every moved/deleted claim must remain in the claim ledger; reject unsupported additions.',
         'Re-measure candidates to describe what changed, not to maximize a feature score. Select for source fidelity, genre fit and readability; keep the original if no candidate is better.'],
       'unvalidated_assumptions':['Separating inferential steps can make some texts easier to follow','Making explicit the original mechanism and its limits may help readers',
          'These effects were not learned or estimated from the feature vectors or a human reference distribution'],
       'missing_learned_components':['trained joint linguistic/sequence/discourse style model','learned intervention policy','calibrated semantic verifier','held-out human preference or indistinguishability evidence'],
       'not_used':'12-descriptor condition classifier; it predicts its training condition, not human-like quality'}

def mechanical_checks(job,c):
    source=job['original'];text=c['text'];issues=[]
    missing=[p for p in job.get('protected',[]) if p not in text]
    if missing:issues.append({'code':'protected_span_missing','spans':missing})
    # Inventory is conservative and lexical. It does not prove numeric semantics.
    numbers=lambda s:set(re.findall(r'(?<![A-Za-z])\d+(?:\.\d+)?(?:%|％)?',s))
    added=sorted(numbers(text)-numbers(source));dropped=sorted(numbers(source)-numbers(text))
    if added or dropped:issues.append({'code':'numeric_inventory_changed','added':added,'dropped':dropped})
    urls=lambda s:set(re.findall(r'https?://[^\s，。；]+',s))
    if urls(text)-urls(source):issues.append({'code':'new_url','values':sorted(urls(text)-urls(source))})
    if re.search(r'我(?:曾经|曾|亲眼|记得)|去年我|有一次我|我们曾',text) and not re.search(r'我(?:曾经|曾|亲眼|记得)|去年我|有一次我|我们曾',source):
        issues.append({'code':'new_personal_anecdote_cue','note':'lexical tripwire, not exhaustive detection'})
    ratio=len(text)/len(source);lo,hi=job.get('length_ratio_bounds',[0.4,1.8])
    if not lo<=ratio<=hi:issues.append({'code':'length_outside_requested_bounds','ratio':ratio,'bounds':[lo,hi]})
    return {'status':'pass' if not issues else 'fail','issues':issues,'length_ratio':ratio,
       'scope':'exact span, numeric token inventory, URL, anecdote-cue and length checks only; passing is not semantic validation'}

def check_review(job,c,review):
    errors=[]
    if not review:return {'status':'missing','issues':['independent semantic review absent']}
    if review.get('binding_sha256')!=binding(job,c):errors.append('review is not bound to current input/genre/claims/protected spans/candidate')
    if review.get('reviewer_type') not in {'independent_language_model','human'}:errors.append('reviewer identity/type declaration missing')
    if review.get('verdict')!='pass':errors.append('review rejected or uncertain')
    if any(not isinstance(i,dict) or i.get('blocking',True) for i in review.get('issues',[])) or review.get('added_claims'):errors.append('unresolved semantic issues or added claims')
    claims=review.get('claims',[]);lookup={r.get('id'):r for r in claims}
    if set(lookup)!={s['id'] for s in job['claims']} or len(lookup)!=len(claims):errors.append('review must cover each claim exactly once')
    for claim in job['claims']:
        r=lookup.get(claim['id'],{})
        if r.get('status')!='preserved':errors.append('claim not preserved: '+claim['id'])
        evidence=r.get('candidate_evidence')
        spans=[evidence] if isinstance(evidence,str) else evidence
        if not isinstance(spans,list) or not spans or any(not isinstance(e,str) or not e or e not in c['text'] for e in spans):errors.append('missing or non-exact candidate evidence: '+claim['id'])
        if not r.get('explanation'):errors.append('claim rationale absent: '+claim['id'])
    return {'status':'pass' if not errors else 'fail','issues':errors,'reviewer_type':review.get('reviewer_type'),
      'scope':'Records the reviewer’s judgment and exact supporting excerpts; software cannot prove entailment or authenticate an independent reviewer'}

def load_measurement(job,variant,text,analyzer,measure_dir=None):
    if measure_dir:
        path=Path(measure_dir)/f'{job["id"]}.{variant}.json'
        if path.exists():
            a=read(path);require(a['text_sha256']==sha(text),'cached measurement does not match exact text: '+str(path));return a
    return analyzer.analyze(text,job.get('id','job')+'.'+variant)

def finalize(job,analyzer,measure_dir=None):
    validate_job(job)
    original=load_measurement(job,'original',job['original'],analyzer,measure_dir)
    diagnosis=diagnose(job['original'],job['genre'],original);candidates=[]
    for c in job['candidates']:
        checks=mechanical_checks(job,c);review=check_review(job,c,c.get('review'))
        a=load_measurement(job,c['id'],c['text'],analyzer,measure_dir)
        before=original['summary'];after=a['summary']
        delta={kind:{k:(v-before[kind][k]) if v is not None and before[kind].get(k) is not None else None for k,v in after[kind].items()}
               for kind in ['surface_values','linguistic_values']}
        candidates.append({'id':c['id'],'text':c['text'],'intent':c.get('intent'),'mechanical_checks':checks,'semantic_review':review,
           'eligible_for_user_test':checks['status']==review['status']=='pass','measurements_after':after,'observed_deltas':delta,
           'diff':list(difflib.unified_diff(job['original'].splitlines(),c['text'].splitlines(),fromfile='original',tofile=c['id'],lineterm=''))})
    eligible={c['id']:c for c in candidates if c['eligible_for_user_test']}
    preference=job.get('selection_preference',[])
    require(isinstance(preference,list) and all(p in {c['id'] for c in candidates} for p in preference),'selection preference references unknown candidate')
    selected=next((eligible[i] for i in preference if i in eligible),None)
    if selected is None and len(eligible)==1:selected=next(iter(eligible.values()))
    # Do not use numeric features as a preference tie-breaker.
    return {'schema_version':VERSION,'job_id':job.get('id'),'status':'reviewed_candidate_for_user_test' if selected else 'abstained',
       'selection_basis':job.get('selection_rationale','Declared editorial preference among candidates passing lexical checks and provisional semantic review; no learned ranking'),
       'original_text':job['original'],'diagnosis':diagnosis,'intervention_plan':job.get('intervention_plan'),'claim_ledger':job['claims'],'candidates':candidates,
       'selected_candidate_id':selected['id'] if selected else None,'final_text':selected['text'] if selected else None,
       'abstention_reason':None if selected else 'No uniquely selected, checked and reviewed candidate. Original retained; inspect failing/missing checks.',
       'rollback_text':job['original'],'acceptance':'Not accepted; owner judgment pending. No claim of human indistinguishability.',
       'quality_score':None,'limitations':job.get('limitations',[])}

def prepare(args):
    text=args.input.read_text();require(text.strip() and len(text)<=20000,'nonempty input, at most 20000 codepoints')
    analyzer=Analyzer(args.research,args.models);a=analyzer.analyze(text,args.input.stem)
    job={'schema_version':'writing-job/0.1','id':args.input.stem,'original':text,'genre':args.genre,
       'source_declaration':'user_supplied_input','claims':[],'protected':[],'candidates':[],
       'selection_preference':[],'length_ratio_bounds':[0.4,1.8]}
    write(args.output,job);write(args.output.with_suffix('.diagnosis.json'),diagnose(text,args.genre,a))
    write(args.output.with_suffix('.analysis.json'),a)
    print('Prepared job and diagnosis. Use SKILL.md to fill source-grounded claims, candidate rewrites and independent review; then finalize. No generation service was called.')

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('input',type=Path);a.add_argument('--genre',choices=GENRES,default='general');a.add_argument('--output',type=Path,required=True)
    b=sub.add_parser('finalize');b.add_argument('job',type=Path);b.add_argument('--output',type=Path,required=True);b.add_argument('--measurements',type=Path)
    for s in (a,b):s.add_argument('--research',type=Path,default=DEFAULT_RESEARCH);s.add_argument('--models',type=Path)
    args=p.parse_args()
    if args.command=='prepare':prepare(args)
    else:
        result=finalize(read(args.job),Analyzer(args.research,args.models),args.measurements);write(args.output,result)
        text_path=args.output.with_suffix('.txt');text_path.write_text(result['final_text'] or result['rollback_text'])
        print(json.dumps({'status':result['status'],'candidate':result['selected_candidate_id'],'output_text':str(text_path)},ensure_ascii=False))
        return 0 if result['status']=='reviewed_candidate_for_user_test' else 2
if __name__=='__main__':raise SystemExit(main())
