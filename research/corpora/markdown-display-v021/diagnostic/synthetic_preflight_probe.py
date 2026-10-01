"""Execute three constructed strings under the proposed runtime limits.

No natural source body is opened. This is not the diagnostic executor.
"""
import json
import os
from pathlib import Path
import resource
import sys
import time
import types
import diagnostic_runner as r

started=time.monotonic()
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(30,30))
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='2'
os.environ['CUDA_VISIBLE_DEVICES']=''
r.no_network_or_children()
deps=json.loads((r.PRIVATE/'dependencies.private.json').read_bytes())
sys.meta_path.insert(0,r.FrozenSourceLoader([f for d in deps for f in d['files']]))
path=r.PROJECTOR_ROOT/'public/continuity_projection.py';code=path.read_bytes()
assert r.digest(code)==r.PROJECTOR_SHA
module=types.ModuleType('synthetic_v021_probe');module.__file__=str(path);sys.modules[module.__name__]=module
exec(compile(code,str(path),'exec'),module.__dict__)
cases=[('前 **强调** 和 [标签](https://example.test) 后。\n\n'*80).encode(),
       ('前[甲`code`乙](https://example.test)后。\n\n'*100).encode(),
       ('| a | b |\n|---|---|\n|x|y|\n\n* note\n\n# Next\n\n普通正文。\n\n'*100).encode()]
counts=[]
for raw in cases:
    result=module.project_bytes(raw)
    assert module.validate_projection(raw,result) is True
    counts.append(result['counts'])
aggregate={'schema_version':'v021-synthetic-preflight/1','status':'PASS','constructed_inputs':3,
           'natural_bodies_read':0,'projection_and_default_replay_verified':True,
           'kernel_network_and_child_execution_denied':True,'projector_sha256':r.PROJECTOR_SHA,
           'elapsed_seconds':time.monotonic()-started,
           'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
           'input_bytes':sum(map(len,cases)),'counts':counts}
r.save(r.PUBLIC/'synthetic-preflight.aggregate.json',aggregate)
print(json.dumps(aggregate,sort_keys=True))
