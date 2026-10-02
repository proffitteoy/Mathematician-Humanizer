"""Reconstructed synthetic-only implementation regressions; no corpus access."""
import dataclasses,itertools,math,tempfile,unittest
from pathlib import Path
import torch
from experimental_natural.schema import *
from experimental_natural.transforms import *
from experimental_natural.models import *
from experimental_natural.objectives import *
from experimental_natural.train import FitLedger,score_model

def tiny_catalog():return Catalog(('a','b','c','length'),('A','A','B','structural_length'),('raw_then_train_zscore',)*4,(3,),())
def record(q='q0',answer='a0',arm='human',split='train',source='baike',n=4,offset=0.,values=None,component=None):
    if values is None:values=torch.tensor([[1.,2.,3.,4.],[2.,4.,1.,5.],[4.,1.,2.,6.],[3.,3.,4.,7.]])[:n]+offset
    return NaturalMeasurementRecord(q,answer,component or q,source,split,arm,values.float(),torch.ones_like(values)*5,
        {'quality_claim':'candidate_unvalidated','comparison_eligible':False,'missing_reason':'synthetic_fixture'},kind='synthetic')
def fixture():
    rs=[record(),record(arm='chatgpt',offset=.5),record(q='q1',answer='a1',offset=1),record(q='q1',answer='a1',arm='chatgpt',offset=1.5)]
    c=tiny_catalog();return c,rs,fit_transform(rs,c,min_components=1)

class FirewallTests(unittest.TestCase):
    def setUp(self):self.c,self.rs,self.tr=fixture();self.p=make_model_packet(self.rs[0],2,self.tr)
    def test_exact_catalog(self):
        c=Catalog.from_contract();self.assertEqual(len(c.ids),70);self.assertEqual(len(c.all_71_ids),71);self.assertNotIn('zh:lexical.content_overlap',c.ids)
    def test_future_values_masks_and_final_lengths_hidden(self):
        old=self.rs[0];v=torch.cat([old.values[:2],torch.full((20,4),float('nan'))]);new=dataclasses.replace(old,values=v,opportunity=torch.full_like(v,float('nan')));new.opportunity[:2]=old.opportunity[:2]
        p=make_model_packet(new,2,self.tr)
        for f in dataclasses.fields(PrefixPacket):
            if f.name=='prefix_unit_count':self.assertEqual(p.prefix_unit_count,2)
            else:self.assertTrue(torch.equal(getattr(p,f.name),getattr(self.p,f.name)))
        model=PrefixModel('F4',InputView(4,(0,1,2,3)),4);self.assertTrue(torch.equal(model(p),model(self.p)))
    def test_labels_hashes_and_source_cannot_enter_forward(self):
        for key in ('source','arm','question_id','hash','source_span','final_sentence_count','future_masks','padding'):
            d=dataclasses.asdict(self.p);d[key]=99
            with self.assertRaises(ValueError):PrefixPacket.from_mapping(d)
        with self.assertRaises(TypeError):PrefixModel('F1',InputView(4,(0,1,2,3)),4)(self.rs[0])
    def test_slice_backing_storage_rejected(self):
        with self.assertRaises(ValueError):dataclasses.replace(self.p,prefix_values=torch.ones(30,4)[:2]).validate(4)
    def test_padding_rejected(self):
        with self.assertRaises(ValueError):dataclasses.replace(self.p,prefix_unit_count=1).validate(4)
    def test_unknown_opportunities_remain_unknown(self):
        p=make_model_packet(dataclasses.replace(self.rs[0],opportunity=torch.full((4,4),float('nan'))),2,self.tr)
        self.assertFalse(p.prefix_opportunity_known.any());self.assertEqual(float(p.prefix_opportunity.sum()),0)
    def test_unaudited_zero_rejected(self):
        with self.assertRaises(ValueError):dataclasses.replace(record(values=torch.zeros(2,4)),opportunity=torch.zeros(2,4))
    def test_missing_never_becomes_observed_zero(self):
        v=self.rs[0].values.clone();v[0,0]=float('nan');r=dataclasses.replace(self.rs[0],values=v);p=make_model_packet(r,2,self.tr)
        self.assertFalse(p.prefix_observed[0,0]);self.assertEqual(float(p.prefix_values[0,0]),0);self.assertEqual(r.measurement_audit['missing_reason'],'synthetic_fixture')
    def test_test_and_davinci_fit_rejected(self):
        for bad in (dataclasses.replace(self.rs[0],split='test'),dataclasses.replace(self.rs[0],arm='davinci')):
            with self.assertRaises(ValueError):fit_transform([bad],self.c,min_components=1)
    def test_natural_fitting_needs_approval(self):
        with self.assertRaises(PermissionError):fit_transform([dataclasses.replace(self.rs[0],kind='natural')],self.c)
    def test_source_scope_rejected(self):
        with self.assertRaises(ValueError):fit_transform(self.rs,self.c,source='web',min_components=1)
    def test_component_split_leak(self):
        with self.assertRaises(ValueError):validate_cohort([self.rs[0],record(q='other',component='q0',split='dev')])
    def test_duplicate_human_rejected(self):
        with self.assertRaises(ValueError):validate_cohort([self.rs[0],self.rs[0]])
    def test_exposed_test_rejected(self):
        with self.assertRaises(ValueError):dataclasses.replace(self.rs[0],split='test',exposed=True)
    def test_no_retrospective_bag_in_prefix_api(self):
        with self.assertRaises(NotImplementedError):make_model_packet(self.rs[0],2,self.tr,'retrospective_bag')

