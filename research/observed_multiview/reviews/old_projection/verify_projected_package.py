"""Read-only post-completion signature/coverage audit. Never opens source bodies."""
from pathlib import Path
import collections,hashlib,json,sqlite3,zlib
ROOT=Path('/workspace/shared/style-scale10-source-v01');P=ROOT/'public';V=ROOT/'private';O=Path('/workspace/shared/style-scale10-old-projection-review-v01/public');OLD=Path('/workspace/shared/style-compiler-data/exposure-fingerprints-v01')
def h(p):
 x=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):x.update(b)
 return x.hexdigest()
def j(p):return json.loads(p.read_text())
def db(p):
 d=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True);d.execute('PRAGMA query_only=ON');return d
planpath=V/'old-projection-exclusion.plan.private.json';receiptpath=V/'old-projection-exclusion.receipt.private.json'
plan=j(planpath);r=j(receiptpath)
assert r['status']=='complete_projected_signature_package_pending_independent_review'
assert h(planpath)==r['plan_sha256']=='a7192181abb1aba7fd9ecb263abbbb5e3769f45ac32aaae852e3247beee0c1be'
assert r['old_expected_views']==324320 and r['old_missing_views']==0 and r['old_unique_texts_expected']==100541
assert r['G2_admitted'] is False and r['cross_projection_coverage_certified'] is False
frozen=P/'frozen-oldprojection-runtime'
for b in plan['code_bindings']:
 p=frozen/Path(b['path']).name
 assert p.stat().st_size==b['bytes'] and h(p)==b['sha256']
for key in ('focused_projection_review',):
 b=plan[key];assert h(Path(b['path']))==b['sha256']
assert h(OLD/'fingerprints.private.sqlite')==plan['old_package_sha256']=='0ca3ca3eec71b88498ed70990804a7dc72d33dc736a0174edd3fdce5e258c3f5'
assert h(OLD/'source-allowlist.private.json')==plan['old_allowlist_sha256']
assert h(V/'incremental-blog-exclusion-allowlist.private.json')==plan['new_three_allowlist_sha256']
for b in (r['new_package'],r['coverage_database']):
 assert Path(b['path']).stat().st_size==b['bytes'] and h(Path(b['path']))==b['sha256']
D=db(Path(r['new_package']['path']));C=db(Path(r['coverage_database']['path']));B=db(OLD/'fingerprints.private.sqlite');N=db(V/'incremental-blog-exclusion.private.sqlite')
for d in (D,C):assert d.execute('pragma integrity_check').fetchone()[0]=='ok'
control=dict(C.execute('select key,value from control'));assert control['status']=='complete' and control['old_package_sha256']==plan['old_package_sha256'] and control['plan_sha256']==h(planpath) and control['old_projection_signature_package_sha256']==r['new_package']['sha256']
assert dict(D.execute('select key,value from control'))['status']=='complete'
oldtexts={x[1]:x for x in B.execute('select id,raw_sha256,codepoints,normalized_sha256,normalized_codepoints from texts')}
new3texts={x[1]:x for x in N.execute('select id,raw_sha256,codepoints,normalized_sha256,normalized_codepoints from texts')}
projected={x[0]:x for x in D.execute('select id,raw_sha256,codepoints,normalized_sha256,normalized_codepoints from texts')}
oldbyid={x[0]:x for x in oldtexts.values()}
oldblocks=set(B.execute('select text_id,normalized_sha256,normalized_codepoints from blocks'))
coverage={x[0]:x for x in C.execute('select * from coverage')}
assert set(coverage)==set(oldtexts)|set(new3texts)
for raw,row in coverage.items():
 expected=oldtexts.get(raw,new3texts.get(raw));assert row[2]==expected[2]
 assert row[1]==(oldtexts[raw][0]if raw in oldtexts else None)
 assert len(row[3])==64 and row[4]>=0 and row[5]>=0 and row[6]in(0,1)
 if row[6]:assert row[4]==0
