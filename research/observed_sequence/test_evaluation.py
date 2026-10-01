"""Original synthetic evaluation tests; no natural data, fitting, parsing or IO.

Fixtures, transforms, priors and checkpoint states below are invented. Run with
the existing CPU interpreter, OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=src:.
"""
from dataclasses import FrozenInstanceError, asdict, replace
import json
import math
import random
import signal
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

from style_compiler.segmentation import segment
from research.observed_sequence import evaluation as ev, fit, models, prepare
from research.observed_sequence.contracts import (
    LOCAL_CHANNELS, ObservedRecord, ObservedUnit, Provenance, SensorRow, digest,
)
from research.observed_sequence.diagnostics import endpoint_flags


def invented_record(label, *, units=6, target_bin=0, zero=False, component=None):
    """Newly authored strings with invented sensors; never a natural fixture."""
    text = "".join(f"紙月{label}{index}在青色盒裡發芽。\n" for index in range(units))
    rows = []
    for span in segment(text)[1]:
        values = tuple(None if j == 1 else (span.index + 1) / (j + 2) for j in range(68))
        opportunities = tuple(None if j == 1 else float(2 + span.index % 3) for j in range(68))
        reasons = tuple("annotation_unresolved" if j == 1 else None for j in range(68))
        counts = [0] * 14
        if not zero:
            counts[target_bin] = span.index + 1
        rows.append(ObservedUnit(span.index, span.start, span.end,
                                SensorRow(LOCAL_CHANNELS, values, opportunities, reasons),
                                tuple(counts), analysis_status="synthetic_fixture"))
    result = ObservedRecord(
        Provenance("a" * 64, digest(text), "PRIVATE_RECORD_" + label,
                   "PRIVATE_COMPONENT_" + (component or label), "test"),
        text, tuple(rows), "b" * 64, "c" * 64)
    result.validate()
    return result


def invented_transform():
    """Literal frozen coefficients; no train records or transform estimation."""
    zeros, ones, support = (0.0,) * 68, (1.0,) * 68, (1,) * 68
    return prepare.TrainTransform(zeros, ones, zeros, ones, 1, support, support,
                                  support, support, zeros, zeros, zeros, zeros)


def invented_checkpoints(*, bias_only=False):
    states = {}
    for arm in ev.ARMS:
        for index, seed in enumerate(ev.SEEDS):
            model = models.make_model(arm, seed=seed)
            state = {key: value.detach().clone() for key, value in model.state_dict().items()}
            if bias_only:
                state = {key: torch.zeros_like(value) for key, value in state.items()}
                key = "head.bias" if arm in ("gru", "shuffled_gru") else "head.2.bias"
                state[key][0] = (5.0, -4.0, 1.0)[index] if arm == "deepsets" else (0.2, 0.5, 0.8)[index]
                state[key][13] = (0.0, 3.0, -1.0)[index]
            states[(arm, seed)] = state
    return states


def predict(records, **kwargs):
    return ev.predict_frozen_test(records, transform=kwargs.pop("transform", invented_transform()),
                                  prior=kwargs.pop("prior", torch.full((14,), 1 / 14, dtype=torch.float64)),
                                  checkpoints=kwargs.pop("checkpoints", invented_checkpoints()),
                                  synthetic_only=True, **kwargs)


class FrozenInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = (invented_record("一", units=7, target_bin=0),
                       invented_record("二", units=5, target_bin=13),
                       invented_record("空", units=5, zero=True))
        cls.states, cls.transform = invented_checkpoints(), invented_transform()
        cls.prior = torch.arange(1, 15, dtype=torch.float64)
        cls.prior = cls.prior / cls.prior.sum()
        cls.result = predict(cls.records, checkpoints=cls.states, transform=cls.transform, prior=cls.prior)

    def test_exact_seventeen_comparators_plus_three_separate_perturbations(self):
        self.assertEqual(tuple((s.arm, s.seed) for s in self.result.series), ev.COMPARATOR_KEYS + ev.DIAGNOSTIC_KEYS)
        self.assertEqual(sum(not s.diagnostic_only for s in self.result.series), 17)
        self.assertEqual(sum(s.diagnostic_only for s in self.result.series), 3)
        for arm in ev.ARMS:
            self.assertEqual(tuple(s.seed for s in self.result.series if s.arm == arm), ev.SEEDS)

    def test_same_ledger_zero_records_and_private_immutable_details(self):
        expected = ((("test", 0, 4), ("test", 0, 5), ("test", 0, 6)), (("test", 1, 4),), ())
        for series in self.result.series:
            self.assertEqual(tuple(tuple(t.target_id for t in r.targets) for r in series.records), expected)
            self.assertIsNone(series.records[2].ce)
            self.assertIsNone(series.records[2].per_bin_absolute_error)
            self.assertEqual(series.records[2].targets, ())
        coverage = self.result.coverage.as_dict()
        self.assertEqual(coverage["records"], 3)
        self.assertEqual(coverage["eligible_records"], 2)
        self.assertEqual(coverage["zero_eligible_records"], 1)
        self.assertEqual(coverage["candidate_pairs"], 5)
        self.assertEqual(coverage["eligible_pairs"], 4)
        self.assertEqual(coverage["pair_missing_reasons"], {"zero_lexical_target": 1})
        self.assertEqual(coverage["channel_missing_reason_counts"][1], {"annotation_unresolved": 17})
        self.assertEqual(coverage["channel_unknown_opportunity_counts"][1], 17)
        self.assertEqual(coverage["channel_present_counts"][0], 17)
        self.assertNotIn("PRIVATE_RECORD", repr(self.result))
        self.assertNotIn(self.records[0].text, repr(self.result))
        self.assertNotIn(self.records[0].text, json.dumps(asdict(self.result), ensure_ascii=False))
        with self.assertRaises(FrozenInstanceError):
            self.result.status = "modified"

    def test_no_transform_or_prior_fitting_and_no_parameter_changes(self):
        before = {key: {name: tensor.clone() for name, tensor in state.items()}
                  for key, state in self.states.items()}
        prior_before = self.prior.clone()
        with patch.object(prepare, "fit_train_transform", side_effect=AssertionError("fit forbidden")), \
             patch.object(fit, "fit_train_transform", side_effect=AssertionError("fit forbidden")), \
             patch.object(models, "record_equal_smoothed_prior", side_effect=AssertionError("prior forbidden")), \
             patch.object(fit, "record_equal_smoothed_prior", side_effect=AssertionError("prior forbidden")), \
             patch.object(torch.optim.AdamW, "step", side_effect=AssertionError("optimizer forbidden")):
            result = predict(self.records, checkpoints=self.states, transform=self.transform, prior=self.prior)
            self.assertEqual(result.series, self.result.series)
        for key, state in self.states.items():
            for name, tensor in state.items():
                torch.testing.assert_close(tensor, before[key][name], rtol=0, atol=0)
        torch.testing.assert_close(self.prior, prior_before, rtol=0, atol=0)

    def test_reject_train_and_development_before_encoding_or_model_creation(self):
        with patch.object(ev, "_models") as builder, patch.object(prepare.TrainTransform, "encode") as encoder:
            for partition in ("train", "development"):
                wrong = replace(self.records[0], provenance=replace(self.records[0].provenance, partition=partition))
                with self.assertRaisesRegex(ValueError, "test_only_entry"):
                    predict((wrong,), checkpoints=self.states)
            builder.assert_not_called()
            encoder.assert_not_called()

    def test_natural_entry_needs_go_and_synthetic_entry_cannot_admit_natural_labels(self):
        with self.assertRaisesRegex(ValueError, "separate_root_go"):
            ev.predict_frozen_test((), transform=self.transform, prior=self.prior, checkpoints=self.states)
        relabeled = replace(self.records[0], units=tuple(
            replace(u, analysis_status="automatic_unvalidated") for u in self.records[0].units))
        with self.assertRaisesRegex(ValueError, "synthetic_only_required"):
            predict((relabeled,), checkpoints=self.states)
        with self.assertRaisesRegex(ValueError, "approval_type"):
            predict((), checkpoints=self.states, root_approved=1)

    def test_checkpoint_set_keys_dtypes_shapes_and_finite_values_are_strict(self):
        wrong = dict(self.states)
        wrong.pop(("gru", ev.SEEDS[2]))
        for states in (wrong, {**self.states, ("gru", 999): self.states[("gru", ev.SEEDS[0])]},
                       {(arm, ev.SEEDS[0]): state for (arm, seed), state in self.states.items()}):
            with self.assertRaisesRegex(ValueError, "exact_fifteen"):
                predict((), checkpoints=states)
        key = ("deepsets", ev.SEEDS[0])
        name = next(iter(self.states[key]))
        for value, reason in ((torch.ones(1), "shape_or_dtype"),
                              (self.states[key][name].double(), "shape_or_dtype"),
                              (torch.full_like(self.states[key][name], math.nan), "nonfinite_checkpoint")):
            with self.assertRaisesRegex(ValueError, reason):
                predict((), checkpoints={**self.states, key: {**self.states[key], name: value}})
        bad = {**self.states[key], "unapproved.extra": torch.ones(1)}
        with self.assertRaisesRegex(ValueError, "checkpoint_state_keys"):
            predict((), checkpoints={**self.states, key: bad})

    def test_no_source_future_or_target_measurement_in_model_inputs(self):
        first = invented_record("遮蔽", units=5)
        second = invented_record("遮蔽", units=8)
        units = list(second.units)
        for index in range(4, len(units)):
            unit = units[index]
            units[index] = replace(unit, row=replace(unit.row, values=(999.0,) * 68,
                                   opportunities=(999.0,) * 68, missing_reasons=(None,) * 68),
                                   target_counts=(0,) * 13 + (9999,))
        second = replace(second, units=tuple(units))
        a, b = predict((first,), checkpoints=self.states), predict((second,), checkpoints=self.states)
        for sa, sb in zip(a.series, b.series):
            # Same already visible prefix, different target/suffix/record length.
            self.assertEqual(sa.records[0].targets[0].logits, sb.records[0].targets[0].logits)
            self.assertNotEqual(sa.records[0].targets[0].target_composition,
                                sb.records[0].targets[0].target_composition)
        seen = []
        encode = prepare.TrainTransform.encode
        def recording_encode(transform, row):
            seen.append(row)
            return encode(transform, row)
        with patch.object(prepare.TrainTransform, "encode", recording_encode):
            predict((first,), checkpoints=self.states)
        self.assertEqual(seen, [u.row for u in first.units[:4]])
        self.assertNotIn(first.units[4].row, seen)

    def test_existing_predict_epoch_zero_and_distinct_perturbation_schedule(self):
        calls, schedules = [], []
        original_predict, original_schedule = ev._predict, ev._scheduled_seed
        def recording_predict(model, target, seed, epoch):
            calls.append((type(model).__name__, target.target_id, seed, epoch))
            return original_predict(model, target, seed, epoch)
        def recording_schedule(seed, purpose, *coordinates):
            schedules.append((seed, purpose, coordinates))
            return original_schedule(seed, purpose, *coordinates)
        with patch.object(ev, "_predict", recording_predict), patch.object(ev, "_scheduled_seed", recording_schedule):
            result = predict((self.records[1],), checkpoints=self.states)
        self.assertEqual(len(calls), 17)
        self.assertTrue(all(call[3] == 0 for call in calls))
        self.assertEqual(schedules, [(seed, ev.PERTURBATION_PURPOSE, (0, "test", 0, 4)) for seed in ev.SEEDS])
        self.assertEqual(sum(s.arm == "shuffled_gru" for s in result.series), 3)
        self.assertEqual(sum(s.arm == ev.PERTURBATION_ARM for s in result.series), 3)

    def test_baselines_and_conditional_record_weighting_not_target_or_token_weighting(self):
        summary = ev.summarize_predictions(self.result).public_report
        constant = next(m for m in summary["comparator_metrics"] if m["arm"] == "constant_prior")
        expected = -(self.prior[0].log().item() + self.prior[13].log().item()) / 2
        self.assertAlmostEqual(constant["conditional_record_equal_ce"], expected, places=12)
        pair_mean = -(3 * self.prior[0].log().item() + self.prior[13].log().item()) / 4
        self.assertGreater(abs(pair_mean - expected), 0.1)
        latest = next(s for s in self.result.series if s.arm == "latest_state")
        q = torch.zeros(14, dtype=torch.float64)
        q[0] = 1
        expected_latest = (0.9 * q + 0.1 * self.prior)
        torch.testing.assert_close(torch.tensor(latest.records[0].targets[0].probabilities),
                                   expected_latest.float(), rtol=1e-6, atol=1e-7)
        self.assertEqual(len(constant["record_equal_per_bin_absolute_error"]), 14)

    def test_failed_units_keep_ledger_and_cannot_be_bridged(self):
        record = invented_record("失敗", units=10)
        units = list(record.units)
        units[4] = replace(units[4], status="failed", failure_reason="parse_failed", target_counts=None,
                           row=SensorRow(LOCAL_CHANNELS, (None,) * 68, (None,) * 68, ("parse_failed",) * 68))
        result = predict((replace(record, units=tuple(units)),), checkpoints=self.states)
        coverage = result.coverage.as_dict()
        self.assertEqual(coverage["unit_failure_reason_counts"], {"parse_failed": 1})
        self.assertEqual(coverage["pair_missing_reasons"],
                         {"insufficient_contiguous_prefix": 4, "parse_failed": 1})
        self.assertEqual(result.records[0].ledger[-1].input_indices, (5, 6, 7, 8))
        for series in result.series:
            self.assertEqual(tuple(t.target_id for t in series.records[0].targets), (("test", 0, 9),))

    def test_model_failure_never_creates_model_specific_scoring_subset(self):
        with patch.object(ev, "_predict", return_value=torch.full((14,), math.nan)):
            with self.assertRaisesRegex(ValueError, "finite"):
                predict((self.records[0],), checkpoints=self.states)
        with patch.object(ev, "_predict", side_effect=RuntimeError("injected_model_failure")):
            with self.assertRaisesRegex(RuntimeError, "injected_model_failure"):
                predict((self.records[0],), checkpoints=self.states)

    def test_zero_eligible_split_returns_coverage_and_undefined_metrics(self):
        result = predict((self.records[2],), checkpoints=self.states)
        report = ev.summarize_predictions(result, speaker_keys={0: None}).public_report
        self.assertEqual(result.status, "stopped_zero_eligible_records")
        self.assertEqual(report["status"], "stopped_zero_eligible_records")
        self.assertEqual(report["coverage"]["zero_eligible_records"], 1)
        self.assertIsNone(report["paired_comparison"]["seed_averaged_record_delta"])
        for metric in report["comparator_metrics"]:
            self.assertIsNone(metric["conditional_record_equal_ce"])
        self.assertIsNone(report["paired_comparison"]["component_bootstrap"]["interval"])
        self.assertEqual(report["paired_comparison"]["component_bootstrap"]["eligible_clusters"], 0)

    def test_summary_safe_report_excludes_ids_and_unknown_public_labels(self):
        report = ev.summarize_predictions(self.result,
                                          page_types={0: "talk", 1: "PRIVATE_PAGE_NAME", 2: "help_talk"},
                                          speaker_keys={0: "PRIVATE_SPEAKER", 1: "PRIVATE_SPEAKER", 2: None})
        public = json.dumps(report.public_report, ensure_ascii=False, allow_nan=False)
        self.assertNotIn("PRIVATE", public)
        self.assertNotIn(self.records[0].text, public)
        self.assertIn("other_or_unknown", public)
        self.assertIn("help_talk", public)
        self.assertIn("PRIVATE_RECORD_", json.dumps(report.private_details))


class PosthocAndBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = (invented_record("春", units=7), invented_record("秋", units=5, target_bin=13))
        cls.result = predict(cls.records, checkpoints=invented_checkpoints(bias_only=True))

    def test_seed_average_is_average_of_losses_not_probability_ensemble(self):
        report = ev.summarize_predictions(self.result)
        series = [s for s in self.result.series if s.arm == "deepsets"]
        direct = math.fsum(r.ce for s in series for r in s.records) / 6
        metric = next(m for m in report.public_report["learned_arm_seed_average_metrics"] if m["arm"] == "deepsets")
        self.assertAlmostEqual(metric["conditional_record_equal_ce"], direct, places=12)
        ensemble_record_losses = []
        for ordinal in range(2):
            losses = []
            for index, target in enumerate(series[0].records[ordinal].targets):
                probabilities = [math.fsum(s.records[ordinal].targets[index].probabilities[j] for s in series) / 3
                                 for j in range(14)]
                losses.append(-math.fsum(q * math.log(p) for q, p in zip(target.target_composition, probabilities)))
            ensemble_record_losses.append(math.fsum(losses) / len(losses))
        ensemble_ce = math.fsum(ensemble_record_losses) / 2
        self.assertGreater(direct - ensemble_ce, 0.5)
        self.assertFalse(report.public_report["probability_ensemble_evaluated"])
        self.assertEqual(len(report.public_report["paired_comparison"]["seedwise"]), 3)
        for row in report.private_details["paired_record_deltas"]:
            self.assertAlmostEqual(row["seed_averaged_delta"], math.fsum(row["seedwise_delta"]) / 3, places=12)

    def test_summary_only_posthoc_no_model_call_and_endpoint_conditioning(self):
        flags = {t.target_id: endpoint_flags(self.records[r.ordinal], t.target_id[2])
                 for r in self.result.series[0].records for t in r.targets}
        with patch.object(ev, "_predict", side_effect=AssertionError("predictions already frozen")), \
             patch.object(ev, "make_model", side_effect=AssertionError("no new models")):
            report = ev.summarize_predictions(self.result, endpoint_flags=flags,
                                              page_types={0: "talk", 1: "user_talk"}).public_report
        baseline = report["posthoc_endpoint_metrics"][0]["buckets"]
        self.assertEqual(baseline["all"]["eligible_pairs"], 4)
        self.assertEqual(baseline["interior"]["eligible_pairs"], 2)
        self.assertEqual(baseline["terminal_source_unit"]["eligible_pairs"], 2)
        self.assertEqual(baseline["plain_character_extensible"]["eligible_pairs"], 0)
        self.assertIsNone(baseline["plain_character_extensible"]["conditional_record_equal_ce"])
        self.assertFalse(report["endpoint_flags_in_model_inputs"])

    def test_posthoc_mapping_coverage_and_types_fail_closed(self):
        for kwargs, reason in (({"speaker_keys": {0: "x"}}, "speaker_mapping"),
                               ({"page_types": {0: "talk"}}, "page_type_mapping"),
                               ({"endpoint_flags": {}}, "endpoint_mapping"),
                               ({"speaker_keys": {0: 1, 1: "x"}}, "speaker_keys")):
            with self.assertRaisesRegex(ValueError, reason):
                ev.summarize_predictions(self.result, **kwargs)
        flags = {t.target_id: {name: False for name in ev.ENDPOINT_FIELDS}
                 for r in self.result.series[0].records for t in r.targets}
        key = next(iter(flags))
        flags[key]["plain_character_extensible"] = True
        with self.assertRaisesRegex(ValueError, "extensibility_requires_terminal"):
            ev.summarize_predictions(self.result, endpoint_flags=flags)

    def test_bootstrap_fixed_2000_replicates_and_deterministic_grouping(self):
        values = {0: -1.0, 1: 2.0, 2: 4.0, 3: 10.0}
        groups = {0: ("work", "b"), 1: ("work", "b"), 2: ("work", "a"), 3: ("work", "c")}
        a, draws_a = ev._grouped_bootstrap(values, groups, seed=ev.COMPONENT_BOOTSTRAP_SEED, budget=ev._Budget())
        b, draws_b = ev._grouped_bootstrap(dict(reversed(list(values.items()))),
                                          dict(reversed(list(groups.items()))),
                                          seed=ev.COMPONENT_BOOTSTRAP_SEED, budget=ev._Budget())
        self.assertEqual(a, b)
        self.assertEqual(draws_a, draws_b)
        self.assertEqual(len(draws_a), 2000)
        self.assertEqual(a["replicates"], 2000)
        self.assertEqual(a["eligible_clusters"], 3)
        self.assertEqual(a["point_estimate"], 3.75)
        ordered = sorted(draws_a)
        self.assertEqual(a["interval"], (ev._percentile(ordered, .025), ev._percentile(ordered, .975)))
        self.assertNotIn("p_value", a)

    def test_group_resampling_preserves_every_record_and_multiplicity_not_cluster_means(self):
        values = {0: 0.0, 1: 2.0, 2: 10.0}
        groups = {0: ("work", "a"), 1: ("work", "a"), 2: ("work", "b")}
        keys = sorted(set(groups.values()), key=ev._group_sort_key)
        picks = [keys.index(("work", "a")), keys.index(("work", "b"))] * 2000
        with patch.object(ev.random.Random, "randrange", side_effect=picks):
            report, samples = ev._grouped_bootstrap(values, groups, seed=ev.COMPONENT_BOOTSTRAP_SEED,
                                                   budget=ev._Budget())
        self.assertEqual(set(samples), {4.0})  # (0 + 2 + 10) / 3, not (1 + 10) / 2
        self.assertEqual(report["interval"], (4.0, 4.0))
        picks = [keys.index(("work", "a"))] * 4000
        with patch.object(ev.random.Random, "randrange", side_effect=picks):
            _, samples = ev._grouped_bootstrap(values, groups, seed=ev.COMPONENT_BOOTSTRAP_SEED,
                                              budget=ev._Budget())
        self.assertEqual(set(samples), {1.0})  # Both copies retain both record losses.

    def test_insufficient_clusters_undefined_not_zero_width_inferred_evidence(self):
        for values, groups in (({}, {}), ({0: 2.0, 1: 8.0}, {0: ("work", "a"), 1: ("work", "a")})):
            report, samples = ev._grouped_bootstrap(values, groups, seed=ev.SPEAKER_BOOTSTRAP_SEED,
                                                   budget=ev._Budget())
            self.assertIsNone(report["interval"])
            self.assertEqual(samples, ())
            self.assertEqual(report["status"], "undefined_fewer_than_two_clusters")

    def test_speaker_missing_keys_are_separate_singletons(self):
        together = ev.summarize_predictions(self.result, speaker_keys={0: "one", 1: "one"})
        separate = ev.summarize_predictions(self.result, speaker_keys={0: None, 1: ""})
        cluster_a = together.public_report["paired_comparison"]["speaker_key_cluster_sensitivity"]
        cluster_b = separate.public_report["paired_comparison"]["speaker_key_cluster_sensitivity"]
        self.assertEqual(cluster_a["eligible_clusters"], 1)
        self.assertIsNone(cluster_a["interval"])
        self.assertEqual(cluster_b["eligible_clusters"], 2)
        self.assertEqual(cluster_b["missing_key_singleton_records"], 2)
        self.assertIsNotNone(cluster_b["interval"])
        self.assertEqual(cluster_b["seed"], ev.SPEAKER_BOOTSTRAP_SEED)

    def test_changed_series_or_target_ledger_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact_frozen_prediction_series"):
            ev.summarize_predictions(replace(self.result, series=self.result.series[:-1]))
        series = self.result.series[0]
        record = series.records[0]
        changed = replace(series, records=(replace(record, targets=record.targets[:-1]),) + series.records[1:])
        with self.assertRaisesRegex(ValueError, "target_ledger_mismatch"):
            ev.summarize_predictions(replace(self.result, series=(changed,) + self.result.series[1:]))


