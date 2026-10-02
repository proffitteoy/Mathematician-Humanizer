#!/usr/bin/env python3
"""Local-only, resumable frozen M4 TRAIN/DEV H+ChatGPT measurement. No fitting."""
from __future__ import annotations
import argparse, collections, dataclasses, gzip, hashlib, importlib.metadata, json, os
from pathlib import Path
import resource, socket, sys, time
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent
REST=BASE/'chinese-linguistic-restoration-20261002'
COHORT=BASE/'m4_chinese_paired_20261002'
PRIVATE=ROOT/'private'; PUBLIC=ROOT/'public'
sys.path[:0]=[str(REST/'repo/src'),str(REST/'repo')]
from research.surface.adapter import SourceObservation, SourceView, Interval, make_projection
from research.linguistic.adapter import measure, lexical, row
from research.linguistic.schema import CHANNEL_IDS, SENSORS, schema_document
from style_compiler.segmentation import segment, SEGMENTER_VERSION
VERSION='m4-zh-train-dev-extraction/1.0.0'
SEED='m4-zh-71-throughput-20-train-families-v1-2026-10-02'
HISTORY=('zh:lexical.content_overlap','zh:lexical.trigram_reuse','zh:syntax.initial_pos_reuse')
ARMS=('human','chatgpt')
EXPECTED_COHORT='caab83530f309622cbafe95b92e648fc59936435b170f7ef3f38abf23cf3a1ca'
EXPECTED_RAW='cc2fb0d6c2e63f507717835cd20f992a513d098af6259ce888552ddeca79cfee'
PROJECTION_PROFILE='m4-frozen-whole-unchanged-answer/provisional-identity-verified/v1'

