"""Model-free, self-contained synthetic admission/accounting compatibility tests.

No empirical configuration, approval, ledger, body, feature, checkpoint, or model
is read/imported. Execute with unittest discovery from this source-overlay root.
"""
import ast
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import run_nuisance_phase as runner
import bounded_nuisance_phase as bounded


def definition():
    return {'base_source_manifest_sha256':runner.BASE_SOURCE_MANIFEST_SHA256,
            'control_source_manifest_sha256':runner.CONTROL_SOURCE_MANIFEST_SHA256,
            'base_contract_sha256':runner.BASE_CONTRACT_SHA256,
            'max_epochs':100, 'patience':10, 'full_TRAIN_and_DEV':True,
            'unchanged_objectives_and_typed_masks':True,
            'original_global_CPU_and_elapsed_wall_seconds':86400,
            'optimizer_execution_authorized_by_this_definition':False,
            'TEST_or_davinci_execution':False, 'source_bound_tensor_integration_required':True,
            'phases':[{'phase_id':runner.PHASE_ID,
                       'max_phase_cpu_seconds':34320,'max_phase_wall_seconds':34320,
                       'minimum_nonfit_reserve_cpu_seconds':120,
                       'minimum_nonfit_reserve_wall_seconds':120,
                       'runs':[{'run_id':rid, 'recipe':runner.control_recipe(rid),
                                'max_cpu_seconds':cap, 'max_wall_seconds':cap}
                               for rid,cap in zip(runner.CONTROL_ORDER, (11160,10800,12240))]}]}


