"""Read back only the three explicitly authorized, already exposed diagnostics.

No projector invocation, new acquisition, NLP, fingerprints, fitting or splits.
The independent partition checks are in addition to the reviewed validator.
"""
import collections
import gzip
import hashlib
import json
import os
import pathlib
import resource
import signal
import sys
import time
import types

ROOT = pathlib.Path('/workspace/shared/style-markdown-projection-v01')
REVIEW = pathlib.Path('/workspace/shared/style-markdown-projection-review-v01')
MANIFEST_SHA = 'aa40b9b3e222a5ca522ae220d6aaf238b271d091180fbeee8a3f287e3cb2345d'
PROJECTOR_SHA = '06da4976dfd55f48f55a23600f32561dd2325fcc1c7d3abb94b73752a9680f2a'
RUNNER_SHA = 'ebb5376c543e9a17ae63a3606141b942e5d9dd9871258ebb67a49fb7b2cd9b72'

def sha(data): return hashlib.sha256(data).hexdigest()
def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def load(p): return json.loads(p.read_bytes())
def size(root): return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())

def main():
    started=time.monotonic()
    private=ROOT/'private'
    raw_manifest=(private/'diagnostic-smoke.manifest.private.json').read_bytes()
    assert sha(raw_manifest)==MANIFEST_SHA
    manifest=json.loads(raw_manifest)
    receipt_bytes=(private/'diagnostic-smoke.receipt.private.json').read_bytes()
    receipt=json.loads(receipt_bytes)
    seal=load(private/'diagnostic-smoke.TERMINAL_SEAL.private.json')
    aggregate_bytes=(ROOT/'public/diagnostic-smoke.aggregate.json').read_bytes()
    aggregate=json.loads(aggregate_bytes)
    marker=load(private/'diagnostic-smoke.ONE_TIME_STARTED.private.json')
    assert seal=={'status':'completed','receipt_sha256':sha(receipt_bytes),'aggregate_sha256':sha(aggregate_bytes),'manifest_sha256':MANIFEST_SHA}
    assert receipt['status']=='completed' and receipt['manifest_sha256']==MANIFEST_SHA
    assert marker['manifest_sha256']==MANIFEST_SHA and marker['status']=='consumed_no_retry'
    assert receipt['network_and_child_execution_kernel_denied'] is True
    assert receipt['read_attempted']==receipt['read_completed']==receipt['projection_completed']==len(receipt['sources'])==3
    assert 'current_source' not in receipt and 'error' not in receipt
    assert receipt['new_candidate_bodies_read']==0 and receipt['admission_approved'] is False
    assert receipt['elapsed_seconds']<60 and receipt['peak_rss_bytes']<512*1024**2
    assert size(ROOT)+size(REVIEW)<4*1024**2
    remaining=60-receipt['elapsed_seconds']-(time.monotonic()-started)
    assert remaining>0
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('combined smoke/readback wall limit')))
    signal.setitimer(signal.ITIMER_REAL,remaining)
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='2'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    code=(ROOT/'public/run_diagnostic_smoke.py').read_bytes();assert sha(code)==RUNNER_SHA
    runner=types.ModuleType('reviewed_smoke_runner');runner.__file__=str(ROOT/'public/run_diagnostic_smoke.py')
    exec(compile(code,runner.__file__,'exec'),runner.__dict__)
    runner.no_network_or_children()
    runner.verify_scope_manifest(manifest)
    for row in manifest['code']:
        data=(ROOT/'public'/row['name']).read_bytes()
        assert sha(data)==row['sha256'] and len(data)==row['bytes']
    dep=manifest['dependencies'];raw_deps=pathlib.Path(dep['path']).read_bytes();assert sha(raw_deps)==dep['sha256']
    deps=json.loads(raw_deps)
    sys.meta_path.insert(0,runner.FrozenSourceLoader([b for d in deps for b in d['files']]))
    source=(ROOT/'public/markdown_projection.py').read_bytes();assert sha(source)==PROJECTOR_SHA
    projector=types.ModuleType('markdown_projection');projector.__file__=str(ROOT/'public/markdown_projection.py')
    sys.modules[projector.__name__]=projector
    exec(compile(source,projector.__file__,'exec'),projector.__dict__)
    members=[];stats=collections.Counter();raw_bytes_read=0
    for index,(bound,result) in enumerate(zip(manifest['sources'],receipt['sources'])):
        pre=load(private/f'pre-read-{index:02}.private.json')
        post=load(private/f'post-read-{index:02}.private.json')
        assert pre['source']==post['source']==bound
        assert pre['manifest_sha256']==post['manifest_sha256']==MANIFEST_SHA
        assert 0<=pre['elapsed_seconds']<=post['elapsed_seconds']<=receipt['elapsed_seconds']
        assert post['actual_sha256']==bound['sha256'] and post['actual_bytes']==bound['bytes'] and post['source_verified'] is True
        assert result['raw_sha256']==bound['sha256'] and result['canonical_member']==bound['canonical_member']
        output=private/f'diagnostic-projection-{index:02}.private.json.gz'
        assert result['projection_path']==str(output)
        compressed=output.read_bytes();assert sha(compressed)==result['projection_sha256']
        with gzip.open(output,'rb') as f:
            expanded=f.read(20*1024**2+1)
        assert len(expanded)<=20*1024**2
        envelope=json.loads(expanded)
        assert set(envelope)=={'projection','diagnostic_metadata'}
        assert envelope['diagnostic_metadata']=={'canonical_member':bound['canonical_member'],'commit':bound['commit'],'permanent_exclusion':True,'purpose':'instrument_smoke_only'}
        path=pathlib.Path(bound['path'])
        assert str(path.resolve())==bound['path'] and not path.is_symlink() and path.stat().st_size==bound['bytes']
        raw=path.read_bytes();raw_bytes_read+=len(raw)
        assert sha(raw)==bound['sha256'] and len(raw)==bound['bytes']
        text=raw.decode('utf-8','strict');v=envelope['projection']
        projector.validate_projection(raw,v)
        assert v['counts']==result['counts'] and v['issues']==result['issues'] and v['structural_status']==result['status']
        # Independent total partition, complement, raw text and byte maps.
        byte_index=[0]
        for char in text:byte_index.append(byte_index[-1]+len(char.encode()))
        position=0;roles=collections.Counter();segment_spans=set()
        for region in v['regions']:
            lo,hi=region['source_char_span'];assert lo==position and hi>lo
            assert region['source_byte_span']==[byte_index[lo],byte_index[hi]]
            roles[region['role']]+=hi-lo;position=hi
        assert position==len(text)
        for seg in v['segments']:
            lo,hi=seg['source_char_span'];segment_spans.add((lo,hi))
            assert seg['text']==text[lo:hi] and raw[byte_index[lo]:byte_index[hi]].decode()==seg['text']
            assert seg['source_map']==[[i,i+1,'identity',0] for i in range(lo,hi)]
            assert seg['source_utf8_boundaries']==[i-byte_index[lo] for i in byte_index[lo:hi+1]]
        assert v['gaps']==[r for r in v['regions'] if tuple(r['source_char_span']) not in segment_spans]
        assert dict(roles)==v['counts']['role_codepoints']
        stats.update(records=1,segments=len(v['segments']),projected_codepoints=sum(len(s['text']) for s in v['segments']))
        stats[v['structural_status']]+=1
        members.append({'canonical_member':bound['canonical_member'],'raw_sha256':bound['sha256'],
                        'output_sha256':sha(compressed),'projection_sha256':v['projection_sha256'],
                        'structural_status':v['structural_status'],'issues':v['issues'],'source_map_verified':True})
    assert raw_bytes_read==52679
    assert aggregate['read_attempted']==aggregate['read_completed']==aggregate['projection_completed']==3
    assert aggregate['projected_segments']==stats['segments'] and aggregate['projected_codepoints']==stats['projected_codepoints']
    signal.setitimer(signal.ITIMER_REAL,0)
    private_result={'schema_version':'independent-three-diagnostic-readback/1','members':members}
    payload=canonical(private_result)+b'\n'
    (REVIEW/'private/smoke-readback.private.json').write_bytes(payload)
    output={'schema_version':'independent-three-diagnostic-readback/1','status':'PASS_EXACT_THREE_DIAGNOSTIC_READBACK',
            'manifest_sha256':MANIFEST_SHA,'receipt_sha256':sha(receipt_bytes),
            'terminal_seal_sha256':sha((private/'diagnostic-smoke.TERMINAL_SEAL.private.json').read_bytes()),
            'private_readback_sha256':sha(payload),'stats':dict(stats),'raw_bytes_read':raw_bytes_read,
            'reviewer_raw_reads':3,'new_candidate_reads':0,'projection_rerun':False,
            'independent_partition_checks':True,'elapsed_seconds':time.monotonic()-started,
            'combined_smoke_and_readback_seconds':receipt['elapsed_seconds']+time.monotonic()-started,
            'reviewer_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            'package_and_review_bytes_before_this_aggregate':size(ROOT)+size(REVIEW),
            'calibration_quality_inference':False,'source_admission':False,'human_origin_verified':False}
    assert output['combined_smoke_and_readback_seconds']<60 and output['package_and_review_bytes_before_this_aggregate']+8192<4*1024**2
    (REVIEW/'public/smoke-readback.aggregate.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(output,sort_keys=True))

if __name__=='__main__':main()
