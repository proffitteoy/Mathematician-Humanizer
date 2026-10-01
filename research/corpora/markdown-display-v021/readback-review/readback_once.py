"""Bounded one-shot readback; never invokes the original diagnostic executor.

Only the three pinned raw diagnostics and their sealed projection envelopes are
read. The public default validator replay is real, budgeted computation.
"""
import argparse
import collections
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import types

ROOT=Path('/workspace/shared/style-markdown-projection-v02-1-diagnostic-review-v01')
EXECUTION=Path('/workspace/shared/style-markdown-projection-v02-1-diagnostic-v01')
PRIVATE=ROOT/'private';PUBLIC=ROOT/'public'
MANIFEST_SHA='9f565d98c5689db39aa23cb3d47600d5a530a1515eaacbdcb8151ea9ce6513b6'
RECEIPT_SHA='89ce29ab36ba8721f564fdd757ec39b08f3031df3e08510f5e7de50bdfadaded'
SEAL_SHA='d6a404d9c70c3c12c341968d491d326a45d85a71f7d25524f7265111acd41118'
RUNNER_SHA='b127b56c13844d669ae4e220d151be988c2bb8496fbaabd4d17ad7144ad60683'
PROJECTOR_SHA='7b9330df302fa3272617667662879a31cec13c323904b5f91715126704345688'
BASE_SHA='06da4976dfd55f48f55a23600f32561dd2325fcc1c7d3abb94b73752a9680f2a'
PROFILE='historical-blog-markdown-display-continuity/0.2.1'
BUDGET_ROOTS=(EXECUTION,Path('/workspace/shared/style-markdown-projection-v02-1'),ROOT,
              Path('/workspace/shared/style-markdown-projection-review-v02'))
CAP=4194304;RESERVE=65536;SECONDS=30;RSS=536870912

def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def pairs(items):
    out={}
    for key,value in items:
        if key in out:raise ValueError('duplicate_json_key')
        out[key]=value
    return out
