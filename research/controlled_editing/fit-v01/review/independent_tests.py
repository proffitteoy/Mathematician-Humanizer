"""Independent audit tests; synthetic fixtures only, no empirical GO/run/TEST reads.
Allowed sources: frozen fit package and its explicitly authorized public references.
"""
from __future__ import annotations
import ast, copy, hashlib, json, math, os, pathlib, statistics, sys, tempfile, unittest
from unittest import mock
PACKAGE=pathlib.Path('/workspace/shared/style-controlled-fit-v01')
REVIEW=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(PACKAGE))
import controller_v03 as C
import fit_wrapper as W
import labels_v02 as L
import test_fit_wrapper as F

EXPECTED_MANIFEST='1c99373b805ca12f46ecd57362b26be376cc4a1005c01009067e8aa304f4e4f7'
EXPECTED_PROTOCOL='b64fb0017677baa8ab4fb52ca17a07b92fac95b72c0cdf742fb7926dc61b0ed2'

def h(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def own_rows():
    rows=[]
    for family,classes in enumerate(((0,), (1,1), (2,2,2,2,2), (3,3,3), (0,1,2,3))):
        for i,label in enumerate(classes):
            xs=[math.sin((family+1)*(j+1)+i*.37)+label*.41+j*.03 for j in range(11)]+[7.0]
            rows.append({'id':f'audit-synthetic-{family}-{i}','family':f'audit-synthetic-family-{family}',
                'partition':'train','condition':C.CONDITIONS[label], 'meaning_verified':True,
                'realized_condition_verified':True,'features':xs})
    return rows

def own_recurrence(rows, epochs=150, lr=.05, equal_family=True):
    """Independently organized math: per-family gradient means, then family mean.
    Does not call controller scaler, softmax, scaled, or replay functions.
    """
    xs=[r['features'] for r in rows]
    center=[statistics.fmean(col) for col in zip(*xs)]
    scales=[statistics.pstdev(col) or 1. for col in zip(*xs)]
    constants=[len(set(col))==1 for col in zip(*xs)]
    xx=[[0. if constants[j] else (x[j]-center[j])/scales[j] for j in range(12)]+[1.] for x in xs]
    groups={f:[i for i,r in enumerate(rows) if r['family']==f] for f in sorted({r['family'] for r in rows})}
    weights=[[0.]*13 for _ in range(4)]
    for epoch in range(epochs):
        row_grad=[]
        for i,row in enumerate(rows):
            logits=[math.fsum(weights[k][j]*xx[i][j] for j in range(13)) for k in range(4)]
            exps=[math.exp(z-max(logits)) for z in logits]; denom=math.fsum(exps)
            target=C.CONDITIONS.index(row['condition'])
            row_grad.append([[(exps[k]/denom-(k==target))*xx[i][j] for j in range(13)] for k in range(4)])
        if equal_family:
            grad=[[statistics.fmean(statistics.fmean(row_grad[i][k][j] for i in group) for group in groups.values()) for j in range(13)] for k in range(4)]
        else:
            grad=[[statistics.fmean(row_grad[i][k][j] for i in range(len(rows))) for j in range(13)] for k in range(4)]
        weights=[[weights[k][j]-lr*grad[k][j] for j in range(13)] for k in range(4)]
    return weights, {'center':center,'scale':scales,'constant':constants,'fit_partition':'train'}

def exclude(args,predicate):
    data,a,b,_=args
    for i,row in enumerate(data['slots']):
        if predicate(row):
            row['realized_condition']=None; row['exclusion_reason']='audit_synthetic_uncertainty'
            a['reviews'][i]['mainpoint_is_real_main_claim']='uncertain'

class FrozenPackage(unittest.TestCase):
    def test_01_manifest_and_protocol_exact(self):
        self.assertEqual(h(PACKAGE/'FILE_HASHES.json'),EXPECTED_MANIFEST)
        self.assertEqual(h(PACKAGE/'protocol.json'),EXPECTED_PROTOCOL)
        self.assertEqual(W.package_hashes_ok(),EXPECTED_MANIFEST)
    def test_02_all_manifest_entries_and_dependency_hashes(self):
        manifest=json.loads((PACKAGE/'FILE_HASHES.json').read_text())
        for entry in manifest['files']:
            p=PACKAGE/entry['path']; self.assertEqual(p.stat().st_size,entry['bytes']);self.assertEqual(h(p),entry['sha256'])
        self.assertEqual(h('/workspace/shared/style-edit-controller-v02/controller.py'),manifest['frozen_dependencies']['controller_v02_sha256'])
        self.assertEqual(h('/workspace/shared/style-controlled-authoring-v02/public/labels.py'),manifest['frozen_dependencies']['public_labels_v02_sha256'])
        self.assertEqual((PACKAGE/'labels_v02.py').read_bytes(),pathlib.Path('/workspace/shared/style-controlled-authoring-v02/public/labels.py').read_bytes())
    def test_03_only_three_v03_changes(self):
        old=pathlib.Path('/workspace/shared/style-edit-controller-v02/controller.py').read_text()
        old=old.replace("VERSION='bounded-structural-edit-controller/0.2'","VERSION='bounded-structural-edit-controller/0.3'")
        old=old.replace("if not isinstance(receipt,dict) or digest(receipt) not in approved_hashes:return False", "if not isinstance(receipt,dict) or set(receipt)!={'source_sha256','candidate_sha256','decision','reviewer_profile','review_id','checks'} or digest(receipt) not in approved_hashes:return False")
        old=old.replace("all(x>0 for x in t['scale']),'checkpoint_transform_invalid')", "all(x>0 for x in t['scale']) and all(type(x) is bool for x in t['constant']),'checkpoint_transform_invalid')")
        self.assertEqual(old,(PACKAGE/'controller_v03.py').read_text())
    def test_04_orchestration_has_one_fixed_fit_and_no_edit(self):
        tree=ast.parse((PACKAGE/'fit_wrapper.py').read_text())
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        calls=[n for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='C']
        fits=[n for n in calls if n.func.attr=='fit']; self.assertEqual(len(fits),1)
        fit=fits[0]; self.assertEqual(ast.literal_eval(fit.args[1]),[])
        kw={n.arg:n.value for n in fit.keywords}
        self.assertEqual(ast.literal_eval(kw['epochs']),150);self.assertEqual(ast.literal_eval(kw['lr']),.05)
        self.assertFalse(any(n.func.attr=='edit' for n in calls))
        assign=next(n for n in ast.walk(run) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='rows' for t in n.targets))
        self.assertEqual(ast.unparse(assign.value),"verified['eligible']['train']")
    def test_05_public_limits_and_claim_boundaries(self):
        p=json.loads((PACKAGE/'protocol.json').read_text())
        self.assertEqual(p['limits'],{'max_cpus':2,'address_space_bytes':536870912,'fit_and_replay_wall_seconds':60,'controlled_artifact_bytes':33554432,'output_reservation_bytes':1048576})
        self.assertEqual(p['inference_candidates_authorized'],0)
        self.assertFalse(p['counts_towards_1280_natural_works']);self.assertFalse(p['generic_stage_complete']);self.assertFalse(p['personalization_authorized'])
    def test_06_no_empirical_artifacts_present(self):
        self.assertFalse((PACKAGE/'ROOT_GO.json').exists());self.assertFalse((PACKAGE/'run_state').exists());self.assertFalse((PACKAGE/'runs').exists())
        evidence=json.loads((PACKAGE/'synthetic-evidence.json').read_text())
        self.assertEqual(evidence['status'],'synthetic_only')
        model=C.load_checkpoint(PACKAGE/'synthetic-only.weights.json',evidence['checkpoint_file_sha256'])
        self.assertEqual(model['training']['provenance'],'synthetic_fixture')

