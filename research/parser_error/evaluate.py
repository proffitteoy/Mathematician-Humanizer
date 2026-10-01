"""Offline aggregate-only audit of a frozen PUD subset; not a style model.

Raw files, selection manifest and per-record predictions stay outside the repo.
ReferenceSentence is intentionally separate from the production provenance gate.
The immutable 71-channel arithmetic is consumed without changing/certifying it.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import dataclass, asdict, replace
import hashlib
import json
from pathlib import Path
import socket
import statistics
from typing import Any

from research.linguistic.adapter import _aggregate, lexical
from research.linguistic.contracts import Token
from research.linguistic.schema import CHANNEL_IDS, ALL_POS, ALL_RELATIONS
from research.linguistic.stanza_local import LocalStanza
from research.surface.adapter import SourceView, SourceObservation
from style_compiler.segmentation import segment

ROOT = Path(__file__).resolve().parents[2]
SEED = 'style-compiler/pud-parser-error/v0.1/'
SOURCE_SHA = 'd3393dd44eb9ae71a6eaa626581c1f760db6148f0d2c6378c2200835e2ede37a'
HISTORY = {'zh:lexical.content_overlap','zh:lexical.trigram_reuse','zh:syntax.initial_pos_reuse'}
WINDOWS = {'zh:lexical.mattr100','zh:lexical.entropy100','zh:upos.bigram_entropy100'}


def sha(b): return hashlib.sha256(b).hexdigest()


@dataclass(frozen=True)
class ReferenceSentence:
    source_sentence_index: int
    start: int
    end: int
    tokens: tuple[Token, ...]
    status: str = 'ok'
    reason: str | None = None
    annotation_provenance: str = 'converted_manual_treebank_reference'


def read_records(raw):
    """Do not normalize line endings or text. Only fixed LF framing is accepted."""
    if b'\r' in raw:
        raise ValueError('unexpected_CR_container_framing')
    records=[]; offset=0
    for block in raw.split(b'\n\n'):
        if block:
            meta={}; rows=[]
            for line in block.decode('utf-8',errors='strict').split('\n'):
                if line.startswith('# '):
                    if ' = ' in line:
                        k,v=line[2:].split(' = ',1)
                        if k in meta: raise ValueError('duplicate_metadata')
                        meta[k]=v
                elif line:
                    row=line.split('\t')
                    if len(row)!=10: raise ValueError('invalid_conllu_columns')
                    rows.append(row)
            records.append({'meta':meta,'rows':rows,'byte_offset':offset,'block_bytes':len(block)})
        offset+=len(block)+2
    return records


def select_records(records):
    chosen=[]
    for prefix in ('n','w'):
        group=[x for x in records if x['meta']['sent_id'].startswith(prefix)]
        chosen.extend(sorted(group,key=lambda x:(sha((SEED+x['meta']['sent_id']).encode()),x['meta']['sent_id']))[:32])
    if len(chosen)!=64: raise ValueError('selection_count')
    return chosen


def validate_tokens(tokens,text):
    """Independent exact-text/basic-tree checks. No production provenance enum."""
    if not tokens: raise ValueError('empty_annotation')
    cursor=0
    for i,t in enumerate(tokens,1):
        if t.local_id!=i: raise ValueError('nondense_token_id')
        if not (cursor<=t.start<t.end<=len(text)): raise ValueError('invalid_offsets')
        if not all(c.isspace() for c in text[cursor:t.start]): raise ValueError('uncovered_text')
        if t.form!=text[t.start:t.end]: raise ValueError('unaligned_form')
        if t.upos not in ALL_POS: raise ValueError('invalid_upos')
        if type(t.head)is not int or not 0<=t.head<=len(tokens) or t.head==i: raise ValueError('invalid_head')
        if t.base_relation not in ALL_RELATIONS: raise ValueError('invalid_relation')
        if (t.head==0)!=(t.deprel=='root'): raise ValueError('root_relation_mismatch')
        cursor=t.end
    if not all(c.isspace() for c in text[cursor:]): raise ValueError('uncovered_text')
    if sum(t.head==0 for t in tokens)!=1: raise ValueError('invalid_root_count')
    for t in tokens:
        seen=set(); cur=t
        while cur.head:
            if cur.local_id in seen: raise ValueError('cycle')
            seen.add(cur.local_id);cur=tokens[cur.head-1]


def reference(record,index):
    text=record['meta'].get('text')
    if text is None: raise ValueError('missing_text')
    tokens=[]; cursor=0
    for row in record['rows']:
        if not row[0].isdigit(): raise ValueError('mwt_or_empty_node')
        form=row[1]
        if not form or form=='_': raise ValueError('missing_form')
        while cursor<len(text) and text[cursor].isspace(): cursor+=1
        end=cursor+len(form)
        if text[cursor:end]!=form: raise ValueError('unaligned_form')
        feats=() if row[5]=='_' else tuple(tuple(x.split('=',1)) for x in row[5].split('|'))
        tokens.append(Token(int(row[0]),cursor,end,form,row[3],int(row[6]),row[7],feats))
        cursor=end
    validate_tokens(tokens,text)
    return ReferenceSentence(index,0,len(text),tuple(tokens))


def make_observation(record):
    text=record['meta']['text']
    source=SourceView(SOURCE_SHA,'zh_pud-ud-test.conllu',record['record_index'],record['byte_offset'],
      'pud_exact_text_lf/0.1.0',0,'','translated_treebank_evaluation_unit',sha(text.encode()),len(text))
    return SourceObservation(source,text)


def control_parse(parser,ref,text):
    import stanza
    # No gold linguistic tags/heads/lemmas/features are supplied to the model.
    doc=stanza.Document([[{'id':(t.local_id,),'text':t.form,'start_char':t.start,'end_char':t.end} for t in ref.tokens]],text=text)
    result=parser.pipeline(doc,processors=['pos','lemma','depparse'])
    if result.text!=text or len(result.sentences)!=1: raise ValueError('control_source_changed')
    tokens=[]
    for w in result.sentences[0].words:
        feats=tuple(tuple(x.split('=',1)) for x in w.feats.split('|')) if w.feats else ()
        tokens.append(Token(w.id,w.start_char,w.end_char,w.text,w.upos,w.head,w.deprel,feats))
    validate_tokens(tokens,text)
    if [(x.start,x.end) for x in tokens]!=[(x.start,x.end) for x in ref.tokens]: raise ValueError('control_tokens_changed')
    return ReferenceSentence(ref.source_sentence_index,0,len(text),tuple(tokens),annotation_provenance='automatic_reference_token_control')


def features(sentences):
    result=_aggregate(sentences,{s.source_sentence_index:s.source_sentence_index for s in sentences})
    # Random PUD records are not contiguous discourse; never validate fake zero-history.
    for key in HISTORY:
        result[key]={'value':None,'numerator':None,'denominator':None,'opportunities':0,
          'missing_reason':'no_verified_prior_context','status':'unavailable','comparison_eligible':False}
    return result


def span(t): return (t.start,t.end)

def head_span(t,tokens): return ('ROOT',) if t.head==0 else span(tokens[t.head-1])


def score_pair(gold,pred):
    gmap={span(t):t for t in gold.tokens};pmap={span(t):t for t in pred.tokens}
    matching=gmap.keys() & pmap.keys()
    result={}
    for kind in ('all','reference_lexical'):
        selected=[g for g in gold.tokens if kind=='all' or lexical(g)]
        counts=Counter({k:0 for k in ('aligned_dependents','unmatched_reference_tokens','upos_correct','reference_head_span_available','predicted_head_span_available','both_head_spans_available','head_correct','full_las_correct','base_las_correct')})
        counts['reference_tokens']=len(selected)
        if kind=='all':counts['predicted_tokens']=len(pred.tokens)
        for g in selected:
            if span(g) not in matching:
                counts['unmatched_reference_tokens']+=1;continue
            p=pmap[span(g)];counts['aligned_dependents']+=1
            counts['upos_correct']+=g.upos==p.upos
            gh=head_span(g,gold.tokens);ph=head_span(p,pred.tokens)
            counts['reference_head_span_available']+=gh==('ROOT',) or gh in pmap
            counts['predicted_head_span_available']+=ph==('ROOT',) or ph in gmap
            counts['both_head_spans_available']+=(gh==('ROOT',) or gh in pmap) and (ph==('ROOT',) or ph in gmap)
            counts['head_correct']+=gh==ph
            counts['full_las_correct']+=gh==ph and g.deprel==p.deprel
            counts['base_las_correct']+=gh==ph and g.base_relation==p.base_relation
        if kind=='all':counts['unmatched_predicted_tokens']=len(pred.tokens)-len(matching)
        result[kind]=counts
    conf={'upos':Counter(),'deprel_full':Counter(),'deprel_base':Counter()}
    for s in matching:
        g,p=gmap[s],pmap[s]
        if g.upos!=p.upos:conf['upos'][(g.upos,p.upos)]+=1
        if g.deprel!=p.deprel:conf['deprel_full'][(g.deprel,p.deprel)]+=1
        if g.base_relation!=p.base_relation:conf['deprel_base'][(g.base_relation,p.base_relation)]+=1
    return result,conf


def fraction(n,d): return n/d if d else None


def score_summary(counts):
    out=dict(counts); d=counts['aligned_dependents'];r=counts['reference_tokens']
    out['reference_token_span_recall']=fraction(d,r)
    if 'predicted_tokens' in counts:
        p=counts['predicted_tokens'];out['token_span_precision']=fraction(d,p);out['token_span_f1']=fraction(2*d,p+r)
    for key in ('upos','head','full_las','base_las'):
        out[key+'_agreement_aligned']=fraction(counts[key+'_correct'],d)
        out[key+'_correct_per_reference_token']=fraction(counts[key+'_correct'],r)
    return out


def sum_nullable(rows,key):
    vals=[r[key] for r in rows if r.get(key)is not None]
    return sum(vals) if vals else None


def channel_report(common,arm):
    result={}
    for key in CHANNEL_IDS:
        pairs=[];grows=[];prows=[];missing=Counter()
        for unit in common:
            g,p=unit['features']['reference'][key],unit['features'][arm][key]
            grows.append(g);prows.append(p)
            if g['value'] is None:missing['reference:'+str(g['missing_reason'])]+=1
            if p['value'] is None:missing[arm+':'+str(p['missing_reason'])]+=1
            if g['value'] is not None and p['value'] is not None:pairs.append(unit)
        diffs=[u['features'][arm][key]['value']-u['features']['reference'][key]['value'] for u in pairs]
        gpaired=[u['features']['reference'][key] for u in pairs];ppaired=[u['features'][arm][key] for u in pairs]
        gagg=features([u['reference'] for u in pairs])[key] if pairs else None
        pagg=features([u[arm] for u in pairs])[key] if pairs else None
        positive_ref=sum(r['value']>0 for r in gpaired);positive_pred=sum(r['value']>0 for r in ppaired)
        result[key]={
          'common_gate_records':len(common),'paired_records':len(pairs),
          'reference_available_records':sum(x['value']is not None for x in grows),
          'model_available_records':sum(x['value']is not None for x in prows),
          'missing_counts':dict(missing),'reference_positive_records':positive_ref,'model_positive_records':positive_pred,
          'evidence_status':('unvalidated_no_support' if not pairs else 'no_positive_event_evidence' if not positive_ref and not positive_pred else 'descriptive_discrepancy_only'),
          'reference_denominator_sum':sum_nullable(gpaired,'denominator'),'model_denominator_sum':sum_nullable(ppaired,'denominator'),
          'reference_opportunities_sum':sum_nullable(gpaired,'opportunities'),'model_opportunities_sum':sum_nullable(ppaired,'opportunities'),
          'reference_numerator_sum':sum_nullable(gpaired,'numerator'),'model_numerator_sum':sum_nullable(ppaired,'numerator'),
          'signed_bias':statistics.mean(diffs) if diffs else None,'mae':statistics.mean(abs(x) for x in diffs) if diffs else None,
          'maximum_absolute_error':max(map(abs,diffs)) if diffs else None,
          'reference_same_support_aggregate':gagg,'model_same_support_aggregate':pagg,
          'same_support_aggregate_delta':pagg['value']-gagg['value'] if gagg and pagg and gagg['value']is not None and pagg['value']is not None else None}
    return result


def evaluate(raw,selection,parser):
    records=read_records(raw)
    for i,r in enumerate(records):r['record_index']=i
    chosen=select_records(records)
    if [x['meta']['sent_id'] for x in chosen]!=[x['sent_id'] for x in selection['selection']]:raise ValueError('selection_changed')
    coverage=Counter({k:0 for k in ('excluded_reference_integer_rows','reference_failed_records','production_failed_source_units','production_pos_only_source_units','source_text_unavailable_records','boundary_not_evaluable_records','production_not_attempted_missing_text_records','control_not_attempted_missing_text_records')});coverage['selected_records']=len(chosen);by_stratum={s:Counter() for s in ('news','wiki')}
    reference_fail=Counter();production_fail=Counter();control_fail=Counter();boundaries=Counter();private=[];common=[]
    unsupported={'upos':Counter(),'deprel':Counter(),'deprel_base':Counter()}
    supported_bases={x.split(':')[0] for x in parser.vocabulary['depparse']['deprel']}
    for i,record in enumerate(chosen):
        stratum='news' if record['meta']['sent_id'][0]=='n' else 'wiki';by_stratum[stratum]['selected']+=1
        rowcount=sum(x[0].isdigit() for x in record['rows']);coverage['selected_reference_integer_rows']+=rowcount
        text=record['meta'].get('text')
        if text is None:
            coverage['source_text_unavailable_records']+=1
            coverage['boundary_not_evaluable_records']+=1
            coverage['reference_failed_records']+=1
            coverage['production_not_attempted_missing_text_records']+=1
            coverage['control_not_attempted_missing_text_records']+=1
            coverage['excluded_reference_integer_rows']+=rowcount
            reference_fail['missing_text']+=1
            private.append({'record_index':record['record_index'],'stratum':stratum,
                'boundary_exact':None,'reference_integer_rows':rowcount,
                'source_text_failure':'missing_text','reference_failure':'missing_text'})
            continue
        spans=segment(text)[1]
        boundary_ok=len(spans)==1 and spans[0].start==0 and spans[0].end==len(record['meta']['text'])
        boundaries[str(len(spans))]+=1
        coverage['boundary_exact_records']+=boundary_ok;coverage['boundary_mismatch_records']+=not boundary_ok
        unit={'record_index':record['record_index'],'stratum':stratum,'boundary_exact':boundary_ok,'reference_integer_rows':rowcount}
        ref=None
        try:
            ref=reference(record,i);coverage['reference_aligned_records']+=1;coverage['reference_aligned_tokens']+=len(ref.tokens)
            for t in ref.tokens:
                if t.upos not in parser.vocabulary['pos']['upos']:unsupported['upos'][t.upos]+=1
                if t.deprel not in parser.vocabulary['depparse']['deprel']:unsupported['deprel'][t.deprel]+=1
                if t.base_relation not in supported_bases:unsupported['deprel_base'][t.base_relation]+=1
        except (ValueError,TypeError,IndexError) as e:
            reason=str(e) if type(e)is ValueError else type(e).__name__
            reference_fail[reason]+=1;coverage['reference_failed_records']+=1;unit['reference_failure']=reason
        parsed=parser.parse(make_observation(record))
        coverage['production_source_units']+=len(parsed.sentences)
        for p in parsed.sentences:
            coverage['production_'+p.status+'_source_units']+=1
            if p.status!='ok':production_fail[p.reason]+=1
        production_ok=boundary_ok and len(parsed.sentences)==1 and parsed.sentences[0].status=='ok'
        ctrl=None
        if ref is not None and boundary_ok:
            try:
                ctrl=control_parse(parser,ref,record['meta']['text']);coverage['control_success_records']+=1
            except (ValueError,RuntimeError,TypeError,IndexError) as e:
                control_fail[type(e).__name__]+=1;unit['control_failure']=type(e).__name__
        if ref is not None and production_ok and ctrl is not None:
            p=replace(parsed.sentences[0],source_sentence_index=i)
            item={'reference':ref,'production':p,'control':ctrl,'stratum':stratum}
            item['features']={arm:features([item[arm]]) for arm in ('reference','production','control')}
            common.append(item);coverage['common_gate_records']+=1;coverage['common_gate_reference_tokens']+=len(ref.tokens)
            coverage['common_gate_reference_lexical_tokens']+=sum(lexical(t) for t in ref.tokens)
            by_stratum[stratum]['common_gate_records']+=1
            unit.update({'reference':asdict(ref),'production':asdict(p),'control':asdict(ctrl)})
        else:
            coverage['excluded_reference_integer_rows']+=rowcount
        private.append(unit)
    scores={};confusions={}
    for arm in ('production','control'):
        scores[arm]={};confusions[arm]={}
        for stratum in ('all','news','wiki'):
            counts={k:Counter() for k in ('all','reference_lexical')};conf={k:Counter() for k in ('upos','deprel_full','deprel_base')}
            for item in common:
                if stratum!='all' and item['stratum']!=stratum:continue
                pair,c=score_pair(item['reference'],item[arm])
                for k,v in pair.items():counts[k].update(v)
                for k,v in c.items():conf[k].update(v)
            scores[arm][stratum]={k:score_summary(v) for k,v in counts.items()}
            if stratum=='all':confusions[arm]={k:[{'reference':a,'prediction':b,'count':n} for (a,b),n in sorted(v.items(),key=lambda kv:(-kv[1],kv[0]))] for k,v in conf.items()}
    return {'coverage':dict(coverage),'stratum_coverage':{s:dict(x) for s,x in by_stratum.items()},
      'operational_source_units_per_reference_record':dict(boundaries),'reference_failures':dict(reference_fail),
      'production_failures':dict(production_fail),'control_failures':dict(control_fail),
      'unsupported_reference_labels':{k:dict(v) for k,v in unsupported.items()},
      'scores_common_gate_only':scores,'aligned_dependent_label_confusions':confusions,
      'channels':{arm:channel_report(common,arm) for arm in ('production','control')}},private


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--private-dir',type=Path,required=True);ap.add_argument('--models',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.private_dir.resolve().is_relative_to(ROOT):raise ValueError('raw_data_must_stay_outside_repository')
    raw=(args.private_dir/'zh_pud-ud-test.conllu').read_bytes()
    if sha(raw)!=SOURCE_SHA:raise ValueError('corpus_hash_mismatch')
    selection_bytes=(args.private_dir/'selection.private.json').read_bytes();selection=json.loads(selection_bytes)
    prereg=(ROOT/'research/parser_error/preregister.public.json').read_bytes()
    if selection['preregister_sha256']!=sha(prereg):raise ValueError('preregister_changed')
    # Fail closed against network access during model initialization and inference.
    def denied(*a,**kw):raise RuntimeError('network_disabled_for_evaluation')
    socket.socket.connect=denied;socket.create_connection=denied
    parser=LocalStanza(args.models,threads=2)
    result,private=evaluate(raw,selection,parser)
    result={'status':'descriptive_measurement_discrepancy_not_construct_validation','preregister_sha256':sha(prereg),
      'private_selection_manifest_sha256':sha(selection_bytes),'corpus_sha256':SOURCE_SHA,
      'parser_profile':asdict(parser.profile),'model_vocabulary':parser.vocabulary,
      'linguistic_module_sha256':{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted((ROOT/'research/linguistic').glob('*.py'))},
      'network_disabled_during_model_run':True,'new_model_downloads':0,'evaluation_records_used_for_fitting':0,**result}
    (args.private_dir/'per-record.private.json').write_text(json.dumps(private,ensure_ascii=False,indent=2))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'coverage':result['coverage'],'production':result['scores_common_gate_only']['production']['all'],'control':result['scores_common_gate_only']['control']['all']},indent=2))

if __name__=='__main__':main()
