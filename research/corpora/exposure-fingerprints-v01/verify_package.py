"""Read-only fingerprint-package integrity checks; no raw corpus or model reads."""
from pathlib import Path
from collections import Counter
import hashlib,json,sqlite3
from fingerprint import unpack_ids,filehash
P=Path('/workspace/shared/style-compiler-data/exposure-fingerprints-v01')
def main():
 receipt=json.loads((P/'aggregate.json').read_text());a=json.loads((P/'source-allowlist.private.json').read_text())
 assert receipt['status']=='fingerprint_package_complete_not_G2_admission'
 assert filehash(P/'fingerprints.private.sqlite')==receipt['fingerprint_database_sha256']
 db=sqlite3.connect((P/'fingerprints.private.sqlite').as_uri()+'?mode=ro',uri=True);db.execute('PRAGMA query_only=ON')
 assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
 n,maxid=db.execute('select count(*),max(id) from grams').fetchone();assert n==maxid==receipt['unique_5shingle_hashes']
 assert db.execute('select count(*) from grams where length(sha256)!=32').fetchone()[0]==0
 text_count=0;memberships=0
 for tid,h,nh,count,blob in db.execute('select id,raw_sha256,normalized_sha256,gram_count,gram_ids_delta_zlib from texts'):
  ids=unpack_ids(blob);assert len(ids)==count and (not ids or ids[-1]<=maxid) and len(nh)==32 and len(h)==64
  assert len(set(ids))==len(ids) and ids==sorted(ids)
  text_count+=1;memberships+=count
 assert text_count==receipt['unique_texts'] and memberships==receipt['counts']['unique_text_gram_memberships']
 expected={r['seq']:r for r in json.loads(Path(a['wikiconv2017']['expected_view_file']).read_text())}
 seen=set();roles=Counter()
 for role,locator,h in db.execute('select b.source_view_role,b.locator_json,t.raw_sha256 from bindings b join texts t on t.id=b.text_id where b.source_id="WikiConv2017"'):
  loc=json.loads(locator);seq=loc['seq'];assert seq not in seen;seen.add(seq);r=expected[seq]
  assert role==r['role'] and loc['row']==r['rownum'] and loc['record_id']==r['id'] and h==r['text_sha256'];roles[role]+=1
 assert seen==set(expected) and dict(roles)==receipt['2017_roles']
 bindings=db.execute('select count(*) from bindings').fetchone()[0];assert bindings==receipt['counts']['bindings']
 assert db.execute('select count(*) from bindings b left join texts t on t.id=b.text_id where t.id is null').fetchone()[0]==0
 blocks=db.execute('select count(*) from blocks').fetchone()[0];assert blocks==receipt['counts']['long_block_or_unit_hashes']
 assert db.execute('select count(*) from blocks where normalized_codepoints<64 or length(normalized_sha256)!=32').fetchone()[0]==0
 db.close()
 result={'schema_version':'exclusion-fingerprint-readback/1','status':'passed','database_sha256':receipt['fingerprint_database_sha256'],'aggregate_sha256':filehash(P/'aggregate.json'),'text_sets_decoded':text_count,'shingle_memberships_checked':memberships,'old2017_views_compared_to_preexisting_readonly_metadata':len(seen),'private_bindings':bindings,'long_block_or_unit_hashes':blocks,'sqlite_integrity':'ok','raw_source_reopened':False,'model_or_target_read':False,'G2_admission_granted':False}
 out=P/'readback.aggregate.json'
 with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(result))
if __name__=='__main__':main()
