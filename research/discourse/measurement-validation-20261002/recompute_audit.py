#!/usr/bin/env python3
"""Read-only, aggregate-only independent audit of an already exposed measurement.
No downloads, models, fitting, source exports, or edits to experiment outputs.
Only the optional --output path is written. Requires existing private cache.
"""
import argparse,collections,copy,hashlib,importlib.util,itertools,json,pathlib,re,statistics,sys,unittest,xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parent.parent
RUN=ROOT/'discourse_validation_run'
CACHE=pathlib.Path('/tmp/gcdt-validation-private')
norm=lambda s:''.join(s.split())
mean=statistics.mean

def seq_spans(parts):
    pos=0; out=[]
    for p in parts:
        end=pos+len(norm(p));out.append((pos,end));pos=end
    return out

def read_xml_layout(path):
    tree=ET.fromstring(path.read_bytes());body=''.join(tree.itertext())
    blocks=[norm(t) for t in re.split(r'\n\s*\n',body) if norm(t)]
    return norm(body),seq_spans(blocks),tree

def read_rs3(path):
    root=ET.fromstring(path.read_bytes())
    nodes={e.attrib['id']:{'kind':e.tag,**dict(e.attrib)} for e in root.find('body')}
    leaves=[(e.attrib['id'],norm(''.join(e.itertext()))) for e in root.find('body') if e.tag=='segment']
    spans=dict(zip([k for k,_ in leaves],seq_spans([s for _,s in leaves])))
    rels={e.attrib['name']:e.attrib['type'] for e in root.findall('header/relations/rel')}
    return nodes,spans,rels,''.join(s for _,s in leaves)

def structures(nodes,spans):
    children={k:[] for k in nodes}
    for k,n in nodes.items():
        if 'parent' in n:children[n['parent']].append(k)
    roots=[k for k,n in nodes.items() if 'parent' not in n]
    assert len(roots)==1
    yields={};depth={};paths={}
    def visit(k,path):
        assert k not in depth
        depth[k]=len(path);paths[k]=path+[k]
        ys={k} if k in spans else set()
        for c in children[k]:ys|=visit(c,path+[k])
        assert ys
        yields[k]=ys
        return ys
    visit(roots[0],[]);assert len(depth)==len(nodes)
    return children,yields,depth,paths

def intervals(leaves,spans):
    out=[]
    for a,b in sorted(spans[k] for k in leaves):
        if out and a<=out[-1][1]:out[-1][1]=max(out[-1][1],b)
        else:out.append([a,b])
    return tuple(map(tuple,out))

def nuclearity(n,rels):
    if 'parent' not in n:return 'ROOT'
    rel=n.get('relname')
    if rel=='span' or rels.get(rel)=='multinuc':return 'N'
    if rels.get(rel)=='rst':return 'S'
    return 'unknown'

def analyse(graph,paras):
    nodes,spans,rels,text=graph
    children,yields,depth,paths=structures(nodes,spans)
    sig={k:intervals(ys,spans) for k,ys in yields.items()}
    groups=[k for k,n in nodes.items() if n['kind']=='group']
    def crosses(k):return sum(any(a<d and c<b for a,b in sig[k]) for c,d in paras)>1
    crossing=sum(crosses(k) for k in groups)
    counters={s:collections.Counter() for s in ['group_yield','native_edge_span','native_edge_nuclearity','native_edge_full']}
    for k,n in nodes.items():
        if n['kind']=='group':counters['group_yield'][sig[k]]+=1
        if 'parent' not in n:continue
        base=(sig[k],sig[n['parent']],n['kind'],n.get('type'))
        counters['native_edge_span'][base]+=1
        counters['native_edge_nuclearity'][base+(nuclearity(n,rels),)]+=1
        counters['native_edge_full'][base+(nuclearity(n,rels),n.get('relname'))]+=1
    lcas=[]
    ordered=sorted(spans,key=lambda k:spans[k][0])
    for _,boundary in paras[:-1]:
        left=[k for k in ordered if spans[k][0]<boundary][-1]
        right=[k for k in ordered if spans[k][1]>boundary][0]
        common=list(itertools.takewhile(lambda ab:ab[0]==ab[1],zip(paths[left],paths[right])))
        lcas.append(len(common)-1)
    nonroot=[n for n in nodes.values() if 'parent' in n]
    features={
        'native_mean_edu_depth':mean(depth[k] for k in spans),
        'native_max_edu_depth':max(depth[k] for k in spans),
        'normalized_max_depth':max(depth[k] for k in spans)/max(1,len(spans)-1),
        'group_branch_gt2_fraction':sum(len(children[k])>2 for k in groups)/len(groups),
        'cross_paragraph_group_fraction':crossing/len(groups),
        'satellite_edge_fraction':sum(nuclearity(n,rels)=='S' for n in nonroot)/len(nonroot),
        'paragraph_boundary_lca_mean_depth':mean(lcas),
    }
    unary=[k for k in groups if len(children[k])==1]
    assert all(nodes[k].get('type')=='span' and nodes[children[k][0]].get('relname')=='span' for k in unary)
    unique_groups=set(sig[k] for k in groups)
    unique_cross=sum(sum(any(a<d and c<b for a,b in s) for c,d in paras)>1 for s in unique_groups)
    all_nontrivial={sig[k] for k in nodes if len(yields[k])>1}
    all_cross=sum(sum(any(a<d and c<b for a,b in s) for c,d in paras)>1 for s in all_nontrivial)
    diag={'nodes':len(nodes),'edges':len(nonroot),'edus':len(spans),'groups':len(groups),'crossing_groups':crossing,'unary_span_groups':len(unary),'unary_crossing_groups':sum(crosses(k) for k in unary),'duplicate_group_yields':len(groups)-len(unique_groups),'group_yield_equals_segment_yield':sum(any(sig[k]==sig[s] for s in spans) for k in groups),'unique_group_yield_fraction':unique_cross/len(unique_groups),'unique_all_nontrivial_yield_fraction':all_cross/len(all_nontrivial)}
    return features,counters,diag

