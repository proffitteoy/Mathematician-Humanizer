"""Original SYNTHETIC integration tests; no corpus, parser, downloads or file IO.

The two-epoch, one-seed smoke below is a test configuration. It is not the
approved 40-epoch, three-seed experiment and supplies no natural-data evidence.
Run with CPU2: OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python -m unittest
research.observed_sequence.test_fit
"""
from collections import defaultdict
from dataclasses import replace
import json
import math
import signal
import unittest
from unittest.mock import patch

import torch

from style_compiler.segmentation import segment
from research.observed_sequence.contracts import LOCAL_CHANNELS, ObservedRecord, ObservedUnit, Provenance, SensorRow, digest
from research.observed_sequence import fit
from research.observed_sequence.models import ConstantPrior, LatestState, make_model


def original_fixture(label, partition, *, units=6, bin_index=0, zero_targets=False,
                     shifted=False):
    """Newly authored source strings and invented measurements, never corpus data."""
    text = "".join(f"原創{label}{index}春雨落在紙船旁。\n" for index in range(units))
    observed = []
    for span in segment(text)[1]:
        values = [1 / 3, None] + [span.index / 10 + j / 100 for j in range(2, 68)]
        opportunities = [2.0, None] + [float(1 + span.index % 3)] * 66
        reasons = [None, "annotation_unresolved"] + [None] * 66
        if shifted:
            values[:2] = [999.0, 99.0]
            opportunities[:2] = [99.0, 9.0]
            reasons[:2] = [None, None]
        counts = [0] * 14
        if not zero_targets:
            counts[bin_index] = 1 + span.index
        observed.append(ObservedUnit(
            span.index, span.start, span.end,
            SensorRow(LOCAL_CHANNELS, tuple(values), tuple(opportunities), tuple(reasons)),
            tuple(counts), analysis_status="synthetic_fixture",
        ))
    record = ObservedRecord(
        Provenance("0" * 64, digest(text), "PRIVATE_RECORD_" + label,
                   "PRIVATE_COMPONENT_" + label, partition),
        text, tuple(observed), "1" * 64, "2" * 64,
    )
    record.validate()
    return record


def original_dataset():
    return (
        (original_fixture("青", "train", units=6, bin_index=0),
         original_fixture("赤", "train", units=8, bin_index=13),
         original_fixture("空", "train", units=5, zero_targets=True)),
        (original_fixture("紫", "development", units=7, bin_index=3, shifted=True),
         original_fixture("白", "development", units=5, zero_targets=True)),
    )


