"""Source-only final lineage closure and quota proposal, never model admission.

Metadata and verified copy/lineage evidence only. Caller must independently bind
source maps, signature coverage and all matching receipts before using outputs.
"""
from __future__ import annotations
from collections import defaultdict,Counter
import hashlib,importlib.util,json,pathlib,sys

ALLOCATOR=pathlib.Path('/workspace/shared/style-learning-pilot/scale10-plan-v03/sample_metadata.py')
ALLOCATOR_SHA256='2aabab330821a7daca9953dd4339ff46bc1cac618588b16596384b75de9a3c08'
if hashlib.sha256(ALLOCATOR.read_bytes()).hexdigest()!=ALLOCATOR_SHA256:raise ValueError('reviewed_allocator_changed')
spec=importlib.util.spec_from_file_location('_scale10_reviewed_allocator',ALLOCATOR);alloc=importlib.util.module_from_spec(spec);spec.loader.exec_module(alloc)
EDGE_KINDS={'old_component','common_version','direct_section','known_translation','known_reprint','concrete_unresolved','raw_exact','normalized_exact','long_block_exact','near_copy'}


def validate_edge(edge):
    if set(edge)!={'a','b','kind','evidence'} or edge['kind'] not in EDGE_KINDS:raise ValueError('invalid_lineage_edge')
    ev=edge['evidence'];kind=edge['kind']
    if not isinstance(ev,dict):raise ValueError('lineage_evidence_required')
    if kind=='near_copy':
        common,a,b=(ev.get(k) for k in ('shared_distinct_grams','left_distinct_grams','right_distinct_grams'))
        if any(type(x)is not int or x<0 for x in (common,a,b)) or common>min(a,b) or common<40 or 5*common<4*min(a,b):raise ValueError('near_copy_evidence_below_threshold')
        if ev.get('gram_domain')!='char5-nfkc-no-ws/v1' or ev.get('unicode_version')!='15.0.0':raise ValueError('signature_domain_mismatch')
        if ev.get('full_distinct_counts') is not True:raise ValueError('truncated_gram_denominator')
    elif kind in {'raw_exact','normalized_exact','long_block_exact'}:
        value=ev.get('sha256')
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('exact_digest_invalid')
        if kind=='long_block_exact' and (type(ev.get('normalized_codepoints'))is not int or ev['normalized_codepoints']<64):raise ValueError('short_block_not_edge')
        if kind!='raw_exact' and (ev.get('domain')!='nfkc-no-ws/v1' or ev.get('unicode_version')!='15.0.0'):raise ValueError('signature_domain_mismatch')
    else:
        if not isinstance(ev.get('metadata_evidence_sha256'),str) or len(ev['metadata_evidence_sha256'])!=64:raise ValueError('lineage_metadata_evidence_missing')
    return edge['a'],edge['b']


