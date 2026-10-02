#!/usr/bin/env python3
"""Final private-cache integrity and aggregate coverage; no raw corpus-body reads."""
import collections,gzip,importlib.metadata,json,math,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'public'))
import extract as ex
from research.surface.adapter import _digest
from research.linguistic.contracts import Token
from research.linguistic.stanza_local import verify_models

def pins():
 p=ex.REST/'public/RESTORATION_RECEIPT.json';b=p.read_bytes()
 assert ex.digest(b)=='2790ce37c80104c4c56fb41c2ee8f9082f9662b88313ce414efa54f96f5cb229'
 receipt=json.loads(b)
 for item in receipt['source_files']:
  b=(ex.REST/'repo'/item['path']).read_bytes();assert len(b)==item['bytes'] and ex.digest(b)==item['sha256']
 for name,expected in receipt['runtime_packages'].items():
  dist=importlib.metadata.distribution(name);assert dist.version==expected['version']
  assert ex.digest(dist.read_text('RECORD'))==expected['RECORD_text_normalized_sha256']
 model_profile=verify_models(ex.REST/'models')
 assert ex.digest((ROOT/'public/extract.py').read_bytes())==receipt['wrapper_sha256']
 assert ex.digest(ex.serial(ex.protocol()))==receipt['protocol_sha256']
 return {'source_files_checked':len(receipt['source_files']),'runtime_packages_checked':len(receipt['runtime_packages']),'model_profile_sha256':model_profile,'restoration_receipt_sha256':'2790ce37c80104c4c56fb41c2ee8f9082f9662b88313ce414efa54f96f5cb229','all_restored_pins_unchanged':True,'source_inventory_note':receipt['source_inventory_note'],'entire_historical_environment_byte_identity':False}

