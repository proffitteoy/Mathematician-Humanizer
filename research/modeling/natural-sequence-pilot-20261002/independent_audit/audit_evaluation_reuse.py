"""Independent synthetic-only causal evaluation reuse audit. Never reads corpora."""
import dataclasses, hashlib, json, os, resource, sys, time, unittest
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from experimental_natural.schema import PrefixPacket,Catalog,permute_packet
from experimental_natural.models import InputView,PrefixModel,IndependentFamilies,parameter_count
from experimental_natural.evaluation_reuse import OnlineMoments,CausalEvaluationState,evaluate_prefix_stream,evaluate_permutations
from experimental_natural.objectives import family_loss

torch.set_num_threads(1)
torch.set_num_interop_threads(1)
if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
F=('prefix_values','prefix_observed','prefix_opportunity','prefix_opportunity_known')
METRICS={}
def record_metric(k,v):METRICS[k]=max(METRICS.get(k,0),float(v))
def packet(n=29,d=7,seed=13187):
 g=torch.Generator().manual_seed(seed);m=torch.rand(n,d,generator=g)>.32;k=torch.rand(n,d,generator=g)>.41
 x=torch.randn(n,d,generator=g)*m;o=torch.rand(n,d,generator=g)*1e3*k
 x[:,1]=9*m[:,1]
 return PrefixPacket(x,m,o,k,n)
def cut(p,t):return PrefixPacket(*(getattr(p,k)[:t].clone() for k in F),t)
def seq(p):return (cut(p,t) for t in range(1,p.prefix_unit_count+1))
def copy(p):return cut(p,p.prefix_unit_count)
def cat():return Catalog(tuple('abcdefg'),('A','A','B','B','C','length','length'),('raw_then_train_zscore',)*7,(5,6),())
def same(a,b,key='output_error',atol=1e-6,rtol=1e-6):
 record_metric(key,(a-b).abs().max());torch.testing.assert_close(a,b,atol=atol,rtol=rtol)

