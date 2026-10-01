"""Independent synthetic-only mechanics checks; writes no source files."""
import hashlib,json,math,random,statistics,unicodedata
from dataclasses import asdict,replace
from research.surface.adapter import SourceView,SourceObservation,Interval,ContextRegion,Projection,make_projection,measure
from style_compiler.contracts import Context,Document,Leakage,Provenance,text_hash
from style_compiler.features import PRIMARY_IDS,extract
from style_compiler.segmentation import segment

rng=random.Random(1012026)
counts={'bitmap_projections':0,'full_source_equivalences':0,'pooled_pair_cases':0,'identity_checks':0}
def source(t):
 s=SourceView(text_hash('independent original synthetic archive'),'synthetic.jsonl',0,0,'independent/1',0,'/text','synthetic',text_hash(t),len(t))
 return SourceObservation(s,t)
def project(o,mask,split=False):
 ints=[]; i=0
 while i<len(mask):
  if not mask[i]: i+=1; continue
  j=i+1
  while j<len(mask) and mask[j] and not split: j+=1
  ints.append(Interval(i,j)); i=j
 return make_projection(o.source,tuple(ints),annotation_profile='independent-synthetic/1',annotation_status='synthetic_fixture')
def quant(v,q):
 s=sorted(v); x=(len(s)-1)*q; k=int(x)
 return s[k] if k==len(s)-1 else (1-(x-k))*s[k]+(x-k)*s[k+1]
def rank(v):
 return [1+sum(y<x for y in v)+(sum(y==x for y in v)-1)/2 for x in v]
def rho(pairs):
 if len(pairs)<3:return None
 a,b=rank([x for x,y in pairs]),rank([y for x,y in pairs]); am,bm=sum(a)/len(a),sum(b)/len(b)
 an,bn=[x-am for x in a],[x-bm for x in b]
 scale=math.sqrt(sum(x*x for x in an)*sum(x*x for x in bn))
 return sum(x*y for x,y in zip(an,bn))/scale if scale else None
def check(t,mask):
 o=source(t); p=project(o,mask); r=measure(o,p); v=r['target_projection']; c=v['counts']; fs=v['features']; ps,ss=segment(t)
 complete=lambda a:all(mask[a.start:a.end]); clipped=lambda a:any(mask[a.start:a.end]) and not complete(a)
 pp=[a for a in ps if complete(a)]; sp=[a for a in ss if complete(a)]; pc=[a.index for a in ps if clipped(a)]; sc=[a.index for a in ss if clipped(a)]
 pairs=[(a,b) for a,b in zip(ss,ss[1:]) if all(mask[a.start:b.end])]
 endpoint_pairs=[(a,b) for a,b in zip(ss,ss[1:]) if complete(a) and complete(b)]
 assert v['paragraphs']==[asdict(a) for a in pp]
 assert v['sentences']==[asdict(a) for a in sp]
 assert v['clipped_paragraph_indices']==pc and v['clipped_sentence_indices']==sc
 assert v['adjacent_pairs']==[{'left_source_sentence_index':a.index,'right_source_sentence_index':b.index} for a,b in pairs]
 assert c['target_codepoints']==sum(mask)
 chars=sum(keep and unicodedata.category(ch)[0] in 'LN' for ch,keep in zip(t,mask))
 assert c['target_content_chars']==chars
 assert c['target_codepoints']+c['excluded_codepoints']==len(t)
 assert c['target_content_chars']+c['excluded_content_chars']==sum(unicodedata.category(ch)[0] in 'LN' for ch in t)
 assert c['eligible_adjacent_pairs']==len(pairs)
 assert c['source_pairs_with_complete_target_endpoints']==len(endpoint_pairs)
 assert c['source_adjacent_pairs']==len(pairs)+c['endpoint_complete_pairs_blocked_by_excluded_gap']+c['source_pairs_without_complete_target_endpoints']
 covered=[0]*len(t)
 for a in p.targets+tuple(x.interval for x in p.excluded_context):
  for i in range(a.start,a.end):covered[i]+=1
 assert covered==[1]*len(t)
 lengths=[a.content_chars for a in sp]; med=statistics.median(lengths) if lengths else None
 single=sum(sum(s.paragraph_index==a.index for s in ss)==1 for a in pp)
 d=sum(abs(b.content_chars-a.content_chars) for a,b in pairs)
 expected={'F002':1000*len(pp)/chars if chars else None,'F003':single/len(pp) if pp else None,'F013':med,'F014':quant(lengths,.75)-quant(lengths,.25) if lengths else None,'F015':quant(lengths,.9) if lengths else None,'F016':statistics.median(abs(x-med) for x in lengths)/med if lengths else None,'F024':d/len(pairs)/med if pairs else None,'F025':rho([(a.content_chars,b.content_chars) for a,b in pairs])}
 for key,want in expected.items():
  clipped_count=len(pc if key in ('F002','F003') else sc)
  f=fs[key]
  if clipped_count:
   assert f['value'] is f['raw_numerator'] is f['denominator'] is None
   assert f['applicability']=='inapplicable_clipped_units'
   assert f['missing_reason']==('partial_source_paragraphs' if key in ('F002','F003') else 'partial_source_sentences')
  elif want is None:assert f['value'] is None and f['missing_reason']
  else:assert math.isclose(f['value'],want,rel_tol=1e-12,abs_tol=1e-12),(t,mask,key,f['value'],want)
  assert not f['eligible_for_comparison'] and f['measurement_error_interval'] is None
  assert f['opportunity']['clipped_unit_count']==clipped_count
  assert f['status']==('unavailable' if f['value'] is None else 'zero_observed' if f['value']==0 else 'observed')
 assert [fs[k]['opportunity']['observed_count'] for k in PRIMARY_IDS]==[chars,len(pp),len(sp),len(sp),len(sp),len(sp),len(pairs),len(pairs)]
 assert v['pair_absolute_difference_sum']==d
 json.dumps(r,allow_nan=False)
 # Inserting an annotation boundary at every retained codepoint preserves union, units and arithmetic.
 split=measure(o,project(o,mask,True)); sv=split['target_projection']
 assert sv['features']==fs and sv['sentences']==v['sentences'] and sv['paragraphs']==v['paragraphs'] and sv['adjacent_pairs']==v['adjacent_pairs']
 assert split['target_component_text_sha256']==r['target_component_text_sha256']
 for k in c:
  if k!='target_interval_count':assert sv['counts'][k]==c[k]
 counts['bitmap_projections']+=1

