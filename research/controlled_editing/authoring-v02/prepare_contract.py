"""Build only frozen plans/prompts/job metadata. Does not author a realization."""
import collections, hashlib, json, platform, sys, unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(x): return hashlib.sha256(x).hexdigest()
def put(path,obj):
    data=canonical(obj)+b'\n'
    if path.exists():
        assert path.read_bytes()==data, 'refuse changed contract overwrite'
    else:path.write_bytes(data)
    return sha(data)
GENRES=['general_explanation','process_description','event_summary','reflective_commentary']
CONDITIONS=['short_early','short_late','mixed_early','mixed_late']
COMMON='''任务：根据这份虚构内容计划写一篇简体中文短文。所有计划都由助手编写，不是史料、真实个人经历或真实人类风格样本。只能使用给定主旨和事实；不得增加人物动机、因果解释、评价、数字或承诺。必须表达所有事实，保留否定、可能性、条件和适用范围。主旨原句必须逐字出现且仅出现一次；主旨位置以不含空白的全文字符计算。不要为了位置比例堆放空格。可自然拆分事实，但不得用无信息的重复句凑长度。正文为120到400个Unicode码点，主要为中文；至少4句，以。！？!?作为句界。仅写普通段落，不加标题、列表、引号、代码、数学公式、署名或条件标签。每个任务只有一次成文机会，无法满足时返回失败原因，不改写内容计划。输出严格JSON对象：{"text": "正文", "failure_reason": null}；如果无法完成，text为null。不要输出解释或分析。'''
TEMPLATES={
'A':{'instruction':COMMON+'\n写作顺序：先核对全部事实和限制，在内部安排信息顺序，再直接给出符合目标节奏与主旨位置的成文。允许自然衔接，但衔接不能引入新的事实。',
     'description':'fact-check then arrange, one realization'},
'B':{'instruction':COMMON+'\n写作顺序：先在内部选择适合目标的信息结构，再逐项对照内容计划确保没有增删或改变范围，最后直接给出成文。用自然表达连接现有事实，不增加新的内容。',
     'description':'arrange then fact-check, one realization'}}
TARGETS={
 'short_early':'短句节奏；至少80%的句子长度不超过24个非空白码点，所有句子不超过32个；主旨起点不晚于全文非空白码点的20%，并位于前2句。',
 'short_late':'短句节奏；至少80%的句子长度不超过24个非空白码点，所有句子不超过32个；主旨起点不早于全文非空白码点的70%，并位于最后2句。',
 'mixed_early':'混合节奏；至少1句不超过18个非空白码点，至少1句达到40个，句长总体标准差除以均值至少0.35；主旨起点不晚于全文非空白码点的20%，并位于前2句。',
 'mixed_late':'混合节奏；至少1句不超过18个非空白码点，至少1句达到40个，句长总体标准差除以均值至少0.35；主旨起点不早于全文非空白码点的70%，并位于最后2句。'}
# Sentence-ending punctuation is excluded from sentence lengths, but included in
# non-whitespace document positions. The final fragment is a sentence if nonempty.
plans=[];counts=collections.Counter()
for line in (ROOT/'private/content_plans.seed.txt').read_text().splitlines():
    genre,title,main,*facts=line.split('|');assert genre in GENRES and len(facts)==6
    i=counts[genre];counts[genre]+=1
    plans.append({'family_id':f'F{GENRES.index(genre)+1}{i+1:02}','genre':genre,'title_for_planning_only':title,'mainpoint_exact':main,'facts':[{'fact_id':f'P{k+1}','text':f} for k,f in enumerate(facts)],'fictional':True,'independence_unit':'one_specific_content_plan_all_realizations_and_paraphrases','family_index_within_genre':i})
assert all(counts[g]==12 for g in GENRES)
# Within each genre and parity, seeded assignment 4 train,1 dev,1 test. This
# preserves 8/2/2 and exact template balance by split, pass and condition.
for g in GENRES:
    for parity in range(2):
        group=sorted([p for p in plans if p['genre']==g and p['family_index_within_genre']%2==parity],key=lambda p:sha(('controlled-family-split/v1\0'+p['family_id']).encode()))
        for n,p in enumerate(group):p['partition']='train' if n<4 else 'dev' if n==4 else 'test'
jobs=[]
for p in plans:
    for c,target in enumerate(CONDITIONS):
        for authoring_pass in (0,1):
            template='AB'[(p['family_index_within_genre']+c+authoring_pass)%2]
            job_id=f"{p['family_id']}-{target}-P{authoring_pass}"
            prompt={'instruction':TEMPLATES[template]['instruction'],'target_instruction':TARGETS[target], 'content_plan':{k:p[k] for k in ('genre','mainpoint_exact','facts','fictional')}}
            jobs.append({'job_id':job_id,'family_id':p['family_id'],'partition':p['partition'],'genre':p['genre'],'nominal_condition':target,'authoring_pass':authoring_pass,'template':template,'review_id':sha(('blind-review-id/v1\0'+job_id).encode())[:24],'prompt':prompt,'prompt_sha256':sha(canonical(prompt))})
