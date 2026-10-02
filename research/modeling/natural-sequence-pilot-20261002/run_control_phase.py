#!/usr/bin/env python3
"""Explicitly authorized fixed mechanism-control phase; --plan performs no feature reads."""
import argparse,hashlib,json,os,re,socket,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def digest(blob):return hashlib.sha256(blob).hexdigest()
def read_json(path):return json.loads(Path(path).read_text())

BASE_SOURCE_MANIFEST_SHA256='6a2f74b87bf202c9791f8e7fd570cabb69590c84870c35c79e403623a1d43501'
CONTROL_ORDER=('pooled.shuffled.F4.1701','pooled.independent.F4.1701')

def control_recipe(run_id):
    if run_id==CONTROL_ORDER[0]:
        return {'id':run_id,'model':'F4','mode':'values','seed':1701,'source':None,'shuffle_training':True}
    if run_id==CONTROL_ORDER[1]:
        return {'id':run_id,'model':'independent_F4','mode':'values','seed':1701,'source':None}
    raise PermissionError('Undeclared control identity')

def verify_public_source(approval):
    base_path=ROOT/'STAGED_SOURCE_MANIFEST.json';base_blob=base_path.read_bytes()
    if digest(base_blob)!=BASE_SOURCE_MANIFEST_SHA256 or approval.get('base_source_manifest_sha256')!=BASE_SOURCE_MANIFEST_SHA256:
        raise PermissionError('Original20-file source binding changed')
    base=json.loads(base_blob)
    for name,expected in base['files'].items():
        if digest((ROOT/name).read_bytes())!=expected:raise PermissionError('Original source changed: '+name)
    path=ROOT/'CONTROL_SOURCE_MANIFEST.json';blob=path.read_bytes()
    if digest(blob)!=approval.get('source_manifest_sha256'):raise PermissionError('Approved control source manifest required')
    manifest=json.loads(blob)
    if manifest.get('base_source_manifest_sha256')!=BASE_SOURCE_MANIFEST_SHA256:raise PermissionError('Wrong original source identity')
    if any(manifest['files'].get(n)!=h for n,h in base['files'].items()):raise PermissionError('Original source omitted or replaced')
    for required in ('run_control_phase.py','CONTROL_EXECUTION_AMENDMENT.json'):
        if required not in manifest['files']:raise PermissionError('Control execution file omitted')
    for name,expected in manifest['files'].items():
        if digest((ROOT/name).read_bytes())!=expected:raise PermissionError('Control source changed: '+name)
    return digest(blob),manifest

def validate_approval(approval,amendment,phase):
    expected=[r['run_id'] for r in phase['runs']];runs=approval.get('run_ids',[])
    if tuple(expected)!=CONTROL_ORDER:raise PermissionError('Fixed control order changed')
    if not all(approval.get(k) is True for k in ('approved','optimizer_fits_approved','full_train_dev_features_approved','publication_verified','independent_review_passed','prune_obsolete_recovery_snapshots_approved')):
        raise PermissionError('Explicit reviewed, published, bounded control authorization required')
    if re.fullmatch('[0-9a-f]{40}',approval.get('published_source_commit','')) is None:raise PermissionError('Verified published source commit required')
    if approval.get('phase_id')!=phase['phase_id'] or not runs or runs!=expected[:len(runs)]:
        raise PermissionError('Only an explicitly authorized leading batch of the fixed controls may run')
    for field in ('max_phase_cpu_seconds','max_phase_wall_seconds'):
        if not 0<approval.get(field,0)<=phase[field]<=13.5*3600:raise PermissionError('Phase bound may only be stricter than sealed ceiling')
    if approval.get('max_global_cpu_seconds')!=24*3600 or approval.get('max_global_wall_seconds')!=24*3600:
        raise PermissionError('Original global budgets cannot be reset or enlarged')
    if approval.get('amendment_sha256')!=digest((ROOT/'CONTROL_EXECUTION_AMENDMENT.json').read_bytes()):raise PermissionError('Control amendment changed')
    if amendment.get('base_source_manifest_sha256')!=BASE_SOURCE_MANIFEST_SHA256:raise PermissionError('Wrong base source binding')
    caps=(6*3600,7.25*3600)
    for item,cap in zip(phase['runs'],caps):
        if item['max_cpu_seconds']!=cap or item['max_wall_seconds']!=cap:raise PermissionError('Control run caps changed')
        if item['recipe']!=control_recipe(item['run_id']):raise PermissionError('Control recipe changed')
    return runs

def validate_registry(run_id,registry):
    recipe=control_recipe(run_id)
    if registry.get(run_id)!=recipe:raise PermissionError('Registered control recipe differs from approved recipe')
    return recipe

def control_training_arguments(run):
    if run != control_recipe(run['id']):raise PermissionError('Training recipe changed')
    return {'seed':run['seed'],'run_id':run['id'],'source':None,
            'shuffle_training':run.get('shuffle_training',False)}

