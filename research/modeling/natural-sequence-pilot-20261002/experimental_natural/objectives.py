"""Fixed-family objectives, paired populations and copy-component inference."""
from collections import defaultdict
from dataclasses import dataclass
import math,random
import torch
from .schema import validate_cohort

def family_loss(prediction,target,observed,families):
    if prediction.shape!=target.shape or observed.shape!=target.shape:raise ValueError('Output/target/mask mismatch')
    if not torch.isfinite(prediction).all():raise FloatingPointError('Numeric failure invalidates comparison, never drop rows')
    losses=[];by_family={}
    for name in dict.fromkeys(families):
        ix=torch.tensor([i for i,f in enumerate(families) if f==name],dtype=torch.long);mask=observed[ix]
        if mask.any():
            loss=((prediction[ix][mask]-target[ix][mask])**2).mean();by_family[name]=loss;losses.append(loss)
    return (torch.stack(losses).mean() if losses else None),by_family

def supported_positions(record,transform,min_prefix=1,score_indices=None):
    eligible=transform.score_eligible.clone()
    if score_indices is not None:
        keep=torch.zeros_like(eligible);keep[list(score_indices)]=True;eligible&=keep
    return tuple(t for t in range(min_prefix,len(record.values)) if ((~torch.isnan(record.values[t]))&eligible).any())

class BalancedPlan:
    """Model-independent jointly supported answer variants, equal questions/arms."""
    def __init__(self,records,transform,arms=('human','chatgpt'),min_prefix=1,score_indices=None):
        records=tuple(records);validate_cohort(records);self.arms=tuple(arms);self.transform=transform
        self.min_prefix=min_prefix;self.score_indices=score_indices;self.records=records;self.by_question={};self.positions={}
        groups=defaultdict(lambda:defaultdict(dict))
        for i,r in enumerate(records):
            if r.arm not in self.arms:continue
            positions=supported_positions(r,transform,min_prefix,score_indices);self.positions[i]=positions
            if positions:groups[r.question][r.answer][r.arm]=i
        for q,answers in groups.items():
            joint={a:d for a,d in answers.items() if set(d)==set(self.arms)}
            if joint:self.by_question[q]=joint
        self.questions=tuple(sorted(self.by_question))
        self.record_indices=tuple(sorted({i for answers in self.by_question.values() for arms in answers.values() for i in arms.values()}))
    def draws(self,seed,count=None):
        if not self.questions:raise ValueError('No jointly supported questions')
        rng=random.Random(seed)
        for _ in range(len(self.questions) if count is None else count):
            q=rng.choice(self.questions);answers=self.by_question[q];a=rng.choice(tuple(sorted(answers)));arm=rng.choice(self.arms)
            i=answers[a][arm];yield i,rng.choice(self.positions[i])
    def exact_weights(self):
        return {(i,t):1/(len(self.questions)*len(answers)*len(arms)*len(self.positions[i]))
            for answers in self.by_question.values() for arms in answers.values() for i in arms.values() for t in self.positions[i]}

@dataclass(frozen=True)
class DocumentScore:
    question:str
    answer:str
    component:str
    source:str
    arm:str
    loss:float
    targets:int
    family_losses:dict
    family_target_counts:dict
    units:int
    target_observations:int

def aggregate_document_scores(scores,arms=('human','chatgpt')):
    tree=defaultdict(lambda:defaultdict(dict));seen=set();qcomp={}
    for row in scores:
        if row.arm not in arms:continue
        if not math.isfinite(row.loss):raise FloatingPointError('Failed score cannot be omitted')
        key=(row.question,row.answer,row.arm)
        if key in seen:raise ValueError('Duplicate document score')
        seen.add(key)
        if row.question in qcomp and qcomp[row.question]!=row.component:raise ValueError('Question cannot span components')
        qcomp[row.question]=row.component;tree[row.question][row.answer][row.arm]=row
    values={};used=[]
    for q,answers in tree.items():
        joint=[v for v in answers.values() if all(a in v for a in arms)]
        if not joint:continue
        values[q]={a:sum(v[a].loss for v in joint)/len(joint) for a in arms};used.extend(v[a] for v in joint for a in arms)
    if not values:return {'equal_arm_mean':None,'by_arm':{},'support':{'questions':0,'components':0,'answers':0,'documents':0,'units':0,'targets':0,'target_observations':0}}
    by_arm={a:sum(v[a] for v in values.values())/len(values) for a in arms}
    return {'equal_arm_mean':sum(by_arm.values())/len(arms),'by_arm':by_arm,
        'paired_arm_differences':{a+'_minus_'+arms[0]:by_arm[a]-by_arm[arms[0]] for a in arms[1:]},
        'support':{'questions':len(values),'components':len({x.component for x in used}),'answers':len({(x.question,x.answer) for x in used}),
            'documents':len(used),'units':sum(x.units for x in used),'targets':sum(x.targets for x in used),'target_observations':sum(x.target_observations for x in used)}}