kinds=collections.Counter();perraw=collections.Counter();segments=set();indexes=collections.defaultdict(set);refs=collections.defaultdict(set)
for row in C.execute('select * from segments'):
 raw,index,rawsha,norm,nchars,kind,ref,lo,hi=row
 assert raw in coverage and index>=0 and (raw,index)not in segments and 0<=lo<hi<=coverage[raw][2]
 assert len(rawsha)==64 and len(norm)==32 and nchars>=0
 segments.add((raw,index));indexes[raw].add(index);perraw[raw]+=1;kinds[kind]+=1
 if kind=='old_normalized_full':assert oldbyid[ref][3:]==(norm,nchars)
 elif kind=='old_normalized_long_block':assert nchars>=64 and (ref,norm,nchars)in oldblocks
 elif kind=='new_projected_signature':
  assert ref in projected and projected[ref][1]==rawsha and projected[ref][3:]==(norm,nchars)
  refs[ref].add(raw)
 elif kind=='empty':assert not nchars and ref is None
 else:raise AssertionError('unexpected_coverage_kind')
for raw,row in coverage.items():
 assert perraw[raw]==row[4]
 assert indexes[raw]==set(range(row[4]))
assert set(refs)==set(projected)
ng,lo,hi=D.execute('select count(*),min(id),max(id) from grams').fetchone();assert not ng or (lo==1 and hi==ng)
assert D.execute('select count(*) from grams where length(sha256)!=32').fetchone()[0]==0
members=decoded=0
for count,blob in D.execute('select gram_count,gram_ids_delta_zlib from texts'):
 dec=zlib.decompressobj();raw=dec.decompress(blob,count*5+1);assert dec.eof and not dec.unused_data and not dec.unconsumed_tail and len(raw)<=count*5
 values=[];v=shift=prev=0
 for byte in raw:
  v+=(byte&127)<<shift
  if byte&128:shift+=7;assert shift<35
  else:assert v>0;prev+=v;assert prev<=ng;values.append(prev);v=shift=0
 assert not shift and len(values)==count
 enc=bytearray();prev=0
 for value in values:
  delta=value-prev;prev=value
  while delta>127:enc.append(128+delta%128);delta//=128
  enc.append(delta)
 assert bytes(enc)==raw;decoded+=1;members+=count
bindings=0
for tid,locator in D.execute('select text_id,locator_json from bindings'):
 x=json.loads(locator);assert x['old_raw_sha256']in refs[tid]
 assert x['projection_sha256']==coverage[x['old_raw_sha256']][3]
 assert (x['old_raw_sha256'],x['segment_index'])in segments
 bindings+=1
counts=r['counts'];assert counts['unique_texts_projected']==len(coverage) and counts['projected_segments']==len(segments)
assert counts['record_quarantines']==sum(x[6]for x in coverage.values())
assert counts['zero_segment_views']==sum(x[4]==0 for x in coverage.values())
assert counts['new_signature_views']==kinds['new_projected_signature']
assert counts['raw_equivalent_views']==kinds['old_normalized_full']
assert counts['old_block_equivalent_views']==kinds['old_normalized_long_block']
assert counts['source_views_seen']==324323 and sum(r['source_counts'].values())==324323
all_old_bindings=B.execute('select count(*) from bindings').fetchone()[0];assert all_old_bindings==324320
for d in(D,C,B,N):d.close()
result={'schema_version':'old-projected-signature-independent-readback/1','decision':'PASS_BOUNDED_OLD_PROJECTED_SIGNATURE_STRUCTURE_ONLY','plan_sha256':h(planpath),'receipt_sha256':h(receiptpath),'projected_package_sha256':r['new_package']['sha256'],'coverage_database_sha256':r['coverage_database']['sha256'],'all_old_source_bindings':all_old_bindings,'old_source_views_missing':0,'old_unique_texts':len(oldtexts),'new3_unique_texts':len(new3texts),'coverage_rows':len(coverage),'segments':len(segments),'segment_coverage_kinds':dict(kinds),'projected_unique_texts':len(projected),'projected_bindings':bindings,'projected_unique_grams':ng,'projected_gram_memberships_decoded':members,'projected_text_sets_decoded':decoded,'quarantined_raw_views':counts['record_quarantines'],'zero_segment_raw_views':counts['zero_segment_views'],'raw_source_bodies_read':0,'source_derivation_rerun':False,'new_parser_or_fit':False,'G2_admitted':False,'compatibility_consumer_and_all_member_expansion_separate_gate':True,'limits':['No raw-text transformation recomputed during audit','Discarded role regions have only original raw-view coverage','Same-profile bounded view comparison is not semantic-copy completeness','Deduplicated projected text needs expansion through all raw-view member bindings'],'remote_writes':False}
(O/'readback.aggregate.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
