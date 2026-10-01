"""One-time offline fingerprints of enumerated, already-exposed licensed sources.
Only exclusion signatures/locators are persisted, privately. No model inputs,
POS, targets, predictions, network requests, new corpus acquisition or fitting.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,hashlib,json,os,re,resource,socket,sqlite3,sys,time,unicodedata,xml.etree.ElementTree as ET,zipfile,zlib
ALGORITHM='exposure-copy-signatures/1.0.0'
NORMALIZATION='Unicode NFKC then remove str.isspace; no punctuation removal or script conversion'
ROOT=Path('/workspace/shared/style-compiler-data/exposure-fingerprints-v01')
REPO=Path('/workspace/shared/style-compiler')
ALLOWLIST_HASH='c6a121bf83ad6908ff1306c35b148b11727a1644944a36ccb9f072ff037d0af3'
CAPS={'wall_seconds':1800,'rss_bytes':3*1024**3,'derivative_bytes':1024**3,'source_view_utf8_bytes':256*1024**2,'source_views':400000,'unique_texts':150000,'unique_grams':8000000}

def sha(b):return hashlib.sha256(b).hexdigest()
def filehash(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def normalize(s):return ''.join(c for c in unicodedata.normalize('NFKC',s) if not c.isspace())
def norm_hash(s):return hashlib.sha256(b'nfkc-no-ws/v1\0'+s.encode()).digest()
def gram_hash(s):return hashlib.sha256(b'char5-nfkc-no-ws/v1\0'+s.encode()).digest()
def pack_ids(ids):
 result=bytearray();old=0
 for n in sorted(set(ids)):
  if type(n) is not int or n<=0:raise ValueError('invalid_gram_id')
  d=n-old;old=n
  while d>=128:result.append((d&127)|128);d>>=7
  result.append(d)
 return zlib.compress(bytes(result),level=6)
def unpack_ids(blob):
 result=[];v=0;shift=0;old=0
 for byte in zlib.decompress(blob):
  v|=(byte&127)<<shift
  if byte&128:shift+=7
  else:
   if v<=0:raise ValueError('nonpositive_delta')
   old+=v;result.append(old);v=0;shift=0
 if shift:raise ValueError('incomplete_varint')
 return result

def wiki_member(project,page):
 if project not in ('zhwiki','zhwikinews','zhwikivoyage') or not isinstance(page,str) or not re.fullmatch('[0-9]+',page):raise ValueError('invalid_wiki_member')
 return canonical(['wikimedia',project,'page:'+str(int(page))]).decode()
def write_new(p,x):
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
 return filehash(p)

class Writer:
 def __init__(self,path,segmenter):
  self.db=sqlite3.connect(path);self.path=path;self.segmenter=segmenter
  self.db.executescript('''PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL; PRAGMA cache_size=-16384;
  CREATE TABLE control(key TEXT PRIMARY KEY,value TEXT);
  CREATE TABLE grams(id INTEGER PRIMARY KEY,sha256 BLOB UNIQUE NOT NULL);
  CREATE TABLE texts(id INTEGER PRIMARY KEY,raw_sha256 TEXT UNIQUE NOT NULL,utf8_bytes INTEGER,codepoints INTEGER,normalized_sha256 BLOB,normalized_codepoints INTEGER,gram_count INTEGER,gram_ids_delta_zlib BLOB);
  CREATE TABLE blocks(text_id INTEGER,kind TEXT,ordinal INTEGER,normalized_sha256 BLOB,normalized_codepoints INTEGER,PRIMARY KEY(text_id,kind,ordinal));
  CREATE TABLE bindings(id INTEGER PRIMARY KEY,source_id TEXT,member_key TEXT,exposure_role TEXT,source_view_role TEXT,source_object_sha256 TEXT,text_id INTEGER,locator_json TEXT);
  ''')
  self.grams={};self.texts={};self.counts=Counter();self.by_source=defaultdict(Counter);self.start=time.monotonic()
 def guard(self):
  c=self.counts
  if time.monotonic()-self.start>CAPS['wall_seconds']:raise RuntimeError('wall_cap')
  if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>CAPS['rss_bytes']:raise RuntimeError('rss_cap')
  size=sum(p.stat().st_size for p in ROOT.iterdir() if p.is_file())
  if size>CAPS['derivative_bytes']:raise RuntimeError('derivative_bytes_cap')
  if c['source_view_utf8_bytes']>CAPS['source_view_utf8_bytes'] or c['bindings']>CAPS['source_views']:raise RuntimeError('source_view_cap')
  if len(self.texts)>CAPS['unique_texts'] or len(self.grams)>CAPS['unique_grams']:raise RuntimeError('dictionary_cap')
  control=json.loads((ROOT/'control.json').read_text())
  if control.get('action')!='run':raise RuntimeError('control_'+str(control.get('action')))
 def add(self,text,source,member,exposure,role,objhash,locator):
  raw=text.encode();rawhash=sha(raw)
  self.counts['source_view_utf8_bytes']+=len(raw);self.counts['bindings']+=1
  self.by_source[source]['views']+=1;self.by_source[source]['utf8_bytes']+=len(raw)
  if rawhash in self.texts:tid=self.texts[rawhash]
  else:
   tid=len(self.texts)+1;self.texts[rawhash]=tid;n=normalize(text);ids=set()
   for i in range(max(0,len(n)-4)):
    h=gram_hash(n[i:i+5]);gid=self.grams.get(h)
    if gid is None:
     gid=len(self.grams)+1;self.grams[h]=gid;self.db.execute('insert into grams values(?,?)',(gid,h))
    ids.add(gid)
   packed=pack_ids(ids)
   self.db.execute('insert into texts values(?,?,?,?,?,?,?,?)',(tid,rawhash,len(raw),len(text),norm_hash(n),len(n),len(ids),packed))
   self.counts['unique_text_gram_memberships']+=len(ids);self.counts['normalized_nonempty_texts']+=bool(n)
   self.counts['texts_with_5shingles']+=bool(ids)
   units=self.segmenter(text)[1]
   blocks=[('physical_blankline_block',i,s) for i,s in enumerate(re.split(r'(?:\r?\n[\t ]*){2,}',text))]
   blocks += [('punctuation_line_unit',i,text[s.start:s.end]) for i,s in enumerate(units)]
   for kind,ordinal,block in blocks:
    bn=normalize(block)
    if len(bn)>=64:
     self.db.execute('insert into blocks values(?,?,?,?,?)',(tid,kind,ordinal,norm_hash(bn),len(bn)))
     self.counts['long_block_or_unit_hashes']+=1
  self.db.execute('insert into bindings(source_id,member_key,exposure_role,source_view_role,source_object_sha256,text_id,locator_json) values(?,?,?,?,?,?,?)',(source,member,exposure,role,objhash,tid,canonical(locator).decode()))
  if self.counts['bindings']%500==0:
   self.db.commit();self.guard()
   if self.counts['bindings']%10000==0:
    (ROOT/'live-status.json').write_text(json.dumps({'status':'running','views':self.counts['bindings'],'unique_texts':len(self.texts),'unique_grams':len(self.grams),'elapsed_seconds':time.monotonic()-self.start}))
  return rawhash

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root-fingerprint-go',action='store_true');args=ap.parse_args()
 if not args.root_fingerprint_go:raise ValueError('root_go_required')
 al=ROOT/'source-allowlist.private.json';assert filehash(al)==ALLOWLIST_HASH;a=json.loads(al.read_text())
 plan=ROOT/'execution-plan.public.json';p=json.loads(plan.read_text());assert p['algorithm_sha256']==filehash(Path(__file__)) and p['allowlist_sha256']==ALLOWLIST_HASH
 # Deny network at process level, not an OS/network setting change.
 def blocked(*args,**kwargs):raise RuntimeError('network_forbidden')
 socket.socket=blocked;socket.create_connection=blocked
 sys.path[:0]=[str(REPO/'src'),str(REPO/'research/audits')]
 for name,h in a['readers'].items():assert filehash(REPO/'research/audits'/name)==h
 from wikiconv_annual_census import Archive,jsonl_records,object_items,views
 from wikiconv_zip_audit import metadata
 from style_compiler.segmentation import segment,SEGMENTER_VERSION
 assert filehash(REPO/'src/style_compiler/segmentation.py')==p['segmentation_sha256']
 marker={'allowlist_sha256':ALLOWLIST_HASH,'execution_plan_sha256':filehash(plan),'algorithm_sha256':filehash(Path(__file__)),'purpose':'exclusion_only'}
 write_new(ROOT/'ONE_TIME_STARTED.json',marker)
 w=Writer(ROOT/'fingerprints.private.sqlite',segment)
 try:
  for item in a['blogs']:
   raw=Path(item['path']).read_bytes();assert sha(raw)==item['sha256'] and len(raw)==item['bytes']
   member=canonical(['gitblog','zhengtianbao.github.io','post:'+item['original_path']]).decode()
   w.add(raw.decode('utf-8'),'third_party_blog39',member,item['exposure_role'],'raw_markdown',item['sha256'],{'path':item['path'],'git_post':item['original_path']})
  for item in a['pmc']:
   raw=Path(item['path']).read_bytes();assert sha(raw)==item['sha256']
   lo,hi=item['article_range'];assert sha(raw[lo:hi])==item['article_sha256']
   assert b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw
   tree=ET.fromstring(raw);articles=[e for e in tree.iter() if e.tag.split('}')[-1]=='article'];assert len(articles)==1
   member=canonical(['pmc','PMC',item['pmcid']]).decode();article=articles[0]
   w.add(raw.decode('utf-8'),'PMC6',member,item['exposure_role'],'raw_OAI_XML',item['sha256'],{'path':item['path']})
   w.add(''.join(article.itertext()),'PMC6',member,item['exposure_role'],'article_itertext_unclassified',item['sha256'],{'path':item['path'],'article_sha256':item['article_sha256']})
   for i,e in enumerate(article.iter()):
    tag=e.tag.split('}')[-1]
    if tag in ('p','article-title','title'):
     w.add(''.join(e.itertext()),'PMC6',member,item['exposure_role'],'JATS_'+tag+'_text_not_training_prose',item['sha256'],{'path':item['path'],'element_preorder':i,'tag':tag})
  old=a['wikiconv2002'];path=Path(old['path']);assert filehash(path)==old['sha256'] and path.stat().st_size==old['bytes']
  with zipfile.ZipFile(path) as z:
   conv=json.loads(z.read('conversations.json'))
   for row,line in enumerate(z.read('utterances.jsonl').splitlines(),1):
    if not line.strip():continue
    for k,v in enumerate(views(json.loads(line))):
     page=metadata(conv[v['conversation']])['page_id']
     w.add(v['text'],'WikiConv2002',wiki_member('zhwiki',page),'prior_format_pilot',v['role'],old['sha256'],{'row':row,'view_ordinal':k,'header':v['header'],'record_id':v['id']})
  spec=a['wikiconv2017'];ep=Path(spec['expected_view_file']);assert filehash(ep)==spec['expected_view_file_sha256']
  expected=defaultdict(list)
  for e in json.loads(ep.read_text()):expected[e['rownum']].append(e)
  for e in expected.values():e.sort(key=lambda r:r['seq'])
  wanted=set(spec['allowed_top_rows']);assert set(expected)==wanted;seen=set();role_counts=Counter();origin_members=set()
  archive=Archive(Path(spec['path']),spec['sha256'],spec['bytes'],spec['expanded_bytes'])
  for row,offset,record in jsonl_records(archive.chunks('utterances.jsonl')):
   if row%1000==0:w.guard()
   if row not in wanted:continue
   observed=list(views(record));assert len(observed)==len(expected[row])
   for v,e in zip(observed,expected[row]):
    assert offset==e['byte_offset'] and v['role']==e['role'] and v['id']==e['id'] and v['conversation']==e['conversation'] and len(v['text'])==e['chars'] and sha(v['text'].encode())==e['text_sha256']
    page=spec['conversation_to_page'][v['conversation']];member=wiki_member('zhwiki',page);origin_members.add(member)
    w.add(v['text'],'WikiConv2017',member,'old_exposed_or_selected_component',v['role'],spec['sha256'],{'row':row,'seq':e['seq'],'byte_offset':offset,'header':v['header'],'record_id':v['id'],'conversation_id':v['conversation'],'whole_parent_row_contaminated':True})
    role_counts[v['role']]+=1
   seen.add(row)
  assert seen==wanted and 'utterances.jsonl' in archive.verified;archive.close()
  w.db.execute('insert into control values(?,?)',('status','complete'))
  w.db.execute('insert into control values(?,?)',('algorithm',ALGORITHM));w.db.commit();w.guard()
  expected_n=sum(len(g) for g in expected.values());assert sum(role_counts.values())==expected_n
  w.db.close()
  result={'schema_version':'exposure-fingerprint-aggregate/1','status':'fingerprint_package_complete_not_G2_admission','algorithm':ALGORITHM,'normalization':NORMALIZATION,'unicode_version':unicodedata.unidata_version,'segmentation':SEGMENTER_VERSION,'allowlist_sha256':ALLOWLIST_HASH,'execution_plan_sha256':filehash(plan),'algorithm_sha256':filehash(Path(__file__)),'fingerprint_database_sha256':filehash(w.path),'fingerprint_database_bytes':w.path.stat().st_size,'source_counts':{k:dict(v) for k,v in w.by_source.items()},'counts':dict(w.counts),'unique_texts':len(w.texts),'unique_5shingle_hashes':len(w.grams),'2017_roles':dict(role_counts),'2017_top_rows':len(seen),'2017_expected_views':expected_n,'2017_origin_page_members':len(origin_members),'all_expected_views_hashed':True,'signature_coverage':['raw_UTF8_text_exact','NFKC_no_whitespace_full','normalized_64plus_blankline_blocks_and_punctuation_line_units','distinct_character_5shingle_full_SHA256_dictionary_sets'],'identities_namespaced_signatures_comparable_across_sources':True,'cross_projection_status':'raw/source-text signatures available; not certified equivalent to future clean prose projection. Future projected candidates must also compare raw views; unsupported mappings/known unresolved lineage quarantine, never treat no match as proof of no semantic copying.','missing_coverage':['three newly acquired pre2022 blog diagnostic representatives are outside this allowlist','future clean-prose projection profile not yet implemented/audited'],'new_download_bytes':0,'models_or_targets_read':False,'personal_owner_text_read':False,'new_source_projection_or_calibration_run':False,'prior_test_used_for_selection_or_evaluation':False,'raw_text_persisted':False,'resources':{'elapsed_seconds':time.monotonic()-w.start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'caps':CAPS},'purpose':'exclusion only, not training corpus or author/human labels'}
  write_new(ROOT/'aggregate.json',result);(ROOT/'live-status.json').write_text(json.dumps({'status':'complete','aggregate_sha256':filehash(ROOT/'aggregate.json')}));print(json.dumps(result))
 except Exception as exc:
  try:w.db.commit();w.db.close()
  except Exception:pass
  failure={'status':'failed_stop_no_retry','type':type(exc).__name__,'reason':str(exc),'counts':dict(w.counts),'purpose':'exclusion only','complete':False}
  write_new(ROOT/'failure.aggregate.json',failure);(ROOT/'live-status.json').write_text(json.dumps(failure));raise

if __name__=='__main__':main()
