"""Gap-safe deterministic measurements of explicit POS/basic-UD analyses.

Importing does no IO. Natural-data bundles contain locators, spans and syntactic
reconstruction information and must remain private even though forms are omitted.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import asdict
import math
import statistics
import unicodedata
from style_compiler.surface import Projection, _components, _contained, _digest
from .contracts import ParsedSource, require
from .schema import SENSORS, CHANNEL_IDS, SCHEMA_VERSION, POS, RELATIONS, CUES

BUNDLE_VERSION = 'zh-linguistic-bundle/0.1.0'
from .unicode_scripts import in_script, SCRIPT_RANGES, UNICODE_VERSION, SCRIPTS_SHA256


def lexical(t):
    return t.upos!='PUNCT' and any(not c.isspace() and unicodedata.category(c)[0]!='P' for c in t.form)


def word_length(t):
    return sum(not c.isspace() and unicodedata.category(c)[0]!='P' for c in t.form)


def entropy(items):
    n=len(items)
    return -sum((v/n)*math.log2(v/n) for v in Counter(items).values()) if n else 0.0


def row(value=None, numerator=None, denominator=None, opportunities=0, reason=None):
    if reason is None and value is None:
        reason='zero_denominator'
    require(value is None or math.isfinite(value),'nonfinite_computed_value')
    return {'value':value,'numerator':numerator,'denominator':denominator,
            'opportunities':opportunities,'missing_reason':reason,
            'status':'unavailable' if value is None else ('zero_observed' if value==0 else 'observed'),
            'comparison_eligible':False,'uncertainty_interval':None}


def ratio(n,d):
    return row(n/d,n,d,d) if d else row(denominator=0)


def average(xs):
    return ratio(sum(xs),len(xs))


def vectors(rows):
    return {'channel_ids':CHANNEL_IDS,
            'values':tuple(rows[k]['value'] for k in CHANNEL_IDS),
            'opportunities':tuple(rows[k]['opportunities'] for k in CHANNEL_IDS),
            'missing_reasons':tuple(rows[k]['missing_reason'] for k in CHANNEL_IDS)}


def _aggregate(sentences, group_ids, prior=None, clipped=False):
    """Recompute from primitive observations; never average document medians.

    prior gives earlier SAME-component source sentences for one sequence row.
    It affects only explicitly history-dependent channels, not its denominator.
    """
    out={}; seq=list(sentences); prior=list(prior or [])
    tokenfail=next((s.reason for s in seq if s.status=='failed'),None)
    depfail='dependency_unavailable' if any(s.status=='pos_only' for s in seq) else None
    if clipped:
        return {spec.id:row(opportunities=None,reason='ineligible_structure') | {'opportunity_type':spec.opportunity} for spec in SENSORS}
    if tokenfail:
        return {spec.id:row(opportunities=None,reason=tokenfail) | {'opportunity_type':spec.opportunity} for spec in SENSORS}
    words={s.source_sentence_index:[t for t in s.tokens if lexical(t)] for s in seq}
    tokens=[t for s in seq for t in words[s.source_sentence_index]];T=len(tokens)
    for p in POS:out['zh:upos.'+p]=ratio(sum(t.upos==p for t in tokens),T)
    lengths=[word_length(t) for t in tokens]
    out['zh:word_length.mean']=average(lengths)
    out['zh:word_length.ge4']=ratio(sum(x>=4 for x in lengths),T)
    out['zh:word.single_han']=ratio(sum(len(t.form)==1 and in_script(t.form,'Han') for t in tokens),T)
    out['zh:word.latin']=ratio(sum(any(unicodedata.category(c)[0]=='L' and in_script(c,'Latin') for c in t.form) for t in tokens),T)
    out['zh:word.decimal_digit']=ratio(sum(any(unicodedata.category(c)=='Nd' for c in t.form) for t in tokens),T)
    for name,(pos,forms) in CUES.items():
        allowed=(pos,) if type(pos)is str else pos
        out['zh:cue.'+name]=ratio(sum(t.upos in allowed and t.form in forms for t in tokens),T)
    components=defaultdict(list)
    for s in seq:components[group_ids[s.source_sentence_index]].extend(words[s.source_sentence_index])
    windows=[ts[i:i+100] for ts in components.values() for i in range(len(ts)-99)]
    out['zh:lexical.mattr100']=average([len({t.form for t in w})/100 for w in windows])
    out['zh:lexical.entropy100']=average([entropy([t.form for t in w])/math.log2(100) for w in windows])
    out['zh:upos.bigram_entropy100']=average([entropy([(a.upos,b.upos) for a,b in zip(w,w[1:])])/math.log2(17*17) for w in windows])
    # History resets at excluded gaps. Empty lexical sets are explicit missing
    # opportunities; known previous parse failure makes history-based rows null.
    history=defaultdict(list)
    for p in prior:history[group_ids[p.source_sentence_index]].append(p)
    overlaps=[];trigrams_total=trigrams_seen=initial_total=initial_seen=0
    history_failreason=None;overlap_failreason=None
    for s in seq:
        gid=group_ids[s.source_sentence_index];old=history[gid]
        current=words[s.source_sentence_index]
        if old and old[-1].source_sentence_index+1==s.source_sentence_index:
            if old[-1].status=='failed':overlap_failreason=old[-1].reason
            else:
                K=lambda ss:{t.form for t in ss.tokens if lexical(t) and t.upos in {'NOUN','PROPN','VERB','ADJ'}}
                left,right=K(old[-1]),K(s)
                if left|right:overlaps.append(len(left&right)/len(left|right))
        if any(p.status=='failed' for p in old):
            history_failreason=next(p.reason for p in old if p.status=='failed')
        else:
            oldtrigrams=set();oldinitial=set()
            for p in old:
                pt=[t for t in p.tokens if lexical(t)];forms=[t.form for t in pt]
                oldtrigrams.update(zip(forms,forms[1:],forms[2:]))
                if len(pt)>=3:oldinitial.add(tuple(t.upos for t in pt[:3]))
            forms=[t.form for t in current];tri=list(zip(forms,forms[1:],forms[2:]))
            trigrams_total+=len(tri);trigrams_seen+=sum(t in oldtrigrams for t in tri)
            if len(current)>=3 and oldinitial:
                initial_total+=1;initial_seen+=tuple(t.upos for t in current[:3]) in oldinitial
        history[gid].append(s)
    out['zh:lexical.content_overlap']=average(overlaps)
    out['zh:lexical.trigram_reuse']=ratio(trigrams_seen,trigrams_total)
    out['zh:syntax.initial_pos_reuse']=ratio(initial_seen,initial_total)
    if overlap_failreason:
        out['zh:lexical.content_overlap']=row(opportunities=None,reason=overlap_failreason)
    if history_failreason:
        for k in ('zh:lexical.trigram_reuse','zh:syntax.initial_pos_reuse'):
            out[k]=row(opportunities=None,reason=history_failreason)
    if not depfail:
        arcs=[];spans=[];normspans=[];depths=[];maxdepth=[];pred=[];sub=0;nounmods=[];rootverbs=[];mods=[]
        for s in seq:
            ts=words[s.source_sentence_index];rank={t.local_id:i for i,t in enumerate(ts)}
            children=defaultdict(list)
            for t in s.tokens:children[t.head].append(t)
            depth={}
            for t in ts:
                cur=t;d=0
                while cur.head:
                    d+=1;cur=s.tokens[cur.head-1]
                depth[t.local_id]=d
            depths.extend(depth.values())
            if depth:maxdepth.append(max(depth.values()))
            for t in ts:
                if t.head and t.head in rank and t.base_relation!='punct':
                    arcs.append(t);dist=abs(rank[t.local_id]-rank[t.head]);spans.append(dist);normspans.append(dist/(len(ts)-1))
                    if t.base_relation in {'amod','nmod','acl','advmod'}:mods.append(rank[t.local_id]<rank[t.head])
                    if t.base_relation in {'ccomp','xcomp','advcl','acl'}:sub+=1
                if t.upos in {'VERB','ADJ','AUX'} and (t.head==0 or t.base_relation in {'ccomp','xcomp','advcl','acl','conj','parataxis'}):pred.append(t)
                if t.head==0 and t.upos=='VERB':rootverbs.append(not any(c.base_relation in {'nsubj','csubj'} for c in children[t.local_id]))
                if t.upos in {'NOUN','PROPN'}:
                    seen=set();pending=[c for c in children[t.local_id] if c.base_relation in {'acl','nmod'}]
                    while pending:
                        c=pending.pop()
                        if c.local_id in seen:continue
                        seen.add(c.local_id);pending.extend(children[c.local_id])
                    nounmods.append(sum(i in rank for i in seen))
        for r in RELATIONS:out['zh:deprel.'+r]=ratio(sum(t.base_relation==r for t in arcs),len(arcs))
        out['zh:dependency.span_mean']=average(spans)
        out['zh:dependency.span_normalized']=average(normspans)
        out['zh:dependency.depth_mean']=average(depths)
        out['zh:dependency.maxdepth_median']=row(statistics.median(maxdepth),opportunities=len(maxdepth)) if maxdepth else row()
        out['zh:syntax.predicate_heads']=ratio(len(pred),len(seq))
        out['zh:syntax.subordinate_arcs']=ratio(100*sub,len(seq))
        out['zh:syntax.predicate_conj_share']=ratio(sum(t.base_relation=='conj' for t in pred),len(pred))
        out['zh:syntax.nominal_modifier_size']=average(nounmods)
        out['zh:syntax.verb_root_without_subject']=average(rootverbs)
        out['zh:syntax.preposed_modifiers']=average(mods)
    else:
        for spec in SENSORS:
            if spec.dependency=='dep' and spec.id!='zh:syntax.initial_pos_reuse':
                out[spec.id]=row(opportunities=None,reason=depfail)
    # Initial POS reuse does not in fact require dependency heads, despite its
    # catalogue family. It remains measured under pos_only.
    for k in CHANNEL_IDS:
        require(k in out,'unimplemented_channel:'+k)
        out[k]['opportunity_type']=next(s.opportunity for s in SENSORS if s.id==k)
    return out


def _view(sentences, projection, parsed):
    components=_components(projection.targets)
    complete=[s for s in sentences if _contained(s.start,s.end,components)]
    clipped=[s for s in sentences if s not in complete and any(p.start<s.end and s.start<p.end for p in components)]
    gids={s.source_sentence_index:next(i for i,c in enumerate(components) if c.start<=s.start and s.end<=c.end) for s in complete}
    rows=[];previous=[]
    for s in complete:
        features=_aggregate([s],gids,[p for p in previous if gids[p.source_sentence_index]==gids[s.source_sentence_index]])
        rows.append({'source_sentence_index':s.source_sentence_index,'source_span':[s.start,s.end],
                     'component_index':gids[s.source_sentence_index],'available_after_codepoint':s.end,
                     'parse_status':s.status,'parse_reason':s.reason,'analysis_status':s.analysis_status,
                     'warnings':s.warnings,'measurements':features,'vector':vectors(features),
                     'cue_evidence':{name:[{'span':[t.start,t.end],'upos':t.upos} for t in s.tokens
                         if lexical(t) and t.upos in ((pos,) if type(pos)is str else pos) and t.form in forms]
                         for name,(pos,forms) in CUES.items()} if s.status!='failed' else None,
                     'subset_only_if_global_ineligible':bool(clipped)})
        previous.append(s)
    global_rows=_aggregate(complete,gids,clipped=bool(clipped))
    graph_nodes=[];graph_edges=[];token_ids={};sentence_ids={}
    for s,sequence_row in zip(complete,rows):
        sid=len(graph_nodes);sentence_ids[s.source_sentence_index]=sid
        graph_nodes.append({'id':sid,'kind':'sentence','source_span':[s.start,s.end],
                            'source_sentence_index':s.source_sentence_index,'available_after_codepoint':s.end,
                            'features':sequence_row['vector']})
        for t in s.tokens:
            nid=len(graph_nodes);token_ids[(s.source_sentence_index,t.local_id)]=nid
            graph_nodes.append({'id':nid,'kind':'token:'+t.upos,'source_span':[t.start,t.end],
                                'source_sentence_index':s.source_sentence_index,'available_after_codepoint':s.end,
                                'features':None,'annotation_status':s.analysis_status})
            graph_edges.append({'source':sid,'target':nid,'relation':'contains_token','available_after_codepoint':s.end})
    for s in complete:
        for t in s.tokens:
            if t.head:
                graph_edges.append({'source':token_ids[(s.source_sentence_index,t.head)],
                 'target':token_ids[(s.source_sentence_index,t.local_id)],'relation':'ud:'+t.deprel,
                 'base_relation':t.base_relation,'available_after_codepoint':s.end,
                 'evidence_spans':[[s.tokens[t.head-1].start,s.tokens[t.head-1].end],[t.start,t.end]],
                 'analysis_status':s.analysis_status})
    for a,b in zip(complete,complete[1:]):
        if a.source_sentence_index+1==b.source_sentence_index and gids[a.source_sentence_index]==gids[b.source_sentence_index]:
            graph_edges.append({'source':sentence_ids[a.source_sentence_index],'target':sentence_ids[b.source_sentence_index],
                                'relation':'original_next_sentence','available_after_codepoint':b.end})
    return {'global_measurements':global_rows,'global_vector':vectors(global_rows),'sequence':rows,
            'graph':{'nodes':graph_nodes,'edges':graph_edges,'graph_kind':'syntactic_basic_ud_not_entity_or_discourse_graph',
                     'absence_is_not_semantic_nonexistence':True,
                     'remaining_information_paths':['token UPOS node types','typed basic dependency structure','source order','missingness']},
            'coverage':{'source_sentences':len(sentences),'complete_target_sentences':len(complete),
                        'clipped_target_sentences':len(clipped),'excluded_sentences':len(sentences)-len(complete)-len(clipped),
                        'complete_parse_failures':sum(s.status=='failed' for s in complete),
                        'complete_pos_only':sum(s.status=='pos_only' for s in complete),
                        'clipped_source_sentence_indices':[s.source_sentence_index for s in clipped]},
            'measurement_population':'all_declared_target_units' if not clipped else 'ineligible_clipped_source_units'}


def measure(observation, projection, parsed):
    require(unicodedata.unidata_version==UNICODE_VERSION,'unicode_script_category_version_mismatch')
    require(type(parsed) is ParsedSource,'expected_parsed_source');parsed.validate(observation)
    require(type(projection) is Projection,'expected_projection');projection.__post_init__()
    require(projection.source==observation.source,'exact_source_projection_mismatch')
    profile={'schema_version':SCHEMA_VERSION,'parser':asdict(parsed.profile),
             'unicode_version':unicodedata.unidata_version,'normalization':'none',
             'token_denominator':'model tokens except PUNCT and all-punctuation/whitespace tokens',
             'gap_policy':'no windows, history or adjacency across target components',
             'clipped_policy':'global abstention; complete local units diagnostic only',
             'unicode_script_property_version':UNICODE_VERSION,'unicode_scripts_sha256':SCRIPTS_SHA256}
    source=_digest(asdict(observation.source));proj=_digest(asdict(projection));prof=_digest(profile)
    # Distinct measurement profiles need distinct measurement keys; the join key
    # is source+projection and can be shared with another explicit measurement branch.
    identity={'source_sha256':source,'projection_sha256':proj,'profile_sha256':prof,
              'annotation_sha256':parsed.fingerprint,
              'source_projection_join_key_sha256':_digest({'source':asdict(observation.source),'projection':asdict(projection)})}
    identity['observation_key_sha256']=_digest(identity)
    result={'bundle_version':BUNDLE_VERSION,'source':asdict(observation.source),
            'projection':asdict(projection),'profile':profile,'identity':identity,
            'measurement_status':'candidate_unvalidated','reference_distribution':None,
            'personalization_admitted':False,'empirical_model_admitted':False,
            'information_mode':'retrospective_source_units_with_sentence_local_parse; exact-prefix producer rerun required for prediction',
            'target':_view(parsed.sentences,projection,parsed)}
    # Keep complete error/quality ledger; counts are not style channels.
    result['parse_audit']={'sentence_statuses':dict(Counter(s.status for s in parsed.sentences)),
       'errors':[{'source_sentence_index':s.source_sentence_index,'reason':s.reason} for s in parsed.sentences if s.reason],
       'upos_inventory':dict(Counter(t.upos for s in parsed.sentences for t in s.tokens)),
       'relation_inventory':dict(Counter(t.deprel for s in parsed.sentences for t in s.tokens if t.deprel)),
       'confidence':'not_calibrated','alternative_analyses':'not_enumerated'}
    return result
