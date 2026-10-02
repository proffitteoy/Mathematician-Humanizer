"""Synthetic boundary tests. Never open natural source data or model assets."""
import copy,io,json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pilot_core import (select_components,read_selected,aligned_prefix_pair,mst_energy,typed_values,SEEDS,digest,serial,slope_schedules,aggregate_measurements)
from pilot_evaluation import (fit_preprocessing,transform,design,fit_train,score_dev,validate_records)


def metadata():
    return [{'component_id':f'{s}-{d}-{i}', 'pair_id':f'{s}-{d}-{i}-p','split':s,'source':d,'fit_eligible_arms':['human','chatgpt']}
        for s in ('train','dev','test') for d in ('baike','web') for i in range(20)]


class CharTokenizer:
    def __call__(self,text,**kwargs):
        # Spaces are ignored and Unicode offsets remain Python codepoints.
        out={'input_ids':[ord(c) for c in text if not c.isspace()]}
        if kwargs.get('return_offsets_mapping'):out['offset_mapping']=[(i,i+1) for i,c in enumerate(text) if not c.isspace()]
        return out


class TrackedRaw(io.RawIOBase):
    name='qazh_chatgpt.jsonl'
    def __init__(self,data):
        self.data=data;self.pos=0;self.extents=[]
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,pos,whence=0):
        self.pos=pos if whence==0 else self.pos+pos if whence==1 else len(self.data)+pos
        return self.pos
    def read(self,size=-1):
        stop=len(self.data) if size<0 else min(len(self.data),self.pos+size)
        self.extents.append((self.pos,stop));data=self.data[self.pos:stop];self.pos=stop;return data
    def readinto(self,buffer):
        data=self.read(len(buffer));buffer[:len(data)]=data;return len(data)


class NoRead:
    name='qazh_chatgpt.jsonl'
    def seek(self,*a):raise AssertionError('Forbidden seek occurred')
    def read(self,*a):raise AssertionError('Forbidden read occurred')


def synthetic_rows(split):
    result=[];count=16 if split=='train' else 8
    for source in ('baike','web'):
        for i in range(count):
            for arm in ('human','chatgpt'):
                vals=[float(i%3)/5]*68;vals[2]=None;vals[3]=0.
                slope=.83+(.01 if arm=='human' else 0)+i/10000
                means=(slope+np.linspace(-.001,.001,20)).tolist()
                result.append({'component_id':f'{split}-{source}-{i}','pair_id':f'{split}-{source}-{i}',
                    'source':source,'split':split,'arm':arm,'window_characters':80,'lexical_tokens':40,
                    'content_tokens':80,'unknown_token_rate':0.,
                    'linguistic':{'values':vals,'observed':[v is not None for v in vals]},
                    'topology':{'available':True,'seed_ids':list(SEEDS),'schedule_means':means,'mean':slope,'sd':.001}})
    return result


class SelectionTests(unittest.TestCase):
    def test_exact_balanced_counts(self):
        chosen,audit=select_components(metadata())
        self.assertEqual(len(chosen),48)
        self.assertEqual(audit['selected_counts'],{'train|baike':16,'train|web':16,'dev|baike':8,'dev|web':8})
        self.assertNotIn('test',{r['split'] for r in chosen})
    def test_order_invariance(self):
        a,_=select_components(metadata());b,_=select_components(metadata()[::-1]);self.assertEqual(a,b)
    def test_one_representative_per_component(self):
        rows=metadata();extra=copy.deepcopy(rows[0]);extra['pair_id']='zzz';rows.append(extra)
        chosen,_=select_components(rows)
        self.assertEqual(len({r['component_id'] for r in chosen}),48)
        self.assertNotIn('zzz',{r['pair_id'] for r in chosen})
    def test_cross_split_component_rejected(self):
        rows=metadata();x=copy.deepcopy(rows[0]);x['split']='test';rows.append(x)
        with self.assertRaises(ValueError):select_components(rows)
    def test_source_conflict_exclusion_before_selection(self):
        rows=metadata();x=copy.deepcopy(rows[0]);x['source']='web';rows.append(x)
        _,audit=select_components(rows);self.assertEqual(audit['conflicting_source_components_excluded'],1)
    def test_test_rejected_before_seek(self):
        r=metadata()[-1]
        with self.assertRaises(PermissionError):read_selected(NoRead(),r,{r['pair_id']},'train')
    def test_unselected_rejected_before_seek(self):
        with self.assertRaises(PermissionError):read_selected(NoRead(),metadata()[0],set(),'train')
    def test_dev_profile_access_rejected(self):
        r=[r for r in metadata() if r['split']=='dev'][0]
        with self.assertRaises(PermissionError):read_selected(NoRead(),r,{r['pair_id']},'train')
    def test_davinci_file_rejected_before_seek(self):
        r=metadata()[0];r['raw_rows']={'chatgpt':{'file':'qazh_davinci.jsonl','offset_bytes':0,'length_bytes':20}}
        with self.assertRaises(PermissionError):read_selected(NoRead(),r,{r['pair_id']},'train')
    def test_valid_selected_exact_bytes(self):
        raw={'model':'chatgpt','source':'web','source_ID':7,'prompt':'问题','human_text':'人类样例','machine_text':'机器样例'}
        family=json.dumps(['web','int',7],ensure_ascii=False,separators=(',',':'))
        pair=digest(json.dumps([family,raw['prompt'],raw['human_text']],ensure_ascii=False,separators=(',',':')))
        data=serial(raw);stream=TrackedRaw(b'padding'+data+b'closed')
        row={'split':'train','source':'web','source_ID':7,'pair_id':pair,'question_family_id':family,'prompt_sha256':digest('问题'),
            'fit_eligible_arms':['human','chatgpt'],'raw_rows':{'chatgpt':{'file':'qazh_chatgpt.jsonl','offset_bytes':7,'length_bytes':len(data)}},
            'arms':{a:{'original_text_sha256':digest(raw[k]),'chars':len(raw[k])} for a,k in [('human','human_text'),('chatgpt','machine_text')]}}
        self.assertEqual(read_selected(stream,row,{pair},'train'),raw);self.assertEqual(stream.tell(),7+len(data))
        self.assertEqual(stream.extents,[(7,7+len(data))])
        raw_tracker=TrackedRaw(b'padding'+data+b'closed')
        buffered=io.BufferedReader(raw_tracker)
        with self.assertRaises(PermissionError):read_selected(buffered,row,{pair},'train')
        self.assertEqual(raw_tracker.extents,[])
        # Integration check uses a real unbuffered FileIO as the runner does.
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'qazh_chatgpt.jsonl';path.write_bytes(b'padding'+data+b'closed')
            with path.open('rb',buffering=0) as raw_file:
                self.assertEqual(read_selected(raw_file,row,{pair},'train'),raw)
                self.assertEqual(raw_file.tell(),7+len(data))


