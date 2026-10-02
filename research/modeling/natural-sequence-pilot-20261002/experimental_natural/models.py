"""From-scratch label-blind prefix models; no padding/batchnorm/full lengths."""
from dataclasses import dataclass
import torch
from torch import nn
from .schema import PrefixPacket

@dataclass(frozen=True)
class InputView:
    dimensions:int
    indices:tuple
    mode:str='values'
    nuisance_indices:tuple=()
    active_value_indices:tuple|None=None
    def __post_init__(self):
        if self.mode not in ('values','mask_opportunity','pure_mask','length'):raise ValueError('Unknown control')
        for ix in (self.indices,self.nuisance_indices):
            if len(set(ix))!=len(ix) or any(i<0 or i>=self.dimensions for i in ix):raise ValueError('Invalid channel selection')
        if not self.indices:raise ValueError('No selected inputs')
    @property
    def has_values(self):return self.mode in ('values','length')
    @property
    def has_opportunity(self):return self.mode in ('values','mask_opportunity')
    @property
    def active_local(self):
        allowed=set(self.indices if self.active_value_indices is None else self.active_value_indices)
        return tuple(i for i,j in enumerate(self.indices) if j in allowed) if self.has_values else ()
    @property
    def active_pairs(self):
        active=set(self.active_local)
        return tuple((j,k) for j in range(self.n) for k in range(j,self.n) if j in active and k in active)
    @property
    def pair_mean_count(self):return len(self.active_local)*(self.n+1)
    @property
    def n(self):return len(self.indices)
    @property
    def pairs(self):return self.n*(self.n+1)//2
    @property
    def local_size(self):return self.n*(1 if self.mode=='length' else 2+int(self.has_opportunity))+len(self.active_local)+3*len(self.nuisance_indices)
    @property
    def summary_size(self):
        coordinate=2 if self.mode=='length' else 4+int(self.has_opportunity)
        return coordinate*self.n+len(self.active_local)+4*self.pairs+self.pair_mean_count+1+5*len(self.nuisance_indices)
    def _selected(self,p):
        p.validate(self.dimensions)
        return (p.prefix_values[:,self.indices],p.prefix_observed[:,self.indices],
                p.prefix_opportunity_known[:,self.indices],torch.log1p(p.prefix_opportunity[:,self.indices]))
    def local(self,p):
        v,m,k,o=self._selected(p);parts=([v[:,self.active_local]] if self.active_local else [])+[m.float()]
        if self.mode!='length':
            if self.has_opportunity:parts.append(o)
            parts.append(k.float())
        if self.nuisance_indices:
            ix=self.nuisance_indices;parts.extend([p.prefix_observed[:,ix].float(),torch.log1p(p.prefix_opportunity[:,ix]),p.prefix_opportunity_known[:,ix].float()])
        return torch.cat(parts,1)
    def summarize(self,p,include_covariance=False):
        v,m,k,o=self._selected(p);v=v.double();m=m.double();k=k.double();o=o.double();t=p.prefix_unit_count
        count=m.sum(0);kc=k.sum(0);parts=[]
        if self.active_local:parts.append(((v*m).sum(0)/count.clamp_min(1))[list(self.active_local)])
        parts.extend([count/t,torch.log1p(count)])
        if self.mode!='length':
            if self.has_opportunity:parts.append((o*k).sum(0)/kc.clamp_min(1))
            parts.extend([kc/t,torch.log1p(kc)])
        ij=torch.triu_indices(self.n,self.n);joint=m.T@m;weighted=v*m;s=weighted.T@m;means=s/joint.clamp_min(1);n=joint[ij[0],ij[1]]
        parts.extend([n/t,torch.log1p(n),(n>=1).double(),(n>=2).double()])
        if self.has_values:
            active=torch.tensor([i in self.active_local for i in range(self.n)])
            parts.extend([means[ij[0],ij[1]][active[ij[0]]],means[ij[1],ij[0]][active[ij[1]]]])
        if include_covariance and self.has_values:
            selected=active[ij[0]]&active[ij[1]];ii=ij[0][selected];jj=ij[1][selected];covariance=[]
            # Direct joint-centered products, in bounded pair chunks, avoid
            # catastrophic product-minus-mean cancellation and PSD assumptions.
            for start in range(0,len(ii),128):
                a=ii[start:start+128];b=jj[start:start+128];n=joint[a,b];mask=m[:,a]*m[:,b]
                centered=(v[:,a]-means[a,b])*(v[:,b]-means[b,a]);cov=(centered*mask).sum(0)/(n-1).clamp_min(1)
                covariance.append(torch.where(n>=2,cov,torch.zeros_like(cov)))
            parts.append(torch.cat(covariance) if covariance else torch.empty(0,dtype=torch.float64))
        parts.append(torch.tensor([float(t)],dtype=torch.float64).log1p())
        if self.nuisance_indices:
            ix=self.nuisance_indices;nm=p.prefix_observed[:,ix].double();nk=p.prefix_opportunity_known[:,ix].double();no=torch.log1p(p.prefix_opportunity[:,ix].double());nc=nm.sum(0);kn=nk.sum(0)
            parts.extend([nc/t,torch.log1p(nc),(no*nk).sum(0)/kn.clamp_min(1),kn/t,torch.log1p(kn)])
        return torch.cat(parts).float()

