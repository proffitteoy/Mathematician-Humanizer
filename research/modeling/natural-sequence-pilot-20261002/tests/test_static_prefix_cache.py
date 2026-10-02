"""Static cache identity, view isolation, numerical equivalence and bounds."""
import dataclasses,unittest
from unittest.mock import patch
import torch
from experimental_natural.models import InputView,PrefixModel,IndependentFamilies
from experimental_natural.static_prefix_cache import StaticPrefixCache,CacheNamespace
from experimental_natural.evaluation_reuse import OnlineMoments,evaluate_prefix_stream,evaluate_permutations,evaluate_cached_batch,_cached_batch_impl
from test_evaluation_reuse import packet,prefixes,cut,catalog

class StaticCacheTests(unittest.TestCase):
    def cache(self,budget=1<<20):return StaticPrefixCache(6,CacheNamespace('1'*64,'2'*64),budget)

    def test_all_projected_views_match_reference(self):
        p=packet();cache=self.cache();canonical=cache.get(p)
        views=[InputView(6,tuple(range(6)),mode,active_value_indices=(0,2,3,4,5)) for mode in ('values','mask_opportunity','pure_mask')]
        views += [InputView(6,(5,4),'length'),InputView(6,(4,0,5,1),'values',(2,3))]
        for view in views:
            for cov in (False,True):torch.testing.assert_close(cache.project(canonical,view,cov),view.summarize(p,cov),atol=1e-6,rtol=1e-6)

    def test_namespace_and_all_packet_fields_change_identity(self):
        p=packet();cache=self.cache();key=cache.key(p)
        other=StaticPrefixCache(6,CacheNamespace('3'*64,'2'*64));self.assertNotEqual(key,other.key(p))
        for field in ('prefix_values','prefix_observed','prefix_opportunity','prefix_opportunity_known'):
            q=dataclasses.replace(p,**{k:getattr(p,k).clone() for k in ('prefix_values','prefix_observed','prefix_opportunity','prefix_opportunity_known')})
            if field=='prefix_values':q.prefix_values[0,0]+=1
            elif field=='prefix_observed':q.prefix_values[0,0]=0;q.prefix_observed[0,0]=False
            elif field=='prefix_opportunity':q.prefix_opportunity[0,0]=3;q.prefix_opportunity_known[0,0]=True
            else:q.prefix_opportunity[0,0]=0;q.prefix_opportunity_known[0,0]=~q.prefix_opportunity_known[0,0]
            self.assertNotEqual(key,cache.key(q))
        with self.assertRaises(AttributeError):cache.namespace=other.namespace

    def test_returned_tensor_mutation_does_not_corrupt_cache(self):
        cache=self.cache();p=packet();first=cache.get(p);first.fill_(999)
        second=cache.get(p);self.assertFalse(torch.equal(first,second));second.zero_()
        third=cache.get(p);self.assertFalse(torch.equal(second,third))

    def test_wrong_online_prefix_rejected(self):
        cache=self.cache();p=packet();online=OnlineMoments(6)
        q=dataclasses.replace(p,prefix_values=p.prefix_values*9)
        for i in range(19):online.append(q.prefix_values[i],q.prefix_observed[i],q.prefix_opportunity[i],q.prefix_opportunity_known[i])
        with self.assertRaises(ValueError):cache.get(p,online)

    def test_cache_bound_and_eviction_preserve_outputs(self):
        cache=self.cache(5000)
        for p in prefixes(packet()):
            canonical=cache.get(p);torch.testing.assert_close(cache.project(canonical,InputView(6,tuple(range(6))),True),InputView(6,tuple(range(6))).summarize(p,True),atol=1e-6,rtol=1e-6)
            s=cache.stats();self.assertLessEqual(s['tensor_bytes']+s['conservative_bookkeeping_bytes'],5000)
        self.assertGreater(cache.evictions,0)
        with self.assertRaises(ValueError):self.cache((1<<30)+1)

    def test_shared_independent_and_shuffle_cache_equivalence(self):
        torch.manual_seed(123);p=packet();cache=self.cache()
        models=[PrefixModel('F4',InputView(6,tuple(range(6))),6,8).eval(),IndependentFamilies(catalog(),7).eval()]
        for model in models:
            a=torch.stack(list(evaluate_prefix_stream(model,prefixes(p),5)))
            b=torch.stack(list(evaluate_prefix_stream(model,prefixes(p),5,cache)))
            torch.testing.assert_close(a,b,atol=1e-6,rtol=1e-6)
        orders=[torch.arange(19),torch.arange(18,-1,-1)]
        torch.testing.assert_close(evaluate_permutations(models[0],p,orders,cache),evaluate_permutations(models[0],p,orders),atol=1e-6,rtol=1e-6)
        self.assertGreater(cache.hits,0)

    def test_multiple_instances_share_process_cache_ceiling(self):
        with patch.object(StaticPrefixCache,'PROCESS_CACHE_LIMIT',12000):
            a=self.cache(5000);b=self.cache(5000)
            for p in prefixes(packet()):a.get(p);b.get(p)
            self.assertLessEqual(StaticPrefixCache.retained_budget_bytes(),12000)

    def test_cached_batch_outputs_and_parameter_gradients(self):
        torch.manual_seed(42);cache=self.cache();packets=list(prefixes(packet(7)))
        models=[PrefixModel(name,InputView(6,tuple(range(6))),6,8).eval() for name in ('F1','Fcov','F2','F3','F4')]
        models.append(IndependentFamilies(catalog(),6).eval())
        for model in models:
            ref=torch.stack([model(p) for p in packets]);ref.square().sum().backward()
            gradients=[p.grad.clone() for p in model.parameters()];model.zero_grad(set_to_none=True)
            out=_cached_batch_impl(model,packets,cache);out.square().sum().backward()
            torch.testing.assert_close(out,ref,atol=1e-6,rtol=1e-6)
            for expected,p in zip(gradients,model.parameters()):torch.testing.assert_close(p.grad,expected,atol=1e-5,rtol=1e-5)
            torch.testing.assert_close(evaluate_cached_batch(model,packets,cache),ref.detach(),atol=1e-6,rtol=1e-6)
