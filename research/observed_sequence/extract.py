"""Manifest-only offline extraction. No training, transforms, test extraction or network.

Explicit stages: gate (fixed first8training records, uncached prefix audit), then
train-dev (reuse the passed gate records and extract remaining approved records).
The caller must have current root approval; passing hashes is integrity evidence,
not a substitute for user authorization or linguistic validity.
"""
from __future__ import annotations
import argparse,collections,dataclasses,hashlib,json,os,pathlib,resource,signal,socket,sys,time
from .contracts import Provenance,require,digest
from .prepare import pair_ledger,closed_boundary
from .producer import SentenceLocalProducer
from style_compiler.segmentation import segment

MODULES=['research/observed_sequence/contracts.py','research/observed_sequence/prepare.py','research/observed_sequence/producer.py','research/observed_sequence/extract.py','research/linguistic/adapter.py','research/linguistic/contracts.py','research/linguistic/schema.py','research/linguistic/stanza_local.py','research/linguistic/unicode_scripts.py','src/style_compiler/segmentation.py']
SEED='style-observed-sequence-wikiconv-2017-v1-20261001'

def sha(data):return hashlib.sha256(data).hexdigest()
def rank(r):return (sha((SEED+'|prefix-audit|'+r['id']).encode()),r['id'])
def block_network(*args,**kwargs):raise PermissionError('observed_extraction_network_disabled')
def jsonbytes(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()

class Budget:
 def __init__(self,out):self.start=time.monotonic();self.out=out
 def check(self):
  require(time.monotonic()-self.start<=5400,'extraction_wall_cap')
  require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<=3*1024**2,'extraction_rss_cap')
  require(sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())<=250000000,'extraction_disk_cap')
 def write(self,path,obj):
  self.check();b=jsonbytes(obj)
  require(sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())+len(b)<=250000000,'extraction_disk_cap')
  with path.open('xb') as f:f.write(b)
  require(sha(path.read_bytes())==sha(b),'output_readback_hash')
  return sha(b)

