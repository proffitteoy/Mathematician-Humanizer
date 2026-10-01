"""Read-only actual-fit verification. Never calls fit or run; never reads TEST.
Only reads the frozen fit package, its outputs, six specifically approved
sanitized handoff files, and root's explicitly permitted budget-release receipt.
Public outputs contain aggregates and hashes, no prose or family identifiers.
"""
from __future__ import annotations
import collections, datetime as dt, hashlib, json, math, os, pathlib, re, resource, signal, statistics, sys, time
PACKAGE=pathlib.Path('/workspace/shared/style-controlled-fit-v01')
INPUT=pathlib.Path('/workspace/shared/style-controlled-authoring-v02/private/train-dev-export-v01')
RUN=PACKAGE/'runs'/'controlled_v1_20261001'
OUT=pathlib.Path(__file__).resolve().parent
RELEASE=pathlib.Path('/workspace/shared/style-controlled-fit-budget-release.json')
EXPECTED={'manifest':'1c99373b805ca12f46ecd57362b26be376cc4a1005c01009067e8aa304f4e4f7','protocol':'b64fb0017677baa8ab4fb52ca17a07b92fac95b72c0cdf742fb7926dc61b0ed2','checkpoint':'c2d6d4352c0209d78f221ede226301fa835fa80c679a77b6f09bd9544aabc83b','fit_receipt':'96283df19251dabc0b4e416d8745e4dd80db227be35b3982489d8f9e3eb5887b','complete':'5e3069433e398b1dc07026d2bc9b6409d18b9e0cf377bdf40ea71286c701279e'}
sys.path.insert(0,str(PACKAGE))
import controller_v03 as C
import fit_wrapper as W
import labels_v02 as L

checks=[]
def check(ok,name):
    if not ok:raise AssertionError(name)
    checks.append(name)
def forbidden_fit(*a,**kw):raise AssertionError('Fitting is forbidden during result audit')
C.fit=forbidden_fit
W.run=forbidden_fit

def sha(path):return hashlib.sha256(W.safe_bytes(path,4*1024*1024)).hexdigest()
def read(path):return W.strict_json(W.safe_bytes(path,4*1024*1024))
def utc(value):
    d=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    check(d.tzinfo is not None and d.utcoffset()==dt.timedelta(0),'valid_UTC_timestamp')
    return d

def own_features(text,span):
    segments=re.split(r'[。！？!?]+',text)
    sizes=[len(''.join(s.split())) for s in segments if s.strip()]
    n=math.fsum(sizes);mean=n/len(sizes)
    sd=math.sqrt(math.fsum((x-mean)**2 for x in sizes)/len(sizes))
    nonspace=len(''.join(text.split()));a,b=span
    return [math.log1p(n),math.log1p(len(sizes)),mean,sd,sd/mean,
        sum(x<=24 for x in sizes)/len(sizes),sum(x>=40 for x in sizes)/len(sizes),
        math.fsum(abs(sizes[i]-sizes[i-1]) for i in range(1,len(sizes)))/max(1,len(sizes)-1)/mean,
        math.log1p(sum(bool(p.strip()) for p in re.split(r'\n[\t ]*\n',text))),
        sum(ch in '，、；：,;:' for ch in text)/len(text),
        len(''.join(text[:a].split()))/nonspace,len(''.join(text[:b].split()))/nonspace]

def own_scaler(rows):
    columns=list(zip(*(r['x'] for r in rows)))
    fixed=[len(set(c))==1 for c in columns]
    return {'center':[c[0] if constant else statistics.fmean(c) for c,constant in zip(columns,fixed)],
            'scale':[1. if constant else statistics.pstdev(c) for c,constant in zip(columns,fixed)],
            'constant':fixed,'fit_partition':'train'}
def transform(x,t):return [0. if t['constant'][j] else (x[j]-t['center'][j])/t['scale'][j] for j in range(12)]+[1.]
def softmax(z):
    e=[math.exp(v-max(z)) for v in z];denom=math.fsum(e);return [v/denom for v in e]
def prediction(x,weights,t):
    y=transform(x,t);return softmax([math.fsum(a*b for a,b in zip(w,y)) for w in weights])
def maxerror(a,b):return max(abs(x-y) for r,s in zip(a,b) for x,y in zip(r,s))

