"""Model-free, self-contained synthetic admission/accounting compatibility tests.

No empirical configuration, approval, ledger, body, feature, checkpoint, or model
is read/imported. Execute with unittest discovery from this source-overlay root.
"""
import ast
import contextlib
import copy
import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import run_pure_followup_phase as runner
import bounded_pure_followup_phase as bounded


def synthetic_history():
    return {'original_first_attempt_unix':90, 'preceding_report_sha256':'e'*64,
            'proposal_sha256':'f'*64, 'completed_registered_fits':7,
            'terminal_resource_filename':'mask_followup.123.resources.json',
            'terminal_resource_sha256':'a'*64, 'post_mask_accounting_sha256':'b'*64}


def definition():
    return {'base_source_manifest_sha256':runner.BASE_SOURCE_MANIFEST_SHA256,
            'control_source_manifest_sha256':runner.CONTROL_SOURCE_MANIFEST_SHA256,
            'nuisance_source_manifest_sha256':runner.NUISANCE_SOURCE_MANIFEST_SHA256,
            'length_replication_source_manifest_sha256':runner.LENGTH_REPLICATION_SOURCE_MANIFEST_SHA256,
            'mask_followup_source_manifest_sha256':runner.MASK_FOLLOWUP_SOURCE_MANIFEST_SHA256,
            'execution_history':synthetic_history(),
            'base_contract_sha256':runner.BASE_CONTRACT_SHA256,
            'max_epochs':100, 'patience':10, 'full_TRAIN_and_DEV':True,
            'unchanged_objectives_and_typed_masks':True,
            'original_global_CPU_and_elapsed_wall_seconds':86400,
            'optimizer_execution_authorized_by_this_definition':False,
            'TEST_or_davinci_execution':False, 'source_bound_tensor_integration_required':True,
            'phases':[{'phase_id':runner.PHASE_ID,
                       'max_phase_cpu_seconds':11400,'max_phase_wall_seconds':11400,
                       'minimum_nonfit_reserve_cpu_seconds':600,
                       'minimum_nonfit_reserve_wall_seconds':600,
                       'runs':[{'run_id':rid, 'recipe':runner.control_recipe(rid),
                                'max_cpu_seconds':cap, 'max_wall_seconds':cap}
                               for rid,cap in zip(runner.CONTROL_ORDER, (10800,))]}]}


def rows():
    result = []
    for i, rid in enumerate(runner.PREREQUISITES):
        result += [{'event':'attempt_started','run_id':rid,'started_unix':100+i},
                   {'event':'completed','run_id':rid,'cpu_seconds':1000}]
    for i in range(1):
        result += [{'event':'attempt_started','run_id':f'earlier.registered.{i}','started_unix':101+i},
                   {'event':'completed','run_id':f'earlier.registered.{i}','cpu_seconds':0}]
    result += [{'event':'attempt_started','run_id':'earlier.failed','started_unix':90},
               {'event':'failed','run_id':'earlier.failed','cpu_seconds':500},
               {'event':'watchdog_cpu_reconciliation','run_id':'earlier.failed','cpu_seconds':600}]
    result += [{'event':'nonfit_resource_cpu','run_id':rid,'cpu_seconds':20}
               for rid in runner.BACKUP_IDS]
    return result


