"""Synthetic equivalence and information-boundary regressions for DEV reuse."""
import dataclasses, unittest
from types import SimpleNamespace
import torch
from experimental_natural.schema import PrefixPacket, Catalog, permute_packet
from experimental_natural.models import InputView, PrefixModel, IndependentFamilies
from experimental_natural.objectives import family_loss
from experimental_natural.evaluation_reuse import OnlineMoments, CausalEvaluationState, evaluate_prefix_stream, evaluate_permutations


def packet(n=19, d=6):
    gen = torch.Generator().manual_seed(921)
    m = torch.rand((n, d), generator=gen) > .3
    m[:, 0] = False; m[0, 0] = True; m[-1, 0] = True
    x = torch.randn((n, d), generator=gen)*m
    x[:, 1] = 7*m[:, 1]  # Constant observed channel, typed missingness retained
    known = torch.rand((n, d), generator=gen) > .4
    o = torch.randint(0, 20, (n, d), generator=gen).float()*known
    return PrefixPacket(x, m, o, known, n)


def cut(p, n):
    return PrefixPacket(*(getattr(p, k)[:n].clone() for k in
        ('prefix_values','prefix_observed','prefix_opportunity','prefix_opportunity_known')), n)


def prefixes(p):
    for n in range(1, p.prefix_unit_count+1):
        yield cut(p, n)


def catalog():
    return Catalog(tuple('abcdef'), ('A','A','B','B','structural_length','structural_length'),
                   ('raw_then_train_zscore',)*6, (4,5), ())


class ReuseTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(1701)
        self.p = packet()

    def test_pair_centered_moments_modes_pruning_and_family_views(self):
        views = [InputView(6, tuple(range(6)), mode, active_value_indices=(0,2,3,4,5))
                 for mode in ('values','mask_opportunity','pure_mask')]
        views += [InputView(6,(4,5),'length'), InputView(6,(0,1,4,5),'values',(2,3))]
        state = OnlineMoments(6)
        for p in prefixes(self.p):
            state.append(p.prefix_values[-1],p.prefix_observed[-1],p.prefix_opportunity[-1],p.prefix_opportunity_known[-1])
            for v in views:
                for cov in (False,True):
                    torch.testing.assert_close(state.summary(v,cov),v.summarize(p,cov),atol=1e-6,rtol=1e-6)

    def test_huge_constant_covariance_stability(self):
        for scale in (1e10,1e15):
            p=PrefixPacket(torch.full((100,2),scale),torch.ones(100,2,dtype=torch.bool),torch.ones(100,2),torch.ones(100,2,dtype=torch.bool),100)
            s=OnlineMoments(2)
            for q in prefixes(p):s.append(q.prefix_values[-1],q.prefix_observed[-1],q.prefix_opportunity[-1],q.prefix_opportunity_known[-1])
            v=InputView(2,(0,1));torch.testing.assert_close(s.summary(v,True),v.summarize(p,True),atol=0,rtol=0)

    def test_all_ladders_controls_batched_output_and_family_loss(self):
        views=[InputView(6,tuple(range(6)),mode) for mode in ('values','mask_opportunity','pure_mask')]+[InputView(6,(4,5),'length')]
        for view in views:
            for name in ('F1','Fcov','F2','F3','F4'):
                model=PrefixModel(name,view,6,8,target_indices=(0,2,3,4,5)).eval()
                with torch.no_grad():reference=torch.stack([model(p) for p in prefixes(self.p)])
                result=torch.stack(list(evaluate_prefix_stream(model,prefixes(self.p),7)))
                torch.testing.assert_close(result,reference,atol=1e-6,rtol=1e-6)
                mask=self.p.prefix_observed[-1].clone();mask[1]=False
                for a,b in zip(reference,result):
                    l,_=family_loss(a,self.p.prefix_values[-1],mask,catalog().families)
                    r,_=family_loss(b,self.p.prefix_values[-1],mask,catalog().families)
                    torch.testing.assert_close(l,r,atol=1e-6,rtol=1e-6)

    def test_independent_family_outputs_and_no_cross_family_value_path(self):
        model=IndependentFamilies(catalog(),7,target_indices=(0,2,3,4,5)).eval()
        with torch.no_grad():ref=torch.stack([model(p) for p in prefixes(self.p)])
        result=torch.stack(list(evaluate_prefix_stream(model,prefixes(self.p),5)))
        torch.testing.assert_close(result,ref,atol=1e-6,rtol=1e-6)
        changed=dataclasses.replace(self.p,prefix_values=self.p.prefix_values.clone())
        changed.prefix_values[:,2:4]*=19
        other=torch.stack(list(evaluate_prefix_stream(model,prefixes(changed),5)))
        torch.testing.assert_close(result[:,0],other[:,0],atol=0,rtol=0)

    def test_parameter_gradient_equivalence_of_reused_kernels(self):
        # Public reuse rejects autograd; test the private mathematical kernel
        # before any proposal to reuse it for training.
        for model in [PrefixModel('F4',InputView(6,tuple(range(6))),6,8).eval(),IndependentFamilies(catalog(),7).eval()]:
            ref=torch.stack([model(p) for p in prefixes(self.p)])
            weights=torch.linspace(.1,1,len(ref))[:,None]
            (ref.square()*weights).sum().backward()
            gradients=[p.grad.clone() for p in model.parameters()];model.zero_grad(set_to_none=True)
            state=CausalEvaluationState(model)
            reuse=state.heads([state._prepare_impl(p) for p in prefixes(self.p)])
            (reuse.square()*weights).sum().backward()
            for expected,p in zip(gradients,model.parameters()):torch.testing.assert_close(p.grad,expected,atol=1e-5,rtol=1e-5)

    def test_shuffled_last_preserving_predictions_and_mean_losses(self):
        model=PrefixModel('F4',InputView(6,tuple(range(6))),6,8).eval();gen=torch.Generator().manual_seed(911)
        for last in (False,True):
            orders=[torch.cat([torch.randperm(18,generator=gen),torch.tensor([18])]) if last else torch.randperm(19,generator=gen) for _ in range(10)]
            with torch.no_grad():ref=torch.stack([model(permute_packet(self.p,x)) for x in orders])
            result=evaluate_permutations(model,self.p,orders)
            torch.testing.assert_close(result,ref,atol=1e-6,rtol=1e-6)
            target=self.p.prefix_values[-1];mask=self.p.prefix_observed[-1]
            a=torch.stack([family_loss(x,target,mask,catalog().families)[0] for x in ref]).mean()
            b=torch.stack([family_loss(x,target,mask,catalog().families)[0] for x in result]).mean()
            torch.testing.assert_close(a,b,atol=1e-6,rtol=1e-6)

    def test_future_mutation_and_head_batch_invariance(self):
        model=PrefixModel('F4',InputView(6,tuple(range(6))),6,8).eval()
        a=torch.stack(list(evaluate_prefix_stream(model,prefixes(self.p),1)))
        b=torch.stack(list(evaluate_prefix_stream(model,prefixes(self.p),32)))
        torch.testing.assert_close(a,b,atol=1e-6,rtol=1e-6)
        changed=dataclasses.replace(self.p,prefix_values=self.p.prefix_values.clone(),prefix_observed=self.p.prefix_observed.clone())
        changed.prefix_values[9:]=0;changed.prefix_observed[9:]=False
        c=torch.stack(list(evaluate_prefix_stream(model,prefixes(changed),32)))
        torch.testing.assert_close(a[:9],c[:9],atol=1e-6,rtol=1e-6)

    def test_reject_updates_changed_past_padding_and_training(self):
        m=PrefixModel('F4',InputView(6,tuple(range(6))),6,8)
        with self.assertRaises(ValueError):CausalEvaluationState(m)
        m.eval();state=CausalEvaluationState(m)
        with self.assertRaises(RuntimeError):state.prepare(cut(self.p,1))
        with torch.no_grad():
            state.prepare(cut(self.p,1))
            bad=cut(self.p,2);bad.prefix_values[0,1]+=1
            with self.assertRaises(ValueError):state.prepare(bad)
            next(m.parameters()).add_(.001)
            with self.assertRaises(RuntimeError):state.prepare(cut(self.p,2))

    def test_727_structural_only_units_are_preserved(self):
        p=packet(727,70);x=torch.zeros_like(p.prefix_values);m=torch.zeros_like(p.prefix_observed)
        x[:,-2]=torch.arange(727).float()/100;m[:,-2]=True
        p=PrefixPacket(x,m,torch.zeros_like(x),torch.zeros_like(m),727)
        model=PrefixModel('F4',InputView(70,tuple(range(70))),70,8).eval()
        result=torch.stack(list(evaluate_prefix_stream(model,prefixes(p),32)))
        self.assertEqual(result.shape,(727,70))
        with torch.no_grad():
            for n in (1,2,64,128,726,727):torch.testing.assert_close(result[n-1],model(cut(p,n)),atol=1e-6,rtol=1e-6)

    def test_partial_generator_preserves_callers_grad_context(self):
        model=PrefixModel('F4',InputView(6,tuple(range(6))),6,8).eval()
        generator=evaluate_prefix_stream(model,prefixes(self.p),2)
        self.assertTrue(torch.is_grad_enabled());next(generator);self.assertTrue(torch.is_grad_enabled())
        generator.close();self.assertTrue(torch.is_grad_enabled())
        def bad_packets():
            yield cut(self.p,1)
            raise RuntimeError('synthetic iterator failure')
        generator=evaluate_prefix_stream(model,bad_packets(),1)
        next(generator);self.assertTrue(torch.is_grad_enabled())
        with self.assertRaises(RuntimeError):next(generator)
        self.assertTrue(torch.is_grad_enabled())

    def test_boolean_permutation_cannot_become_a_row_mask(self):
        model=PrefixModel('F4',InputView(6,tuple(range(6))),6,8).eval()
        for order in (torch.tensor([False,True]),torch.tensor([0,1],dtype=torch.uint8),torch.tensor([[0,1]])):
            with self.assertRaises(ValueError):evaluate_permutations(model,cut(self.p,2),[order])

    def test_large_head_preserves_reference_float32_reduction_order(self):
        from experimental_natural.plan import build_ladder
        from profile_kernels_synthetic import packet as diagnostic_packet
        c=Catalog.from_contract();eligible=torch.tensor([x not in {'zh:lexical.entropy100','zh:lexical.mattr100','zh:upos.bigram_entropy100'} for x in c.ids])
        models,_=build_ladder(c,transform=SimpleNamespace(active_values=torch.ones(70,dtype=torch.bool),score_eligible=eligible))
        p=diagnostic_packet(64)
        for name in ('Fcov','F2_wide','F4'):
            m=models[name].eval()
            with torch.no_grad():reference=torch.stack([m(q) for q in prefixes(p)])
            result=torch.stack(list(evaluate_prefix_stream(m,prefixes(p),32)))
            torch.testing.assert_close(result,reference,atol=1e-6,rtol=1e-6)
