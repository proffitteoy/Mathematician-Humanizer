"""Independent invariant and synthetic brute-force verification; no external code."""
import ast,collections,hashlib,json,math,pathlib,random,time,unicodedata,re
D=pathlib.Path(__file__).resolve().parents[1];P=D/'public';R=D/'private'
# Compile only the algorithm functions; never rerun corpus preparation on import.
source=(P/'prepare_cohort.py').read_text(); tree=ast.parse(source)
functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['digest','norm','join','line_spans','block_spans','sentence_spans','support']]
ns=globals().copy();ns['CPU']=time.process_time();compiled=compile(ast.Module(body=functions,type_ignores=[]),'<audited preparation functions>','exec');exec(compiled,ns)
results=[];rng=random.Random(640781)
for k,minchars in [(3,12),(5,50)]:
 docs=[]
 alphabet='甲乙丙丁戊己庚辛壬癸春夏秋冬天地山水木火人心思考语言中文'
 for group in range(20):
  base=''.join(rng.choice(alphabet) for _ in range(90+group))
  for edits in [0,1,2,5,10]:
   chars=list(base)
   for _ in range(edits):chars[rng.randrange(len(chars))]=rng.choice(alphabet)
   docs.append((len(docs),'synthetic',''.join(chars)))
 # Unique text set matching algorithm's deliberate exact-dedup stage.
 docs=list({t:(i,a,t) for i,a,t in docs}.values())
 observed=set();ns['link']=lambda a,b,*args:observed.add(tuple(sorted((a,b))))
 summary=ns['join'](docs,k,minchars,'synthetic_near')
 expected=set()
 for a,(_,_,ta) in enumerate(docs):
  sa={ta[z:z+k] for z in range(len(ta)-k+1)}
  for ib,_,tb in docs[:a]:
   sb={tb[z:z+k] for z in range(len(tb)-k+1)};inter=len(sa&sb)
   if 5*inter>=4*len(sa|sb):expected.add(tuple(sorted((docs[a][0],ib))))
 assert observed==expected,(k,len(observed),len(expected))
 results.append({'check':'prefix_join_vs_all_pairs_synthetic','gram_n':k,'documents':len(docs),'expected_positive_pairs':len(expected),'actual_positive_pairs':len(observed),'pass':True})
for t,blocks,lines in [('甲\r\n乙',1,2),('甲\r\n\r\n乙',2,2),('甲\r\r乙',2,2),('甲\n \t\n乙',2,2),('\n\n甲\n',1,1),('甲\\n乙',1,1)]:
 s=ns['support'](t);assert s['blocks']==blocks and s['nonempty_lines']==lines
results.append({'check':'CR_LF_CRLF_blank_line_and_literal_escape_cases','cases':6,'pass':True})
cohort=[json.loads(x) for x in (R/'cohort_identity_views.jsonl').read_text().splitlines()];components=json.loads((R/'components_and_splits.json').read_text());agg=json.loads((P/'aggregate_audit.json').read_text());freeze=json.loads((R/'freeze_manifest.json').read_text())
assert len(cohort)==3000 and len({r['pair_id'] for r in cohort})==3000
families=collections.defaultdict(list)
for row in cohort:families[row['question_family_id']].append(row)
assert len(families)==2987
for rr in families.values():
 assert len({r['split'] for r in rr})==1
 assert len({r['component_id'] for r in rr})==1
 assert abs(sum(r['equal_question_family_answer_weight'] for r in rr)-1)<1e-12
 assert all(r['fit_eligible_arms']==(['human','chatgpt'] if r['split'] in ('train','dev') else []) for r in rr)
assert all(r['split']!='test' for r in cohort if r['component_development_exposed'])
component_map={c['component_id']:c for c in components};assert len(component_map)==len(components)
assert sum(len(c['members']) for c in components)==3000
assert sum(len(c['question_families']) for c in components)==2987
# Independently resolve each original raw byte slice and verify identity, exact shared prompt/human.
raw={f:(D/'raw'/f).read_bytes() for f in ['qazh_chatgpt.jsonl','qazh_davinci.jsonl']}
for row in cohort:
 decoded=[]
 for key in ['chatgpt','davinci']:
  rr=row['raw_rows'][key];d=json.loads(raw[rr['file']][rr['offset_bytes']:rr['offset_bytes']+rr['length_bytes']]);decoded.append(d)
  assert type(d['source_ID'])==type(row['source_ID']) and d['source_ID']==row['source_ID'] and d['source']==row['source']
  assert hashlib.sha256(d['machine_text'].encode()).hexdigest()==row['arms'][key]['original_text_sha256']
 assert decoded[0]['prompt']==decoded[1]['prompt'] and decoded[0]['human_text']==decoded[1]['human_text']
 assert hashlib.sha256(decoded[0]['human_text'].encode()).hexdigest()==row['arms']['human']['original_text_sha256']
for name,sha in freeze['private_files'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==sha
assert hashlib.sha256((P/'prepare_cohort.py').read_bytes()).hexdigest()==freeze['code_sha256']
assert hashlib.sha256((P/'SCHEMA_AMENDMENT_1.md').read_bytes()).hexdigest()==freeze['schema_amendment_sha256']
results += [{'check':'full_byte_offset_identity_and_cross_generator_equality','paired_records':3000,'pass':True},{'check':'equal_question_family_weights_and_component_split_isolation','question_families':2987,'pass':True},{'check':'exposed_family_test_exclusion_and_davinci_fit_exclusion','pass':True},{'check':'frozen_private_manifest_and_code_hashes','pass':True}]
receipt={'passed':True,'checks':results,'code_sha256':freeze['code_sha256'],'verification_code_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'note':'Synthetic checks validate implementation; real cohort invariants use raw byte slices without printing or redistributing text.'}
(P/'verification_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