def encode(events):
    return ''.join(json.dumps(e, sort_keys=True)+'\n' for e in events).encode()


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.amendment = definition()
        self.phase = self.amendment['phases'][0]
        data = json.dumps(self.amendment).encode()
        (self.root/'PURE_FOLLOWUP_EXECUTION_AMENDMENT.json').write_bytes(data)
        self.approval = {k:True for k in runner.REQUIRED_FLAGS}
        self.approval.update(phase_id=runner.PHASE_ID, receipt='synthetic approval only',
                             execution_history=synthetic_history(), published_source_commit='a'*40, run_ids=list(runner.CONTROL_ORDER),
                             max_phase_cpu_seconds=11400, max_phase_wall_seconds=11400,
                             max_global_cpu_seconds=86400, max_global_wall_seconds=86400,
                             nonfit_reserve_cpu_seconds=600, nonfit_reserve_wall_seconds=600,
                             amendment_sha256=runner.digest(data), source_manifest_sha256='d'*64,
                             tensor_integration_source_manifest_sha256='d'*64)
        self.patch = patch.object(runner, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        tensor_path=self.root/'private/staged/PURE_FOLLOWUP_TENSOR_INTEGRATION.json'
        tensor_path.parent.mkdir(parents=True)
        self.tensor={'status':'passed','source_manifest_sha256':'d'*64,
                     'run_ids':list(runner.CONTROL_ORDER),'synthetic_only':True,'empirical_reads':0,
                     'checks':{k:True for k in runner.TENSOR_CHECKS}}
        tensor_blob=json.dumps(self.tensor).encode();tensor_path.write_bytes(tensor_blob)
        self.approval['tensor_integration_receipt_sha256']=runner.digest(tensor_blob)
        self.events = rows()
        self.blob = encode(self.events)
        self.cost = sum(runner.ledger_costs(self.events).values())
        self.report = {'status':'one_fixed_mask_followup_completed',
                       'source_manifest_sha256':runner.MASK_FOLLOWUP_SOURCE_MANIFEST_SHA256,
                       'all46_source_config_hashes_verified':True, 'completed_registered_fits':7,
                       'global_budget':{'recorded_CPU_used_seconds':self.cost, 'original_first_attempt_unix':90,
                                        'CPU_and_elapsed_wall_ceiling_seconds':86400},
                       'resources':{synthetic_history()['terminal_resource_filename']:{'exit_code':0,'stopped_reason':None,'status':'completed'}}}
        self.approval['accounting'] = {'ledger_prefix_bytes':len(self.blob),
                                      'ledger_prefix_sha256':runner.digest(self.blob),
                                      'original_first_attempt_unix':90,
                                      'accounted_cpu_seconds':self.cost,
                                      'backup_cpu_seconds':{rid:20 for rid in runner.BACKUP_IDS}}
        self.resources = {**self.approval['accounting'], 'status':'passed',
                          'mask_followup_report_sha256':synthetic_history()['preceding_report_sha256'],
                          'mask_followup_source_manifest_sha256':runner.MASK_FOLLOWUP_SOURCE_MANIFEST_SHA256,
                          'terminal_resource_filename':synthetic_history()['terminal_resource_filename'],
                          'terminal_resource_sha256':synthetic_history()['terminal_resource_sha256'],
                          'global_CPU_and_elapsed_wall_ceiling_seconds':86400,
                          'no_fit_active':True,'all_prior_selected_latest_two_backups_verified':True,
                          'completed_registered_fits':synthetic_history()['completed_registered_fits'],
                          'verified_backup_run_ids':sorted(e['run_id'] for e in self.events if e['event']=='completed')}

    def validate(self, approval=None, amendment=None, phase=None):
        return runner.validate_approval(approval or self.approval, amendment or self.amendment, phase or self.phase)

    def test_every_approval_gate_is_required(self):
        self.assertEqual(self.validate(), list(runner.CONTROL_ORDER))
        for flag in runner.REQUIRED_FLAGS:
            with self.subTest(flag=flag), self.assertRaises(PermissionError):
                self.validate({**self.approval, flag:False})

    def test_fixed_exact_batch_seed_and_architecture(self):
        self.validate()
        for ids in ([], list(runner.CONTROL_ORDER)*2, ['pooled.mask_opportunity.F4.1702'],
                    ['pooled.pure_mask.F4.1703'], ['pooled.pure_mask.F2.1702'],
                    ['pooled.pure_mask.F4.1701']):
            with self.subTest(ids=ids), self.assertRaises(PermissionError):
                self.validate({**self.approval,'run_ids':ids})

    def test_pure_followup_modes_and_training_flags(self):
        grid = {rid:runner.control_recipe(rid) for rid in runner.CONTROL_ORDER}
        for rid, mode in zip(runner.CONTROL_ORDER, ('pure_mask',)):
            recipe = runner.validate_registry(rid, grid)
            self.assertEqual(recipe['mode'], mode)
            self.assertEqual(runner.control_training_arguments(recipe),
                             {'seed':recipe['seed'], 'run_id':rid, 'source':None, 'shuffle_training':False})
        grid[runner.CONTROL_ORDER[0]] = {**grid[runner.CONTROL_ORDER[0]], 'mode':'values'}
        with self.assertRaises(PermissionError):
            runner.validate_registry(runner.CONTROL_ORDER[0], grid)

    def test_objective_support_optimizer_and_cap_contract_frozen(self):
        for key, value in (('max_epochs',2), ('patience',1), ('full_TRAIN_and_DEV',False),
                           ('unchanged_objectives_and_typed_masks',False), ('TEST_or_davinci_execution',True)):
            with self.subTest(key=key), self.assertRaises(PermissionError):
                self.validate(amendment={**self.amendment,key:value})
        for index in range(1):
            for key in ('max_cpu_seconds','max_wall_seconds','recipe'):
                phase = copy.deepcopy(self.phase)
                if key == 'recipe': phase['runs'][index][key]['mode'] = 'values'
                else: phase['runs'][index][key] += 1
                with self.assertRaises(PermissionError): self.validate(phase=phase)

    def test_global_phase_and_nonfinite_budgets_rejected(self):
        for key in ('max_global_cpu_seconds','max_global_wall_seconds'):
            with self.assertRaises(PermissionError): self.validate({**self.approval,key:172800})
        for key in ('max_phase_cpu_seconds','max_phase_wall_seconds'):
            for value in (0,10800,11399,11401,float('nan'),float('inf'),True):
                with self.subTest(key=key,value=value), self.assertRaises(PermissionError):
                    self.validate({**self.approval,key:value})
        for key in ('nonfit_reserve_cpu_seconds','nonfit_reserve_wall_seconds'):
            with self.assertRaises(PermissionError): self.validate({**self.approval,key:0})

    def test_plan_and_denial_never_import_torch_or_read_features(self):
        with patch.object(sys,'argv',['run_pure_followup_phase.py','--plan']), \
             patch.object(runner,'verify_public_source',side_effect=AssertionError('source read')), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            runner.main()
        self.assertEqual(json.loads(out.getvalue())['phase_id'],runner.PHASE_ID)
        self.assertNotIn('torch',sys.modules)
        with patch.object(sys,'argv',['run_pure_followup_phase.py']):
            with self.assertRaises(PermissionError): runner.main()
        self.assertNotIn('torch',sys.modules)

    def verify(self, blob=None, approval=None, report=None, resources=None):
        return runner.verify_accounting_receipt(approval or self.approval,
                    self.blob if blob is None else blob, report or self.report, resources or self.resources)

    def test_final_prior_phase_and_backup_reconciliation_required(self):
        self.verify()
        for report in ({**self.report,'status':'bounded_control_phase_incomplete'},
                       {**self.report,'global_budget':{**self.report['global_budget'],'recorded_CPU_used_seconds':self.cost+1}}):
            with self.assertRaises(PermissionError): self.verify(report=report)
        with self.assertRaises(PermissionError): self.verify(resources={'exit_code':-9,'stopped_reason':'CPU_limit'})
        a = copy.deepcopy(self.approval)
        a['accounting']['backup_cpu_seconds'][runner.BACKUP_IDS[0]] = 19
        with self.assertRaises(PermissionError): self.verify(approval=a)

    def test_prefix_prevents_reset_rewrite_truncation_but_allows_appended_costs(self):
        later = self.blob + encode([{'event':'nonfit_resource_cpu','run_id':'new.backup','cpu_seconds':100}])
        self.verify(later)
        for bad in (self.blob[:-1], self.blob.replace(b'600',b'000'), encode(self.events[2:])):
            with self.assertRaises(PermissionError): self.verify(bad)
        a = copy.deepcopy(self.approval)
        a['accounting']['original_first_attempt_unix'] = 100
        with self.assertRaises(PermissionError): self.verify(approval=a)

    def allocate(self, events=None, remaining=None, now=1000, state=None):
        return runner.assert_remaining_allocation(events or self.events,
                    self.phase['runs'] if remaining is None else remaining, self.approval, state, now)

    def test_failures_are_charged_once_at_highest_observed_cpu(self):
        self.assertEqual(self.cost,6640)
        self.assertEqual(self.allocate()['CPU_remaining_seconds'],79760)
        events = self.events + [{'event':'failed','run_id':'expensive.failure','cpu_seconds':71000}]
        self.assertGreater(sum(runner.ledger_costs(events).values()),71000)
        with self.assertRaises(RuntimeError): self.allocate(events)

    def test_both_caps_and_overhead_must_fit_actual_global_budget(self):
        self.assertEqual(self.allocate()['required_remaining_run_CPU_seconds'],10800)
        slack = 86400-10800-600-self.cost
        exact = self.events + [{'event':'nonfit_resource_cpu','run_id':'other','cpu_seconds':slack}]
        self.allocate(exact)
        with self.assertRaises(RuntimeError):
            self.allocate(exact+[{'event':'nonfit_resource_cpu','run_id':'other','cpu_seconds':slack+1}])
        # This one-run batch cannot shrink its registered cap to fit the budget.
        phase=copy.deepcopy(self.phase);phase['runs'][0]['max_cpu_seconds']-=1
        with self.assertRaises(PermissionError):self.validate(phase=phase)

    def test_original_wall_clock_survives_failures_and_recorded_highwater(self):
        with self.assertRaises(RuntimeError): self.allocate(now=90+86400)
        with self.assertRaises(RuntimeError):
            self.allocate(self.events+[{'event':'failed','run_id':'clock.observation','global_wall_seconds':86400}])
        with self.assertRaises(RuntimeError): self.allocate(now=90+86400-10800-599)

    def test_current_unfinished_fit_blocks(self):
        with self.assertRaises(PermissionError):
            self.allocate(self.events+[{'event':'attempt_started','run_id':'still.running','started_unix':900}])

    def test_resume_retains_all_prior_cpu_and_original_run_wall(self):
        rid=runner.CONTROL_ORDER[0]
        events=self.events+[{'event':'attempt_started','run_id':rid,'started_unix':900},
                            {'event':'interrupted','run_id':rid,'cpu_seconds':4000,'wall_seconds':100}]
        result=self.allocate(events)
        self.assertEqual(result['required_remaining_run_CPU_seconds'],6800)
        self.assertEqual(result['CPU_used_seconds'],10640)
        self.assertEqual(result['required_remaining_run_wall_seconds'],10700)
        with self.assertRaises(RuntimeError): self.allocate(events,now=900+10800)
        with self.assertRaises(PermissionError): self.allocate(events+[{'event':'failed','run_id':rid,'cpu_seconds':4001}])

    def test_phase_clocks_do_not_reset_on_new_invocation(self):
        state={'started_unix':950,'cpu_baseline':1000}
        with self.assertRaises(RuntimeError): self.allocate(state=state)
        state={'started_unix':1000-11400,'cpu_baseline':6640}
        with self.assertRaises(RuntimeError): self.allocate(state=state)

    def test_supervisor_includes_new_backup_cpu_without_double_charging_fit(self):
        rid=runner.CONTROL_ORDER[0]
        new=self.events+[{'event':'epoch','run_id':rid,'cpu_seconds':100},
                         {'event':'nonfit_resource_cpu','run_id':runner.BACKUP_IDS[0],'cpu_seconds':70}]
        a=bounded.live_accounting(self.events,new,150,{'cpu_baseline':self.cost,'started_unix':900},1000)
        self.assertEqual(a['global_cpu_seconds'],self.cost+200)
        self.assertEqual(a['phase_cpu_seconds'],200)
        self.assertEqual(a['uncharged_invocation_cpu_seconds'],50)
        self.assertEqual(a['global_wall_seconds'],910)

    def test_supervisor_stops_on_original_global_and_phase_clocks(self):
        original={'global_cpu_seconds':1,'global_wall_seconds':1,'phase_cpu_seconds':1,'phase_wall_seconds':1}
        for field,limit,reason in (('global_cpu_seconds',86400,'original_global_CPU_limit'),
                                  ('global_wall_seconds',86400,'original_global_wall_limit'),
                                  ('phase_cpu_seconds',11400,'original_phase_CPU_limit'),
                                  ('phase_wall_seconds',11400,'original_phase_wall_limit')):
            self.assertEqual(bounded.stop_reason({**original,field:limit},0,self.approval),reason)
        self.assertEqual(bounded.stop_reason(original,2*1024**3,self.approval),'2GiB_process_tree_RSS')

    def test_training_call_preserves_full_support_and_default_optimizer(self):
        # AST-only check imports neither torch nor the empirical study.
        path=Path(runner.__file__)
        tree=ast.parse(path.read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        train=[n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='train_one_staged']
        self.assertEqual(len(train),1)
        kw={k.arg for k in train[0].keywords}
        self.assertNotIn('score_indices',kw)
        defaults=[n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='TrainingConfig']
        self.assertEqual(len(defaults),1)
        self.assertEqual(defaults[0].keywords,[])
        replacements=[n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='replace']
        self.assertEqual([{k.arg for k in n.keywords} for n in replacements],[{'max_fit_seconds'}])
        imports=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertFalse(any('torch' in ast.unparse(n) for n in imports))

    def test_frozen_and_new_source_inclusion_and_bytes_are_checked(self):
        # Synthetic20/32/39/46 identities; no empirical configurations are needed.
        files={}; stages=[]
        specifications=(('STAGED',20,'BASE'),('CONTROL',20,'CONTROL'),
                        ('NUISANCE',32,'NUISANCE'),('LENGTH_REPLICATION',39,'LENGTH_REPLICATION'),
                        ('MASK_FOLLOWUP',46,'MASK_FOLLOWUP'))
        with contextlib.ExitStack() as stack:
            bindings={}
            for prefix,count,constant in specifications:
                for i in range(len(files),count):
                    name=f'old{i}.py';(self.root/name).write_text('frozen\n')
                    files[name]=runner.digest((self.root/name).read_bytes())
                blob=json.dumps({'files':dict(files)}).encode()
                filename=prefix+'_SOURCE_MANIFEST.json'
                (self.root/filename).write_bytes(blob)
                value=runner.digest(blob)
                stack.enter_context(patch.object(runner,constant+'_SOURCE_MANIFEST_SHA256',value))
                key=('base' if constant=='BASE' else constant.lower())+'_source_manifest_sha256'
                bindings[key]=value
            for name in runner.PUBLIC_SOURCE_ALLOWLIST:
                (self.root/name).parent.mkdir(exist_ok=True)
                (self.root/name).write_text('synthetic '+name+'\n')
                files[name]=runner.digest((self.root/name).read_bytes())
            for name in ('PURE_FOLLOWUP_EXECUTION_AMENDMENT.json','MASK_FOLLOWUP_SOURCE_MANIFEST.json'):
                files[name]=runner.digest((self.root/name).read_bytes())
            manifest={**bindings,'files':files,'public_source_allowlist':list(runner.PUBLIC_SOURCE_ALLOWLIST)}
            def verify():
                blob=json.dumps(manifest).encode();(self.root/'PURE_FOLLOWUP_SOURCE_MANIFEST.json').write_bytes(blob)
                runner.verify_public_source({**bindings,'source_manifest_sha256':runner.digest(blob)})
            verify()
            (self.root/'old0.py').write_text('modified\n')
            with self.assertRaises(PermissionError):verify()
            (self.root/'old0.py').write_text('frozen\n')
            for name in ('old0.py',runner.PUBLIC_SOURCE_ALLOWLIST[0]):
                value=files.pop(name)
                with self.assertRaises(PermissionError):verify()
                files[name]=value
            files['extra.py']='a'*64
            with self.assertRaises(PermissionError):verify()
            del files['extra.py']
            manifest['public_source_allowlist'].append('PURE_FOLLOWUP_EXECUTION_AMENDMENT.json')
            with self.assertRaises(PermissionError):verify()

    def test_supervisor_is_exact_mechanical_copy_of_reviewed_v2(self):
        source=Path(bounded.__file__).read_text().replace('pure_followup','mask_followup').replace('PURE_FOLLOWUP','MASK_FOLLOWUP')
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),
                         '8e526eaec638ed6d5895998fcb43436ab288b9cff25ef99d30e64c0d214fc8be')

    def test_post_mask_accounting_allows_later_costs_without_reset(self):
        self.verify(self.blob+encode([{'event':'nonfit_resource_cpu','run_id':'validation.new','cpu_seconds':123}]))
        for field in ('no_fit_active','all_prior_selected_latest_two_backups_verified'):
            with self.assertRaises(PermissionError):self.verify(resources={**self.resources,field:False})
        with self.assertRaises(PermissionError):self.verify(resources={**self.resources,'verified_backup_run_ids':self.resources['verified_backup_run_ids'][:-1]})
        with self.assertRaises(PermissionError):self.verify(resources={**self.resources,'accounted_cpu_seconds':self.cost-1})
        with self.assertRaises(PermissionError):self.verify(report={**self.report,'resources':{'bad':{'exit_code':0,'status':'completed','stopped_reason':'overrun'}}})

    def test_local_execution_bindings_missing_malformed_or_mismatched_fail_closed(self):
        for key in synthetic_history():
            approval=copy.deepcopy(self.approval)
            del approval['execution_history'][key]
            with self.subTest(missing=key), self.assertRaises(PermissionError):self.validate(approval)
        for key,value in (('original_first_attempt_unix',0),('original_first_attempt_unix',float('nan')),
                          ('preceding_report_sha256',''),('proposal_sha256','wrong'),
                          ('completed_registered_fits',True),('completed_registered_fits',0)):
            approval=copy.deepcopy(self.approval);approval['execution_history'][key]=value
            with self.subTest(key=key,value=value), self.assertRaises(PermissionError):self.validate(approval)
        for key,value in (('original_first_attempt_unix',91),('preceding_report_sha256','c'*64),
                          ('proposal_sha256','b'*64),('completed_registered_fits',8)):
            approval=copy.deepcopy(self.approval);approval['execution_history'][key]=value
            with self.subTest(mismatch=key), self.assertRaises(PermissionError):self.validate(approval)
        approval=copy.deepcopy(self.approval);approval.pop('execution_history')
        with self.assertRaises(PermissionError):self.validate(approval)
        amendment=copy.deepcopy(self.amendment);amendment.pop('execution_history')
        with self.assertRaises(PermissionError):self.validate(amendment=amendment)

    def test_local_prior_completion_count_is_enforced(self):
        approval=copy.deepcopy(self.approval)
        approval['execution_history']['completed_registered_fits']+=1
        resources=copy.deepcopy(self.resources);resources['completed_registered_fits']+=1
        with self.assertRaises(PermissionError):self.verify(approval=approval,resources=resources)

    def test_preflight_pins_prior_report_proposal_and_post_accounting(self):
        private=self.root/'private/staged'
        (private/'fit_ledger.jsonl').write_bytes(self.blob)
        report_blob=json.dumps(self.report).encode()
        report_hash=runner.digest(report_blob)
        (private/'MASK_FOLLOWUP_REPORT.json').write_bytes(report_blob)
        proposal_blob=b'{"synthetic_proposal": true}\n'
        (private/'PURE_FOLLOWUP_PROPOSAL.json').write_bytes(proposal_blob)
        terminal_blob=json.dumps(self.report['resources'][synthetic_history()['terminal_resource_filename']]).encode()
        (private/synthetic_history()['terminal_resource_filename']).write_bytes(terminal_blob)
        terminal_hash=runner.digest(terminal_blob)
        accounting={**self.resources,'mask_followup_report_sha256':report_hash,'terminal_resource_sha256':terminal_hash}
        accounting_blob=json.dumps(accounting).encode()
        (private/'PURE_FOLLOWUP_ACCOUNTING.json').write_bytes(accounting_blob)
        approval=copy.deepcopy(self.approval)
        approval['accounting'].update(mask_followup_report_sha256=report_hash,
                                    post_mask_accounting_sha256=runner.digest(accounting_blob),terminal_resource_sha256=terminal_hash)
        approval['execution_history'].update(preceding_report_sha256=report_hash,
                                              proposal_sha256=runner.digest(proposal_blob),terminal_resource_sha256=terminal_hash,
                                              post_mask_accounting_sha256=runner.digest(accounting_blob))
        with patch.object(runner.time,'time',return_value=1000):
            _,remaining,allocation=runner.preflight(approval,self.phase)
            self.assertEqual([r['run_id'] for r in remaining],list(runner.CONTROL_ORDER))
            self.assertEqual(allocation['required_remaining_run_CPU_seconds'],10800)
            (private/'fit_ledger.jsonl').write_bytes(self.blob+encode([
                {'event':'nonfit_resource_cpu','run_id':'validation.new','cpu_seconds':7}]))
            self.assertEqual(runner.preflight(approval,self.phase)[2]['CPU_used_seconds'],self.cost+7)
            for name in ('MASK_FOLLOWUP_REPORT.json','PURE_FOLLOWUP_PROPOSAL.json','PURE_FOLLOWUP_ACCOUNTING.json',synthetic_history()['terminal_resource_filename']):
                path=private/name;original=path.read_bytes();path.write_bytes(original+b' ')
                with self.assertRaises(PermissionError):runner.preflight(approval,self.phase)
                path.write_bytes(original)

    def test_compact_observer_preserves_accounting_and_handles_partial_append(self):
        path=self.root/'ledger.jsonl';path.write_bytes(self.blob)
        observer=bounded.LedgerObserver(path)
        compact=observer.read()
        self.assertEqual(runner.ledger_costs(compact),runner.ledger_costs(self.events))
        self.assertEqual(runner.global_wall(compact,1000),runner.global_wall(self.events,1000))
        extra=encode([{'event':'nonfit_resource_cpu','run_id':'backup.new','cpu_seconds':3}])
        with path.open('ab') as f:f.write(extra[:-1])
        self.assertEqual(runner.ledger_costs(observer.read()),runner.ledger_costs(compact))
        with path.open('ab') as f:f.write(b'\n')
        self.assertEqual(runner.ledger_costs(observer.read())['backup.new'],3)
        path.write_bytes(b'')
        with self.assertRaises(PermissionError):observer.read()

    def test_observer_rejects_same_size_history_rewrite(self):
        path=self.root/'ledger.jsonl';path.write_bytes(self.blob)
        observer=bounded.LedgerObserver(path);observer.read()
        path.write_bytes(self.blob.replace(b'600',b'700'))
        with self.assertRaises(PermissionError):observer.read()

    def test_tensor_receipt_is_required_true_and_source_bound(self):
        runner.verify_tensor_integration(self.approval,'d'*64)
        for value in (None,False):
            a=dict(self.approval)
            if value is None:a.pop('tensor_integration_passed')
            else:a['tensor_integration_passed']=False
            with self.assertRaises(PermissionError):self.validate(a)
        with self.assertRaises(PermissionError):
            self.validate({**self.approval,'tensor_integration_source_manifest_sha256':'e'*64})
        with self.assertRaises(PermissionError):
            runner.verify_tensor_integration(self.approval,'e'*64)
        path=self.root/'private/staged/PURE_FOLLOWUP_TENSOR_INTEGRATION.json'
        for field in runner.TENSOR_CHECKS:
            receipt=copy.deepcopy(self.tensor);receipt['checks'][field]=False
            blob=json.dumps(receipt).encode();path.write_bytes(blob)
            with self.assertRaises(PermissionError):
                runner.verify_tensor_integration({**self.approval,'tensor_integration_receipt_sha256':runner.digest(blob)},'d'*64)

    def test_historical_crash_reconciliation_never_offsets_fresh_cpu(self):
        rid=runner.CONTROL_ORDER[0]
        before=self.events+[{'event':'attempt_started','run_id':rid,'started_unix':900},
                            {'event':'interrupted','run_id':rid,'cpu_seconds':4000}]
        after=before+[{'event':'resume_started','run_id':rid,'cpu_seconds':5100,'reconciled_cpu_seconds':5000}]
        state={'cpu_baseline':self.cost,'started_unix':800}
        for old,new in ((before,after),(bounded.compact_accounting_rows(before),bounded.compact_accounting_rows(after))):
            actual=bounded.live_accounting(old,new,150,state,1000)
            self.assertEqual(actual['global_cpu_seconds'],11790)
            self.assertEqual(actual['uncharged_invocation_cpu_seconds'],50)

    def supervisor_mocks(self, popen, *, waited_cpu=0, clock=None, resume=False):
        private=self.root/'private/staged'
        ledger=private/'fit_ledger.jsonl';ledger.write_bytes(self.blob)
        approval_path=self.root/'approval.json';approval_path.write_text(json.dumps(self.approval))
        sampler=types.SimpleNamespace(process_tree=lambda pid,seen:(0,0))
        zero=types.SimpleNamespace(ru_utime=0,ru_stime=0)
        final=types.SimpleNamespace(ru_utime=waited_cpu,ru_stime=0)
        stack=contextlib.ExitStack()
        stack.enter_context(patch.dict(sys.modules,{'bounded_profile':sampler}))
        stack.enter_context(patch.object(runner,'verify_public_source',return_value=('d'*64,{})))
        stack.enter_context(patch.object(runner,'preflight',return_value=(self.events,self.phase['runs'],{})))
        argv=['bounded_pure_followup_phase.py','--approval',str(approval_path)]
        if resume:argv+=['--resume-run',runner.CONTROL_ORDER[0],'--reconciled-cpu-seconds','5000']
        stack.enter_context(patch.object(sys,'argv',argv))
        stack.enter_context(patch.object(bounded.subprocess,'Popen',**popen))
        stack.enter_context(patch.object(bounded.resource,'getrusage',side_effect=[zero,final]))
        stack.enter_context(patch.object(bounded.os,'sched_setaffinity'))
        if clock is not None:stack.enter_context(patch.object(bounded.time,'time',side_effect=clock))
        else:stack.enter_context(patch.object(bounded.time,'time',return_value=1000))
        return stack,ledger,private

    def test_popen_failure_charges_startup_and_writes_terminal_receipt(self):
        stack,ledger,private=self.supervisor_mocks({'side_effect':OSError('synthetic spawn failure')})
        with stack,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):bounded.main()
        events=runner.ledger_rows(ledger.read_bytes())
        self.assertGreater(sum(runner.ledger_costs(events).values()),self.cost)
        self.assertTrue(any(e['event']=='supervisor_attempt_started' for e in events))
        self.assertTrue(any(e['event']=='supervisor_attempt_terminal' for e in events))
        receipt=json.loads(next(private.glob('pure_followup.*.resources.json')).read_text())
        self.assertNotEqual(receipt['exit_code'],0)
        self.assertEqual(receipt['status'],'startup_failed')
        self.assertEqual(receipt['stopped_reason'],'startup_failure')
        self.assertTrue((private/(runner.PHASE_ID+'.json')).exists())

    def test_final_waited_cpu_cannot_report_success_above_global_limit(self):
        child=types.SimpleNamespace(pid=999999,returncode=0,poll=lambda:0,wait=lambda:0)
        stack,ledger,private=self.supervisor_mocks({'return_value':child},waited_cpu=90000)
        with stack,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as error:bounded.main()
        self.assertNotEqual(error.exception.code,0)
        receipt=json.loads(next(private.glob('pure_followup.*.resources.json')).read_text())
        self.assertGreater(receipt['global_cpu_seconds_used'],86400)
        self.assertNotEqual(receipt['exit_code'],0)
        self.assertEqual(receipt['child_exit_code'],0)
        self.assertEqual(receipt['status'],'resource_interrupted')
        self.assertEqual(receipt['stopped_reason'],'original_global_CPU_limit')

    def test_final_elapsed_wall_overrun_is_failure_even_with_zero_child_exit(self):
        child=types.SimpleNamespace(pid=999999,returncode=0,poll=lambda:0,wait=lambda:0)
        stack,ledger,private=self.supervisor_mocks({'return_value':child})
        # Preflight is isolated; the terminal original-clock check must still
        # reject this deliberately exhausted synthetic wall origin.
        with stack,patch.object(bounded.time,'time',return_value=100000),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as error:bounded.main()
        self.assertNotEqual(error.exception.code,0)
        receipt=json.loads(next(private.glob('pure_followup.*.resources.json')).read_text())
        self.assertEqual(receipt['stopped_reason'],'original_global_wall_limit')

    def test_prelaunch_reconciliation_is_durable_before_child_starts(self):
        rid=runner.CONTROL_ORDER[0]
        self.events += [{'event':'attempt_started','run_id':rid,'started_unix':900},
                        {'event':'interrupted','run_id':rid,'cpu_seconds':4000}]
        self.blob=encode(self.events)
        child=types.SimpleNamespace(pid=999999,returncode=0,poll=lambda:0,wait=lambda:0)
        seen=[]
        def launch(*args,**kwargs):
            events=runner.ledger_rows((self.root/'private/staged/fit_ledger.jsonl').read_bytes())
            seen.append(runner.ledger_costs(events)[rid]);return child
        stack,ledger,private=self.supervisor_mocks({'side_effect':launch},resume=True)
        with stack,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):bounded.main()
        self.assertEqual(seen,[5000])
        self.assertTrue(any(e['event']=='prelaunch_cpu_reconciliation' for e in runner.ledger_rows(ledger.read_bytes())))

    def test_phase_state_cannot_be_recreated_after_failed_startup(self):
        path=self.root/'private/staged';path.mkdir(parents=True,exist_ok=True)
        events=self.events+[{'event':'nonfit_resource_cpu','run_id':'startup.failure',
                            'phase_id':runner.PHASE_ID,'cpu_seconds':1}]
        with patch.object(runner,'preflight',return_value=(events,self.phase['runs'],{})):
            with self.assertRaises(PermissionError):
                runner.get_phase_state(self.approval,'s'*64,self.phase,create=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
