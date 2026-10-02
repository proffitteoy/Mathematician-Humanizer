"""Tiny synthetic optimizer/recovery regressions; no empirical body reads."""
import contextlib
import copy
import dataclasses
import hashlib
import io
import json
from pathlib import Path
import random
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

import torch

from experimental_natural.models import InputView, PrefixModel
from experimental_natural.objectives import BalancedPlan
from experimental_natural.plan import transform_signature
from experimental_natural.schema import FitAuthorization
from experimental_natural.static_prefix_cache import CacheNamespace
from experimental_natural.train import FitLedger, TrainingConfig
from experimental_natural.staged_training import (
    DAY_SECONDS, RecoveryError, ResourceStop, StagedResourceGuard,
    _hash_file, _load_snapshot, _total_cpu, train_one_staged,
)
from test_core import fixture, record


class StagedTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog, self.train, self.transform = fixture()
        self.dev = [record(q='d' + str(i), answer='a' + str(i), split='dev',
                           arm=arm, offset=.25 + i + (arm == 'chatgpt') * .5)
                    for i in range(2) for arm in ('human', 'chatgpt')]
        self.phase_started = time.time() - .01
        self.config = TrainingConfig(max_epochs=4, patience=10, batch_questions=1)

    def model(self):
        torch.manual_seed(1701)
        return PrefixModel('F4', InputView(4, (0, 1, 2, 3)), 4, width=4)

    def args(self, name='fit', **changes):
        root = self.root / name
        result = dict(seed=1701, run_id='pooled.F4.1701', outdir=root / 'outputs',
                      ledger=FitLedger(root / 'ledger.jsonl'), run_cpu_limit_seconds=120,
                      phase_started_unix=self.phase_started, phase_cpu_baseline=0,
                      cache_namespace=CacheNamespace(transform_signature(self.transform), '2' * 64),
                      bindings={'contract': 'synthetic-contract', 'code': 'synthetic-code',
                                'data': 'synthetic-fixture'}, config=self.config,
                      derived_root=root)
        result.update(changes)
        return result

    def fit(self, model=None, args=None):
        model = self.model() if model is None else model
        args = self.args() if args is None else args
        with contextlib.redirect_stdout(io.StringIO()):
            result = train_one_staged(model, self.train, self.dev, self.transform, **args)
        return result

    def snapshots(self, args):
        return [e for e in args['ledger'].events() if e['event'] == 'snapshot_committed']

    def last_snapshot(self, args):
        return torch.load(self.snapshots(args)[-1]['snapshot_path'], map_location='cpu', weights_only=True)

    def assert_tree_equal(self, a, b):
        if isinstance(a, torch.Tensor):
            self.assertTrue(torch.equal(a, b), 'Tensor trajectory changed')
        elif isinstance(a, dict):
            self.assertEqual(set(a), set(b))
            for key in a:
                self.assert_tree_equal(a[key], b[key])
        elif isinstance(a, (list, tuple)):
            self.assertEqual(len(a), len(b))
            for x, y in zip(a, b):
                self.assert_tree_equal(x, y)
        else:
            self.assertEqual(a, b)

    def interrupt(self, args, after_steps=3):
        step = torch.optim.Adam.step
        count = 0

        def interrupted(optimizer, *a, **kw):
            nonlocal count
            result = step(optimizer, *a, **kw)
            count += 1
            if count == after_steps:
                raise KeyboardInterrupt('synthetic interruption after partial-epoch update')
            return result

        with patch.object(torch.optim.Adam, 'step', interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.fit(args=args)
        return count

    def test_exact_optimizer_selection_sampler_and_rng_after_partial_epoch(self):
        original_forward = PrefixModel.forward
        original_step = torch.optim.Adam.step
        original_draws = BalancedPlan.draws
        trajectories, samplers = {}, {}
        active = 'full'
        trace = []

        def stochastic_train(model, packet):
            result = original_forward(model, packet)
            if model.training:
                result = result + .001 * (random.random() + torch.rand(()))
            return result

        def step(optimizer, *a, **kw):
            result = original_step(optimizer, *a, **kw)
            trace.append(copy.deepcopy(optimizer.state_dict()))
            return result

        def draws(plan, seed, count=None):
            rows = tuple(original_draws(plan, seed, count))
            samplers.setdefault(active, []).append((seed, rows))
            yield from rows

        full, resumed = self.args('full'), self.args('resumed')
        with patch.object(PrefixModel, 'forward', stochastic_train), patch.object(BalancedPlan, 'draws', draws):
            with patch.object(torch.optim.Adam, 'step', step):
                full_result = self.fit(args=full)
            trajectories['full'] = trace[:]
            trace.clear()
            active = 'interrupted'
            # interrupt() wraps the tracing step, preserving the discarded update.
            with patch.object(torch.optim.Adam, 'step', step):
                self.interrupt(resumed)
            trajectories['interrupted'] = trace[:]
            trace.clear()
            active = 'resumed'
            with patch.object(torch.optim.Adam, 'step', step):
                resumed_result = self.fit(args={**resumed, 'resume': True})
            trajectories['resumed'] = trace[:]
        self.assertEqual(full_result['selected_epoch'], resumed_result['selected_epoch'])
        self.assertEqual(full_result['best_dev_score'], resumed_result['best_dev_score'])
        self.assert_tree_equal(trajectories['full'], trajectories['interrupted'][:2] + trajectories['resumed'])
        final_full, final_resumed = self.last_snapshot(full), self.last_snapshot(resumed)
        for key in ('state_dict', 'optimizer_state_dict', 'best_state_dict',
                    'best_optimizer_state_dict', 'python_rng_state', 'torch_rng_state',
                    'next_epoch', 'next_sampler_seed', 'best_epoch', 'stale_epochs'):
            self.assert_tree_equal(final_full[key], final_resumed[key])
        self.assertEqual(samplers['full'][1:], samplers['resumed'])
        self.assertEqual(samplers['full'][:2], samplers['interrupted'])
        events = resumed['ledger'].events()
        self.assertEqual(sum(e['event'] == 'attempt_started' for e in events), 1)
        self.assertEqual(sum(e['event'] == 'interrupted' for e in events), 1)
        self.assertEqual(sum(e['event'] == 'resume_started' for e in events), 1)
        self.assertTrue(resumed['ledger'].assert_complete([resumed['run_id']]))

    def test_final_shape_hash_complete_dev_and_immutable_retention(self):
        args = self.args()
        stdout = io.StringIO()
        real_print = print

        def copy_secondary(message, **kwargs):
            real_print(message, **kwargs)
            receipt = json.loads(message)
            if receipt['event'] == 'snapshot_committed':
                primary = Path(receipt['snapshot_path'])
                secondary = self.root / 'secondary' / primary.name
                secondary.parent.mkdir(exist_ok=True)
                shutil.copyfile(primary, secondary)
                self.assertEqual(_hash_file(secondary), receipt['snapshot_sha256'])
                (primary.parent / (receipt['snapshot_sha256'] + '.secondary.json')).write_text(json.dumps({
                    'snapshot_sha256': receipt['snapshot_sha256'], 'snapshot_bytes': receipt['snapshot_bytes'],
                    'secondary_path': str(secondary), 'readback_verified': True}))

        with contextlib.redirect_stdout(stdout), patch('experimental_natural.staged_training.print', copy_secondary):
            result = train_one_staged(self.model(), self.train, self.dev, self.transform, **args)
        saved = torch.load(result['checkpoint_path'], map_location='cpu', weights_only=True)
        self.assertEqual(set(saved), {'state_dict', 'seed', 'epoch', 'dev_score', 'run_id', 'transform'})
        self.assertEqual(_hash_file(result['checkpoint_path']), result['checkpoint_sha256'])
        self.assertEqual(saved['epoch'], result['selected_epoch'])
        expected_prefixes = sum(len(self.dev[i].values) - 1 for i in range(len(self.dev)))
        events = args['ledger'].events()
        self.assertTrue(all(e['dev_prefixes'] == expected_prefixes for e in events if e['event'] == 'epoch'))
        commits = self.snapshots(args)
        self.assertEqual(len(commits), 5)
        self.assertEqual(sum(Path(e['snapshot_path']).exists() for e in commits), 2)
        self.assertEqual(sum(e['event'] == 'snapshot_pruned' for e in events), 3)
        for entry in commits[-2:]:
            path = Path(entry['snapshot_path'])
            self.assertEqual(path.stat().st_mode & 0o222, 0)
            self.assertEqual(_hash_file(path), entry['snapshot_sha256'])
        receipts = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(len(receipts), 5)
        for receipt in receipts:
            self.assertEqual(set(receipt), {'event', 'run_id', 'epoch', 'snapshot_path', 'snapshot_sha256', 'snapshot_bytes'})
            self.assertGreater(receipt['snapshot_bytes'], 0)

    def test_no_primary_pruning_without_verified_secondary_copy(self):
        args = self.args()
        self.fit(args=args)
        commits = self.snapshots(args)
        self.assertTrue(all(Path(e['snapshot_path']).is_file() for e in commits))
        self.assertEqual(sum(e['event'] == 'backup_needed' for e in args['ledger'].events()), 3)
        self.assertFalse(any(e['event'] == 'snapshot_pruned' for e in args['ledger'].events()))

    def test_invalid_secondary_receipt_cannot_remove_last_copy(self):
        args = self.args()
        real_print = print

        def wrong_secondary(message, **kwargs):
            real_print(message, **kwargs)
            entry = json.loads(message)
            if entry['event'] == 'snapshot_committed':
                primary = Path(entry['snapshot_path'])
                (primary.parent / (entry['snapshot_sha256'] + '.secondary.json')).write_text(json.dumps({
                    'snapshot_sha256': entry['snapshot_sha256'], 'snapshot_bytes': entry['snapshot_bytes'],
                    'secondary_path': str(primary), 'readback_verified': True}))

        with patch('experimental_natural.staged_training.print', wrong_secondary):
            self.fit(args=args)
        self.assertTrue(all(Path(e['snapshot_path']).is_file() for e in self.snapshots(args)))
        self.assertFalse(any(e['event'] == 'snapshot_pruned' for e in args['ledger'].events()))

    def test_corrupt_latest_snapshot_is_rejected_without_fallback(self):
        args = self.args()
        self.interrupt(args)
        snapshot = Path(self.snapshots(args)[-1]['snapshot_path'])
        snapshot.chmod(0o644)
        with snapshot.open('ab') as stream:
            stream.write(b'corrupt')
        with self.assertRaisesRegex(RecoveryError, 'hash mismatch'):
            self.fit(args={**args, 'resume': True})

    def test_changed_bindings_config_transform_and_data_are_rejected(self):
        args = self.args()
        self.interrupt(args)
        for changes in ({'bindings': {'contract': 'different'}}, {'seed': 1702},
                        {'config': dataclasses.replace(self.config, learning_rate=.002)},
                        {'run_cpu_limit_seconds': 121}):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(RecoveryError, 'changed on resume'):
                    self.fit(args={**args, **changes, 'resume': True})
        self.train[0].values[0, 0] += .1
        with self.assertRaisesRegex(RecoveryError, 'changed on resume'):
            self.fit(args={**args, 'resume': True})

    def test_crash_requires_explicit_cpu_and_never_rolls_back_spending(self):
        args = self.args()
        self.interrupt(args)
        ledger = args['ledger']
        # Stand in for an external watchdog observation after a terminal marker
        # was not durably written by a killed process.
        ledger.append({'event': 'external_resource_observation', 'run_id': args['run_id'],
                       'cpu_seconds_current_fit': 7.})
        with self.assertRaisesRegex(RecoveryError, 'reconciled_cpu_seconds'):
            self.fit(args={**args, 'resume': True})
        with self.assertRaisesRegex(RecoveryError, 'roll back'):
            self.fit(args={**args, 'resume': True, 'reconciled_cpu_seconds': 6.})
        result = self.fit(args={**args, 'resume': True, 'reconciled_cpu_seconds': 8.})
        self.assertGreater(result['cpu_seconds'], 8.)
        self.assertGreaterEqual(ledger.consumed_cpu(), result['cpu_seconds'])
        self.assertTrue(any(e['event'] == 'external_resource_observation' for e in ledger.events()))

    def test_later_recorded_clean_interruption_cost_is_preserved(self):
        args = self.args()
        self.interrupt(args)
        args['ledger'].append({'event': 'interrupted', 'run_id': args['run_id'],
                               'cpu_seconds': 9., 'wall_seconds': 10., 'resumable': True})
        result = self.fit(args={**args, 'resume': True})
        self.assertGreater(result['cpu_seconds'], 9.)
        self.assertGreater(result['wall_seconds'], 10.)

    def test_phase_baseline_and_clocks_cannot_reset_on_resume(self):
        args = self.args()
        self.interrupt(args)
        for changes in ({'phase_started_unix': time.time() - .001}, {'phase_cpu_baseline': .01},
                        {'phase_cpu_limit_seconds': 100.}, {'phase_wall_limit_seconds': 100.}):
            with self.assertRaisesRegex(RecoveryError, 'phase cannot reset'):
                self.fit(args={**args, **changes, 'resume': True})

    def test_new_phase_keeps_run_and_global_spending(self):
        args = self.args()
        self.interrupt(args)
        args['ledger'].append({'event': 'interrupted', 'run_id': args['run_id'],
                               'cpu_seconds': 13., 'wall_seconds': 14., 'resumable': True})
        result = self.fit(args={**args, 'resume': True, 'phase_id': 'phase-2',
                               'phase_started_unix': time.time() - .001, 'phase_cpu_baseline': 13.})
        self.assertGreater(result['cpu_seconds'], 13.)
        self.assertGreater(result['global_cpu_seconds'], 13.)
        self.assertGreater(result['wall_seconds'], 14.)
        self.assertLess(result['phase_cpu_seconds'], result['cpu_seconds'])

    def test_numeric_failure_stays_failed_and_cannot_resume(self):
        args = self.args()
        with patch.object(PrefixModel, 'forward', side_effect=FloatingPointError('synthetic nonfinite data')):
            with self.assertRaises(FloatingPointError):
                self.fit(args=args)
        events = args['ledger'].events()
        self.assertEqual(events[-1]['event'], 'failed')
        self.assertFalse(events[-1]['resumable'])
        self.assertGreater(events[-1]['cpu_seconds'], 0.)
        with self.assertRaisesRegex(RecoveryError, 'Failed/completed'):
            self.fit(args={**args, 'resume': True})
        with self.assertRaises(ValueError):
            args['ledger'].assert_complete([args['run_id']])

    def test_guard_during_dev_logs_interruption_and_replays_the_epoch(self):
        args = self.args()
        original = StagedResourceGuard.check
        dev_calls = 0
        original_scorer = __import__('experimental_natural.scoring_reuse', fromlist=['score_model_reuse']).score_model_reuse

        def scorer(*a, **kw):
            guard = kw['progress_guard']
            def stop():
                nonlocal dev_calls
                dev_calls += 1
                guard()
                if dev_calls == 3:
                    raise ResourceStop('synthetic DEV prefix ceiling')
            return original_scorer(*a, **{**kw, 'progress_guard': stop})

        with patch('experimental_natural.scoring_reuse.score_model_reuse', scorer):
            with self.assertRaisesRegex(ResourceStop, 'DEV prefix'):
                self.fit(args=args)
        self.assertEqual(self.last_snapshot(args)['epoch'], 0)
        self.assertEqual(args['ledger'].events()[-1]['event'], 'interrupted')
        self.fit(args={**args, 'resume': True})
        self.assertEqual(self.last_snapshot(args)['epoch'], 4)

    def test_natural_requires_optimizer_retention_and_factory_authorization(self):
        self.train = [dataclasses.replace(r, kind='natural') for r in self.train]
        self.dev = [dataclasses.replace(r, kind='natural') for r in self.dev]
        args = self.args(config=TrainingConfig())
        with patch.object(torch.optim, 'Adam', side_effect=AssertionError('Natural optimizer must not run')):
            with self.assertRaises(PermissionError):
                self.fit(args=args)
            both = FitAuthorization(True, 'synthetic-negative-gate-test',
                                    ('train_model', 'prune_obsolete_recovery_snapshots'))
            with self.assertRaisesRegex(ValueError, 'factory'):
                self.fit(args={**args, 'authorization': both})
            model = self.model()
            model.initialization_seed = 1701
            model.transform_signature = transform_signature(self.transform)
            with self.assertRaisesRegex(PermissionError, 'prune_obsolete'):
                self.fit(model=model, args={**args, 'authorization': FitAuthorization(True, 'test', ('train_model',))})
            with self.assertRaisesRegex(ValueError, 'hyperparameter'):
                self.fit(model=model, args={**args, 'authorization': both, 'config': self.config})
        self.assertFalse(args['ledger'].path.exists())

    def test_failed_fits_count_against_global_fit_limit(self):
        args = self.args()
        ledger = args['ledger']
        ledger.max_fits = 200  # The engine still retains the original hard 100.
        for i in range(100):
            ledger.append({'event': 'attempt_started', 'run_id': 'old-' + str(i),
                           'started_unix': self.phase_started})
            ledger.append({'event': 'failed', 'run_id': 'old-' + str(i), 'cpu_seconds': .01})
        with self.assertRaisesRegex(ResourceStop, 'fit budget'):
            self.fit(args=args)
        self.assertEqual(len([e for e in ledger.events() if e['event'] == 'attempt_started']), 100)
        self.assertAlmostEqual(ledger.consumed_cpu(), 1.)

    def test_test_and_davinci_are_rejected_without_attempt(self):
        for change in ({'split': 'test'}, {'arm': 'davinci'}):
            self.dev[0] = dataclasses.replace(self.dev[0], **change)
            args = self.args()
            with self.assertRaisesRegex(ValueError, 'firewall'):
                self.fit(args=args)
            self.assertFalse(args['ledger'].path.exists())


class StagedBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = FitLedger(self.root / 'ledger.jsonl')
        self.now = 1000000.

    def guard(self, *, old_cpu=10., current_cpu=4., cpu_baseline=7., elapsed_cpu=1.,
              elapsed_wall=1., run_age=10., global_age=20., phase_age=5.,
              phase_baseline=0., phase_cpu_limit=100., phase_wall_limit=100.,
              run_cpu_limit=100., config=None):
        events = [dict(event='attempt_started', run_id='old', started_unix=self.now - global_age),
                  dict(event='failed', run_id='old', cpu_seconds=old_cpu),
                  dict(event='attempt_started', run_id='new', started_unix=self.now - run_age),
                  dict(event='snapshot_committed', run_id='new', cpu_seconds_current_fit=current_cpu)]
        self.process = patch('experimental_natural.staged_training.time.process_time', return_value=elapsed_cpu)
        self.mono = patch('experimental_natural.staged_training.time.monotonic', return_value=elapsed_wall)
        self.wall = patch('experimental_natural.staged_training.time.time', return_value=self.now)
        for p in (self.process, self.mono, self.wall):
            p.start()
            self.addCleanup(p.stop)
        return StagedResourceGuard(config=config or TrainingConfig(), ledger=self.ledger,
            run_id='new', derived_root=self.root, events=events, session_cpu_started=0.,
            session_monotonic_started=0., cpu_baseline=cpu_baseline,
            run_started_unix=self.now - run_age, run_cpu_limit_seconds=run_cpu_limit,
            phase_id='phase', phase={'started_unix': self.now - phase_age, 'cpu_baseline': phase_baseline,
                                    'cpu_limit_seconds': phase_cpu_limit, 'wall_limit_seconds': phase_wall_limit})

    def test_accounting_adds_failed_and_reconciled_cpu_without_double_count(self):
        guard = self.guard()
        a = guard.check()
        self.assertEqual(a['cpu_seconds'], 8.)
        self.assertEqual(a['global_cpu_seconds'], 18.)
        self.assertEqual(a['phase_cpu_seconds'], 18.)
        self.assertEqual(a['wall_seconds'], 10.)
        self.assertEqual(a['global_wall_seconds'], 20.)
        self.assertEqual(a['phase_wall_seconds'], 5.)

    def test_all_cpu_and_elapsed_wall_budgets_stop(self):
        cases = [({'old_cpu': DAY_SECONDS, 'phase_cpu_limit': DAY_SECONDS}, 'Global CPU'),
                 ({'global_age': DAY_SECONDS + 1}, 'Global wall'),
                 ({'phase_cpu_limit': 17.}, 'Phase CPU'),
                 ({'phase_age': 101.}, 'Phase wall'),
                 ({'run_cpu_limit': 7.}, 'Per-run CPU'),
                 ({'config': TrainingConfig(max_fit_seconds=9.)}, 'Per-run wall')]
        for values, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ResourceStop, expected):
                    self.guard(**values).check()

    def test_higher_ledger_setting_cannot_reset_original_24h_cpu(self):
        self.ledger.max_cpu_seconds = DAY_SECONDS * 3
        guard = self.guard(old_cpu=DAY_SECONDS - 1, phase_cpu_limit=DAY_SECONDS * 2)
        with self.assertRaisesRegex(ResourceStop, 'Global CPU'):
            guard.check()

    def test_rss_and_disk_have_hard_guards(self):
        guard = self.guard()
        with patch('experimental_natural.staged_training._peak_rss_bytes', return_value=2 * 1024**3):
            with self.assertRaisesRegex(ResourceStop, 'RSS'):
                guard.check()
        with patch('experimental_natural.staged_training._disk_bytes', return_value=2 * 1024**3):
            guard.disk_bytes(refresh=True)
            with self.assertRaisesRegex(ResourceStop, 'Derived-disk'):
                guard.check()

    def test_disk_inventory_is_cached_for_prefixes_and_can_be_forced_for_writes(self):
        guard = self.guard()
        with patch('experimental_natural.staged_training._disk_bytes', return_value=0) as inventory:
            guard.check()
            guard.check()
            self.assertEqual(inventory.call_count, 1)
            guard.disk_bytes(refresh=True)
            self.assertEqual(inventory.call_count, 2)

    def test_ledger_costs_take_maximum_evidence_per_run(self):
        events = [dict(run_id='a', cpu_seconds=9.), dict(run_id='a', cpu_seconds_current_fit=12.),
                  dict(run_id='a', cpu_seconds=3.), dict(run_id='b', cpu_seconds=4.)]
        self.assertEqual(_total_cpu(events), 16.)


if __name__ == '__main__':
    unittest.main(verbosity=2)