def decode(raw):
    return json.loads(raw,object_pairs_hook=pairs,
                      parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite_json')))
def bound(path,digest):
    raw=path.read_bytes()
    if sha(raw)!=digest:raise ValueError('hash_binding_mismatch:'+path.name)
    return raw
def total_bytes():return sum(p.stat().st_size for root in BUDGET_ROOTS for p in root.rglob('*') if p.is_file())
def save(path,value,terminal=False):
    raw=canonical(value)+b'\n'
    if total_bytes()+len(raw)>(CAP if terminal else CAP-RESERVE):raise RuntimeError('charged_storage_cap')
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return sha(raw)

def independent_check(raw,value):
    """Independent total partition, fragment, hard-gap and proof reconstruction."""
    text=raw.decode('utf-8','strict');n=len(text)
    assert value['profile']==PROFILE and value['source_sha256']==sha(raw)
    assert value['source_bytes']==len(raw) and value['source_codepoints']==n
    assert value['projection_sha256']==sha(canonical({k:v for k,v in value.items() if k!='projection_sha256'}))
    kinds=[];roles=[];paragraphs=[];ids=[];end=0
    for region in value['regions']:
        lo,hi=region['start'],region['end']
        assert type(lo) is int and type(hi) is int and lo==end and lo<hi<=n
        assert region['kind'] in {'content','syntax_only','barrier'}
        kinds.extend([region['kind']]*(hi-lo));roles.extend([region['role']]*(hi-lo))
        paragraphs.extend([region['paragraph_id']]*(hi-lo));ids.extend([region['proof_ids']]*(hi-lo));end=hi
    assert end==n
    proof_map={}
    for index,proof in enumerate(value['syntax_proofs']):
        assert proof['id']==index and proof['base_sha256']==BASE_SHA
        assert proof['kind'] in {'resolved_emphasis_delimiters','validated_link_wrapper'}
        covered=set();prior=-1
        for lo,hi in proof['source_spans']:
            assert 0<=lo<hi<=n and lo>=prior;covered.update(range(lo,hi));prior=hi
        proof_map[index]=(covered,proof['paragraph_id'])
    offsets=[0]
    for char in text:offsets.append(offsets[-1]+len(char.encode('utf-8')))
    observed=[];edge_count=0;prior=-1
    for index,segment in enumerate(value['segments']):
        assert segment['index']==index
        positions=[]
        for lo,hi in segment['source_spans']:
            assert 0<=lo<hi<=n and lo>=prior;prior=hi
            positions.extend(range(lo,hi))
            assert raw[offsets[lo]:offsets[hi]].decode('utf-8')==text[lo:hi]
        assert positions and all(kinds[i]=='content' and paragraphs[i]==segment['paragraph_id'] for i in positions)
        assert segment['text']==''.join(text[i] for i in positions)
        assert segment['text_sha256']==sha(segment['text'].encode())
        assert segment['source_map']==[[i,i+1,'identity',0] for i in positions]
        assert segment['source_cover']==[positions[0],positions[-1]+1]
        expected_edges=[]
        for output_index,(left,right) in enumerate(zip(positions,positions[1:])):
            if right==left+1:continue
            assert right>left+1
            proof_set=set()
            for omitted in range(left+1,right):
                assert kinds[omitted]=='syntax_only' and paragraphs[omitted]==segment['paragraph_id']
                assert ids[omitted]
                for ident in ids[omitted]:
                    assert ident in proof_map
                    coverage,pid=proof_map[ident]
                    assert omitted in coverage and pid==segment['paragraph_id']
                    proof_set.add(ident)
            expected_edges.append({'left_output':output_index,'right_output':output_index+1,
                'source_gap':[left+1,right],'kind':'proved_syntax_only_elision','proof_ids':sorted(proof_set)})
        assert segment['continuity_edges']==expected_edges
        edge_count+=len(expected_edges);observed.extend(positions)
    assert observed==[i for i,kind in enumerate(kinds) if kind=='content']
    assert value['barriers']==[r for r in value['regions'] if r['kind']=='barrier']
    assert value['syntax_elisions']==[r for r in value['regions'] if r['kind']=='syntax_only']
    boundaries=[]
    for left,right in zip(value['segments'],value['segments'][1:]):
        lo,hi=left['source_cover'][1],right['source_cover'][0]
        boundaries.append({'left_segment':left['index'],'right_segment':right['index'],'source_gap':[lo,hi],
            'kind':'removed_content_or_unknown_boundary','reasons':sorted(set(roles[lo:hi]))})
    assert value['content_boundaries']==boundaries
    for field in ('table_annotation_scopes','table_caption_scopes'):
        for lo,hi in value[field]:assert 0<=lo<=hi<=n and all(kinds[i]=='barrier' for i in range(lo,hi))
    assert value['counts']=={'segments':len(value['segments']),'projected_codepoints':len(observed),'syntax_continuity_edges':edge_count}
    assert value['structural_status']==('quarantined' if value['issues'] else 'projected')
    assert not value['issues'] or not value['segments']
    for field in ('semantic_equivalence_claimed','model_admitted','split_eligible','natural_validation_performed','old_exclusion_certificate_applies'):
        assert value[field] is False
    assert value['human_origin']=='unknown' and value['rights_status']=='unverified' and value['author_attribution']=='unverified'
    return kinds,roles

def main():
    start=time.monotonic()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('readback_30_second_cap')))
    signal.setitimer(signal.ITIMER_REAL,SECONDS)
    resource.setrlimit(resource.RLIMIT_AS,(RSS,RSS));resource.setrlimit(resource.RLIMIT_CPU,(SECONDS,SECONDS))
    os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='2'
    os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
    ap=argparse.ArgumentParser();ap.add_argument('--contract-sha256',required=True);args=ap.parse_args()
    contract_raw=bound(PRIVATE/'readback.contract.private.json',args.contract_sha256);contract=decode(contract_raw)
    assert sha(Path(__file__).read_bytes())==contract['script_sha256']
    assert sha((PUBLIC/'READBACK_CONTRACT.zh.md').read_bytes())==contract['written_contract_sha256']
    for name,binding in contract['preflight_files'].items():
        assert Path(name).name==name
        data=bound(PUBLIC/name,binding['sha256']);assert len(data)==binding['bytes']
    assert contract['caps']=={'seconds':SECONDS,'address_space_bytes':RSS,'cpu_threads':2,'charged_bytes':CAP,'terminal_reserve_bytes':RESERVE}
    assert contract['budget_roots']==[str(p) for p in BUDGET_ROOTS]
    assert contract['execution_manifest_sha256']==MANIFEST_SHA and contract['receipt_sha256']==RECEIPT_SHA and contract['seal_sha256']==SEAL_SHA
    assert contract['root_authorized_scope']=='EXACT_THREE_EXPOSED_DIAGNOSTIC_READBACK_WITH_DEFAULT_REPLAY_ONLY'
    assert contract['interpreter']=={'path':sys.executable,'version':sys.version,'binary_sha256':sha(Path(sys.executable).read_bytes())}
    assert total_bytes()<CAP-RESERVE
    m=decode(bound(EXECUTION/'private/v021-diagnostic.manifest.private.json',MANIFEST_SHA))
    receipt=decode(bound(EXECUTION/'private/v021-diagnostic.receipt.private.json',RECEIPT_SHA))
    seal=decode(bound(EXECUTION/'private/v021-diagnostic.TERMINAL_SEAL.private.json',SEAL_SHA))
    assert not (EXECUTION/'private/v021-diagnostic.FAILURE.private.json').exists()
    assert seal['status']==receipt['status']=='completed' and seal['manifest_sha256']==MANIFEST_SHA and seal['receipt_sha256']==RECEIPT_SHA
    aggregate=decode(bound(EXECUTION/'public/v021-diagnostic.aggregate.json',seal['aggregate_sha256']))
    assert receipt['readback_remaining_reserved_seconds']==seal['readback_remaining_reserved_seconds']==30
    assert receipt['execution_reserved_seconds']==30 and receipt['elapsed_seconds']<30 and receipt['peak_rss_bytes']<RSS
    assert receipt['read_attempted']==receipt['read_completed']==receipt['projection_completed']==len(receipt['sources'])==3
    assert receipt['network_and_child_execution_kernel_denied'] is True and 'current_source' not in receipt
    assert contract['sources']==m['sources'] and len(m['sources'])==3
    assert sum(s['bytes'] for s in m['sources'])==52679 and all(s['permanently_excluded'] is True for s in m['sources'])
    for c in m['code']:
        data=bound(EXECUTION/'public'/c['name'],c['sha256']);assert len(data)==c['bytes']
    assert set(c['name'] for c in m['code'])=={p.name for p in (EXECUTION/'public').glob('*.py')}
    runner_raw=bound(EXECUTION/'public/diagnostic_runner.py',RUNNER_SHA)
    runner=types.ModuleType('frozen_guard_helpers');runner.__file__=str(EXECUTION/'public/diagnostic_runner.py')
    exec(compile(runner_raw,runner.__file__,'exec'),runner.__dict__)
    runner.verify_runtime_bindings(m);runner.verify_scope_manifest(m)
    runner.verify_go(m,MANIFEST_SHA,EXECUTION/'private/ROOT_GO.json',receipt['root_go_sha256'])
    runner.no_network_or_children()
    deps=decode(bound(Path(m['dependencies']['path']),m['dependencies']['sha256']))
    sys.meta_path.insert(0,runner.FrozenSourceLoader([b for d in deps for b in d['files']]))
    projector_raw=bound(Path(m['projector']['path']),PROJECTOR_SHA)
    bound(Path(m['base']['path']),BASE_SHA)
    module=types.ModuleType('readback_continuity_v021');module.__file__=m['projector']['path'];sys.modules[module.__name__]=module
    exec(compile(projector_raw,module.__file__,'exec'),module.__dict__)
    assert module.PROFILE==PROFILE
    save(PRIVATE/'readback.ONE_TIME_STARTED.private.json',{'status':'consumed_no_retry','contract_sha256':args.contract_sha256,
        'script_sha256':contract['script_sha256'],'elapsed_seconds':time.monotonic()-start,'root_authorized_scope':contract['root_authorized_scope']})
    out={'schema_version':'v021-independent-readback/1','status':'started','contract_sha256':args.contract_sha256,
         'execution_manifest_sha256':MANIFEST_SHA,'execution_receipt_sha256':RECEIPT_SHA,'execution_seal_sha256':SEAL_SHA,
         'raw_read_attempted':0,'raw_read_completed':0,'sealed_output_read_completed':0,'default_replay_completed':0,
         'independent_partition_completed':0,'members':[],'root_reserved_seconds':SECONDS,
         'new_candidate_body_reads':0,'original_executor_rerun':False,'default_validator_replay':True,
         'network_and_child_execution_kernel_denied':True,'durable_completion_requires_seal':True}
    try:
        stats=collections.Counter()
        for index,(source,executed) in enumerate(zip(m['sources'],receipt['sources'])):
            assert time.monotonic()-start<SECONDS and total_bytes()<CAP-RESERVE
            out['current_source']={'index':index,'source':source}
            pre=decode((EXECUTION/f'private/pre-read-{index:02}.private.json').read_bytes())
            post=decode((EXECUTION/f'private/post-read-{index:02}.private.json').read_bytes())
            assert pre['source']==post['source']==source and pre['manifest_sha256']==post['manifest_sha256']==MANIFEST_SHA
            assert 0<=pre['elapsed_seconds']<=post['elapsed_seconds']<=receipt['elapsed_seconds']
            assert post['actual_sha256']==source['sha256'] and post['actual_bytes']==source['bytes'] and post['source_verified'] is True
            assert executed['raw_sha256']==source['sha256'] and executed['canonical_member']==source['canonical_member']
            path=Path(source['path']);assert str(path.resolve())==source['path'] and not path.is_symlink() and path.stat().st_size==source['bytes']
            save(PRIVATE/f'pre-read-{index:02}.private.json',{'source':source,'contract_sha256':args.contract_sha256,'action':'read_exact_exposed_diagnostic','elapsed_seconds':time.monotonic()-start})
            out['raw_read_attempted']+=1
            with path.open('rb') as f:raw=f.read(source['bytes']+1)
            out['raw_read_completed']+=1
            save(PRIVATE/f'post-read-{index:02}.private.json',{'source_sha256':source['sha256'],'actual_sha256':sha(raw),'actual_bytes':len(raw),'contract_sha256':args.contract_sha256,'elapsed_seconds':time.monotonic()-start})
            assert sha(raw)==source['sha256'] and len(raw)==source['bytes']
            output=EXECUTION/f'private/diagnostic-projection-{index:02}.private.json.gz'
            assert executed['projection_path']==str(output)
            compressed=bound(output,executed['projection_sha256']);out['sealed_output_read_completed']+=1
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as f:expanded=f.read(20*1024**2+1)
            assert len(expanded)<=20*1024**2
            envelope=decode(expanded);assert set(envelope)=={'projection','diagnostic_metadata'}
            assert envelope['diagnostic_metadata']=={'canonical_member':source['canonical_member'],'commit':source['commit'],
                'permanent_exclusion':True,'purpose':'versioned_instrument_smoke_only','natural_role_qualification':False}
            value=envelope['projection'];assert value['counts']==executed['counts'] and value['issues']==executed['issues'] and value['structural_status']==executed['status']
            module.validate_projection(raw,value)  # default replay=True, intentionally budgeted
            out['default_replay_completed']+=1
            kinds,roles=independent_check(raw,value);out['independent_partition_completed']+=1
            fixed_issues=[]
            for issue in contract['known_role_spans']:
                if issue['raw_sha256']==source['sha256']:
                    lo,hi=issue['source_char_span']
                    assert all(kinds[i]=='barrier' and roles[i]=='unresolved_table_annotation_scope' for i in range(lo,hi))
                    fixed_issues.append({'source_char_span':[lo,hi],'status':'entire_known_table_note_span_is_hard_barrier'})
            member={'canonical_member':source['canonical_member'],'raw_sha256':source['sha256'],'output_sha256':sha(compressed),
                    'projection_sha256':value['projection_sha256'],'status':value['structural_status'],'counts':value['counts'],
                    'default_replay_passed':True,'independent_partition_passed':True,'known_role_spans':fixed_issues}
            out['members'].append(member);out.pop('current_source',None)
            stats.update(value['counts']);stats[value['structural_status']]+=1
        assert len(out['members'])==3 and sum(len(m['known_role_spans']) for m in out['members'])==1
        assert stats['segments']==aggregate['projected_segments'] and stats['projected_codepoints']==aggregate['projected_codepoints'] and stats['syntax_continuity_edges']==aggregate['syntax_continuity_edges']
        out['stats']=dict(stats);out['status']='completed'
    except BaseException as exc:
        out['status']='failed_no_retry';out['failure_type']=type(exc).__name__;out['failure_message']=str(exc)
    out['elapsed_seconds']=time.monotonic()-start
    out['cpu_seconds']=resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime
    out['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    out['charged_bytes_before_terminal']=total_bytes()
    out['execution_receipt_elapsed_seconds']=receipt['elapsed_seconds']
    out['combined_recorded_execution_readback_seconds']=receipt['elapsed_seconds']+out['elapsed_seconds']
    receipt_hash=save(PRIVATE/'readback.receipt.private.json',out,True)
    safe={k:out[k] for k in ('schema_version','status','contract_sha256','raw_read_attempted','raw_read_completed',
        'sealed_output_read_completed','default_replay_completed','independent_partition_completed','new_candidate_body_reads',
        'original_executor_rerun','default_validator_replay','elapsed_seconds','cpu_seconds','peak_rss_bytes','charged_bytes_before_terminal',
        'combined_recorded_execution_readback_seconds','durable_completion_requires_seal')}
    safe.update(receipt_sha256=receipt_hash,known_v01_table_annotation_now_excluded=out['status']=='completed',
        stats=out.get('stats',{}),source_admission_approved=False,human_origin_verified=False,old_exclusion_certificate_applies=False)
    aggregate_hash=save(PUBLIC/'readback.aggregate.json',safe,True)
    if time.monotonic()-start>=SECONDS:raise TimeoutError('terminal_deadline')
    save(PRIVATE/'readback.TERMINAL_SEAL.private.json',{'status':out['status'],'contract_sha256':args.contract_sha256,
        'receipt_sha256':receipt_hash,'aggregate_sha256':aggregate_hash,'terminal_elapsed_seconds':time.monotonic()-start},True)
    if time.monotonic()-start>=SECONDS:raise TimeoutError('terminal_deadline')
    signal.setitimer(signal.ITIMER_REAL,0)
    print(json.dumps(safe,sort_keys=True))
    if out['status']!='completed':raise SystemExit(1)

if __name__=='__main__':
    try:main()
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL,0)
        if (PRIVATE/'readback.ONE_TIME_STARTED.private.json').exists():
            try:save(PRIVATE/'readback.FAILURE.private.json',{'status':'failed_no_retry','failure_type':type(exc).__name__,'seal_invalid_if_present':True},True)
            except BaseException:pass
        raise
