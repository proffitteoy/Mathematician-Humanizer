#!/usr/bin/env python3
"""Measure original English prose against same-language archive descriptions; never authorship scoring."""
import argparse,collections,hashlib,json,math,os,pathlib,re,statistics,socket,platform,sys
CUES=['for example','for instance','in particular','on the other hand','roughly speaking','it turns out','we now','we first','we can','note that','however','therefore']
def dollar_math(m):
 s=m.group()[1:-1].strip()
 return ' MATHEXPR ' if re.search(r'\\[A-Za-z]|[{}^_=<>∑∈∀∃]|(?<=[A-Za-z0-9])[+*/](?=[A-Za-z0-9])',s) or re.fullmatch(r'[A-Za-z](?:[+-]\d+)?',s) else m.group()
def prepare(text):
 paras=[];excluded=[]
 for i,p in enumerate(re.split(r'\n\s*\n',text.strip())):
  q=re.sub(r'\s+',' ',p).strip();q=re.sub(r'\$[^$]*\$',dollar_math,q)
  if len(re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)*",q.replace('MATHEXPR','').replace('CODEEXPR','')))<5:excluded.append(i);continue
  paras.append(q)
 return paras,excluded
def mattr(w,k=100):
 if len(w)<k:return None
 c=collections.Counter(w[:k]);s=len(c);n=1
 for a,b in zip(w,w[k:]):
  c[a]-=1
  if c[a]==0:del c[a]
  c[b]+=1;s+=len(c);n+=1
 return s/(n*k)
def compute(docs,paras):
 pc=collections.Counter();rawpc=collections.Counter();rels=collections.Counter();sizes=[];psizes=[];span=[];depth=[];words=[];q=0;modal=0;first=0;fail=[];raws=0;zeros=0;mathn=0;coden=0
 for pi,doc in enumerate(docs):
  pn=0
  for si,s in enumerate(doc.sentences):
   aw=s.words;rawpc.update(w.upos for w in aw);raws+=1;mathn+=sum(w.text=='MATHEXPR' for w in aw);coden+=sum(w.text=='CODEEXPR' for w in aw)
   if any(w.head is None or not w.deprel or w.head<0 or w.head>len(aw) for w in aw):fail.append([pi,si])
   lex=[w for w in aw if w.upos not in ('PUNCT','SYM','X') and w.text not in ('MATHEXPR','CODEEXPR')];ids={w.id for w in lex}
   if not lex:zeros+=1;continue
   sizes.append(len(lex));pn+=len(lex);pc.update(w.upos for w in lex);words.extend(w.text.lower() for w in lex);q+=int('?' in s.text);modal+=sum(w.xpos=='MD' for w in lex);first+=sum(w.text.lower() in ('i','we','me','us','our','my') for w in lex)
   for w in lex:
    if w.head and w.head in ids:span.append(abs(w.id-w.head));rels[w.deprel]+=1
    cur=w;seen=set();d=0
    while cur.head and cur.head not in seen and cur.head<=len(aw):seen.add(cur.head);d+=1;cur=aw[cur.head-1]
    depth.append(d)
  psizes.append(pn)
 n=sum(pc.values())
 if not n:raise ValueError('No English lexical material')
 text=' '.join(paras).lower();cue={k:len(re.findall(r'(?<!\w)'+re.escape(k)+r'(?!\w)',text)) for k in CUES}
 f={'punctuation_tokens_per_100_words':100*rawpc.get('PUNCT',0)/n,'sentence_words_mean':statistics.mean(sizes),'paragraph_words_mean':statistics.mean(psizes),'dependency_span_mean':statistics.mean(span) if span else None,'dependency_depth_mean':statistics.mean(depth),'mattr100':mattr(words),'question_sentence_share':q/len(sizes),'modal_per_100_words':100*modal/n,'first_person_per_100_words':100*first/n,'subordinate_arcs_per_100_words':100*sum(v for k,v in rels.items() if k.split(':')[0] in ('acl','advcl','ccomp','xcomp','csubj'))/n}
 f.update({'upos_'+k:pc[k]/n for k in ['NOUN','VERB','ADJ','ADV','PRON','SCONJ','CCONJ','AUX']});f.update({'cue_'+k.replace(' ','_'):1000*v/n for k,v in cue.items()})
 return {'status':'MEASURED' if not fail else 'INCOMPLETE','lexical_words':n,'lexical_sentences':len(sizes),'paragraphs':len(paras),'features':f,'upos_counts':dict(pc),'coverage':{'parsed_sentences_total':raws,'zero_lexical_sentences':zeros,'math_tokens':mathn,'code_tokens':coden,'incomplete_dependency_sentences':fail},'quality_or_authorship_score':None}
