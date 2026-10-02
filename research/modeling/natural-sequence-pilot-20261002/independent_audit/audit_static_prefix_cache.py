"""Independent synthetic-only summary-cache identity/projection/resource audit."""
import dataclasses,hashlib,json,os,resource,sys,time,unittest
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_evaluation_reuse import packet,cut,seq,copy,cat,same,METRICS,F
from experimental_natural.schema import PrefixPacket,permute_packet
from experimental_natural.models import InputView,PrefixModel,IndependentFamilies
from experimental_natural.evaluation_reuse import OnlineMoments,CausalEvaluationState,evaluate_prefix_stream,evaluate_permutations,evaluate_cached_batch,_cached_batch_impl
from experimental_natural.static_prefix_cache import CacheNamespace,StaticPrefixCache

def cache(d=7,budget=1<<20):return StaticPrefixCache(d,CacheNamespace('a'*64,'b'*64),budget)
class IndependentStaticCacheAudit(unittest.TestCase):
 def setUp(self):torch.manual_seed(557);self.p=packet(23)
 def test_namespace_transform_profile_and_dtype_change_keys(self):
  c=cache();key=c.key(self.p)
  for a,b in [('c'*64,'b'*64),('a'*64,'c'*64)]:self.assertNotEqual(key,StaticPrefixCache(7,CacheNamespace(a,b)).key(self.p))
  for k in F:
   p=copy(self.p)
   if k=='prefix_values':p.prefix_observed[0,0]=True;p.prefix_values[0,0]+=1
   if k=='prefix_observed':p.prefix_values[0,0]=0;p.prefix_observed[0,0]=~p.prefix_observed[0,0]
   if k=='prefix_opportunity':p.prefix_opportunity_known[0,0]=True;p.prefix_opportunity[0,0]+=1
   if k=='prefix_opportunity_known':p.prefix_opportunity[0,0]=0;p.prefix_opportunity_known[0,0]=~p.prefix_opportunity_known[0,0]
   self.assertNotEqual(key,c.key(p))
  self.assertNotEqual(key,c.key(cut(self.p,22)))
  p=dataclasses.replace(self.p,prefix_values=self.p.prefix_values.double());self.assertNotEqual(key,c.key(p))
  with self.assertRaises(dataclasses.FrozenInstanceError):c.namespace.transform_sha256='c'*64
  with self.assertRaises(AttributeError):c.namespace=CacheNamespace('c'*64,'d'*64)
 def test_random_view_projection_including_unsorted_nuisance_and_empty_active(self):
  c=cache();canonical=c.get(self.p);g=torch.Generator().manual_seed(817)
  for _ in range(30):
   order=torch.randperm(7,generator=g).tolist();ix=tuple(order[:4]);nuisance=tuple(order[4:]);active=tuple(torch.randperm(7,generator=g)[:3].tolist())
   for mode in ('values','mask_opportunity','pure_mask','length'):
    for enabled in (active,()):
     view=InputView(7,ix,mode,nuisance,enabled)
     for cov in (False,True):same(c.project(canonical,view,cov),view.summarize(self.p,cov),'cache_projection_error')
 def test_all_ladder_controls_cached_outputs_and_gradients(self):
  c=cache();p=cut(self.p,9)
  for mode in ('values','mask_opportunity','pure_mask','length'):
   view=InputView(7,(5,6) if mode=='length' else tuple(range(7)),mode,active_value_indices=(0,2,3,5,6))
   for name in ('F1','Fcov','F2','F3','F4'):
    m=PrefixModel(name,view,7,5,target_indices=(0,2,5)).eval();ref=torch.stack([m(q) for q in seq(p)]);ref.square().sum().backward();grads=[x.grad.clone() for x in m.parameters()];m.zero_grad(set_to_none=True)
    state=CausalEvaluationState(m,c);got=state.heads([state._prepare_impl(q) for q in seq(p)]);same(ref,got,'cache_output_error');got.square().sum().backward()
    for want,x in zip(grads,m.parameters()):same(want,x.grad,'cache_gradient_error',1e-5,1e-5)
  self.assertGreater(c.hits,0)
 def test_exact_sparse_cached_batch_outputs_losses_and_gradients(self):
  from experimental_natural.objectives import family_loss
  c=cache();packets=[cut(self.p,n) for n in (23,2,11,1,7)];other=packet(16,seed=971);packets.append(cut(other,16))
  models=[]
  for mode in ('values','mask_opportunity','pure_mask','length'):
   view=InputView(7,(5,6) if mode=='length' else tuple(range(7)),mode,active_value_indices=(0,2,3,5,6))
   models.extend(PrefixModel(name,view,7,5,target_indices=(0,2,5)).eval() for name in ('F1','Fcov','F2','F3','F4'))
  models.append(IndependentFamilies(cat(),5,target_indices=(0,2,3,5,6)).eval())
  target=torch.arange(7).float()/7;mask=torch.tensor([1,0,1,0,0,1,0],dtype=torch.bool);weights=torch.arange(1,7).float()/21
  for m in models:
   ref=torch.stack([m(q) for q in packets]);loss=sum(w*family_loss(y,target,mask,cat().families)[0] for w,y in zip(weights,ref));loss.backward();grads=[x.grad.clone() for x in m.parameters()];m.zero_grad(set_to_none=True)
   got=_cached_batch_impl(m,packets,c);same(ref,got,'sparse_cached_batch_output_error');newloss=sum(w*family_loss(y,target,mask,cat().families)[0] for w,y in zip(weights,got));same(loss,newloss,'sparse_cached_batch_loss_error');newloss.backward()
   for want,param in zip(grads,m.parameters()):same(want,param.grad,'sparse_cached_batch_gradient_error',1e-5,1e-5)
   same(ref.detach(),evaluate_cached_batch(m,packets,c),'public_cached_batch_output_error')
  m=models[-1]
  for ps in ([],[packets[0]]*33):
   with self.assertRaises(ValueError):evaluate_cached_batch(m,ps,c)
  self.assertEqual(evaluate_cached_batch(m,[packets[0]]*32,c).shape,(32,7));m.train()
  with self.assertRaises(ValueError):evaluate_cached_batch(m,packets,c)
 def test_independent_cached_family_isolation(self):
  c=cache();m=IndependentFamilies(cat(),5,target_indices=(0,2,3,5,6)).eval()
  with torch.no_grad():ref=torch.stack([m(q) for q in seq(self.p)])
  got=torch.stack(list(evaluate_prefix_stream(m,seq(self.p),8,c)));same(ref,got,'cache_independent_output_error')
  p=copy(self.p);p.prefix_values[:,2:5].mul_(9);changed=torch.stack(list(evaluate_prefix_stream(m,seq(p),8,c)))
  same(got[:,0],changed[:,0],'cached_cross_family_value_error',0,0)
 def test_cache_mutations_stale_online_and_backing_storage_fail_closed(self):
  c=cache();a=c.get(self.p);before=a.clone();a.fill_(99);same(c.get(self.p),before,'cache_mutation_error',0,0)
  b=c.get(self.p);b.fill_(0);same(c.get(self.p),before,'cache_mutation_error',0,0)
  wrong=copy(self.p);wrong.prefix_values.mul_(2);o=OnlineMoments(7)
  for i in range(23):o.append(*(getattr(wrong,k)[i] for k in F))
  with self.assertRaises(ValueError):cache().get(self.p,o)
  with self.assertRaises(ValueError):c.get(dataclasses.replace(cut(self.p,2),prefix_values=self.p.prefix_values[:2]))
 def test_future_suffix_cache_identity_and_projected_prefixes(self):
  c=cache();a=cut(self.p,9);key=c.key(a);before=c.get(a);p=copy(self.p)
  for k in F:getattr(p,k)[9:].zero_()
  after=cut(p,9);self.assertEqual(key,c.key(after));same(before,c.get(after),'cache_future_error',0,0)
 def test_cache_eviction_with_fixed_small_budget(self):
  c=cache(budget=10000);view=InputView(7,tuple(range(7)))
  for p in seq(self.p):
   same(c.project(c.get(p),view,True),view.summarize(p,True),'cache_eviction_error')
   s=c.stats();self.assertLessEqual(s['tensor_bytes']+s['conservative_bookkeeping_bytes'],10000)
  self.assertGreater(c.evictions,0);self.assertEqual(c.stats()['disk_bytes'],0)
  for budget in (0,-1,(1<<30)+1):
   with self.assertRaises(ValueError):cache(budget=budget)
 def test_process_budget_includes_namespace_reserves_and_projection_maps(self):
  import gc
  from unittest.mock import patch
  gc.collect()
  baseline=StaticPrefixCache.retained_budget_bytes()
  with patch.object(StaticPrefixCache,'PROCESS_CACHE_LIMIT',baseline+8000):
   instances=[cache(budget=10000) for _ in range(3)]
   with self.assertRaises((ValueError,RuntimeError,MemoryError)):cache(budget=10000)
   self.assertLessEqual(StaticPrefixCache.retained_budget_bytes(),baseline+8000)
  c=cache(budget=10000);canonical=c.get(self.p)
  for i in range(7):
   for mode in ('values','mask_opportunity','pure_mask','length'):
    ix=tuple((i+j)%7 for j in range(7));v=InputView(7,ix,mode)
    for cov in (False,True):same(c.project(canonical,v,cov),v.summarize(self.p,cov),'bounded_map_projection_error')
  self.assertLessEqual(c._map_bytes,c._reserve)
 def test_cached_shuffled_and_last_preserving_same_declared_orders(self):
  c=cache();p=cut(self.p,13);m=PrefixModel('F4',InputView(7,tuple(range(7))),7,5,target_indices=(0,2,5)).eval();g=torch.Generator().manual_seed(129)
  for last in (False,True):
   orders=[torch.cat([torch.randperm(12,generator=g),torch.tensor([12])]) if last else torch.randperm(13,generator=g) for _ in range(10)]
   with torch.no_grad():ref=torch.stack([m(permute_packet(p,order)) for order in orders])
   same(ref,evaluate_permutations(m,p,orders,c),'cache_permutation_output_error')
 def test_727_structural_only_cache_shape_budget_and_all_prefix_retention(self):
  p=packet(727,70)
  for k in F:getattr(p,k).zero_()
  p.prefix_values[:,-2]=torch.arange(727).float()/11;p.prefix_observed[:,-2]=True
  c=cache(70,budget=1<<30);m=PrefixModel('F4',InputView(70,tuple(range(70))),70,4,target_indices=(0,68,69)).eval()
  outputs=torch.stack(list(evaluate_prefix_stream(m,seq(p),32,c)));self.assertEqual(tuple(outputs.shape),(727,70));self.assertEqual(c.stats()['entries'],727)
  self.assertEqual(tuple(c.get(p).shape),(17886,));self.assertEqual(c.stats()['tensor_bytes'],727*17886*4)
  with torch.no_grad():
   for n in (1,2,64,128,726,727):same(outputs[n-1],m(cut(p,n)),'cache_structural_727_output_error')
  METRICS['structural_cache_canonical_shape']=[17886];METRICS['structural_cache_rows']=727;METRICS['structural_cache_stats']=c.stats()

if __name__=='__main__':
 start=time.perf_counter();cpu=time.process_time();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentStaticCacheAudit))
 paths=['experimental_natural/evaluation_reuse.py','experimental_natural/static_prefix_cache.py','tests/test_evaluation_reuse.py','tests/test_static_prefix_cache.py','independent_audit/audit_static_prefix_cache.py']
 receipt={'kind':'independent_synthetic_static_prefix_cache_audit','successful':r.wasSuccessful(),'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'metrics':METRICS,'natural_body_reads':0,'natural_test_or_davinci_access':False,'natural_fits':0,'optimizer_steps':0,'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'torch_num_threads':torch.get_num_threads(),'cpu_affinity_count':len(os.sched_getaffinity(0)),'sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}}
 (ROOT/'independent_audit/STATIC_PREFIX_CACHE_AUDIT_RECEIPT.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');print(json.dumps(receipt,sort_keys=True));sys.exit(not r.wasSuccessful())
