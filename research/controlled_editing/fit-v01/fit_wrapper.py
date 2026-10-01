"""Fail-closed single-fit wrapper. Import and validate never fit or read a corpus.

Only --run with an externally supplied root GO file hash can start an empirical
fit. Do not manufacture an empirical GO for synthetic tests. The functions below
accept synthetic in-memory fixtures for unit tests, with explicit provenance.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, os, re, resource, signal, stat, sys, time
from pathlib import Path
import controller_v03 as C
import labels_v02 as L

ROOT=Path(__file__).resolve().parent
CONDITIONS=C.CONDITIONS
INPUT_FILES=('train_dev.json','labels_a.json','labels_b.json','label_receipts.json','storage_receipt.json')
BLIND_TO=['nominal_target','template','pass','partition','model_scores','other_rater_labels']
LIMIT=32*1024*1024
OUTPUT_RESERVE=1024*1024
MAX_INPUT_FILE=4*1024*1024
PROTOCOL_SHA=None  # never an authority; ROOT_GO must bind the frozen file bytes


def require(ok, why):
    if not ok: raise C.ContractError(why)


def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def file_hash(p): return sha_bytes(safe_bytes(p, MAX_INPUT_FILE))
def exact(obj, fields, why): require(type(obj) is dict and set(obj)==set(fields),why)
def valid_sha(v): return type(v) is str and re.fullmatch(r'[0-9a-f]{64}',v) is not None


def safe_bytes(path, limit):
    p=Path(path)
    require(not p.is_symlink(),'symlink_input_forbidden')
    fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        s=os.fstat(fd); require(stat.S_ISREG(s.st_mode) and s.st_size<=limit,'input_size_or_type_limit')
        with os.fdopen(fd,'rb',closefd=False) as f: b=f.read(limit+1)
        require(len(b)<=limit,'input_size_limit'); return b
    finally: os.close(fd)


def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate_json_key'); out[k]=v
        return out
    def constant(value): raise C.ContractError('nonfinite_json')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)


def write_once(path, obj):
    with Path(path).open('xb') as f:
        f.write(C.canonical(obj)+b'\n'); f.flush(); os.fsync(f.fileno())


def package_hashes_ok():
    raw=safe_bytes(ROOT/'FILE_HASHES.json',MAX_INPUT_FILE); manifest=strict_json(raw)
    exact(manifest,{'schema','files','frozen_dependencies'},'package_manifest_schema')
    require(manifest['schema']=='controlled-fit-package/v1','package_manifest_schema')
    names=set()
    for item in manifest['files']:
        exact(item,{'path','bytes','sha256'},'package_entry_schema')
        name=item['path']; require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]+',name) and name not in names,'package_entry_path')
        names.add(name); content=safe_bytes(ROOT/name,MAX_INPUT_FILE)
        require(len(content)==item['bytes'] and sha_bytes(content)==item['sha256'],'package_file_hash_mismatch:'+name)
    require({'fit_wrapper.py','controller_v03.py','labels_v02.py','protocol.json','PROTOCOL.md','test_fit_wrapper.py'}<=names,'package_files_missing')
    return sha_bytes(raw)


def package_bytes():
    total=0
    # Never leave this authorized output tree or follow a symlink.
    for base,dirs,files in os.walk(ROOT,followlinks=False):
        for name in dirs+files:
            p=Path(base)/name
            require(not p.is_symlink(),'package_symlink_forbidden')
            if p.is_file(): total+=p.stat().st_size
    return total


def read_authorized_inputs(input_dir, expected_go_sha):
    require(valid_sha(expected_go_sha),'explicit_expected_root_GO_hash_required')
    folder=Path(input_dir).resolve(); require(folder!=ROOT,'input_directory_must_be_separate')
    go_raw=safe_bytes(folder/'ROOT_GO.json',65536)
    require(sha_bytes(go_raw)==expected_go_sha,'root_GO_file_hash_mismatch')
    go=strict_json(go_raw)
    exact(go,{'schema','action','actor','run_id','package_manifest_sha256','protocol_sha256','input_sha256','review_approval_sha256','training_scope','issued_at_utc'},'root_GO_schema')
    require(go['schema']=='root-controlled-fit-go/v1' and go['action']=='CONTROLLED_STYLE_TRAIN_GO' and go['actor']=='root','root_GO_action')
    require(type(go['run_id']) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,64}',go['run_id']),'run_id_invalid')
    require(go['package_manifest_sha256']==package_hashes_ok(),'root_GO_package_mismatch')
    require(go['protocol_sha256']==file_hash(ROOT/'protocol.json'),'root_GO_protocol_mismatch')
    require(go['training_scope']=='single_condition_only_fit_train256_dev64_no_test_no_inference','root_GO_scope')
    exact(go['input_sha256'],INPUT_FILES,'root_GO_input_hash_set')
    inputs={}
    for name in INPUT_FILES:
        raw=safe_bytes(folder/name,MAX_INPUT_FILE)
        require(sha_bytes(raw)==go['input_sha256'][name],'input_hash_mismatch:'+name)
        inputs[name]=strict_json(raw)
    require(C.digest(inputs['label_receipts.json'])==go['review_approval_sha256'],'root_GO_review_approval_mismatch')
    return go,inputs


def validate_reviews(data, a, b, receipts):
    exact(receipts,{'schema','dataset_file_sha256','review_files_sha256','raters','review_scope','projection_receipt'},'label_receipts_schema')
    require(receipts['schema']=='dual-blind-label-receipts/v1','label_receipts_schema')
    require(receipts['review_scope']=='all_completed_train_dev_slots_only_test_sealed','label_scope')
    exact(receipts['review_files_sha256'],{'a','b'},'review_hash_schema')
    require(type(receipts['raters']) is list and len(receipts['raters'])==2,'two_raters_required')
    ids=[]
    for i,r in enumerate(receipts['raters']):
        exact(r,{'rater_id','review_context_id','independent_of_authoring','independent_of_fit','blind_to','review_file_sha256'},'rater_receipt_schema')
        require(type(r['rater_id']) is str and bool(r['rater_id']) and type(r['review_context_id']) is str and bool(r['review_context_id']),'rater_identity')
        require(r['independent_of_authoring'] is True and r['independent_of_fit'] is True and r['blind_to']==BLIND_TO,'independent_blind_receipt_required')
        require(r['review_file_sha256']==receipts['review_files_sha256'][('a','b')[i]],'rater_file_hash_binding')
        ids.append((r['rater_id'],r['review_context_id']))
    require(ids[0][0]!=ids[1][0] and ids[0][1]!=ids[1][1],'independent_raters_required')
    lookup=[]
    for i,payload in enumerate((a,b)):
        exact(payload,{'schema','reviews'},'reviews_file_schema')
        require(payload['schema']=='sanitized-blind-reviews/v1' and type(payload['reviews']) is list,'reviews_file_schema')
        table={}
        for r in payload['reviews']:
            require(type(r) is dict and type(r.get('review_id')) is str and r['review_id'] and r['review_id'] not in table,'duplicate_or_invalid_review_id')
            require(r.get('rater_id')==ids[i][0],'rater_id_mismatch');table[r['review_id']]=r
        lookup.append(table)
    completed={r['review_id'] for r in data['slots'] if r['status']=='completed'}
    require(set(lookup[0])==set(lookup[1])==completed,'review_coverage_mismatch')
    projection=receipts['projection_receipt']
    exact(projection,{'schema','actor','original_review_files_sha256','original_review_row_counts','subset_review_files_sha256','selected_review_ids','selected_review_ids_sha256','test_rows_exported'},'projection_receipt_schema')
    require(projection['schema']=='root-train-dev-review-projection/v1' and projection['actor']=='root','root_projection_attestation_required')
    exact(projection['original_review_files_sha256'],{'a','b'},'original_review_hash_schema')
    require(all(valid_sha(v) for v in projection['original_review_files_sha256'].values()),'original_review_source_hash_required')
    require(projection['original_review_row_counts']=={'a':384,'b':384},'original_review_row_counts')
    require(projection['subset_review_files_sha256']==receipts['review_files_sha256'],'projection_subset_hash_mismatch')
    require(projection['selected_review_ids']==sorted(completed) and projection['selected_review_ids_sha256']==C.digest(sorted(completed)),'projection_selected_ids_mismatch')
    require(type(projection['test_rows_exported']) is int and projection['test_rows_exported']==0,'projection_test_rows_forbidden')
    # Original file hashes are coordinator attestations only. No original path
    # is admitted or opened; its 384 records include sealed TEST judgments.
    return lookup


def validate_data(data,a,b,receipts,*,synthetic=False):
    exact(data,{'schema','provenance','source_draft_manifest_sha256','family_split_manifest_sha256','slots'},'dataset_schema')
    require(data['schema']=='sanitized-controlled-train-dev/v1' and data['provenance']==('synthetic_fixture' if synthetic else 'assistant_authored_controlled'),'controlled_provenance_required')
    require(valid_sha(data['source_draft_manifest_sha256']) and valid_sha(data['family_split_manifest_sha256']),'source_manifest_binding_required')
    require(type(data['slots']) is list and len(data['slots'])==320,'all_320_original_train_dev_slots_required')
    slot_fields={'id','family','partition','genre','status','text','text_sha256','mainpoint_exact','fact_ids','review_id','realized_condition','exclusion_reason'}
    seen=set(); families={}; review_ids=set(); partitions={'train':[],'dev':[]}
    for r in data['slots']:
        exact(r,slot_fields,'slot_schema_no_nominal_target_or_test')
        require(type(r['id']) is str and r['id'] and r['id'] not in seen,'duplicate_or_invalid_slot_id');seen.add(r['id'])
        require(r['partition'] in partitions,'test_or_unknown_partition_forbidden')
        require(type(r['family']) is str and r['family'] and r['genre'] in C.GENRES,'family_or_genre_invalid')
        group=families.setdefault(r['family'],{'partition':r['partition'],'genre':r['genre'],'slots':0})
        require(group['partition']==r['partition'] and group['genre']==r['genre'],'family_leakage_or_genre_change');group['slots']+=1
        require(r['status'] in ('completed','generation_failed','technical_failed','unfinished'),'slot_status')
        require(type(r['exclusion_reason']) in (str,type(None)),'exclusion_reason_invalid')
        require(r['realized_condition'] is None or r['realized_condition'] in CONDITIONS,'invalid_realized_condition')
        if r['status']=='completed':
            require(type(r['text']) is str and r['text'] and len(r['text'].encode())<=16384,'completed_text_invalid')
            require(r['text_sha256']==C.text_hash(r['text']),'text_hash_mismatch')
            require(type(r['mainpoint_exact']) is str and r['mainpoint_exact'],'mainpoint_required')
            require(type(r['fact_ids']) is list and r['fact_ids']==['P1','P2','P3','P4','P5','P6'],'six_fact_ids_required')
            require(type(r['review_id']) is str and r['review_id'] and r['review_id'] not in review_ids,'duplicate_or_invalid_review_id');review_ids.add(r['review_id'])
        else:
            require(all(r[k] is None for k in ('text','text_sha256','mainpoint_exact','review_id','realized_condition')) and r['fact_ids']==[] and bool(r['exclusion_reason']),'failed_slot_must_remain_in_denominator')
        partitions[r['partition']].append(r)
    require(len(partitions['train'])==256 and len(partitions['dev'])==64,'partition_slot_counts')
    require(all(g['slots']==8 for g in families.values()),'eight_slots_per_original_family')
    for partition,n in [('train',32),('dev',8)]:
        groups=[g for g in families.values() if g['partition']==partition]
        require(len(groups)==n,'family_counts')
        require(all(sum(g['genre']==genre for g in groups)==n//4 for genre in C.GENRES),'family_genre_balance')
    lookups=validate_reviews(data,a,b,receipts)
    eligible={'train':[],'dev':[]}; counts={p:{c:set() for c in CONDITIONS} for p in partitions}; exclusions={}
    for row in data['slots']:
        if row['status']!='completed': exclusions[row['status']]=exclusions.get(row['status'],0)+1;continue
        props=L.observed_properties(row['text'],row['mainpoint_exact'])
        outcome=L.adjudicate_pair(lookups[0][row['review_id']],lookups[1][row['review_id']],props,row['fact_ids'])
        realized=outcome['realized_condition']
        require(realized==row['realized_condition'],'exported_actual_label_disagrees_with_dual_review')
        if realized is None:
            require(bool(row['exclusion_reason']),'excluded_label_reason_required');exclusions['dual_review_or_support_excluded']=exclusions.get('dual_review_or_support_excluded',0)+1;continue
        require(row['exclusion_reason'] is None,'eligible_exclusion_reason_mismatch')
        p=row['partition']; counts[p][realized].add(row['family'])
        eligible[p].append({'id':row['id'],'family':row['family'],'partition':p,'condition':realized,'meaning_verified':True,'realized_condition_verified':True,'features':C.features(row['text'],props['mainpoint_span']),'text':row['text'],'mainpoint_span':props['mainpoint_span']})
    support={p:{c:len(fs) for c,fs in cs.items()} for p,cs in counts.items()}
    for p,minimum in [('train',16),('dev',4)]:
        require(all(n>=minimum for n in support[p].values()),'insufficient_'+p+'_family_support')
    return {'eligible':eligible,'all_slots':partitions,'family_support':support,'exclusions':exclusions}


def probabilities(model,features):
    x=C.scaled(features,model['transform'])
    return C.softmax([math.fsum(wj*xj for wj,xj in zip(w,x)) for w in model['condition_weights']])


def family_metrics(model, rows, all_slots):
    """CE/accuracy condition on eligible rows; coverage uses all original slots."""
    family={r['family']:{'all':0,'eligible':0,'ce':0.,'correct':0.,'rule_ce':0.,'rule_correct':0.} for r in all_slots}
    for r in all_slots:family[r['family']]['all']+=1
    for r in rows:
        f=family[r['family']];p=probabilities(model,r['features']);target=CONDITIONS.index(r['condition'])
        f['eligible']+=1;f['ce']-=math.log(max(p[target],1e-300));f['correct']+=max(range(4),key=lambda j:p[j])==target
        # Labels were defined by exactly these thresholds. This is not an
        # independent style or quality predictor, and not a semantic test.
        a,b=r['mainpoint_span'];rule_condition=L.observed_properties(r['text'],r['text'][a:b])['mechanical_condition']
        require(rule_condition in CONDITIONS,'rule_outside_support_on_eligible_row')
        rule_index=CONDITIONS.index(rule_condition);rule=[1e-15]*4;rule[rule_index]=1.;denom=math.fsum(rule);f['rule_ce']-=math.log(rule[target]/denom);f['rule_correct']+=(rule_index==target)
    usable=[f for f in family.values() if f['eligible']]
    mean=lambda field:math.fsum(f[field]/f['eligible'] for f in usable)/len(usable) if usable else None
    return {'family_macro_cross_entropy_on_eligible':mean('ce'),'family_macro_accuracy_on_eligible':mean('correct'),'family_macro_coverage_over_all_original_slots':math.fsum(f['eligible']/f['all'] for f in family.values())/len(family),'eligible_families':len(usable),'all_families':len(family),'eligible_rows':len(rows),'all_slots':len(all_slots),'by_family':family,'exact_threshold_rule':{'interpretation':'tautological_class_definition_comparator_not_human_style','family_macro_cross_entropy_on_eligible':mean('rule_ce'),'family_macro_accuracy_on_eligible':mean('rule_correct'),'coverage_is_shared_dual_review_filter':True}}


def gradient_replay(rows, model):
    """Independent recurrence verifies the one fitted checkpoint; no selection."""
    require(model['transform']==C.scale_fit([r['features'] for r in rows]),'checkpoint_scaler_not_train_only')
    transformed=[C.scaled(r['features'],model['transform']) for r in rows]
    families={r['family'] for r in rows}; counts={f:sum(r['family']==f for r in rows) for f in families}
    w=[[0.]*13 for _ in CONDITIONS];first_norm=None
    for epoch in range(150):
        grad=[[0.]*13 for _ in CONDITIONS]
        for row,x in zip(rows,transformed):
            p=C.softmax([sum(v*q for v,q in zip(wc,x)) for wc in w]);y=CONDITIONS.index(row['condition']);mass=1/(len(families)*counts[row['family']])
            for k in range(4):
                for j in range(13):grad[k][j]+=mass*(p[k]-(k==y))*x[j]
        if epoch==0:first_norm=math.sqrt(sum(v*v for row in grad for v in row))
        w=[[v-.05*g for v,g in zip(wc,gc)] for wc,gc in zip(w,grad)]
    error=max(abs(a-b) for wa,wb in zip(w,model['condition_weights']) for a,b in zip(wa,wb))
    require(first_norm is not None and first_norm>0,'zero_initial_gradient')
    require(error<=1e-12,'checkpoint_gradient_replay_mismatch')
    require(any(v!=0 for wc in model['condition_weights'] for v in wc),'untrained_zero_weights')
    require(all(v==0. for uc in model['preference_weights'] for v in uc),'preference_weights_must_remain_zero')
    require(model['training']['epochs']==150 and model['training']['lr']==.05 and model['training']['preference_pairs']==0,'fixed_fit_mismatch')
    return {'zero_initialized_recurrence_replayed':True,'first_gradient_l2':first_norm,'max_abs_weight_replay_error':error,'preference_pairs':[],'preference_weights_exact_zero':True,'alternate_models_selected':0}


def verify_storage(receipt,go):
    exact(receipt,{'schema','actor','measured_at_utc','excluded_root','external_controlled_bytes','controlled_byte_cap','exclusive_budget_reservation','reserved_output_bytes','no_other_controlled_writes_until_release'},'storage_receipt_schema')
    require(receipt['schema']=='controlled-artifact-budget-receipt/v1' and receipt['actor']=='root','storage_receipt_actor')
    require(receipt['excluded_root']==str(ROOT) and receipt['controlled_byte_cap']==LIMIT and receipt['reserved_output_bytes']==OUTPUT_RESERVE,'storage_budget_scope')
    require(receipt['exclusive_budget_reservation'] is True and receipt['no_other_controlled_writes_until_release'] is True,'exclusive_storage_reservation_required')
    measured=dt.datetime.fromisoformat(receipt['measured_at_utc'].replace('Z','+00:00'))
    require(measured.tzinfo is not None and 0<=(dt.datetime.now(dt.timezone.utc)-measured).total_seconds()<=600,'storage_receipt_stale')
    used=receipt['external_controlled_bytes'];require(type(used) is int and used>=0,'storage_measurement_invalid')
    require(used+package_bytes()+OUTPUT_RESERVE<=LIMIT,'controlled_artifact_cap_exceeded')
    return used


def apply_limits():
    require(hasattr(os,'sched_getaffinity') and hasattr(resource,'RLIMIT_AS'),'resource_enforcement_unavailable')
    cpus=sorted(os.sched_getaffinity(0))[:2]; require(cpus,'no_cpu_available');os.sched_setaffinity(0,cpus)
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    def expired(signum,frame): raise C.ContractError('fit_and_replay_wall_budget_exceeded')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,60)
    return {'cpu_affinity':cpus,'address_space_bytes':512*1024*1024,'wall_seconds':60}


def run(input_dir, expected_go_sha):
    go,inputs=read_authorized_inputs(input_dir,expected_go_sha)
    receipts=inputs['label_receipts.json']
    require(receipts.get('dataset_file_sha256')==go['input_sha256']['train_dev.json'],'review_dataset_hash_mismatch')
    require(receipts.get('review_files_sha256')=={'a':go['input_sha256']['labels_a.json'],'b':go['input_sha256']['labels_b.json']},'review_payload_hash_mismatch')
    verified=validate_data(inputs['train_dev.json'],inputs['labels_a.json'],inputs['labels_b.json'],receipts)
    external_bytes=verify_storage(inputs['storage_receipt.json'],go)
    control=ROOT/'run_state';control.mkdir(exist_ok=True)
    # This marker is never removed, even on failure. It prevents a second fit
    # with a different run id or GO. A failure requires a new version + root GO.
    marker={'schema':'single-fit-start/v1','root_GO_file_sha256':expected_go_sha,'run_id':go['run_id'],'started_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    write_once(control/'EMPIRICAL_START.json',marker)
    output=ROOT/'runs'/go['run_id'];output.parent.mkdir(exist_ok=True);output.mkdir(exist_ok=False)
    try:
        resources=apply_limits();started=time.monotonic();rows=verified['eligible']['train']
        authorization={'action':'CONTROLLED_STYLE_TRAIN_GO','actor':'root','dataset_sha256':C.digest(rows),'labels_sha256':C.digest([{'id':r['id'],'condition':r['condition'],'meaning_verified':r['meaning_verified'],'realized_condition_verified':r['realized_condition_verified']} for r in rows]),'independent_label_review':True,'protocol_sha256':go['protocol_sha256']}
        model=C.fit(rows,[],provenance='assistant_authored_controlled',authorization=authorization,epochs=150,lr=.05)
        model['training']['wrapper_root_GO_sha256']=expected_go_sha
        model['training']['wrapper_package_manifest_sha256']=go['package_manifest_sha256']
        replay=gradient_replay(rows,model)
        checkpoint=output/'condition-only.weights.json';checkpoint_sha=C.save_checkpoint(model,checkpoint)
        loaded=C.load_checkpoint(checkpoint,checkpoint_sha);require(loaded==model,'checkpoint_roundtrip_mismatch')
        metrics={p:family_metrics(loaded,verified['eligible'][p],verified['all_slots'][p]) for p in ('train','dev')}
        elapsed=time.monotonic()-started;require(elapsed<=60,'fit_and_replay_wall_budget_exceeded')
        result={'schema':'controlled-condition-fit-receipt/v1','status':'completed_verified_condition_only_fit','root_GO_sha256':expected_go_sha,'package_manifest_sha256':go['package_manifest_sha256'],'input_sha256':go['input_sha256'],'checkpoint_file_sha256':checkpoint_sha,'checkpoint_model_sha256':C.digest(model),'fit_invocations':1,'epochs':150,'learning_rate':.05,'resources':resources,'fit_replay_and_diagnostics_seconds':elapsed,'gradient_replay':replay,'family_support':verified['family_support'],'exclusions':verified['exclusions'],'metrics':metrics,'semantic_guarantee':False,'test_opened':False,'inference_candidates_generated':0,'generic_stage_complete':False,'counts_towards_1280_natural_works':False}
        write_once(output/'FIT_RECEIPT.json',result)
        require(external_bytes+package_bytes()<=LIMIT,'controlled_artifact_cap_exceeded')
        require(sum(p.stat().st_size for p in output.iterdir())<=OUTPUT_RESERVE,'output_reservation_exceeded')
        write_once(control/'EMPIRICAL_COMPLETE.json',{'run_id':go['run_id'],'receipt_sha256':file_hash(output/'FIT_RECEIPT.json'),'checkpoint_sha256':checkpoint_sha})
        print(json.dumps({'status':result['status'],'output':str(output),'test_opened':False}))
    except BaseException as exc:
        # Interrupted/partial checkpoints are not deployable without COMPLETE.
        try:write_once(output/'FAILED.json',{'status':'failed_closed_no_retry','error_type':type(exc).__name__,'error':str(exc),'root_GO_sha256':expected_go_sha})
        except Exception:pass
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');parser.add_argument('--input-dir');parser.add_argument('--expected-go-sha256');args=parser.parse_args()
    require(args.run and args.input_dir and args.expected_go_sha256,'empirical_execution_requires_explicit_run_inputs_and_root_GO_hash')
    run(args.input_dir,args.expected_go_sha256)

if __name__=='__main__':main()
