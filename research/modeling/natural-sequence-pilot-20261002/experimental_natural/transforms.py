"""Train-only hierarchy-weighted transformations and output eligibility."""
from dataclasses import dataclass
from collections import defaultdict
import torch
from .schema import FitAuthorization,assert_fit_scope

def hierarchical_unit_weights(records):
    """Fixed question→answer→H/ChatGPT half-slot→unit mass before masking.
    Blank arms retain their slots without reallocation. Normalize observed
    channel mass only afterward. All declared questions/answers remain present.
    """
    tree=defaultdict(lambda:defaultdict(list))
    for i,r in enumerate(records):tree[r.question][r.answer].append(i)
    out=[torch.zeros(len(r.values),dtype=torch.float64) for r in records]
    for answers in tree.values():
        for indices in answers.values():
            for i in indices:
                if len(records[i].values):out[i].fill_(1/(len(tree)*len(answers)*2*len(records[i].values)))
    return out

@dataclass(frozen=True)
class FrozenTransform:
    ids:tuple
    families:tuple
    transforms:tuple
    structural_indices:tuple
    mean:torch.Tensor
    scale:torch.Tensor
    active_values:torch.Tensor
    score_eligible:torch.Tensor
    component_support:tuple
    source_scope:str|None
    training_sources:tuple
    fit_question_count:int
    min_components:int
    input_component_support:tuple=()
    def pretransform(self,raw):
        if raw.shape[-1]!=len(self.ids):raise ValueError('Channel width mismatch')
        x=raw.to(torch.float64).clone()
        for j,kind in enumerate(self.transforms):
            if kind=='log1p_then_train_zscore':
                obs=~torch.isnan(x[...,j])
                if (x[...,j][obs]<0).any():raise ValueError('Negative declared log1p input')
                x[...,j]=torch.log1p(x[...,j])
            elif kind!='raw_then_train_zscore':raise ValueError('Unregistered transform')
        return x
    def apply(self,raw):
        x=self.pretransform(raw)
        return torch.where((~torch.isnan(x))&self.active_values,(x-self.mean)/self.scale,torch.zeros_like(x)).float()
    def target(self,row):return self.apply(row),(~torch.isnan(row))&self.score_eligible
    def to_dict(self):return {k:(v.tolist() if isinstance(v,torch.Tensor) else v) for k,v in self.__dict__.items()}
    @classmethod
    def from_dict(cls,d):
        d=dict(d);d.setdefault('input_component_support',d.get('component_support',()))
        for k in ('ids','families','transforms','structural_indices','component_support','training_sources','input_component_support'):d[k]=tuple(d[k])
        for k in ('mean','scale'):d[k]=torch.tensor(d[k],dtype=torch.float64)
        for k in ('active_values','score_eligible'):d[k]=torch.tensor(d[k],dtype=torch.bool)
        obj=cls(**d)
        if (obj.scale<=0).any() or not torch.isfinite(obj.scale).all():raise ValueError('Malformed frozen scale')
        return obj