class TransformTests(unittest.TestCase):
    def test_hierarchical_unit_mass(self):
        rs=[record(),record(arm='chatgpt',n=2),record(answer='a1'),record(answer='a1',arm='chatgpt'),record(q='q1'),record(q='q1',arm='chatgpt')];w=hierarchical_unit_weights(rs)
        self.assertAlmostEqual(sum(float(x.sum()) for x in w),1);self.assertAlmostEqual(float(w[0].sum()),.125);self.assertAlmostEqual(float(w[4].sum()),.25)
    def test_blank_arm_keeps_fixed_half_slot(self):
        rs=[record(values=torch.full((2,4),10.)),record(arm='chatgpt',values=torch.empty(0,4)),record(q='q1',values=torch.zeros(2,4)),record(q='q1',arm='chatgpt',values=torch.zeros(2,4))]
        w=hierarchical_unit_weights(rs);self.assertAlmostEqual(float(w[0].sum()),.25);self.assertEqual(float(w[1].sum()),0);self.assertAlmostEqual(sum(float(x.sum()) for x in w),.75)
        tr=fit_transform(rs,tiny_catalog(),min_components=1);self.assertTrue(torch.allclose(tr.mean,torch.full((4,),10/3,dtype=torch.float64)))
    def test_constant_unseen_variation_is_frozen_zero(self):
        tr=fit_transform([record(values=torch.tensor([[2.,1.,float('nan'),4.],[2.,3.,float('nan'),7.]]))],tiny_catalog(),min_components=1)
        x=tr.apply(torch.tensor([100.,5.,9.,8.]));self.assertEqual(float(x[0]),0);self.assertEqual(float(x[2]),0);self.assertFalse(tr.score_eligible[0]);self.assertFalse(tr.score_eligible[2])
    def test_per_component_not_rows_eligibility(self):
        tr=fit_transform([record(values=torch.rand(300,4)+1)],tiny_catalog(),min_components=2);self.assertFalse(tr.score_eligible.any());self.assertEqual(tr.component_support,(1,1,1,1))
    def test_no_test_clipping(self):
        _,_,tr=fixture();self.assertGreater(float(tr.apply(torch.ones(4)*1000).max()),100)
    def test_roundtrip_transform(self):
        _,rs,tr=fixture();self.assertTrue(torch.equal(FrozenTransform.from_dict(tr.to_dict()).apply(rs[0].values),tr.apply(rs[0].values)))

