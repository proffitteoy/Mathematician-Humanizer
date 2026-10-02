#!/usr/bin/env python3
"""Frozen standard-library structural-view evaluator. No model, source-text export or corpus release."""
import argparse, collections, hashlib, json, math, pathlib, re, resource, statistics, sys, time, xml.etree.ElementTree as ET
HERE=pathlib.Path(__file__).resolve().parent
BASE=HERE.parent/'research_discourse_validation'
CACHE=pathlib.Path('/tmp/gcdt-validation-private')
def norm(s):return ''.join(s.split())
def stable(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(obj):return hashlib.sha256(stable(obj).encode()).hexdigest()
def spans(parts):
 out=[];p=0
 for text in parts:
  n=len(norm(text));out.append([p,p+n]);p+=n
 return out

def load_layout(xml_bytes,tok_text):
 root=ET.fromstring(xml_bytes); body=''.join(root.itertext())
 paras=[norm(x) for x in re.split(r'\n\s*\n',body) if norm(x)]
 slines=[s for s in tok_text.splitlines() if norm(s)]
 sentences=[norm(s) for s in slines]
 assert norm(body)==''.join(sentences),'xml_sentence_stream_mismatch'
 toks=[norm(t) for s in slines for t in s.split()]
 return {'text':norm(body),'paragraphs':spans(paras),'sentences':spans(sentences),'tokens':spans(toks),'sentence_keys':[digest(s) for s in sentences],'metadata':dict(root.attrib)}

def read_graph(rs3_bytes):
 root=ET.fromstring(rs3_bytes); rels={e.attrib['name']:e.attrib['type'] for e in root.findall('header/relations/rel')}
 body=root.find('body'); nodes={};segs=[]
 for e in body:
  assert e.tag in ('segment','group'),'unexpected_rs3_element'
  a=dict(e.attrib);id=a['id'];assert id not in nodes,'duplicate_id'
  nodes[id]={'id':id,'kind':e.tag,'group_type':a.get('type'),'parent':a.get('parent'),'relation':a.get('relname')}
  if e.tag=='segment':segs.append((id,norm(''.join(e.itertext()))))
 assert [int(x[0]) for x in segs]==sorted(int(x[0]) for x in segs),'unordered_segment_ids'
 return {'nodes':nodes,'relations':rels,'edu_ids':[x[0] for x in segs],'edu_spans':spans([x[1] for x in segs]),'text':''.join(x[1] for x in segs)}

def nuclearity(n,rels):
 if n['parent'] is None:return 'ROOT'
 if n['relation']=='span' or rels.get(n['relation'])=='multinuc':return 'N'
 if rels.get(n['relation'])=='rst':return 'S'
 return 'unknown'

def enrich(g):
 nodes=g['nodes'];children={k:[] for k in nodes};roots=[]
 for k,n in nodes.items():
  if n['parent'] is None:roots.append(k)
  else:
   assert n['parent'] in nodes,'missing_parent';children[n['parent']].append(k)
 assert len(roots)==1,'not_single_root'
 root=roots[0];positions={x:i for i,x in enumerate(g['edu_ids'])};yields={};paths={};busy=set()
 def visit(k,path):
  assert k not in busy,'cycle';assert k not in paths,'revisited_vertex';busy.add(k);paths[k]=path+[k]
  ys=([positions[k]] if k in positions else [])
  for c in children[k]:ys.extend(visit(c,path+[k]))
  assert len(ys)==len(set(ys)),'duplicate_leaf';ys=sorted(ys);assert ys,'empty_group';yields[k]=ys;busy.remove(k);return ys
 visit(root,[]);assert len(paths)==len(nodes),'disconnected_graph'
 return {'root':root,'children':children,'yields':yields,'paths':paths,'nuclearities':{k:nuclearity(n,g['relations']) for k,n in nodes.items()}}

def overlaps(a,b):return a[0]<b[1] and b[0]<a[1]
def view(layout,g):
 assert layout['text']==g['text'],'layout_edu_stream_mismatch'
 e=enrich(g); projections=[]
 for a in layout['paragraphs']:
  edus=[i for i,s in enumerate(g['edu_spans']) if overlaps(a,s)]
  eset=set(edus)
  projections.append({'span':a,'sentences':[i for i,s in enumerate(layout['sentences']) if overlaps(a,s)],'edus':edus,'nodes':sorted(k for k,ys in e['yields'].items() if eset.intersection(ys))})
 return {'paragraphs':projections,'sentences':layout['sentences'],'tokens':layout['tokens'],'sentence_keys':layout['sentence_keys'],'edu_ids':g['edu_ids'],'edu_spans':g['edu_spans'],'nodes':g['nodes'],'relations':g['relations'],'structure':e,'missing_layers':{x:{'value':None,'reason':'no_gold_layer'} for x in ['entity_identity','coreference','bridging','argument_support_attack','argument_truth','coherence_quality','perceptual_rhythm','human_AI_provenance']}}

def measure(v):
 e=v['structure']; nodes=v['nodes']; eduids=v['edu_ids']; ps=v['paragraphs']; groups=[k for k,n in nodes.items() if n['kind']=='group'];depths=[len(e['paths'][k])-1 for k in eduids]
 crossing=sum(sum(k in p['nodes'] for p in ps)>1 for k in groups)
 lcas=[];straddling=0
 for p in ps[:-1]:
  b=p['span'][1]
  left=[i for i,s in enumerate(v['edu_spans']) if s[0]<b];right=[i for i,s in enumerate(v['edu_spans']) if s[1]>b]
  if not left or not right:continue
  i,j=left[-1],right[0]
  if i==j:straddling+=1
  a=e['paths'][eduids[i]];bb=e['paths'][eduids[j]];common=0
  for x,y in zip(a,bb):
   if x!=y:break
   common+=1
  lcas.append(common-1)
 nonroot=[k for k in nodes if nodes[k]['parent'] is not None]
 counts=collections.Counter(nodes[k]['relation'] for k in nonroot if nodes[k]['relation']!='span')
 return {'characters':v['sentences'][-1][1] if v['sentences'] else 0,'tokens':len(v['tokens']),'sentences':len(v['sentences']),'paragraphs':len(ps),'edus':len(eduids),'native_vertices':len(nodes),'native_groups':len(groups),'native_mean_edu_depth':statistics.mean(depths),'native_max_edu_depth':max(depths),'normalized_max_depth':max(depths)/max(1,len(eduids)-1),'group_branch_gt2_fraction':sum(len(e['children'][k])>2 for k in groups)/len(groups) if groups else None,'cross_paragraph_group_fraction':crossing/len(groups) if groups else None,'satellite_edge_fraction':sum(e['nuclearities'][k]=='S' for k in nonroot)/len(nonroot) if nonroot else None,'paragraph_boundary_lca_mean_depth':statistics.mean(lcas) if lcas else None,'paragraph_boundary_lca_depths':lcas,'paragraph_sentence_counts':[len(p['sentences']) for p in ps],'paragraph_edu_counts':[len(p['edus']) for p in ps],'paragraph_boundaries_straddled_by_edu':straddling,'paragraph_boundaries_straddled_by_sentence':sum(any(a<b<s for a,s in v['sentences']) for b in [p['span'][1] for p in ps[:-1]]),'discontinuous_native_yields':sum(ys!=list(range(ys[0],ys[-1]+1)) for ys in e['yields'].values()),'relation_counts':dict(sorted(counts.items())),'unknown_nuclearity_edges':sum(x=='unknown' for x in e['nuclearities'].values())}

def retention(v,raw):
 out=json.loads(stable(v));root=ET.fromstring(raw)
 expected={x.attrib['id']:{'id':x.attrib['id'],'kind':x.tag,'group_type':x.attrib.get('type'),'parent':x.attrib.get('parent'),'relation':x.attrib.get('relname')} for x in root.find('body')}
 labels={x.attrib['name']:x.attrib['type'] for x in root.findall('header/relations/rel')}
 proj=set(k for p in out['paragraphs'] for k in p['nodes'])
 edges={(k,n['parent'],n['relation']) for k,n in out['nodes'].items() if k in proj and n['parent'] is not None}
 goldedges={(k,n['parent'],n['relation']) for k,n in expected.items() if n['parent'] is not None}
 return {'json_roundtrip_identical':out==v,'native_attributes_exact':out['nodes']==expected,'relation_definitions_exact':out['relations']==labels,'projected_vertex_recall':len(proj.intersection(expected))/len(expected),'projected_labelled_edge_recall':len(edges.intersection(goldedges))/len(goldedges) if goldedges else 1,'paragraph_spans_exact':[p['span'] for p in out['paragraphs']]==[p['span'] for p in v['paragraphs']],'sentence_spans_exact':out['sentences']==v['sentences']}

def merge_intervals(intervals):
 out=[]
 for a,b in sorted(intervals):
  if out and a<=out[-1][1]:out[-1][1]=max(b,out[-1][1])
  else:out.append([a,b])
 return tuple(tuple(x) for x in out)
def signatures(g):
 e=enrich(g);ys={k:merge_intervals([g['edu_spans'][i] for i in ix]) for k,ix in e['yields'].items()};res={x:collections.Counter() for x in ['group_yield','native_edge_span','native_edge_nuclearity','native_edge_full']}
 for k,n in g['nodes'].items():
  if n['kind']=='group':res['group_yield'][ys[k]]+=1
  if n['parent'] is None:continue
  base=(ys[k],ys[n['parent']],n['kind'],n['group_type'])
  res['native_edge_span'][base]+=1
  res['native_edge_nuclearity'][base+(e['nuclearities'][k],)]+=1
  res['native_edge_full'][base+(e['nuclearities'][k],n['relation'])]+=1
 return res

def f1(a,b):
 a=collections.Counter(a);b=collections.Counter(b);na=sum(a.values());nb=sum(b.values());match=sum((a&b).values())
 return {'reference_count':na,'alternate_count':nb,'matched':match,'precision':match/nb if nb else (1 if not na else 0),'recall':match/na if na else (1 if not nb else 0),'f1':2*match/(na+nb) if na+nb else 1}
def boundary_scores(text_a,spans_a,text_b,spans_b):
 if text_a!=text_b:return {'status':'missing','reason':'character_stream_mismatch','reference_characters':len(text_a),'alternate_characters':len(text_b)}
 return {'status':'ok',**f1([x[1] for x in spans_a[:-1]],[x[1] for x in spans_b[:-1]])}
def segmentation(path):
 lines=[norm(x) for x in path.read_text().splitlines() if norm(x)]
 return ''.join(lines),spans(lines)

def perturbations(layout,g,v):
 bag=sorted(layout['sentence_keys']);rev=list(reversed(layout['sentence_keys']));original=layout['sentence_keys']
 pends={p[1] for p in layout['paragraphs'][:-1]};options=[s[1] for s in layout['sentences'][:-1] if s[1] not in pends]
 out={'reverse_sentence_order':{'sentence_bag_unchanged':sorted(rev)==bag,'ordered_layout_changed':rev!=original,'status':'ok' if rev!=original else 'inapplicable_palindrome'}}
 if pends and options:
  moved=set(pends);moved.remove(min(moved));moved.add(options[0]);end=layout['paragraphs'][-1][1];cuts=[0]+sorted(moved)+[end];altered=dict(layout);altered['paragraphs']=[[a,b] for a,b in zip(cuts,cuts[1:])]
  pv=view(altered,g)
  out['move_paragraph_boundary']={'status':'ok','sentence_bag_unchanged':sorted(altered['sentence_keys'])==bag,'ordered_sentences_unchanged':altered['sentence_keys']==original,'paragraph_projection_changed':pv['paragraphs']!=v['paragraphs'],'hierarchy_unchanged':pv['nodes']==v['nodes']}
 else:out['move_paragraph_boundary']={'status':'inapplicable','reason':'no_unused_sentence_boundary_or_single_paragraph'}
 return out

FEATURES=['native_mean_edu_depth','native_max_edu_depth','normalized_max_depth','group_branch_gt2_fraction','cross_paragraph_group_fraction','satellite_edge_fraction','paragraph_boundary_lca_mean_depth']
def process(d):
 out={'id':d['id'],'split':d['split'],'genre':d['genre'],'exposure_status':'exposed_calibration_document_no_future_heldout_claim','parser_accuracy':'not_evaluated_no_predictive_parser','argument_correctness':'not_evaluated_no_gold_layer'}
 try:
  layout=load_layout((CACHE/d['files']['xml']['path']).read_bytes(),(CACHE/d['files']['tokenized']['path']).read_text());raw=(CACHE/d['files']['rs3']['path']).read_bytes();g=read_graph(raw);v=view(layout,g)
  metadata={k:val for k,val in layout['metadata'].items() if k in ['sourceURL','dateCreated','dateModified','dateCollected','author','genre','id']}
  out.update({'status':'ok','source_metadata':metadata,'rights':{'private_use':'bounded_local_measurement_authorized','redistribution':'not_cleared_no_source_or_annotation_release','repository_license':'Apache-2.0','paper_license':'CC-BY_unspecified_version','source_terms':'not_independently_resolved_in_this_experiment'},'primary':measure(v),'retention':retention(v,raw),'perturbations':perturbations(layout,g,v),'missing_layers':v['missing_layers']})
  if d['split']=='test':
   ar=(CACHE/d['double_rst_paths'][0]).read_bytes();ag=read_graph(ar);out['double_rst_segmentation']=boundary_scores(g['text'],g['edu_spans'],ag['text'],ag['edu_spans'])
   if g['text']==ag['text']:
    av=view(layout,ag);out['alternate']=measure(av);out['alternate_retention']=retention(av,ar);a=signatures(g);b=signatures(ag);out['annotation_agreement']={k:f1(a[k],b[k]) for k in a}
    out['absolute_measurement_differences']={k:abs(out['primary'][k]-out['alternate'][k]) if out['primary'][k] is not None and out['alternate'][k] is not None else None for k in FEATURES}
   else:out['annotation_agreement']={'status':'missing','reason':'character_stream_mismatch'}
   sa,spa=segmentation(CACHE/d['alternate_segmentation_paths'][0]);sb,spb=segmentation(CACHE/d['alternate_segmentation_paths'][1]);out['pre_adjudication_segmentation']=boundary_scores(sa,spa,sb,spb);out['adjudicated_file_vs_primary_rst']=boundary_scores(g['text'],g['edu_spans'],sa,spa)
 except Exception as exc:out.update({'status':'failed','failure':str(exc),'failure_type':type(exc).__name__})
 return out

def summarize(rows):
 good=[r for r in rows if r['status']=='ok'];paired=[r for r in good if 'alternate' in r];out={'documents_requested':len(rows),'documents_ok':len(good),'failed_documents':[r['id'] for r in rows if r['status']!='ok'],'total_primary_edus':sum(r['primary']['edus'] for r in good),'total_primary_paragraphs':sum(r['primary']['paragraphs'] for r in good),'measurement_sensitivity':{},'agreement_macro':{}}
 for key in FEATURES:
  vals=[r['absolute_measurement_differences'][key] for r in paired if r['absolute_measurement_differences'][key] is not None];flips=ties=equal=0
  for i,a in enumerate(paired):
   for b in paired[i+1:]:
    x=a['primary'][key]-b['primary'][key];y=a['alternate'][key]-b['alternate'][key]
    if x*y<0:flips+=1
    elif (x==0)!=(y==0):ties+=1
    else:equal+=1
  if vals:out['measurement_sensitivity'][key]={'n_documents':len(vals),'mean_absolute_difference':statistics.mean(vals),'min_absolute_difference':min(vals),'max_absolute_difference':max(vals),'document_rank_pair_flips':flips,'document_rank_tie_changes':ties,'unchanged_order_pairs':equal}
 for section,keys in [('annotation_agreement',['group_yield','native_edge_span','native_edge_nuclearity','native_edge_full']),('double_rst_segmentation',[None]),('pre_adjudication_segmentation',[None])]:
  for key in keys:
   vals=[]
   for r in paired:
    score=r.get(section,{});score=score.get(key,{}) if key else score
    if 'f1' in score:vals.append(score['f1'])
   if vals:out['agreement_macro'][section+('/'+key if key else '')]={'n':len(vals),'mean_f1':statistics.mean(vals),'min_f1':min(vals),'max_f1':max(vals)}
 return out

def main():
 resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024));resource.setrlimit(resource.RLIMIT_CPU,(600,600))
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['dev','test']);args=p.parse_args();start=time.perf_counter();cpu=time.process_time()
 if args.phase=='test':
  frozen=json.loads((HERE/'freeze.json').read_text())
  for path,sha in frozen['sha256'].items():assert hashlib.sha256((HERE/path).read_bytes()).hexdigest()==sha,'Frozen file changed'
  assert not (HERE/'test_results.json').exists(),'Test already evaluated; no silent retuning/rerun'
 m=json.loads((BASE/'minimal_gcdt_manifest.json').read_text());rows=[process(d) for d in m['documents'] if d['split']==args.phase]
 result={'phase':args.phase,'pin':m['commit'],'evaluation_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'definition_version':'native-rs3-view-v1','documents':rows,'summary':summarize(rows),'resources':{'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,'peak_rss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'processes':1,'external_models':0}}
 (HERE/(args.phase+'_results.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result['summary'],indent=2));print(json.dumps(result['resources']))
if __name__=='__main__':main()