class NumericalIndependent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=own_rows();cls.model=C.fit(cls.rows,[],provenance='synthetic_fixture',epochs=150,lr=.05)
        cls.weights,cls.transform=own_recurrence(cls.rows)
    def test_07_independent_150_step_recurrence(self):
        error=max(abs(x-y) for a,b in zip(self.model['condition_weights'],self.weights) for x,y in zip(a,b))
        self.assertLess(error,1e-12)
        self.assertTrue(any(x!=0 for row in self.model['condition_weights'] for x in row))
        for a,b in zip(self.model['transform']['center'],self.transform['center']):self.assertAlmostEqual(a,b,places=14)
    def test_08_family_weighting_differs_from_row_pooling(self):
        pooled,_=own_recurrence(self.rows,equal_family=False)
        difference=max(abs(x-y) for a,b in zip(self.weights,pooled) for x,y in zip(a,b))
        self.assertGreater(difference,.01)
    def test_09_zero_preferences_and_wrapper_replay(self):
        self.assertEqual(self.model['preference_weights'],[[0.]*13 for _ in range(4)])
        receipt=W.gradient_replay(self.rows,self.model)
        self.assertGreater(receipt['first_gradient_l2'],0);self.assertLessEqual(receipt['max_abs_weight_replay_error'],1e-12)
    def test_10_replication_inside_family_preserves_loss(self):
        rows=copy.deepcopy(self.rows);duplicates=[]
        for r in rows:
            if r['family']=='audit-synthetic-family-0':
                for i in range(7):
                    d=copy.deepcopy(r);d['id']+=f'-repeat-{i}';duplicates.append(d)
        # Scaling is row-based as specified: use the fixed original transform
        # in a separate recurrence check of the update, not a second scaler claim.
        with mock.patch.object(C,'scale_fit',return_value=copy.deepcopy(self.model['transform'])):
            model=C.fit(rows+duplicates,[],provenance='synthetic_fixture',epochs=150,lr=.05)
        self.assertLess(max(abs(x-y) for a,b in zip(model['condition_weights'],self.model['condition_weights']) for x,y in zip(a,b)),1e-12)
    def test_11_dev_rows_cannot_be_fitted(self):
        rows=copy.deepcopy(self.rows);rows[0]['partition']='dev'
        with self.assertRaisesRegex(C.ContractError,'train_rows_only'):C.fit(rows,[],provenance='synthetic_fixture')
    def test_12_model_roundtrip_and_hash_tamper(self):
        with tempfile.TemporaryDirectory(prefix='audit-synthetic-',dir=REVIEW) as temp:
            p=pathlib.Path(temp)/'synthetic.weights.json';digest=C.save_checkpoint(self.model,p)
            self.assertEqual(C.load_checkpoint(p,digest),self.model)
            with self.assertRaisesRegex(C.ContractError,'file_hash_mismatch'):C.load_checkpoint(p,'0'*64)
            with self.assertRaises(FileExistsError):C.save_checkpoint(self.model,p)
    def test_13_all_nonbool_constant_masks_rejected(self):
        for bad in (0,1,'false',None,[],{}):
            with self.subTest(value=repr(bad)),tempfile.TemporaryDirectory(prefix='audit-synthetic-',dir=REVIEW) as temp:
                model=copy.deepcopy(self.model);model['transform']['constant'][0]=bad
                p=pathlib.Path(temp)/'synthetic-invalid.json';digest=C.save_checkpoint(model,p)
                with self.assertRaisesRegex(C.ContractError,'transform_invalid'):C.load_checkpoint(p,digest)
    def test_14_receipt_six_keys_exact_even_if_hash_approved(self):
        receipt={'source_sha256':C.text_hash('synthetic source'),'candidate_sha256':C.text_hash('synthetic candidate'),'decision':'pass','reviewer_profile':'independent_preservation_review/v1','review_id':'audit-fixture-only','checks':['facts','negation','modality','quantifiers','scope']}
        self.assertTrue(C.semantic_receipt_ok('synthetic source','synthetic candidate',receipt,{C.digest(receipt)}))
        for key in ('condition','score','preference','nominal_target'):
            poisoned=dict(receipt,**{key:'audit-synthetic-extra'})
            self.assertFalse(C.semantic_receipt_ok('synthetic source','synthetic candidate',poisoned,{C.digest(poisoned)}))

