"""Synthetic-only scorer integration regressions; no corpus reads or fitting."""
import dataclasses
import json
import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import torch

from experimental_natural import scoring_reuse, train
from experimental_natural.models import IndependentFamilies, InputView, PrefixModel, TrainingMean
from experimental_natural.objectives import BalancedPlan, aggregate_document_scores, family_loss
from experimental_natural.plan import transform_signature
from experimental_natural.schema import Catalog, NaturalMeasurementRecord, PrefixPacket, make_model_packet
from experimental_natural.scoring_reuse import score_model_reuse
from experimental_natural.static_prefix_cache import CacheNamespace, StaticPrefixCache
from experimental_natural.transforms import FrozenTransform


def catalog(dimensions=6):
    families = ('A', 'A', 'B', 'B') + ('structural_length',) * (dimensions - 4)
    return Catalog(tuple('sensor_' + str(i) for i in range(dimensions)), families,
                   ('raw_then_train_zscore',) * dimensions, tuple(range(4, dimensions)), ())


def transform(dimensions=6):
    c = catalog(dimensions)
    active = torch.ones(dimensions, dtype=torch.bool)
    active[1] = False
    eligible = active.clone()
    eligible[3] = False
    return FrozenTransform(c.ids, c.families, c.transforms, c.structural_indices,
        torch.linspace(-.2, .4, dimensions).double(), torch.linspace(.8, 2., dimensions).double(),
        active, eligible, (50,) * dimensions, None, ('baike', 'web'), 100, 50)


def record(question, answer, arm, length, seed, dimensions=6):
    generator = torch.Generator().manual_seed(seed)
    values = torch.randn((length, dimensions), generator=generator)
    values[torch.rand((length, dimensions), generator=generator) < .23] = float('nan')
    opportunity = torch.randint(1, 12, (length, dimensions), generator=generator).float()
    opportunity[torch.rand((length, dimensions), generator=generator) < .2] = float('nan')
    if length > 4:
        values[2] = float('nan')
        values[3, (0, 2, 4, 5)] = float('nan')
        values[4, 0] = 0.
        opportunity[4, 0] = 7.
    if length > 6:
        values[5] = float('nan')
        values[6] = float('nan')
        values[6, 2] = .7  # Exactly one observed eligible family.
    return NaturalMeasurementRecord(question, answer, 'component_' + question,
        'web' if question == 'q1' else 'baike', 'dev', arm, values, opportunity,
        {'missing_reason': 'synthetic_fixture'}, kind='synthetic')


def fixture():
    records = [record('orphan', 'a0', 'human', 5, 91)]
    for question, answer, lengths in (('q0', 'a0', (9, 8)), ('q0', 'a1', (7, 10)),
                                      ('q1', 'a0', (11, 6)), ('q2', 'a0', (4, 3))):
        for arm, length in zip(('human', 'chatgpt'), lengths):
            records.append(record(question, answer, arm, length, 310 + len(records)))
    records += [record('blank', 'a0', 'human', 1, 18), record('blank', 'a0', 'chatgpt', 0, 19)]
    return tuple(records), transform()


def cache_for(tr, budget=1 << 20):
    return StaticPrefixCache(len(tr.ids), CacheNamespace(transform_signature(tr), '9' * 64), budget)


def model_for(name, tr, mode='values'):
    active = tuple(torch.where(tr.active_values)[0].tolist())
    targets = tuple(torch.where(tr.score_eligible)[0].tolist())
    indices = tr.structural_indices if mode == 'length' else tuple(range(len(tr.ids)))
    return PrefixModel(name, InputView(len(tr.ids), indices, mode, active_value_indices=active),
                       len(tr.ids), 8, target_indices=targets)


class ScoringReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.threads = torch.get_num_threads()
        torch.set_num_threads(2)
        cls.comparison_metrics = {}

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.threads)
        print('SCORING_REUSE_COMPARISON_RECEIPT ' + json.dumps({
            'scope': 'synthetic_only_no_fitting',
            'natural_bodies_read': 0, 'test_bodies_read': 0, 'davinci_bodies_read': 0,
            'model_fits': 0,
            'comparison_rule': {
                'predictions_document_and_aggregate_losses': {'atol': 1e-6, 'rtol': 0},
                'individual_target_and_family_losses': {'atol': 1e-6, 'rtol': 1e-6}},
            'differences': cls.comparison_metrics}, sort_keys=True, allow_nan=False))

    def setUp(self):
        torch.manual_seed(1701)
        self.records, self.transform = fixture()
        self.plan = BalancedPlan(self.records, self.transform)

    def record_difference(self, name, actual, expected):
        actual = torch.as_tensor(actual, dtype=torch.float64).flatten()
        expected = torch.as_tensor(expected, dtype=torch.float64).flatten()
        difference = (actual - expected).abs()
        nonzero = expected != 0
        metrics = self.comparison_metrics.setdefault(name,
            {'max_absolute': 0., 'max_relative_nonzero_reference': 0.,
             'max_absolute_zero_reference': 0., 'values_compared': 0})
        metrics['max_absolute'] = max(metrics['max_absolute'], float(difference.max()))
        if nonzero.any():
            metrics['max_relative_nonzero_reference'] = max(metrics['max_relative_nonzero_reference'],
                float((difference[nonzero] / expected[nonzero].abs()).max()))
        if (~nonzero).any():
            metrics['max_absolute_zero_reference'] = max(metrics['max_absolute_zero_reference'],
                float(difference[~nonzero].max()))
        metrics['values_compared'] += difference.numel()

    def assert_nested_close(self, actual, expected, rtol=0):
        if isinstance(expected, dict):
            self.assertEqual(set(actual), set(expected))
            for key in expected:
                self.assert_nested_close(actual[key], expected[key], rtol)
        elif type(expected) is float:
            self.assertTrue(math.isfinite(actual))
            self.assertLessEqual(abs(actual - expected), 1e-6 + rtol * abs(expected))
        else:
            self.assertEqual(actual, expected)

    def assert_scores_close(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assert_nested_close(dataclasses.asdict(a), dataclasses.asdict(b))
            self.record_difference('document_loss', a.loss, b.loss)
            for family in b.family_losses:
                self.record_difference('document_family_loss', a.family_losses[family], b.family_losses[family])
        aa, bb = aggregate_document_scores(actual), aggregate_document_scores(expected)
        self.assert_nested_close(aa, bb)
        if bb['equal_arm_mean'] is not None:
            self.record_difference('aggregate_loss', aa['equal_arm_mean'], bb['equal_arm_mean'])
            for arm in bb['by_arm']:
                self.record_difference('aggregate_loss', aa['by_arm'][arm], bb['by_arm'][arm])

    def assert_reference(self, model, plan=None, cache=None, capture=False, **kwargs):
        plan = self.plan if plan is None else plan
        cache = cache_for(plan.transform) if cache is None else cache
        traces = ([], [])
        def recorder(destination):
            def score(prediction, target, observed, families):
                loss, parts = family_loss(prediction, target, observed, families)
                destination.append((prediction.clone(), target.clone(), observed.clone(),
                                    None if loss is None else float(loss),
                                    {name: float(value) for name, value in parts.items()}))
                return loss, parts
            return score
        with patch.object(train, 'family_loss', side_effect=recorder(traces[0])):
            expected = train.score_model(model, plan, **kwargs)
        with patch.object(scoring_reuse, 'family_loss', side_effect=recorder(traces[1])):
            actual = score_model_reuse(model, plan, cache=cache, **kwargs)
        self.assert_scores_close(actual, expected)
        if capture:
            self.assertEqual(len(traces[0]), len(traces[1]))
            for expected_part, actual_part in zip(*traces):
                self.record_difference('predictions', actual_part[0], expected_part[0])
                self.record_difference('individual_target_loss', actual_part[3], expected_part[3])
                for family in expected_part[4]:
                    self.record_difference('individual_family_loss', actual_part[4][family], expected_part[4][family])
                for a, b in zip(actual_part[:3], expected_part[:3]):
                    torch.testing.assert_close(a, b, atol=1e-6, rtol=0)
                # Match the reviewed kernels' atol=rtol=1e-6 criterion for
                # individual squared losses. Document/aggregate losses and
                # predictions above use the stronger absolute-only bound.
                self.assert_nested_close(actual_part[3], expected_part[3], rtol=1e-6)
                self.assert_nested_close(actual_part[4], expected_part[4], rtol=1e-6)
        return actual

    def test_ladders_controls_outputs_family_losses_and_hierarchy(self):
        for mode in ('values', 'mask_opportunity', 'pure_mask', 'length'):
            for name in ('F1', 'Fcov', 'F2', 'F3', 'F4'):
                with self.subTest(mode=mode, name=name):
                    self.assert_reference(model_for(name, self.transform, mode), capture=True)

    def test_independent_families_and_training_mean_reference_paths(self):
        targets = tuple(torch.where(self.transform.score_eligible)[0].tolist())
        active = tuple(torch.where(self.transform.active_values)[0].tolist())
        independent = IndependentFamilies(catalog(), 7, targets, active)
        self.assert_reference(independent, capture=True)
        self.assert_reference(TrainingMean(6), capture=True)

    def test_score_gate_min_prefix_gaps_and_answer_population(self):
        plan = BalancedPlan(self.records, self.transform, min_prefix=3, score_indices=(0, 2, 4))
        model = model_for('F4', self.transform)
        rows = self.assert_reference(model, plan, capture=True)
        self.assertEqual([r.question for r in rows], [self.records[i].question for i in plan.record_indices])
        self.assertEqual([r.targets for r in rows], [len(plan.positions[i]) for i in plan.record_indices])
        self.assertFalse(any(r.question in ('orphan', 'blank') for r in rows))
        self.assertTrue(any(b - a > 1 for i in plan.record_indices for a, b in
                            zip(plan.positions[i], plan.positions[i][1:])))
        for row, index in zip(rows, plan.record_indices):
            expected_counts = {}
            expected_observations = 0
            for position in plan.positions[index]:
                _, observed = self.transform.target(self.records[index].values[position])
                keep = torch.zeros_like(observed)
                keep[[0, 2, 4]] = True
                observed &= keep
                expected_observations += int(observed.sum())
                for family in {self.transform.families[j] for j in torch.where(observed)[0].tolist()}:
                    expected_counts[family] = expected_counts.get(family, 0) + 1
            self.assertEqual(row.family_target_counts, expected_counts)
            self.assertEqual(row.target_observations, expected_observations)

    def test_ten_seeded_permutation_losses_and_last_preserving_controls(self):
        models = [model_for('F4', self.transform),
                  IndependentFamilies(catalog(), 7, (0, 2, 4, 5), (0, 2, 3, 4, 5))]
        for model in models:
            for last in (False, True):
                with self.subTest(model=type(model).__name__, last=last):
                    self.assert_reference(model, permutations=10, preserve_last=last, capture=True)
        # Nonrecurrent controls and F0 explicitly retain reference forwards.
        for model in (model_for('F3', self.transform), TrainingMean(6)):
            self.assert_reference(model, permutations=10, preserve_last=True, capture=True)

    def test_exact_record_position_repeat_seeds_without_deduplication(self):
        plan = BalancedPlan(self.records, self.transform, min_prefix=4)
        model = model_for('F4', self.transform)
        real_evaluate = scoring_reuse.evaluate_permutations
        for last in (False, True):
            calls = []
            def checked(model, packet, orders, summary_cache):
                i, position = [(i, t) for i in plan.record_indices for t in plan.positions[i]][len(calls)]
                self.assertEqual(len(orders), 10)
                for rep, order in enumerate(orders):
                    generator = torch.Generator().manual_seed(47011 + 104729 * i + 15485863 * position + rep)
                    expected = (torch.cat([torch.randperm(position - 1, generator=generator),
                                          torch.tensor([position - 1])]) if last else
                                torch.randperm(position, generator=generator))
                    self.assertTrue(torch.equal(order, expected))
                calls.append((i, position))
                return real_evaluate(model, packet, orders, summary_cache)
            with patch.object(scoring_reuse, 'evaluate_permutations', side_effect=checked):
                score_model_reuse(model, plan, cache=cache_for(self.transform), permutations=10,
                                  preserve_last=last)
            self.assertEqual(calls, [(i, t) for i in plan.record_indices for t in plan.positions[i]])
        one = torch.tensor([0])
        orders = list(scoring_reuse._orders(10, 1, 47011, True))
        self.assertEqual(len(orders), 10)
        self.assertTrue(all(torch.equal(x, one) for x in orders))

    def test_mean_of_losses_is_not_loss_of_mean_predictions(self):
        plan = BalancedPlan(self.records, self.transform, score_indices=(0,))
        model = model_for('F4', self.transform)
        # Deliberately large permutation variance makes the incorrect estimator
        # fail decisively; all ten loss calculations must remain distinct.
        offsets = torch.arange(10).float() - 4.5
        def predictions(model, packet, orders, summary_cache):
            out = torch.zeros((10, 6))
            out[:, 0] = offsets
            return out
        with patch.object(scoring_reuse, 'evaluate_permutations', side_effect=predictions):
            actual = score_model_reuse(model, plan, cache=cache_for(self.transform), permutations=10)
        for row, i in zip(actual, plan.record_indices):
            targets = [float(self.transform.target(self.records[i].values[t])[0][0]) for t in plan.positions[i]]
            expected = sum(sum(float((offset - target) ** 2) for offset in offsets) / 10
                           for target in targets) / len(targets)
            self.assertAlmostEqual(row.loss, expected, places=6)
            self.assertGreater(row.loss - sum(target ** 2 for target in targets) / len(targets), 8.)

    def test_owned_packet_boundary_and_prefix_gaps(self):
        plan = BalancedPlan(self.records, self.transform, min_prefix=4, score_indices=(2,))
        real_stream = scoring_reuse.evaluate_prefix_stream
        streams = []
        def checked(model, packets, head_batch_size, summary_cache):
            self.assertEqual(head_batch_size, 32)
            index = plan.record_indices[len(streams)]
            seen = []
            streams.append(seen)
            def audited():
                for packet in packets:
                    self.assertIs(type(packet), PrefixPacket)
                    packet.validate(6)
                    self.assertEqual({f.name for f in dataclasses.fields(packet)}, {
                        'prefix_values', 'prefix_observed', 'prefix_opportunity',
                        'prefix_opportunity_known', 'prefix_unit_count'})
                    expected = make_model_packet(self.records[index], packet.prefix_unit_count, self.transform)
                    for field in dataclasses.fields(packet):
                        a, b = getattr(packet, field.name), getattr(expected, field.name)
                        if isinstance(a, torch.Tensor):
                            self.assertTrue(torch.equal(a, b))
                            self.assertEqual(a.untyped_storage().nbytes(), a.numel() * a.element_size())
                        else:
                            self.assertEqual(a, b)
                    seen.append(packet.prefix_unit_count)
                    yield packet
            return real_stream(model, audited(), head_batch_size=head_batch_size, summary_cache=summary_cache)
        with patch.object(scoring_reuse, 'evaluate_prefix_stream', side_effect=checked):
            self.assert_reference(model_for('F4', self.transform), plan, capture=True)
        self.assertEqual(streams, [list(range(1, max(plan.positions[i]) + 1)) for i in plan.record_indices])

    def test_cache_signature_dimension_and_model_provenance_fail_closed(self):
        model = model_for('F4', self.transform)
        bad_cache = StaticPrefixCache(6, CacheNamespace('1' * 64, '9' * 64), 1 << 20)
        with self.assertRaisesRegex(ValueError, 'TRAIN transform'):
            score_model_reuse(model, self.plan, cache=bad_cache)
        bad_cache = StaticPrefixCache(5, CacheNamespace(transform_signature(self.transform), '9' * 64), 1 << 20)
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            score_model_reuse(model, self.plan, cache=bad_cache)
        model.transform_signature = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Model does not match'):
            score_model_reuse(model, self.plan, cache=cache_for(self.transform))
        self.assertTrue(model.training)

    def test_no_learned_state_across_records_or_parameter_updates(self):
        model = model_for('F4', self.transform)
        cache = cache_for(self.transform)
        before = self.assert_reference(model, cache=cache)
        with torch.no_grad():
            model.head[-1].bias.add_(.1)
        after = self.assert_reference(model, cache=cache, capture=True)
        self.assertNotEqual(before[0].loss, after[0].loss)
        self.assertGreater(cache.hits, 0)
        # Reversing the selected record order may not carry causal state over.
        self.plan.record_indices = tuple(reversed(self.plan.record_indices))
        self.assert_reference(model, cache=cache, capture=True)
        self.assertIsNone(next(model.parameters()).grad)

    def test_empty_plan_and_changed_missing_support_do_not_change_population(self):
        model = model_for('F4', self.transform)
        empty = BalancedPlan(self.records, self.transform, score_indices=())
        self.assertEqual(score_model_reuse(model, empty, cache=cache_for(self.transform)), [])
        self.assertEqual(train.score_model(model, empty), [])
        i = self.plan.record_indices[0]
        old = self.plan.positions[i]
        self.plan.positions[i] = ()
        with self.assertRaisesRegex(ValueError, 'cannot omit'):
            score_model_reuse(model, self.plan, cache=cache_for(self.transform))
        self.plan.positions[i] = old
        self.records[i].values[old[0]] = float('nan')
        for permutations in (0, 10):
            with self.assertRaisesRegex(AssertionError, 'Fixed target support changed'):
                score_model_reuse(model, self.plan, cache=cache_for(self.transform), permutations=permutations)
        self.assertTrue(model.training)

    def test_numeric_and_iterator_failures_restore_all_training_modes(self):
        model = model_for('F4', self.transform)
        model.phi.eval()  # Preserve a mixed caller state too.
        modes = [m.training for m in model.modules()]
        with torch.no_grad():
            model.head[-1].bias[0] = float('nan')
        for permutations in (0, 10):
            with self.assertRaises(FloatingPointError):
                score_model_reuse(model, self.plan, cache=cache_for(self.transform), permutations=permutations)
            self.assertEqual([m.training for m in model.modules()], modes)
        model = model_for('F4', self.transform).eval()
        with patch.object(scoring_reuse, 'make_model_packet', side_effect=RuntimeError('synthetic failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                score_model_reuse(model, self.plan, cache=cache_for(self.transform))
        self.assertFalse(model.training)
        self.assertTrue(torch.is_grad_enabled())

    def test_nonfinite_observed_target_and_overflow_loss_fail(self):
        for value in (float('inf'), 1e30):
            records, tr = fixture()
            plan = BalancedPlan(records, tr)
            i = plan.record_indices[0]
            position = plan.positions[i][-1]
            records[i].values[position, 0] = value
            with self.subTest(value=value), self.assertRaises(FloatingPointError):
                score_model_reuse(TrainingMean(6), plan, cache=cache_for(tr))

    def test_parameter_change_during_scoring_fails_and_restores_mode(self):
        model = model_for('F4', self.transform)
        real_stream = scoring_reuse.evaluate_prefix_stream
        def changed(*args, **kwargs):
            for output in real_stream(*args, **kwargs):
                with torch.no_grad():
                    next(model.parameters()).add_(.01)
                yield output
        with patch.object(scoring_reuse, 'evaluate_prefix_stream', side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, 'parameter updates'):
                score_model_reuse(model, self.plan, cache=cache_for(self.transform))
        self.assertTrue(model.training)

    def test_progress_guard_prefix_batch_boundaries_and_exception_modes(self):
        for permutations in (0, 10):
            for model in (model_for('F4', self.transform), TrainingMean(6)):
                calls = []
                score_model_reuse(model, self.plan, cache=cache_for(self.transform),
                                  permutations=permutations, progress_guard=lambda: calls.append(1))
                if permutations or type(model) is TrainingMean:
                    expected = 2 * sum(len(self.plan.positions[i]) for i in self.plan.record_indices)
                else:
                    expected = sum(max(self.plan.positions[i]) + math.ceil(max(self.plan.positions[i]) / 32)
                                   for i in self.plan.record_indices)
                self.assertEqual(len(calls), expected)
                for fail_at in (1, 2, 9):
                    calls = []
                    model.eval()
                    if type(model) is PrefixModel:
                        model.phi.train()
                    modes = [m.training for m in model.modules()]
                    def guard():
                        calls.append(1)
                        if len(calls) == fail_at:
                            raise RuntimeError('synthetic resource ceiling')
                    with self.assertRaisesRegex(RuntimeError, 'resource ceiling'):
                        score_model_reuse(model, self.plan, cache=cache_for(self.transform),
                                          permutations=permutations, progress_guard=guard)
                    self.assertEqual([m.training for m in model.modules()], modes)
                    self.assertTrue(torch.is_grad_enabled())

    def test_test_and_davinci_rejected_before_body_access(self):
        class ForbiddenBody:
            def __init__(self, split, arm):
                self.split, self.arm = split, arm
            @property
            def values(self):
                raise AssertionError('Forbidden measurement body accessed')
        for split, arm in (('test', 'human'), ('dev', 'davinci')):
            plan = SimpleNamespace(transform=self.transform, record_indices=(0,),
                records=(ForbiddenBody(split, arm),), positions={0: (1,)}, score_indices=None)
            with self.assertRaisesRegex(ValueError, 'excludes TEST and davinci'):
                score_model_reuse(model_for('F4', self.transform), plan, cache=cache_for(self.transform))

    def test_bad_positions_and_permutation_arguments_fail_without_population_repair(self):
        model = model_for('F4', self.transform)
        i = self.plan.record_indices[0]
        for positions in ((0,), (1, 1), (4, 1), (len(self.records[i].values),)):
            self.plan.positions[i] = positions
            with self.assertRaises(ValueError):
                score_model_reuse(model, self.plan, cache=cache_for(self.transform))
        for count in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                score_model_reuse(model, self.plan, cache=cache_for(self.transform), permutations=count)

    def test_structural_only_727_prefixes_preserve_long_shape(self):
        dimensions, length = 70, 728
        tr = transform(dimensions)
        active = torch.zeros(dimensions, dtype=torch.bool)
        active[-2:] = True
        tr = dataclasses.replace(tr, structural_indices=(68, 69), active_values=active,
                                 score_eligible=active.clone())
        records = []
        for arm in ('human', 'chatgpt'):
            values = torch.full((length, dimensions), float('nan'))
            values[:, -2] = torch.arange(length).float() / 100
            values[:, -1] = 2. + torch.arange(length).float() / 700
            records.append(NaturalMeasurementRecord('long', 'a0', 'long', 'baike', 'dev', arm,
                values, torch.ones_like(values), {'missing_reason': 'synthetic_fixture'},
                kind='synthetic'))
        plan = BalancedPlan(records, tr)
        # Sparse target plans still advance every one of the 727 current units.
        for i in plan.record_indices:
            plan.positions[i] = (1, 2, 63, 127, 511, 726, 727)
        model = model_for('F4', tr, 'length')
        result = self.assert_reference(model, plan, cache=cache_for(tr, 2 << 20), capture=True)
        self.assertEqual([row.units for row in result], [728, 728])
        self.assertEqual([row.targets for row in result], [7, 7])
        self.assertEqual([row.target_observations for row in result], [14, 14])


if __name__ == '__main__':
    unittest.main()