jobs.sort(key=lambda j:(j['authoring_pass'],sha(('controlled-authoring-order/v1\0'+j['job_id']).encode())))
for i,j in enumerate(jobs):j['global_order']=i
assert len(jobs)==384 and len({j['job_id'] for j in jobs})==384
for p in plans:
    for target in CONDITIONS:
        js=[j for j in jobs if j['family_id']==p['family_id'] and j['nominal_condition']==target]
        assert {j['template'] for j in js}=={'A','B'} and {j['authoring_pass'] for j in js}=={0,1}
for genre in GENRES:
    for split in ('train','dev','test'):
        for pa in (0,1):
            for c in CONDITIONS:
                n=collections.Counter(j['template'] for j in jobs if (j['genre'],j['partition'],j['authoring_pass'],j['nominal_condition'])==(genre,split,pa,c));assert n['A']==n['B']
plan_sha=put(ROOT/'private/family-manifest.json',plans)
job_sha=put(ROOT/'private/authoring-jobs.json',jobs)
put(ROOT/'public/prompt-templates.json',{'templates':TEMPLATES,'targets':TARGETS})
put(ROOT/'public/counterbalance.aggregate.json',{'families':48,'genres':{g:12 for g in GENRES},'family_partitions':dict(collections.Counter(p['partition'] for p in plans)),'realization_partitions':dict(collections.Counter(j['partition'] for j in jobs)),'conditions':{c:96 for c in CONDITIONS},'templates':{'A':192,'B':192},'passes':{'0':192,'1':192},'all_family_condition_cells_have_both_templates_and_passes':True,'each_genre_split_pass_condition_has_equal_templates':True,'planned_realizations':384,'authored_realizations':0})
put(ROOT/'public/generator-provenance.contract.json',{'provider':'OpenAI','interface':'native_assistant_authoring','actual_model_identifier':None,'actual_model_revision':None,'sampling_seed':None,'temperature':None,'unknown_fields_reason':'not exposed by this runtime; never infer from requested model name','per_attempt_required':['job_id','prompt_sha256','authoring_pass','template','author_context_id','started_utc','finished_utc','provider','actual_model_identifier','actual_model_revision','sampling_seed','temperature','available_requested_configuration','raw_envelope_sha256','parsed_text_sha256_or_null','status','failure_reason_or_null'],'reproducibility_claim':'exact realized text and prompt replay/audit only; not provider-level regeneration equivalence','separate_context_per_pass':True,'other_pass_realizations_visible_to_author':False,'runtime_for_manifest_validation':{'python':platform.python_version(),'unicode':unicodedata.unidata_version}})
put(ROOT/'public/authoring.contract.json',{'schema':'controlled-structural-authoring/v2','action_requested':'CONTROLLED_AUTHORING_384_GO','status':'frozen_proposal_requires_root_GO','allowed_stage':'exact384_assistant_authored_controlled_drafts_only','family_manifest_sha256':plan_sha,'job_manifest_sha256':job_sha,'plan_family_count':48,'genre_count':4,'nominal_conditions':CONDITIONS,'authoring_passes':2,'templates':2,'draft_attempts':384,'per_job_text_attempts':1,'preserved_v1_manifest_sha256':'3120a687bb6d3f7cbb75dba55aa86f54d2c20101d0d50d5b38337f1def4c17fa','pre_generation_amendment':'120–400 CP; six-fact plans93–120 CP plus main claim <=12; avoid unsupported expansion; root approved before any prose generation','text_codepoint_bounds':[120,400],'per_job_raw_envelope_byte_limit':16384,'local_artifact_byte_cap':33554432,'artifact_scope':'all files and transient copies under style-controlled-authoring-v01 and style-controlled-authoring-v02 including sanitized exports, authoring outputs and later blind-label derivatives; provider transcripts are not measured by local disk accounting','max_parallel_author_contexts':2,'failed_generation':'retain exact raw envelope and failure; no replacement, polishing or new prose attempt in v2; transport uncertainty is failure, not blind retry','declared_inference_candidates':0,'model_fit_authorized':False,'natural_source_reads_authorized':False,'owner_text_authorized':False,'network_downloads_or_external_API_cost_authorized':False,'counts_towards_1280_natural_works':False,'generic_stage_complete':False,'test_family_count':8,'test_claim_limit':'exploratory family-level feasibility only; not semantic guarantee or stage1 acceptance','independent_review_required_before_GO':True})
print(json.dumps({'families':len(plans),'jobs':len(jobs),'family_manifest_sha256':plan_sha,'jobs_sha256':job_sha},indent=2))