class DataIndependent(unittest.TestCase):
    def test_15_support_exact_boundary_16_and_4(self):
        args=F.fixtures()
        exclude(args,lambda r:(r['partition']=='train' and int(r['family'].split('-')[-1])>=16) or (r['partition']=='dev' and int(r['family'].split('-')[-1])>=36))
        v=W.validate_data(*args,synthetic=True)
        self.assertEqual(set(v['family_support']['train'].values()),{16});self.assertEqual(set(v['family_support']['dev'].values()),{4})
        self.assertEqual(len(v['all_slots']['train']),256);self.assertEqual(len(v['all_slots']['dev']),64)
    def test_16_zero_eligible_families_remain_coverage_denominator(self):
        args=F.fixtures();exclude(args,lambda r:r['family']=='synthetic-family-0')
        v=W.validate_data(*args,synthetic=True)
        model=C.fit(v['eligible']['train'],[],provenance='synthetic_fixture',epochs=150,lr=.05)
        m=W.family_metrics(model,v['eligible']['train'],v['all_slots']['train'])
        self.assertEqual(m['eligible_families'],31);self.assertEqual(m['all_families'],32)
        self.assertEqual(m['family_macro_coverage_over_all_original_slots'],31/32)
        self.assertEqual(m['by_family']['synthetic-family-0']['eligible'],0)
        self.assertEqual(m['exact_threshold_rule']['family_macro_accuracy_on_eligible'],1.)
    def test_17_extra_review_rows_fail_instead_of_reading_originals(self):
        args=F.fixtures();extra=copy.deepcopy(args[1]['reviews'][0]);extra['review_id']='audit-extra-row';args[1]['reviews'].append(extra)
        with self.assertRaisesRegex(C.ContractError,'coverage_mismatch'):W.validate_data(*args,synthetic=True)
    def test_18_projection_disallows_original_paths_and_nonzero_or_bool_test_count(self):
        for mutate in (lambda p:p.update(original_path='/not/opened'),lambda p:p.update(test_rows_exported=1),lambda p:p.update(test_rows_exported=False)):
            args=F.fixtures();mutate(args[3]['projection_receipt'])
            with self.assertRaises(C.ContractError):W.validate_data(*args,synthetic=True)
    def test_19_review_unknown_fields_rejected(self):
        args=F.fixtures();args[1]['reviews'][0]['nominal_target']='audit-synthetic-extra'
        with self.assertRaisesRegex(ValueError,'review_schema'):W.validate_data(*args,synthetic=True)
    def test_20_validation_does_no_file_io(self):
        args=F.fixtures()
        with mock.patch('builtins.open',side_effect=AssertionError('Unexpected file access')),mock.patch.object(os,'open',side_effect=AssertionError('Unexpected file access')),mock.patch.object(pathlib.Path,'open',side_effect=AssertionError('Unexpected file access')):
            v=W.validate_data(*args,synthetic=True)
        self.assertEqual(len(v['eligible']['train']),256)
    def test_21_strict_top_level_and_slot_keys(self):
        for target in ('top','slot'):
            args=F.fixtures();obj=args[0] if target=='top' else args[0]['slots'][0];obj['template']='audit-synthetic-extra'
            with self.assertRaises(C.ContractError):W.validate_data(*args,synthetic=True)
    def test_22_family_genre_balance_enforced(self):
        args=F.fixtures()
        for r in args[0]['slots']:
            if r['family']=='synthetic-family-0':r['genre']=C.GENRES[1]
        with self.assertRaisesRegex(C.ContractError,'genre_balance'):W.validate_data(*args,synthetic=True)