def assert_remaining_allocation(ledger,remaining,approval):
    events=ledger.events();cpu=ledger.consumed_cpu();starts=[e['started_unix'] for e in events if e['event']=='attempt_started']
    if not starts:raise PermissionError('Existing original study ledger required')
    used_wall=max(time.time()-min(starts),max((e.get('global_wall_seconds',0) for e in events),default=0))
    prior={}
    for e in events:prior[e['run_id']]=max(prior.get(e['run_id'],0),e.get('cpu_seconds',0),e.get('cpu_seconds_current_fit',0))
    required=sum(max(0,r['max_cpu_seconds']-prior.get(r['run_id'],0)) for r in remaining)
    if required>24*3600-cpu:raise RuntimeError('Requested control run caps exceed remaining original CPU budget')
    if used_wall>=24*3600 or cpu>=24*3600:raise RuntimeError('Original study budget exhausted')
    if min(approval['max_phase_wall_seconds'],24*3600-used_wall)<=0:raise RuntimeError('No original elapsed wall allocation remains')
    return {'CPU_used_seconds':cpu,'CPU_remaining_seconds':24*3600-cpu,'elapsed_wall_used_seconds':used_wall,'elapsed_wall_remaining_seconds':24*3600-used_wall}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',default='pooled_mechanism_seed1701');parser.add_argument('--approval');parser.add_argument('--plan',action='store_true')
    parser.add_argument('--resume-run');parser.add_argument('--reconciled-cpu-seconds',type=float);args=parser.parse_args()
    amendment=read_json(ROOT/'CONTROL_EXECUTION_AMENDMENT.json');phases={x['phase_id']:x for x in amendment['phases']}
    if args.phase not in phases:raise ValueError('Undeclared phase')
    phase=phases[args.phase]
    if args.plan:
        print(json.dumps(phase,indent=2));return
    if not args.approval:raise PermissionError('No optimizer authorization supplied')
    approval=read_json(args.approval);run_ids=validate_approval(approval,amendment,phase);source_hash,_=verify_public_source(approval)
    import torch
    from dataclasses import replace
    from profile_natural import descriptors,deny,EXPECTED_COHORT,canonical
    from experimental_natural.schema import Catalog,FitAuthorization,validate_cohort
    from experimental_natural.cache_adapter import load_train_dev_cache
    from experimental_natural.transforms import FrozenTransform
    from experimental_natural.plan import registered_run_grid,build_registered_model,transform_signature
    from experimental_natural.train import FitLedger,TrainingConfig
    from experimental_natural.staged_training import train_one_staged
    from experimental_natural.static_prefix_cache import CacheNamespace,StaticPrefixCache
    torch.set_num_threads(2);torch.set_num_interop_threads(2);os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
    socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
    extraction=ROOT.parent/'chinese-extraction-recovery-20261002'
    private=ROOT/'private/staged';private.mkdir(parents=True,exist_ok=True)
    full=read_json(extraction/'public/full_receipt.json');verification=read_json(extraction/'public/verification_receipt.json')
    if full.get('arm_records')!=4814 or verification.get('records')!=4814 or verification.get('verified') is not True or verification.get('all_cache_hashes_and_annotation_fingerprints_verified') is not True:
        raise PermissionError('Complete verified4814-arm extraction required')
    if verification.get('test_raw_bodies_read')!=0 or verification.get('davinci_bodies_read')!=0:raise PermissionError('Unexpected extraction access')
    protocol_data=read_json(extraction/'public/extraction_protocol.json')
    if protocol_data.get('cohort_manifest_sha256')!=EXPECTED_COHORT:raise PermissionError('Frozen cohort changed')
    protocol=digest(canonical(protocol_data))
    if digest((extraction/'public/verification_receipt.json').read_bytes())!=approval.get('verification_receipt_sha256'):
        raise PermissionError('Verified measurement receipt changed')
    for flag in ('cache_commit_unit_counts_verified','all_structural_span_widths_verified','equal_question_family_weights_verified'):
        if verification.get(flag) is not True:raise PermissionError('Incomplete structural/cohort verification')
    transform_path=ROOT/'private/transform.pooled.json';transform_blob=transform_path.read_bytes()
    if digest(transform_blob)!=approval.get('pooled_transform_file_sha256'):raise PermissionError('Frozen pooled transform changed')
    if digest((ROOT/'training_contract.json').read_bytes())!=amendment['base_contract_sha256']:raise PermissionError('Base scientific contract changed')
    transform=FrozenTransform.from_dict(json.loads(transform_blob));catalog=Catalog.from_contract();desc=descriptors(extraction,protocol)
    data_digest=digest('\n'.join(d.sha256 for d in desc).encode())
    if data_digest!=approval.get('train_dev_cache_manifest_sha256'):raise PermissionError('Approved TRAIN/DEV cache population changed')
    if len([d for d in desc if d.split=='train'])!=3632 or len([d for d in desc if d.split=='dev'])!=1182:raise ValueError('Unexpected full TRAIN/DEV population')
    ledger=FitLedger(private/'fit_ledger.jsonl',max_fits=100,max_cpu_seconds=24*3600)
    completed={e['run_id'] for e in ledger.events() if e['event']=='completed'}
    if args.resume_run and args.resume_run not in run_ids:raise PermissionError('Resume run not authorized in this fixed batch')
    # One phase clock/baseline survives later invocations; the staged engine
    # independently binds these values to each run's append-only identity.
    phase_path=private/(phase['phase_id']+'.json')
    if phase_path.exists():state=read_json(phase_path)
    else:
        state={'phase_id':phase['phase_id'],'started_unix':time.time(),'cpu_baseline':ledger.consumed_cpu(),'source_manifest_sha256':source_hash}
        with phase_path.open('x') as f:json.dump(state,f,sort_keys=True);f.flush();os.fsync(f.fileno())
    if state['source_manifest_sha256']!=source_hash:raise PermissionError('Cannot silently replace running-phase source')
    remaining=[r for r in phase['runs'] if r['run_id'] in run_ids and r['run_id'] not in completed]
    assert_remaining_allocation(ledger,remaining,approval)
    auth=FitAuthorization(True,approval['receipt'],('read_train_dev_features','train_model','prune_obsolete_recovery_snapshots'))
    records=[load_train_dev_cache(d,catalog,auth) for d in desc];validate_cohort(records)
    train=[r for r in records if r.split=='train'];dev=[r for r in records if r.split=='dev']
    profile=full['measurement_profile_sha256']
    if len(profile)!=1:raise ValueError('Ambiguous measurement profile')
    namespace=CacheNamespace(transform_signature(transform),profile[0]);cache=StaticPrefixCache(70,namespace,1<<30)
    bindings={'contract_sha256':amendment['base_contract_sha256'],'source_manifest_sha256':source_hash,
              'amendment_sha256':approval['amendment_sha256'],'train_dev_cache_manifest_sha256':data_digest,
              'verification_receipt_sha256':approval['verification_receipt_sha256'],'transform_sha256':transform_signature(transform)}
    # The already-reported analyticF0 remains unchanged; this phase does not recompute or overwrite it.
    grid={r['id']:r for r in registered_run_grid()};outdir=private/'checkpoints'
    for limits in phase['runs']:
        run_id=limits['run_id']
        if run_id not in run_ids or run_id in completed:continue
        if args.resume_run and run_id!=args.resume_run:
            if run_id not in completed:raise PermissionError('Cannot skip an earlier pending run to resume later')
            continue
        run=validate_registry(run_id,grid);model=build_registered_model(catalog,run,transform)
        config=replace(TrainingConfig(),max_fit_seconds=limits['max_wall_seconds'])
        prior=max((max(e.get('cpu_seconds',0),e.get('cpu_seconds_current_fit',0)) for e in ledger.events() if e['run_id']==run_id),default=0)
        active={'run_id':run_id,'phase_id':phase['phase_id'],'started_unix':time.time(),'process_pid':os.getpid(),
                'process_cpu_seconds_at_start':time.process_time(),'prior_run_cpu_seconds':prior}
        temporary=private/'ACTIVE_RUN.tmp';temporary.write_text(json.dumps(active)+'\n');os.replace(temporary,private/'ACTIVE_RUN.json')
        result=train_one_staged(model,train,dev,transform,**control_training_arguments(run),outdir=outdir,ledger=ledger,
            run_cpu_limit_seconds=limits['max_cpu_seconds'],phase_started_unix=state['started_unix'],phase_cpu_baseline=state['cpu_baseline'],
            cache=cache,cache_namespace=namespace,bindings=bindings,phase_id=phase['phase_id'],
            phase_cpu_limit_seconds=approval['max_phase_cpu_seconds'],phase_wall_limit_seconds=approval['max_phase_wall_seconds'],
            config=config,authorization=auth,resume=(args.resume_run==run_id),reconciled_cpu_seconds=args.reconciled_cpu_seconds,
            derived_root=private)
        print(json.dumps({'stage':'fit_completed','run_id':run_id,'selected_epoch':result['selected_epoch'],
            'global_cpu_seconds_used':ledger.consumed_cpu(),'global_cpu_seconds_remaining':24*3600-ledger.consumed_cpu()}),flush=True)
        args.resume_run=None;args.reconciled_cpu_seconds=None
    print(json.dumps({'phase_id':phase['phase_id'],'status':'authorized_batch_complete','global_cpu_seconds_used':ledger.consumed_cpu(),
        'remaining_registered_controls':'pending','full_study_complete':False,'style_claim':False}),flush=True)

if __name__=='__main__':main()
