"""Frozen operational descriptors; does not certify semantic preservation."""
import math,re
SCHEMA='controlled-structural-labels/v2'
FACT_LABELS=('preserved','changed_or_missing','uncertain')
SEMANTIC_AXES=('facts','unsupported_additions','negation','modality','quantifiers','scope')

def observed_properties(text,mainpoint):
    if not isinstance(text,str) or not isinstance(mainpoint,str) or not mainpoint:
        raise ValueError('text_and_mainpoint_required')
    nonspace=sum(not c.isspace() for c in text)
    spans=[];start=0
    for m in re.finditer(r'[。！？!?]+',text):
        if text[start:m.start()].strip():spans.append((start,m.start()))
        start=m.end()
    if text[start:].strip():spans.append((start,len(text)))
    lengths=[sum(not c.isspace() for c in text[a:b]) for a,b in spans]
    mean=sum(lengths)/len(lengths) if lengths else 0
    sd=math.sqrt(sum((x-mean)**2 for x in lengths)/len(lengths)) if lengths else 0
    cv=sd/mean if mean else None
    short=bool(len(lengths)>=4 and sum(n<=24 for n in lengths)/len(lengths)>=.8 and max(lengths)<=32)
    mixed=bool(len(lengths)>=4 and min(lengths)<=18 and max(lengths)>=40 and cv>=.35)
    assert not(short and mixed)
    unique=text.count(mainpoint)==1
    point=text.index(mainpoint) if unique else None
    point_end=point+len(mainpoint) if unique else None
    containing=next((i for i,(a,b) in enumerate(spans) if a<=point and point_end<=b),None) if unique else None
    pos=sum(not c.isspace() for c in text[:point])/nonspace if unique and nonspace else None
    early=bool(containing is not None and pos<=.2 and containing<2)
    late=bool(containing is not None and pos>=.7 and containing>=len(spans)-2)
    rhythm='short' if short else 'mixed' if mixed else 'outside_support'
    placement='early' if early else 'late' if late else 'outside_support'
    format_ok=not bool(re.search(r'(?m)^\s*(?:#{1,6}\s|[-*+]\s|[0-9]+[.)、]\s)|```|~~~|[“”‘’「」『』"\[\]<>$∀∃=∑∫]|\\(?:begin|frac|sum|int|forall|exists)\b',text))
    han=sum('\u3400'<=c<='\u4dbf' or '\u4e00'<=c<='\u9fff' for c in text)
    supported=bool(120<=len(text)<=400 and nonspace and han/nonspace>=.5 and format_ok and unique and len(lengths)>=4 and text.rstrip().endswith(tuple('。！？!?')))
    return {'schema':SCHEMA,'raw_codepoints':len(text),'nonspace_codepoints':nonspace,'sentence_lengths':lengths,'sentence_count':len(lengths),'sentence_cv':cv,'short_fraction':sum(n<=24 for n in lengths)/len(lengths) if lengths else None,'unique_exact_mainpoint':unique,'mainpoint_span':[point,point_end] if unique else None,'mainpoint_sentence_index_zero_based':containing,'mainpoint_start_fraction':pos,'rhythm_observed':rhythm,'placement_observed':placement,'format_and_length_support':supported,'mechanical_condition':f'{rhythm}_{placement}' if supported and rhythm!='outside_support' and placement!='outside_support' else None,'semantic_guarantee':False}

def adjudicate_pair(a,b,properties,fact_ids):
    """Agreement filter. No nominal target enters this function."""
    for x in (a,b):
        if set(x)!={'review_id','rater_id','fact_labels','semantic_axes','mainpoint_is_real_main_claim','rhythm_label','placement_label'}:raise ValueError('review_schema')
        if set(x['fact_labels'])!=set(fact_ids) or any(v not in FACT_LABELS for v in x['fact_labels'].values()):raise ValueError('fact_labels')
        if set(x['semantic_axes'])!=set(SEMANTIC_AXES) or any(v not in ('pass','fail','uncertain') for v in x['semantic_axes'].values()):raise ValueError('semantic_labels')
        if x['mainpoint_is_real_main_claim'] not in ('yes','no','uncertain'):raise ValueError('mainpoint_label')
        if x['rhythm_label'] not in ('short','mixed','outside_support','uncertain') or x['placement_label'] not in ('early','late','outside_support','uncertain'):raise ValueError('style_labels')
    if a['review_id']!=b['review_id'] or not a['rater_id'] or a['rater_id']==b['rater_id']:raise ValueError('independent_review_identity')
    semantic=all(all(v=='preserved' for v in x['fact_labels'].values()) and all(v=='pass' for v in x['semantic_axes'].values()) for x in (a,b))
    style=(a['rhythm_label']==b['rhythm_label']==properties['rhythm_observed'] and a['placement_label']==b['placement_label']==properties['placement_observed'] and all(x['mainpoint_is_real_main_claim']=='yes' for x in (a,b)))
    return {'semantic_consensus_pass':semantic,'realized_condition':properties['mechanical_condition'] if semantic and style else None,'nominal_condition_used':False,'semantic_guarantee':False,'uncertainty_retained':not(semantic and style)}
