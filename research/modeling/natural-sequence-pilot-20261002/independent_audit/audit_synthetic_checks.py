#!/usr/bin/env python3
"""Independent synthetic checks, reconstructed after executor replacement.

No natural record body is read. Prior execution receipts do not validate this
reconstruction; rerun against restored sources and the authorized runtime.
"""
import dataclasses
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
torch.set_num_threads(2)
from experimental_natural.schema import Catalog, NaturalMeasurementRecord, PrefixPacket, make_model_packet, validate_cohort
from experimental_natural.transforms import fit_transform, hierarchical_unit_weights
from experimental_natural.models import InputView, PrefixModel, IndependentFamilies
from experimental_natural.objectives import BalancedPlan, DocumentScore, family_loss, paired_seed_comparison
from experimental_natural.train import score_model, _shuffle, FitLedger, TrainingConfig, train_one, deterministic_seed


def tiny_catalog():
    return Catalog(('a', 'b', 'c', 'length'), ('A', 'A', 'B', 'structural_length'),
                   ('raw_then_train_zscore',) * 4, (3,), ())


def record(q='q0', answer='a0', arm='human', split='train', source='baike', n=4,
           offset=0., values=None, component=None):
    if values is None:
        values = torch.tensor([[1., 2., 3., 4.], [2., 4., 1., 5.],
                               [4., 1., 2., 6.], [3., 3., 4., 7.]])[:n] + offset
    return NaturalMeasurementRecord(q, answer, component or q, source, split, arm,
        values.float(), torch.ones_like(values) * 5,
        {'quality_claim': 'candidate_unvalidated', 'comparison_eligible': False,
         'missing_reason': 'synthetic_fixture'}, kind='synthetic')


def fixture():
    records = [record(), record(arm='chatgpt', offset=.5),
               record(q='q1', answer='a1', offset=1),
               record(q='q1', answer='a1', arm='chatgpt', offset=1.5)]
    catalog = tiny_catalog()
    return catalog, records, fit_transform(records, catalog, min_components=1)


def packet(raw, opportunity=None):
    raw = torch.as_tensor(raw, dtype=torch.float32)
    known = torch.ones_like(raw, dtype=torch.bool) if opportunity is None else ~torch.isnan(opportunity)
    opportunity = torch.ones_like(raw) if opportunity is None else torch.nan_to_num(opportunity)
    return PrefixPacket(torch.nan_to_num(raw).clone(), (~torch.isnan(raw)).clone(),
                        opportunity.clone(), known.clone(), len(raw))