def paired_seed_comparison(baseline_runs,new_runs,arms=('human','chatgpt'),replicates=2000,level=.9833333333333333,seed=91823):
    """Seed-average before component bootstrap; exact ratio of aggregate losses."""
    if set(baseline_runs)!=set(new_runs) or set(baseline_runs)!={1701,1702,1703}:raise ValueError('All registered seeds required; failures cannot disappear')
    keys=None;b_maps=[];n_maps=[]
    for runs,maps in ((baseline_runs,b_maps),(new_runs,n_maps)):
        for run in sorted(runs):
            rows=runs[run];m={(r.question,r.answer,r.arm):r for r in rows}
            if len(m)!=len(rows):raise ValueError('Duplicate targets')
            if keys is None:keys=set(m)
            if set(m)!=keys:raise ValueError('Model-specific omission changes population')
            if any(not math.isfinite(r.loss) for r in rows):raise FloatingPointError('Failed run invalidates comparison')
            maps.append(m)
    groups=defaultdict(lambda:defaultdict(dict));qcomp={};qsource={}
    for key in sorted(keys):
        q,a,arm=key;row=b_maps[0][key]
        if any((m[key].component,m[key].source)!=(row.component,row.source) for m in b_maps+n_maps):raise ValueError('Identity changed across runs')
        if q in qcomp and (qcomp[q],qsource[q])!=(row.component,row.source):raise ValueError('Question changes component/source')
        qcomp[q]=row.component;qsource[q]=row.source
        groups[q][a][arm]=(sum(m[key].loss for m in b_maps)/3,sum(m[key].loss for m in n_maps)/3)
    qvalues={}
    for q,answers in groups.items():
        joint=[v for v in answers.values() if all(a in v for a in arms)]
        if joint:qvalues[q]={a:tuple(sum(v[a][k] for v in joint)/len(joint) for k in (0,1)) for a in arms}
    if not qvalues:raise ValueError('No paired population')
    clusters=defaultdict(list)
    for q in qvalues:clusters[qcomp[q]].append(q)
    def summarize(qs):
        armvalues={a:tuple(sum(qvalues[q][a][k] for q in qs)/len(qs) for k in (0,1)) for a in arms}
        b=sum(v[0] for v in armvalues.values())/len(arms);n=sum(v[1] for v in armvalues.values())/len(arms)
        return {'baseline':b,'new':n,'absolute_gain':b-n,'relative_gain':None if b==0 else (b-n)/b,
            'by_arm':{a:{'baseline':v[0],'new':v[1],'absolute_gain':v[0]-v[1]} for a,v in armvalues.items()}}
    point=summarize(list(qvalues));rng=random.Random(seed);component_ids=tuple(sorted(clusters));boots=[]
    for _ in range(replicates):boots.append(summarize([q for c in rng.choices(component_ids,k=len(component_ids)) for q in clusters[c]]))
    def interval(name):
        vals=sorted(x[name] for x in boots if x[name] is not None)
        if len(vals)!=replicates:return None
        def quantile(p):
            j=p*(len(vals)-1);lo=int(j);hi=min(lo+1,len(vals)-1);return vals[lo]+(j-lo)*(vals[hi]-vals[lo])
        alpha=(1-level)/2;return [quantile(alpha),quantile(1-alpha)]
    ci=interval('relative_gain')
    return {**point,'absolute_interval':interval('absolute_gain'),'relative_interval':ci,'positive_increment_evidence':bool(ci and ci[0]>0),
        'useful_increment_evidence':bool(ci and ci[0]>.01),'interval_level':level,'replicates':replicates,'questions':len(qvalues),'components':len(clusters),
        'seeds':[1701,1702,1703],'seed_count_is_sample_size':False}
