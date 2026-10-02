#!/usr/bin/env python3
"""Reproduce the 13-file sample identity and structural counts, without publishing text.
Use only where the source licenses permit the intended research. No downloaded code runs.
"""
import argparse,collections,fcntl,hashlib,json,pathlib,re,resource,urllib.request
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
HAN=re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff]')
def blocks(raw,source,key):
 text=raw.decode('utf-8'); lines=text.splitlines(keepends=True); out=[]; pos=0; inmeta=False; fence=None; listscope=False; admin=False
 roles=[]
 for i,line in enumerate(lines):
  s=line.strip(); role='prose_candidate'
  if i==0 and s=='---': inmeta=True; role='frontmatter'
  elif inmeta:
   role='frontmatter'
   if s=='---':inmeta=False
  elif fence:
   role='fenced_code'
   if s.startswith(fence):fence=None
  elif s.startswith(('```','~~~')):role='fenced_code';fence=s[:3]
  elif not s:role='blank'
  elif source=='yufree' and key=='museum' and s.startswith('2020年对每个经历过的人'):admin=True;role='administrative_call_to_action'
  elif admin:role='administrative_call_to_action'
  elif s.startswith('>'):role='project_boilerplate' if source=='liqi' and '本文参与' in s else 'marked_quote'
  elif s.startswith('!['):role='image_reference'
  elif re.match(r'^#{1,6}\s',s):role='interviewer_question' if source=='liqi' and not s.startswith('# ') else 'heading';listscope=False
  elif source=='liqi' and re.match(r'^\*\*.+\*\*$',s):role='interviewer_question';listscope=False
  elif re.match(r'^([-*_])(?:\s*\1){2,}$',s):role='thematic_break';listscope=False
  elif re.match(r'^(?:[-+*]|\d+[.)])\s+',s):role='list_item';listscope=True
  elif line.startswith(('    ','\t')):role='list_continuation_prose' if listscope else 'indented_ambiguous'
  elif s.startswith('<'):role='html_or_comment'
  elif re.match(r'^https?://\S+$',s):role='standalone_url'
  else:listscope=False
  roles.append((role,pos,pos+len(line.encode()),i+1,i+1,line));pos+=len(line.encode())
 # Merge same-role contiguous physical lines; blank lines remain separate boundary spans.
 for role,start,end,l1,l2,line in roles:
  if out and out[-1]['role']==role and role not in {'interviewer_question','heading','list_item','image_reference','thematic_break'}:
   out[-1]['end_byte']=end;out[-1]['line_end']=l2
  else:out.append({'role':role,'start_byte':start,'end_byte':end,'line_start':l1,'line_end':l2})
 for b in out:
  chunk=raw[b['start_byte']:b['end_byte']]; b['sha256']=hashlib.sha256(chunk).hexdigest(); b['han_characters']=len(HAN.findall(chunk.decode()));b['utf8_bytes']=len(chunk)
 assert out[0]['start_byte']==0 and out[-1]['end_byte']==len(raw)
 assert all(a['end_byte']==b['start_byte'] for a,b in zip(out,out[1:]))
 return out

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--cache-dir',required=True,help='Local private source cache outside the publication directory')
 parser.add_argument('--verify-cache-only',action='store_true')
 parser.add_argument('--confirm-noncommercial-research',action='store_true')
 args=parser.parse_args()
 root=pathlib.Path(__file__).resolve().parent; cache=pathlib.Path(args.cache_dir).resolve()
 if root==cache or root in cache.parents: raise SystemExit('Keep raw source cache outside publication directory')
 cache.mkdir(parents=True,exist_ok=True)
 lock=open(cache/'.acquire.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 m=json.load(open(root/'candidate_manifest.json'));total=0;result=[]
 for row in m['documents']:
  dest=cache/(row['id']+'.md')
  if not dest.exists():
   if args.verify_cache_only: raise SystemExit('Missing source cache: '+row['id'])
   if not args.confirm_noncommercial_research: raise SystemExit('Check rights and pass --confirm-noncommercial-research before source acquisition')
   req=urllib.request.Request(row['raw_url'],headers={'User-Agent':'bounded-longform-source-audit/1.0'})
   with urllib.request.urlopen(req,timeout=30) as response: b=response.read(row['source_bytes']+1)
  else:b=dest.read_bytes()
  total+=len(b)
  if total>20*1024**2:raise SystemExit('Budget exceeded')
  assert len(b)==row['source_bytes'],row['id']
  assert hashlib.sha256(b).hexdigest()==row['sha256'],row['id']
  assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==row['git_blob_sha1'],row['id']
  if not dest.exists():dest.write_bytes(b)
  key=row['id'].removeprefix(row['source_id']+'-');spans=blocks(b,row['source_id'],key)
  counts=collections.Counter(s['role'] for s in spans if s['role']!='blank');hans=collections.Counter()
  for span in spans:hans[span['role']]+=span['han_characters']
  assert dict(counts)==row['role_block_counts'],row['id']
  assert dict(hans)==row['role_han_counts'],row['id']
  result.append({'id':row['id'],'identity_and_structure':'pass'})
 print(json.dumps({'documents':len(result),'source_bytes':total,'raw_published':False,'results':result},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