class GuardedBackend:
 def __init__(self,backend,budget):self.original=backend;self.profile=backend.profile;self.budget=budget
 def pipeline(self,text):self.budget.check();value=self.original.pipeline(text);self.budget.check();return value


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--stage',choices=['gate','train-dev'],required=True)
 for name in ['repo','data','manifest','plan','models','out']:ap.add_argument('--'+name,type=pathlib.Path,required=True)
 ap.add_argument('--manifest-sha256',required=True);ap.add_argument('--plan-sha256',required=True)
 a=ap.parse_args();repo=a.repo.resolve();out=a.out.resolve();require(repo!=out and repo not in out.parents,'private_output_inside_repo');out.mkdir(parents=True,exist_ok=True)
 budget=Budget(out);socket.socket.connect=block_network;socket.socket.connect_ex=block_network;socket.getaddrinfo=block_network
 def timeout(*args):raise RuntimeError('extraction_wall_cap')
 signal.signal(signal.SIGALRM,timeout);signal.alarm(5400)
 mb=a.manifest.read_bytes();pb=a.plan.read_bytes();require(sha(mb)==a.manifest_sha256 and sha(pb)==a.plan_sha256,'frozen_plan_or_manifest_hash')
 manifest=json.loads(mb);plan=json.loads(pb);require(plan['selected_manifest_sha256']==sha(mb),'plan_manifest_join')
 code={p:sha((repo/p).read_bytes()) for p in MODULES}
 selected=manifest['selected_records'];require(len(selected)==192,'selection_size')
 train=sorted((r for r in selected if r['partition']=='train'),key=rank);gate=train[:8]
 if a.stage=='gate':chosen=gate;gate_receipt=None
 else:
  gate_receipt=json.loads((out/'gate-receipt.private.json').read_text())
  require(gate_receipt['status']=='pass' and gate_receipt['manifest_sha256']==sha(mb) and gate_receipt['plan_sha256']==sha(pb) and gate_receipt['module_hashes']==code,'gate_not_passed_or_code_changed')
  chosen=[r for r in selected if r['partition'] in {'train','development'}]
 require(all(r['partition']!='test' for r in chosen),'sealed_test')
 chosen_map={r['rownum']:r for r in chosen};sources={}
 sys.path.insert(0,str(repo/'research/audits'))
 from wikiconv_annual_census import Archive,jsonl_records,views
 z=Archive(a.data/'wikiconv-chinese-2017/full.corpus.zip',manifest['archive_sha256'],80074478,871024181)
 for n,offset,r in jsonl_records(z.chunks('utterances.jsonl')):
  if n%1000==0:budget.check()
  if n not in chosen_map:continue
  e=chosen_map[n];v=next(views(r));require(v['id']==e['id'] and v['conversation']==e['conversation_id'] and offset==e['byte_offset'] and digest(v['text'])==e['source_sha256'],'manifest_source_join')
  require([[x.start,x.end] for x in segment(v['text'])[1]]==e['source_unit_spans'],'manifest_span_join');sources[e['id']]=v['text']
 require(len(sources)==len(chosen),'missing_source_record');z.close()
 from research.linguistic.stanza_local import LocalStanza
 parser=LocalStanza(a.models,threads=2);producer=SentenceLocalProducer(GuardedBackend(parser,budget));budget.check()
 if gate_receipt:require(gate_receipt['parser_profile_sha256']==producer.parser_profile_sha256 and gate_receipt['measurement_schema_sha256']==producer.measurement_schema_sha256,'gate_profile_changed')
 receipts=[];counts=collections.Counter();partition_counts=collections.defaultdict(collections.Counter);checks=0;records_dir=out/'records';records_dir.mkdir(exist_ok=True)
 gate_ids={r['id'] for r in gate}
 for entry in chosen:
  budget.check();key=sha(entry['id'].encode());path=records_dir/(key+'.private.json')
  if a.stage=='train-dev' and entry['id'] in gate_ids:
   old=json.loads(path.read_text());oldreceipt=next(r for r in gate_receipt['record_receipts'] if r['file']==path.name)
   require(sha(path.read_bytes())==oldreceipt['sha256'],'gate_cache_hash');receipts.append(oldreceipt);stats=old['summary']
  else:
   text=sources[entry['id']];prov=Provenance(manifest['archive_sha256'],entry['source_sha256'],entry['id'],entry['component_id'],entry['partition'])
   record=producer.record(text,prov);spans=segment(text)[1][:len(record.units)]
   cached=tuple(producer._sentence(text,prov.source_sha256,s,use_cache=True) for s in spans)
   ledger=pair_ledger(record);audit=[]
   if a.stage=='gate':
    for target in range(4,len(record.units)):
     if not closed_boundary(text,target):continue
     fresh,units=producer.audit_prefix(text,prov,spans[target].start)
     require(fresh==cached[:target],'strict_prefix_cached_token_pos_head_mismatch')
     require(units==record.units[:target],'strict_prefix_cached_features_mismatch')
     checks+=1;audit.append({'target_index':target,'input_cutoff':spans[target].start,'parsed': [dataclasses.asdict(x) for x in fresh],'units':[dataclasses.asdict(x) for x in units],'tokens_pos_heads_features_equal':True})
   stats={'partition':entry['partition'],'units':len(record.units),'original_pairs':len(ledger),'eligible_pairs':sum(x.eligible for x in ledger),'records_with_eligible_pairs':int(any(x.eligible for x in ledger)),'unit_parse_failures':sum(u.status=='failed' for u in record.units),'pair_missing_reasons':dict(collections.Counter(x.missing_reason for x in ledger if not x.eligible))}
   payload={'manifest_entry':entry,'record':dataclasses.asdict(record),'cached_parses':[dataclasses.asdict(x) for x in cached],'pair_ledger':[dataclasses.asdict(x) for x in ledger],'strict_prefix_uncached_audit':audit,'summary':stats}
   h=budget.write(path,payload);receipts.append({'file':path.name,'sha256':h,'partition':entry['partition'],'summary':stats})
  counts.update({k:stats[k] for k in ['units','original_pairs','eligible_pairs','records_with_eligible_pairs','unit_parse_failures']});partition_counts[entry['partition']].update({k:stats[k] for k in ['units','original_pairs','eligible_pairs','records_with_eligible_pairs','unit_parse_failures']});partition_counts[entry['partition']]['records']+=1
 require(code=={p:sha((repo/p).read_bytes()) for p in MODULES},'code_changed_during_extraction');budget.check()
 result={'status':'pass','stage':a.stage,'manifest_sha256':sha(mb),'plan_sha256':sha(pb),'module_hashes':code,'parser_profile_sha256':producer.parser_profile_sha256,'measurement_schema_sha256':producer.measurement_schema_sha256,'parser_profile':dataclasses.asdict(parser.profile),'selected_records':len(chosen),'partition_counts':{p:dict(v) for p,v in partition_counts.items()},'counts':dict(counts),'strict_prefix_checks':checks,'gate_selection_algorithm':"first8TRAIN by SHA256(seed+'|prefix-audit|'+record_id)",'parser_pipeline_calls_this_stage':producer.parser_calls,'record_receipts':receipts,'resources':{'wall_seconds':round(time.monotonic()-budget.start,3),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'private_output_bytes_before_receipt':sum(p.stat().st_size for p in out.rglob('*') if p.is_file()),'new_download_bytes':0,'cpu_threads':2},'network_blocked':True,'test_records_extracted':0,'comparison_eligible_promoted':False,'author_or_human_truth_admission':False,'transform_fit':False,'model_fit':False}
 name='gate-receipt.private.json' if a.stage=='gate' else 'train-dev-receipt.private.json';h=budget.write(out/name,result)
 public={k:result[k] for k in ['status','stage','manifest_sha256','plan_sha256','module_hashes','parser_profile_sha256','measurement_schema_sha256','selected_records','partition_counts','counts','strict_prefix_checks','gate_selection_algorithm','parser_pipeline_calls_this_stage','resources','network_blocked','test_records_extracted','comparison_eligible_promoted','author_or_human_truth_admission','transform_fit','model_fit']};public['private_receipt_sha256']=h;budget.write(out/(name.replace('.private','.aggregate')),public);print(json.dumps(public,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