class IndependentAudit(unittest.TestCase):
    def test_contract_identity(self):
        expected = '2729b1608397be1d45e3620c86ec7b3ae1f21fdc9e28c70bc942c41b0a122444'
        self.assertEqual(hashlib.sha256((ROOT / 'training_contract.json').read_bytes()).hexdigest(), expected)

    def test_covariance_against_direct_centered_reference(self):
        generator = torch.Generator().manual_seed(813)
        for n in (1, 2, 5, 29):
            raw = torch.randn(n, 5, generator=generator)
            raw[torch.rand(n, 5, generator=generator) < .35] = float('nan')
            raw[:, 4] = float('nan')
            view = InputView(5, tuple(range(5)))
            summary = view.summarize(packet(raw), True)
            pairs = view.pairs
            covariance = summary[view.summary_size - 1:view.summary_size - 1 + pairs]
            first = summary[30 + 4 * pairs:30 + 5 * pairs]
            second = summary[30 + 5 * pairs:30 + 6 * pairs]
            index = 0
            for j in range(5):
                for k in range(j, 5):
                    observed = ~torch.isnan(raw[:, j]) & ~torch.isnan(raw[:, k])
                    x, y = raw[observed, j].double(), raw[observed, k].double()
                    expected = 0. if len(x) < 2 else float(((x - x.mean()) * (y - y.mean())).sum() / (len(x) - 1))
                    self.assertAlmostEqual(float(covariance[index]), expected, places=6)
                    self.assertAlmostEqual(float(first[index]), float(x.mean()) if len(x) else 0., places=6)
                    self.assertAlmostEqual(float(second[index]), float(y.mean()) if len(y) else 0., places=6)
                    index += 1

    def test_same_means_different_covariance(self):
        a, b = packet([[-1., -1.], [1., 1.]]), packet([[-1., 1.], [1., -1.]])
        view = InputView(2, (0, 1))
        self.assertTrue(torch.equal(view.summarize(a), view.summarize(b)))
        first, second = view.summarize(a, True), view.summarize(b, True)
        self.assertEqual(int(torch.count_nonzero(first - second)), 1)
        self.assertEqual(float(first[view.summary_size]), 2.)
        self.assertEqual(float(second[view.summary_size]), -2.)

    def test_constant_large_values_have_exact_zero_covariance(self):
        for value, n in ((1e10, 100), (1e15, 7), (1e15, 100)):
            view = InputView(2, (0, 1))
            summary = view.summarize(packet(torch.full((n, 2), value)), True)
            self.assertTrue(torch.equal(summary[view.summary_size - 1:view.summary_size + 2], torch.zeros(3)))

    def test_covariance_only_adds_values_not_support(self):
        p = packet([[1., float('nan'), 5.], [3., 2., 7.], [5., 4., float('nan')]])
        view = InputView(3, (0, 1, 2))
        first, second = view.summarize(p), view.summarize(p, True)
        self.assertTrue(torch.equal(first[:-1], second[:len(first) - 1]))
        self.assertEqual(float(first[-1]), float(second[-1]))

    def test_unknown_opportunity_does_not_change_value_covariance(self):
        a = packet([[1., 2.], [3., 6.]])
        b = dataclasses.replace(a, prefix_opportunity=torch.zeros_like(a.prefix_opportunity),
                                prefix_opportunity_known=torch.zeros_like(a.prefix_opportunity_known))
        view = InputView(2, (0, 1))
        start = view.summary_size - 1
        self.assertTrue(torch.equal(view.summarize(a, True)[start:start + 3], view.summarize(b, True)[start:start + 3]))

    def test_exact_fifty_independent_components_gate(self):
        records = [record(q=f'q{i}', component=f'c{i}', offset=i) for i in range(49)]
        self.assertFalse(fit_transform(records, tiny_catalog()).score_eligible.any())
        records += [record(q='q49', component='c49', offset=49)]
        self.assertTrue(fit_transform(records, tiny_catalog()).score_eligible.all())
        duplicates = [record(q=f'q{i}', component='same', offset=i) for i in range(60)]
        self.assertFalse(fit_transform(duplicates, tiny_catalog()).score_eligible.any())

    def test_repeated_units_do_not_reweight_document_transform(self):
        catalog, records, transform = fixture()
        repeated = dataclasses.replace(records[0], values=records[0].values.repeat_interleave(7, 0),
                                      opportunity=records[0].opportunity.repeat_interleave(7, 0))
        modified = fit_transform([repeated, *records[1:]], catalog, min_components=1)
        self.assertTrue(torch.allclose(transform.mean, modified.mean, atol=1e-12, rtol=1e-12))
        self.assertTrue(torch.allclose(transform.scale, modified.scale, atol=1e-12, rtol=1e-12))

    def test_empty_arm_keeps_fixed_slot_without_reallocation(self):
        # Coordinator's prospective interpretation, not yet run before reset.
        records = [record(values=torch.full((1, 4), 10.)),
                   record(arm='chatgpt', values=torch.empty(0, 4)),
                   record(q='q1', values=torch.zeros(1, 4)),
                   record(q='q1', arm='chatgpt', values=torch.zeros(1, 4))]
        weights = hierarchical_unit_weights(records)
        self.assertAlmostEqual(float(weights[0].sum()), .25)
        self.assertAlmostEqual(sum(float(w.sum()) for w in weights), .75)
        transform = fit_transform(records, tiny_catalog(), min_components=1)
        self.assertTrue(torch.allclose(transform.mean, torch.full((4,), 10 / 3, dtype=torch.float64)))
        # A wholly empty answer variant must retain its declared answer slot too.
        variants = [record(values=torch.empty(0, 4)), record(arm='chatgpt', values=torch.empty(0, 4)),
                    record(answer='a1'), record(answer='a1', arm='chatgpt'),
                    record(q='q1'), record(q='q1', arm='chatgpt')]
        weights = hierarchical_unit_weights(variants)
        self.assertAlmostEqual(float(weights[2].sum()), .125)
        self.assertAlmostEqual(sum(float(w.sum()) for w in weights), .75)

    def test_dev_test_davinci_normalizer_firewall(self):
        for field, value in [('split', 'dev'), ('split', 'test'), ('arm', 'davinci')]:
            with self.assertRaises(ValueError):
                fit_transform([dataclasses.replace(record(), **{field: value})], tiny_catalog(), min_components=1)

    def test_joint_support_removes_missing_arm_answer_only(self):
        _, records, transform = fixture()
        records += [record(q='q0', answer='missing_arm')]
        plan = BalancedPlan(records, transform)
        self.assertNotIn('missing_arm', plan.by_question['q0'])
        weights = plan.exact_weights()
        self.assertAlmostEqual(sum(weights.values()), 1.)
        self.assertAlmostEqual(sum(w for (i, _), w in weights.items() if records[i].arm == 'human'), .5)

    def test_same_component_many_questions_keeps_equal_question_point(self):
        def row(q, component, arm, loss):
            return DocumentScore(q, 'a', component, 'baike', arm, loss, 1, {}, {}, 2, 1)
        rows = [row(q, component, arm, loss)
                for q, component, loss in [('q0', 'c0', 1.), ('q1', 'c0', 3.), ('q2', 'c1', 11.)]
                for arm in ('human', 'chatgpt')]
        altered = [dataclasses.replace(r, loss=r.loss - 1) for r in rows]
        result = paired_seed_comparison({s: rows for s in (1701, 1702, 1703)},
                                        {s: altered for s in (1701, 1702, 1703)}, replicates=50)
        self.assertAlmostEqual(result['baseline'], 5.)
        self.assertAlmostEqual(result['relative_gain'], .2)
        self.assertEqual(result['components'], 2)
        self.assertEqual(result['questions'], 3)
        self.assertAlmostEqual(result['interval_level'], .9833333333333333)

    def test_last_preserving_shuffle_retains_all_packet_channels(self):
        _, records, transform = fixture()
        p = make_model_packet(records[0], 4, transform)
        shuffled = _shuffle(p, 833, preserve_last=True)
        for field in dataclasses.fields(PrefixPacket):
            if field.name != 'prefix_unit_count':
                self.assertTrue(torch.equal(getattr(p, field.name)[-1], getattr(shuffled, field.name)[-1]))
        view = InputView(4, (0, 1, 2, 3))
        self.assertTrue(torch.allclose(view.summarize(p, True), view.summarize(shuffled, True), atol=1e-6, rtol=1e-6))

    def test_shuffle_averages_losses_not_predictions(self):
        catalog, records, transform = fixture()
        plan = BalancedPlan(records, transform)
        class Last(torch.nn.Module):
            def forward(self, p):
                return p.prefix_values[-1]
        model = Last()
        rows = score_model(model, plan, permutations=10)
        i = plan.record_indices[0]
        losses, prediction_losses = [], []
        for t in plan.positions[i]:
            p = make_model_packet(records[i], t, transform)
            target, observed = transform.target(records[i].values[t])
            predictions = [model(_shuffle(p, 47011 + 104729 * i + 15485863 * t + rep)) for rep in range(10)]
            losses.append(sum(float(family_loss(v, target, observed, catalog.families)[0]) for v in predictions) / 10)
            prediction_losses.append(float(family_loss(torch.stack(predictions).mean(0), target, observed, catalog.families)[0]))
        self.assertAlmostEqual(rows[0].loss, sum(losses) / len(losses), places=7)
        self.assertGreater(rows[0].loss, sum(prediction_losses) / len(prediction_losses) + 1e-5)

    def test_independent_family_and_ablation_no_value_backdoor(self):
        catalog, records, transform = fixture()
        p = make_model_packet(records[0], 4, transform)
        altered = dataclasses.replace(p, prefix_values=p.prefix_values.clone())
        altered.prefix_values[:, 2] += 1000
        model = IndependentFamilies(catalog, 4)
        self.assertTrue(torch.equal(model(p)[:2], model(altered)[:2]))
        for name in ('F1', 'Fcov', 'F2', 'F3', 'F4'):
            model = PrefixModel(name, InputView(4, (0, 1, 3)), 4)
            self.assertTrue(torch.equal(model(p), model(altered)))

    def test_question_cannot_move_components_or_sources(self):
        for field, value in [('component', 'other'), ('source', 'web')]:
            with self.assertRaises(ValueError):
                validate_cohort([record(), dataclasses.replace(record(answer='another'), **{field: value})])

    def test_interrupted_cpu_accounting_blocks_next_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = FitLedger(Path(directory) / 'ledger.jsonl')
            ledger.begin('interrupted', {})
            ledger.append({'event': 'epoch', 'run_id': 'interrupted', 'cpu_seconds_current_fit': 12.})
            self.assertEqual(ledger.consumed_cpu(), 12.)
            with self.assertRaises(RuntimeError):
                ledger.begin('later', {})

    def test_synthetic_training_reproduces_checkpoint(self):
        _, records, transform = fixture()
        dev = [dataclasses.replace(r, question='dev' + r.question, component='dev' + r.component, split='dev') for r in records]
        states = []
        with tempfile.TemporaryDirectory() as directory:
            ledger = FitLedger(Path(directory) / 'ledger.jsonl')
            for run in ('repeat_a', 'repeat_b'):
                deterministic_seed(1701)
                model = PrefixModel('F4', InputView(4, (0, 1, 2, 3)), 4, width=3)
                result = train_one(model, records, dev, transform, seed=1701, run_id=run,
                    outdir=directory, ledger=ledger, config=TrainingConfig(max_epochs=3, patience=1))
                self.assertEqual(result['event'], 'completed')
                saved = torch.load(Path(directory) / (run + '.pt'), map_location='cpu', weights_only=True)
                states.append(saved)
                for key, value in model.state_dict().items():
                    self.assertTrue(torch.equal(value, saved['state_dict'][key]))
            self.assertTrue(ledger.assert_complete(['repeat_a', 'repeat_b']))
        self.assertEqual(states[0]['epoch'], states[1]['epoch'])
        self.assertEqual(states[0]['dev_score'], states[1]['dev_score'])
        for key, value in states[0]['state_dict'].items():
            self.assertTrue(torch.equal(value, states[1]['state_dict'][key]))

    def test_pruned_outputs_and_value_paths_preserve_packet(self):
        from experimental_natural.plan import build_ladder
        catalog, records, transform = fixture()
        transform = dataclasses.replace(transform, active_values=torch.tensor([True, False, True, True]),
                                        score_eligible=torch.tensor([True, False, False, True]))
        models, brackets = build_ladder(catalog, transform=transform)
        p = make_model_packet(records[0], 4, transform)
        self.assertEqual(p.prefix_values.shape, (4, 4))
        for model in models.values():
            self.assertEqual(model.head[-1].out_features, 2)
            self.assertEqual(model.target_indices, (0, 3))
            self.assertEqual(model.view.local_size, 15)
            self.assertEqual(len(model.view.active_pairs), 6)
            output = model(p)
            self.assertEqual(float(output[1]), 0.)
            self.assertEqual(float(output[2]), 0.)
            target, observed = transform.target(records[0].values[3])
            loss, _ = family_loss(output, target, observed, catalog.families)
            loss.backward()
            self.assertTrue(torch.all(model.head[-1].weight.grad.abs().sum(1) > 0))
            self.assertTrue(torch.all(model.head[-1].bias.grad != 0))
        for bracket in brackets.values():
            self.assertLessEqual(bracket['max_relative_mismatch'], .1)

    def test_finite_failure_cannot_become_missing(self):
        _, records, transform = fixture()
        p = make_model_packet(records[0], 2, transform)
        altered = dataclasses.replace(p, prefix_values=p.prefix_values.clone())
        altered.prefix_values[0, 0] = float('inf')
        with self.assertRaises(ValueError):
            PrefixModel('F4', InputView(4, (0, 1, 2, 3)), 4)(altered)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentAudit))
    sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((ROOT / 'experimental_natural').glob('*.py'))}
    receipt = {'kind': 'independent_synthetic_audit_after_reconstruction', 'tests_run': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'success': result.wasSuccessful(),
               'natural_record_bodies_read': 0, 'natural_fits': 0,
               'synthetic_optimizer_test': 'Two tiny synthetic runs attempted by checkpoint test',
               'test_or_davinci_bodies_read': 0, 'sources': sources}
    (Path(__file__).parent / 'SYNTHETIC_AUDIT_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    sys.exit(not result.wasSuccessful())
