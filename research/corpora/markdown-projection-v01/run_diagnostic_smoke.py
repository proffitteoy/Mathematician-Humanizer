"""Root-authorized ONE-TIME three-exposed-diagnostic instrument smoke only.

Not a corpus runner or admission/calibration approval. Every source path/hash is
in an externally pinned manifest. Refuses a second invocation after its marker.
"""
from __future__ import annotations
import argparse
import ctypes
import errno
import gzip
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import types

ROOT=Path('/workspace/shared/style-markdown-projection-v01')
PUBLIC=ROOT/'public'; PRIVATE=ROOT/'private'
MARKER=PRIVATE/'diagnostic-smoke.ONE_TIME_STARTED.private.json'
MANIFEST=PRIVATE/'diagnostic-smoke.manifest.private.json'
ALLOWLIST=Path('/workspace/shared/style-scale10-source-v01/private/incremental-blog-exclusion-allowlist.private.json')
ACQUISITION=Path('/workspace/shared/style-pre2022-blog-acquisition/private/acquisition-receipt.json')
CAP=4*1024*1024
sys.dont_write_bytecode=True

def digest(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def total_bytes(): return sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
def save_blob(path,b,terminal=False):
    if total_bytes()+len(b)>(CAP if terminal else CAP-65536):raise RuntimeError('derivative_byte_cap')
    with path.open('xb') as f:
        f.write(b);f.flush();os.fsync(f.fileno())
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)

def save(path,value,terminal=False):
    save_blob(path,canonical(value)+b'\n',terminal)

def no_network_or_children():
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(38,1,0,0,0)!=0:raise RuntimeError('no_new_privileges_failed')
    lib=ctypes.CDLL('libseccomp.so.2',use_errno=True)
    lib.seccomp_init.argtypes=[ctypes.c_uint32];lib.seccomp_init.restype=ctypes.c_void_p
    lib.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    lib.seccomp_load.argtypes=[ctypes.c_void_p]
    lib.seccomp_release.argtypes=[ctypes.c_void_p]
    lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p]
    context=lib.seccomp_init(0x7fff0000)
    if not context: raise RuntimeError('seccomp_init_failed')
    try:
        for name in ('socket','socketpair','socketcall','connect','bind','listen','accept','accept4','sendto','sendmsg','sendmmsg','recvfrom','recvmsg','recvmmsg','execve','execveat','fork','vfork','clone','clone3','io_uring_setup'):
            number=lib.seccomp_syscall_resolve_name(name.encode())
            if number>=0 and lib.seccomp_rule_add(context,0x00050000|errno.EPERM,number,0)!=0:
                raise RuntimeError('seccomp_rule_failed')
        if lib.seccomp_load(context)!=0: raise RuntimeError('seccomp_load_failed')
    finally: lib.seccomp_release(context)
    def audit(event,args):
        if event=='import' and args and str(args[0]).split('.')[0] in {'torch','stanza','spacy','sklearn','transformers','tensorflow','jax'}:
            raise RuntimeError('nlp_or_model_import_forbidden')
        if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork'}:
            raise RuntimeError('child_execution_forbidden')
    sys.addaudithook(audit)

class FrozenSourceLoader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self, bindings):
        self.modules={}
        for b in bindings:
            path=Path(b['path'])
            raw=path.read_bytes()
            if digest(raw)!=b['sha256'] or len(raw)!=b['bytes']:raise RuntimeError('dependency_file_changed')
            if path.suffix!='.py':continue
            parts=path.parts
            name=next((n for n in ('markdown_it','mdurl') if n in parts),None)
            if name is None:continue
            suffix=parts[parts.index(name):]
            package=suffix[-1]=='__init__.py'
            dotted='.'.join(suffix[:-1] if package else suffix[:-1]+(path.stem,))
            self.modules[dotted]=(path,raw,package)
    def find_spec(self,fullname,path=None,target=None):
        if fullname in self.modules:
            return importlib.util.spec_from_loader(fullname,self,is_package=self.modules[fullname][2])
        if fullname.split('.')[0] in {'markdown_it','mdurl'}:
            raise RuntimeError('unbound_dependency_import')
        return None
    def create_module(self,spec):return None
    def exec_module(self,module):
        path,raw,package=self.modules[module.__name__]
        module.__file__=str(path)
        if package:module.__path__=[str(path.parent)]
        exec(compile(raw,str(path),'exec'),module.__dict__)