class ArchitectureTests(unittest.TestCase):
    def setUp(self):self.c,self.rs,self.tr=fixture();self.p=make_model_packet(self.rs[0],4,self.tr);self.view=InputView(4,(0,1,2,3))
    def test_registered_summary_widths(self):
        v=InputView(70,tuple(range(70)));self.assertEqual(v.summary_size,15331);self.assertEqual(v.summary_size+v.pairs,17816)
    def test_set_and_moment_permutation_invariance(self):
        q=permute_packet(self.p,torch.tensor([3,0,2,1]))
        for name in ('F1','Fcov','F2'):
            m=PrefixModel(name,self.view,4);self.assertTrue(torch.allclose(m(self.p),m(q),atol=1e-6,rtol=1e-6),name)
    def test_order_model_can_change(self):
        torch.manual_seed(44);m=PrefixModel('F4',self.view,4);self.assertFalse(torch.allclose(m(self.p),m(permute_packet(self.p,torch.tensor([3,2,1,0]))),atol=1e-8))
    def test_batch_invariance(self):
        for name in ('F1','Fcov','F2','F3','F4'):
            m=PrefixModel(name,self.view,4);self.assertTrue(torch.equal(m(self.p),m.forward_batch([make_model_packet(self.rs[1],1,self.tr),self.p])[1]))
    def test_joint_pair_means_and_covariance(self):
        raw=torch.tensor([[1.,10.],[3.,float('nan')],[5.,30.]]);p=PrefixPacket(torch.nan_to_num(raw),~torch.isnan(raw),torch.ones_like(raw),torch.ones_like(raw,dtype=torch.bool),3)
        s=InputView(2,(0,1)).summarize(p,True)
        self.assertAlmostEqual(float(s[30]),4);self.assertAlmostEqual(float(s[31]),40);self.assertAlmostEqual(float(s[32]),200);self.assertEqual(float(s[25]),3);self.assertEqual(float(s[28]),20)
    def test_centered_covariance_stable_for_huge_constant_prefix(self):
        for value,n in ((1e10,100),(1e15,7)):
            raw=torch.full((n,2),value);p=PrefixPacket(raw,torch.ones_like(raw,dtype=torch.bool),torch.ones_like(raw),torch.ones_like(raw,dtype=torch.bool),n)
            v=InputView(2,(0,1));s=v.summarize(p,True);self.assertTrue(torch.equal(s[v.summary_size-1:v.summary_size+2],torch.zeros(3)))
    def test_covariance_missing_one_joint_observation(self):
        s=self.view.summarize(make_model_packet(self.rs[0],1,self.tr),True);start=self.view.summary_size-1;self.assertTrue(torch.equal(s[start:start+self.view.pairs],torch.zeros(self.view.pairs)))
    def test_masks_only_remove_value_paths(self):
        p=dataclasses.replace(self.p,prefix_values=self.p.prefix_values*77+3)
        for mode in ('mask_opportunity','pure_mask'):
            m=PrefixModel('F4',InputView(4,(0,1,2,3),mode),4);self.assertTrue(torch.equal(m(self.p),m(p)))
    def test_pure_mask_removes_opportunity_magnitude(self):
        p=dataclasses.replace(self.p,prefix_opportunity=self.p.prefix_opportunity*99);m=PrefixModel('F4',InputView(4,(0,1,2,3),'pure_mask'),4);self.assertTrue(torch.equal(m(self.p),m(p)))
    def test_length_only_removes_other_values_masks_and_opportunities(self):
        p=dataclasses.replace(self.p,prefix_values=self.p.prefix_values.clone(),prefix_observed=self.p.prefix_observed.clone(),prefix_opportunity=self.p.prefix_opportunity*3);p.prefix_values[:,:3]=0;p.prefix_observed[:,:3]=False
        m=PrefixModel('F4',InputView(4,(3,),'length'),4);self.assertTrue(torch.equal(m(self.p),m(p)))
    def test_family_ablation_removes_every_path(self):
        p=dataclasses.replace(self.p,**{k:getattr(self.p,k).clone() for k in ('prefix_values','prefix_observed','prefix_opportunity','prefix_opportunity_known')})
        p.prefix_values[:,:2]=0;p.prefix_observed[:,:2]=False;p.prefix_opportunity[:,:2]=0;p.prefix_opportunity_known[:,:2]=False
        for name in ('F1','Fcov','F2','F4'):
            m=PrefixModel(name,InputView(4,(2,3)),4);self.assertTrue(torch.equal(m(self.p),m(p)))
    def test_independent_family_cannot_see_other_values(self):
        m=IndependentFamilies(self.c,4);p=dataclasses.replace(self.p,prefix_values=self.p.prefix_values.clone());p.prefix_values[:,2]*=9;self.assertTrue(torch.equal(m(self.p)[:2],m(p)[:2]))
    def test_capacity_match_uses_all_parameters(self):
        target=parameter_count(PrefixModel('F4',self.view,4));m,meta=capacity_match('F2',self.view,4,[target]);self.assertLessEqual(meta['max_relative_mismatch'],.1);m(self.p).square().sum().backward()
        self.assertTrue(all(p.grad is not None and torch.count_nonzero(p.grad)>0 for p in m.parameters()));self.assertEqual(meta['trainable_parameters'],parameter_count(m))
    def test_independent_random_order_target_expectation(self):
        m=PrefixModel('F4',self.view,4)
        for order in itertools.permutations(range(4)):
            p=m(permute_packet(self.p,torch.tensor(order))).detach();risk=sum(float(((p-s)**2).mean()) for s in (-1.,1.))/2
            self.assertAlmostEqual(risk,1+float((p*p).mean()),places=6)