def _run():
 p=argparse.ArgumentParser();p.add_argument('text');p.add_argument('--models',required=True);p.add_argument('--contract',required=True);p.add_argument('--profile');p.add_argument('--genre',default='math_exposition');p.add_argument('--out',required=True);a=p.parse_args()
 if pathlib.Path(a.out).exists():raise ValueError('Output exists; choose a new measurement path')
 os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
 import stanza,torch
 torch.set_num_threads(2);contract=json.loads(pathlib.Path(a.contract).read_text(encoding='utf-8'));versions={'stanza':stanza.__version__,'torch':str(torch.__version__),'python':platform.python_version()}
 if versions!=contract['model_versions']:raise ValueError('Runtime mismatch')
 for rel,sha in contract['model_sha256'].items():
  if hashlib.sha256((pathlib.Path(a.models)/rel).read_bytes()).hexdigest()!=sha:raise ValueError('Model identity mismatch: '+rel)
 def deny(*a,**k):raise RuntimeError('English measurement is offline')
 socket.socket.connect=deny;socket.create_connection=deny
 raw=pathlib.Path(a.text).read_bytes();text=raw.decode('utf-8')
 if len(re.findall(r'[\u3400-\u9fff]',text))>max(10,len(text)*.05):raise ValueError('Use the Chinese instrument for Chinese prose')
 paras,excluded=prepare(text);nlp=stanza.Pipeline('en',dir=a.models,processors=contract['processors'],package=None,download_method=None,use_gpu=False,verbose=False)
 out=compute([nlp(p) for p in paras],paras);out.update({'text_sha256':hashlib.sha256(raw).hexdigest(),'measured_projection_sha256':hashlib.sha256('\n\n'.join(paras).encode()).hexdigest(),'excluded_short_paragraph_indices':excluded,'instrument_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'reference_contract_sha256':contract['contract_sha256'],'interpretation':'Same-language marginal diagnostics, not authorship similarity or quality. Currency is retained; explicit dollar math is elided. Original text remains unchanged.'})
 if a.profile:
  pr=json.loads(pathlib.Path(a.profile).read_text(encoding='utf-8'))
  if pr.get('schema')=='style-study-results/1':pr=pr['reference_blog']['development_profiles']
  n=out['lexical_words'];band='<=500' if n<=500 else '501-2000' if n<=2000 else '2001-5000' if n<=5000 else '>5000';key='genre_length/'+a.genre+'/'+band;ref=pr['groups'].get(key)
  if not ref or ref['article_count']<10:key='genre/'+a.genre;ref=pr['groups'].get(key)
  ds={}
  if ref:
   for k,v in out['features'].items():
    r=ref['features'].get(k)
    if r and v is not None and r['family_weighted_q10'] is not None:ds[k]={'value':v,'q10':r['family_weighted_q10'],'q90':r['family_weighted_q90'],'within_marginal_interval':r['family_weighted_q10']<=v<=r['family_weighted_q90']}
  out['comparison']={'stratum':key,'reference_articles':ref['article_count'] if ref else 0,'features':ds,'joint_acceptance':None,'interpretation':'Review differences; do not rewrite correct mathematics just to satisfy marginal intervals.'}
 with pathlib.Path(a.out).open('x',encoding='utf-8') as handle:handle.write(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:out[k] for k in ['status','lexical_words','lexical_sentences','text_sha256']},indent=2))
 return 0
def main():
 try:return _run()
 except (ValueError,TypeError,OSError,ImportError,KeyError) as exc:
  print('style-compiler-english: '+str(exc),file=sys.stderr);return 2
if __name__=='__main__':main()