def finish_gate(rows,base_members,base_component_map,old_excluded_members,new_edges,calibration_rows,diagnostic_members,quotas=None):
    """Return private proposal and public zero-violation counts. No body access.

    Every row supplies qualification and complete matching coverage as separately
    reviewed source-stage facts. This kernel does not assert those facts itself.
    """
    rows=list(rows);members=set(base_members);old_excluded=set(old_excluded_members);edges=list(new_edges);calibration=list(calibration_rows);diagnostics=set(diagnostic_members)
    if set(base_component_map)!=members:raise ValueError('base_member_coverage_mismatch')
    if not old_excluded<=members or not diagnostics<=members:raise ValueError('exclusion_member_missing')
    oldgroups=defaultdict(list)
    for m,c in base_component_map.items():oldgroups[c].append(m)
    oldedges=[(group[0],m) for group in oldgroups.values() for m in group[1:]]
    newpairs=[validate_edge(e) for e in edges]
    for pair in newpairs:
        if not set(pair)<=members:raise ValueError('new_edge_member_missing')
    oldmapping,oldcontaminated=alloc.freeze_components(members,oldedges+newpairs,[],old_excluded|diagnostics)
    source_calibration={}
    for source in alloc.QUOTAS:
        source_rows=[r for r in calibration if r['source_frame']==source]
        if len(source_rows)!=32:raise ValueError('calibration_frozen_count')
        groups={oldmapping[r['member_key']] for r in source_rows}
        if len(groups)!=32 or groups&oldcontaminated:raise ValueError('calibration_underfilled_or_old_contaminated')
        source_calibration[source]=len(groups)
    if len({oldmapping[r['member_key']] for r in calibration})!=96:raise ValueError('calibration_cross_source_collision')
    exposed=old_excluded|diagnostics|{r['member_key'] for r in calibration}
    mapping,excluded=alloc.freeze_components(members,oldedges+newpairs,[],exposed)
    prepared=[];counts=Counter();source_counts=defaultdict(Counter)
    seen=set()
    for r in rows:
        required={'record_key','member_key','source_frame','source_sha256','projection_sha256','projection_profile','preparse_eligible','matching_coverage_complete','rights_role_resolution','frozen_candidate'}
        if set(r)!=required:raise ValueError('source_stage_fields_only')
        if r['record_key'] in seen:raise ValueError('duplicate_candidate_record')
        seen.add(r['record_key'])
        if r['member_key'] not in mapping:raise ValueError('candidate_member_missing')
        if r['source_frame'] not in alloc.QUOTAS:raise ValueError('invalid_source_frame')
        if r['frozen_candidate'] is not True:raise ValueError('posthoc_candidate_added')
        if type(r['matching_coverage_complete'])is not bool or type(r['preparse_eligible'])is not bool:raise ValueError('invalid_boolean')
        if r['rights_role_resolution'] not in {'calibrated_allowlist','quarantined','unknown'}:raise ValueError('invalid_role_resolution')
        counts['candidate_records']+=1;source_counts[r['source_frame']]['candidate_records']+=1
        admitted=r['preparse_eligible'] and r['matching_coverage_complete'] and r['rights_role_resolution']=='calibrated_allowlist'
        if not r['matching_coverage_complete']:counts['quarantined_missing_comparable_signatures']+=1
        if r['rights_role_resolution']!='calibrated_allowlist':counts['quarantined_roles_or_rights']+=1
        if admitted:source_counts[r['source_frame']]['eligible_before_exclusions']+=1
        prepared.append({k:r[k] for k in ('record_key','source_frame','source_sha256','projection_sha256','projection_profile')}|{'preparse_eligible':admitted,'component_id':mapping[r['member_key']]})
    proposal=alloc.allocate(prepared,excluded,quotas)
    part={r['component_id']:r['partition'] for r in proposal['selected_records']}
    cross=sum(1 for a,b in newpairs if mapping[a] in part and mapping[b] in part and part[mapping[a]]!=part[mapping[b]])
    oldcross=len({r['component_id'] for r in proposal['selected_records']}&excluded)
    if cross or oldcross:raise AssertionError('lineage_split_violation')
    public={'schema_version':'scale10-source-lineage-gate/0.1','status':'underfilled_stop' if proposal['status']=='underfilled_stop' else 'quota_proposal_complete_independent_G2_review_required','counts':dict(counts),'source_counts':{k:dict(v) for k,v in source_counts.items()},'calibration_final_components':source_calibration,'new_edge_kinds':dict(Counter(e['kind'] for e in edges)),'coverage':proposal['coverage'],'cross_split_hard_edges':cross,'selected_old_or_exposed_components':oldcross,'duplicate_selected_components':len(proposal['selected_records'])-len({r['component_id'] for r in proposal['selected_records']}),'selection_sha256':proposal['selection_sha256'],'G2_admitted':False,'parser_or_fit_authorized':False}
    return {'public':public,'private':{'proposal':proposal,'member_component_map':mapping,'excluded_components':sorted(excluded)}}