class ObjectiveTests(unittest.TestCase):
    def setUp(self):self.c,self.rs,self.tr=fixture()
    def test_family_balance_hand_calculation(self):
        loss,_=family_loss(torch.tensor([1.,1.,3.,5.]),torch.zeros(4),torch.ones(4,dtype=torch.bool),self.c.families);self.assertAlmostEqual(float(loss),(1+9+25)/3,places=6)
    def test_joint_answer_weighting_and_lengths(self):
        rs=[record(),record(arm='chatgpt',n=2),record(answer='a1'),record(answer='a1',arm='chatgpt'),record(q='q1'),record(q='q1',arm='chatgpt')];p=BalancedPlan(rs,self.tr);w=p.exact_weights()
        self.assertAlmostEqual(sum(w.values()),1)
        for i,expected in ((0,.125),(1,.125),(4,.25)):self.assertAlmostEqual(sum(v for (j,t),v in w.items() if i==j),expected)
        self.assertEqual(len(list(p.draws(1701))),2)
    def test_singletons_remain_but_not_transitions(self):
        p=BalancedPlan(self.rs+[record(q='single',n=1),record(q='single',n=1,arm='chatgpt')],self.tr);self.assertEqual(len(p.records),6);self.assertEqual(len(p.questions),2)
        self.assertEqual(supported_positions(record(n=2),self.tr),(1,));self.assertEqual(supported_positions(record(n=2),self.tr,2),())
    def test_numeric_failure_not_deleted(self):
        with self.assertRaises(FloatingPointError):family_loss(torch.full((4,),float('nan')),torch.zeros(4),torch.ones(4,dtype=torch.bool),self.c.families)
    def test_seed_omission_rejected(self):
        with self.assertRaises(ValueError):paired_seed_comparison({1701:[]},{1701:[]})
    def test_aggregate_ratio_not_mean_document_percentage(self):
        def row(q,a,x):return DocumentScore(q,'a',q,'baike',a,x,1,{},{},2,4)
        b=[row(q,a,x) for q,x in [('q0',1),('q1',9)] for a in ('human','chatgpt')];n=[row(q,a,x) for q,x in [('q0',.5),('q1',9)] for a in ('human','chatgpt')]
        r=paired_seed_comparison({s:b for s in (1701,1702,1703)},{s:n for s in (1701,1702,1703)},replicates=30);self.assertAlmostEqual(r['relative_gain'],.05);self.assertEqual(r['questions'],2)
    def test_failed_attempts_count_and_block_freeze(self):
        with tempfile.TemporaryDirectory() as d:
            l=FitLedger(Path(d)/'ledger.jsonl',max_fits=1);l.begin('x',{});l.append({'event':'failed','run_id':'x','cpu_seconds':0})
            with self.assertRaises(RuntimeError):l.begin('y',{})
            with self.assertRaises(ValueError):l.assert_complete(['x'])
    def test_no_row_omission_or_duplicates(self):
        rows=score_model(TrainingMean(4),BalancedPlan(self.rs,self.tr))
        with self.assertRaises(ValueError):aggregate_document_scores(rows+[rows[0]])
        with self.assertRaises(ValueError):paired_seed_comparison({s:rows for s in (1701,1702,1703)},{s:rows[:-1] for s in (1701,1702,1703)})

