#!/usr/bin/env python3
"""Gated natural cost-only profile: TRAIN transforms, no optimizer or test access.
Reconstructed after executor reset; all gates must pass again before execution.
"""
import argparse,collections,hashlib,json,os,resource,socket,sys,time
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent;sys.path.insert(0,str(ROOT))
from experimental_natural.schema import Catalog,FitAuthorization,validate_cohort,make_model_packet
from experimental_natural.cache_adapter import CacheDescriptor,load_train_dev_cache
from experimental_natural.transforms import fit_transform,common_support_channels
from experimental_natural.plan import build_ladder,build_control,registered_run_grid
from experimental_natural.models import parameter_count,independent_capacity_match
from experimental_natural.objectives import BalancedPlan
EXPECTED_COHORT='caab83530f309622cbafe95b92e648fc59936435b170f7ef3f38abf23cf3a1ca'
SELECTION_SEED='m4-zh-natural-throughput-fixed32train16dev-v1.1-20261002'
def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def hashed(s):return digest((SELECTION_SEED+'\0'+s).encode())
def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
def deny(*args,**kwargs):raise RuntimeError('Network disabled for resource profile')
def guard(start):
    if time.monotonic()-start>1100:raise RuntimeError('Approaching20-minute profile ceiling')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>2*1024**3:raise RuntimeError('Profile exceeded2GiB RSS')

def prerequisites(extraction,approval_path):
    approval=json.loads(Path(approval_path).read_text())
    if not approval.get('approved') or not approval.get('independent_review_passed'):raise PermissionError('Coordinator approval and independent review required')
    if approval.get('max_train_components')!=32 or approval.get('max_dev_components')!=16:raise PermissionError('Wrong bounded profile scope')
    full=json.loads((extraction/'public/full_receipt.json').read_text());verified=json.loads((extraction/'public/verification_receipt.json').read_text())
    if full.get('arm_records')!=4814 or verified.get('records')!=4814 or verified.get('verified') is not True or verified.get('all_cache_hashes_and_annotation_fingerprints_verified') is not True:raise PermissionError('Complete verified extraction required')
    if verified.get('test_raw_bodies_read')!=0 or verified.get('davinci_bodies_read')!=0:raise ValueError('Unexpected prior extraction access')
    protocol=json.loads((extraction/'public/extraction_protocol.json').read_text())
    if protocol.get('cohort_manifest_sha256')!=EXPECTED_COHORT:raise ValueError('Wrong frozen cohort')
    return approval,verified,digest(canonical(protocol))

def descriptors(extraction,protocol_hash):
    data=(BASE/'m4_chinese_paired_20261002/private/cohort_identity_views.jsonl').read_bytes()
    if digest(data)!=EXPECTED_COHORT:raise ValueError('Frozen cohort metadata changed')
    rows=[json.loads(line) for line in data.splitlines()];rows=[r for r in rows if r['split'] in ('train','dev')]
    if collections.Counter(r['split'] for r in rows)!={'train':1816,'dev':591}:raise ValueError('Wrong population')
    bypair={r['pair_id']:r for r in rows};events={}
    for line in (extraction/'private/execution_ledger.jsonl').read_text().splitlines():
        event=json.loads(line)
        if event['event']=='cache_committed':
            if event['cache_file'] in events:raise ValueError('Duplicate cache commit')
            events[event['cache_file']]=event
    expected={f"{r['pair_id']}.{arm}.json.gz" for r in rows for arm in ('human','chatgpt')}
    if set(events)!=expected:raise ValueError('Missing/unexpected cache population')
    out=[]
    for name,event in sorted(events.items()):
        r=bypair[event['pair_id']];arm=event['arm']
        if event['split']!=r['split'] or arm not in ('human','chatgpt'):raise ValueError('Wrong cache arm/split')
        out.append(CacheDescriptor(str(extraction/'private/cache'/name),event['cache_sha256'],r['question_family_id'],r['pair_id'],r['component_id'],r['source'],r['split'],arm,protocol_hash))
    return out