def full_equivalence(t):
 o=source(t); r=measure(o,project(o,[True]*len(t)))
 d=Document('independent-synthetic',t,Context('zh','synthetic','synthetic','synthetic'),Provenance('synthetic_test','independent','original synthetic fixture',True,True),Leakage('synthetic-work','synthetic-lineage','synthetic-content','synthetic-duplicate'))
 baseline=extract(d)
 for view in ('raw_source','target_projection'):
  for k in PRIMARY_IDS:
   assert r[view]['features'][k]['value']==baseline['features'][k]['value'],(t,k)
   assert r[view]['features'][k]['status']==baseline['features'][k]['status']
 counts['full_source_equivalences']+=1

fixtures=['','甲。乙乙。','甲。\r\n乙。','甲🙂。乙。','e\u0301。𠀀！','3.1. X.','甲。!?乙。','\t甲。\n🙂\n乙。','\r\n\t \u200d🙂']
for t in fixtures:
 full_equivalence(t)
 for m in range(1<<len(t)):check(t,[bool(m>>i&1) for i in range(len(t))])
alphabet='甲乙丙abcX９0。！？!. \r\n\t\u2028\u200d\u0301🙂𠀀”'
for j in range(600):
 t=''.join(rng.choice(alphabet) for _ in range(rng.randrange(101)))
 full_equivalence(t);check(t,[rng.random()<.7 for _ in t])
for j in range(400):
 lines=['甲'*rng.randint(1,15)+'。' for _ in range(rng.randint(4,15))]
 t='\n'.join(lines);mask=[]
 for i,line in enumerate(lines):
  mask.extend([rng.random()<.75]*len(line))
  if i<len(lines)-1:mask.append(rng.random()<.8)
 check(t,mask);counts['pooled_pair_cases']+=1
# Source equality and independent canonical digest reconstruction.
o=source('甲。乙。');p=project(o,[True,True,False,False]);r=measure(o,p)
for key,payload in [('source_view_sha256',r['source']),('projection_sha256',r['projection']),('measurement_profile_sha256',r['measurement_profile']),('observation_key_sha256',{'source':r['source'],'profile':r['measurement_profile'],'projection':r['projection']})]:
 assert r[key]==hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest();counts['identity_checks']+=1
for field,value in [('member_name','different.jsonl'),('record_index',1),('record_byte_offset',1),('scanner_version','independent/2'),('view_index',1),('json_pointer','/original'),('role','different'),('archive_sha256',text_hash('different'))]:
 other=SourceObservation(replace(o.source,**{field:value}),o.text)
 try:measure(other,p)
 except ValueError:pass
 else:raise AssertionError(field)
 counts['identity_checks']+=1
print(json.dumps({'status':'PASS','seed':1012026,'counts':counts,'python_unicode_version':unicodedata.unidata_version},indent=2))
