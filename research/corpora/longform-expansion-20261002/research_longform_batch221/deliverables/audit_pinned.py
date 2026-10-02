#!/usr/bin/env python3
"""Reproducible structural/language/duplication diagnostics, no model admission.
Consumes only the private verified acquisition cache; no network or source execution.
The scanner partitions original bytes without deleting or stitching role boundaries.
"""
import collections, datetime, hashlib, importlib.util, itertools, json, pathlib, re, resource, signal, statistics, time, unicodedata
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2)); signal.alarm(590);START=time.monotonic()
ROOT=pathlib.Path(__file__).resolve().parents[1]; P=ROOT/'private'; D=ROOT/'deliverables'; PREV=ROOT.parent/'research_longform_acquisition'
HAN=re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff]'); LATIN=re.compile(r'[A-Za-z]'); PROSE={'prose_candidate','list_continuation_prose'}
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def norm(t):return re.sub(r'\s+','',unicodedata.normalize('NFKC',t)).casefold()

def blocks(raw):
 lines=raw.decode('utf-8').splitlines(keepends=True);out=[];pos=0;meta=False;fence=None;listscope=False;html=None;math=False
 for i,line in enumerate(lines):
  s=line.strip();role='prose_candidate'
  if i==0 and s=='---':meta=True;role='frontmatter'
  elif meta:
   role='frontmatter'
   if s in {'---','...'}:meta=False
  elif fence:
   role='fenced_code'
   if re.fullmatch(re.escape(fence[0])+'{'+str(fence[1])+r',}\s*',s):fence=None
  elif (m:=re.match(r'^(`{3,}|~{3,})',s)):role='fenced_code';fence=(m[1][0],len(m[1]))
  elif html:
   role='html_block'
   if html in s.lower():html=None
  elif s.startswith('<!--'):
   role='html_block'; html=None if '-->' in s else '-->'
  elif (m:=re.match(r'^<(script|style|pre|table|div)(?:\s|>)',s,re.I)):
   role='html_block';end='</'+m[1].lower()+'>';html=None if end in s.lower() else end
  elif math:
   role='display_math'
   if s.endswith('$$'):math=False
  elif s.startswith('$$'):role='display_math';math=not(len(s)>2 and s.endswith('$$'))
  elif not s:role='blank'
  elif s.startswith('>'):role='marked_quote'
  elif s.startswith('!['):role='image_reference'
  elif re.match(r'^#{1,6}\s',s):role='heading';listscope=False
  elif re.match(r'^([-*_])(?:\s*\1){2,}$',s):role='thematic_break';listscope=False
  elif re.match(r'^\[\^[^]]+\]:',s):role='footnote_definition';listscope=False
  elif re.match(r'^\[[^]]+\]:',s):role='reference_definition';listscope=False
  elif s.count('|')>=2 and (s.startswith('|') or re.match(r'^:?-{3,}',s)):role='table_candidate';listscope=False
  elif re.match(r'^(?:[-+*]|\d+[.)])\s+',s):role='list_item';listscope=True
  elif line.startswith(('    ','\t')):role='list_continuation_prose' if listscope else 'indented_ambiguous'
  elif s.startswith('<'):role='html_or_comment'
  elif re.match(r'^(?:推荐人|推薦人|链接|連結|题目|題目)\s*[:：]',s):role='bibliographic_or_contributor_label'
  elif re.match(r'^https?://\S+$',s):role='standalone_url'
  else:listscope=False
  end=pos+len(line.encode('utf-8'))
  if out and out[-1]['role']==role and role not in {'heading','list_item','image_reference','thematic_break'}:
   out[-1]['end_byte']=end;out[-1]['line_end']=i+1
  else:out.append({'role':role,'start_byte':pos,'end_byte':end,'line_start':i+1,'line_end':i+1})
  pos=end
 for b in out:
  piece=raw[b['start_byte']:b['end_byte']];t=piece.decode('utf-8')
  b.update(sha256=sha(piece),utf8_bytes=len(piece),unicode_characters=len(t),han_characters=len(HAN.findall(t)),ascii_latin_letters=len(LATIN.findall(t)))
 assert out and out[0]['start_byte']==0 and out[-1]['end_byte']==len(raw)
 assert all(a['end_byte']==b['start_byte'] for a,b in zip(out,out[1:]))
 return out,{'unclosed_frontmatter':meta,'unclosed_code_fence':fence is not None,'unclosed_html_block':html is not None,'unclosed_display_math':math}