class IndependentReuseAudit(unittest.TestCase):
 def setUp(self):torch.manual_seed(731);self.p=packet()
 def test_twenty_ladders_and_controls_outputs_losses_and_gradients(self):
  for mode in ('values','mask_opportunity','pure_mask','length'):
   view=InputView(7,(5,6) if mode=='length' else tuple(range(7)),mode,active_value_indices=(0,2,3,5,6))
   for name in ('F1','Fcov','F2','F3','F4'):
    model=PrefixModel(name,view,7,9,target_indices=(0,2,5)).eval();before=parameter_count(model)
    p=cut(self.p,13);ref=torch.stack([model(q) for q in seq(p)])
    weights=torch.linspace(.1,1,len(ref));target=torch.arange(7).float()/7;mask=torch.tensor([1,0,1,0,0,1,0],dtype=torch.bool)
    loss=sum(w*family_loss(y,target,mask,cat().families)[0] for w,y in zip(weights,ref));loss.backward()
    gradients=[x.grad.clone() for x in model.parameters()];model.zero_grad(set_to_none=True)
    state=CausalEvaluationState(model);got=state.heads([state._prepare_impl(q) for q in seq(p)])
    same(ref,got);got_loss=sum(w*family_loss(y,target,mask,cat().families)[0] for w,y in zip(weights,got));same(loss,got_loss,'loss_error')
    got_loss.backward()
    for want,param in zip(gradients,model.parameters()):same(want,param.grad,'gradient_error',1e-5,1e-5)
    self.assertEqual(before,parameter_count(model));self.assertTrue(torch.equal(got[:,[1,3,4,6]],torch.zeros(13,4)))
 def test_independent_families_gradient_equivalence_and_isolation(self):
  model=IndependentFamilies(cat(),5,target_indices=(0,2,3,5,6),active_value_indices=(0,2,3,5,6)).eval();p=cut(self.p,17)
  ref=torch.stack([model(q) for q in seq(p)]);ref.square().mean().backward();grads=[q.grad.clone() for q in model.parameters()];model.zero_grad(set_to_none=True)
  state=CausalEvaluationState(model);got=state.heads([state._prepare_impl(q) for q in seq(p)]);same(ref,got);got.square().mean().backward()
  for want,param in zip(grads,model.parameters()):same(want,param.grad,'gradient_error',1e-5,1e-5)
  b=copy(p);b.prefix_values[:,2:5]*=13
  a=torch.stack(list(evaluate_prefix_stream(model,seq(p),5)));other=torch.stack(list(evaluate_prefix_stream(model,seq(b),5)))
  same(a[:,0],other[:,0],'cross_family_value_error',0,0)
 def test_pair_moments_missing_constant_extremes_and_pruning(self):
  probes=[]
  for n,value in ((1,0.),(7,1e15),(727,1e15)):
   x=torch.full((n,7),value);probes.append(PrefixPacket(x,torch.ones_like(x,dtype=torch.bool),torch.zeros_like(x),torch.zeros_like(x,dtype=torch.bool),n))
  missing=packet();missing.prefix_values.zero_();missing.prefix_observed.zero_();missing.prefix_opportunity.zero_();missing.prefix_opportunity_known.zero_();probes.append(missing)
  p=packet(97);p.prefix_values.mul_(1e10);p.prefix_values.add_(p.prefix_observed*1e15);probes.append(p)
  for p in probes:
   state=OnlineMoments(7)
   for t in range(p.prefix_unit_count):state.append(*(getattr(p,k)[t] for k in F))
   for view in (InputView(7,tuple(range(7)),active_value_indices=(0,2,4,5,6)),InputView(7,(0,1,5,6),'values',(2,3,4)),InputView(7,(5,6),'length'),InputView(7,tuple(range(7)),'pure_mask')):
    for cov in (False,True):
     a=state.summary(view,cov);b=view.summarize(p,cov)
     torch.testing.assert_close(a,b,atol=1e-6,rtol=2e-6)
     record_metric('moment_scaled_error',((a-b).abs()/(1+b.abs())).max())
     self.assertTrue(torch.isfinite(a).all())
 def test_shuffled_last_preserving_losses_selected_orders(self):
  p=cut(self.p,17);g=torch.Generator().manual_seed(9761)
  for mode in ('values','mask_opportunity','pure_mask','length'):
   model=PrefixModel('F4',InputView(7,(5,6) if mode=='length' else tuple(range(7)),mode),7,9,target_indices=(0,2,5)).eval()
   for preserve in (False,True):
    orders=[torch.cat([torch.randperm(16,generator=g),torch.tensor([16])]) if preserve else torch.randperm(17,generator=g) for _ in range(10)]
    with torch.no_grad():ref=torch.stack([model(permute_packet(p,order)) for order in orders])
    got=evaluate_permutations(model,p,orders);same(ref,got,'permutation_output_error')
    target=torch.arange(7).float()/7;mask=torch.tensor([1,0,1,0,0,1,0],dtype=torch.bool)
    a=torch.stack([family_loss(y,target,mask,cat().families)[0] for y in ref]).mean();b=torch.stack([family_loss(y,target,mask,cat().families)[0] for y in got]).mean();same(a,b,'permutation_loss_error')
 def test_boolean_masks_cannot_masquerade_as_permutations(self):
  model=PrefixModel('F4',InputView(7,tuple(range(7))),7,9).eval();p=cut(self.p,2)
  for dtype in (torch.bool,torch.uint8):
   with self.assertRaises((ValueError,TypeError,IndexError)):evaluate_permutations(model,p,[torch.tensor([0,1],dtype=dtype)])
 def test_future_suffix_values_masks_opportunities_and_length_cannot_leak(self):
  model=PrefixModel('F4',InputView(7,tuple(range(7))),7,9).eval();a=torch.stack(list(evaluate_prefix_stream(model,seq(self.p),1)))
  b=copy(self.p)
  for k in F:getattr(b,k)[9:].zero_()
  changed=torch.stack(list(evaluate_prefix_stream(model,seq(b),64)));same(a[:9],changed[:9],'future_prefix_error')
  shortened=torch.stack(list(evaluate_prefix_stream(model,seq(cut(self.p,9)),7)));same(a[:9],shortened,'future_length_error')
 def test_batch_sizes_selected_prefixes_and_allmissing(self):
  model=PrefixModel('F4',InputView(7,tuple(range(7))),7,9).eval();sel=(0,2,8,14,28)
  with torch.no_grad():ref=torch.stack([model(cut(self.p,t+1)) for t in sel])
  for batch in (1,2,7,32,100):
   result=torch.stack(list(evaluate_prefix_stream(model,seq(self.p),batch)));same(ref,result[list(sel)],'selected_prefix_error')
  p=copy(self.p)
  for k in F:getattr(p,k).zero_()
  with torch.no_grad():ref=torch.stack([model(q) for q in seq(p)])
  same(ref,torch.stack(list(evaluate_prefix_stream(model,seq(p),8))),'allmissing_output_error')
 def test_padding_views_mutation_and_parameter_updates_rejected(self):
  model=PrefixModel('F4',InputView(7,tuple(range(7))),7,9).eval()
  with torch.no_grad():
   state=CausalEvaluationState(model);first=cut(self.p,1);state.prepare(first);first.prefix_values[0,0]+=1
   changed=cut(self.p,2);changed.prefix_values[0]=first.prefix_values[0]
   with self.assertRaises(ValueError):state.prepare(changed)
   state=CausalEvaluationState(model)
   with self.assertRaises(ValueError):state.prepare(dataclasses.replace(cut(self.p,1),prefix_values=self.p.prefix_values[:1]))
   with self.assertRaises(ValueError):state.prepare(dataclasses.replace(cut(self.p,2),prefix_unit_count=1))
   state.prepare(cut(self.p,1));next(model.parameters()).add_(.01)
   with self.assertRaises(RuntimeError):state.prepare(cut(self.p,2))
  model.train()
  with self.assertRaises(ValueError):CausalEvaluationState(model)
 def test_generator_does_not_leak_autograd_state_when_paused(self):
  model=PrefixModel('F4',InputView(7,tuple(range(7))),7,9).eval();g=evaluate_prefix_stream(model,seq(self.p),2)
  before=torch.is_grad_enabled()
  try:next(g);self.assertEqual(torch.is_grad_enabled(),before)
  finally:g.close()
 def test_727_unit_structural_only_shape_and_reference(self):
  p=packet(727,70)
  for k in F:getattr(p,k).zero_()
  p.prefix_values[:,-2]=torch.arange(727).float()/17;p.prefix_observed[:,-2]=True
  model=PrefixModel('F4',InputView(70,tuple(range(70))),70,6,target_indices=(0,68,69)).eval()
  got=torch.stack(list(evaluate_prefix_stream(model,seq(p),32)));self.assertEqual(got.shape,(727,70))
  with torch.no_grad():
   for n in (1,2,63,64,65,128,726,727):same(got[n-1],model(cut(p,n)),'structural_727_output_error')
  METRICS['structural_727_prediction_shape']=list(got.shape)

if __name__=='__main__':
 start=time.perf_counter();cpu=time.process_time();suite=unittest.defaultTestLoader.loadTestsFromTestCase(IndependentReuseAudit);result=unittest.TextTestRunner(verbosity=2).run(suite)
 paths=['training_contract.json','EXECUTION_CLARIFICATIONS.json','experimental_natural/models.py','experimental_natural/train.py','experimental_natural/schema.py','experimental_natural/transforms.py','experimental_natural/objectives.py','experimental_natural/plan.py','experimental_natural/evaluation_reuse.py','tests/test_evaluation_reuse.py','independent_audit/audit_evaluation_reuse.py']
 receipt={'kind':'independent_synthetic_evaluation_reuse_audit','successful':result.wasSuccessful(),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'metrics':METRICS,'natural_body_reads':0,'natural_test_or_davinci_access':False,'optimizer_steps':0,'natural_fits':0,'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'torch_num_threads':torch.get_num_threads(),'cpu_affinity_count':len(os.sched_getaffinity(0)),'sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}}
 (ROOT/'independent_audit/EVALUATION_REUSE_AUDIT_RECEIPT.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(json.dumps(receipt,sort_keys=True));sys.exit(not result.wasSuccessful())
