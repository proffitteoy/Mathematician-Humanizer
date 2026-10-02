#!/usr/bin/env python3
"""Reconstruct public-only facts from prior emitted code/tool results; no data access."""
import ast,hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b if isinstance(b,bytes) else b.encode()).hexdigest()
serialize=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def save(name,obj): (ROOT/name).write_bytes(serialize(obj)+b'\n')
upos=['ADJ','ADP','ADV','AUX','CCONJ','DET','NOUN','NUM','PART','PRON','PROPN','SCONJ','VERB']
rels=['acl','advcl','advmod','amod','appos','aux','case','cc','ccomp','clf','compound','conj','cop','csubj','det','discourse','dislocated','flat','iobj','mark','nmod','nsubj','nummod','obj','obl','parataxis','xcomp']
shape=['word_length.mean','word_length.ge4','word.single_han','word.latin','word.decimal_digit']
lexical=['lexical.mattr100','lexical.entropy100','lexical.content_overlap','lexical.trigram_reuse']
geometry=['dependency.span_mean','dependency.span_normalized','dependency.depth_mean','dependency.maxdepth_median']
syntax=['syntax.predicate_heads','syntax.subordinate_arcs','syntax.predicate_conj_share','syntax.nominal_modifier_size','syntax.verb_root_without_subject','syntax.preposed_modifiers','syntax.initial_pos_reuse']
cues=['pronoun_first','pronoun_second','pronoun_third','negator','de_function_form','di_subordinator_form','de_extent_form','le_auxiliary_form','zhe_auxiliary_form','guo_auxiliary_form']
families={}
for family,ids in [('upos_composition',['upos.'+p for p in upos]),('dependency_composition',['deprel.'+r for r in rels]),('lexical_shape',shape),('lexical_reuse',lexical),('upos_sequence',['upos.bigram_entropy100']),('dependency_geometry',geometry),('syntactic_configuration',syntax),('closed_class_cues',['cue.'+c for c in cues])]:
 for k in ids:families['zh:'+k]=family
channels=list(families);assert len(channels)==71
source=(ROOT/'extract.py').read_bytes();expected='617c3b1ebc88f623e7de9930aad873d00a48a06ee41e4e7c5e9eabd6ffd4aec1';assert sha(source)==expected
module=ast.parse(source)
ns={'CHANNEL_IDS':tuple(channels)}
for node in module.body:
 if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'VERSION','SEED','HISTORY','ARMS','EXPECTED_COHORT','EXPECTED_RAW','PROJECTION_PROFILE'}:
  ns[node.targets[0].id]=ast.literal_eval(node.value)
 if isinstance(node,ast.FunctionDef) and node.name=='protocol':
  exec(compile(ast.Module(body=[node],type_ignores=[]),'<recovered_original_protocol>','exec'),ns)
protocol=ns['protocol']();assert sha(serialize(protocol))=='6e2c5562dfd51b3735486475376662acf09d1fe218a95e5005fb4eeb6ac719a9'
save('extraction_protocol.json',protocol)
save('cache_schema_reconstructed.json',{
 'reconstruction_status':'ordered IDs and cache field contract reconstructed from emitted original wrapper and reviewed design; not a byte-exact recovery of the lost channel_schema.json',
 'authoritative_schema_source':'proffitteoy/style-compiler@2c3eeb0bcf3020fcba36f13b2bc6bab490b3f1ae:research/linguistic/schema.py',
 'original_channel_schema_sha256_from_training_contract':'e331e222e8f6e26eefc7a71c623121baa44c3fe6f9217a78c537db3458157610',
 'channel_ids_exact_order_71':channels,'channels':[{'id':c,'family':families[c],'history_audit_only':c in ns['HISTORY']} for c in channels],
 'core_local_ids_68':[c for c in channels if c not in ns['HISTORY']],
 'measurement_paths':['bundle.target.global_measurements','bundle.target.sequence[].measurements'],
 'typed_row_fields':['value','numerator','denominator','opportunities','missing_reason','status','comparison_eligible','uncertainty_interval','opportunity_type'],
 'opportunity_policy':'Preserve original instrument denominator/opportunity fields; never recompute or epsilon/zero-fill from schema labels',
 'status_values':['observed','zero_observed','unavailable'],
 'structural_fields':['source_sentence_index','source_span','structure.source_sentence_span_codepoints','structure.content_codepoints','structure.lexical_token_count','lexical_token_count_status','lexical_token_count_missing_reason','operational_physical_line_index','frozen_blank_line_block_memberships','frozen_blank_line_block_overlaps','parse_status','parse_reason'],
 'T_semantics':'Exact count of unchanged instrument lexical(t) after successful parse, including true zero; null with reason for failed parse',
 'span_width_semantics':'end-start in original source codepoints; remains available independently of parsing',
 'cohort_fields':['pair_id','arm','split','question_family_id','component_id','source','source_ID','inference_cluster','question_family_answer_count','equal_question_family_answer_weight','authorship_status','source_support'],
 'ledger_events':{'measurement_started':['phase','pair_id','arm','split','raw_access'], 'cache_committed':['phase','cache_file','cache_sha256','pair_id','arm','split','bytes','timing','source_failure','local_units']},
 'private_only_fields':['cohort','raw_access_audit','parsed_annotation','source_view','projection','structural_units','bundle'],
 'candidate_unvalidated':True,'empirical_model_admitted':False,'comparison_eligible':False,'discourse_graph':{'value':None,'missing_reason':'no_validated_M4_producer'},
 'web_original_writer_paragraph_view':{'value':None,'missing_reason':'original_writer_layout_unsupported_unknown'}})