def stats(values):return {'total':sum(values),'min':min(values),'median':statistics.median(values),'max':max(values)} if values else {'total':0,'min':None,'median':None,'max':None}

def aggregate(rows):
 role=collections.defaultdict(collections.Counter)
 for r in rows:
  for key,counts in r['role_totals'].items():role[key].update(counts)
 return {'documents':len(rows),'raw_source_bytes':sum(r['raw_source_bytes'] for r in rows),'source_unicode_characters':stats([r['source_unicode_characters'] for r in rows]),'source_han_characters':stats([r['source_han_characters'] for r in rows]),'prose_candidate_unicode_characters':stats([r['prose_candidate_unicode_characters'] for r in rows]),'prose_candidate_han_characters':stats([r['prose_candidate_han_characters'] for r in rows]),'prose_candidate_paragraph_like_blocks':stats([r['prose_candidate_paragraph_like_blocks'] for r in rows]),'longform_screen_ge1000han_ge8blocks':sum(r['longform_screen'] for r in rows),'legacy_sample_scanner_longform_count':sum(r['legacy_longform_screen'] for r in rows),'longform_legacy_v2_disagreement_count':sum(r['longform_screen']!=r['legacy_longform_screen'] for r in rows),'script_diagnostic_counts':dict(collections.Counter(r['script_diagnostic'] for r in rows)),'whole_source_script_diagnostic_counts':dict(collections.Counter(r['whole_source_script_diagnostic'] for r in rows)),'role_totals':{k:dict(v) for k,v in sorted(role.items())},'documents_with_role':dict(collections.Counter(k for r in rows for k,v in r['role_totals'].items() if v['utf8_bytes']>0)),'lexical_review_flag_document_counts':dict(collections.Counter(k for r in rows for k,v in r['lexical_review_flags'].items() if v)),'unclosed_syntax_document_counts':dict(collections.Counter(k for r in rows for k,v in r['unclosed_syntax'].items() if v))}

def groups(counter):return [ids for ids in counter.values() if len(ids)>1]