def contract_span_wrappers(graph):
    nodes,spans,rels,text=copy.deepcopy(graph)
    removed=0
    while True:
        children,_,_,_=structures(nodes,spans)
        candidates=[k for k,n in nodes.items() if n['kind']=='group' and n.get('type')=='span' and len(children[k])==1 and nodes[children[k][0]].get('relname')=='span']
        if not candidates:break
        k=candidates[0];n=nodes[k];child=nodes[children[k][0]]
        for key in ['parent','relname']:
            if key in n:child[key]=n[key]
            else:child.pop(key,None)
        del nodes[k];removed+=1
    return (nodes,spans,rels,text),removed

def overlap(a,b):
    matched=sum((a&b).values());na=sum(a.values());nb=sum(b.values())
    return {'reference_count':na,'alternate_count':nb,'matched':matched,'f1':2*matched/(na+nb) if na+nb else 1}

def segmentation(path):
    ls=[norm(s) for s in path.read_text().splitlines() if norm(s)]
    return ''.join(ls),collections.Counter(b for a,b in seq_spans(ls)[:-1])

def flipcount(pairs):
    flips=ties=unchanged=0
    for a,b in itertools.combinations(pairs,2):
        x=a[0]-b[0];y=a[1]-b[1]
        if x*y<0:flips+=1
        elif (x==0)!=(y==0):ties+=1
        else:unchanged+=1
    return {'flips':flips,'tie_changes':ties,'unchanged':unchanged}