def choose_components(desc,split,n):return set(sorted({d.component for d in desc if d.split==split},key=lambda c:hashed(split+'\0'+c))[:n])
def distribution(pairs,records=None):
    lengths=[t for i,t in pairs]
    if not lengths:return {'count':0}
    ordered=sorted(lengths)
    return {'count':len(lengths),'min':min(lengths),'median':ordered[len(ordered)//2],'p90':ordered[int(.9*(len(ordered)-1))],
        'p99':ordered[int(.99*(len(ordered)-1))],'max':max(lengths),'mean':sum(lengths)/len(lengths),
        'bins':{label:sum(lo<=x<=hi for x in lengths) for label,lo,hi in [('1',1,1),('2-4',2,4),('5-16',5,16),('17-64',17,64),('65+',65,10**9)]}}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--approval',required=True);args=ap.parse_args();start=time.monotonic();cpu=time.process_time()
    torch.set_num_threads(2);torch.set_num_interop_threads(2);os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
    socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
    extraction=BASE/'chinese-train-dev-measurement-20261002';approval,verification,protocol_hash=prerequisites(extraction,args.approval)
    auth=FitAuthorization(True,approval['receipt'],('read_train_dev_features','fit_transform'));desc=descriptors(extraction,protocol_hash)
    train_components=choose_components(desc,'train',32);dev_components=choose_components(desc,'dev',16)
    selected=[d for d in desc if d.split=='train' or (d.split=='dev' and d.component in dev_components)];private=ROOT/'private';private.mkdir(exist_ok=True)
    write(private/'throughput_selection.json',{'seed':SELECTION_SEED,'train_components':sorted(train_components),'dev_components':sorted(dev_components),
        'cache_paths_to_load':[d.path for d in selected],'purpose':'all TRAIN for transforms;32 TRAIN/16 DEV components for cost only'})
    catalog=Catalog.from_contract();records=[]
    for i,d in enumerate(selected):
        guard(start);records.append(load_train_dev_cache(d,catalog,auth))
        if (i+1)%500==0:print(json.dumps({'stage':'cache_loading','loaded':i+1,'total':len(selected)}),flush=True)
    validate_cohort(records);train=[r for r in records if r.split=='train'];dev=[r for r in records if r.split=='dev']
    transforms={};support={};timings={};capacity={};scope_q={}
    for scope in ('pooled','baike','web'):
        guard(start);tr=train if scope=='pooled' else [r for r in train if r.source==scope]
        transform=fit_transform(tr,catalog,source=None if scope=='pooled' else scope,authorization=auth);transforms[scope]=transform
        write(private/f'transform.{scope}.json',transform.to_dict())
        support[scope]={'train_questions':transform.fit_question_count,'target_gate_components':50,'target_component_support':dict(zip(catalog.ids,transform.component_support)),'all_unit_input_component_support':dict(zip(catalog.ids,transform.input_component_support)),
            'eligible_target_ids':[id for id,ok in zip(catalog.ids,transform.score_eligible) if ok],'frozen_zero_value_ids':[id for id,ok in zip(catalog.ids,transform.active_values) if not ok]}
        scope_q[scope]=len(BalancedPlan(tr,transform).questions)
    _,availability=common_support_channels(train,catalog);support['train_cell_unit_availability']=availability
    transform=transforms['pooled'];profile_train=[r for r in train if r.component in train_components]
    train_plan=BalancedPlan(profile_train,transform);dev_plan=BalancedPlan(dev,transform);train_pairs=list(train_plan.draws(1701,32))
    all_train_pairs=[(i,t) for i in train_plan.record_indices for t in train_plan.positions[i]];all_dev_pairs=[(i,t) for i in dev_plan.record_indices for t in dev_plan.positions[i]]
    dev_pairs=sorted(all_dev_pairs,key=lambda z:hashed('dev-prefix\0'+dev[z[0]].answer+'\0'+dev[z[0]].arm+'\0'+str(z[1])))[:16]
    if not dev_pairs:raise ValueError('No selected DEV timing support')
    write(private/'throughput_prefix_selection.json',{'train_pairs':train_pairs,'dev_pairs':dev_pairs,'train_record_keys':[(r.question,r.answer,r.arm) for r in profile_train],
        'dev_record_keys':[(r.question,r.answer,r.arm) for r in dev]})
    models,brackets=build_ladder(catalog,transform=transform);capacity['pooled_brackets']=brackets
    active=tuple(torch.where(transform.active_values)[0].tolist());targets=tuple(torch.where(transform.score_eligible)[0].tolist())
    independent,bracket=independent_capacity_match(catalog,parameter_count(models['F4']),target_indices=targets,active_value_indices=active)
    models['independent_F4']=independent;capacity['independent_bracket']=bracket
    for mode in ('mask_opportunity','pure_mask','length'):
        for name in ('F1','F2','F4'):models[mode+'.'+name]=build_control(catalog,name,mode,1701,transform)
    for name,model in models.items():
        guard(start);model.train();model.zero_grad(set_to_none=True);t0=time.monotonic();c0=time.process_time();losses=[]
        for i,t in train_pairs:
            guard(start);output=model(make_model_packet(profile_train[i],t,transform));losses.append(output.square().mean())
        # Match the real32-question minibatch graph footprint. This scalar is a
        # resource workload, not observed target loss; no optimizer is created.
        torch.stack(losses).mean().backward();guard(start);del losses,output
        train_seconds=time.monotonic()-t0;train_cpu=time.process_time()-c0
        model.zero_grad(set_to_none=True);model.eval();t0=time.monotonic();c0=time.process_time()
        with torch.no_grad():
            for i,t in dev_pairs:guard(start);model(make_model_packet(dev[i],t,transform))
        guard(start);dev_seconds=time.monotonic()-t0;dev_cpu=time.process_time()-c0
        timings[name]={'parameters':parameter_count(model),'width':model.width,'train_prefixes':len(train_pairs),'train_forward_backward_seconds':train_seconds,
            'train_cpu_seconds':train_cpu,'dev_prefixes':len(dev_pairs),'dev_forward_seconds':dev_seconds,'dev_cpu_seconds':dev_cpu}
        print(json.dumps({'stage':'model_profile','model':name,**timings[name]}),flush=True)
    for scope in ('baike','web'):
        ladder,bracket=build_ladder(catalog,transform=transforms[scope]);capacity[scope]={'models':{k:parameter_count(v) for k,v in ladder.items()},'brackets':bracket};del ladder;guard(start)
    groups=verification['groups'];dev_transitions={scope:sum(g['adjacent_transitions'] for key,g in groups.items() if key.startswith('dev|') and (scope=='pooled' or key.endswith('|'+scope))) for scope in ('pooled','baike','web')}
    projections=[]
    for run in registered_run_grid():
        scope=run['source'] or 'pooled';key=run['model'] if run['mode']=='values' else run['mode']+'.'+run['model'];t=timings[key];multiplier=10 if run.get('shuffle_training') else 1
        tr=t['train_forward_backward_seconds']/t['train_prefixes']*scope_q[scope];dv=t['dev_forward_seconds']/t['dev_prefixes']*dev_transitions[scope]*multiplier
        tc=t['train_cpu_seconds']/t['train_prefixes']*scope_q[scope];dc=t['dev_cpu_seconds']/t['dev_prefixes']*dev_transitions[scope]*multiplier
        projections.append({'run':run['id'],'max100epoch_seconds':100*(tr+dv),'max100epoch_cpu_seconds':100*(tc+dc),
            'per_epoch_train_seconds':tr,'per_epoch_dev_seconds':dv,'per_epoch_train_cpu_seconds':tc,'per_epoch_dev_cpu_seconds':dc})
    result={'status':'bounded_nonoptimizing_resource_profile_complete','empirical_optimizer_fits':0,'optimizer_steps':0,'train_only_preprocessing_fits':3,
        'performance_scores_or_model_selection':False,'raw_test_bodies_read':0,'davinci_bodies_read':0,'train_components_profiled':len(train_components),
        'dev_components_profiled':len(dev_components),'train_cache_records_loaded_for_transforms':len(train),'dev_cache_records_loaded':len(dev),
        'train_all_profile_prefix_distribution':distribution(all_train_pairs),'train_sample_prefix_distribution':distribution(train_pairs),
        'dev_all_selected_prefix_distribution':distribution(all_dev_pairs),'dev_sample_prefix_distribution':distribution(dev_pairs),'support':support,'capacity':capacity,'timings':timings,'projections':projections,
        'max100epoch72fit_projected_wall_hours':sum(r['max100epoch_seconds'] for r in projections)/3600,
        'max100epoch72fit_projected_cpu_hours':sum(r['max100epoch_cpu_seconds'] for r in projections)/3600,'projection_safety_factor':1.5,
        'max100epoch72fit_conservative_wall_hours':1.5*sum(r['max100epoch_seconds'] for r in projections)/3600,
        'max100epoch72fit_conservative_cpu_hours':1.5*sum(r['max100epoch_cpu_seconds'] for r in projections)/3600,
        'projection_cautions':['Small deterministic component sample','No optimizer-step/checkpoint cost included','Source-specific cost uses pooled timings',
            'DEV all-transition count upper-bounds eligible transitions','Early stopping not assumed','Stable centered covariance implementation'],
        'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,
        'quality_claim':'candidate_unvalidated','style_author_discourse_model':False}
    write(ROOT/'NATURAL_THROUGHPUT.json',result)
    print(json.dumps({k:v for k,v in result.items() if k in ('status','wall_seconds','cpu_seconds','peak_process_rss_bytes','max100epoch72fit_projected_wall_hours','max100epoch72fit_projected_cpu_hours','max100epoch72fit_conservative_cpu_hours')}),flush=True)
if __name__=='__main__':main()