def _head(nin,width,nout):return nn.Sequential(nn.Linear(nin,width),nn.Tanh(),nn.Linear(width,width),nn.Tanh(),nn.Linear(width,nout))

class PrefixModel(nn.Module):
    def __init__(self,name,view,targets,width=32,target_indices=None):
        super().__init__()
        if name not in ('F1','Fcov','F2','F3','F4'):raise ValueError('Unregistered model')
        self.name=name;self.view=view;self.targets=targets;self.width=width
        self.target_indices=tuple(range(targets)) if target_indices is None else tuple(target_indices)
        if not self.target_indices or len(set(self.target_indices))!=len(self.target_indices):raise ValueError('No eligible or duplicate outputs')
        self.register_buffer('output_indices',torch.tensor(self.target_indices,dtype=torch.long))
        self.include_covariance=name!='F1' and view.has_values;size=view.summary_size+(len(view.active_pairs) if self.include_covariance else 0)
        if name in ('F2','F3','F4'):
            self.phi=nn.Sequential(nn.Linear(view.local_size,width),nn.Tanh(),nn.Linear(width,width),nn.Tanh());size+=2*width
        if name=='F3':size+=view.local_size
        if name=='F4':self.gru=nn.GRU(view.local_size,width,batch_first=True);size+=width
        self.head=_head(size,width,len(self.target_indices))
    def forward(self,packet):
        if type(packet) is not PrefixPacket:raise TypeError('Only prefix-only PrefixPacket is accepted')
        parts=[self.view.summarize(packet,self.include_covariance)]
        if self.name in ('F2','F3','F4'):
            local=self.view.local(packet);embedding=self.phi(local)
            parts.extend([embedding.double().sum(0).float(),embedding.double().mean(0).float()])
            if self.name=='F3':parts.append(local[-1])
            if self.name=='F4':
                _,h=self.gru(local.unsqueeze(0));parts.append(h[0,0])
        learned=self.head(torch.cat(parts));result=learned.new_zeros(self.targets).scatter(0,self.output_indices,learned)
        if not torch.isfinite(result).all():raise FloatingPointError('Nonfinite model output')
        return result
    def forward_batch(self,packets):return torch.stack([self(p) for p in packets])

class TrainingMean(nn.Module):
    def __init__(self,dimensions):super().__init__();self.register_buffer('mean',torch.zeros(dimensions))
    def forward(self,packet):packet.validate(len(self.mean));return self.mean.clone()
    def forward_batch(self,packets):return torch.stack([self(p) for p in packets])

def parameter_count(model):return sum(p.numel() for p in model.parameters() if p.requires_grad)

