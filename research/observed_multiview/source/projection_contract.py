"""Independent source-map reconstruction and cache binding; no source I/O."""
import hashlib
from project_wikitext import PROFILE, canonical, entity_value, sha, _inline


def validate_projection(source, result):
    if result.get('profile')!=PROFILE or result.get('source_sha256')!=sha(source) or result.get('source_codepoints')!=len(source):raise ValueError('source_or_profile_changed')
    payload={k:v for k,v in result.items() if k!='projection_sha256'}
    if result.get('projection_sha256')!=hashlib.sha256(canonical(payload)).hexdigest():raise ValueError('projection_hash_changed')
    previous_end=0; emitted=0
    for index,segment in enumerate(result['segments']):
        if segment['index']!=index:raise ValueError('segment_index')
        spans=segment['source_spans']
        if len(spans)!=1:raise ValueError('contiguous_source_span_required')
        lo,hi=spans[0]
        if not (0<=previous_end<=lo<hi<=len(source)):raise ValueError('source_span_order')
        if any(b['start']<hi and b['end']>lo for b in result['barriers']):raise ValueError('barrier_bridging')
        previous_end=hi;mapping=segment['source_map'];text=segment['text']
        if len(mapping)!=len(text):raise ValueError('map_length')
        prior=(-1,-1);prior_output=-1
        for char,row in zip(text,mapping):
            if not isinstance(row,list) or len(row)!=4:raise ValueError('map_shape')
            start,end,op,out=row
            if type(start)is not int or type(end)is not int or type(out)is not int or not lo<=start<end<=hi:raise ValueError('map_bounds')
            if (start,end)<prior or ((start,end)!=prior and start<prior[1]):raise ValueError('nonmonotone_map')
            if (start,end)==prior and out!=prior_output+1:raise ValueError('entity_output_order')
            if (start,end)!=prior and out!=0:raise ValueError('entity_output_start')
            if op=='identity':
                if end!=start+1 or out!=0 or source[start:end]!=char:raise ValueError('identity_map_mismatch')
            elif op=='entity':
                value=entity_value(source[start:end])
                if not 0<=out<len(value) or value[out]!=char:raise ValueError('entity_map_mismatch')
            else:raise ValueError('unsupported_map_operation')
            prior=(start,end);prior_output=out;emitted+=1
        expected_text,expected_mapping=_inline(source[lo:hi],lo)
        if expected_text!=text or expected_mapping!=mapping:raise ValueError('unapproved_deletion_or_projection')
        # Verify entity expansions are complete, not selected characters.
        for i,row in enumerate(mapping):
            if row[2]=='entity' and (i+1==len(mapping) or mapping[i+1][:2]!=row[:2]):
                if row[3]+1!=len(entity_value(source[row[0]:row[1]])):raise ValueError('incomplete_entity_expansion')
    for b in result['barriers']:
        if not 0<=b['start']<b['end']<=len(source) or not b['reasons']:raise ValueError('invalid_barrier')
    return {'status':'source_map_verified','emitted_codepoints':emitted,'segments':len(result['segments']),'barriers':len(result['barriers']),'nonreconstructible_codepoints':0}