save('predeclaration_receipt.reconstructed.json',{
 'full_support':{'arms':4814,'codepoints':1576626,'frozen_sentence_proxy_units':41849,'pairs':2407},
 'pilot_plan_sha256':'2de48ce4ab8e947588ef7b5d0f9c00ac65c4cec6b34dad594e57cdc2b71979ef',
 'pilot_support':{'arms':40,'codepoints':10663,'frozen_sentence_proxy_units':296,'pairs':20},
 'protocol_sha256':'6e2c5562dfd51b3735486475376662acf09d1fe218a95e5005fb4eeb6ac719a9','selected_before_any_measurement':True,'test_and_davinci_bodies_read':0})
save('model_free_receipt.reconstructed.json',{'tests_run':164,'restored_tests_run':156,'wrapper_tests_run':8,'failures':0,'errors':0,'skips':[{'test':'test_unicode_tables_match_full_official_local_data (research.linguistic.independent_checks.IndependentReview.test_unicode_tables_match_full_official_local_data)','reason':'Set STYLE_UNICODE_SCRIPTS_FILE to the pinned official Unicode15 Scripts.txt'}],'success':True,'wrapper_tests_success':True,'model_free':True,'corpus_bodies_read':0})
save('pilot_summary.reconstructed.json',{
 'phase':'pilot','arm_records':40,'record_statuses':{'measured_no_parse_failure':39,'complete_parse_failure':1},
 'sentence_error_reasons':{'alignment_failed':1},'local_sequence_rows':320,'measurement_profile_sha256':['221323897ea20205d0801383537558b4411cb47eb945c2deac51e24ccb2549a3'],
 'model_load_seconds':4.106790374004049,'phase_wall_seconds':19.9413821369817,'measurement_wall_seconds':15.341792401944986,'measurement_cpu_seconds':30.238295355999988,
 'peak_rss_bytes':991526912,'raw_test_bodies_read':0,'davinci_bodies_read':0,'candidate_unvalidated':True,'strict_prefix_causal_claim':False,'all_per_sample_data_private':True,
 'projection_scale':147.85951420800902,'projection_safety_factor':1.25,'projected_total_wall_seconds':2839.644254913641,'pilot_cache_bytes':973802,'projected_derived_disk_bytes':190468123.3184845,
 'go_full_run_at_that_time':True,'newly_measured':40,'cache_reused':0,'derived_bytes':1044979,
 'protocol_sha256':'6e2c5562dfd51b3735486475376662acf09d1fe218a95e5005fb4eeb6ac719a9','wrapper_sha256':expected})
save('pilot_resource_receipt.reconstructed.json',{'phase':'pilot','affinity_cores':[0,1],'elapsed_seconds':20.703769221989205,'peak_process_tree_rss_bytes_sampled_100ms':991932416,'cpu_seconds_sampled':35.730000000000004,'exit_code':0,'stopped_reason':None,'rss_limit_bytes':2147483648,'wall_limit_seconds':1200.0,'derived_bytes_sampled':1044979})
save('checkpoint_2025_arms.reconstructed.json',{
 'snapshot_committed_arms':2025,'total_arms':4814,'groups':{
 'web|human':{'arms':498,'with_source_failure':0,'with_parse_failure':0,'units':2575,'failed_units':0,'reasons':{},'window100_local_available':35,'window100_local_zero_denominator':2540,'window100_global_available':405},
 'web|chatgpt':{'arms':498,'with_source_failure':0,'with_parse_failure':0,'units':5264,'failed_units':0,'reasons':{},'window100_local_available':0,'window100_local_zero_denominator':5264,'window100_global_available':452},
 'baike|human':{'arms':515,'with_source_failure':0,'with_parse_failure':8,'units':7530,'failed_units':38,'reasons':{'alignment_failed':37,'resource_limit':1},'window100_local_available':46,'window100_local_zero_denominator':7446,'window100_global_available':315},
 'baike|chatgpt':{'arms':514,'with_source_failure':0,'with_parse_failure':0,'units':4758,'failed_units':0,'reasons':{},'window100_local_available':0,'window100_local_zero_denominator':4758,'window100_global_available':342}},
 'measured_wall_seconds':942.623928542569,'cache_bytes':57736897,'naive_remaining_measurement_minutes_at_that_time':21.63768013749156,'partial_snapshot_not_final':True,'test_or_davinci_bodies_read':0})
