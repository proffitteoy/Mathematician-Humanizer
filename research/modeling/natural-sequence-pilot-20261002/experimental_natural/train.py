"""Explicitly gated training; imports perform no empirical I/O."""
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib,json,math,os,random,re,resource,time
import torch
from .schema import FitAuthorization,assert_fit_scope,make_model_packet,permute_packet,validate_cohort
from .objectives import BalancedPlan,DocumentScore,family_loss,aggregate_document_scores
FIXED_SEEDS=(1701,1702,1703)

@dataclass(frozen=True)
class TrainingConfig:
    learning_rate:float=.001
    weight_decay:float=.001
    batch_questions:int=32
    gradient_norm_cap:float=1.
    max_epochs:int=100
    patience:int=10
    max_cpu_threads:int=2
    max_fit_seconds:float=24*3600
    max_rss_bytes:int=2*1024**3
    max_output_bytes:int=2*1024**3
    profile:bool=False

class FitLedger:
    def __init__(self,path,max_fits=100,max_cpu_seconds=24*3600):
        self.path=Path(path);self.max_fits=max_fits;self.max_cpu_seconds=max_cpu_seconds;self.path.parent.mkdir(parents=True,exist_ok=True)
    def events(self):return [json.loads(line) for line in self.path.read_text().splitlines() if line] if self.path.exists() else []
    def append(self,event):
        with self.path.open('a') as stream:stream.write(json.dumps(event,sort_keys=True,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
    def consumed_cpu(self):
        costs={}
        for e in self.events():costs[e['run_id']]=max(costs.get(e['run_id'],0),e.get('cpu_seconds',0),e.get('cpu_seconds_current_fit',0))
        return sum(costs.values())
    def begin(self,run_id,metadata):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',run_id):raise ValueError('Unsafe run identifier')
        events=self.events();attempts=[e for e in events if e['event']=='attempt_started']
        if any(e['run_id']==run_id for e in attempts):raise ValueError('Run already attempted; retries need explicit new budgeted IDs')
        if len(attempts)>=self.max_fits:raise RuntimeError('Optimizer-fit budget exhausted')
        terminal={e['run_id'] for e in events if e['event'] in ('completed','failed')}
        if {e['run_id'] for e in attempts}-terminal:raise RuntimeError('Interrupted attempts require reconciliation')
        if self.consumed_cpu()>=self.max_cpu_seconds:raise RuntimeError('Aggregate CPU budget exhausted')
        self.append({'event':'attempt_started','run_id':run_id,'attempt_number':len(attempts)+1,'started_unix':time.time(),**metadata})
    def assert_complete(self,expected):
        events=self.events();started={e['run_id'] for e in events if e['event']=='attempt_started'};completed={e['run_id'] for e in events if e['event']=='completed'}
        if set(expected)!=started or set(expected)!=completed or any(e['event']=='failed' for e in events):raise ValueError('Incomplete/extra/failed runs cannot be omitted')
        return True

def deterministic_seed(seed):random.seed(seed);torch.manual_seed(seed);torch.use_deterministic_algorithms(True)

def _shuffle(packet,seed,preserve_last=False):
    g=torch.Generator().manual_seed(seed);n=packet.prefix_unit_count
    order=torch.cat([torch.randperm(n-1,generator=g),torch.tensor([n-1])]) if preserve_last else torch.randperm(n,generator=g)
    return permute_packet(packet,order)

def score_model(model,plan,*,permutations=0,preserve_last=False,shuffle_seed=47011):
    """Private document records; permutation scoring averages losses, not predictions."""
    was_training=model.training;model.eval();rows=[]
    try:
        with torch.no_grad():
            for i in plan.record_indices:
                r=plan.records[i];losses=[];families={};family_counts={};observations=0
                for t in plan.positions[i]:
                    packet=make_model_packet(r,t,plan.transform);target,observed=plan.transform.target(r.values[t])
                    if plan.score_indices is not None:
                        keep=torch.zeros_like(observed);keep[list(plan.score_indices)]=True;observed&=keep
                    parts=[];family_parts={}
                    for rep in range(permutations or 1):
                        p=_shuffle(packet,shuffle_seed+104729*i+15485863*t+rep,preserve_last) if permutations else packet
                        loss,by_family=family_loss(model(p),target,observed,plan.transform.families)
                        if loss is None:raise AssertionError('Fixed target support changed')
                        parts.append(float(loss))
                        for f,v in by_family.items():family_parts.setdefault(f,[]).append(float(v))
                    losses.append(sum(parts)/len(parts));observations+=int(observed.sum())
                    for f,v in family_parts.items():families[f]=families.get(f,0)+sum(v)/len(v);family_counts[f]=family_counts.get(f,0)+1
                rows.append(DocumentScore(r.question,r.answer,r.component,r.source,r.arm,sum(losses)/len(losses),len(losses),
                    {f:v/family_counts[f] for f,v in families.items()},family_counts,len(r.values),observations))
    finally:model.train(was_training)
    return rows

def _guard(config,start,cpu_start,outdir,ledger):
    if time.monotonic()-start>config.max_fit_seconds:raise RuntimeError('Wall ceiling reached')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>config.max_rss_bytes:raise RuntimeError('RSS ceiling reached')
    if sum(p.stat().st_size for p in Path(outdir).rglob('*') if p.is_file())>config.max_output_bytes:raise RuntimeError('Derived-disk ceiling reached')
    events=ledger.events();beginnings=[e.get('started_unix') for e in events if e['event']=='attempt_started' and e.get('started_unix') is not None]
    if beginnings and time.time()-min(beginnings)>24*3600:raise RuntimeError('Aggregate study wall ceiling reached')
    spent=ledger.consumed_cpu();current=max((e.get('cpu_seconds_current_fit',0) for e in events if e.get('run_id')==events[-1].get('run_id')),default=0)
    if spent+max(0,time.process_time()-cpu_start-current)>ledger.max_cpu_seconds:raise RuntimeError('Aggregate CPU ceiling reached')

def train_one(model,train_records,dev_records,transform,*,seed,run_id,outdir,ledger,source=None,shuffle_training=False,config=TrainingConfig(),authorization=FitAuthorization()):
    train_records=tuple(train_records);dev_records=tuple(dev_records);authorization.require(train_records+dev_records,'train_model')
    assert_fit_scope(train_records,'train',source);assert_fit_scope(dev_records,'dev',source);validate_cohort(train_records+dev_records)
    if transform.source_scope!=source:raise ValueError('Wrong source-specific transform')
    if set(transform.training_sources)!={r.source for r in train_records}:raise ValueError('Transform from other training sources')
    if seed not in FIXED_SEEDS:raise ValueError('Seed replacement/search forbidden')
    natural=any(r.kind=='natural' for r in train_records+dev_records)
    if natural:
        from .plan import transform_signature
        if getattr(model,'initialization_seed',None)!=seed:raise ValueError('Fixed-seed model factory required')
        if getattr(model,'transform_signature',None)!=transform_signature(transform):raise ValueError('Exact TRAIN transform/target gate required')
        fixed=TrainingConfig()
        for field in ('learning_rate','weight_decay','batch_questions','gradient_norm_cap','patience'):
            if getattr(config,field)!=getattr(fixed,field):raise ValueError('Unregistered hyperparameter change')
        if config.max_epochs!=100 and not config.profile:raise ValueError('Unregistered epoch cap')
        if config.profile:authorization.require(train_records+dev_records,'training_profile')
    if config.max_cpu_threads>2 or config.max_rss_bytes>2*1024**3 or config.max_output_bytes>2*1024**3:raise ValueError('Resource ceiling exceeded')
    train_plan=BalancedPlan(train_records,transform);dev_plan=BalancedPlan(dev_records,transform)
    if not train_plan.questions or not dev_plan.questions:raise ValueError('No joint train/dev support')
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True);path=outdir/(run_id+'.pt')
    ledger.begin(run_id,{'seed':seed,'source_scope':source,'shuffle_training':shuffle_training,'config':asdict(config),
        'kind':'natural' if natural else 'synthetic','train_questions':len(train_plan.questions),'dev_questions':len(dev_plan.questions)})
    start=time.monotonic();cpu_start=time.process_time();best=float('inf');best_epoch=None;stale=0
    try:
        torch.set_num_threads(config.max_cpu_threads)
        if torch.get_num_interop_threads()>config.max_cpu_threads:torch.set_num_interop_threads(config.max_cpu_threads)
        if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:config.max_cpu_threads])
        deterministic_seed(seed);optimizer=torch.optim.Adam(model.parameters(),lr=config.learning_rate,weight_decay=config.weight_decay)
        for epoch in range(1,config.max_epochs+1):
            model.train();draws=list(train_plan.draws(seed*100000+epoch));batch_losses=[]
            for offset in range(0,len(draws),config.batch_questions):
                _guard(config,start,cpu_start,outdir,ledger);optimizer.zero_grad(set_to_none=True);losses=[]
                for draw_index,(i,t) in enumerate(draws[offset:offset+config.batch_questions],start=offset):
                    r=train_records[i];packet=make_model_packet(r,t,transform)
                    if shuffle_training:packet=_shuffle(packet,seed*10**9+epoch*10**6+draw_index)
                    target,observed=transform.target(r.values[t]);loss,_=family_loss(model(packet),target,observed,transform.families)
                    if loss is None:raise AssertionError('Training support changed')
                    losses.append(loss)
                batch=torch.stack(losses).mean()
                if not torch.isfinite(batch):raise FloatingPointError('Nonfinite objective')
                batch.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),config.gradient_norm_cap,error_if_nonfinite=True);optimizer.step();batch_losses.append(float(batch.detach()))
            dev=aggregate_document_scores(score_model(model,dev_plan,permutations=10 if shuffle_training else 0))['equal_arm_mean']
            if dev is None or not math.isfinite(dev):raise FloatingPointError('Invalid DEV score')
            improved=dev<best
            if improved:
                best=dev;best_epoch=epoch;stale=0;temporary=path.with_suffix('.pt.tmp')
                torch.save({'state_dict':model.state_dict(),'seed':seed,'epoch':epoch,'dev_score':dev,'run_id':run_id,'transform':transform.to_dict()},temporary);os.replace(temporary,path)
            else:stale+=1
            ledger.append({'event':'epoch','run_id':run_id,'epoch':epoch,'draws':len(draws),'batch_mean_diagnostic':sum(batch_losses)/len(batch_losses),
                'dev_score':dev,'checkpoint_selected':improved,'stale_epochs':stale,'wall_seconds':time.monotonic()-start,'cpu_seconds_current_fit':time.process_time()-cpu_start})
            _guard(config,start,cpu_start,outdir,ledger)
            if stale>=config.patience:break
        saved=torch.load(path,map_location='cpu',weights_only=True);model.load_state_dict(saved['state_dict'])
        result={'event':'completed','run_id':run_id,'selected_epoch':best_epoch,'best_dev_score':best,'checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'cpu_seconds':time.process_time()-cpu_start,'wall_seconds':time.monotonic()-start};ledger.append(result);return result
    except BaseException as error:
        ledger.append({'event':'failed','run_id':run_id,'error_type':type(error).__name__,'error':str(error),'cpu_seconds':time.process_time()-cpu_start,'wall_seconds':time.monotonic()-start});raise
