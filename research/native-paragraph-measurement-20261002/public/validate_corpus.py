"""Validate a pinned local corpus and emit only aggregate public evidence.

Only --private-output receives document IDs joined to measurements, offsets,
source structures or text. The public review selection is source metadata only.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from lxml import etree, html
from native_adapter import adapt_html, adapt_draftjs, measure, content_chars, sha256


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)+'\n')


def rank(record):
    return sha256(('native-source-handcheck/1.0.0\0'+record['document_id']).encode())


def choose_review(inputs):
    groups=defaultdict(list)
    challenges=defaultdict(list)
    for x in inputs:
        r=x['document']['provenance']['metadata']['corpus_record']
        groups[(r['source']['source_id'],r['genre'])].append(r)
        roles={u['role'] for u in x['source_units']}
        for role in ('marked_quotation','caption','heading','unmapped_source_text','division_element_mixed','atomic_entity'):
            if role in roles: challenges[role].append(r)
        counts=Counter(u['role'] for u in x['source_units'])
        if counts['division_element_mixed'] > counts['paragraph_element_mixed']:
            challenges['division_dominant_no_paragraph_inference'].append(r)
        if r['author_unit']['kind']=='coauthored': challenges['coauthor'].append(r)
        if r['source']['source_item_id']=='6605': challenges['translation_metadata'].append(r)
    selected={}
    for name,rs in sorted(groups.items()):
        r=min(rs,key=rank); selected.setdefault(r['document_id'],{'record':r,'strata':[]})['strata'].append('source_genre:'+':'.join(name))
    for name,rs in sorted(challenges.items()):
        r=min(rs,key=rank); selected.setdefault(r['document_id'],{'record':r,'strata':[]})['strata'].append('challenge:'+name)
    return selected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission-public', required=True,type=Path)
    parser.add_argument('--source-root',required=True,type=Path)
    parser.add_argument('--public-output',required=True,type=Path)
    parser.add_argument('--private-output',required=True,type=Path)
    args=parser.parse_args()
    args.public_output.mkdir(parents=True,exist_ok=True);args.private_output.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('admission_loader',args.admission_public/'loader.py')
    loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
    inputs=list(loader.iter_feature_analysis_inputs(args.admission_public/'REGISTRY.json',args.source_root))
    selected=choose_review(inputs)
    roles_cp=Counter();roles_ln=Counter();totals=Counter();formats=Counter();missing=Counter();checks=Counter(); source_meta=[]
    private_views=[];private_measures=[]; private_review=[]
    for x in inputs:
        r=x['document']['provenance']['metadata']['corpus_record']; text=x['document']['text']
        if r['content']['structure_format']=='html_leaf_blocks/1.0.0':
            raw=loader.checked_file(args.source_root,r['content']['body_html']).decode()
            view=adapt_html(raw,text)
            wrapped_markup='<section><div>'+html.tostring(html.fromstring(raw),encoding='unicode',with_tail=False)+'</div></section>'
            wrapped=adapt_html(wrapped_markup,text)
            assert measure(text,view)['features']==measure(text,wrapped)['features']
            checks['html_wrapper_invariance_documents']+=1
        else:
            raw=None;view=adapt_draftjs(x['source_structure'],text)
        m=measure(text,view)
        assert m['counts']['selected_LN']+m['counts']['excluded_LN']==m['counts']['body_LN']
        for key in ('semantic_paragraphs','quotation_attribution','rhetorical_hierarchy','argument_structure','clean_author_prose'):
            assert view['unsupported'][key]['value'] is None
        assert m['fit_authorized'] is False and x['fit_authorized'] is False
        assert r['assistance_status']=='unknown' and r['admission']['cohort']=='H_G'
        assert all(text[p['start']:p['end']] for p in m['paragraphs'])
        for u in view['units']:
            roles_cp[u['role']]+=u['end']-u['start']; roles_ln[u['role']]+=content_chars(u['text'])
        totals.update(m['counts']);totals['documents']+=1
        totals['native_paragraph_nodes_including_excluded_or_empty']+=len(view['paragraphs'])
        totals['legacy_native_nonempty_blocks']+=sum(u['source_block_index'] is not None for u in x['source_units'])
        totals['empty_native_paragraph_nodes']+=sum(p['start']==p['end'] for p in view['paragraphs'])
        totals['source_units_with_LN_inline_gaps']+=sum(u['role']=='inline_gap' and content_chars(u['text'])>0 for u in view['units'])
        totals['explicit_heading_nodes']+=sum(n['heading_level'] is not None for n in view['nodes'])
        totals['explicit_list_item_nodes']+=sum(n['boundary_kind']=='list_item' for n in view['nodes'])
        formats[view['source_format']]+=1
        missing.update(k+':'+v['missing_reason'] for k,v in m['features'].items() if v['value'] is None)
        checks['exact_body_partition_documents']+=1; checks['role_sensitive_denominator_documents']+=1
        private_views.append({'document_id':r['document_id'],'view':view})
        private_measures.append({'document_id':r['document_id'],'measurement':m})
        source_meta.append({'document_id':r['document_id'],'source_url':r['source']['canonical_url'],
                            'structure_format':r['content']['structure_format'],
                            'body_sha256':r['content']['body_text']['sha256'],
                            'structure_sha256':r['content']['structure']['sha256'],
                            'body_html_sha256':r['content'].get('body_html',{}).get('sha256')})
        if r['document_id'] in selected:
            private_review.append({'document_id':r['document_id'],'strata':selected[r['document_id']]['strata'],
                                   'source_url':r['source']['canonical_url'],'body_html':raw,
                                   'draftjs':x['source_structure'] if raw is None else None,
                                   'view':view,'measurement':m})
    assert totals['documents']==47 and totals['body_codepoints']==182610 and totals['legacy_native_nonempty_blocks']==1136
    assert sum(roles_cp.values())==totals['body_codepoints']
    assert sum(roles_ln.values())==totals['body_LN']
    for filename,data in [('NATIVE_VIEWS.jsonl',private_views),('MEASUREMENTS.jsonl',private_measures),('REVIEW_PACKETS.jsonl',private_review)]:
        (args.private_output/filename).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data))
    receipt={'schema_version':'native-source-validation/1.0.0','status':'structural_validation_passed_pending_independent_review',
             'counts':dict(totals),'formats':dict(formats),'body_codepoints_by_role':dict(roles_cp),
             'body_LN_by_role':dict(roles_ln),'checks':dict(checks),'measurement_missingness':dict(missing),
             'subset_selection':{'method':'minimum SHA256 per source x genre plus structural challenge stratum; union, deterministic',
                                 'seed':'native-source-handcheck/1.0.0','selected_documents':len(selected),
                                 'gold_annotation':False,'review_status':'pending_manual_source_inspection'},
             'observed_list_items':0,'list_validation_scope':'synthetic fixtures only; no list items observed in this release',
             'fit_performed':False,'new_downloads':False,'parser_models_loaded':False,'frozen_experiment_touched':False,
             'library_versions':{'lxml':'.'.join(map(str,etree.LXML_VERSION)),'libxml':'.'.join(map(str,etree.LIBXML_VERSION))},
             'limits':['Operational source-boundary measurement only','No human-feature stability or authorship conclusion',
                       'Source layout is not discourse syntax','All 47 retain assistance unknown operational-human admission']}
    receipt['coverage_limits']={'documents_with_under_half_body_LN_in_primary_projection':sum(m['measurement']['counts']['selected_LN']*2 < m['measurement']['counts']['body_LN'] for m in private_measures),
        'documents_with_fewer_than_five_selected_paragraphs':sum(m['measurement']['counts']['eligible_paragraphs']<5 for m in private_measures),
        'comparison_design_not_assessed_documents':len(private_measures),'meaning':'Audit diagnostics, not validated sample support thresholds'}
    dump(args.public_output/'AGGREGATE_VALIDATION.json',receipt)
    dump(args.public_output/'SOURCE_METADATA.json',source_meta)
    dump(args.public_output/'REVIEW_SELECTION.json',{'selection':[
        {'document_id':k,'source_url':v['record']['source']['canonical_url'],'strata':v['strata'],
         'selection_hash':rank(v['record'])} for k,v in sorted(selected.items())]})
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
