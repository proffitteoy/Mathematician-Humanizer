"""Fixed-control admission and tiny synthetic integration; no natural inputs."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import run_control_phase as runner

ROOT = Path(__file__).resolve().parents[1]

class ControlAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        # Self-contained synthetic definition: published tests require no local
        # experiment configuration, approvals, manifests or result records.
        self.amendment={'base_source_manifest_sha256':runner.BASE_SOURCE_MANIFEST_SHA256,
            'phases':[{'phase_id':'pooled_mechanism_seed1701',
                'max_phase_cpu_seconds':48600,'max_phase_wall_seconds':48600,
                'runs':[
                    {'run_id':'pooled.shuffled.F4.1701','max_cpu_seconds':21600,'max_wall_seconds':21600,
                     'recipe':{'id':'pooled.shuffled.F4.1701','model':'F4','mode':'values','seed':1701,
                               'source':None,'shuffle_training':True}},
                    {'run_id':'pooled.independent.F4.1701','max_cpu_seconds':26100,'max_wall_seconds':26100,
                     'recipe':{'id':'pooled.independent.F4.1701','model':'independent_F4','mode':'values',
                               'seed':1701,'source':None}}]}]}
        self.phase=self.amendment['phases'][0]
        self.blob=json.dumps(self.amendment).encode();(self.root/'CONTROL_EXECUTION_AMENDMENT.json').write_bytes(self.blob)
        self.approval={k:True for k in ('approved','optimizer_fits_approved','full_train_dev_features_approved','publication_verified','independent_review_passed','prune_obsolete_recovery_snapshots_approved')}
        self.approval.update(phase_id=self.phase['phase_id'],run_ids=list(runner.CONTROL_ORDER),published_source_commit='a'*40,
                             max_phase_cpu_seconds=48600,max_phase_wall_seconds=48600,max_global_cpu_seconds=86400,
                             max_global_wall_seconds=86400,amendment_sha256=hashlib.sha256(self.blob).hexdigest())
        self.patch=patch.object(runner,'ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)

    def test_all_explicit_admission_flags_required(self):
        self.assertEqual(runner.validate_approval(self.approval,self.amendment,self.phase),list(runner.CONTROL_ORDER))
        for key in ('approved','optimizer_fits_approved','full_train_dev_features_approved','publication_verified','independent_review_passed','prune_obsolete_recovery_snapshots_approved'):
            with self.subTest(key=key),self.assertRaises(PermissionError):
                runner.validate_approval({**self.approval,key:False},self.amendment,self.phase)

    def test_fixed_seed_order_and_scope(self):
        for ids in ([runner.CONTROL_ORDER[1]],list(reversed(runner.CONTROL_ORDER)),['pooled.shuffled.F4.1702'],['web.F4.1701']):
            with self.subTest(ids=ids),self.assertRaises(PermissionError):
                runner.validate_approval({**self.approval,'run_ids':ids},self.amendment,self.phase)

    def test_global_budget_cannot_expand_or_reset(self):
        for key in ('max_global_cpu_seconds','max_global_wall_seconds'):
            with self.assertRaises(PermissionError):runner.validate_approval({**self.approval,key:172800},self.amendment,self.phase)

    def test_stricter_phase_bound_allowed_expansion_rejected(self):
        for key in ('max_phase_cpu_seconds','max_phase_wall_seconds'):
            runner.validate_approval({**self.approval,key:48000},self.amendment,self.phase)
            for value in (0,48601):
                with self.assertRaises(PermissionError):runner.validate_approval({**self.approval,key:value},self.amendment,self.phase)

    def test_recipe_and_run_caps_are_fixed(self):
        for change in ('recipe','max_cpu_seconds','max_wall_seconds'):
            phase=copy.deepcopy(self.phase)
            if change=='recipe':phase['runs'][0]['recipe']['shuffle_training']=False
            else:phase['runs'][0][change]+=1
            with self.assertRaises(PermissionError):runner.validate_approval(self.approval,self.amendment,phase)

    def test_deny_before_source_or_body_reads(self):
        path=self.root/'approval.json';path.write_text(json.dumps({**self.approval,'approved':False}))
        with patch.object(sys,'argv',['run_control_phase.py','--approval',str(path)]),patch.object(runner,'verify_public_source',side_effect=AssertionError('Source phase reached')) as source:
            with self.assertRaises(PermissionError):runner.main()
        source.assert_not_called()

    def test_plan_needs_no_approval_or_body_access(self):
        with patch.object(sys,'argv',['run_control_phase.py','--plan']),patch.object(runner,'verify_public_source',side_effect=AssertionError('Source/body phase reached')),contextlib.redirect_stdout(io.StringIO()) as out:
            runner.main()
        self.assertEqual(json.loads(out.getvalue())['phase_id'],self.phase['phase_id'])

    def test_registry_and_training_flags(self):
        registry={rid:runner.control_recipe(rid) for rid in runner.CONTROL_ORDER}
        for i,rid in enumerate(runner.CONTROL_ORDER):
            recipe=runner.validate_registry(rid,registry);args=runner.control_training_arguments(recipe)
            self.assertEqual(args,{'seed':1701,'run_id':rid,'source':None,'shuffle_training':i==0})
        bad=copy.deepcopy(registry);bad[runner.CONTROL_ORDER[0]]['shuffle_training']=False
        with self.assertRaises(PermissionError):runner.validate_registry(runner.CONTROL_ORDER[0],bad)

    def test_cumulative_and_resume_budget_accounting(self):
        class Ledger:
            def __init__(self,cpu,old_wall=0,partial=0):self.cpu=cpu;self.old_wall=old_wall;self.partial=partial
            def consumed_cpu(self):return self.cpu
            def events(self):return [{'event':'attempt_started','run_id':'old','started_unix':time.time()-self.old_wall},
                                     {'event':'interrupted','run_id':runner.CONTROL_ORDER[0],'cpu_seconds':self.partial}]
        value=runner.assert_remaining_allocation(Ledger(36173),self.phase['runs'],self.approval)
        self.assertEqual(value['CPU_remaining_seconds'],50227)
        with self.assertRaises(RuntimeError):runner.assert_remaining_allocation(Ledger(50000),self.phase['runs'],self.approval)
        with self.assertRaises(RuntimeError):runner.assert_remaining_allocation(Ledger(1,86401),self.phase['runs'],self.approval)
        # A resumed run preserves charged CPU; only its unspent cap is reserved again.
        runner.assert_remaining_allocation(Ledger(50000,partial=14000),self.phase['runs'],self.approval)

    def test_old_and_new_source_bytes_and_inclusion_verified(self):
        (self.root/'old.py').write_text('fixed old source\n')
        old={'files':{'old.py':hashlib.sha256((self.root/'old.py').read_bytes()).hexdigest()}}
        blob=json.dumps(old).encode();(self.root/'STAGED_SOURCE_MANIFEST.json').write_bytes(blob);base=hashlib.sha256(blob).hexdigest()
        (self.root/'run_control_phase.py').write_text('fixed new source\n')
        files={**old['files'],**{n:hashlib.sha256((self.root/n).read_bytes()).hexdigest() for n in ('run_control_phase.py','CONTROL_EXECUTION_AMENDMENT.json')}}
        manifest={'base_source_manifest_sha256':base,'files':files};data=json.dumps(manifest).encode();(self.root/'CONTROL_SOURCE_MANIFEST.json').write_bytes(data)
        approval={'base_source_manifest_sha256':base,'source_manifest_sha256':hashlib.sha256(data).hexdigest()}
        with patch.object(runner,'BASE_SOURCE_MANIFEST_SHA256',base):
            runner.verify_public_source(approval)
            for name in ('old.py','run_control_phase.py','CONTROL_EXECUTION_AMENDMENT.json'):
                original=(self.root/name).read_bytes();(self.root/name).write_bytes(original+b'changed')
                with self.assertRaises(PermissionError):runner.verify_public_source(approval)
                (self.root/name).write_bytes(original)
            del manifest['files']['old.py'];data=json.dumps(manifest).encode();(self.root/'CONTROL_SOURCE_MANIFEST.json').write_bytes(data)
            with self.assertRaises(PermissionError):runner.verify_public_source({**approval,'source_manifest_sha256':hashlib.sha256(data).hexdigest()})

class SyntheticControlIntegrationTests(unittest.TestCase):
    def test_registered_factory_training_flags_and_DEV_permutations(self):
        import torch
        from test_core import fixture,record
        from experimental_natural.plan import registered_run_grid,build_registered_model,transform_signature
        from experimental_natural.static_prefix_cache import CacheNamespace
        from experimental_natural.train import FitLedger,TrainingConfig
        from experimental_natural.staged_training import train_one_staged
        from experimental_natural import scoring_reuse
        torch.set_num_threads(2)
        catalog,train,transform=fixture();dev=[record(q='d'+str(i),answer='a'+str(i),split='dev',arm=arm,offset=.25+i)
                                            for i in range(2) for arm in ('human','chatgpt')]
        registry={r['id']:r for r in registered_run_grid()}
        for i,rid in enumerate(runner.CONTROL_ORDER):
            recipe=runner.validate_registry(rid,registry);model=build_registered_model(catalog,recipe,transform)
            self.assertEqual(model.initialization_seed,1701)
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);ledger=FitLedger(root/'ledger.jsonl');original=scoring_reuse.score_model_reuse
                with patch.object(scoring_reuse,'score_model_reuse',wraps=original) as scorer,contextlib.redirect_stdout(io.StringIO()):
                    result=train_one_staged(model,train,dev,transform,**runner.control_training_arguments(recipe),
                        outdir=root/'outputs',ledger=ledger,run_cpu_limit_seconds=120,phase_started_unix=time.time(),phase_cpu_baseline=0,
                        phase_cpu_limit_seconds=120,phase_wall_limit_seconds=120,
                        cache_namespace=CacheNamespace(transform_signature(transform),'2'*64),
                        bindings={'contract':'synthetic','data':'synthetic','code':'synthetic'},
                        config=TrainingConfig(max_epochs=2,patience=10,batch_questions=1),derived_root=root)
                self.assertEqual(scorer.call_count,2)
                self.assertTrue(all(c.kwargs['permutations']==(10 if i==0 else 0) for c in scorer.call_args_list))
                completed=[e for e in ledger.events() if e['event']=='completed'];self.assertEqual(len(completed),1)
                self.assertEqual(completed[0]['run_id'],rid);self.assertGreaterEqual(result['selected_epoch'],1)

if __name__=='__main__':unittest.main(verbosity=2)
