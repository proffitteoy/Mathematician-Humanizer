"""Private audit records and strict five-field prefix-only forward boundary."""
from dataclasses import dataclass,fields
from typing import Mapping
import json
from pathlib import Path
import torch
CONTRACT_PATH=Path(__file__).resolve().parents[1]/'training_contract.json'

@dataclass(frozen=True)
class Catalog:
    ids:tuple
    families:tuple
    transforms:tuple
    structural_indices:tuple
    all_71_ids:tuple
    @classmethod
    def from_contract(cls,path=CONTRACT_PATH):
        m=json.loads(Path(path).read_text())['measurement'];local=tuple(m['core_local_channel_ids_68'])
        structural=tuple(m['supplemental_structural_ids']);all_ids=tuple(m['channel_ids_exact_71'])
        if len(all_ids)!=71 or len(set(all_ids))!=71:raise ValueError('Exact unique71-channel catalog required')
        excluded={'zh:lexical.content_overlap','zh:lexical.trigram_reuse','zh:syntax.initial_pos_reuse'}
        if local!=tuple(x for x in all_ids if x not in excluded):raise ValueError('Safe local catalog mismatch')
        family={x:k for k,v in m['families'].items() for x in v};ids=local+structural
        return cls(ids,tuple(family[x] if x in family else 'structural_length' for x in ids),
            tuple(m['per_channel_transform'][x] if x in local else m['structural_transform'] for x in ids),
            tuple(range(len(local),len(ids))),all_ids)

@dataclass(frozen=True)
class NaturalMeasurementRecord:
    """Private audit identity. Exact71 typed observations remain in the unchanged cache."""
    question:str
    answer:str
    component:str
    source:str
    split:str
    arm:str
    values:torch.Tensor
    opportunity:torch.Tensor
    measurement_audit:Mapping
    kind:str='natural'
    panel:str=''
    exposed:bool=False
    direct_count_indices:tuple=()
    def __post_init__(self):
        if self.values.ndim!=2 or self.opportunity.shape!=self.values.shape:raise ValueError('Equally shaped2D arrays required')
        if self.kind not in ('natural','synthetic'):raise ValueError('Unknown data kind')
        if self.split not in ('train','dev','test'):raise ValueError('Unknown split')
        if self.arm not in ('human','chatgpt','davinci'):raise ValueError('Unknown arm')
        if torch.isinf(self.values).any() or torch.isinf(self.opportunity).any():raise ValueError('Infinite measurements')
        known=~torch.isnan(self.opportunity)
        if (self.opportunity[known]<0).any():raise ValueError('Negative opportunities')
        zero=self.values==0
        if self.direct_count_indices:
            if any(i<0 or i>=self.values.shape[1] for i in self.direct_count_indices):raise ValueError('Invalid direct-count index')
            zero=zero.clone();zero[:,self.direct_count_indices]=False
        if (zero&(~known|(self.opportunity<=0))).any():raise ValueError('Observed sensor zero requires positive audited opportunity')
        if self.exposed and self.split=='test':raise ValueError('Exposed records cannot reach prospective test')
        if self.kind=='natural':
            if self.measurement_audit.get('quality_claim')!='candidate_unvalidated':raise ValueError('Instrument status must remain unchanged')
            if self.measurement_audit.get('comparison_eligible') is not False:raise ValueError('Experimental adapter cannot validate instrument')

@dataclass(frozen=True)
class PrefixPacket:
    prefix_values:torch.Tensor
    prefix_observed:torch.Tensor
    prefix_opportunity:torch.Tensor
    prefix_opportunity_known:torch.Tensor
    prefix_unit_count:int
    def validate(self,dimensions):
        if type(self) is not PrefixPacket:raise TypeError('Exact PrefixPacket type required')
        if type(self.prefix_unit_count) is not int or self.prefix_unit_count<1:raise ValueError('Nonempty observed prefix required')
        shape=(self.prefix_unit_count,dimensions)
        for name in ('prefix_values','prefix_observed','prefix_opportunity','prefix_opportunity_known'):
            x=getattr(self,name)
            if type(x) is not torch.Tensor or tuple(x.shape)!=shape:raise ValueError('No padding/future rows/tensor subclasses')
            if x.storage_offset()!=0 or x.untyped_storage().nbytes()!=x.numel()*x.element_size():raise ValueError('Storage must contain only this prefix')
        if self.prefix_observed.dtype!=torch.bool or self.prefix_opportunity_known.dtype!=torch.bool:raise ValueError('Boolean masks required')
        if not torch.isfinite(self.prefix_values).all() or not torch.isfinite(self.prefix_opportunity).all():raise ValueError('Nonfinite forward covariates')
        if (self.prefix_values[~self.prefix_observed]!=0).any():raise ValueError('Missing values require neutral placeholders')
        if (self.prefix_opportunity[~self.prefix_opportunity_known]!=0).any():raise ValueError('Unknown opportunities require neutral placeholders')
        if (self.prefix_opportunity<0).any():raise ValueError('Negative opportunities')
        return self
    @classmethod
    def from_mapping(cls,value):
        if type(value) is not dict or set(value)!={x.name for x in fields(cls)}:raise ValueError('Five-field forward allowlist mismatch')
        return cls(**value)

def make_model_packet(record,cutoff,transform,mode='supplied_annotation_prefix'):
    if mode!='supplied_annotation_prefix':raise NotImplementedError('Separate retrospective experiment is deferred')
    if type(cutoff) is not int or cutoff<1 or cutoff>len(record.values):raise ValueError('Invalid prefix cut')
    raw=record.values[:cutoff].clone().contiguous();observed=~torch.isnan(raw)
    values=transform.apply(raw).clone().contiguous();o=record.opportunity[:cutoff].clone().contiguous();known=~torch.isnan(o)
    opportunity=torch.where(known,o,torch.zeros_like(o)).clone().contiguous()
    return PrefixPacket(values,observed.clone().contiguous(),opportunity,known.clone().contiguous(),cutoff).validate(len(transform.ids))

def permute_packet(packet,order):
    if sorted(order.tolist())!=list(range(packet.prefix_unit_count)):raise ValueError('Not a complete prefix permutation')
    return PrefixPacket(*(getattr(packet,k)[order].clone().contiguous() for k in ('prefix_values','prefix_observed','prefix_opportunity','prefix_opportunity_known')),packet.prefix_unit_count)

def validate_cohort(records):
    seen=set();questions={};components={};identities={}
    for r in records:
        key=(r.question,r.answer,r.arm)
        if key in seen:raise ValueError('Duplicate answer-arm; human must occur once')
        seen.add(key);identity=(r.component,r.source)
        if r.question in identities and identities[r.question]!=identity:raise ValueError('Question must map to one component and source')
        identities[r.question]=identity
        for table,key in ((questions,r.question),(components,r.component)):
            if key in table and table[key]!=r.split:raise ValueError('Question/component crosses frozen splits')
            table[key]=r.split
    return True

@dataclass(frozen=True)
class FitAuthorization:
    """Fail-closed workflow receipt; not a cryptographic authorization service."""
    approved:bool=False
    receipt:str=''
    actions:tuple=()
    def require(self,records,action):
        if all(r.kind=='synthetic' for r in records):return
        if not self.approved or not self.receipt or action not in self.actions:raise PermissionError('Coordinator approval required for empirical '+action)

def assert_fit_scope(records,split,source=None):
    for r in records:
        if r.split!=split or r.arm not in ('human','chatgpt'):raise ValueError('Fit/development split/generator firewall')
        if source is not None and r.source!=source:raise ValueError('Source-holdout fitting firewall')
    validate_cohort(records)