class AlignmentTests(unittest.TestCase):
    def test_unicode_offsets_and_equal_lengths(self):
        r=aligned_prefix_pair('  中文😀。还有后文','简体 测试',CharTokenizer())
        self.assertEqual(r['n_tokens'],4)
        self.assertEqual(r['windows'][0]['text'],'  中文😀。')
        self.assertEqual(r['windows'][1]['text'],'简体 测试')
    def test_maximum_256(self):
        r=aligned_prefix_pair('中'*300,'文'*280,CharTokenizer());self.assertEqual(r['n_tokens'],256)
    def test_blank_pair_availability(self):
        self.assertFalse(aligned_prefix_pair('', '中文',CharTokenizer())['available'])
    def test_future_changes_do_not_change_encoded_prefix(self):
        a=aligned_prefix_pair('中'*256+'后文','文'*256,CharTokenizer())
        b=aligned_prefix_pair('中'*256+'不同未来','文'*256,CharTokenizer())
        self.assertEqual(a['windows'],b['windows'])
    def test_wordpiece_boundary_reduction(self):
        class T:
            def __call__(self,text,**kwargs):
                if text=='abc':out={'input_ids':[1,2],'offset_mapping':[(0,1),(1,3)]}
                elif text=='a':out={'input_ids':[8],'offset_mapping':[(0,1)]}
                else:out={'input_ids':[3],'offset_mapping':[(0,len(text))]}
                return out
        self.assertFalse(aligned_prefix_pair('abc','x',T())['available'])
    def test_invalid_offset_rejected(self):
        def bad(text,**kwargs):return {'input_ids':[1],'offset_mapping':[(0,999)]}
        with self.assertRaises(ValueError):aligned_prefix_pair('中','文',bad)


