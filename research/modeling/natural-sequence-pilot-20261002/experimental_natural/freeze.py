"""Immutable evaluator handoff; no TEST access or fitting."""
from pathlib import Path
import hashlib,json,os
from .plan import registered_run_grid

def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def freeze_bundle(destination,*,contract_path,transform_paths,checkpoint_paths,ledger,approved_panels):
    expected=[r['id'] for r in registered_run_grid()];ledger.assert_complete(expected)
    if set(checkpoint_paths)!=set(expected):raise ValueError('All registered checkpoints required')
    if set(transform_paths)!={'pooled','baike','web'}:raise ValueError('All TRAIN-only source scopes required')
    if set(approved_panels)!={'seen_generator','generator_transfer'}:raise ValueError('Unexpected panel')
    destination=Path(destination)
    if destination.exists():raise FileExistsError('Cannot silently overwrite frozen bundle')
    root=Path(__file__).parent
    manifest={'version':'experimental-natural-frozen/0.2-reconstructed','contract_sha256':sha256(contract_path),
        'code_sha256':{p.name:sha256(p) for p in sorted(root.glob('*.py'))},
        'transforms':{k:{'path':str(Path(v).resolve()),'sha256':sha256(v)} for k,v in transform_paths.items()},
        'checkpoints':{k:{'path':str(Path(v).resolve()),'sha256':sha256(v)} for k,v in checkpoint_paths.items()},
        'fit_ledger_sha256':sha256(ledger.path),'approved_panels':list(approved_panels),'quality_claim':'candidate_unvalidated','live_prefix_claim':False,
        'unrun_stages':['retrospective_permutation','block_models','sparse_gates','smooth_loss_residualization','natural_annotation_reliability'],'style_author_discourse_model':False}
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x') as stream:json.dump(manifest,stream,sort_keys=True,indent=2);stream.write('\n')
    os.chmod(destination,0o444);return manifest

def verify_frozen_bundle(manifest_path,contract_path):
    m=json.loads(Path(manifest_path).read_text())
    if sha256(contract_path)!=m['contract_sha256']:raise ValueError('Contract changed after freeze')
    for name,digest in m['code_sha256'].items():
        if sha256(Path(__file__).parent/name)!=digest:raise ValueError('Code changed after freeze')
    for group in ('transforms','checkpoints'):
        for entry in m[group].values():
            if sha256(entry['path'])!=entry['sha256']:raise ValueError('Frozen artifact changed')
    return m
