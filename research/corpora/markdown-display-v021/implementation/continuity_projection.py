"""Synthetic-reviewed development profile for proved syntax-only continuity.

No natural runner. Never executes source Markdown, fetches links, or fits a model.
The frozen v01 parser is retained as a stricter structural/quarantine substrate.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import sys
import types

BASE_PATH=Path('/workspace/shared/style-markdown-projection-v01/public/markdown_projection.py')
BASE_SHA='06da4976dfd55f48f55a23600f32561dd2325fcc1c7d3abb94b73752a9680f2a'
PROFILE='historical-blog-markdown-display-continuity/0.2.1'
SCHEMA='markdown-display-continuity/2.1'

def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
base_raw=BASE_PATH.read_bytes()
if sha(base_raw)!=BASE_SHA:raise RuntimeError('frozen_v01_base_changed')
base=types.ModuleType('markdown_projection_v01_frozen')
base.__file__=str(BASE_PATH);sys.modules[base.__name__]=base
exec(compile(base_raw,str(BASE_PATH),'exec'),base.__dict__)
ProjectionError=base.ProjectionError


def runs(indices):
    result=[]
    for i in indices:
        if result and result[-1][1]==i:result[-1][1]=i+1
        else:result.append([i,i+1])
    return result


def grammar_with_maps(raw):
    """Replay only the frozen structural setup, with exact parser-owned maps."""
    src,mapping=base.normalized_source(raw);starts=base.line_offsets(src)
    front=base.frontmatter_scope(src)
    if src.startswith('\ufeff') and not front:front=[base.Scope(0,1,'bom')]
    masked=base.blank_regions(src,front);md=base.parser()
    preliminary=md.parse(masked,{})
    if len(preliminary)>base.MAX_AST_TOKENS:raise ProjectionError('preliminary_ast_token_cap')
    protected=list(front)
    for token in preliminary:
        if token.type in {'fence','code_block'}:
            a,b=base.block_bounds(token,starts,len(src));protected.append(base.Scope(a,b,token.type))
        elif token.type=='inline' and 'source_offsets' in token.meta:
            if len(token.content)>base.MAX_INLINE_CHARS:raise ProjectionError('inline_character_cap')
            md.inline.parse(token.content,md,{},[])
            for e in md.inline.last_events:
                if e['rule']=='backticks' and 'code_inline' in e['tokens']:
                    offsets=token.meta['source_offsets'][e['start']:e['end']]
                    if offsets:protected.append(base.Scope(offsets[0],offsets[-1]+1,'inline_code'))
    extra=base.extension_scopes(masked,protected);expanded=[]
    for region in extra:
        a=src.rfind('\n',0,region.start)+1;q=src.find('\n',region.end)
        b=q+1 if q>=0 else len(src)
        if region.end>region.start and src[region.end-1:region.end]=='\n':b=region.end
        expanded.append(base.Scope(a,b,region.role,region.unresolved))
    env={};tokens=md.parse(base.blank_regions(src,front+expanded),env)
    if len(tokens)>base.MAX_AST_TOKENS:raise ProjectionError('ast_token_cap')
    return src,mapping,starts,md,tokens,env


def _derive(data):
    initial=base.project_bytes(data)
    raw=data.decode('utf-8');n=len(raw)
    # Each raw codepoint has exactly one final classification.
    roles=['unclassified']*n;kinds=['barrier']*n;paragraphs=[None]*n;proof_ids=[set() for _ in raw]
    for region in initial['regions']:
        a,b=region['source_char_span'];role=region['role']
        for i in range(a,b):roles[i]=role
    issues=list(initial['issues']);proofs=[];table_scopes=[];table_caption_scopes=[];paragraph_context={}

    if not issues:
        src,mapping,starts,md,tokens,env=grammar_with_maps(raw)
        def raw_indices(offsets):
            return [r for o in offsets for r in range(*mapping[o])]
        def mark(offsets,kind,role,pid,proof=None):
            for r in raw_indices(offsets):
                kinds[r]=kind;roles[r]=role;paragraphs[r]=pid
                if proof is not None:proof_ids[r].add(proof)
        def add_proof(kind,offset_groups,pid,types):
            indices=[r for group in offset_groups for r in raw_indices(group)]
            ident=len(proofs)
            proofs.append({'id':ident,'kind':kind,'source_spans':runs(sorted(indices)),
                           'paragraph_id':pid,'ast_types':types,'base_sha256':BASE_SHA})
            return ident

        def inline(content,offsets,pid,list_context=False,depth=0,label=False):
            if depth>16:raise ProjectionError('link_label_recursion_cap')
            if len(offsets)!=len(content) or any(src[o]!=c for o,c in zip(offsets,content)):
                raise ProjectionError('inline_source_alignment')
            local_roles,local_errors,types=base.inline_roles(md,content,env,list_context)
            events=list(md.inline.last_events)
            issues.extend(local_errors)
            for j,role in enumerate(local_roles):
                mark(offsets[j:j+1],'content' if role=='prose' else 'barrier',
                     ('link_label_text' if label else 'body_text') if role=='prose' else role,pid)
            # The substrate rejects unresolved delimiter text. Only remaining
            # source markers consumed by the CommonMark emphasis rule qualify.
            for e in events:
                a,b=e['start'],e['end']
                if e['rule']=='emphasis' and all(x=='emphasis_marker' for x in local_roles[a:b]):
                    proof=add_proof('resolved_emphasis_delimiters',[offsets[a:b]],pid,types)
                    mark(offsets[a:b],'syntax_only','emphasis_delimiter',pid,proof)
            # Longer link events first. The grammar already validated each link;
            # parseLinkLabel merely locates its exact visible-label source slice.
            for e in sorted(events,key=lambda x:x['end']-x['start'],reverse=True):
                a,b=e['start'],e['end']
                if e['rule']!='link' or not all(x=='link_label_and_destination' for x in local_roles[a:b]):continue
                if 'link_open' not in e['tokens'] or 'link_close' not in e['tokens'] or content[a:a+1]!='[':
                    raise ProjectionError('unproved_link_event')
                state=base.StateInline(content,md,env,[]);state.projection_events=[]
                end=md.helpers.parseLinkLabel(state,a,True)
                if not a<end<b or content[end]!=']':raise ProjectionError('link_label_boundary')
                # Wrapper/destination/title/reference-key source is non-visible
                # syntax. The visible label is independently parsed recursively.
                proof=add_proof('validated_link_wrapper',[offsets[a:a+1],offsets[end:b]],pid,e['tokens'])
                mark(offsets[a:a+1],'syntax_only','link_wrapper',pid,proof)
                mark(offsets[end:b],'syntax_only','link_wrapper',pid,proof)
                inline(content[a+1:end],offsets[a+1:end],pid,False,depth+1,True)

        stack=[];container_path=[];pid=0;previous_image=False;table_after=None;table_context=None
        prior_paragraph_blocks=[];list_blocks=[]
        for token_index,token in enumerate(tokens):
            if token.type=='paragraph_open':prior_paragraph_blocks.append(base.block_bounds(token,starts,len(src)))
            elif token.type in {'bullet_list_open','ordered_list_open'}:list_blocks.append(base.block_bounds(token,starts,len(src)))
            if token.type=='table_open':
                table_start,table_end=base.block_bounds(token,starts,len(src))
                adjacent=[(a,b) for a,b in prior_paragraph_blocks if b<=table_start and not src[b:table_start].strip()]
                if adjacent:
                    a,b=max(adjacent,key=lambda pair:pair[1])
                    containing=[(x,y) for x,y in list_blocks if x<=a<b<=y<=table_start and not src[y:table_start].strip()]
                    if containing:a,b=min(containing,key=lambda pair:pair[0])
                    table_caption_scopes.append([mapping[a][0],mapping[b][0] if b<len(mapping) else n])
                if table_after is None:
                    # Token types alone alias sibling containers. The complete
                    # path of opener indices identifies this actual AST container.
                    table_after=table_end;table_context=tuple(container_path)
                previous_image=False
            elif token.type in {'heading_open','hr'}:
                if table_after is not None and tuple(container_path)==table_context:
                    end=base.block_bounds(token,starts,len(src))[0]
                    if table_after<end:table_scopes.append([mapping[table_after][0] if table_after<len(mapping) else n,mapping[end][0] if end<len(mapping) else n])
                    table_after=None
                    table_context=None
                previous_image=False
            elif token.type in {'fence','code_block','html_block','definition'}:previous_image=False
            if token.nesting==-1:
                if not stack:raise ProjectionError('ast_stack_underflow')
                stack.pop();container_path.pop();continue
            ancestors=tuple(stack)
            if token.type=='inline':
                if not ancestors or ancestors[-1]!='paragraph_open' or any(x in ancestors for x in ('blockquote_open','heading_open','table_open')):
                    previous_image=False
                elif 'source_offsets' in token.meta:
                    local_roles,errs,types=base.inline_roles(md,token.content,env,'list_item_open' in ancestors)
                    issues.extend(errs)
                    image='image' in types
                    raw_roles={roles[r] for r in raw_indices(token.meta['source_offsets'])}
                    protected_paragraph=(image or previous_image or any('caption' in x or x=='heading' for x in raw_roles))
                    previous_image=image
                    if not protected_paragraph:
                        paragraph_context[pid]='list_prose_candidate' if 'list_item_open' in ancestors else 'body_prose_candidate'
                        inline(token.content,token.meta['source_offsets'],pid,'list_item_open' in ancestors)
                        pid+=1
            if token.nesting==1:
                stack.append(token.type)
                container_path.append((token.type,token_index))
        if table_after is not None and table_after<len(mapping):table_scopes.append([mapping[table_after][0],n])
        for a,b in table_scopes:
            for i in range(a,b):
                if roles[i]=='table':continue
                kinds[i]='barrier';roles[i]='unresolved_table_annotation_scope';paragraphs[i]=None;proof_ids[i].clear()
        for a,b in table_caption_scopes:
            for i in range(a,b):
                kinds[i]='barrier';roles[i]='unresolved_table_caption_scope';paragraphs[i]=None;proof_ids[i].clear()
    issues=sorted(set(issues))
    if issues:
        for i in range(n):
            if kinds[i] in {'content','syntax_only'}:
                kinds[i]='barrier';roles[i]='quarantined_inline_scope';proof_ids[i].clear()

    groups=[];current=[];pid=None
    def flush():
        nonlocal current,pid
        if current:
            if ''.join(raw[i] for i in current).strip():groups.append((pid,current))
            else:
                for i in current:kinds[i]='barrier';roles[i]='discarded_visible_whitespace'
        current=[];pid=None
    for i,kind in enumerate(kinds):
        if kind=='content':
            if current and paragraphs[i]!=pid:flush()
            if not current:pid=paragraphs[i]
            current.append(i)
        elif kind=='barrier':flush()
    flush()
    segments=[]
    for pid,indices in groups:
        spans=runs(indices);edges=[];offset=0
        for left,right in zip(spans,spans[1:]):
            offset+=left[1]-left[0];a,b=left[1],right[0]
            if any(kinds[i]!='syntax_only' for i in range(a,b)):raise ProjectionError('content_gap_bridge')
            edges.append({'left_output':offset-1,'right_output':offset,'source_gap':[a,b],
                          'kind':'proved_syntax_only_elision','proof_ids':sorted(set().union(*(proof_ids[i] for i in range(a,b))))})
        text=''.join(raw[i] for i in indices)
        segments.append({'index':len(segments),'paragraph_id':pid,'context_role':paragraph_context[pid],
                         'text':text,'text_sha256':sha(text.encode()),'source_spans':spans,
                         'source_map':[[i,i+1,'identity',0] for i in indices],
                         'source_cover':[indices[0],indices[-1]+1],'continuity_edges':edges})
    regions=[];i=0
    while i<n:
        j=i+1
        while j<n and (kinds[j],roles[j],paragraphs[j],proof_ids[j])==(kinds[i],roles[i],paragraphs[i],proof_ids[i]):j+=1
        regions.append({'start':i,'end':j,'kind':kinds[i],'role':roles[i],
                        'paragraph_id':paragraphs[i],'proof_ids':sorted(proof_ids[i])});i=j
    boundaries=[]
    for left,right in zip(segments,segments[1:]):
        a,b=left['source_cover'][1],right['source_cover'][0]
        boundaries.append({'left_segment':left['index'],'right_segment':right['index'],
                           'source_gap':[a,b],'kind':'removed_content_or_unknown_boundary',
                           'reasons':sorted(set(roles[a:b]))})
    result={'schema_version':SCHEMA,'profile':PROFILE,'base_sha256':BASE_SHA,
            'source_frame':'historical_blog_markdown','source_sha256':sha(data),'source_bytes':len(data),'source_codepoints':n,
            'segments':segments,'regions':regions,'barriers':[r for r in regions if r['kind']=='barrier'],
            'syntax_elisions':[r for r in regions if r['kind']=='syntax_only'],'syntax_proofs':proofs,
            'content_boundaries':boundaries,'table_annotation_scopes':table_scopes,
            'table_caption_scopes':table_caption_scopes,'issues':issues,
            'structural_status':'quarantined' if issues else 'projected',
            'counts':{'segments':len(segments),'projected_codepoints':sum(len(s['text']) for s in segments),
                      'syntax_continuity_edges':sum(len(s['continuity_edges']) for s in segments)},
            'semantic_equivalence_claimed':False,'human_origin':'unknown','rights_status':'unverified',
            'author_attribution':'unverified','model_admitted':False,'split_eligible':False,
            'natural_validation_performed':False,'old_exclusion_certificate_applies':False}
    result['projection_sha256']=sha(canonical(result))
    return result


def project_bytes(data):
    result=_derive(data);validate_projection(data,result,replay=False);return result


def validate_projection(data,result,*,replay=True):
    raw=data.decode('utf-8');n=len(raw)
    # Public validation re-derives the frozen profile from the already-supplied
    # bytes. This is not a second source read, and is never a semantic oracle.
    # It prevents a rehashed forged syntax certificate from authorizing elision.
    if replay and result!=_derive(data):raise ProjectionError('frozen_profile_replay_mismatch')
    if result['profile']!=PROFILE or result['schema_version']!=SCHEMA or result['base_sha256']!=BASE_SHA:
        raise ProjectionError('profile_binding')
    if result['source_sha256']!=sha(data) or result['source_bytes']!=len(data) or result['source_codepoints']!=n:
        raise ProjectionError('source_binding')
    if result['projection_sha256']!=sha(canonical({k:v for k,v in result.items() if k!='projection_sha256'})):
        raise ProjectionError('projection_hash')
    kinds=[None]*n;roles=[None]*n;paragraphs=[None]*n;proof_ids=[None]*n;end=0
    for region in result['regions']:
        a,b=region['start'],region['end']
        if type(a)is not int or type(b)is not int or a!=end or not a<b<=n or region['kind'] not in {'content','syntax_only','barrier'}:raise ProjectionError('source_partition')
        for i in range(a,b):kinds[i]=region['kind'];roles[i]=region['role'];paragraphs[i]=region['paragraph_id'];proof_ids[i]=region['proof_ids']
        end=b
    if end!=n:raise ProjectionError('source_partition_tail')
    for p in result['syntax_proofs']:
        if p['id']!=result['syntax_proofs'].index(p) or p['kind'] not in {'resolved_emphasis_delimiters','validated_link_wrapper'} or p['base_sha256']!=BASE_SHA:raise ProjectionError('syntax_proof_schema')
        for a,b in p['source_spans']:
            if not 0<=a<b<=n:raise ProjectionError('syntax_proof_bounds')
    observed=[];previous=-1
    for index,segment in enumerate(result['segments']):
        if segment['index']!=index:raise ProjectionError('segment_index')
        indices=[];spans=segment['source_spans']
        for a,b in spans:
            if type(a)is not int or type(b)is not int or not previous<=a<b<=n:raise ProjectionError('source_span_order')
            indices.extend(range(a,b));previous=b
        if not indices or any(kinds[i]!='content' or paragraphs[i]!=segment['paragraph_id'] for i in indices):raise ProjectionError('content_span_role')
        if segment['source_cover']!=[indices[0],indices[-1]+1] or segment['text']!=''.join(raw[i] for i in indices) or segment['source_map']!=[[i,i+1,'identity',0] for i in indices]:raise ProjectionError('character_provenance')
        if segment['text_sha256']!=sha(segment['text'].encode()):raise ProjectionError('text_hash')
        expected=[];offset=0
        for left,right in zip(spans,spans[1:]):
            offset+=left[1]-left[0];a,b=left[1],right[0]
            if a==b or any(kinds[i]!='syntax_only' for i in range(a,b)):raise ProjectionError('hard_content_boundary_bridged')
            ids=sorted(set(x for i in range(a,b) for x in proof_ids[i]))
            if not ids:raise ProjectionError('unproved_syntax_gap')
            for i in range(a,b):
                if not any(0<=pid<len(result['syntax_proofs']) and any(lo<=i<hi for lo,hi in result['syntax_proofs'][pid]['source_spans']) for pid in proof_ids[i]):raise ProjectionError('syntax_gap_proof_coverage')
            expected.append({'left_output':offset-1,'right_output':offset,'source_gap':[a,b],'kind':'proved_syntax_only_elision','proof_ids':ids})
        if segment['continuity_edges']!=expected:raise ProjectionError('continuity_edge_binding')
        observed.extend(indices)
    if observed!=[i for i,k in enumerate(kinds) if k=='content']:raise ProjectionError('content_coverage')
    if result['barriers']!=[r for r in result['regions'] if r['kind']=='barrier'] or result['syntax_elisions']!=[r for r in result['regions'] if r['kind']=='syntax_only']:raise ProjectionError('partition_views')
    if result['counts']!={'segments':len(result['segments']),'projected_codepoints':len(observed),'syntax_continuity_edges':sum(len(s['continuity_edges']) for s in result['segments'])}:raise ProjectionError('count_binding')
    if result['structural_status']!=('quarantined' if result['issues'] else 'projected') or result['issues'] and result['segments']:raise ProjectionError('quarantine_consistency')
    for key in ('semantic_equivalence_claimed','model_admitted','split_eligible','natural_validation_performed','old_exclusion_certificate_applies'):
        if result[key] is not False:raise ProjectionError('unwarranted_claim:'+key)
    if result['human_origin']!='unknown' or result['rights_status']!='unverified' or result['author_attribution']!='unverified':raise ProjectionError('origin_or_rights_claim')
    return True