def verify_recurrence(rows,t,saved):
    """Verification-only recurrence from the frozen 150-step specification.
    No optimizer/fit API, no output checkpoint, no selection, no alternative fit.
    """
    groups=collections.Counter(r['family'] for r in rows)
    xx=[transform(r['x'],t) for r in rows];weights=[[0.]*13 for _ in range(4)];first=None
    for epoch in range(150):
        g=[[0.]*13 for _ in range(4)]
        for row,x in zip(rows,xx):
            p=softmax([math.fsum(a*b for a,b in zip(w,x)) for w in weights])
            mass=1/(len(groups)*groups[row['family']]);target=C.CONDITIONS.index(row['condition'])
            for k in range(4):
                for j in range(13):g[k][j]+=mass*(p[k]-(k==target))*x[j]
        if epoch==0:first=math.sqrt(math.fsum(v*v for row in g for v in row))
        for k in range(4):
            for j in range(13):weights[k][j]-=.05*g[k][j]
    return {'first_gradient_l2':first,'max_abs_checkpoint_weight_error':maxerror(weights,saved),'steps':150,'learning_rate':.05,'verification_only':True,'fit_function_calls':0,'checkpoint_writes':0}

def independent_metrics(rows,slots,weights,t):
    families={r['family']:{'all':0,'eligible':0,'ce':0.,'correct':0.,'rule_ce':0.,'rule_correct':0.} for r in slots}
    p_error=0.
    for slot in slots:families[slot['family']]['all']+=1
    confusion=[[0]*4 for _ in range(4)]
    for row in rows:
        target=C.CONDITIONS.index(row['condition']);p=prediction(row['x'],weights,t)
        selected=max(range(4),key=lambda k:p[k]);f=families[row['family']]
        f['eligible']+=1;f['ce']-=math.log(max(p[target],1e-300));f['correct']+=(selected==target)
        confusion[target][selected]+=1
        # Definition comparator, not another learned model.
        mechanical=L.observed_properties(row['text'],row['mainpoint'])['mechanical_condition']
        rule_index=C.CONDITIONS.index(mechanical);rp=[1e-15]*4;rp[rule_index]=1.;denom=math.fsum(rp)
        f['rule_ce']-=math.log(rp[target]/denom);f['rule_correct']+=(rule_index==target)
    good=[f for f in families.values() if f['eligible']]
    mean=lambda key:statistics.fmean(f[key]/f['eligible'] for f in good)
    aggregate={'all_families':len(families),'all_slots':len(slots),'eligible_families':len(good),'eligible_rows':len(rows),
        'family_macro_accuracy_on_eligible':mean('correct'),'family_macro_cross_entropy_on_eligible':mean('ce'),
        'family_macro_coverage_over_all_original_slots':statistics.fmean(f['eligible']/f['all'] for f in families.values()),
        'exact_threshold_rule':{'family_macro_accuracy_on_eligible':mean('rule_correct'),'family_macro_cross_entropy_on_eligible':mean('rule_ce'),
            'coverage_is_shared_dual_review_filter':True,'interpretation':'tautological_class_definition_comparator_not_human_style'}}
    return aggregate,families,confusion


