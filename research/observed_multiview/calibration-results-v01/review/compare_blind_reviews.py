"""Post-blind conservative comparison; original judgments are immutable inputs."""
import collections,hashlib,json,pathlib
O=pathlib.Path('/workspace/shared/style-scale10-calibration-results-review-v01');B=pathlib.Path('/workspace/shared/style-calibration-second-review')
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def j(p):return json.loads(p.read_text())
ap=O/'private/BLIND_A_PER_RECORD_FROZEN.private.json';bp=B/'review-labels.frozen.private.json';br=B/'FROZEN.receipt.json'
assert h(ap)=='567ca63802543b8e6cdc1682ccfeb9e99d3208f84851f227b42ffe68d194d4a5'
assert h(bp)=='36887220588145e70adfe5f681b62b6a5f65c26b4c832afc59fea3e4d85ae02a'
assert h(br)=='1c7deef80b47d1a607826a76d94218955c1e09619770b93cf3ed5523322e639c'
A=j(ap);BB=j(bp);a=A['records'];bm={x['record_key']:x for x in BB['records']};checks={x['record_key']:x for x in j(O/'private/record-checks.private.json')};rows=[];cells=collections.Counter();dispositions=collections.Counter();bysource=collections.defaultdict(collections.Counter)
for x in a:
 y=bm[x['record_key']];assert x['output_sha256']==y['output_sha256'] and x['source_sha256']==y['source_sha256'];assert x['full_raw_source_read']and y['assistant_raw_and_all_projected_text_read']
 ar=x['role_judgment'];by=y['role_isolation']
 if y['role_decision']=='undetermined':by='uncertain'
 cells[ar+'/'+by]+=1
 if x['frozen_index']==85:final='quarantine';why='双方对照后同意：独立时刻表导航角色漏出，整记录隔离；不回写原始A标签'
 elif x['frozen_index']==72:final='undetermined';why='价格/食物标签与句内列举边界保留未决，待未来书面角色合同决定'
 else:
  ad='quarantine'if checks[x['record_key']]['segments']==0 or ar=='fail'else 'undetermined'if ar=='uncertain' or x['rights_judgment']=='uncertain'else 'allowed_body_candidate'
  assert ad==y['role_decision'];final=ad;why='两份盲审的规范化记录处置一致'
 rows.append({'record_key':x['record_key'],'frozen_index':x['frozen_index'],'source_frame':x['source_frame'],'A_role':ar,'B_normalized_role':by,'A_rights_label':x['rights_judgment'],'B_rights_label':y['specific_rights_risk_review'],'adjudicated_disposition':final,'reason':why,'character_eligible':x['preparse_eligible'],'admitted':False})
 dispositions[final]+=1;bysource[x['source_frame']][final]+=1
aggregate={'schema_version':'fixed96-postblind-comparison/1','original_A_labels_sha256':h(ap),'original_B_labels_sha256':h(bp),'B_frozen_receipt_sha256':h(br),'B_postblind_concurrence_sha256':h(B/'POSTBLIND_CONCURRENCE.private.json'),'originals_unchanged':True,'full_read_records_each_reviewer':96,'normalized_role_agreements':94,'original_disagreements':2,'normalized_role_confusion':dict(cells),'conservative_final_record_dispositions':dict(dispositions),'by_source':{k:dict(v)for k,v in bysource.items()},'adjudication':'navigation-bearing record quarantined; price/food boundary unresolved','character_eligible_records_before_role_review':1,'character_eligible_records_passing_adjudicated_role_disposition':0,'admitted_records':0,'rights_label_semantics_not_assumed_equal':True,'human_gold':False,'source_admission_approved':False,'copy_lineage_gate':'not_yet_run','NLP_or_fit_calls':0,'replacement_records':0}
(O/'private/ADJUDICATION.private.json').write_text(json.dumps({'aggregate':aggregate,'records':rows},ensure_ascii=False,indent=2)+'\n')
(O/'public/postblind-comparison.aggregate.json').write_text(json.dumps(aggregate,ensure_ascii=False,indent=2)+'\n');print(json.dumps(aggregate,ensure_ascii=False,indent=2))
