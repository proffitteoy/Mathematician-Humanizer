#!/usr/bin/env python3
"""Synthetic forward/backward resource profile; no optimizer or corpus access."""
import json,os,resource,sys,time
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));torch.set_num_threads(2)
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
from experimental_natural.schema import Catalog,PrefixPacket
from experimental_natural.plan import build_ladder,registered_run_grid,build_control
from experimental_natural.models import parameter_count,independent_capacity_match
catalog=Catalog.from_contract();models,brackets=build_ladder(catalog)
independent,meta=independent_capacity_match(catalog,parameter_count(models['F4']));brackets['independent_F4']=meta;models['independent_F4']=independent
for mode in ('mask_opportunity','pure_mask','length'):
    for name in ('F1','F2','F4'):models[mode+'.'+name]=build_control(catalog,name,mode,1701)
measurements={};D=len(catalog.ids);started=time.monotonic()
for name,m in models.items():
    measurements[name]={'parameters':parameter_count(m),'width':m.width,'timings':[]}
    for length in (8,32,128):
        if time.monotonic()-started>1100:raise RuntimeError('Synthetic profile wall cap')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>2*1024**3:raise RuntimeError('Synthetic profile RSS cap')
        torch.manual_seed(55);v=torch.rand(length,D);obs=torch.rand(length,D)>.1;v[~obs]=0
        p=PrefixPacket(v,obs,torch.ones(length,D)*10,torch.ones(length,D,dtype=torch.bool),length)
        m(p).square().mean().backward();m.zero_grad(set_to_none=True);cpu=time.process_time();start=time.monotonic()
        out=m.forward_batch([p]*32).square().mean();out.backward()
        measurements[name]['timings'].append({'prefix_units':length,'batch_questions':32,'forward_backward_wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu})
        m.zero_grad(set_to_none=True);del out
    print(json.dumps({'model':name,**measurements[name]}),flush=True)
result={'kind':'post_reset_synthetic_throughput_no_empirical_fit','models':measurements,'brackets':brackets,'registered_optimizer_fit_count':len(registered_run_grid()),
    'empirical_optimizer_fits':0,'synthetic_optimizer_fits':0,'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
    'cpu_affinity':sorted(os.sched_getaffinity(0)),'threads':torch.get_num_threads(),'natural_cache_bodies_read':0,'test_or_davinci_bodies_read':0,
    'wall_seconds':time.monotonic()-started,'warning':'Full70 active architecture upper bounds; fixed synthetic prefix lengths do not estimate natural eligibility or full-run cost'}
(ROOT/'SYNTHETIC_THROUGHPUT.json').write_text(json.dumps(result,indent=2)+'\n');(ROOT/'REGISTERED_RUN_GRID.json').write_text(json.dumps(registered_run_grid(),indent=2)+'\n');print(json.dumps(result))
