"""Independent 70-coordinate long-prefix permutation equivalence regression."""
import hashlib,json,os,resource,sys,time
from pathlib import Path
from types import SimpleNamespace
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from experimental_natural.schema import Catalog,permute_packet
from experimental_natural.plan import build_ladder
from experimental_natural.evaluation_reuse import evaluate_permutations
from experimental_natural.static_prefix_cache import StaticPrefixCache,CacheNamespace
from experimental_natural.objectives import family_loss
from profile_kernels_synthetic import packet

def main():
 torch.set_num_threads(1);torch.set_num_interop_threads(1);os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);start=time.perf_counter();catalog=Catalog.from_contract();excluded={'zh:lexical.entropy100','zh:lexical.mattr100','zh:upos.bigram_entropy100'}
 eligible=torch.tensor([x not in excluded for x in catalog.ids]);transform=SimpleNamespace(active_values=torch.ones(70,dtype=torch.bool),score_eligible=eligible)
 models,_=build_ladder(catalog,1701,transform);model=models['F4'].eval();cache=StaticPrefixCache(70,CacheNamespace('a'*64,'b'*64),1<<20);cases=[]
 for n in (64,727):
  p=packet(n)
  for last in (False,True):
   orders=[]
   for rep in range(10):
    g=torch.Generator().manual_seed(47011+rep);orders.append(torch.cat([torch.randperm(n-1,generator=g),torch.tensor([n-1])]) if last else torch.randperm(n,generator=g))
   with torch.no_grad():ref=torch.stack([model(permute_packet(p,o)) for o in orders])
   got=evaluate_permutations(model,p,orders,cache);torch.testing.assert_close(got,ref,atol=1e-6,rtol=1e-6)
   target=torch.zeros(70);a=torch.stack([family_loss(x,target,eligible,catalog.families)[0] for x in ref]).mean();b=torch.stack([family_loss(x,target,eligible,catalog.families)[0] for x in got]).mean();torch.testing.assert_close(a,b,atol=1e-6,rtol=1e-6)
   cases.append({'prefix_units':n,'preserve_last':last,'permutations':10,'output_max_error':float((ref-got).abs().max()),'mean_separate_family_loss_error':float((a-b).abs())})
 result={'successful':True,'kind':'independent_synthetic_long_prefix_permutation_audit','cases':cases,'wall_seconds':time.perf_counter()-start,'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'natural_body_reads':0,'natural_fits':0,'optimizer_steps':0,'sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['experimental_natural/evaluation_reuse.py','experimental_natural/static_prefix_cache.py','independent_audit/audit_permutation_tail.py']}}
 (ROOT/'independent_audit/PERMUTATION_TAIL_AUDIT_RECEIPT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