def main(output):
    original_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in RUN.iterdir() if p.is_file()}
    manifest=json.loads((ROOT/'research_discourse_validation/minimal_gcdt_manifest.json').read_text())
    stored={r['id']:r for phase in ['dev','test'] for r in json.loads((RUN/(phase+'_results.json')).read_text())['documents']}
    frozen=json.loads((RUN/'freeze.json').read_text())
    assert all(original_files[n]==h for n,h in frozen['sha256'].items())
    original_summary=json.loads((RUN/'test_results.json').read_text())['summary']
    logs=json.loads((RUN/'download_log.json').read_text());meta=json.loads((ROOT/'research_discourse_validation/GCDT_metadata.json').read_text())
    expected={x['path']:x.get('sha') for x in meta['files']}
    for entry in logs:
        data=(CACHE/entry['path']).read_bytes()
        assert len(data)==entry['bytes']
        assert hashlib.sha256(data).hexdigest()==entry['sha256']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==entry['git_blob_sha']==expected[entry['path']]
    sys.path.insert(0,str(RUN));import evaluate as original_evaluator
    totals=collections.Counter();paired=[];agreements=collections.defaultdict(list);contraction_scores=[];retention_graphs=0
    variants=collections.defaultdict(list);all_diags=[];layout_tags=collections.Counter();recomputed_fields=0
    for doc in manifest['documents']:
        row=stored[doc['id']];text,paras,tree=read_xml_layout(CACHE/doc['files']['xml']['path'])
        layout_tags.update(e.tag for e in tree.iter() if e is not tree)
        tok=(CACHE/doc['files']['tokenized']['path']).read_text()
        assert text==norm(tok)
        totals['documents']+=1;totals['primary_paragraphs']+=len(paras);totals['primary_sentences']+=sum(bool(norm(l)) for l in tok.splitlines())
        primary=read_rs3(CACHE/doc['files']['rs3']['path']);assert primary[3]==text
        totals['primary_edus']+=len(primary[1])
        gs=[primary]
        if doc['split']=='test':gs.append(read_rs3(CACHE/doc['double_rst_paths'][0]))
        local=[];reduced=[]
        for graph,which in zip(gs,['primary','alternate']):
            assert graph[3]==text
            features,scores,diag=analyse(graph,paras)
            # Independent XML-derived oracle against the actual representation.
            raw=(CACHE/(doc['files']['rs3']['path'] if which=='primary' else doc['double_rst_paths'][0])).read_bytes()
            layout=original_evaluator.load_layout((CACHE/doc['files']['xml']['path']).read_bytes(),tok)
            represented=original_evaluator.view(layout,original_evaluator.read_graph(raw))
            roundtripped=json.loads(json.dumps(represented))
            assert roundtripped==represented
            oracle_nodes={k:{'id':k,'kind':n['kind'],'group_type':n.get('type'),'parent':n.get('parent'),'relation':n.get('relname')} for k,n in graph[0].items()}
            assert represented['nodes']==oracle_nodes
            assert represented['relations']==graph[2]
            assert represented['edu_spans']==[list(s) for s in graph[1].values()]
            child,ys,depth,paths=structures(graph[0],graph[1])
            edu_order={k:i for i,k in enumerate(graph[1])}
            assert represented['structure']['yields']=={k:sorted(edu_order[i] for i in values) for k,values in ys.items()}
            assert represented['structure']['paths']==paths
            assert represented['structure']['nuclearities']=={k:nuclearity(n,graph[2]) for k,n in graph[0].items()}
            covered=set()
            for block,(a,b) in zip(represented['paragraphs'],paras):
                expected={k for k,leaves in ys.items() if any(a<graph[1][i][1] and graph[1][i][0]<b for i in leaves)}
                assert set(block['nodes'])==expected;assert block['span']==[a,b];covered|=expected
            assert covered==set(graph[0])
            oracle_edges={(k,n['parent'],n['relname']) for k,n in graph[0].items() if 'parent' in n}
            represented_edges={(k,n['parent'],n['relation']) for k,n in represented['nodes'].items() if k in covered and n['parent'] is not None}
            assert oracle_edges==represented_edges
            retention_graphs+=1
            for key,val in features.items():assert abs(val-row[which][key])<1e-12;recomputed_fields+=1
            assert diag['groups']==row[which]['native_groups']
            assert diag['nodes']==row[which]['native_vertices']
            local.append((features,scores,diag));all_diags.append(diag)
            if doc['split']=='test':
                contracted,n=contract_span_wrappers(graph);cf,cs,cd=analyse(contracted,paras)
                assert n==diag['unary_span_groups'];assert cd['unary_span_groups']==0
                # Contraction preserves every non-span labelled attachment by retargeting
                # wrapper incoming edges; no source tokens or rhetorical label is deleted.
                before=collections.Counter(n.get('relname') for n in graph[0].values() if n.get('relname') not in (None,'span'))
                after=collections.Counter(n.get('relname') for n in contracted[0].values() if n.get('relname') not in (None,'span'))
                assert before==after
                reduced.append((cf,cs,cd))
        if doc['split']=='test':
            for key in local[0][1]:
                score=overlap(local[0][1][key],local[1][1][key]);agreements[key].append(score)
                for field,val in score.items():assert abs(val-row['annotation_agreement'][key][field])<1e-12;recomputed_fields+=1
            at,bounda=segmentation(CACHE/doc['alternate_segmentation_paths'][0]);bt,boundb=segmentation(CACHE/doc['alternate_segmentation_paths'][1]);assert at==bt==text
            boundary=overlap(bounda,boundb);agreements['pre_adjudication_segmentation'].append(boundary)
            assert abs(boundary['f1']-row['pre_adjudication_segmentation']['f1'])<1e-12
            edu_boundaries=collections.Counter(b for a,b in list(primary[1].values())[:-1])
            alt_boundaries=collections.Counter(b for a,b in list(gs[1][1].values())[:-1])
            assert edu_boundaries==alt_boundaries==bounda
            variants['native_group_fraction'].append(tuple(x[0]['cross_paragraph_group_fraction'] for x in local))
            variants['deduplicated_group_yield_fraction'].append(tuple(x[2]['unique_group_yield_fraction'] for x in local))
            variants['all_nontrivial_unique_yield_fraction'].append(tuple(x[2]['unique_all_nontrivial_yield_fraction'] for x in local))
            variants['contracted_nonunary_group_fraction'].append(tuple(x[0]['cross_paragraph_group_fraction'] for x in reduced))
            contraction_scores.append(overlap(reduced[0][1]['native_edge_full'],reduced[1][1]['native_edge_full']))
            paired.append(local)
    measures={}
    for key in paired[0][0][0]:
        pairs=[(p[0][0][key],p[1][0][key]) for p in paired];diffs=[abs(a-b) for a,b in pairs];f=flipcount(pairs)
        s=original_summary['measurement_sensitivity'][key]
        assert abs(mean(diffs)-s['mean_absolute_difference'])<1e-12
        assert (f['flips'],f['tie_changes'],f['unchanged'])==(s['document_rank_pair_flips'],s['document_rank_tie_changes'],s['unchanged_order_pairs'])
        measures[key]={'n_documents':len(pairs),'mean_absolute_difference':mean(diffs),'max_absolute_difference':max(diffs),**f}
    agreement_summary={}
    for key,scores in agreements.items():
        totalscore={k:sum(s[k] for s in scores) for k in ['reference_count','alternate_count','matched']}
        agreement_summary[key]={'macro_f1':mean(s['f1'] for s in scores),'micro_f1':2*totalscore['matched']/(totalscore['reference_count']+totalscore['alternate_count']),**totalscore}
    variant_summary={k:{'macro_absolute_difference':mean(abs(a-b) for a,b in pairs),**flipcount(pairs)} for k,pairs in variants.items()}
    group_totals={which:{key:sum(p[i][2][key] for p in paired) for key in ['groups','crossing_groups','unary_span_groups','unary_crossing_groups','duplicate_group_yields','group_yield_equals_segment_yield']} for i,which in enumerate(['primary','alternate'])}
    sys.path.insert(0,str(RUN));import test_synthetic
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_synthetic)
    result=unittest.TestResult();suite.run(result);assert result.wasSuccessful()
    test_paths={d['files'][k]['path'] for d in manifest['documents'] if d['split']=='test' for k in ['xml','tokenized','rs3']}
    test_paths.update(p for d in manifest['documents'] if d['split']=='test' for p in d['double_rst_paths']+d['alternate_segmentation_paths'])
    first_test=min(x['download_utc'] for x in logs if x['path'] in test_paths)
    assert first_test>frozen['executor_timestamp']
    out={'scope':'Independent read-only replay of exposed inputs; post-hoc diagnostic, not new held-out evaluation','checks':{'frozen_hashes_match':True,'downloaded_bytes_hashes_match':True,'stored_feature_agreement_fields_match':recomputed_fields,'independently_checked_retention_graphs':retention_graphs,'all_primary_and_alternate_streams_align':True,'all_released_rs3_and_adjudicated_boundaries_equal':True,'all_original_artifact_hashes_unchanged':True,'synthetic_tests_passed':result.testsRun},'totals':{**totals,'graphs':len(all_diags),'native_vertices':sum(d['nodes'] for d in all_diags),'native_edges':sum(d['edges'] for d in all_diags)},'agreement':agreement_summary,'sensitivity':measures,'encoding_diagnostic':{'paired_group_aggregates':group_totals,'crossing_fraction_variants':variant_summary,'contracted_native_full_edge_macro_f1':mean(s['f1'] for s in contraction_scores),'interpretation':'Unary span-group contraction is an audit diagnostic, not canonical RST Parseval or a new selected metric. Raw differences combine rhetorical annotation and native encoding. Every contracted group had exactly one span-linked child; contraction retains all non-span relation labels. No attribution percentage is justified.'},'layout_tag_counts':dict(layout_tags),'chronology':{'freeze_clock_utc':frozen['freeze_utc_from_clock_tool'],'freeze_executor_utc':frozen['executor_timestamp'],'first_logged_test_download_utc':first_test,'limitation':'Local hashes and chronology are internally consistent; audit alone cannot attest absence of earlier unlogged body access or reruns.'},'privacy':'Aggregate-only output; no source text, per-document scores, sentence hashes, full graphs, paragraph vectors, or source annotation bytes'}
    assert original_files=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in RUN.iterdir() if p.is_file()}
    pathlib.Path(output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default=str(pathlib.Path(__file__).with_name('aggregate_checks.json')));main(p.parse_args().output)
