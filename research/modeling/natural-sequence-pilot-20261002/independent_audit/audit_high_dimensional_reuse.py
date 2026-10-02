"""All-70-coordinate synthetic regression for wide-head floating-point changes."""
import hashlib,json,os,resource,sys,time
from pathlib import Path
from types import SimpleNamespace
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from experimental_natural.schema import Catalog
from experimental_natural.plan import build_ladder,build_control
from experimental_natural.models import independent_capacity_match,parameter_count
from experimental_natural.evaluation_reuse import evaluate_prefix_stream,evaluate_cached_batch
from experimental_natural.static_prefix_cache import StaticPrefixCache,CacheNamespace
from profile_kernels_synthetic import packet,prefix

def main():
 torch.set_num_threads(1);torch.set_num_interop_threads(1);os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);start=time.perf_counter();cpu=time.process_time()
 catalog=Catalog.from_contract();excluded={'zh:lexical.entropy100','zh:lexical.mattr100','zh:upos.bigram_entropy100'}
 transform=SimpleNamespace(active_values=torch.ones(70,dtype=torch.bool),score_eligible=torch.tensor([name not in excluded for name in catalog.ids]))
 models,_=build_ladder(catalog,1701,transform);targets=tuple(torch.where(transform.score_eligible)[0].tolist())
 models['independent_F4'],_=independent_capacity_match(catalog,parameter_count(models['F4']),target_indices=targets,active_value_indices=tuple(range(70)))
 for mode in ('mask_opportunity','pure_mask','length'):
  for name in ('F1','F2','F4'):models[mode+'.'+name]=build_control(catalog,name,mode,1701,transform)
 stats=[];cache=StaticPrefixCache(70,CacheNamespace('a'*64,'b'*64),1<<28)
 for n in (64,727):
  p=packet(n);selected=list(range(1,n+1)) if n==64 else [1,8,32,64,128,256,512,727]
  for name,model in models.items():
   model.eval()
   with torch.no_grad():ref=torch.stack([model(prefix(p,t)) for t in selected])
   outputs=torch.stack(list(evaluate_prefix_stream(model,(prefix(p,t) for t in range(1,n+1)),32,cache)))
   got=outputs[torch.tensor(selected)-1];error=float((got-ref).abs().max());torch.testing.assert_close(got,ref,atol=1e-6,rtol=1e-6)
   sparse=[]
   for i in range(0,len(selected),32):sparse.extend(evaluate_cached_batch(model,[prefix(p,t) for t in selected[i:i+32]],cache).unbind(0))
   sparse=torch.stack(sparse);error_sparse=float((sparse-ref).abs().max());torch.testing.assert_close(sparse,ref,atol=1e-6,rtol=1e-6)
   row={'prefix_count':n,'model':name,'reference_probe_count':len(selected),'full_dense_reference':n==64,'stream_error':error,'sparse_error':error_sparse};stats.append(row);print(json.dumps(row),flush=True)
 result={'successful':True,'kind':'independent_high_dimensional_synthetic_reuse_audit','architectures':len(models),'shape_model_cases':len(stats),'natural_body_reads':0,'natural_fits':0,'optimizer_steps':0,'test_or_davinci_reads':0,'max_output_error':max(max(x['stream_error'],x['sparse_error']) for x in stats),'cases':stats,'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'cache':cache.stats(),'sha256':{x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in ['experimental_natural/evaluation_reuse.py','experimental_natural/static_prefix_cache.py','profile_kernels_synthetic.py','independent_audit/audit_high_dimensional_reuse.py']}}
 (ROOT/'independent_audit/HIGH_DIMENSIONAL_REUSE_AUDIT_RECEIPT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