class RevisedAuditTests(unittest.TestCase):
    def test_question_maps_to_one_component_and_source(self):
        for bad in (record(answer='b',component='different'),record(answer='b',source='web')):
            with self.assertRaises(ValueError):validate_cohort([record(),bad])
    def test_frozen_value_paths_and_unscored_outputs_have_no_parameters(self):
        from experimental_natural.plan import build_ladder
        c,rs,tr=fixture();tr=dataclasses.replace(tr,active_values=torch.tensor([True,False,True,True]),score_eligible=torch.tensor([True,False,False,True]))
        models,_=build_ladder(c,transform=tr);m=models['F4'];self.assertEqual(m.head[-1].out_features,2);self.assertNotIn(1,m.view.active_local);self.assertEqual(len(m.view.active_pairs),6)
        out=m(make_model_packet(rs[0],4,tr));self.assertEqual(float(out[1]),0);self.assertEqual(float(out[2]),0)
        self.assertNotIn('B',IndependentFamilies(c,4,target_indices=(0,3),active_value_indices=(0,2,3)).names)
    def test_interrupted_fit_blocks_restart_and_preserves_cpu(self):
        with tempfile.TemporaryDirectory() as d:
            l=FitLedger(Path(d)/'ledger.jsonl');l.begin('x',{});l.append({'event':'epoch','run_id':'x','cpu_seconds_current_fit':17});self.assertEqual(l.consumed_cpu(),17)
            with self.assertRaises(RuntimeError):l.begin('y',{})
    def test_direct_structural_count_zero_has_no_fake_opportunity(self):
        r=record(values=torch.tensor([[1.,2.,3.,0.]]));o=r.opportunity.clone();o[:,3]=float('nan');r=dataclasses.replace(r,opportunity=o,direct_count_indices=(3,))
        self.assertEqual(float(r.values[0,3]),0);self.assertTrue(torch.isnan(r.opportunity[0,3]))
    def test_public_export_rejects_private_records(self):
        from experimental_natural.report import validate_public
        with self.assertRaises(ValueError):validate_public(record())
        for k in ('raw_text','question','source_span','cache_sha256','predictions'):
            with self.assertRaises(ValueError):validate_public({'support':{k:1}})
    def test_72_run_grid(self):
        from experimental_natural.plan import registered_run_grid
        self.assertEqual(len(registered_run_grid()),72)

