#!/usr/bin/env python3
"""Secondary local/tool-session backup. Lossless private archive, not durable storage."""
from __future__ import annotations
import argparse,base64,gzip,hashlib,io,json,lzma,os,re,shutil,tarfile,tempfile,time,zlib
from pathlib import Path
VERSION='zh-extraction-secondary-cache/1.0.0'
CAP=32*1024**2
CHUNK=64*1024
CACHE_NAME=re.compile(r'[a-f0-9]{64}\.(human|chatgpt)\.json\.gz\Z')

def sha(b):return hashlib.sha256(b).hexdigest()
def file_sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  while b:=f.read(1024**2):h.update(b)
 return h.hexdigest()
def js(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def write(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.tmp');temp.write_bytes(js(obj)+b'\n');os.replace(temp,path)
def add(tar,name,payload):
 info=tarfile.TarInfo(name);info.size=len(payload);info.mtime=0;info.uid=info.gid=0;info.mode=0o600
 tar.addfile(info,io.BytesIO(payload))
def snapshot(ledger):
 data=Path(ledger).read_bytes();lines=data.splitlines(keepends=True);events=[];last=None;end=0;names=set()
 for line in lines:
  if not line.endswith(b'\n'):break
  event=json.loads(line);end+=len(line)
  if event.get('event')=='cache_committed':
   assert event['split'] in ('train','dev') and event['arm'] in ('human','chatgpt'),'out_of_scope_cache'
   name=event['cache_file'];assert CACHE_NAME.fullmatch(name),'unsafe_cache_name'
   assert name not in names,'duplicate_committed_cache';names.add(name);events.append(event);last=end
 assert events,'no_committed_cache'
 return data[:last],events

def repack(raw,header):
 compressed=gzip.compress(raw,compresslevel=6,mtime=0)
 assert len(header)==10 and header[:4]==b'\x1f\x8b\x08\x00','unsupported_gzip_header'
 return header+compressed[10:]

def pack(root,destination,cap=CAP):
 root=Path(root);dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
 started=time.monotonic();ledger,events=snapshot(root/'private/execution_ledger.jsonl')
 manifest={'version':VERSION,'payload_mode':'exact_decompressed_json_bytes','gzip_compresslevel':6,'gzip_mtime':0,'zlib_version':zlib.ZLIB_VERSION,
   'zlib_runtime_version':zlib.ZLIB_RUNTIME_VERSION,'ledger_sha256':sha(ledger),'committed_cache_count':len(events),'files':[]}
 target=dest/'cache_snapshot.tar.xz';tmp=dest/'cache_snapshot.tar.xz.tmp'
 try:
  with lzma.LZMAFile(tmp,'wb',format=lzma.FORMAT_XZ,filters=[{'id':lzma.FILTER_LZMA2,'preset':6,'dict_size':16*1024**2}]) as compressed:
   with tarfile.open(fileobj=compressed,mode='w|',format=tarfile.PAX_FORMAT) as tar:
    for event in sorted(events,key=lambda e:e['cache_file']):
     name=event['cache_file'];b=(root/'private/cache'/name).read_bytes();assert sha(b)==event['cache_sha256'],'cache_sha_mismatch'
     raw=gzip.decompress(b);json.loads(raw)
     manifest['files'].append({'name':name,'gz_sha256':sha(b),'gz_bytes':len(b),'raw_sha256':sha(raw),'raw_bytes':len(raw),'gzip_header_hex':b[:10].hex()})
     add(tar,'cache_json/'+name[:-3],raw)
    add(tar,'execution_ledger.jsonl',ledger);add(tar,'backup_manifest.json',js(manifest))
  size=tmp.stat().st_size
  if size>cap:
   # Original caches and previous generations are untouched; this oversized copy is not promoted.
   result={'success':False,'reason':'compressed_archive_budget_exceeded','committed_cache_count':len(events),'compressed_bytes':size,'cap_bytes':cap,'elapsed_seconds':time.monotonic()-started,'source_caches_unchanged':True}
   write(dest/'backup_attempt_receipt.json',result);tmp.unlink();return result
  os.replace(tmp,target)
  chunks=[]
  with target.open('rb') as f:
   while b:=f.read(CHUNK):chunks.append({'bytes':len(b),'sha256':sha(b)})
  private_index={'version':VERSION,'archive_file':str(target.resolve()),'archive_sha256':file_sha(target),'archive_bytes':size,'chunk_bytes':CHUNK,'chunks':chunks,'committed_cache_count':len(events),'ledger_sha256':sha(ledger)}
  write(dest/'chunk_index.json',private_index)
  result={'success':True,'version':VERSION,'archive_file':str(target.resolve()),'chunk_index_file':str((dest/'chunk_index.json').resolve()),'archive_sha256':private_index['archive_sha256'],'compressed_bytes':size,'chunk_count':len(chunks),'committed_cache_count':len(events),'ledger_sha256':sha(ledger),'elapsed_seconds':time.monotonic()-started,'durability':'secondary_only_no_guarantee','tool_store_verified':False}
  write(dest/'backup_attempt_receipt.json',result);return result
 except Exception:
  if tmp.exists():tmp.unlink()
  raise

def encode_gzip(raw):
 return gzip.compress(raw,compresslevel=6,mtime=0)

def inspect_restore(archive,destination=None):
 # Scientific payload is exact original decompressed JSON bytes. A changed
 # container stream gets a new hash and an explicit old/new restoration map.
 archive=Path(archive);dest=Path(destination) if destination else None
 if dest:
  assert not dest.exists() or not any(dest.iterdir()),'restore_destination_must_be_empty'
  dest.mkdir(parents=True,exist_ok=True);(dest/'private/cache').mkdir(parents=True,exist_ok=True)
 seen={};manifest=None;ledger=None
 with tarfile.open(archive,'r|xz') as tar:
  for member in tar:
   assert member.isfile() and member.size<=64*1024**2,'unsafe_member_type_or_size'
   name=member.name
   assert name in ('backup_manifest.json','execution_ledger.jsonl') or (name.startswith('cache_json/') and CACHE_NAME.fullmatch(name[len('cache_json/'):]+'.gz')), 'unsafe_archive_name'
   f=tar.extractfile(member);raw=f.read();assert len(raw)==member.size
   if name=='backup_manifest.json':assert manifest is None;manifest=json.loads(raw)
   elif name=='execution_ledger.jsonl':assert ledger is None;ledger=raw
   else:
    cache_name=name[len('cache_json/'):]+'.gz';assert cache_name not in seen;json.loads(raw)
    seen[cache_name]={'raw_sha256':sha(raw),'raw_bytes':len(raw)}
    if dest:
     compressed=encode_gzip(raw);assert gzip.decompress(compressed)==raw
     (dest/'private/cache'/cache_name).write_bytes(compressed)
 assert manifest and ledger and manifest['version']==VERSION and manifest['payload_mode']=='exact_decompressed_json_bytes'
 assert sha(ledger)==manifest['ledger_sha256'] and len(seen)==manifest['committed_cache_count']==len(manifest['files'])
 mappings={};changed=0
 for item in manifest['files']:
  assert CACHE_NAME.fullmatch(item['name']) and seen[item['name']]=={k:item[k] for k in ('raw_sha256','raw_bytes')},'cache_manifest_mismatch'
  if dest:
   path=dest/'private/cache'/item['name'];newhash=file_sha(path);changed+=newhash!=item['gz_sha256']
   mappings[item['name']]={'original_gzip_sha256':item['gz_sha256'],'restored_gzip_sha256':newhash,'original_json_sha256':item['raw_sha256'],'restored_gzip_bytes':path.stat().st_size,'gzip_identity_changed':newhash!=item['gz_sha256']}
 if dest:
  # Retain the exact original ledger as evidence, and explicitly update only the
  # physical cache-container identities used by the active on-disk ledger.
  (dest/'private/secondary_original_execution_ledger.jsonl').write_bytes(ledger)
  restored_lines=[]
  for line in ledger.splitlines(keepends=True):
   event=json.loads(line)
   if event.get('event')=='cache_committed':
    mapping=mappings[event['cache_file']]
    assert event['cache_sha256']==mapping['original_gzip_sha256']
    if mapping['gzip_identity_changed']:
     event.update(cache_sha256=mapping['restored_gzip_sha256'],bytes=mapping['restored_gzip_bytes'],original_cache_sha256=mapping['original_gzip_sha256'],original_json_sha256=mapping['original_json_sha256'],container_regenerated_from_secondary_backup=True)
     line=js(event)+b'\n'
   restored_lines.append(line)
  restored_ledger=b''.join(restored_lines);(dest/'private/execution_ledger.jsonl').write_bytes(restored_ledger)
  prefix,events=snapshot(dest/'private/execution_ledger.jsonl');assert len(events)==len(seen)
  for event in events:assert file_sha(dest/'private/cache'/event['cache_file'])==event['cache_sha256']
  write(dest/'private/secondary_restoration_receipt.json',{'version':VERSION,'archive_sha256':file_sha(archive),'original_ledger_sha256':sha(ledger),'restored_ledger_sha256':sha(restored_ledger),'committed_cache_count':len(seen),'changed_gzip_containers':changed,'all_original_json_bytes_sha256_verified':True,'measurement_values_or_identities_changed':False,'file_mapping':mappings})
 return {'verified':True,'committed_cache_count':len(seen),'archive_sha256':file_sha(archive),'archive_bytes':archive.stat().st_size,'exact_original_json_bytes_verified':True,'gzip_container_hashes_preserved':len(seen)-changed if dest else None,'gzip_container_hashes_regenerated':changed if dest else None,'destination_written':bool(dest),'payload_mode':'exact_decompressed_json_bytes'}

def read_chunk(index_path,number):
 index=json.loads(Path(index_path).read_bytes());assert type(number)is int and 0<=number<len(index['chunks'])
 meta=index['chunks'][number]
 with open(index['archive_file'],'rb') as f:f.seek(number*index['chunk_bytes']);b=f.read(meta['bytes'])
 assert len(b)==meta['bytes'] and sha(b)==meta['sha256'],'chunk_mismatch'
 return base64.b64encode(b).decode('ascii')

def write_chunk(directory,number,b64):
 assert type(number)is int and 0<=number<10000
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
 raw=base64.b64decode(b64,validate=True);assert len(raw)<=CHUNK
 (directory/f'{number:05d}.bin').write_bytes(raw)
 return {'number':number,'bytes':len(raw),'sha256':sha(raw)}

def finish_readback(directory,index_path,destination):
 directory=Path(directory);index=json.loads(Path(index_path).read_bytes());dest=Path(destination)
 assert len(list(directory.glob('*.bin')))==len(index['chunks'])
 with dest.open('wb') as f:
  for i,expected in enumerate(index['chunks']):
   b=(directory/f'{i:05d}.bin').read_bytes();assert len(b)==expected['bytes'] and sha(b)==expected['sha256'];f.write(b)
 assert dest.stat().st_size==index['archive_bytes'] and file_sha(dest)==index['archive_sha256'],'archive_readback_hash_mismatch'
 info=inspect_restore(dest)
 return dict(info,tool_store_archive_readback_verified=True)

def main():
 os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
 p=argparse.ArgumentParser();p.add_argument('action',choices=['pack','inspect','restore','read-chunk','write-chunk','finish-readback']);p.add_argument('--root');p.add_argument('--destination');p.add_argument('--archive');p.add_argument('--index');p.add_argument('--number',type=int);p.add_argument('--base64');p.add_argument('--directory');p.add_argument('--cap',type=int,default=CAP);a=p.parse_args()
 if a.action=='pack':r=pack(a.root,a.destination,a.cap)
 elif a.action=='inspect':r=inspect_restore(a.archive)
 elif a.action=='restore':r=inspect_restore(a.archive,a.destination)
 elif a.action=='read-chunk':print(read_chunk(a.index,a.number),end='');return
 elif a.action=='write-chunk':r=write_chunk(a.directory,a.number,a.base64)
 else:r=finish_readback(a.directory,a.index,a.destination)
 print(json.dumps(r),flush=True)
if __name__=='__main__':main()