def main():
 state=json.load(open(P/'final_identity_manifest.json'));receipts=state['candidates']
 assert len(receipts)==221
 spec=importlib.util.spec_from_file_location('legacy_sample_scanner',PREV/'deliverables/reproduce_sample.py');legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
 result=[];spans_private=[];author_fields=collections.defaultdict(collections.Counter);doc_raw=collections.defaultdict(list);doc_norm=collections.defaultdict(list);paragraphs=collections.defaultdict(list);shingles={};sampleids=set();legacy_repro_checks=0
 old=json.load(open(PREV/'deliverables/candidate_manifest.json'))['documents']
 for r in old:
  b=(PREV/'payloads'/r['source_id']/r['source_path']).read_bytes();ss=legacy.blocks(b,r['source_id'],r['id'].removeprefix(r['source_id']+'-'))
  assert sha(b)==r['sha256'];h=sum(x['han_characters'] for x in ss if x['role'] in PROSE);n=sum(x['role'] in PROSE for x in ss)
  assert h==r['prose_candidate_han'] and n==r['prose_candidate_blocks'];legacy_repro_checks+=1
 allinputs=[(r,(P/r['private_relative_path']).read_bytes(),False) for r in receipts if r['status']=='verified']+[(r,(PREV/'payloads'/r['source_id']/r['source_path']).read_bytes(),True) for r in old]
 for r,raw,isprior in allinputs:
  identifier=r.get('id',r['source_id']+':'+r['source_path']);text=raw.decode('utf-8')
  assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['git_blob_sha1']
  assert sha(raw)==r['sha256']
  spans,unclosed=blocks(raw);role=collections.defaultdict(collections.Counter);prose=[]
  for idx,s in enumerate(spans):
   role[s['role']].update({k:s[k] for k in ['utf8_bytes','unicode_characters','han_characters','ascii_latin_letters']});role[s['role']]['blocks']+=1
   if s['role'] in PROSE:
    piece=raw[s['start_byte']:s['end_byte']].decode('utf-8');prose.append(piece)
    if s['han_characters']>=40 and len(piece)>=100:paragraphs[sha(norm(piece).encode())].append({'document':identifier,'span_index':idx,'prior_sample':isprior})
  body='\n'.join(raw[s['start_byte']:s['end_byte']].decode('utf-8') for s in spans if s['role']!='frontmatter')
  doc_raw[sha(raw)].append(identifier);doc_norm[sha(norm(body).encode())].append(identifier)
  # Five-codepoint shingles, only within prose spans. No stitching across headings/quotes/code.
  gramset=set()
  for piece in prose:
   n=norm(piece)
   gramset.update(n[i:i+5] for i in range(max(0,len(n)-4)))
  shingles[identifier]=gramset
  if isprior:sampleids.add(identifier);continue
  front=text.split('---',2)[1] if text.startswith('---') else '';am=re.search(r'^author:\s*(.*?)\s*$',front,re.M);av=am[1].strip().strip("\"'") if am else None;author_fields[r['source_id']]['explicit_nonempty' if av else 'explicit_empty' if am else 'absent']+=1
  oldspans=legacy.blocks(raw,r['source_id'],'batch-unreviewed')
  ph=sum(s['han_characters'] for s in spans if s['role'] in PROSE);pc=sum(s['unicode_characters'] for s in spans if s['role'] in PROSE);pl=sum(s['ascii_latin_letters'] for s in spans if s['role'] in PROSE);pb=sum(s['role'] in PROSE for s in spans)
  ratio=ph/(ph+pl) if ph+pl else 0
  row={'id':identifier,'source_id':r['source_id'],'source_path':r['source_path'],'source_url':r['source_url'],'raw_sha256':sha(raw),'git_blob_sha1':r['git_blob_sha1'],'raw_source_bytes':len(raw),'source_unicode_characters':len(text),'source_han_characters':len(HAN.findall(text)),'prose_candidate_unicode_characters':pc,'prose_candidate_han_characters':ph,'prose_candidate_paragraph_like_blocks':pb,'longform_screen':ph>=1000 and pb>=8,'legacy_longform_screen':sum(s['han_characters'] for s in oldspans if s['role'] in PROSE)>=1000 and sum(s['role'] in PROSE for s in oldspans)>=8,'script_diagnostic':'Han-dominant' if ratio>=.5 else 'mixed-Han-Latin' if ratio>=.1 else 'Latin-heavy-or-other' if ph+pl else 'no-eligible-prose-letters','whole_source_script_diagnostic':'Han-dominant' if len(HAN.findall(text))/(len(HAN.findall(text))+len(LATIN.findall(text)))>=.5 else 'mixed-or-Latin-heavy','prose_han_over_han_plus_ascii_latin':ratio,'role_totals':{k:dict(v) for k,v in role.items()},'unclosed_syntax':unclosed,'lexical_review_flags':{'repeated_named_contributor_pattern':len(re.findall(r'推荐人\s*[:：]',text))>=2,'marked_quotation':any(s['role']=='marked_quote' for s in spans),'inline_quote_opening_mark':bool(re.search('[“「『]',text)),'reprint_translation_rights_terms':bool(re.search(r'转载|轉載|译者|譯者|译文|譯文|翻译|翻譯|版权|版權|copyright',text,re.I)),'minor_family_terms':bool(re.search(r'儿童|兒童|小孩|孩子|儿子|兒子|女儿|女兒|幼儿|幼兒|未成年|小学|小學',text)),'email_like_string':bool(re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',text)),'administrative_call_terms':bool(re.search(r'报名|報名|注册|註冊|登记|登記|填.{0,4}表|订阅|訂閱|购买|購買',text))},'production_assistance_status':'unknown','model_admitted':False}
  result.append(row);spans_private.append({'id':identifier,'source_sha256':sha(raw),'spans':spans})
  if time.monotonic()-START>480:raise RuntimeError('Audit nearing wall limit')
 # Exhaustive within-collected-set comparisons. Thresholds are diagnostic, not deletion decisions.
 ids=list(shingles);near=[];pair_count=0
 for i,a in enumerate(ids):
  A=shingles[a]
  for b in ids[i+1:]:
   if a in sampleids and b in sampleids:continue
   B=shingles[b];pair_count+=1
   if not A or not B:continue
   common=len(A&B);j=common/(len(A)+len(B)-common);c=common/min(len(A),len(B))
   if j>=.8 or (c>=.8 and common>=200):near.append({'a':a,'b':b,'jaccard':j,'smaller_set_containment':c,'shared_5grams':common,'cross_source':a.split(':')[0].split('-')[0]!=b.split(':')[0].split('-')[0],'includes_prior_sample':a in sampleids or b in sampleids})
 pg=[v for v in paragraphs.values() if len({x['document'] for x in v})>1 and any(not x['prior_sample'] for x in v)]
 exact=[v for v in groups(doc_raw) if any(x not in sampleids for x in v)]
 normalized=[v for v in groups(doc_norm) if any(x not in sampleids for x in v)]
 write(P/'document_measurements.json',result);write(P/'structure_spans.json',spans_private);write(P/'duplication_review.json',{'exact_source_groups':exact,'normalized_nonfrontmatter_groups':normalized,'repeated_long_paragraph_groups':pg,'near_duplicate_pairs':near})
 summary={'schema':'pinned-longform-aggregate-audit/2.0','original_candidate_denominator':221,'acquired_verified_measured':len(result),'failed_or_unattempted':221-len(result),'overall':aggregate(result),'screen_positive_subset':aggregate([r for r in result if r['longform_screen']]),'frontmatter_author_field_counts':{s:dict(c) for s,c in author_fields.items()},'by_source':{s:aggregate([r for r in result if r['source_id']==s]) for s in ['yihui','yufree']},'longform_definition':'At least 1000 Han codepoints and 8 contiguous prose/list-continuation blocks; operational diagnostic only. Inline quotes, Markdown/link syntax, and unresolved indirect borrowing can remain.','language_method':'Script proxy only: Han/(Han+ASCII Latin letters) in prose-role spans; >=.5 Han-dominant, >=.1 mixed, else Latin-heavy/other, or no eligible letters. Whole-source proxy also reported; excludes no roles and is influenced by code and citations. Not a validated language ID or a human-origin detector.','characters_definition':'Unicode codepoints of original source spans, including syntax and whitespace. Han count uses U+3400-4DBF and U+4E00-9FFF, not Chinese words.','paragraph_definition':'Contiguous same-role source lines separated by blanks/role changes; not gold linguistic paragraphs. Lists excluded except continuation prose.','duplication':{'scope':'Verified new batch plus previous 13 locally held sample files; no search outside this collected set','comparison_documents':len(allinputs),'exact_raw_duplicate_groups':len(exact),'normalized_body_duplicate_groups':len(normalized),'normalized_body_method':'NFKC, Unicode whitespace removal, casefold; omit frontmatter; do not strip source content roles','repeated_long_prose_paragraph_groups':len(pg),'documents_in_repeated_long_prose_paragraph_groups':len({x['document'] for g in pg for x in g}),'paragraph_method':'Only whole prose/list-continuation spans >=100 source codepoints and >=40 Han; NFKC, whitespace removal, casefold. Cross-document matches only.','exhaustive_document_pairs_compared':pair_count,'high_overlap_pairs':len(near),'high_overlap_cross_source_pairs':sum(x['cross_source'] for x in near),'high_overlap_including_prior_sample_pairs':sum(x['includes_prior_sample'] for x in near),'high_overlap_method':'Exact sets of normalized 5-codepoint shingles inside each prose span only. Flag Jaccard >=.8 OR smaller-set containment >=.8 with >=200 shared shingles. A flag is review evidence, not plagiarism proof; absence does not rule out paraphrase or shared sources.'},'prior_13_same_scanner_reproductions_passed':legacy_repro_checks,'raw_redistributed':False,'verified_unaided_human_documents':0,'model_admitted_documents':0,'additional_declared_blog_bylines':0,'declared_blog_bylines_reused':2,'source_rights':'CC BY-NC-SA 4.0 primary-source notices; noncommercial research only, subject to embedded third-party content and other rights.','limitations':['Convenience stratum enriched by source-byte length, two technical-adjacent blog bylines, 2015–2021; not representative of human writing','Scanner is not a complete CommonMark parser; lazy blockquotes, nested lists, inline code/quotes, footnotes and indirect quotations may be ambiguous','Lexical flags are review triage, not validated privacy/rights/translation labels; no document has full privacy or author-role clearance','No genres assigned from byte length or automatic keywords; no clean author-only prose claim','Dates and bylines are source declarations and repository history, not independent evidence of human composition or no AI assistance'],'resources':{'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'elapsed_seconds':round(time.monotonic()-START,3),'memory_limit_bytes':512*1024**2,'wall_limit_seconds':590}}
 write(D/'aggregate_audit.json',summary)
 print(json.dumps({'acquired':len(result),'overall':summary['overall'],'duplication':summary['duplication'],'resources':summary['resources']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
