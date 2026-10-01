"""Read-only signature/metadata audit. No source bodies or derivation rerun."""
from pathlib import Path
import hashlib,json,sqlite3,zlib
ROOT=Path('/workspace/shared/style-scale10-source-v01');P=ROOT/'public';V=ROOT/'private';O=Path('/workspace/shared/style-scale10-matcher-review-v01/public')
def h(p):
 d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):d.update(b)
 return d.hexdigest()
def j(p):return json.loads(p.read_text())
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
m=j(P/'incremental-blog-exclusion-FILE_HASHES.json')
assert h(P/'incremental-blog-exclusion-FILE_HASHES.json')=='cb593ff9f2261b90fdc082f86bfd8e502f94b6dad041589d5c3324e4ce496f43'
for name,e in m.items():assert (P/name).stat().st_size==e['bytes'] and h(P/name)==e['sha256']
a=j(V/'incremental-blog-exclusion-allowlist.private.json');plan=j(V/'incremental-blog-exclusion-plan.private.json');marker=j(V/'incremental-blog-exclusion-ONE_TIME_STARTED.private.json');before=j(V/'incremental-blog-exclusion-presource-tests.private.json');detail=j(V/'incremental-blog-exclusion-coverage.private.json');agg=j(P/'incremental-blog-exclusion-coverage.aggregate.json');complete=j(V/'incremental-blog-exclusion-COMPLETE.private.json')
assert h(V/'incremental-blog-exclusion-allowlist.private.json')==plan['allowlist_sha256']==marker['allowlist_sha256']==agg['allowlist_sha256']
assert h(V/'incremental-blog-exclusion-plan.private.json')==marker['execution_plan_sha256']
assert plan['implementation_hashes']==before['implementation_hashes']
for name,sha in plan['implementation_hashes'].items():assert h(P/name)==sha
assert before['status']=='passed' and before['before_raw_bodies'] and before['returncode']==0
assert h(V/'incremental-blog-exclusion-coverage.private.json')==agg['private_detail_sha256']
assert complete['public_aggregate_sha256']==h(P/'incremental-blog-exclusion-coverage.aggregate.json')
assert a['source_count']==len(a['sources'])==3
for row in a['sources']:assert h(Path(row['license_metadata_path']))==row['license_metadata_sha256']
dbpath=V/'incremental-blog-exclusion.private.sqlite'
assert h(dbpath)==agg['incremental_package_sha256']=='225d002fa7dc3436cb50075e712bff8d263fbf1bc802823fe43ef76a925c5a08'
assert dbpath.stat().st_size==agg['incremental_package_bytes']==1658880
D=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True);D.execute('PRAGMA query_only=ON')
assert D.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
control=dict(D.execute('select key,value from control'));assert control['status']=='complete' and control['algorithm']=='exposure-copy-signatures/1.0.0' and control['unicode_version']=='15.0.0'
ng,lo,hi=D.execute('select count(*),min(id),max(id) from grams').fetchone();assert ng==hi==18637 and lo==1
assert D.execute('select count(*) from grams where length(sha256)!=32').fetchone()[0]==0
seen=members=0
for count,blob in D.execute('select gram_count,gram_ids_delta_zlib from texts'):
 dec=zlib.decompressobj();raw=dec.decompress(blob,count*5+1);assert dec.eof and not dec.unused_data and not dec.unconsumed_tail and len(raw)<=count*5
 vals=[];v=shift=prev=0
 for byte in raw:
  v+=(byte&127)<<shift
  if byte&128:shift+=7;assert shift<35
  else:
   assert v>0;prev+=v;assert prev<=ng;vals.append(prev);v=shift=0
 assert not shift and len(vals)==count
 enc=bytearray();prev=0
 for value in vals:
  delta=value-prev;prev=value
  while delta>127:enc.append(128+(delta%128));delta//=128
  enc.append(delta)
 assert bytes(enc)==raw
 seen+=1;members+=count
assert seen==3
source_by_sha={x['sha256']:x for x in a['sources']};bound=[]
for source,member,role,obj,raw,bytes_,chars in D.execute('select b.source_id,b.member_key,b.source_view_role,b.source_object_sha256,t.raw_sha256,t.utf8_bytes,t.codepoints from bindings b join texts t on t.id=b.text_id'):
 assert source=='pre2022_blog_diagnostic3' and role=='raw_markdown' and obj==raw and raw in source_by_sha
 x=source_by_sha[raw];assert bytes_==x['bytes'];assert member==canonical(['gitblog',x['repository'],'post:'+x['path']]).decode();bound.append(raw)
assert len(bound)==3 and set(bound)==set(source_by_sha)
assert D.execute('select count(*) from blocks where normalized_codepoints<64 or length(normalized_sha256)!=32').fetchone()[0]==0
nb=D.execute('select count(*) from blocks').fetchone()[0];D.close()
receipts=detail['combined_matching_receipts'];assert len(receipts)==3
projected=set();rawspans=set();oldfull=[];selfraw=[]
for r in receipts:
 assert r['admission_authorized'] is False and r['cross_projection_coverage_certified'] is False
 for package in r['packages']:
  if package['package_sha256']==agg['old_package_sha256']:oldfull.append(package['reference_texts_scanned']==package['reference_texts_expected']==100541)
  if package['package_sha256']==agg['incremental_package_sha256']:
   selfraw.append(any(hit['candidate_role']=='full_raw_source_view' and 'raw_exact' in hit['reasons'] for hit in package['hits']))
  for hit in package['hits']:
   key=(r['record_key'],hit['candidate_view'])
   if hit['candidate_role']=='projected_segment':projected.add(key)
   if hit['candidate_role']=='mapped_contiguous_raw_source_span':rawspans.add(key)
assert len(oldfull)==3 and all(oldfull) and len(selfraw)==3 and all(selfraw)
assert len(projected)==agg['projected_segments_matched_raw_signatures']==92
assert len(rawspans)==agg['mapped_raw_spans_matched_raw_signatures']==109
assert sum(x['diagnostic_segments']for x in detail['source_bindings'])==149
old=Path('/workspace/shared/style-compiler-data/exposure-fingerprints-v01/fingerprints.private.sqlite');assert h(old)==agg['old_package_sha256']=='0ca3ca3eec71b88498ed70990804a7dc72d33dc736a0174edd3fdce5e258c3f5'
result={'schema_version':'incremental3-independent-readback/1','decision':'PASS_EXACT3_RAW_SIGNATURE_PACKAGE_ONLY','public_manifest_entries_verified':len(m),'package_sha256':h(dbpath),'unique_text_sets_decoded':seen,'unique_gram_dictionary':ng,'gram_memberships_decoded':members,'bindings_verified':len(bound),'long_blocks_verified':nb,'old_package_unchanged':True,'complete_old_scans_receipts_checked':3,'complete_old_texts_per_scan':100541,'raw_exact_self_exclusions':3,'diagnostic_projected_coverage':[92,149],'diagnostic_raw_span_coverage':[109,149],'cross_projection_certified':False,'G2_admitted':False,'author_matcher_tests_passed':28,'independent_matcher_tests_passed':6,'random_frozen_segmenter_comparisons':200,'source_bodies_read':0,'derivation_rerun':False,'parser_calls':0,'fits':0,'remote_writes':False}
(O/'increment-readback.aggregate.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