class ResourceAndControlTests(unittest.TestCase):
    def test_control_hook_before_work_and_at_safe_boundaries_propagates_and_restores(self):
        class StopHere(Exception):
            pass
        with patch.object(ev, "_models") as builder:
            with self.assertRaises(StopHere):
                predict((), control_hook=lambda: (_ for _ in ()).throw(StopHere()))
            builder.assert_not_called()
        old_threads, old_handler = torch.get_num_threads(), signal.getsignal(signal.SIGALRM)
        count = 0
        def hook():
            nonlocal count
            count += 1
            if count == 6:
                raise StopHere()
        with self.assertRaises(StopHere):
            predict((invented_record("停止"),), control_hook=hook)
        self.assertEqual(count, 6)
        self.assertEqual(torch.get_num_threads(), old_threads)
        self.assertEqual(signal.getsignal(signal.SIGALRM), old_handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))

    def test_wall_and_rss_guards(self):
        budget = ev._Budget(previous_wall_seconds=ev.MAX_WALL_SECONDS)
        with self.assertRaisesRegex(ev.EvaluationStopped, "wall_cap"):
            budget.check()
        with patch.object(ev.resource, "getrusage", return_value=SimpleNamespace(ru_maxrss=ev.MAX_RSS_KIB + 1)):
            with self.assertRaisesRegex(ev.EvaluationStopped, "rss_cap"):
                ev._Budget().check()
        result = predict((invented_record("時限", units=5),))
        with self.assertRaisesRegex(ev.EvaluationStopped, "wall_cap"):
            ev.summarize_predictions(replace(result, prediction_wall_seconds=ev.MAX_WALL_SECONDS))

    def test_first_blocking_control_hook_is_inside_wall_interrupt(self):
        old_threads, old_handler = torch.get_num_threads(), signal.getsignal(signal.SIGALRM)
        with patch.object(ev, "MAX_WALL_SECONDS", 0.03):
            with self.assertRaisesRegex(ev.EvaluationStopped, "wall_cap"):
                with ev._bounded_cpu_run(ev._Budget(lambda: time.sleep(0.3))):
                    self.fail("blocking control hook should have been interrupted")
        self.assertEqual(torch.get_num_threads(), old_threads)
        self.assertEqual(signal.getsignal(signal.SIGALRM), old_handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))

    def test_bootstrap_control_hook_can_interrupt(self):
        count = 0
        def hook():
            nonlocal count
            count += 1
            if count == 10:
                raise RuntimeError("caller_paused")
        with self.assertRaisesRegex(RuntimeError, "caller_paused"):
            ev._grouped_bootstrap({0: 1.0, 1: 2.0}, {0: ("work", "a"), 1: ("work", "b")},
                                  seed=ev.COMPONENT_BOOTSTRAP_SEED, budget=ev._Budget(hook))
        self.assertEqual(count, 10)

    def test_random_states_preserved(self):
        before = torch.random.get_rng_state().clone()
        python_before = random.getstate()
        result = predict((invented_record("隨機一", units=5), invented_record("隨機二", units=5)))
        ev.summarize_predictions(result, speaker_keys={0: None, 1: None})
        torch.testing.assert_close(torch.random.get_rng_state(), before, rtol=0, atol=0)
        self.assertEqual(random.getstate(), python_before)


if __name__ == "__main__":
    unittest.main()