def digest(b): return hashlib.sha256(b if isinstance(b,bytes) else b.encode('utf8')).hexdigest()
def serial(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
def write_json(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp'); temp.write_bytes(serial(x)+b'\n'); os.replace(temp,p)
def append_event(x):
    with (PRIVATE/'execution_ledger.jsonl').open('ab') as f:
        f.write(serial(x)+b'\n'); f.flush(); os.fsync(f.fileno())
def deny(*args,**kwargs): raise RuntimeError('network_connections_disabled_for_local_measurement')
def offline():
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
    socket.socket.connect=deny; socket.socket.connect_ex=deny; socket.create_connection=deny

def load_rows():
    data=(COHORT/'private/cohort_identity_views.jsonl').read_bytes()
    assert digest(data)==EXPECTED_COHORT,'frozen_cohort_hash_mismatch'
    rows=[json.loads(line) for line in data.splitlines()]
    rows=[r for r in rows if r['split'] in ('train','dev')]
    assert collections.Counter(r['split'] for r in rows)=={'train':1816,'dev':591}
    assert all(r['fit_eligible_arms']==list(ARMS) for r in rows)
    return sorted(rows,key=lambda r:(r['split']!='train',r['pair_id']))

def select_pilot(rows):
    families=collections.defaultdict(list)
    for r in rows:
        if r['split']=='train': families[r['question_family_id']].append(r)
    chosen=sorted(families,key=lambda f:digest(SEED+'\0'+f))[:20]
    return [min(families[f],key=lambda r:r['pair_id']) for f in chosen]

def total_support(rows):
    return {'pairs':len(rows),'arms':len(rows)*2,
            'codepoints':sum(r['arms'][a]['chars'] or 0 for r in rows for a in ARMS),
            'frozen_sentence_proxy_units':sum(r['arms'][a]['sentences'] or 0 for r in rows for a in ARMS)}

def protocol():
    return {'version':VERSION,'seed':SEED,'cohort_manifest_sha256':EXPECTED_COHORT,
      'raw_file_sha256_from_frozen_receipt':EXPECTED_RAW,
      'scope':{'splits':['train','dev'],'arms':list(ARMS),'paired_records':2407,'arm_measurements':4814},
      'pilot_rule':'20 smallest SHA256(seed + NUL + question_family_id) TRAIN families; smallest pair_id in each; both arms; no replacement',
      'raw_access':'seek/read exact frozen CHATGPT row offsets only; do not read davinci file or test raw bodies; no whole raw file decode',
      'projection_annotation_status':'provisional','projection_profile':PROJECTION_PROFILE,
      'source_producer':'existing71-channel instruments, unmodified; candidate_unvalidated; no fitting',
      'channel_ids':list(CHANNEL_IDS),'history_channel_ids_audit_only':list(HISTORY),
      'information_mode':'supplied_complete_unit_annotation_sequence_not_certified_live_prefix',
      'paragraphs':'Operational physical-line and frozen blank-line blocks retained; original writer paragraphs unknown for Web',
      'failure_rule':'preserve original typed null/denominator/opportunity/status; failures logged; no truncation, substitution or result-driven replacement',
      'cache':'per-arm gzip full bundle + exact parsed annotations, structural audit and cohort grouping; atomic save plus SHA256 ledger; verify on recovery',
      'budgets':{'cpu_affinity_cores':2,'tree_rss_bytes':2*1024**3,'new_derived_disk_bytes':1024**3,'aggregate_wall_seconds':7200},
      'go_rule':'After40: max(per-arm, per-codepoint, per-frozen-proxy-unit linear wall projections)*1.25 + model-load time <=7200; disk same conservative scaling <=1GiB; actual RSS <=2GiB',
      'release_boundary':'Only code/protocol and aggregate receipts public; per-arm data, parses, locators, text hashes stay local/private',
      'model_files':'Existing verify_models pins; unchanged models and runtime; no installs/downloads/API/remote writes',
      'strict_prefix_causal_claim':False,'full_per_sample_upload_authorized':False}

def predeclare():
    p=protocol(); pp=PUBLIC/'extraction_protocol.json'
    if pp.exists(): assert json.loads(pp.read_bytes())==p,'protocol_changed_after_predeclaration'
    else: write_json(pp,p)
    rows=load_rows(); pilot=select_pilot(rows)
    plan={'protocol_sha256':digest(serial(p)),'pilot_pairs':[r['pair_id'] for r in pilot],
      'pilot_families':[r['question_family_id'] for r in pilot],
      'pilot_support':total_support(pilot),'full_support':total_support(rows),
      'pilot_selected_before_any_measurement':True}
    if (PRIVATE/'pilot_plan.json').exists(): assert json.loads((PRIVATE/'pilot_plan.json').read_bytes())==plan
    else: write_json(PRIVATE/'pilot_plan.json',plan)
    write_json(PUBLIC/'predeclaration_receipt.json',{'protocol_sha256':plan['protocol_sha256'],
      'pilot_plan_sha256':digest(serial(plan)),'pilot_support':plan['pilot_support'],'full_support':plan['full_support'],
      'selected_before_any_measurement':True,'test_and_davinci_bodies_read':0})
    return rows,pilot,plan

def read_approved_row(stream,r):
    assert r['split'] in ('train','dev') and r['fit_eligible_arms']==list(ARMS),'unauthorized_row'
    loc=r['raw_rows']['chatgpt']; assert loc['file']=='qazh_chatgpt.jsonl'
    stream.seek(loc['offset_bytes']); data=stream.read(loc['length_bytes'])
    assert len(data)==loc['length_bytes'],'short_raw_row'
    raw=json.loads(data.decode('utf8'))
    assert raw['model']=='chatgpt' and raw['source']==r['source'] and raw['source_ID']==r['source_ID']
    family=json.dumps([raw['source'],type(raw['source_ID']).__name__,raw['source_ID']],ensure_ascii=False,separators=(',',':'))
    assert family==r['question_family_id']
    assert digest(json.dumps([family,raw['prompt'],raw['human_text']],ensure_ascii=False,separators=(',',':')))==r['pair_id']
    assert digest(raw['prompt'])==r['prompt_sha256']
    for arm,field in [('human','human_text'),('chatgpt','machine_text')]:
        text=raw[field]; m=r['arms'][arm]
        assert (digest(text) if isinstance(text,str) else None)==m['original_text_sha256']
        assert (len(text) if isinstance(text,str) else None)==m['chars']
    return raw,{'row_bytes_sha256':digest(data),'offset_bytes':loc['offset_bytes'],'length_bytes':len(data),'line':loc['line']}

def cache_path(r,arm): return PRIVATE/'cache'/f"{r['pair_id']}.{arm}.json.gz"
def audit_identity(r,arm):
    return {'pair_id':r['pair_id'],'arm':arm,'split':r['split'],
        'question_family_id':r['question_family_id'],'component_id':r['component_id'],
        'source':r['source'],'source_ID':r['source_ID'],'inference_cluster':r['inference_cluster'],
        'question_family_answer_count':r['question_family_answer_count'],
        'equal_question_family_answer_weight':r['equal_question_family_answer_weight'],
        'authorship_status':r['authorship_status'],'source_support':r['arms'][arm]}

def verify_cache(p,r,arm,events):
    b=p.read_bytes(); h=digest(b); old=events.get(p.name)
    assert old and old['cache_sha256']==h,'cache_missing_or_mismatched_ledger'
    x=json.loads(gzip.decompress(b))
    assert x['cohort']==audit_identity(r,arm) and x['version']==VERSION
    assert x['protocol_sha256']==digest(serial(protocol()))
    assert x['history_channel_ids_audit_only']==list(HISTORY)
    return old

def extract_arm(r,arm,text,rawloc,parser,protocol_hash):
    start=time.monotonic(); cpu=time.process_time()
    x={'version':VERSION,'protocol_sha256':protocol_hash,'cohort':audit_identity(r,arm),
       'raw_access_audit':rawloc,'history_channel_ids_audit_only':list(HISTORY),
       'information_mode':'supplied_complete_unit_annotation_sequence_not_certified_live_prefix',
       'discourse_graph':{'value':None,'missing_reason':'no_validated_M4_producer'},
       'original_writer_paragraph_view':{'value':None,'missing_reason':'original_writer_layout_unsupported_unknown'} if r['source']=='web' else {'status':'only_frozen_blank_line_support_proxy_not_rhetorical_gold'},
       'bundle':None,'parsed_annotation':None,'source_failure':None,'structural_units':[]}
    p=None; obs=None
    if not isinstance(text,str) or not text.strip():
        failure='source_'+r['arms'][arm]['status']; x['source_failure']={'reason':failure,'scope':'whole_source','exception_class':None}
    else:
        loc=r['raw_rows']['chatgpt']
        sv=SourceView(EXPECTED_RAW,'qazh_chatgpt.jsonl',loc['line']-1,loc['offset_bytes'],
          'frozen-jsonl-byte-offset/1.0.0',0 if arm=='human' else 1,
          '/human_text' if arm=='human' else '/machine_text',arm,
          r['arms'][arm]['original_text_sha256'],len(text))
        obs=SourceObservation(sv,text)
        projection=make_projection(sv,(Interval(0,len(text)),),annotation_profile=PROJECTION_PROFILE,annotation_status='provisional')
        blocks,units=segment(text)
        x['operational_segmenter']=SEGMENTER_VERSION
        x['operational_physical_line_spans']=[dataclasses.asdict(b) for b in blocks]
        for u in units:
            frozen_blocks=r['arms'][arm]['block_spans']
            x['structural_units'].append({'source_sentence_index':u.index,'source_span':[u.start,u.end],
              'structure.source_sentence_span_codepoints':u.end-u.start,'structure.content_codepoints':u.content_chars,
              'structure.lexical_token_count':None,'lexical_token_count_status':'unavailable',
              'lexical_token_count_missing_reason':None,'operational_physical_line_index':u.paragraph_index,
              'frozen_blank_line_block_memberships':[i for i,(a,b) in enumerate(frozen_blocks) if a<=u.start and u.end<=b],
              'frozen_blank_line_block_overlaps':[i for i,(a,b) in enumerate(frozen_blocks) if a<u.end and u.start<b]})
        try:
            p=parser.parse(obs)
            x['bundle']=measure(obs,projection,p); x['parsed_annotation']=dataclasses.asdict(p)
            assert len(x['bundle']['target']['global_measurements'])==71
            assert list(x['bundle']['target']['global_vector']['channel_ids'])==list(CHANNEL_IDS)
            assert x['bundle']['measurement_status']=='candidate_unvalidated'
            assert not x['bundle']['empirical_model_admitted'] and not x['bundle']['learned_contract_compatible']
            for unit,s in zip(x['structural_units'],p.sentences):
                assert unit['source_sentence_index']==s.source_sentence_index
                unit['structure.lexical_token_count']=sum(lexical(t) for t in s.tokens) if s.status!='failed' else None
                unit['lexical_token_count_status']='observed' if s.status!='failed' else 'unavailable'
                unit['lexical_token_count_missing_reason']=s.reason if s.status=='failed' else None
                unit['parse_status']=s.status; unit['parse_reason']=s.reason
            x['source_view']=dataclasses.asdict(sv);x['projection']=dataclasses.asdict(projection)
        except (ValueError,RuntimeError,IndexError,TypeError) as e:
            known={'source_resource_limit','sentence_count_resource_limit','total_token_resource_limit'}
            reason=str(e) if str(e) in known else 'source_contract_or_measurement_failure'
            x['source_failure']={'reason':reason,'scope':'whole_source','exception_class':type(e).__name__}
    if x['source_failure']:
        reason=x['source_failure']['reason']
        x['failure_global_measurements']={s.id:row(opportunities=None,reason=reason)|{'opportunity_type':s.opportunity} for s in SENSORS}
        for unit in x['structural_units']:unit['lexical_token_count_missing_reason']=reason
    x['timing']={'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu}
    return x

def summarize(items,phase,load_seconds,wall_seconds):
    status=collections.Counter(); errors=collections.Counter(); local=0; global_available=collections.Counter(); profiles=set()
    for x in items:
        if x['source_failure']: status['source_failure']+=1;errors[x['source_failure']['reason']]+=1
        else:
            b=x['bundle']; failures=b['target']['coverage']['complete_parse_failures']
            status['complete_parse_failure' if failures else 'measured_no_parse_failure']+=1
            for e in b['parse_audit']['errors']:errors[e['reason']]+=1
            local+=len(b['target']['sequence']); profiles.add(b['identity']['profile_sha256'])
            for k,v in b['target']['global_measurements'].items():
                if v['value'] is not None:global_available[k]+=1
    return {'phase':phase,'arm_records':len(items),'record_statuses':dict(status),'sentence_error_reasons':dict(errors),
      'local_sequence_rows':local,'global_available_by_channel':dict(global_available),'measurement_profile_sha256':sorted(profiles),
      'model_load_seconds':load_seconds,'phase_wall_seconds':wall_seconds,
      'measurement_wall_seconds':sum(x['timing']['wall_seconds'] for x in items),
      'measurement_cpu_seconds':sum(x['timing']['cpu_seconds'] for x in items),
      'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
      'raw_test_bodies_read':0,'davinci_bodies_read':0,'candidate_unvalidated':True,
      'strict_prefix_causal_claim':False,'all_per_sample_data_private':True}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['predeclare','pilot','full']); a=ap.parse_args()
    offline(); rows,pilot,plan=predeclare()
    if a.phase=='predeclare':print(json.dumps(json.loads((PUBLIC/'predeclaration_receipt.json').read_bytes())),flush=True);return
    tests=json.loads((PUBLIC/'model_free_receipt.json').read_bytes()); assert tests['success'] and tests['wrapper_tests_success']
    if a.phase=='full':
        pilot_receipt=json.loads((PUBLIC/'pilot_receipt.json').read_bytes()); assert pilot_receipt['go_full_run'], 'pilot_cost_requires_authorization'
    assert importlib.metadata.version('torch')=='2.3.1+cpu' and importlib.metadata.version('numpy')=='1.26.4'
    assert len(os.sched_getaffinity(0))<=2,'two_cpu_affinity_required'
    begin=time.monotonic(); load=time.monotonic()
    from research.linguistic.stanza_local import LocalStanza
    parser=LocalStanza(REST/'models',threads=2); load=time.monotonic()-load
    write_json(PRIVATE/'parser_profile.json',dataclasses.asdict(parser.profile))
    events={}
    ledger=PRIVATE/'execution_ledger.jsonl'
    if ledger.exists():
        for line in ledger.read_bytes().splitlines():
            e=json.loads(line)
            if e['event']=='cache_committed':events[e['cache_file']]=e
    selected=pilot if a.phase=='pilot' else rows
    finished=[]; recovered=0; measured=0
    with (COHORT/'raw/qazh_chatgpt.jsonl').open('rb') as stream:
        for r in selected:
            raw=None; rawloc=None
            for arm in ARMS:
                p=cache_path(r,arm)
                if p.exists():
                    e=verify_cache(p,r,arm,events);recovered+=1
                else:
                    if raw is None:raw,rawloc=read_approved_row(stream,r)
                    append_event({'event':'measurement_started','phase':a.phase,'pair_id':r['pair_id'],'arm':arm,'split':r['split'],'raw_access':rawloc})
                    x=extract_arm(r,arm,raw['human_text' if arm=='human' else 'machine_text'],rawloc,parser,plan['protocol_sha256'])
                    payload=gzip.compress(serial(x),compresslevel=6,mtime=0);tmp=p.with_suffix('.tmp');tmp.write_bytes(payload);os.replace(tmp,p)
                    e={'event':'cache_committed','phase':a.phase,'cache_file':p.name,'cache_sha256':digest(payload),
                       'pair_id':r['pair_id'],'arm':arm,'split':r['split'],'bytes':len(payload),'timing':x['timing'],
                       'source_failure':x['source_failure'],'local_units':len(x['structural_units'])}
                    append_event(e); events[p.name]=e; measured+=1
                finished.append(p)
                if len(finished)%20==0:print(json.dumps({'phase':a.phase,'completed':len(finished),'total':len(selected)*2,'newly_measured':measured,'cache_reused':recovered,'wall_seconds':time.monotonic()-begin}),flush=True)
    # Read one cached record at a time; aggregate without retaining the whole corpus.
    # Pilot has40; full is streamed into a reducer below to stay bounded.
    items=(json.loads(gzip.decompress(p.read_bytes())) for p in finished)
    if a.phase=='pilot':
        items=list(items); result=summarize(items,a.phase,load,time.monotonic()-begin)
        ratios=[plan['full_support'][k]/max(plan['pilot_support'][k],1) for k in ('arms','codepoints','frozen_sentence_proxy_units')]
        scale=max(ratios);cache_bytes=sum(p.stat().st_size for p in finished)
        result.update({'projection_scale':scale,'projection_safety_factor':1.25,
          'projected_total_wall_seconds':load+result['measurement_wall_seconds']*scale*1.25,
          'pilot_cache_bytes':cache_bytes,'projected_derived_disk_bytes':cache_bytes*scale*1.25+10*1024**2})
        result['go_full_run']=result['projected_total_wall_seconds']<=7200 and result['projected_derived_disk_bytes']<=1024**3 and result['peak_rss_bytes']<=2*1024**3
    else:
        result=stream_aggregate(items,load,time.monotonic()-begin)
    result.update({'newly_measured':measured,'cache_reused':recovered,'derived_bytes':sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()),
       'protocol_sha256':plan['protocol_sha256'],'wrapper_sha256':digest(Path(__file__).read_bytes())})
    write_json(PUBLIC/(a.phase+'_receipt.json'),result)
    print(json.dumps(result),flush=True)

def stream_aggregate(items,load,wall):
    # Accumulate aggregate availability/status and support by split/arm/source.
    groups={}; n=0; profiles=set(); error=collections.Counter(); sources=collections.Counter();totalrows=0;totalcpu=totalwall=0
    for x in items:
        n+=1;c=x['cohort'];key='|'.join(c[k] for k in ('split','arm','source'))
        g=groups.setdefault(key,{'records':0,'families':set(),'components':set(),'equal_question_weight_sum':0.0,'source_failure':0,'with_parse_failure':0,'sequence_rows':0,'global_available':collections.Counter(),'local_available':collections.Counter(),'missing_reasons':collections.Counter(),'resource_failed_units':0,'global_positive_denominator_zero':collections.Counter()})
        g['records']+=1;g['families'].add(c['question_family_id']);g['components'].add(c['component_id']);g['equal_question_weight_sum']+=c['equal_question_family_answer_weight']
        totalcpu+=x['timing']['cpu_seconds'];totalwall+=x['timing']['wall_seconds']
        if x['source_failure']:g['source_failure']+=1;error[x['source_failure']['reason']]+=1;continue
        b=x['bundle'];profiles.add(b['identity']['profile_sha256']);g['with_parse_failure']+=bool(b['target']['coverage']['complete_parse_failures']);seq=b['target']['sequence'];g['sequence_rows']+=len(seq);totalrows+=len(seq)
        for e in b['parse_audit']['errors']:error[e['reason']]+=1
        for k,v in b['target']['global_measurements'].items():
            if v['value'] is not None:g['global_available'][k]+=1
            if v['value']==0 and (v['denominator'] or 0)>0:g['global_positive_denominator_zero'][k]+=1
        for u in seq:
            if u['parse_reason']=='resource_limit':g['resource_failed_units']+=1
            for k,v in u['measurements'].items():
                if v['value'] is not None:g['local_available'][k]+=1
                else:g['missing_reasons'][v['missing_reason']]+=1
    for g in groups.values():
        g['families']=len(g['families']);g['components']=len(g['components'])
        for key in ('global_available','local_available','global_positive_denominator_zero'):g[key]={k:g[key][k] for k in CHANNEL_IDS}
    return {'phase':'full','arm_records':n,'local_sequence_rows':totalrows,'groups':groups,'sentence_or_source_error_reasons':dict(error),
      'measurement_profile_sha256':sorted(profiles),'model_load_seconds':load,'phase_wall_seconds':wall,'measurement_wall_seconds':totalwall,'measurement_cpu_seconds':totalcpu,
      'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
      'raw_test_bodies_read':0,'davinci_bodies_read':0,'candidate_unvalidated':True,'strict_prefix_causal_claim':False,'all_per_sample_data_private':True}
if __name__=='__main__':main()