class DecodeAndPreparationTests(unittest.TestCase):
    def test_json_roundtrip_and_strict_fields(self):
        record = original_fixture("往復", "train")
        payload = json.loads(json.dumps(fit.encode_record(record), ensure_ascii=False))
        self.assertEqual(fit.decode_record(payload), record)
        self.assertEqual(fit.decode_record(fit.encode_record(record)), record)
        for extra in ({"unexpected": 1},):
            with self.assertRaisesRegex(ValueError, "fields_mismatch"):
                fit.decode_record({**payload, **extra})
        payload["units"][0]["target_counts"][0] = True
        with self.assertRaisesRegex(ValueError, "target_counts"):
            fit.decode_record(payload)

    def test_raw_text_hash_validation_is_preserved(self):
        payload = fit.encode_record(original_fixture("檢核", "train"))
        payload["text"] += "改寫"
        with self.assertRaisesRegex(ValueError, "exact_source_text"):
            fit.decode_record(payload)

    def test_train_only_frozen_zero_variance_and_unsupported_channels(self):
        train, dev = original_dataset()
        prepared = fit.prepare_train_dev(train, dev, synthetic_only=True)
        transform = prepared.transform
        self.assertEqual(transform.train_record_count, 3)
        self.assertEqual(transform.value_scale[:2], (0.0, 0.0))
        self.assertEqual(transform.opportunity_scale[:2], (0.0, 0.0))
        self.assertEqual(transform.value_support_records[:2], (3, 0))
        self.assertEqual(transform.value_observation_count[:2], (19, 0))
        self.assertEqual(transform.value_mean[0], 1 / 3)
        prefix = prepared.development.records[0].targets[0].prefix
        self.assertEqual(prefix[:, :8].tolist(), [[0, 1, 0, 1, 0, 1, 0, 1]] * 4)

    def test_shared_ledger_keeps_zero_eligible_records_out_of_loss(self):
        train, dev = original_dataset()
        prepared = fit.prepare_train_dev(train, dev, synthetic_only=True)
        self.assertEqual(prepared.train.coverage["records"], 3)
        self.assertEqual(prepared.train.coverage["eligible_records"], 2)
        self.assertEqual(prepared.train.coverage["zero_eligible_records"], 1)
        self.assertEqual(prepared.train.coverage["candidate_pairs"], 7)
        self.assertEqual(prepared.train.coverage["eligible_pairs"], 6)
        self.assertEqual(prepared.train.coverage["pair_missing_reasons"], {"zero_lexical_target": 1})
        self.assertEqual(len(prepared.train.records[2].ledger), 1)
        self.assertEqual(prepared.train.records[2].targets, ())
        self.assertEqual(prepared.train.records[0].targets[0].target_id, ("train", 0, 4))
        self.assertEqual(prepared.train.records[1].targets[-1].target_id, ("train", 1, 7))
        with self.assertRaisesRegex(ValueError, "zero_eligible_record"):
            fit._batch_loss(ConstantPrior(torch.full((14,), 1 / 14, dtype=torch.float64)),
                            (prepared.train.records[2],), 1, 1, fit._Budget())

    def test_conditional_record_equal_ce_and_prior_not_pair_or_token_weighted(self):
        train, dev = original_dataset()
        prepared = fit.prepare_train_dev(train, dev, synthetic_only=True)
        logits = torch.arange(14, dtype=torch.float64)
        prior = logits.softmax(-1)
        model = ConstantPrior(prior)
        expected = -(prior[0].log() + prior[13].log()) / 2
        actual = fit._batch_loss(model, prepared.train.eligible_records, 1, 1, fit._Budget())
        torch.testing.assert_close(actual, expected, rtol=1e-14, atol=1e-14)
        pair_equal = -(2 * prior[0].log() + 4 * prior[13].log()) / 6
        self.assertGreater(abs(actual.item() - pair_equal.item()), 0.5)
        metrics = fit._aggregate_metrics(model, prepared.train, 1, fit._Budget())
        self.assertAlmostEqual(metrics["conditional_record_equal_ce"], expected.item(), places=12)
        self.assertEqual(metrics["eligible_records"], 2)
        self.assertEqual(len(metrics["record_equal_per_bin_absolute_error"]), 14)

    def test_test_partition_rejected_before_transform_and_evaluation(self):
        train, dev = original_dataset()
        sealed = replace(dev[0], provenance=replace(dev[0].provenance, partition="test"))
        with patch.object(fit, "fit_train_transform") as transform:
            for first, second in (((sealed,), dev), (train, (sealed,))):
                with self.assertRaisesRegex(ValueError, "test_sealed"):
                    fit.prepare_train_dev(first, second, synthetic_only=True)
            transform.assert_not_called()
        prepared = fit.prepare_train_dev(train, dev, synthetic_only=True)
        sealed_split = replace(prepared.development, partition="test")
        with self.assertRaisesRegex(ValueError, "test_evaluation_not_implemented"):
            fit._aggregate_metrics(ConstantPrior(torch.full((14,), 1 / 14)), sealed_split, 0, fit._Budget())

    def test_known_group_record_and_exact_source_isolation(self):
        train, dev = original_dataset()
        for attribute in ("record_id", "component_id"):
            forged = replace(dev[0], provenance=replace(
                dev[0].provenance, **{attribute: getattr(train[0].provenance, attribute)}))
            with self.subTest(attribute=attribute), self.assertRaisesRegex(ValueError, "cross_partition"):
                fit.prepare_train_dev(train, (forged,), synthetic_only=True)
        same_source = replace(train[0], provenance=replace(
            train[0].provenance, partition="development", record_id="new", component_id="new"))
        with self.assertRaisesRegex(ValueError, "cross_partition"):
            fit.prepare_train_dev(train, (same_source,), synthetic_only=True)
        with self.assertRaisesRegex(ValueError, "duplicate_source_record"):
            fit.prepare_train_dev(train + train[:1], dev, synthetic_only=True)

    def test_profile_change_and_zero_valid_partition_stop(self):
        train, dev = original_dataset()
        changed = replace(dev[0], parser_profile_sha256="9" * 64)
        with self.assertRaisesRegex(ValueError, "profile_changed"):
            fit.prepare_train_dev(train, (changed,), synthetic_only=True)
        for first, second in (((train[2],), dev), (train, (dev[1],))):
            with self.assertRaisesRegex(ValueError, "partition_zero_valid"):
                fit.prepare_train_dev(first, second, synthetic_only=True)

    def test_natural_go_required_and_smoke_cannot_admit_natural_units(self):
        train, dev = original_dataset()
        with self.assertRaisesRegex(ValueError, "separate_root_go"):
            fit.fit_train_dev(train, dev)
        with self.assertRaisesRegex(ValueError, "separate_root_go"):
            fit.prepare_train_dev(train, dev)
        natural_label = replace(train[0], units=tuple(
            replace(unit, analysis_status="automatic_unvalidated") for unit in train[0].units))
        with self.assertRaisesRegex(ValueError, "synthetic_only_required"):
            fit.prepare_train_dev((natural_label,), dev, synthetic_only=True)

    def test_natural_api_cannot_change_fixed_experiment_configuration(self):
        # Mock dispatch only: no natural records or natural fitting in this test.
        with patch.object(fit, "_fit", return_value="dispatch_only") as call:
            self.assertEqual(fit.fit_train_dev((), (), root_approved=True), "dispatch_only")
        self.assertEqual(call.call_args.kwargs, {
            "epochs": 40, "seeds": (1729, 2718, 3141),
            "synthetic_only": False, "root_approved": True, "control_hook": None,
        })
        for epochs in (0, 3, True):
            with self.assertRaisesRegex(ValueError, "smoke_epochs"):
                fit.fit_synthetic_smoke((), (), epochs=epochs)


class SyntheticTrainingSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train, cls.dev = original_dataset()
        cls.observed_targets = defaultdict(set)
        original_predict = fit._predict

        def collect(model, target, seed, epoch):
            cls.observed_targets[type(model).__name__].add(target.target_id)
            return original_predict(model, target, seed, epoch)

        cls.rng_before = torch.random.get_rng_state().clone()
        with patch.object(fit, "_predict", side_effect=collect):
            cls.result = fit.fit_synthetic_smoke(cls.train, cls.dev, epochs=2)
        cls.replay = fit.fit_synthetic_smoke(cls.train, cls.dev, epochs=2)

    def test_all_seven_arms_use_identical_target_ids(self):
        prepared = fit.prepare_train_dev(self.train, self.dev, synthetic_only=True)
        expected = {target.target_id for split in (prepared.train, prepared.development)
                    for record in split.records for target in record.targets}
        self.assertEqual(set(self.observed_targets), {
            "ConstantPrior", "LatestState", "MaskLengthMLP", "PooledRawMLP",
            "DeepSets", "GRUPredictor", "ShuffledGRU",
        })
        for targets in self.observed_targets.values():
            self.assertEqual(targets, expected)

    def test_smoke_has_all_models_best_states_coverage_and_no_private_report(self):
        report = self.result.public_report
        self.assertEqual(report["status"], "completed_synthetic_smoke")
        self.assertIn("test_configuration", report["configuration_kind"])
        self.assertEqual(report["epochs"], 2)
        self.assertEqual(report["seeds"], [1729])
        self.assertEqual(report["resources"]["optimizer_updates"], 10)
        self.assertEqual(report["resources"]["cpu_threads"], 2)
        self.assertFalse(report["test_evaluated"])
        self.assertEqual({run.arm for run in self.result.fits}, set(fit.ARMS))
        self.assertEqual(report["coverage"]["development"]["zero_eligible_records"], 1)
        self.assertEqual(report["baselines"]["constant_prior"]["train"]["eligible_records"], 2)
        expected_prior = torch.full((14,), (1 / 14) / 3, dtype=torch.float64)
        expected_prior[0] += 1 / 3
        expected_prior[13] += 1 / 3
        torch.testing.assert_close(self.result.prior, expected_prior)
        text = json.dumps(report, ensure_ascii=False, allow_nan=False)
        self.assertNotIn("PRIVATE_RECORD_", text)
        self.assertNotIn("PRIVATE_COMPONENT_", text)
        for record in self.train + self.dev:
            self.assertNotIn(record.text, text)
            self.assertNotIn(record.provenance.source_sha256, text)
        for run in self.result.fits:
            self.assertIn(run.best_epoch, (1, 2))
            model = make_model(run.arm, seed=run.seed)
            model.load_state_dict(run.best_state)
            self.assertTrue(all(value.device.type == "cpu" for value in run.best_state.values()))
            self.assertTrue(math.isfinite(run.train_metrics["conditional_record_equal_ce"]))

    def test_deterministic_replay_preserves_rng_and_exact_best_checkpoints(self):
        torch.testing.assert_close(torch.random.get_rng_state(), self.rng_before, rtol=0, atol=0)
        for first, second in zip(self.result.fits, self.replay.fits):
            self.assertEqual(first.best_epoch, second.best_epoch)
            self.assertEqual(first.train_metrics, second.train_metrics)
            self.assertEqual(first.development_metrics, second.development_metrics)
            for key in first.best_state:
                torch.testing.assert_close(first.best_state[key], second.best_state[key], rtol=0, atol=0)
        self.assertEqual(self.result.public_report["fits"], self.replay.public_report["fits"])

    def test_earliest_epoch_wins_exact_development_ties(self):
        real_metrics = fit._aggregate_metrics

        def exact_tie(model, split, seed, budget):
            metrics = real_metrics(model, split, seed, budget)
            if split.partition == "development":
                metrics["conditional_record_equal_ce"] = 2.0
            return metrics

        with patch.object(fit, "_aggregate_metrics", side_effect=exact_tie):
            tied = fit.fit_synthetic_smoke(self.train, self.dev, epochs=2)
        self.assertTrue(all(run.best_epoch == 1 for run in tied.fits))

    def test_update_and_wall_caps_fail_closed(self):
        budget = fit._Budget()
        budget.updates = fit.MAX_UPDATES
        with self.assertRaisesRegex(fit.FitStopped, "optimizer_update_cap") as caught:
            budget.before_update()
        self.assertEqual(caught.exception.status, "stopped_resource_cap")
        self.assertEqual(caught.exception.optimizer_updates, 4800)
        budget.start -= fit.MAX_WALL_SECONDS + 1
        with self.assertRaisesRegex(fit.FitStopped, "wall_cap"):
            budget.check()
        with patch.object(fit, "MAX_UPDATES", 1), patch.object(fit, "make_model") as factory:
            with self.assertRaisesRegex(fit.FitStopped, "cap_before_training"):
                fit.fit_synthetic_smoke(self.train, self.dev)
            factory.assert_not_called()

    def test_cooperative_control_can_stop_before_any_fitting_and_restores_timer(self):
        class CallerStop(RuntimeError):
            pass

        calls = []
        def stop():
            calls.append("checked")
            raise CallerStop("caller_requested_stop")

        old_threads = torch.get_num_threads()
        old_handler = signal.getsignal(signal.SIGALRM)
        with patch.object(fit, "prepare_train_dev") as prepare:
            with self.assertRaisesRegex(CallerStop, "caller_requested_stop"):
                fit.fit_synthetic_smoke(self.train, self.dev, control_hook=stop)
            prepare.assert_not_called()
        self.assertEqual(calls, ["checked"])
        self.assertEqual(torch.get_num_threads(), old_threads)
        self.assertEqual(signal.getsignal(signal.SIGALRM), old_handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))

    def test_cooperative_control_runs_through_batches_epochs_and_evaluation(self):
        calls = []
        with patch.object(fit, "_predict", wraps=fit._predict) as predict:
            result = fit.fit_synthetic_smoke(
                self.train, self.dev, epochs=1, control_hook=lambda: calls.append(1))
        # Every prediction is preceded by a check, with additional checks for
        # evaluation records, epochs, batches, optimizer steps and boundaries.
        self.assertGreater(len(calls), predict.call_count)
        self.assertEqual(result.public_report["resources"]["optimizer_updates"], 5)


if __name__ == "__main__":
    unittest.main()
