"""Immutable evaluator handoff; no TEST access or fitting."""
from pathlib import Path
import hashlib,json,os
import torch
from .plan import registered_run_grid,build_registered_model,transform_signature
from .schema import Catalog
from .transforms import FrozenTransform

def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def freeze_bundle(destination,*,contract_path,transform_paths,checkpoint_paths,ledger,approved_panels):
    grid=registered_run_grid();expected=[r['id'] for r in grid];ledger.assert_complete(expected)
    if set(checkpoint_paths)!=set(expected):raise ValueError('All registered checkpoints required')
    if set(transform_paths)!={'pooled','baike','web'}:raise ValueError('All TRAIN-only source scopes required')
    if set(approved_panels)!={'seen_generator','generator_transfer'}:raise ValueError('Unexpected panel')
    completed={e['run_id']:e for e in ledger.events() if e['event']=='completed'}
    if set(completed)!=set(expected):raise ValueError('Completed ledger identities differ from fixed grid')
    # First bind every file to the successful training event, not merely to
    # whatever arbitrary bytes happen to exist at freeze time.
    for run in grid:
        entry=completed[run['id']]
        if sha256(checkpoint_paths[run['id']])!=entry.get('checkpoint_sha256'):raise ValueError('Checkpoint hash does not match completed fit ledger')
    catalog=Catalog.from_contract(contract_path)
    transforms={k:FrozenTransform.from_dict(json.loads(Path(v).read_text())) for k,v in transform_paths.items()}
    for scope,transform in transforms.items():
        if transform.ids!=catalog.ids or transform.source_scope!=(None if scope=='pooled' else scope):raise ValueError('Wrong frozen channel/source transform')
    for run in grid:
        scope=run['source'] or 'pooled';transform=transforms[scope];entry=completed[run['id']]
        checkpoint=torch.load(checkpoint_paths[run['id']],map_location='cpu',weights_only=True)
        if checkpoint.get('run_id')!=run['id'] or checkpoint.get('seed')!=run['seed']:raise ValueError('Checkpoint run/seed identity mismatch')
        if checkpoint.get('epoch')!=entry.get('selected_epoch') or checkpoint.get('dev_score')!=entry.get('best_dev_score'):raise ValueError('Checkpoint does not match selected DEV decision')
        if transform_signature(FrozenTransform.from_dict(checkpoint['transform']))!=transform_signature(transform):raise ValueError('Checkpoint transform does not match frozen source fit')
        model=build_registered_model(catalog,run,transform);expected_state=model.state_dict();actual=checkpoint['state_dict']
        if set(actual)!=set(expected_state):raise ValueError('Checkpoint architecture mismatch')
        for key in actual:
            if actual[key].shape!=expected_state[key].shape:raise ValueError('Checkpoint parameter shape mismatch')
            if not torch.isfinite(actual[key]).all():raise ValueError('Nonfinite frozen checkpoint')
            if key.endswith('output_indices') and not torch.equal(actual[key],expected_state[key]):raise ValueError('Checkpoint target-coordinate mapping changed')
        model.load_state_dict(actual,strict=True)
    destination=Path(destination)
    if destination.exists():raise FileExistsError('Cannot silently overwrite frozen bundle')
    root=Path(__file__).parent
    manifest={'version':'experimental-natural-frozen/0.2-reconstructed','contract_sha256':sha256(contract_path),
        'code_sha256':{p.name:sha256(p) for p in sorted(root.glob('*.py'))},
        'transforms':{k:{'path':str(Path(v).resolve()),'sha256':sha256(v)} for k,v in transform_paths.items()},
        'checkpoints':{k:{'path':str(Path(v).resolve()),'sha256':sha256(v)} for k,v in checkpoint_paths.items()},
        'fit_ledger_path':str(Path(ledger.path).resolve()),'fit_ledger_sha256':sha256(ledger.path),'approved_panels':list(approved_panels),'quality_claim':'candidate_unvalidated','live_prefix_claim':False,
        'unrun_stages':['retrospective_permutation','block_models','sparse_gates','smooth_loss_residualization','natural_annotation_reliability'],'style_author_discourse_model':False}
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x') as stream:json.dump(manifest,stream,sort_keys=True,indent=2);stream.write('\n')
    os.chmod(destination,0o444);return manifest

def verify_frozen_bundle(manifest_path,contract_path):
    m=json.loads(Path(manifest_path).read_text())
    if sha256(contract_path)!=m['contract_sha256']:raise ValueError('Contract changed after freeze')
    if 'fit_ledger_path' not in m or sha256(m['fit_ledger_path'])!=m['fit_ledger_sha256']:raise ValueError('Fit ledger changed after freeze')
    for name,digest in m['code_sha256'].items():
        if sha256(Path(__file__).parent/name)!=digest:raise ValueError('Code changed after freeze')
    for group in ('transforms','checkpoints'):
        for entry in m[group].values():
            if sha256(entry['path'])!=entry['sha256']:raise ValueError('Frozen artifact changed')
    return m