def fit_transform(records,catalog,*,source=None,min_components=50,authorization=FitAuthorization()):
    records=tuple(records)
    if not records:raise ValueError('Empty training collection')
    assert_fit_scope(records,'train',source);authorization.require(records,'fit_transform')
    if min_components!=50 and any(r.kind!='synthetic' for r in records):raise ValueError('Natural gate fixed at50 components')
    D=len(catalog.ids)
    if any(r.values.shape[1]!=D for r in records):raise ValueError('Channel width mismatch')
    blank=FrozenTransform(catalog.ids,catalog.families,catalog.transforms,catalog.structural_indices,
        torch.zeros(D,dtype=torch.float64),torch.ones(D,dtype=torch.float64),torch.ones(D,dtype=torch.bool),
        torch.ones(D,dtype=torch.bool),tuple([0]*D),source,tuple(sorted({r.source for r in records})),len({r.question for r in records}),min_components)
    arrays=[blank.pretransform(r.values) for r in records];weights=hierarchical_unit_weights(records)
    mass=torch.zeros(D,dtype=torch.float64);sums=mass.clone();support=[set() for _ in range(D)];target_support=[set() for _ in range(D)]
    for r,x,w in zip(records,arrays,weights):
        obs=~torch.isnan(x);mass+=(obs*w[:,None]).sum(0);sums+=(torch.nan_to_num(x)*w[:,None]).sum(0)
        for j in torch.where(obs.any(0))[0].tolist():support[j].add(r.component)
        for j in torch.where(obs[1:].any(0))[0].tolist():target_support[j].add(r.component)
    mean=torch.where(mass>0,sums/mass.clamp_min(1e-300),torch.zeros_like(sums));variance=torch.zeros(D,dtype=torch.float64)
    minimum=torch.full((D,),float('inf'),dtype=torch.float64);maximum=torch.full((D,),float('-inf'),dtype=torch.float64)
    for x,w in zip(arrays,weights):
        obs=~torch.isnan(x);variance+=torch.where(obs,(x-mean)**2,torch.zeros_like(x)).mul(w[:,None]).sum(0)
        if len(x):
            minimum=torch.minimum(minimum,torch.where(obs,x,float('inf')).min(0).values)
            maximum=torch.maximum(maximum,torch.where(obs,x,float('-inf')).max(0).values)
    variance/=mass.clamp_min(1e-300);active=(mass>0)&(maximum>minimum)&(variance>0)
    # 1 is solely an internal divisor on a frozen-zero path, not a fitted scale.
    scale=torch.where(active,torch.sqrt(variance),torch.ones_like(variance));input_counts=tuple(len(s) for s in support);counts=tuple(len(s) for s in target_support)
    eligible=active&(torch.tensor(counts)>=min_components)
    # Reuse the trainer's exact jointly supported answer/arm population. Removing
    # unsupported targets may remove a paired variant; monotonically iterate to
    # the fixed population so every retained output has actual supervision.
    from .objectives import BalancedPlan
    for _ in range(D+1):
        provisional=FrozenTransform(catalog.ids,catalog.families,catalog.transforms,catalog.structural_indices,mean,scale,active,eligible,counts,source,blank.training_sources,blank.fit_question_count,min_components,input_counts)
        plan=BalancedPlan(records,provisional);joint_support=[set() for _ in range(D)]
        for i in plan.record_indices:
            observed=~torch.isnan(records[i].values[list(plan.positions[i])])
            for j in torch.where(observed.any(0))[0].tolist():joint_support[j].add(records[i].component)
        counts=tuple(len(s) for s in joint_support)
        updated=eligible&(torch.tensor(counts)>=min_components)
        if torch.equal(updated,eligible):break
        eligible=updated
    else:raise AssertionError('Monotone target-support selection did not converge')
    return FrozenTransform(catalog.ids,catalog.families,catalog.transforms,catalog.structural_indices,mean,scale,active,eligible,counts,source,blank.training_sources,blank.fit_question_count,min_components,input_counts)

def common_support_channels(records,catalog,threshold=.9):
    assert_fit_scope(records,'train')
    if threshold!=.9:raise ValueError('Common-support threshold fixed at0.90')
    cells=defaultdict(list)
    for r in records:cells[(r.source,r.arm)].append(r)
    selected=torch.ones(len(catalog.ids),dtype=torch.bool);report={}
    for source in sorted({r.source for r in records}):
        for arm in ('human','chatgpt'):
            rows=[r.values for r in cells[(source,arm)] if len(r.values)]
            if not rows:selected[:]=False;report[source+'/'+arm]=None;continue
            availability=(~torch.isnan(torch.cat(rows))).double().mean(0);selected&=availability>=threshold;report[source+'/'+arm]=availability.tolist()
    return selected,report