def verify():
 started=time.monotonic();pin=pins()
 full=json.loads((ex.PUBLIC/'full_receipt.json').read_bytes());assert full['arm_records']==4814
 rows=ex.load_rows();bypair={r['pair_id']:r for r in rows};events={};starts=[]
 family_counts=collections.Counter(r['question_family_id'] for r in rows)
 for record in rows:
  n=family_counts[record['question_family_id']]
  assert record['question_family_answer_count']==n and abs(record['equal_question_family_answer_weight']*n-1)<1e-12
  assert record['inference_cluster']==record['component_id']
 for line in (ex.PRIVATE/'execution_ledger.jsonl').read_bytes().splitlines():
  e=json.loads(line)
  if e['event']=='cache_committed':assert e['cache_file'] not in events;events[e['cache_file']]=e
  elif e['event']=='measurement_started':starts.append(e)
 assert len(events)==4814 and len({(e['pair_id'],e['arm']) for e in starts})==4814
 assert all(e['split'] in ('train','dev') and e['arm'] in ex.ARMS for e in starts)
 expected={ex.cache_path(r,a).name for r in rows for a in ex.ARMS}
 assert set(events)==expected=={p.name for p in (ex.PRIVATE/'cache').glob('*.json.gz')}
 restoration_file=ex.PRIVATE/'secondary_restoration_receipt.json'
 restored=json.loads(restoration_file.read_bytes()) if restoration_file.exists() else None
 restored_map=restored['file_mapping'] if restored else {}
 status=collections.Counter();reasons=collections.Counter();typed=collections.Counter();groups={};profiles=set()
 for name,e in sorted(events.items()):
  r=bypair[e['pair_id']];arm=e['arm'];p=ex.PRIVATE/'cache'/name;ex.verify_cache(p,r,arm,events)
  raw=gzip.decompress(p.read_bytes())
  if name in restored_map:assert ex.digest(raw)==restored_map[name]['original_json_sha256']
  x=json.loads(raw)
  assert e['local_units']==len(x['structural_units']),'cache_commit_unit_count_mismatch'
  for unit in x['structural_units']:
   width=unit['structure.source_sentence_span_codepoints'];span=unit['source_span']
   assert type(width)is int and math.isfinite(width) and width==span[1]-span[0] and width>0,'structural_span_width_mismatch'
  c=x['cohort'];w=c['equal_question_family_answer_weight'];key='|'.join(c[k] for k in ('split','arm','source'))
  g=groups.setdefault(key,{'records':0,'families':set(),'components':set(),'total_question_weight':0.0,'no_parse_failure_question_weight':0.0,'source_failures':0,'records_with_parse_failure':0,'sequence_units':0,'adjacent_transitions':0,'records_at_least2_units':0,'records_at_least8_units':0,'frozen_proxy_units':0,'operational_vs_frozen_count_mismatch_records':0,'global_available':collections.Counter(),'local_available':collections.Counter(),'global_available_weight':collections.Counter(),'local_available_document_fraction_weight':collections.Counter(),'sentence_failures':collections.Counter()})
  g['records']+=1;g['families'].add(c['question_family_id']);g['components'].add(c['component_id']);g['total_question_weight']+=w
  assert x['discourse_graph']=={'value':None,'missing_reason':'no_validated_M4_producer'}
  if c['source']=='web':assert x['original_writer_paragraph_view']=={'value':None,'missing_reason':'original_writer_layout_unsupported_unknown'}
  if x['source_failure']:
   status['source_failure']+=1;g['source_failures']+=1
   assert set(x['failure_global_measurements'])==set(ex.CHANNEL_IDS)
   assert all(v['value'] is None for v in x['failure_global_measurements'].values());continue
  b=x['bundle'];profiles.add(b['identity']['profile_sha256']);seq=b['target']['sequence'];pa=x['parsed_annotation']
  assert b['measurement_status']=='candidate_unvalidated' and b['reference_distribution'] is None
  assert not any(b[k] for k in ('personalization_admitted','empirical_model_admitted','learned_contract_compatible'))
  assert _digest(pa)==b['identity']['annotation_sha256']
  for key2 in ('source','projection','profile'):assert _digest(b[key2])==b['identity'][key2+'_sha256']
  assert len(seq)==len(x['structural_units'])==len(pa['sentences'])
  assert b['target']['coverage']['clipped_target_sentences']==0 and b['projection']['annotation_status']=='provisional'
  assert b['source']['json_pointer']==('/human_text' if arm=='human' else '/machine_text')
  assert b['source']['record_byte_offset']==r['raw_rows']['chatgpt']['offset_bytes']
  assert b['source']['text_sha256']==r['arms'][arm]['original_text_sha256'] and b['source']['text_codepoints']==r['arms'][arm]['chars']
  failures=b['target']['coverage']['complete_parse_failures']
  if failures:status['with_parse_failure']+=1;g['records_with_parse_failure']+=1
  else:status['without_parse_failure']+=1;g['no_parse_failure_question_weight']+=w
  g['sequence_units']+=len(seq);g['adjacent_transitions']+=max(len(seq)-1,0);g['records_at_least2_units']+=len(seq)>=2;g['records_at_least8_units']+=len(seq)>=8
  g['frozen_proxy_units']+=r['arms'][arm]['sentences'];g['operational_vs_frozen_count_mismatch_records']+=len(seq)!=r['arms'][arm]['sentences']
  for k,v in b['target']['global_measurements'].items():
   if v['value'] is not None:g['global_available'][k]+=1;g['global_available_weight'][k]+=w
  local=collections.Counter()
  for i,(s,u,pas) in enumerate(zip(seq,x['structural_units'],pa['sentences'])):
   assert s['source_sentence_index']==u['source_sentence_index']==pas['source_sentence_index']==i
   assert s['source_span']==u['source_span']==[pas['start'],pas['end']]
   assert u['structure.source_sentence_span_codepoints']==pas['end']-pas['start']
   assert u['parse_status']==s['parse_status']==pas['status'] and u['parse_reason']==s['parse_reason']==pas['reason']
   assert s['available_after_codepoint']==pas['end']
   if pas['status']=='failed':assert u['structure.lexical_token_count'] is None;reasons[pas['reason']]+=1;g['sentence_failures'][pas['reason']]+=1
   else:
    toks=[Token(t['local_id'],t['start'],t['end'],t['form'],t['upos'],t['head'],t['deprel'],tuple(tuple(v) for v in t['feats'])) for t in pas['tokens']]
    assert u['structure.lexical_token_count']==sum(ex.lexical(t) for t in toks)
   for k,v in s['measurements'].items():
    if v['value'] is not None:local[k]+=1;g['local_available'][k]+=1
  for k in ex.CHANNEL_IDS:g['local_available_document_fraction_weight'][k]+=w*(local[k]/len(seq) if seq else 0)
  for mm,vector in [(b['target']['global_measurements'],b['target']['global_vector'])]+[(s['measurements'],s['vector']) for s in seq]:
   assert vector['channel_ids']==list(ex.CHANNEL_IDS),'channel_vector_order_mismatch'
   assert vector['values']==[mm[k]['value'] for k in ex.CHANNEL_IDS],'channel_vector_value_mismatch'
   assert vector['opportunities']==[mm[k]['opportunities'] for k in ex.CHANNEL_IDS],'channel_vector_opportunity_mismatch'
   assert vector['missing_reasons']==[mm[k]['missing_reason'] for k in ex.CHANNEL_IDS],'channel_vector_missingness_mismatch'
   assert set(mm)==set(ex.CHANNEL_IDS)
   for k,v in mm.items():
    assert {'value','numerator','denominator','opportunities','missing_reason','status','comparison_eligible','uncertainty_interval','opportunity_type'}<=set(v)
    assert v['comparison_eligible'] is False and v['uncertainty_interval'] is None
    value=v['value'];typed[v['status']]+=1
    if value is None:assert v['status']=='unavailable' and v['missing_reason'] is not None
    else:assert math.isfinite(value) and v['missing_reason'] is None and v['status']==('zero_observed' if value==0 else 'observed')
 assert profiles=={'221323897ea20205d0801383537558b4411cb47eb945c2deac51e24ccb2549a3'}
 for g in groups.values():
  g['families']=len(g['families']);g['components']=len(g['components']);d=g['total_question_weight'];assert abs(d-g['families'])<1e-8
  g['no_parse_failure_equal_question_fraction']=g.pop('no_parse_failure_question_weight')/d
  for key2 in ('global_available','local_available'):g[key2]={k:g[key2][k] for k in ex.CHANNEL_IDS}
  for key2 in ('global_available_weight','local_available_document_fraction_weight'):
   g[key2.replace('_weight','_equal_question_fraction')]={k:g[key2][k]/d for k in ex.CHANNEL_IDS};del g[key2]
 result={'verified':True,'equal_question_family_weights_verified':True,'cache_commit_unit_counts_verified':True,'all_structural_span_widths_verified':True,'records':4814,'unique_cache_commits':len(events),'measurement_attempts':len(starts),'counts':dict(status),'sentence_failure_reasons':dict(reasons),'typed_measurement_status_counts':dict(typed),'groups':groups,'instrument_integrity':pin,'measurement_profile_sha256':list(profiles),'elapsed_seconds':time.monotonic()-started,'test_raw_bodies_read':0,'davinci_bodies_read':0,'no_fitting':True,'all_cache_hashes_and_annotation_fingerprints_verified':True,'secondary_restored_record_json_hashes_checked':len(restored_map),'weighted_coverage_definition':'Original1/answers_per_family weights; per-document local availability fraction then equal questions; zero-unit records retain0 availability in the denominator','private_artifacts_uploaded':False}
 ex.write_json(ex.PUBLIC/'verification_receipt.json',result)
 print(json.dumps({k:v for k,v in result.items() if k not in ('groups','instrument_integrity')}),flush=True)
if __name__=='__main__':
 os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
 if '--pins-only' in sys.argv:print(json.dumps(pins()))
 else:verify()