def rows():
    result = []
    for i, rid in enumerate(runner.PREREQUISITES):
        result += [{'event':'attempt_started','run_id':rid,'started_unix':100+i},
                   {'event':'completed','run_id':rid,'cpu_seconds':1000}]
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
        (self.root/'NUISANCE_EXECUTION_AMENDMENT.json').write_bytes(data)
        self.approval = {k:True for k in runner.REQUIRED_FLAGS}
        self.approval.update(phase_id=runner.PHASE_ID, receipt='synthetic approval only',
                             published_source_commit='a'*40, run_ids=list(runner.CONTROL_ORDER),
                             max_phase_cpu_seconds=34320, max_phase_wall_seconds=34320,
                             max_global_cpu_seconds=86400, max_global_wall_seconds=86400,
                             nonfit_reserve_cpu_seconds=120, nonfit_reserve_wall_seconds=120,
                             amendment_sha256=runner.digest(data), source_manifest_sha256='d'*64,
                             tensor_integration_source_manifest_sha256='d'*64)
        self.patch = patch.object(runner, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        tensor_path=self.root/'private/staged/NUISANCE_TENSOR_INTEGRATION.json'
        tensor_path.parent.mkdir(parents=True)
        self.tensor={'status':'passed','source_manifest_sha256':'d'*64,
                     'run_ids':list(runner.CONTROL_ORDER),'synthetic_only':True,'empirical_reads':0,
                     'checks':{k:True for k in runner.TENSOR_CHECKS}}
        tensor_blob=json.dumps(self.tensor).encode();tensor_path.write_bytes(tensor_blob)
        self.approval['tensor_integration_receipt_sha256']=runner.digest(tensor_blob)
        self.events = rows()
        self.blob = encode(self.events)
        self.cost = sum(runner.ledger_costs(self.events).values())
        self.resources = {'exit_code':0, 'stopped_reason':None}
        self.report = {'status':'both_registered_controls_completed',
                       'source_manifest_sha256':runner.CONTROL_SOURCE_MANIFEST_SHA256,
                       'all_frozen20_and_control_source_hashes_verified':True,
                       'global_budget':{'CPU_used_seconds':self.cost, 'original_first_attempt_unix':90,
                                        'CPU_and_elapsed_wall_ceiling_seconds':86400},
                       'resources':self.resources}
        self.approval['accounting'] = {'ledger_prefix_bytes':len(self.blob),
                                      'ledger_prefix_sha256':runner.digest(self.blob),
                                      'original_first_attempt_unix':90,
                                      'accounted_cpu_seconds':self.cost,
                                      'backup_cpu_seconds':{rid:20 for rid in runner.BACKUP_IDS}}

    def validate(self, approval=None, amendment=None, phase=None):
        return runner.validate_approval(approval or self.approval, amendment or self.amendment, phase or self.phase)

    def test_every_approval_gate_is_required(self):
        self.assertEqual(self.validate(), list(runner.CONTROL_ORDER))
        for flag in runner.REQUIRED_FLAGS:
            with self.subTest(flag=flag), self.assertRaises(PermissionError):
                self.validate({**self.approval, flag:False})

    def test_fixed_order_leading_batch_seed_and_architecture(self):
        for count in (1,2,3):
            self.validate({**self.approval,'run_ids':list(runner.CONTROL_ORDER[:count])})
        for ids in ([], [runner.CONTROL_ORDER[1]], list(reversed(runner.CONTROL_ORDER)),
                    ['pooled.mask_opportunity.F4.1702'], ['pooled.mask_opportunity.F2.1701']):
            with self.subTest(ids=ids), self.assertRaises(PermissionError):
                self.validate({**self.approval,'run_ids':ids})

    def test_nuisance_modes_and_training_flags(self):
        grid = {rid:runner.control_recipe(rid) for rid in runner.CONTROL_ORDER}
        for rid, mode in zip(runner.CONTROL_ORDER, ('mask_opportunity','pure_mask','length')):
            recipe = runner.validate_registry(rid, grid)
            self.assertEqual(recipe['mode'], mode)
            self.assertEqual(runner.control_training_arguments(recipe),
                             {'seed':1701, 'run_id':rid, 'source':None, 'shuffle_training':False})
        grid[runner.CONTROL_ORDER[0]] = {**grid[runner.CONTROL_ORDER[0]], 'mode':'values'}
        with self.assertRaises(PermissionError):
            runner.validate_registry(runner.CONTROL_ORDER[0], grid)

    def test_objective_support_optimizer_and_cap_contract_frozen(self):
        for key, value in (('max_epochs',2), ('patience',1), ('full_TRAIN_and_DEV',False),
                           ('unchanged_objectives_and_typed_masks',False), ('TEST_or_davinci_execution',True)):
            with self.subTest(key=key), self.assertRaises(PermissionError):
                self.validate(amendment={**self.amendment,key:value})
        for index in range(3):
            for key in ('max_cpu_seconds','max_wall_seconds','recipe'):
                phase = copy.deepcopy(self.phase)
                if key == 'recipe': phase['runs'][index][key]['mode'] = 'values'
                else: phase['runs'][index][key] += 1
                with self.assertRaises(PermissionError): self.validate(phase=phase)

    def test_global_phase_and_nonfinite_budgets_rejected(self):
        for key in ('max_global_cpu_seconds','max_global_wall_seconds'):
            with self.assertRaises(PermissionError): self.validate({**self.approval,key:172800})
        for key in ('max_phase_cpu_seconds','max_phase_wall_seconds'):
            for value in (0,34321,float('nan'),float('inf'),True):
                with self.subTest(key=key,value=value), self.assertRaises(PermissionError):
                    self.validate({**self.approval,key:value})
        for key in ('nonfit_reserve_cpu_seconds','nonfit_reserve_wall_seconds'):
            with self.assertRaises(PermissionError): self.validate({**self.approval,key:0})

    def test_plan_and_denial_never_import_torch_or_read_features(self):
        with patch.object(sys,'argv',['run_nuisance_phase.py','--plan']), \
             patch.object(runner,'verify_public_source',side_effect=AssertionError('source read')), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            runner.main()
        self.assertEqual(json.loads(out.getvalue())['phase_id'],runner.PHASE_ID)
        self.assertNotIn('torch',sys.modules)
        with patch.object(sys,'argv',['run_nuisance_phase.py']):
            with self.assertRaises(PermissionError): runner.main()
        self.assertNotIn('torch',sys.modules)

    def verify(self, blob=None, approval=None, report=None, resources=None):
        return runner.verify_accounting_receipt(approval or self.approval,
                    self.blob if blob is None else blob, report or self.report, resources or self.resources)

    def test_final_prior_phase_and_backup_reconciliation_required(self):
        self.verify()
        for report in ({**self.report,'status':'bounded_control_phase_incomplete'},
                       {**self.report,'global_budget':{**self.report['global_budget'],'CPU_used_seconds':0}}):
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
        self.assertEqual(self.cost,2640)
        self.assertEqual(self.allocate()['CPU_remaining_seconds'],83760)
        events = self.events + [{'event':'failed','run_id':'expensive.failure','cpu_seconds':50000}]
        self.assertGreater(sum(runner.ledger_costs(events).values()),50000)
        with self.assertRaises(RuntimeError): self.allocate(events)

    def test_all_three_caps_and_overhead_must_fit_actual_global_budget(self):
        self.assertEqual(self.allocate()['required_remaining_run_CPU_seconds'],34200)
        slack = 86400-34200-120-self.cost
        exact = self.events + [{'event':'nonfit_resource_cpu','run_id':'other','cpu_seconds':slack}]
        self.allocate(exact)
        with self.assertRaises(RuntimeError):
            self.allocate(exact+[{'event':'nonfit_resource_cpu','run_id':'other','cpu_seconds':slack+1}])
        # A smaller explicitly approved batch can fit; no silent truncation.
        self.allocate(exact+[{'event':'nonfit_resource_cpu','run_id':'other','cpu_seconds':slack+1}],self.phase['runs'][:1])

    def test_original_wall_clock_survives_failures_and_recorded_highwater(self):
        with self.assertRaises(RuntimeError): self.allocate(now=90+86400)
        with self.assertRaises(RuntimeError):
            self.allocate(self.events+[{'event':'failed','run_id':'clock.observation','global_wall_seconds':86400}])
        with self.assertRaises(RuntimeError): self.allocate(now=90+86400-34200-119)

    def test_current_unfinished_fit_blocks(self):
        with self.assertRaises(PermissionError):
            self.allocate(self.events+[{'event':'attempt_started','run_id':'still.running','started_unix':900}])

    def test_resume_retains_all_prior_cpu_and_original_run_wall(self):
        rid=runner.CONTROL_ORDER[0]
        events=self.events+[{'event':'attempt_started','run_id':rid,'started_unix':900},
                            {'event':'interrupted','run_id':rid,'cpu_seconds':4000,'wall_seconds':100}]
        result=self.allocate(events)
        self.assertEqual(result['required_remaining_run_CPU_seconds'],30200)
        self.assertEqual(result['CPU_used_seconds'],6640)
        self.assertEqual(result['required_remaining_run_wall_seconds'],34100)
        with self.assertRaises(RuntimeError): self.allocate(events,now=900+11160)
        with self.assertRaises(PermissionError): self.allocate(events+[{'event':'failed','run_id':rid,'cpu_seconds':4001}])

    def test_phase_clocks_do_not_reset_on_new_invocation(self):
        state={'started_unix':950,'cpu_baseline':1000}
        with self.assertRaises(RuntimeError): self.allocate(state=state)
        state={'started_unix':1000-34320,'cpu_baseline':2640}
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
                                  ('phase_cpu_seconds',34320,'original_phase_CPU_limit'),
                                  ('phase_wall_seconds',34320,'original_phase_wall_limit')):
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
        # Entirely synthetic manifest with patched pins; no study files needed.
        (self.root/'old.py').write_text('frozen\n')
        base={'files':{'old.py':runner.digest((self.root/'old.py').read_bytes())}}
        base_blob=json.dumps(base).encode()
        (self.root/'STAGED_SOURCE_MANIFEST.json').write_bytes(base_blob)
        base_hash=runner.digest(base_blob)
        control={'files':base['files']}
        control_blob=json.dumps(control).encode()
        (self.root/'CONTROL_SOURCE_MANIFEST.json').write_bytes(control_blob)
        control_hash=runner.digest(control_blob)
        files=dict(base['files'])
        for name in ('run_nuisance_phase.py','bounded_nuisance_phase.py','tests/test_nuisance_runner.py','tests/test_nuisance_tensor_integration.py'):
            (self.root/name).parent.mkdir(exist_ok=True)
            (self.root/name).write_text('synthetic '+name+'\n')
            files[name]=runner.digest((self.root/name).read_bytes())
        files['NUISANCE_EXECUTION_AMENDMENT.json']=runner.digest((self.root/'NUISANCE_EXECUTION_AMENDMENT.json').read_bytes())
        manifest={'base_source_manifest_sha256':base_hash,'control_source_manifest_sha256':control_hash,'files':files}
        blob=json.dumps(manifest).encode()
        (self.root/'NUISANCE_SOURCE_MANIFEST.json').write_bytes(blob)
        approval={'source_manifest_sha256':runner.digest(blob),'base_source_manifest_sha256':base_hash,'control_source_manifest_sha256':control_hash}
        with patch.object(runner,'BASE_SOURCE_MANIFEST_SHA256',base_hash), patch.object(runner,'CONTROL_SOURCE_MANIFEST_SHA256',control_hash):
            runner.verify_public_source(approval)
            (self.root/'old.py').write_text('modified\n')
            with self.assertRaises(PermissionError):runner.verify_public_source(approval)
            (self.root/'old.py').write_text('frozen\n')
            del manifest['files']['old.py']
            blob=json.dumps(manifest).encode();(self.root/'NUISANCE_SOURCE_MANIFEST.json').write_bytes(blob)
            with self.assertRaises(PermissionError):
                runner.verify_public_source({**approval,'source_manifest_sha256':runner.digest(blob)})

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
        path=self.root/'private/staged/NUISANCE_TENSOR_INTEGRATION.json'
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
            self.assertEqual(actual['global_cpu_seconds'],7790)
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
        argv=['bounded_nuisance_phase.py','--approval',str(approval_path)]
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
        receipt=json.loads(next(private.glob('nuisance.*.resources.json')).read_text())
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
        receipt=json.loads(next(private.glob('nuisance.*.resources.json')).read_text())
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
        receipt=json.loads(next(private.glob('nuisance.*.resources.json')).read_text())
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