def capacity_match(name,view,targets,target_counts,max_width=512,target_indices=None):
    counts=tuple(target_counts);nout=targets if target_indices is None else len(target_indices);candidates=[]
    for width in range(1,max_width+1):
        size=view.summary_size+(len(view.active_pairs) if name!='F1' and view.has_values else 0);extra=0
        if name in ('F2','F3','F4'):extra+=(view.local_size+1)*width+(width+1)*width;size+=2*width
        if name=='F3':size+=view.local_size
        if name=='F4':extra+=3*width*view.local_size+3*width*width+6*width;size+=width
        count=extra+(size+1)*width+(width+1)*width+(width+1)*nout;candidates.append((max(abs(count-c)/c for c in counts),count,width))
    feasible=[c for c in candidates if c[0]<=.10]
    if feasible:selected=min(feasible);status='within_10_percent_all_targets'
    else:
        upper=[c for c in candidates if c[1]>=max(counts)]
        if not upper:raise ValueError('No active upper bracket within declared width bound')
        selected=min(upper,key=lambda x:x[1]);status='active_upper_bracket_mismatch'
    model=PrefixModel(name,view,targets,selected[2],target_indices)
    if parameter_count(model)!=selected[1]:raise AssertionError('Parameter accounting mismatch')
    return model,{'width':selected[2],'trainable_parameters':selected[1],'target_counts':counts,'max_relative_mismatch':selected[0],'status':status}

class IndependentFamilies(nn.Module):
    """Separate family+length value states; common nuisance inputs, no cross-value moments.
    Nuisance summary representation differs from the shared model; this must be
    disclosed/reviewed before interpreting cross-family comparisons.
    """
    def __init__(self,catalog,width,target_indices=None,active_value_indices=None):
        super().__init__();self.dimensions=len(catalog.ids);self.width=width
        eligible=set(range(self.dimensions) if target_indices is None else target_indices)
        self.names=tuple(f for f in dict.fromkeys(catalog.families) if any(i in eligible for i,x in enumerate(catalog.families) if x==f))
        self.target_indices=[];self.models=nn.ModuleList();lengths=set(catalog.structural_indices)
        for family in self.names:
            target=tuple(i for i,f in enumerate(catalog.families) if f==family and i in eligible);own={i for i,f in enumerate(catalog.families) if f==family}
            ix=tuple(sorted(own|lengths));nuisance=tuple(i for i in range(self.dimensions) if i not in ix)
            self.target_indices.append(target);self.models.append(PrefixModel('F4',InputView(self.dimensions,ix,'values',nuisance,active_value_indices),len(target),width))
        if not self.models:raise ValueError('No eligible independent-family target')
    def forward(self,packet):
        out=torch.zeros(self.dimensions)
        for model,indices in zip(self.models,self.target_indices):out=out.scatter(0,torch.tensor(indices),model(packet))
        return out
    def forward_batch(self,packets):return torch.stack([self(p) for p in packets])

def independent_capacity_match(catalog,target,max_width=512,target_indices=None,active_value_indices=None):
    counts=[];dims=len(catalog.ids);lengths=set(catalog.structural_indices);eligible=set(range(dims) if target_indices is None else target_indices)
    for width in range(1,max_width+1):
        total=0
        for family in dict.fromkeys(catalog.families):
            targets=tuple(i for i,f in enumerate(catalog.families) if f==family and i in eligible)
            if not targets:continue
            own={i for i,f in enumerate(catalog.families) if f==family};ix=tuple(sorted(own|lengths));nuisance=tuple(i for i in range(dims) if i not in ix)
            v=InputView(dims,ix,'values',nuisance,active_value_indices);size=v.summary_size+len(v.active_pairs)+3*width
            total+=(v.local_size+1)*width+(width+1)*width+3*width*v.local_size+3*width*width+6*width
            total+=(size+1)*width+(width+1)*width+(width+1)*len(targets)
        counts.append((abs(total-target)/target,total,width))
    feasible=[x for x in counts if x[0]<=.1];selected=min(feasible) if feasible else min((x for x in counts if x[1]>=target),key=lambda x:x[1])
    model=IndependentFamilies(catalog,selected[2],target_indices,active_value_indices)
    if parameter_count(model)!=selected[1]:raise AssertionError('Independent count mismatch')
    return model,{'width':selected[2],'trainable_parameters':selected[1],'target_counts':[target],'max_relative_mismatch':selected[0],'status':'within_10_percent' if feasible else 'active_upper_bracket_mismatch'}