class NumericTests(unittest.TestCase):
    def test_zero_distance_mst_edges(self):
        self.assertEqual(mst_energy([[0,0,2],[0,0,2],[2,2,0]]),2)
    def test_mst_known_square(self):
        x=np.array([[0,0],[1,0],[0,1],[1,1]])
        d=np.sqrt(((x[:,None]-x[None,:])**2).sum(2));self.assertEqual(mst_energy(d),3)
    def test_negative_distance_rejected(self):
        with self.assertRaises(ValueError):mst_energy([[0,-1],[-1,0]])
    def test_typed_null_preserved(self):
        channels=[f'c{i}' for i in range(68)]
        measures={c:{'value':None,'opportunities':None,'missing_reason':'no_parse','status':'unavailable','comparison_eligible':False} for c in channels}
        r=typed_values(measures,channels);self.assertEqual(r['values'],[None]*68);self.assertEqual(r['observed'],[False]*68)
    def test_zero_requires_real_opportunity(self):
        channels=[f'c{i}' for i in range(68)]
        measures={c:{'value':0,'opportunities':2,'missing_reason':None,'status':'zero_observed','comparison_eligible':False} for c in channels}
        self.assertEqual(typed_values(measures,channels)['values'],[0]*68)
        measures['c0']['opportunities']=0
        with self.assertRaises(ValueError):typed_values(measures,channels)
    def test_dev_preprocessing_forbidden(self):
        with self.assertRaises(PermissionError):fit_preprocessing([[1.],[2.]],'dev')
    def test_train_median_no_dev_recalculation(self):
        p=fit_preprocessing([[1.,np.nan],[3.,np.nan]],'train')
        before=copy.deepcopy(p);x=transform([[100000.,999.]],p)
        self.assertEqual(p,before);self.assertEqual(p['median'],[2.,0.]);self.assertEqual(x[0,1],0)
    def test_missing_indicator_and_observed_zero_distinct(self):
        p=fit_preprocessing([[0.],[np.nan],[2.]],'train')
        x=transform([[0.],[np.nan]],p);self.assertNotEqual(x[0,1],x[1,1])
    def test_pairwise_topology_missing(self):
        rows=synthetic_rows('train');rows[0]['topology']={'available':False,'reason':'short'}
        x=design(rows,'baseline_slope');self.assertTrue(np.isnan(x[0,-1]));self.assertTrue(np.isnan(x[1,-1]))
    def test_no_training_on_dev(self):
        with self.assertRaises(PermissionError):fit_train(synthetic_rows('dev'))
    def test_train_dev_component_leak_rejected(self):
        fit=fit_train(synthetic_rows('train'));dev=synthetic_rows('dev');dev[0]['component_id']=fit['train_components'][0];dev[1]['component_id']=fit['train_components'][0]
        with self.assertRaises(ValueError):score_dev(dev,fit)
    def test_full_synthetic_workflow_aggregate_only(self):
        fit=fit_train(synthetic_rows('train'));r=score_dev(synthetic_rows('dev'),fit)
        self.assertEqual(r['status'],'development_evidence_not_independent_validation');self.assertEqual(len(r['numerical_sensitivity']['gains']),20)
        self.assertNotIn('dev-baike-0',json.dumps(r));self.assertNotIn('coefficients',json.dumps(r))


class CoverageTests(unittest.TestCase):
    def records(self):
        rows=synthetic_rows('train')
        for r in rows:
            text='中'*80;r.update(alignment={'available':True},alignment_verified=True,window_text=text,window_sha256=digest(text),linguistic_input_sha256=digest(text),encoded_input_ids=[101]+[1]*80+[102],encoded_special_tokens_mask=[1]+[0]*80+[1],aligned_content_ids=[1]*80,han_characters=80,repeated_vector_fraction=0.1)
            t=r['topology'];t['rerun_slopes']=[[x]*3 for x in t['schedule_means']];t['mc_se']=t['sd']/np.sqrt(20);t['grid']=[20,30,40,50,60,70,80]
        return rows
    def test_split_source_arm_coverage_and_confounds(self):
        result=aggregate_measurements(self.records(),'train','selection')
        self.assertEqual(len(result['groups']),4)
        self.assertEqual(result['paired_coverage']['train|baike']['finite_topology_pairs'],16)
        cell=result['groups']['train|web|human']
        self.assertEqual(cell['token_count']['mean'],80);self.assertEqual(cell['han_count']['mean'],80)
        self.assertAlmostEqual(cell['repeated_vector_fraction']['mean'],.1)
        self.assertNotIn('window_text',json.dumps(result))
    def test_pair_coverage_tracks_unavailable_arm(self):
        rows=self.records();rows[0]['topology']={'available':False,'reason':'synthetic_short'}
        r=aggregate_measurements(rows,'train','selection')
        self.assertEqual(r['paired_coverage']['train|baike']['finite_topology_pairs'],15)
        self.assertFalse(r['all_topology_finite'])
    def test_alignment_digest_corruption_rejected(self):
        rows=self.records();rows[0]['linguistic_input_sha256']='0'*64
        with self.assertRaises(ValueError):aggregate_measurements(rows,'train','selection')
    def test_tiny_profile_confounds_suppressed(self):
        rows=self.records()[:4]
        r=aggregate_measurements(rows,'profile','selection')
        self.assertEqual(r['groups']['train|baike|human']['token_count']['numeric_summary'],'suppressed_below_five')


class EstimatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cloud=np.random.default_rng(1729).normal(size=(50,3))
        cls.estimate=slope_schedules(cls.cloud)
    def test_registered_estimator_finite_and_replayable(self):
        r=self.estimate;self.assertTrue(r['available']);self.assertEqual(r['seed_ids'],list(SEEDS))
        energy=np.asarray(r['mean_MST_energies_by_schedule_rerun_scale']);x=np.log(r['grid']);xc=x-x.mean()
        replay=((np.log(energy)-np.log(energy).mean(-1,keepdims=True))*xc).sum(-1)/(xc@xc)
        np.testing.assert_allclose(replay,r['rerun_slopes'],atol=1e-12)
    def test_estimator_scale_translation_invariance(self):
        altered=slope_schedules(self.cloud*3+10)
        np.testing.assert_allclose(altered['rerun_slopes'],self.estimate['rerun_slopes'],atol=1e-10)
    def test_degenerate_cloud_explicit_missing(self):
        self.assertFalse(slope_schedules(np.zeros((50,3)))['available'])
        self.assertFalse(slope_schedules(np.ones((49,3)))['available'])


if __name__=='__main__':unittest.main(verbosity=2)