save('continuity_incident.json',{
 'status':'blocked_executor_replaced_before_completion','observed_utc':'2026-10-02T03:39:26Z',
 'transport_error':'exec-server transport disconnected; failed to resume exec-server session: exec-server protocol error: executor key changed during session recovery',
 'last_confirmed_cache_aggregate':{'committed':4338,'by_split':{'train':3632,'dev':706},'cache_mib_rounded':115.0},
 'last_progress_log':{'phase':'full','completed':4320,'total':4814,'newly_measured':4280,'cache_reused':40,'wall_seconds':2002.9309815049928},
 'recoverable_private_cache_count':0,'recoverable_cohort_file_count':0,'recoverable_model_or_runtime_directories':0,
 'search_scope':['expected workspace paths','/workspace depth3','/tmp depth3','live extraction process list'],
 'new_workspace_overlay_used_mib':88,'full_receipt_reached':False,'verification_receipt_reached':False,
 'downstream_cache_gate':'closed','scientific_extraction_complete':False,
 'no_rerun_no_download_after_replacement':True,'no_private_sample_export':True,
 'interpretation':'Prior completion counts describe observed progress in the replaced executor only. They do not represent presently available or verified training data.'})
save('input_pins.json',{
 'restored_instrument_repo':'proffitteoy/style-compiler','restored_instrument_revision':'2c3eeb0bcf3020fcba36f13b2bc6bab490b3f1ae',
 'M4_revision':'628bf0fcb2e8c6b7ffa71fd1af6be413aced8f7d',
 'cohort_identity_views_sha256':'caab83530f309622cbafe95b92e648fc59936435b170f7ef3f38abf23cf3a1ca',
 'components_and_splits_sha256':'835e6521559b29349570d99b25bc96d353837d8383e002e0b3dadf507a3579b0',
 'component_edges_sha256':'fd738ba9c9aa5f353edeb995699bf8df60a4d78dd0d4ffa0ae064aa439d4b0ec',
 'qazh_chatgpt_jsonl_sha256':'cc2fb0d6c2e63f507717835cd20f992a513d098af6259ce888552ddeca79cfee',
 'qazh_chatgpt_jsonl_bytes':7025906,'qazh_chatgpt_git_blob_sha1':'be87e80335e8c1baa494d5272cbee1d5b2dfff3d',
 'stanza':'1.10.1','torch':'2.3.1+cpu','numpy':'1.26.4','exact_historical_runtime':False,
 'model_repo_commit':'82f2856d1cf4f933738a8a84b5ad959d156040a0','language':'zh-hans','resources':'1.10.0',
 'resources_json_sha256':'3efb2833a67c0184fac2ea9986c04f9585bfb89fb943a4ab1a6bcbed641d6be0',
 'models':{
 'tokenize/gsdsimp.pt':{'bytes':1383326,'sha256':'962f2578e2a3dabeb4671053372eb1bd092357921904233556c8d77a46440882'},
 'pos/gsdsimp_nocharlm.pt':{'bytes':21285503,'sha256':'0dea6b43c267b408fc7c353e41b449a06bff309a93ba75fa63db32bf9f388cb7'},
 'lemma/gsdsimp_nocharlm.pt':{'bytes':6592066,'sha256':'8fe38f6b081d939662a4e78a4350a2253f879c41004327ac6fb78d7078bdeea2'},
 'depparse/gsdsimp_nocharlm.pt':{'bytes':103928202,'sha256':'7a3f038233a772c50372a58b58a05ca0c3b0be9c88d6ed7b2664373c0ef741f6'},
 'pretrain/fasttext157.pt':{'bytes':306614467,'sha256':'630daf461d1dc6f49642ee534102bf08783866949f7f046cf2df3667dcc5e112'}},
 'parse_settings':{'threads':2,'use_gpu':False,'tokenize_no_ssplit':True,'download_method':None},
 'guard_limits':{'source_codepoints':200000,'source_sentences':512,'sentence_codepoints_before_parse':2048,'sentence_tokens':2048,'total_tokens':16384},
 'last_verified_measurement_profile_sha256':'221323897ea20205d0801383537558b4411cb47eb945c2deac51e24ccb2549a3',
 'restoration_source_manifest_sha256':{'repo-source-manifest.json':'3e321c88abe981c6f8e9b4cecad0ec9a21dd71b30feebfe1a780b44a8402abdc','repo-additional-source-manifest.json':'61fd06d87958fa1c8c8e32f06b18926b473aa3fde06d614f0a0de01012723299','repo-schema-source-manifest.json':'911a1291922333160b4699ea3c7ae82aeafebf87764721eafb2b1510e7998b3d'},
 'instrument_checkpoint_before_replacement':{'source_files_checked':48,'runtime_packages_checked':12,'all_unchanged':True,'runtime_RECORD_hash_convention':'read_text universal-newline normalization, matching restoration manifest'}})
print(json.dumps({'source_exact_hash_match':True,'protocol_canonical_hash_match':True,'files':len(list(ROOT.iterdir()))}))