def verify_scope_manifest(manifest):
    values=[]
    for key,path in (('allowlist_binding',ALLOWLIST),('acquisition_receipt_binding',ACQUISITION)):
        binding=manifest[key]
        if binding['path']!=str(path):raise RuntimeError('scope_metadata_path_changed')
        raw=path.read_bytes()
        if digest(raw)!=binding['sha256']:raise RuntimeError('scope_metadata_changed')
        values.append(json.loads(raw))
    allow,acquisition=values
    if len(allow['sources'])!=3:raise RuntimeError('diagnostic_allowlist_size')
    expected=[]
    for a in allow['sources']:
        matches=[r for r in acquisition['results'] if r['repository']==a['repository'] and r['path']==a['path'] and r['commit']==a['commit'] and r['diagnostic_exposure']]
        if len(matches)!=1:raise RuntimeError('acquisition_diagnostic_binding')
        r=matches[0]
        if r['sha256']!=a['sha256'] or r['bytes']!=a['bytes']:raise RuntimeError('diagnostic_allowlist_binding')
        expected.append({'path':r['dest'],'sha256':a['sha256'],'bytes':a['bytes'],'commit':a['commit'],
            'canonical_member':canonical(['gitblog',a['repository'],'post:'+a['path']]).decode(),
            'permanently_excluded':True})
    if manifest['sources']!=expected:raise RuntimeError('exact_three_diagnostic_scope_mismatch')