class CacheAdapterTests(unittest.TestCase):
    def payload(self):
        from experimental_natural.cache_adapter import CacheDescriptor
        c=Catalog.from_contract();d=CacheDescriptor('/not/read','a'*64,'q','a','c','baike','train','human','b'*64);rows=[];units=[]
        for t in range(2):
            measures={k:{'value':1.,'opportunities':4,'missing_reason':None,'status':'observed','comparison_eligible':False} for k in c.all_71_ids}
            rows.append({'source_sentence_index':t,'source_span':[t*3,t*3+3],'parse_status':'success','parse_reason':None,'vector':{'channel_ids':list(c.all_71_ids)},'measurements':measures})
            units.append({'source_sentence_index':t,'source_span':[t*3,t*3+3],c.ids[-2]:3,c.ids[-1]:0})
        return {'cohort':{'question_family_id':'q','pair_id':'a','component_id':'c','source':'baike','split':'train','arm':'human'},'protocol_sha256':'b'*64,
            'history_channel_ids_audit_only':['zh:lexical.content_overlap','zh:lexical.trigram_reuse','zh:syntax.initial_pos_reuse'],
            'information_mode':'supplied_complete_unit_annotation_sequence_not_certified_live_prefix','structural_units':units,'source_failure':None,
            'bundle':{'measurement_status':'candidate_unvalidated','empirical_model_admitted':False,'learned_contract_compatible':False,'target':{'sequence':rows}}},d,c
    def test_adapter_synthetic_exact_schema_and_no_structural_opportunity(self):
        from experimental_natural.cache_adapter import from_cache_payload
        x,d,c=self.payload();r=from_cache_payload(x,d,c,kind='synthetic');self.assertEqual(r.values.shape,(2,70));self.assertTrue(torch.isnan(r.opportunity[:,-2:]).all());self.assertEqual(float(r.values[0,-1]),0);self.assertFalse(r.measurement_audit['comparison_eligible'])
    def test_adapter_missing_sensor_and_unknown_opportunity_stay_missing(self):
        from experimental_natural.cache_adapter import from_cache_payload
        x,d,c=self.payload();x['bundle']['target']['sequence'][0]['measurements'][c.ids[0]].update(value=None,opportunities=None,missing_reason='alignment_failure',status='unavailable')
        r=from_cache_payload(x,d,c,kind='synthetic');self.assertTrue(torch.isnan(r.values[0,0]));self.assertTrue(torch.isnan(r.opportunity[0,0]));self.assertEqual(r.measurement_audit['missing_reason_counts']['alignment_failure'],1)
    def test_test_and_davinci_blocked_before_file_open(self):
        from experimental_natural.cache_adapter import load_train_dev_cache
        from unittest.mock import patch
        x,d,c=self.payload()
        for bad in (dataclasses.replace(d,split='test'),dataclasses.replace(d,arm='davinci')):
            with patch('pathlib.Path.read_bytes',side_effect=AssertionError('must not read')):
                with self.assertRaises(PermissionError):load_train_dev_cache(bad,c)
    def test_frozen_identity_mismatch_rejected(self):
        from experimental_natural.cache_adapter import from_cache_payload
        x,d,c=self.payload();x['cohort']['component_id']='bad'
        with self.assertRaises(ValueError):from_cache_payload(x,d,c,kind='synthetic')
    def test_whole_source_failure_retains_lengths_missing_sensors(self):
        from experimental_natural.cache_adapter import from_cache_payload
        x,d,c=self.payload();x['bundle']=None;x['source_failure']={'reason':'source_resource_limit'}
        for u in x['structural_units']:u[c.ids[-1]]=None
        r=from_cache_payload(x,d,c,kind='synthetic');self.assertTrue(torch.isnan(r.values[:,:68]).all());self.assertEqual(float(r.values[0,-2]),3)

if __name__=='__main__':torch.set_num_threads(2);unittest.main(verbosity=2)
