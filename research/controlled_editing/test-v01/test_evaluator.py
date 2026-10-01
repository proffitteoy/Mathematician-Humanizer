"""One-shot controlled structural TEST evaluator. Import never opens data.
Preparation and synthetic tests are not empirical evaluation authority.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, os, re, resource, signal, stat, sys, time
from pathlib import Path
import inference_core as C
import labels_v02 as L

ROOT=Path(__file__).resolve().parent
CANONICAL_ROOT=Path('/workspace/shared/style-controlled-test-v01')
# This literal is the single global TEST gate for this controlled corpus, even
# for future evaluator versions. Never remove, relocate, replace or reset it.
GLOBAL_TEST_START=CANONICAL_ROOT/'run_state'/'TEST_START.json'
FIT_ROOT=Path('/workspace/shared/style-controlled-fit-v01')
CHECKPOINT=FIT_ROOT/'runs/controlled_v1_20261001/condition-only.weights.json'
FIT_RECEIPT=FIT_ROOT/'runs/controlled_v1_20261001/FIT_RECEIPT.json'
FIT_COMPLETE=FIT_ROOT/'run_state/EMPIRICAL_COMPLETE.json'
CHECKPOINT_SHA='c2d6d4352c0209d78f221ede226301fa835fa80c679a77b6f09bd9544aabc83b'
FIT_RECEIPT_SHA='96283df19251dabc0b4e416d8745e4dd80db227be35b3982489d8f9e3eb5887b'
FIT_COMPLETE_SHA='5e3069433e398b1dc07026d2bc9b6409d18b9e0cf377bdf40ea71286c701279e'
CONDITIONS=C.CONDITIONS
INPUT_FILES=('test.json','labels_a.json','labels_b.json','label_receipts.json','storage_receipt.json')
CODE_FILES=('test_evaluator.py','inference_core.py','labels_v02.py')
BLIND_TO=['nominal_target','template','pass','partition','model_scores','other_rater_labels']
LIMIT=32*1024*1024
OUTPUT_RESERVE=1024*1024
MAX_INPUT_FILE=4*1024*1024

def require(ok, why):
    if not ok: raise C.ContractError(why)


def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def file_hash(p): return sha_bytes(safe_bytes(p, MAX_INPUT_FILE))
def exact(obj, fields, why): require(type(obj) is dict and set(obj)==set(fields),why)
def valid_sha(v): return type(v) is str and re.fullmatch(r'[0-9a-f]{64}',v) is not None


def safe_bytes(path, limit):
    p=Path(path).absolute()
    require(all(not part.is_symlink() for part in [p,*p.parents]),'symlink_input_forbidden')
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


def fsync_directory(path):
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0))
    try:os.fsync(fd)
    finally:os.close(fd)


def durable_mkdir(path,*,exist_ok=False):
    path=Path(path)
    require(all(not p.is_symlink() for p in [path,*path.parents]),'directory_symlink_forbidden')
    path.mkdir(exist_ok=exist_ok)
    require(path.is_dir(),'directory_required')
    # Both the new directory inode and its entry in the parent must survive a
    # crash before any child file can be treated as durably frozen.
    fsync_directory(path)
    fsync_directory(path.parent)


def write_once(path, obj):
    raw=C.canonical(obj)+b'\n'
    require(len(raw)<=OUTPUT_RESERVE,'single_output_size_limit')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o444)
    try:
        with os.fdopen(fd,'wb',closefd=False) as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
    finally:os.close(fd)
    # Persist the directory entry as well as the contents before proceeding.
    dfd=os.open(Path(path).parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
    try:os.fsync(dfd)
    finally:os.close(dfd)
    return sha_bytes(raw)


def validate_reviews(data, a, b, receipts):
    exact(receipts,{'schema','dataset_file_sha256','review_files_sha256','raters','review_scope','projection_receipt'},'label_receipts_schema')
    require(receipts['schema']=='dual-blind-label-receipts/v1','label_receipts_schema')
    require(receipts['review_scope']=='all_completed_test_slots_only_train_dev_excluded','label_scope')
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
    exact(projection,{'schema','actor','original_review_files_sha256','original_review_row_counts','subset_review_files_sha256','selected_review_ids','selected_review_ids_sha256','train_dev_rows_exported'},'projection_receipt_schema')
    require(projection['schema']=='root-test-review-projection/v1' and projection['actor']=='root','root_projection_attestation_required')
    exact(projection['original_review_files_sha256'],{'a','b'},'original_review_hash_schema')
    require(all(valid_sha(v) for v in projection['original_review_files_sha256'].values()),'original_review_source_hash_required')
    exact(projection['original_review_row_counts'],{'a','b'},'original_review_row_counts_schema')
    require(all(type(n) is int and n==384 for n in projection['original_review_row_counts'].values()),'original_review_row_counts')
    require(projection['subset_review_files_sha256']==receipts['review_files_sha256'],'projection_subset_hash_mismatch')
    require(projection['selected_review_ids']==sorted(completed) and projection['selected_review_ids_sha256']==C.digest(sorted(completed)),'projection_selected_ids_mismatch')
    require(type(projection['train_dev_rows_exported']) is int and projection['train_dev_rows_exported']==0,'projection_train_dev_rows_forbidden')
    # Original file hashes are coordinator attestations only. No original path
    # is admitted or opened; its 384 records include TRAIN and DEV judgments outside this export.
    return lookup


def validate_structure(data,*,synthetic=False):
    exact(data,{'schema','provenance','source_draft_manifest_sha256','family_split_manifest_sha256','slots'},'dataset_schema')
    require(data['schema']=='sanitized-controlled-test/v1' and data['provenance']==('synthetic_fixture' if synthetic else 'assistant_authored_controlled'),'controlled_provenance_required')
    require(valid_sha(data['source_draft_manifest_sha256']) and valid_sha(data['family_split_manifest_sha256']),'source_manifest_binding_required')
    require(type(data['slots']) is list and len(data['slots'])==64,'all_64_original_test_slots_required')
    slot_fields={'id','family','partition','genre','status','text','text_sha256','mainpoint_exact','fact_ids','review_id'}
    seen=set(); families={}; review_ids=set(); partitions={'test':[]}
    for r in data['slots']:
        exact(r,slot_fields,'slot_schema_no_nominal_target_or_train_dev')
        require(type(r['id']) is str and r['id'] and r['id'] not in seen,'duplicate_or_invalid_slot_id');seen.add(r['id'])
        require(r['partition'] in partitions,'train_dev_or_unknown_partition_forbidden')
        require(type(r['family']) is str and r['family'] and r['genre'] in C.GENRES,'family_or_genre_invalid')
        group=families.setdefault(r['family'],{'partition':r['partition'],'genre':r['genre'],'slots':0})
        require(group['partition']==r['partition'] and group['genre']==r['genre'],'family_leakage_or_genre_change');group['slots']+=1
        require(r['status'] in ('completed','generation_failed','technical_failed','unfinished'),'slot_status')
        if r['status']=='completed':
            require(type(r['text']) is str and r['text'] and len(r['text'].encode())<=16384,'completed_text_invalid')
            require(r['text_sha256']==C.text_hash(r['text']),'text_hash_mismatch')
            require(type(r['mainpoint_exact']) is str and r['mainpoint_exact'],'mainpoint_required')
            require(type(r['fact_ids']) is list and r['fact_ids']==['P1','P2','P3','P4','P5','P6'],'six_fact_ids_required')
            require(type(r['review_id']) is str and r['review_id'] and r['review_id'] not in review_ids,'duplicate_or_invalid_review_id');review_ids.add(r['review_id'])
        else:
            require(all(r[k] is None for k in ('text','text_sha256','mainpoint_exact','review_id')) and r['fact_ids']==[],'failed_slot_must_remain_in_denominator')
        partitions[r['partition']].append(r)
    require(len(partitions['test'])==64,'partition_slot_counts')
    require(all(g['slots']==8 for g in families.values()),'eight_slots_per_original_family')
    for partition,n in [('test',8)]:
        groups=[g for g in families.values() if g['partition']==partition]
        require(len(groups)==n,'family_counts')
        require(all(sum(g['genre']==genre for g in groups)==n//4 for genre in C.GENRES),'family_genre_balance')
    return partitions


def validate_data(data,a,b,receipts,*,synthetic=False):
    partitions=validate_structure(data,synthetic=synthetic)
    lookups=validate_reviews(data,a,b,receipts)
    eligible={'test':[]}; counts={p:{c:set() for c in CONDITIONS} for p in partitions}; exclusions={}
    for row in data['slots']:
        if row['status']!='completed': exclusions[row['status']]=exclusions.get(row['status'],0)+1;continue
        props=L.observed_properties(row['text'],row['mainpoint_exact'])
        outcome=L.adjudicate_pair(lookups[0][row['review_id']],lookups[1][row['review_id']],props,row['fact_ids'])
        realized=outcome['realized_condition']
        if realized is None:
            exclusions['dual_review_or_support_excluded']=exclusions.get('dual_review_or_support_excluded',0)+1;continue
        p=row['partition']; counts[p][realized].add(row['family'])
        eligible[p].append({'id':row['id'],'family':row['family'],'partition':p,'condition':realized,'meaning_verified':True,'realized_condition_verified':True,'features':C.features(row['text'],props['mainpoint_span']),'text':row['text'],'mainpoint_span':props['mainpoint_span']})
    support={p:{c:len(fs) for c,fs in cs.items()} for p,cs in counts.items()}
    # No minimum TEST support gate: all 64 original slots remain reportable.
    return {'eligible':eligible,'all_slots':partitions,'family_support':support,'exclusions':exclusions}


def probabilities(model,features):
    x=C.scaled(features,model['transform'])
    p=C.softmax([math.fsum(wj*xj for wj,xj in zip(w,x)) for w in model['condition_weights']])
    require(C.finite(p) and all(0<=v<=1 for v in p) and abs(math.fsum(p)-1)<1e-12,'invalid_probabilities')
    return p


def predict_all(model,data,*,synthetic=False):
    """No reviews or realized-label fields are accepted by this function."""
    validate_structure(data,synthetic=synthetic)
    result=[]
    for row in data['slots']:
        item={'id':row['id'],'family':row['family'],'partition':'test','text_sha256':row['text_sha256'],'generation_status':row['status'],'prediction_status':None,'probabilities':None,'predicted_condition':None}
        if row['status']!='completed':item['prediction_status']='unproduced_original_slot'
        elif row['text'].count(row['mainpoint_exact'])!=1:item['prediction_status']='mainpoint_span_unavailable'
        else:
            a=row['text'].index(row['mainpoint_exact']);x=C.features(row['text'],[a,a+len(row['mainpoint_exact'])]);p=probabilities(model,x)
            item.update(prediction_status='predicted',probabilities=p,predicted_condition=CONDITIONS[max(range(4),key=lambda j:p[j])])
        result.append(item)
    return {'schema':'frozen-controlled-test-predictions/v1','provenance':'synthetic_fixture' if synthetic else 'assistant_authored_controlled','conditions':list(CONDITIONS),'all_original_slots':64,'predictions':result,'labels_opened_before_freeze':False}


def family_metrics(predictions,verified):
    """Score only the persisted prediction object, never recompute model scores."""
    all_slots=verified['all_slots']['test'];rows=verified['eligible']['test']
    lookup={p['id']:p for p in predictions['predictions']}
    require(len(lookup)==64 and set(lookup)=={r['id'] for r in all_slots},'prediction_slot_coverage')
    family={r['family']:{'all':0,'eligible':0,'ce':0.,'correct':0.,'rule_ce':0.,'rule_correct':0.} for r in all_slots}
    for r in all_slots:family[r['family']]['all']+=1
    for r in rows:
        saved=lookup[r['id']];p=saved['probabilities']
        require(saved['family']==r['family'] and saved['prediction_status']=='predicted' and C.finite(p) and len(p)==4,'eligible_prediction_missing')
        target=CONDITIONS.index(r['condition']);f=family[r['family']]
        f['eligible']+=1;f['ce']-=math.log(max(p[target],1e-300));f['correct']+=saved['predicted_condition']==r['condition']
        a,b=r['mainpoint_span'];rule_condition=L.observed_properties(r['text'],r['text'][a:b])['mechanical_condition']
        require(rule_condition in CONDITIONS,'rule_outside_support_on_eligible_row')
        rule_index=CONDITIONS.index(rule_condition);rule=[1e-15]*4;rule[rule_index]=1.;denom=math.fsum(rule)
        f['rule_ce']-=math.log(rule[target]/denom);f['rule_correct']+=rule_index==target
    usable=[f for f in family.values() if f['eligible']]
    mean=lambda field:math.fsum(f[field]/f['eligible'] for f in usable)/len(usable) if usable else None
    return {'family_macro_cross_entropy_on_eligible':mean('ce'),'family_macro_accuracy_on_eligible':mean('correct'),'family_macro_coverage_over_all_original_slots':math.fsum(f['eligible']/f['all'] for f in family.values())/len(family),'eligible_families':len(usable),'all_families':len(family),'eligible_rows':len(rows),'all_slots':len(all_slots),'by_family':family,'exact_threshold_rule':{'interpretation':'tautological_class_definition_comparator_not_human_style','family_macro_cross_entropy_on_eligible':mean('rule_ce'),'family_macro_accuracy_on_eligible':mean('rule_correct'),'coverage_is_shared_dual_review_filter':True}}


def write_run_output(path,obj):
    total=0
    for folder in (ROOT/'run_state',ROOT/'runs'):
        if not folder.exists():continue
        require(not folder.is_symlink(),'output_tree_symlink_forbidden')
        for base,dirs,files in os.walk(folder,followlinks=False):
            for name in dirs+files:
                p=Path(base)/name;require(not p.is_symlink(),'output_tree_symlink_forbidden')
                if p.is_file():total+=p.stat().st_size
    reserve=0 if Path(path).name=='FAILED.json' else 4096
    require(total+len(C.canonical(obj))+1+reserve<=OUTPUT_RESERVE,'cumulative_output_reservation_exceeded')
    return write_once(path,obj)


def package_bytes():
    total=0
    for base,dirs,files in os.walk(ROOT,followlinks=False):
        for name in dirs+files:
            p=Path(base)/name;require(not p.is_symlink(),'package_symlink_forbidden')
            if p.is_file():total+=p.stat().st_size
    return total


def package_hashes_ok():
    raw=safe_bytes(ROOT/'FILE_HASHES.json',MAX_INPUT_FILE);m=strict_json(raw)
    exact(m,{'schema','files','frozen_dependencies'},'package_manifest_schema')
    require(m['schema']=='controlled-test-package/v1' and type(m['files']) is list,'package_manifest_schema')
    names=set()
    for item in m['files']:
        exact(item,{'path','bytes','sha256'},'package_entry_schema');name=item['path']
        require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]+',name) and name not in names,'package_entry_path');names.add(name)
        raw_file=safe_bytes(ROOT/name,MAX_INPUT_FILE)
        require(type(item['bytes']) is int and len(raw_file)==item['bytes'] and sha_bytes(raw_file)==item['sha256'],'package_file_hash_mismatch:'+name)
    require(set(CODE_FILES)|{'protocol.json','PROTOCOL.md','test_test_evaluator.py'}<=names,'package_files_missing')
    return sha_bytes(raw)


def timestamp_age(value):
    require(type(value) is str,'timestamp_type')
    parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    require(parsed.tzinfo is not None,'timestamp_timezone_required')
    return (dt.datetime.now(dt.timezone.utc)-parsed).total_seconds()


def verify_storage(receipt):
    exact(receipt,{'schema','actor','measured_at_utc','excluded_root','external_controlled_bytes','controlled_byte_cap','exclusive_budget_reservation','reserved_output_bytes','no_other_controlled_writes_until_release'},'storage_receipt_schema')
    require(receipt['schema']=='controlled-artifact-budget-receipt/v1' and receipt['actor']=='root','storage_receipt_actor')
    require(receipt['excluded_root']==str(ROOT) and type(receipt['controlled_byte_cap']) is int and receipt['controlled_byte_cap']==LIMIT and type(receipt['reserved_output_bytes']) is int and receipt['reserved_output_bytes']==OUTPUT_RESERVE,'storage_budget_scope')
    require(receipt['exclusive_budget_reservation'] is True and receipt['no_other_controlled_writes_until_release'] is True,'exclusive_storage_reservation_required')
    require(0<=timestamp_age(receipt['measured_at_utc'])<=600,'storage_receipt_stale')
    used=receipt['external_controlled_bytes'];require(type(used) is int and used>=0,'storage_measurement_invalid')
    require(used+package_bytes()+OUTPUT_RESERVE<=LIMIT,'controlled_artifact_cap_exceeded')
    return used


def authorize_go(input_dir,expected_go_sha):
    # A refused second invocation opens no input, even if it has a new GO/run id.
    require(ROOT==CANONICAL_ROOT,'evaluator_relocation_forbidden')
    require(not GLOBAL_TEST_START.exists() and not GLOBAL_TEST_START.is_symlink(),'global_TEST_already_started_no_rerun')
    require(valid_sha(expected_go_sha),'explicit_expected_root_GO_hash_required')
    folder=Path(input_dir).absolute()
    require(all(not p.is_symlink() for p in [folder,*folder.parents]),'symlink_input_directory_forbidden')
    require(folder==folder.resolve(),'noncanonical_input_directory_forbidden')
    require(folder.is_dir() and folder!=ROOT and ROOT not in folder.parents and FIT_ROOT!=folder and FIT_ROOT not in folder.parents,'input_directory_must_be_separate')
    require(set(p.name for p in folder.iterdir())==set(INPUT_FILES)|{'ROOT_GO.json'},'input_directory_exact_files_required')
    raw=safe_bytes(folder/'ROOT_GO.json',65536);require(sha_bytes(raw)==expected_go_sha,'root_GO_file_hash_mismatch');go=strict_json(raw)
    exact(go,{'schema','action','actor','run_id','package_manifest_sha256','protocol_sha256','code_sha256','input_sha256','review_approval_sha256','checkpoint_sha256','fit_receipt_sha256','fit_complete_sha256','global_test_start_path','test_scope','issued_at_utc'},'root_GO_schema')
    require(go['schema']=='root-controlled-test-go/v1' and go['action']=='CONTROLLED_STRUCTURAL_TEST_GO' and go['actor']=='root','root_GO_action')
    require(type(go['run_id']) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,64}',go['run_id']),'run_id_invalid')
    require(0<=timestamp_age(go['issued_at_utc'])<=600,'root_GO_stale')
    require(go['package_manifest_sha256']==package_hashes_ok(),'root_GO_package_mismatch')
    require(go['protocol_sha256']==file_hash(ROOT/'protocol.json'),'root_GO_protocol_mismatch')
    exact(go['code_sha256'],CODE_FILES,'root_GO_code_hash_set')
    require(all(go['code_sha256'][n]==file_hash(ROOT/n) for n in CODE_FILES),'root_GO_code_mismatch')
    exact(go['input_sha256'],INPUT_FILES,'root_GO_input_hash_set')
    require(all(valid_sha(x) for x in go['input_sha256'].values()) and valid_sha(go['review_approval_sha256']),'root_GO_invalid_input_hash')
    require(go['checkpoint_sha256']==CHECKPOINT_SHA and go['fit_receipt_sha256']==FIT_RECEIPT_SHA and go['fit_complete_sha256']==FIT_COMPLETE_SHA,'frozen_fit_binding_mismatch')
    require(go['global_test_start_path']==str(GLOBAL_TEST_START),'global_TEST_marker_path_mismatch')
    require(go['test_scope']=='one_time_frozen_condition_checkpoint_test64_eight_families_no_fit_no_tuning_no_inference','root_GO_scope')
    storage=read_bound(folder,'storage_receipt.json',go)
    return folder,go,verify_storage(storage)


def read_bound(folder,name,go):
    require(name in INPUT_FILES,'unapproved_input_name')
    raw=safe_bytes(folder/name,MAX_INPUT_FILE);require(sha_bytes(raw)==go['input_sha256'][name],'input_hash_mismatch:'+name)
    return strict_json(raw)


def validate_model(m,*,synthetic=False):
    require(m.get('schema')==C.VERSION and m.get('feature_schema_sha256')==C.SCHEMA_SHA and m.get('feature_names')==list(C.FEATURES) and m.get('conditions')==list(CONDITIONS),'checkpoint_schema_mismatch')
    t=m['training'];require(t['status']=='completed_actual_gradient_fit' and t['training_only'] is True and t['provenance']==('synthetic_fixture' if synthetic else 'assistant_authored_controlled'),'trained_checkpoint_required')
    require(type(t['epochs']) is int and t['epochs']==150 and t['lr']==.05 and type(t['preference_pairs']) is int and t['preference_pairs']==0,'fixed_fit_mismatch')
    require(all(type(m[k]) is list and len(m[k])==4 and all(type(v) is list and len(v)==13 and C.finite(v) for v in m[k]) for k in ('condition_weights','preference_weights')),'checkpoint_tensor_invalid')
    require(all(v==0 for row in m['preference_weights'] for v in row),'preference_weights_must_remain_zero')
    tr=m['transform'];require(tr['fit_partition']=='train' and all(len(tr[k])==12 for k in ('center','scale','constant')) and C.finite(tr['center']+tr['scale']) and all(x>0 for x in tr['scale']) and all(type(x) is bool for x in tr['constant']),'checkpoint_transform_invalid')
    return m


def load_frozen_model():
    # These are the only approved prior-stage artifact reads. No train/dev data.
    raw=safe_bytes(CHECKPOINT,OUTPUT_RESERVE);require(sha_bytes(raw)==CHECKPOINT_SHA,'checkpoint_file_hash_mismatch');payload=strict_json(raw)
    exact(payload,{'model','model_sha256'},'checkpoint_payload_schema');m=payload['model'];require(payload['model_sha256']==C.digest(m),'checkpoint_model_hash_mismatch')
    raw=safe_bytes(FIT_RECEIPT,OUTPUT_RESERVE);require(sha_bytes(raw)==FIT_RECEIPT_SHA,'fit_receipt_hash_mismatch');fit=strict_json(raw)
    raw=safe_bytes(FIT_COMPLETE,65536);require(sha_bytes(raw)==FIT_COMPLETE_SHA,'fit_completion_hash_mismatch');complete=strict_json(raw)
    require(complete=={'run_id':'controlled_v1_20261001','receipt_sha256':FIT_RECEIPT_SHA,'checkpoint_sha256':CHECKPOINT_SHA},'completed_fit_required')
    require(fit['schema']=='controlled-condition-fit-receipt/v1' and fit['status']=='completed_verified_condition_only_fit' and fit['test_opened'] is False and fit['fit_invocations']==1 and fit['epochs']==150 and fit['learning_rate']==.05 and fit['checkpoint_file_sha256']==CHECKPOINT_SHA and fit['checkpoint_model_sha256']==C.digest(m),'fit_receipt_binding_mismatch')
    return validate_model(m)


def apply_limits():
    require(hasattr(os,'sched_getaffinity') and hasattr(resource,'RLIMIT_AS'),'resource_enforcement_unavailable')
    cpus=sorted(os.sched_getaffinity(0))[:2];require(cpus,'no_cpu_available');os.sched_setaffinity(0,cpus)
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024));resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    def expired(signum,frame):raise C.ContractError('test_wall_budget_exceeded')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,60)
    return {'cpu_affinity':cpus,'address_space_bytes':512*1024*1024,'wall_seconds':60}


def evaluate_after_start(folder,go,model,output,expected_go_sha):
    """Caller must have already irrevocably claimed the global TEST marker."""
    marker=strict_json(safe_bytes(GLOBAL_TEST_START,65536))
    require(marker.get('root_GO_file_sha256')==expected_go_sha and marker.get('input_sha256')==go['input_sha256'] and marker.get('checkpoint_sha256')==CHECKPOINT_SHA and marker.get('fit_receipt_sha256')==FIT_RECEIPT_SHA,'global_TEST_claim_required')
    data=read_bound(folder,'test.json',go)
    predictions=predict_all(model,data)
    predictions.update(checkpoint_file_sha256=CHECKPOINT_SHA,test_file_sha256=go['input_sha256']['test.json'],root_GO_sha256=expected_go_sha)
    prediction_path=output/'PREDICTIONS_FROZEN.json'
    prediction_sha=write_run_output(prediction_path,predictions)
    # The durable immutable file exists before the FIRST label file is opened.
    saved=safe_bytes(prediction_path,OUTPUT_RESERVE);require(sha_bytes(saved)==prediction_sha,'prediction_freeze_mismatch');frozen=strict_json(saved)
    a=read_bound(folder,'labels_a.json',go);b=read_bound(folder,'labels_b.json',go);receipts=read_bound(folder,'label_receipts.json',go)
    require(C.digest(receipts)==go['review_approval_sha256'],'root_GO_review_approval_mismatch')
    require(receipts.get('dataset_file_sha256')==go['input_sha256']['test.json'],'review_dataset_hash_mismatch')
    require(receipts.get('review_files_sha256')=={'a':go['input_sha256']['labels_a.json'],'b':go['input_sha256']['labels_b.json']},'review_payload_hash_mismatch')
    verified=validate_data(data,a,b,receipts)
    metrics=family_metrics(frozen,verified)
    audit={};lookups=validate_reviews(data,a,b,receipts)
    for row in data['slots']:
        if row['status']!='completed':audit[row['id']]={'eligible':False,'exclusion_reason':row['status']};continue
        props=L.observed_properties(row['text'],row['mainpoint_exact'])
        outcome=L.adjudicate_pair(lookups[0][row['review_id']],lookups[1][row['review_id']],props,row['fact_ids'])
        audit[row['id']]={'eligible':outcome['realized_condition'] is not None,'actual_realized_condition':outcome['realized_condition'],'semantic_consensus_pass':outcome['semantic_consensus_pass'],'mechanical_condition':props['mechanical_condition'],'exclusion_reason':None if outcome['realized_condition'] is not None else 'dual_review_or_support_excluded'}
    return prediction_sha,metrics,verified,audit


def run(input_dir,expected_go_sha):
    resources=apply_limits();started=time.monotonic();output=None;claimed=False
    try:
        folder,go,external_bytes=authorize_go(input_dir,expected_go_sha);model=load_frozen_model()
        control=GLOBAL_TEST_START.parent;durable_mkdir(control,exist_ok=True)
        require(not control.is_symlink(),'marker_directory_symlink_forbidden')
        output=ROOT/'runs'/go['run_id'];durable_mkdir(output.parent,exist_ok=True)
        require(not output.parent.is_symlink() and not output.exists() and not output.is_symlink(),'output_already_exists_or_symlink')
        marker={'schema':'one-time-controlled-TEST-start/v1','root_GO_file_sha256':expected_go_sha,'run_id':go['run_id'],'package_manifest_sha256':go['package_manifest_sha256'],'protocol_sha256':go['protocol_sha256'],'code_sha256':go['code_sha256'],'input_sha256':go['input_sha256'],'checkpoint_sha256':CHECKPOINT_SHA,'fit_receipt_sha256':FIT_RECEIPT_SHA,'fit_complete_sha256':FIT_COMPLETE_SHA,'started_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'failure_consumes_test_authorization':True}
        # O_EXCL arbitrates concurrent invocations. No test bytes above this line.
        marker_sha=write_run_output(GLOBAL_TEST_START,marker);claimed=True
        durable_mkdir(output,exist_ok=False)
        predictions_sha,metrics,verified,audit=evaluate_after_start(folder,go,model,output,expected_go_sha)
        require(time.monotonic()-started<=60,'test_wall_budget_exceeded')
        result={'schema':'controlled-condition-test-receipt/v1','status':'completed_one_time_exploratory_test','root_GO_sha256':expected_go_sha,'TEST_START_sha256':marker_sha,'package_manifest_sha256':go['package_manifest_sha256'],'protocol_sha256':go['protocol_sha256'],'code_sha256':go['code_sha256'],'input_sha256':go['input_sha256'],'checkpoint_file_sha256':CHECKPOINT_SHA,'fit_receipt_sha256':FIT_RECEIPT_SHA,'fit_complete_sha256':FIT_COMPLETE_SHA,'predictions_file_sha256':predictions_sha,'predictions_frozen_before_labels_and_diagnostics':True,'family_support':verified['family_support']['test'],'exclusions':verified['exclusions'],'all_slot_audit':audit,'metrics':metrics,'resources':resources,'wall_seconds':time.monotonic()-started,'fit_invocations':0,'alternate_checkpoints':0,'inference_candidates_generated':0,'test_reruns_permitted':0,'eight_families_exploratory_only':True,'human_style_claim':False,'semantic_guarantee':False,'generic_stage_complete':False,'counts_towards_1280_natural_works':False,'personalization_authorized':False}
        receipt_sha=write_run_output(output/'TEST_RECEIPT.json',result)
        complete={'schema':'one-time-controlled-TEST-complete/v1','run_id':go['run_id'],'receipt_sha256':receipt_sha,'predictions_sha256':predictions_sha,'TEST_START_sha256':marker_sha}
        complete_size=len(C.canonical(complete))+1
        output_bytes=sum(p.stat().st_size for p in output.iterdir())+GLOBAL_TEST_START.stat().st_size+complete_size
        require(output_bytes<=OUTPUT_RESERVE,'output_reservation_exceeded')
        require(external_bytes+package_bytes()+complete_size<=LIMIT,'controlled_artifact_cap_exceeded')
        require(time.monotonic()-started<=60,'test_wall_budget_exceeded')
        write_run_output(control/'TEST_COMPLETE.json',complete)
    except BaseException as exc:
        if claimed and output is not None and output.is_dir():
            try:write_run_output(output/'FAILED.json',{'status':'failed_closed_TEST_consumed_no_rerun','error_type':type(exc).__name__,'error':str(exc)[:2048],'root_GO_sha256':expected_go_sha})
            except BaseException:pass
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)
    # A reporting channel failure must not retroactively invalidate the durable
    # commit or create FAILED beside an otherwise successful completion.
    try:print(json.dumps({'status':result['status'],'output':str(output),'test_reruns_permitted':0}))
    except OSError:pass


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--input-dir');p.add_argument('--expected-go-sha256');a=p.parse_args()
    require(a.run and a.input_dir and a.expected_go_sha256,'explicit_TEST_GO_required')
    run(a.input_dir,a.expected_go_sha256)

if __name__=='__main__':main()