class FailClosedIndependent(unittest.TestCase):
    def test_23_absent_hash_prevents_any_read(self):
        with mock.patch.object(W,'safe_bytes',side_effect=AssertionError('Unexpected read')):
            with self.assertRaisesRegex(C.ContractError,'expected_root_GO_hash'):W.read_authorized_inputs('/not/opened',None)
    def test_24_exclusive_synthetic_marker_cannot_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='audit-synthetic-',dir=REVIEW) as temp:
            p=pathlib.Path(temp)/'synthetic.lock';W.write_once(p,{'synthetic_fixture':True})
            first=p.read_bytes()
            with self.assertRaises(FileExistsError):W.write_once(p,{'synthetic_fixture':False})
            self.assertEqual(first,p.read_bytes())
    def test_25_symlink_and_file_size_rejected(self):
        with tempfile.TemporaryDirectory(prefix='audit-synthetic-',dir=REVIEW) as temp:
            p=pathlib.Path(temp)/'synthetic.txt';p.write_text('synthetic')
            with self.assertRaisesRegex(C.ContractError,'size'):W.safe_bytes(p,1)
            q=pathlib.Path(temp)/'synthetic-link';q.symlink_to(p)
            with self.assertRaisesRegex(C.ContractError,'symlink'):W.safe_bytes(q,100)
    def test_26_duplicate_nan_infinity_json_rejected(self):
        for raw in ('{"x":0,"x":1}','{"x":NaN}','{"x":Infinity}','{"x":-Infinity}'):
            with self.assertRaises(C.ContractError):W.strict_json(raw)
    def test_27_fresh_exclusive_storage_and_exact_boundary(self):
        import datetime as dt
        receipt={'schema':'controlled-artifact-budget-receipt/v1','actor':'root','measured_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'excluded_root':str(PACKAGE),'external_controlled_bytes':W.LIMIT-W.OUTPUT_RESERVE-12345,'controlled_byte_cap':W.LIMIT,'exclusive_budget_reservation':True,'reserved_output_bytes':W.OUTPUT_RESERVE,'no_other_controlled_writes_until_release':True}
        with mock.patch.object(W,'package_bytes',return_value=12345):
            self.assertEqual(W.verify_storage(receipt,{}),receipt['external_controlled_bytes'])
            receipt['external_controlled_bytes']+=1
            with self.assertRaisesRegex(C.ContractError,'cap_exceeded'):W.verify_storage(receipt,{})
        receipt['external_controlled_bytes']=0;receipt['exclusive_budget_reservation']=False
        with self.assertRaisesRegex(C.ContractError,'exclusive'):W.verify_storage(receipt,{})
    def test_28_resource_limits_are_applied_for_this_synthetic_review(self):
        import resource
        self.assertLessEqual(len(os.sched_getaffinity(0)),2)
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS),(536870912,536870912))
        self.assertEqual(resource.getrlimit(resource.RLIMIT_CPU),(60,60))
    def test_29_start_is_global_and_exclusive_before_fit(self):
        source=(PACKAGE/'fit_wrapper.py').read_text();tree=ast.parse(source)
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        calls=[n for n in ast.walk(run) if isinstance(n,ast.Call)]
        starts=[n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='write_once' and 'EMPIRICAL_START.json' in ast.unparse(n)]
        fit=next(n for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='fit')
        self.assertEqual(len(starts),1);self.assertLess(starts[0].lineno,fit.lineno)
        self.assertFalse(any(isinstance(n.func,ast.Attribute) and n.func.attr in ('unlink','remove','rmdir') for n in calls))
    def test_30_completion_after_replay_roundtrip_receipt_and_budget(self):
        tree=ast.parse((PACKAGE/'fit_wrapper.py').read_text());run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        complete=next(n for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='write_once' and 'EMPIRICAL_COMPLETE.json' in ast.unparse(n))
        for name in ('gradient_replay','load_checkpoint','family_metrics'):
            calls=[n for n in ast.walk(run) if isinstance(n,ast.Call) and ((isinstance(n.func,ast.Name) and n.func.id==name) or (isinstance(n.func,ast.Attribute) and n.func.attr==name))]
            self.assertTrue(calls);self.assertTrue(all(n.lineno<complete.lineno for n in calls))

if __name__=='__main__':
    resources=W.apply_limits()
    unittest.main(verbosity=2)