def read_bound_source(source,index,receipt,started,manifest_sha):
    receipt['current_source']={'index':index,'binding':source}
    path=Path(source['path'])
    if path.is_symlink() or str(path.resolve())!=source['path']:raise RuntimeError('source_path_alias')
    if path.stat().st_size!=source['bytes']:raise RuntimeError('source_size_mismatch')
    save(PRIVATE/f'pre-read-{index:02}.private.json',{'source':source,'action':'open_exact_diagnostic_once',
         'manifest_sha256':manifest_sha,'permanently_excluded':True,'elapsed_seconds':time.monotonic()-started})
    receipt['read_attempted']+=1
    with path.open('rb') as handle:raw=handle.read(source['bytes']+1)
    receipt['read_completed']+=1
    save(PRIVATE/f'post-read-{index:02}.private.json',{'source':source,'action':'raw_read_completed',
         'actual_bytes':len(raw),'actual_sha256':digest(raw),
         'source_verified':len(raw)==source['bytes'] and digest(raw)==source['sha256'],
         'manifest_sha256':manifest_sha,'elapsed_seconds':time.monotonic()-started})
    if len(raw)!=source['bytes'] or digest(raw)!=source['sha256']:raise RuntimeError('diagnostic_source_mismatch')
    return raw

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest-sha256',required=True)
    args=ap.parse_args();started=time.monotonic()
    raw_manifest=MANIFEST.read_bytes()
    if digest(raw_manifest)!=args.manifest_sha256:raise RuntimeError('manifest_pin_mismatch')
    manifest=json.loads(raw_manifest)
    if manifest['action']!='ROOT_AUTHORIZED_ONE_TIME_THREE_DIAGNOSTIC_SMOKE' or len(manifest['sources'])!=3:
        raise RuntimeError('wrong_smoke_scope')
    if manifest['caps']!={'derivative_bytes':CAP,'wall_seconds':60,'rss_bytes':512*1024**2,'cpu_threads':2}:
        raise RuntimeError('wrong_smoke_caps')
    verify_scope_manifest(manifest)
    if manifest['interpreter']!={'path':sys.executable,'version':sys.version,'binary_sha256':digest(Path(sys.executable).read_bytes())}:
        raise RuntimeError('interpreter_binding_changed')
    if digest((PUBLIC/'synthetic-tests.log').read_bytes())!=manifest['synthetic_tests']['log_sha256']:
        raise RuntimeError('synthetic_log_changed')
    code={}
    for b in manifest['code']:
        if Path(b['name']).name!=b['name'] or not b['name'].endswith('.py'):raise RuntimeError('invalid_code_path')
        path=PUBLIC/b['name'];data=path.read_bytes()
        if digest(data)!=b['sha256']:raise RuntimeError('code_pin_mismatch')
        code[b['name']]=data
    # Atomic consumed marker is created before importing projector or reading any
    # diagnostic body. It remains on every error, including resource failure.
    save(MARKER,{'schema_version':'one-time-marker/1','manifest_sha256':args.manifest_sha256,
                 'status':'consumed_no_retry','root_authorization':manifest['root_authorization']})
    receipt={'schema_version':'markdown-three-diagnostic-smoke/1','status':'started',
             'manifest_sha256':args.manifest_sha256,'code_bindings':manifest['code'],
             'sources':[],'permanent_exclusions':3,'new_candidate_bodies_read':0,
             'instrument_smoke_only':True,'admission_approved':False,'fit_performed':False,
             'read_attempted':0,'read_completed':0,'projection_completed':0,
             'durable_completion_requires_seal':True}
    sandboxed=False
    try:
        for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
            os.environ[variable]='2'
        os.environ['CUDA_VISIBLE_DEVICES']=''
        available=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,available[:2])
        resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
        resource.setrlimit(resource.RLIMIT_CPU,(60,60))
        signal.signal(signal.SIGALRM,lambda signum,frame: (_ for _ in ()).throw(TimeoutError('wall_clock_cap')))
        signal.alarm(60)
        no_network_or_children()
        sandboxed=True
        dependency_bytes=Path(manifest['dependencies']['path']).read_bytes()
        if digest(dependency_bytes)!=manifest['dependencies']['sha256']:raise RuntimeError('dependency_manifest_changed')
        deps=json.loads(dependency_bytes)
        sys.meta_path.insert(0,FrozenSourceLoader([b for d in deps for b in d['files']]))
        module=types.ModuleType('markdown_projection');module.__file__=str(PUBLIC/'markdown_projection.py')
        sys.modules[module.__name__]=module
        exec(compile(code['markdown_projection.py'],module.__file__,'exec'),module.__dict__)
        for index,source in enumerate(manifest['sources']):
            if time.monotonic()-started>60:raise TimeoutError('wall_clock_cap')
            raw=read_bound_source(source,index,receipt,started,args.manifest_sha256)
            value=module.project_bytes(raw)
            envelope={'projection':value,'diagnostic_metadata':{'canonical_member':source['canonical_member'],
               'commit':source['commit'],'permanent_exclusion':True,'purpose':'instrument_smoke_only'}}
            encoded=gzip.compress(canonical(envelope),mtime=0)
            target=PRIVATE/f'diagnostic-projection-{index:02}.private.json.gz'
            save_blob(target,encoded)
            receipt['sources'].append({'raw_sha256':source['sha256'],'source_bytes':len(raw),
                'canonical_member':source['canonical_member'],'projection_path':str(target),
                'projection_sha256':digest(encoded),'status':value['structural_status'],
                'issues':value['issues'],'counts':value['counts']})
            receipt['projection_completed']+=1
            receipt.pop('current_source',None)
        receipt['status']='completed'
    except BaseException as exc:
        receipt['status']='failed_no_retry';receipt['error']=type(exc).__name__+':'+str(exc)
    finally:
        signal.alarm(0)
        receipt['elapsed_seconds']=time.monotonic()-started
        receipt['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        receipt['package_bytes_before_receipt']=total_bytes()
        receipt['no_other_source_bodies_read']=True
        receipt['network_and_child_execution_kernel_denied']=sandboxed
        receipt_bytes=canonical(receipt)+b'\n'
        save_blob(PRIVATE/'diagnostic-smoke.receipt.private.json',receipt_bytes,terminal=True)
        aggregate={'schema_version':'markdown-diagnostic-smoke-aggregate/1',
            'status':receipt['status'],'read_attempted':receipt['read_attempted'],
            'read_completed':receipt['read_completed'],'projection_completed':receipt['projection_completed'],
            'diagnostics_completed':len(receipt['sources']),'new_candidate_bodies_read':0,
            'structurally_projected':sum(x['status']=='projected' for x in receipt['sources']),
            'structurally_quarantined':sum(x['status']=='quarantined' for x in receipt['sources']),
            'projected_segments':sum(x['counts']['segments'] for x in receipt['sources']),
            'projected_codepoints':sum(x['counts']['projected_codepoints'] for x in receipt['sources']),
            'elapsed_seconds':receipt['elapsed_seconds'],'peak_rss_bytes':receipt['peak_rss_bytes'],
            'receipt_sha256':digest(receipt_bytes),
            'instrument_smoke_only':True,'natural_calibration_run':False,'admitted_records':0,
            'raw_text_published':False,'remote_writes':False,'retry_authorized':False,
            'durable_completion_requires_seal':True}
        save(PUBLIC/'diagnostic-smoke.aggregate.json',aggregate,terminal=True)
        save(PRIVATE/'diagnostic-smoke.TERMINAL_SEAL.private.json',{
            'status':receipt['status'],'receipt_sha256':digest(receipt_bytes),
            'aggregate_sha256':digest(canonical(aggregate)+b'\n'),
            'manifest_sha256':args.manifest_sha256},terminal=True)
        print(json.dumps(aggregate,sort_keys=True))
    if receipt['status']!='completed':raise SystemExit(1)

if __name__=='__main__':main()
