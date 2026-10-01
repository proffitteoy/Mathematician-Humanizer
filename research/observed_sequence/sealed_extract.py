"""One-shot TEST-only source extraction helper, invoked only after root TEST GO.

No filesystem access or model initialization occurs at import. Source endpoint
labels are deliberately not computed here; prediction must precede diagnosis.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict
import hashlib,json,pathlib,sys
from .contracts import Provenance,require
from .prepare import pair_ledger
from .producer import SentenceLocalProducer
from .extract import GuardedBackend
from style_compiler.segmentation import segment


def sha(x):return hashlib.sha256(x).hexdigest()

def extract_sealed_test(*,repo,data,manifest,expected_manifest_sha256,model_directory,
                        expected_parser_profile_sha256,expected_schema_sha256,
                        private_out,budget,control_hook,root_test_go=False):
 """Return private records and metadata after an explicit root-authorized call.

 budget must enforce90min extraction,3GiB and250MB private output. Test data may
 not be used to retry thresholds, replace records or revise fitted parameters.
 """
 require(root_test_go is True,'one_time_root_test_go_required')
 repo=pathlib.Path(repo);data=pathlib.Path(data);private_out=pathlib.Path(private_out)
 raw=pathlib.Path(manifest).read_bytes();require(sha(raw)==expected_manifest_sha256,'test_manifest_hash')
 frame=json.loads(raw);chosen=[r for r in frame['selected_records'] if r['partition']=='test']
 require(len(chosen)==32 and sum(r['prefix_units_cap'] for r in chosen)==485,'fixed_test_frame')
 require(len({r['component_id'] for r in chosen})==32,'test_known_components')
 control_hook();budget.check()
 sys.path.insert(0,str(repo/'research/audits'))
 from wikiconv_annual_census import Archive,jsonl_records,views
 wanted={r['rownum']:r for r in chosen};sources={};speakers={}
 z=Archive(data/'wikiconv-chinese-2017/full.corpus.zip',frame['archive_sha256'],80074478,871024181)
 try:
  for n,offset,r in jsonl_records(z.chunks('utterances.jsonl')):
   if n%1000==0:control_hook();budget.check()
   if n not in wanted:continue
   e=wanted[n];v=next(views(r))
   require(v['id']==e['id'] and v['conversation']==e['conversation_id'] and offset==e['byte_offset'] and sha(v['text'].encode())==e['source_sha256'],'test_source_join')
   require([[s.start,s.end] for s in segment(v['text'])[1]]==e['source_unit_spans'],'test_source_spans')
   sources[e['id']]=v['text'];speakers[e['id']]=v['speaker']
 finally:z.close()
 require(len(sources)==32,'test_record_missing')
 from research.linguistic.stanza_local import LocalStanza
 parser=LocalStanza(model_directory,threads=2);producer=SentenceLocalProducer(GuardedBackend(parser,budget))
 require(producer.parser_profile_sha256==expected_parser_profile_sha256 and producer.measurement_schema_sha256==expected_schema_sha256,'frozen_test_profile')
 records=[];metadata=[];receipts=[];counts=Counter();record_dir=private_out/'records';record_dir.mkdir(exist_ok=True)
 for e in chosen:
  control_hook();budget.check();text=sources[e['id']]
  provenance=Provenance(frame['archive_sha256'],e['source_sha256'],e['id'],e['component_id'],'test')
  record=producer.record(text,provenance);ledger=pair_ledger(record);spans=segment(text)[1][:len(record.units)]
  cached=tuple(producer._sentence(text,provenance.source_sha256,s,use_cache=True) for s in spans)
  name=sha(e['id'].encode())+'.private.json'
  summary={'units':len(record.units),'candidate_pairs':len(ledger),'eligible_pairs':sum(x.eligible for x in ledger),'record_with_eligible_pairs':int(any(x.eligible for x in ledger)),'parse_failures':sum(u.status=='failed' for u in record.units),'pair_missing_reasons':dict(Counter(x.missing_reason for x in ledger if not x.eligible))}
  payload={'manifest_entry':e,'record':asdict(record),'cached_parses':[asdict(x) for x in cached],'pair_ledger':[asdict(x) for x in ledger],'declared_top_speaker_key':speakers[e['id']],'summary':summary}
  h=budget.write(record_dir/name,payload);receipts.append({'file':name,'sha256':h,'summary':summary})
  records.append(record);metadata.append({'record_id':e['id'],'component_id':e['component_id'],'speaker_key':speakers[e['id']],'page_type':e['page_type']})
  counts.update({k:summary[k] for k in ['units','candidate_pairs','eligible_pairs','record_with_eligible_pairs','parse_failures']})
 return tuple(records),tuple(metadata),{'status':'test_extraction_completed_for_frozen_evaluation','records':32,'counts':dict(counts),'record_receipts':receipts,'parser_profile_sha256':producer.parser_profile_sha256,'measurement_schema_sha256':producer.measurement_schema_sha256,'parser_calls':producer.parser_calls,'fit_performed':False,'endpoint_flags_computed':False}
