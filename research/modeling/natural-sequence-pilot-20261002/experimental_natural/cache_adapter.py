"""Verified TRAIN/DEV cache adapter. Never opens raw releases or TEST caches."""
from collections import Counter
from dataclasses import dataclass
import gzip,hashlib,json,math
from pathlib import Path
import torch
from .schema import NaturalMeasurementRecord,FitAuthorization

@dataclass(frozen=True)
class CacheDescriptor:
    path:str
    sha256:str
    question:str
    answer:str
    component:str
    source:str
    split:str
    arm:str
    protocol_sha256:str
    exposed:bool=False
    def validate_before_read(self):
        if self.split not in ('train','dev') or self.arm not in ('human','chatgpt'):raise PermissionError('Cache-body split/generator firewall')
        if len(self.sha256)!=64 or len(self.protocol_sha256)!=64:raise ValueError('Verified cache/protocol hashes required')

def from_cache_payload(payload,descriptor,catalog,*,kind='natural'):
    descriptor.validate_before_read();c=payload['cohort']
    expected={'question_family_id':descriptor.question,'pair_id':descriptor.answer,'component_id':descriptor.component,'source':descriptor.source,'split':descriptor.split,'arm':descriptor.arm}
    if any(c.get(k)!=v for k,v in expected.items()):raise ValueError('Frozen cohort/cache join mismatch')
    if payload['protocol_sha256']!=descriptor.protocol_sha256:raise ValueError('Wrong extraction contract')
    if set(payload['history_channel_ids_audit_only'])!={'zh:lexical.content_overlap','zh:lexical.trigram_reuse','zh:syntax.initial_pos_reuse'}:raise ValueError('History-channel provenance mismatch')
    if payload['information_mode']!='supplied_complete_unit_annotation_sequence_not_certified_live_prefix':raise ValueError('Wrong information boundary')
    units=payload['structural_units'];indices=[u['source_sentence_index'] for u in units]
    if len(set(indices))!=len(indices) or indices!=sorted(indices):raise ValueError('Duplicate or unordered source units')
    values=torch.full((len(units),len(catalog.ids)),float('nan'));opportunities=torch.full_like(values,float('nan'))
    bundle=payload['bundle'];failure=payload['source_failure'];rows={}
    if bundle is not None:
        if bundle['measurement_status']!='candidate_unvalidated' or bundle['empirical_model_admitted'] is not False or bundle['learned_contract_compatible'] is not False:raise ValueError('Instrument flags changed')
        seq=bundle['target']['sequence'];rows={r['source_sentence_index']:r for r in seq}
        if len(rows)!=len(seq) or set(rows)!=set(indices):raise ValueError('Structural/measurement unit join mismatch')
    elif failure is None:raise ValueError('No bundle and no explicit source failure')
    reasons=Counter();statuses=Counter();unit_failure=False
    for t,u in enumerate(units):
        if u[catalog.ids[-2]]!=u['source_span'][1]-u['source_span'][0]:raise ValueError('Structural span width mismatch')
        if bundle is not None:
            row=rows[u['source_sentence_index']]
            if row['source_span']!=u['source_span']:raise ValueError('Structural span join mismatch')
            if tuple(row['vector']['channel_ids'])!=catalog.all_71_ids or set(row['measurements'])!=set(catalog.all_71_ids):raise ValueError('Exact71-channel schema mismatch')
            unit_failure|=row.get('parse_status')=='failed' or row.get('parse_reason') is not None
            for j,channel in enumerate(catalog.ids[:68]):
                m=row['measurements'][channel]
                if m['comparison_eligible'] is not False:raise ValueError('Cannot promote eligibility')
                value=m['value'];opportunity=m['opportunities']
                if value is None:
                    if m['status']!='unavailable' or m.get('missing_reason') is None:raise ValueError('Malformed typed missing measurement')
                elif not math.isfinite(value) or m.get('missing_reason') is not None or m['status']!=('zero_observed' if value==0 else 'observed'):raise ValueError('Malformed observed measurement')
                if opportunity is not None and (not math.isfinite(opportunity) or opportunity<0):raise ValueError('Malformed opportunity')
                if value is not None:values[t,j]=float(value)
                if opportunity is not None:opportunities[t,j]=float(opportunity)
                if m.get('missing_reason'):reasons[m['missing_reason']]+=1
                statuses[m['status']]+=1
        elif failure:reasons[failure['reason']]+=68
        for j in catalog.structural_indices:
            value=u[catalog.ids[j]]
            if value is not None:values[t,j]=float(value)
        if u.get('lexical_token_count_missing_reason'):reasons[u['lexical_token_count_missing_reason']]+=1
    audit={'quality_claim':'candidate_unvalidated','comparison_eligible':False,'empirical_model_admitted':False,'learned_contract_compatible':False,
        'cache_path':descriptor.path,'cache_sha256':descriptor.sha256,'protocol_sha256':descriptor.protocol_sha256,'source_failure':failure,
        'unit_parse_or_resource_failure':unit_failure,'missing_reason_counts':dict(reasons),'measurement_status_counts':dict(statuses),
        'full_exact_71_audit':'unchanged_private_cache','discourse_graph':{'value':None,'missing_reason':'no_validated_M4_producer'}}
    return NaturalMeasurementRecord(descriptor.question,descriptor.answer,descriptor.component,descriptor.source,descriptor.split,descriptor.arm,
        values,opportunities,audit,kind=kind,exposed=descriptor.exposed,direct_count_indices=catalog.structural_indices)

def load_train_dev_cache(descriptor,catalog,authorization=FitAuthorization()):
    descriptor.validate_before_read()
    if not authorization.approved or not authorization.receipt or 'read_train_dev_features' not in authorization.actions:raise PermissionError('Explicit bounded feature-access approval required')
    blob=Path(descriptor.path).read_bytes()
    if hashlib.sha256(blob).hexdigest()!=descriptor.sha256:raise ValueError('Cache hash mismatch')
    return from_cache_payload(json.loads(gzip.decompress(blob)),descriptor,catalog)
