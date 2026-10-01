"""Metadata/code-only proposal preparation. Never opens an article body."""
from pathlib import Path
import json
import sys
import diagnostic_runner as r

def binding(path):
    raw=path.read_bytes();return {'path':str(path),'sha256':r.digest(raw),'bytes':len(raw)}

def main():
    if r.MARKER.exists() or r.MANIFEST.exists():raise RuntimeError('proposal_or_execution_already_exists')
    allow=json.loads(r.ALLOWLIST.read_bytes());receipt=json.loads(r.ACQUISITION.read_bytes())
    sources=[]
    for a in allow['sources']:
        rows=[v for v in receipt['results'] if v['repository']==a['repository'] and v['path']==a['path'] and v['commit']==a['commit'] and v['diagnostic_exposure']]
        if len(rows)!=1:raise RuntimeError('diagnostic_receipt_identity')
        v=rows[0]
        if (v['sha256'],v['bytes'])!=(a['sha256'],a['bytes']):raise RuntimeError('diagnostic_receipt_binding')
        sources.append({'path':v['dest'],'sha256':a['sha256'],'bytes':a['bytes'],'commit':a['commit'],
                        'canonical_member':r.canonical(['gitblog',a['repository'],'post:'+a['path']]).decode(),
                        'permanently_excluded':True})
    if len(sources)!=3 or sum(s['bytes'] for s in sources)!=52679:raise RuntimeError('wrong_exact_three_scope')
    manifest={'schema_version':'markdown-v021-diagnostic-manifest/1',
        'action':'V021_ONE_TIME_THREE_EXPOSED_DIAGNOSTIC_PROPOSAL','status':'AWAITING_ROOT_FINAL_BINDING_GO',
        'sources':sources,'profile':r.PROFILE,'projector':binding(r.PROJECTOR_ROOT/'public/continuity_projection.py'),
        'base':binding(r.BASE_PATH),'contract':binding(r.PUBLIC/'DIAGNOSTIC_EXECUTION_CONTRACT.md'),
        'dependencies':binding(r.PRIVATE/'dependencies.private.json'),
        'allowlist_binding':binding(r.ALLOWLIST),'acquisition_receipt_binding':binding(r.ACQUISITION),
        'code':[{'name':p.name,'sha256':r.digest(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(r.PUBLIC.glob('*.py'))],
        'synthetic_tests':{'methods_passed':24,'log_sha256':r.digest((r.PUBLIC/'preflight-tests.log').read_bytes()),
                           'runtime_probe':binding(r.PUBLIC/'synthetic-preflight.aggregate.json')},
        'root_review_attestation':'Root assignment confirms independent inspection of exact v0.2.1 container-identity diff, 71 author/container tests and 33 independent adversaries passing; exact selected projector hash is separately pinned.',
        'interpreter':{'path':sys.executable,'version':sys.version,'binary_sha256':r.digest(Path(sys.executable).read_bytes())},
        'budget_roots':[str(p) for p in r.BUDGET_ROOTS],
        'caps':{'derivative_bytes':r.CAP,'cumulative_execution_readback_seconds':60,
                'execution_seconds':r.EXECUTION_SECONDS,'readback_seconds':r.READBACK_SECONDS,
                'rss_bytes':512*1024**2,'cpu_threads':2,'terminal_reserve_bytes':r.TERMINAL_RESERVE},
        'new_candidate_reads_authorized':False,'new_calibration_authorized':False,'fingerprint_access_authorized':False,
        'model_fit_authorized':False,'split_authorized':False,'remote_writes_authorized':False,'no_retry':True}
    r.verify_scope_manifest(manifest);r.verify_runtime_bindings(manifest)
    r.save(r.MANIFEST,manifest)
    print(json.dumps({'status':'READY_FOR_ROOT_BINDING_GO','manifest_sha256':r.digest(r.MANIFEST.read_bytes()),
       'contract_sha256':manifest['contract']['sha256'],'runner_sha256':r.digest((r.PUBLIC/'diagnostic_runner.py').read_bytes()),
       'budget_bytes':r.total_bytes(),'marker_exists':r.MARKER.exists(),'natural_body_reads':0},sort_keys=True))

if __name__=='__main__':main()