def main():
    startwall=time.monotonic();startcpu=time.process_time()
    os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912));resource.setrlimit(resource.RLIMIT_CPU,(60,60));signal.alarm(60)
    check(sha(PACKAGE/'FILE_HASHES.json')==EXPECTED['manifest'],'manifest_external_hash_match')
    check(W.package_hashes_ok()==EXPECTED['manifest'],'all_frozen_package_files_unchanged')
    check(sha(PACKAGE/'protocol.json')==EXPECTED['protocol'],'protocol_external_hash_match')
    allowed=set(W.INPUT_FILES)|{'ROOT_GO.json'}
    check({p.name for p in INPUT.iterdir()}==allowed,'exact_six_sanitized_files_and_no_extras')
    check(all(p.is_file() and not p.is_symlink() for p in INPUT.iterdir()),'six_regular_nonsymlink_files')
    check({p.name for p in RUN.iterdir()}=={'FIT_RECEIPT.json','condition-only.weights.json'},'only_checkpoint_and_fit_receipt_in_run')
    start=read(PACKAGE/'run_state'/'EMPIRICAL_START.json');complete=read(PACKAGE/'run_state'/'EMPIRICAL_COMPLETE.json')
    gohash=sha(INPUT/'ROOT_GO.json');go,inputs=W.read_authorized_inputs(INPUT,gohash)
    check(gohash==start['root_GO_file_sha256'],'GO_matches_exclusive_START')
    check(sha(RUN/'condition-only.weights.json')==EXPECTED['checkpoint'],'checkpoint_external_hash_match')
    check(sha(RUN/'FIT_RECEIPT.json')==EXPECTED['fit_receipt'],'fit_receipt_external_hash_match')
    check(sha(PACKAGE/'run_state'/'EMPIRICAL_COMPLETE.json')==EXPECTED['complete'],'complete_external_hash_match')
    check(complete['checkpoint_sha256']==EXPECTED['checkpoint'] and complete['receipt_sha256']==EXPECTED['fit_receipt'],'complete_binds_exact_checkpoint_and_receipt')
    check(go['run_id']==start['run_id']==complete['run_id']==RUN.name,'run_identity_matches')
    measured=utc(inputs['storage_receipt.json']['measured_at_utc']);issued=utc(go['issued_at_utc']);started=utc(start['started_at_utc'])
    release=read(RELEASE);released=utc(release['released_at_utc'])
    check(measured<=issued<=started<=released,'timestamp_order_storage_GO_START_release')
    check(0<=(started-measured).total_seconds()<=600,'storage_receipt_fresh_at_actual_start')
    receipt=read(RUN/'FIT_RECEIPT.json');model=C.load_checkpoint(RUN/'condition-only.weights.json',EXPECTED['checkpoint'])
    check(receipt['root_GO_sha256']==gohash and receipt['package_manifest_sha256']==EXPECTED['manifest'],'fit_receipt_binds_GO_and_package')
    check(receipt['input_sha256']==go['input_sha256'],'fit_receipt_binds_all_five_inputs')
    labels=inputs['label_receipts.json'];data=inputs['train_dev.json'];reviews=(inputs['labels_a.json'],inputs['labels_b.json'])
    check(labels['dataset_file_sha256']==go['input_sha256']['train_dev.json'],'labels_bind_dataset_file')
    check(labels['review_files_sha256']=={key:go['input_sha256'][name] for key,name in (('a','labels_a.json'),('b','labels_b.json'))},'labels_bind_subset_review_files')
    verified=W.validate_data(data,*reviews,labels)
    tables=[{r['review_id']:r for r in payload['reviews']} for payload in reviews]
    independent={'train':[],'dev':[]};support={p:{c:set() for c in C.CONDITIONS} for p in independent};counts={p:collections.Counter() for p in independent};exclusions=collections.Counter()
    features_error=0.
    for slot in data['slots']:
        p=slot['partition'];check(p in ('train','dev'),'slot_partition_train_or_dev_only')
        if slot['status']!='completed':exclusions[slot['status']]+=1;continue
        props=L.observed_properties(slot['text'],slot['mainpoint_exact'])
        actual=L.adjudicate_pair(tables[0][slot['review_id']],tables[1][slot['review_id']],props,slot['fact_ids'])['realized_condition']
        check(actual==slot['realized_condition'],'frozen_dual_review_label_recomputed')
        if actual is None:exclusions['dual_review_or_support_excluded']+=1;continue
        x=own_features(slot['text'],props['mainpoint_span']);features_error=max(features_error,max(abs(a-b) for a,b in zip(x,C.features(slot['text'],props['mainpoint_span']))))
        independent[p].append({'family':slot['family'],'condition':actual,'x':x,'text':slot['text'],'mainpoint':slot['mainpoint_exact']})
        support[p][actual].add(slot['family']);counts[p][actual]+=1
    support={p:{c:len(fs) for c,fs in cs.items()} for p,cs in support.items()}
    check(features_error<=1e-12,'independent_12_features_match')
    check(support==verified['family_support']==receipt['family_support'],'family_support_recomputed_matches_receipt')
    check(dict(exclusions)==verified['exclusions']==receipt['exclusions'],'excluded_slot_counts_match')
    check(all(v>=16 for v in support['train'].values()) and all(v>=4 for v in support['dev'].values()),'all_class_family_support_thresholds_pass')
    t=own_scaler(independent['train']);saved=model['transform']
    scaler_error=max(max(abs(a-b) for a,b in zip(t[k],saved[k])) for k in ('center','scale'))
    check(t['constant']==saved['constant'] and scaler_error<=1e-12,'independent_train_only_scaler_matches_checkpoint')
    check(model['training']['epochs']==150 and model['training']['lr']==.05 and model['training']['preference_pairs']==0,'fixed_training_metadata')
    check(model['training']['dataset_sha256']==C.digest(verified['eligible']['train']),'training_dataset_digest_matches_validated_train_rows')
    train_rows=verified['eligible']['train']
    label_hash=C.digest([{'id':r['id'],'condition':r['condition'],'meaning_verified':r['meaning_verified'],'realized_condition_verified':r['realized_condition_verified']} for r in train_rows])
    authorization={'action':'CONTROLLED_STYLE_TRAIN_GO','actor':'root','dataset_sha256':C.digest(train_rows),'labels_sha256':label_hash,'independent_label_review':True,'protocol_sha256':go['protocol_sha256']}
    check(model['training']['labels_sha256']==label_hash and model['authorization_sha256']==C.digest(authorization),'training_labels_and_authorization_digest_reconstructed')
    check(model['training']['provenance']=='assistant_authored_controlled' and model['training']['training_only'] is True and model['training']['status']=='completed_actual_gradient_fit','actual_controlled_training_provenance')
    check(receipt['epochs']==150 and receipt['learning_rate']==.05 and 0<=receipt['fit_replay_and_diagnostics_seconds']<=60,'fit_receipt_fixed_budget_metadata')
    check(len(receipt['resources']['cpu_affinity'])<=2 and receipt['resources']['address_space_bytes']==536870912 and receipt['resources']['wall_seconds']==60,'fit_receipt_resource_limit_metadata')
    check(model['training']['realizations']==len(independent['train']) and model['training']['families']==32,'training_row_and_family_metadata')
    check(model['training']['wrapper_root_GO_sha256']==gohash and model['training']['wrapper_package_manifest_sha256']==EXPECTED['manifest'],'checkpoint_wrapper_provenance_bindings')
    check(C.digest(model)==receipt['checkpoint_model_sha256'],'model_content_hash_matches_receipt')
    check(all(v==0. for row in model['preference_weights'] for v in row),'all_preference_weights_exact_zero')
    check(all(math.isfinite(v) for row in model['condition_weights'] for v in row) and any(v!=0 for row in model['condition_weights'] for v in row),'condition_weights_finite_and_nonzero')
    recurrence=verify_recurrence(independent['train'],t,model['condition_weights'])
    check(recurrence['max_abs_checkpoint_weight_error']<=1e-12 and recurrence['first_gradient_l2']>0,'independent_frozen_gradient_recurrence_matches_checkpoint')
    metrics={};confusion={};metric_error=0.;component_error=0.;prob_error=0.
    for p in ('train','dev'):
        agg,components,cm=independent_metrics(independent[p],verified['all_slots'][p],model['condition_weights'],t)
        metrics[p]=agg;confusion[p]=cm
        old=receipt['metrics'][p]
        for k,v in agg.items():
            if isinstance(v,dict):
                for kk,vv in v.items():
                    if isinstance(vv,(int,float)) and not isinstance(vv,bool):metric_error=max(metric_error,abs(vv-old[k][kk]))
                    else:check(vv==old[k][kk],'rule_comparator_metadata_matches')
            else:metric_error=max(metric_error,abs(v-old[k]))
        check(set(components)==set(old['by_family']),'internal_family_component_set_matches')
        for family,values in components.items():
            for key,value in values.items():component_error=max(component_error,abs(value-old['by_family'][family][key]))
        for row,wr in zip(independent[p],verified['eligible'][p]):
            pp=prediction(row['x'],model['condition_weights'],t);savedp=W.probabilities(model,wr['features']);prob_error=max(prob_error,max(abs(a-b) for a,b in zip(pp,savedp)))
    check(max(metric_error,component_error,prob_error)<=1e-12,'all_predictions_aggregates_and_private_family_components_recomputed')
    check(receipt['fit_invocations']==1 and receipt['test_opened'] is False and receipt['inference_candidates_generated']==0,'receipt_single_fit_no_TEST_no_candidates')
    check(release['test_remains_unscored'] is True and release['exclusive_budget_reservation_released'] is True,'root_attests_release_and_unscored_TEST')
    check(release['checkpoint_sha256']==EXPECTED['checkpoint'] and release['fit_receipt_sha256']==EXPECTED['fit_receipt'] and release['complete_sha256']==EXPECTED['complete'],'release_binds_exact_final_artifacts')
    packagebytes=W.package_bytes();runbytes=sum(p.stat().st_size for p in RUN.iterdir())
    check(packagebytes==release['final_package_bytes_including_markers'],'package_final_bytes_including_markers_recomputed')
    check(runbytes<=1048576,'actual_run_outputs_within_one_MiB')
    check(release['reserved_external_upper_bound']==inputs['storage_receipt.json']['external_controlled_bytes'],'release_external_bound_matches_root_storage_receipt')
    combined=packagebytes+release['reserved_external_upper_bound']+4096
    check(combined==release['combined_with_4096_release_allowance'] and combined<33554432,'final_combined_root_bound_arithmetic_matches_under_cap')
    check(combined+1048576<33554432,'new_audit_full_one_MiB_reservation_fits_root_bound')
    check(W.package_hashes_ok()==EXPECTED['manifest'],'frozen_package_unchanged_after_result_audit')
    resources={'cpu_affinity':sorted(os.sched_getaffinity(0)),'address_space_limit_bytes':resource.getrlimit(resource.RLIMIT_AS)[0],'cpu_limit_seconds':60,'cpu_seconds':time.process_time()-startcpu,'wall_seconds':time.monotonic()-startwall,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    public={'schema':'controlled-fit-result-independent-audit/v1','status':'pass_observed_fit_result_no_TEST_no_inference','audited_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'checkpoint_sha256':EXPECTED['checkpoint'],'fit_receipt_sha256':EXPECTED['fit_receipt'],'complete_sha256':EXPECTED['complete'],'root_GO_sha256':gohash,'package_manifest_sha256':EXPECTED['manifest'],'protocol_sha256':EXPECTED['protocol'],'release_receipt_sha256':sha(RELEASE),'input_file_hashes':{'ROOT_GO.json':gohash,**go['input_sha256']},'checks_total':len(checks),'distinct_checks':sorted(set(checks)),'eligible_class_counts':{p:dict(v) for p,v in counts.items()},'family_support':support,'exclusions':dict(exclusions),'metrics':metrics,'confusion_matrices':{'class_order':list(C.CONDITIONS),**confusion},'recomputation_max_abs_errors':{'features':features_error,'scaler':scaler_error,'probabilities':prob_error,'aggregate_metrics':metric_error,'private_family_components':component_error},'gradient_recurrence_verification':recurrence,'resources_for_this_audit':resources,'budget':{'actual_package_including_markers_bytes':packagebytes,'actual_run_output_bytes':runbytes,'root_attested_external_upper_bound_bytes':release['reserved_external_upper_bound'],'root_release_allowance_bytes':4096,'root_combined_bound_before_new_audit_bytes':combined,'reserved_new_audit_bytes':1048576,'cap_bytes':33554432,'external_directories_independently_counted':False},'scope':{'fit_api_calls':0,'wrapper_run_calls':0,'new_empirical_checkpoints':0,'TEST_reads':0,'TEST_scores':0,'real_inference_candidates':0,'original_384_review_file_reads':0,'private_family_plans_read':0,'remote_writes':0,'raw_rows_or_family_ids_in_report':False},'limits_of_evidence':['External disk total relies on root receipt; prohibited trees were not scanned.','Original 384-row review projection and reviewer independence remain root attestations.','The ledger and recurrence validate this checkpoint; they are not a process-history attestation beyond observed frozen code and markers.','Condition accuracy is on eligible rows only, and the exact rule comparator is definitional.']}
    (OUT/'aggregate-verification.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':public['status'],'checks_total':len(checks),'distinct_checks':len(set(checks)),'metrics':metrics,'max_abs_errors':public['recomputation_max_abs_errors'],'gradient_recurrence':recurrence,'resources':resources},ensure_ascii=False,indent=2))
    signal.alarm(0)

if __name__=='__main__':main()
