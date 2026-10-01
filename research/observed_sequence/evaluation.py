"""Caller-fed, frozen TEST inference and separate posthoc summaries.

There is no file loader, parser, transform/prior estimator, optimizer, download,
or work at import. The caller must separately verify the approved artifact hashes
and authorize a natural test opening. A True flag records approval, not grants it.

First call predict_frozen_test and privately persist/hash its immutable result.
Only afterwards compute endpoint flags and call summarize_predictions.
Page/speaker metadata may be read earlier for exact extraction joins, but is
consumed only by the posthoc summary and never passed into a model. Stage two never calls a model. Neither the predictions
object nor private_details is a public report. Source text is not retained.

The main statistic averages three separately scored seed losses; no probability
ensemble is evaluated. Both bootstrap intervals are descriptive, conditional on
these fixed models and eligible records, with no p-value or population claim.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
import hashlib
import json
import math
import random
import resource
import signal
import threading
import time

import torch
from torch import Tensor

from .contracts import ObservedRecord, PredictionPair, finite, require
from .fit import ARMS, SEEDS, PreparedTarget, _predict, _scheduled_seed
from .models import ConstantPrior, LatestState, make_model, shuffle_prefix, soft_target_cross_entropy
from .prepare import TrainTransform, pair_ledger, prefix_lengths

MAX_WALL_SECONDS = 1800
MAX_RSS_KIB = 3 * 1024**2
BOOTSTRAP_REPLICATES = 2000
COMPONENT_BOOTSTRAP_SEED = 2026100101
SPEAKER_BOOTSTRAP_SEED = 2026100102
BOOTSTRAP_HASH_DOMAIN = "observed-sequence-test-bootstrap/v1"
PERCENTILE_PROBABILITIES = (0.025, 0.975)
PERTURBATION_PURPOSE = "test_time_order_perturbation"
PERTURBATION_ARM = "gru_test_time_order_perturbation"
BASELINES = ("constant_prior", "latest_state")
COMPARATOR_KEYS = tuple((arm, None) for arm in BASELINES) + tuple(
    (arm, seed) for arm in ARMS for seed in SEEDS)
DIAGNOSTIC_KEYS = tuple((PERTURBATION_ARM, seed) for seed in SEEDS)
ENDPOINT_FIELDS = ("terminal_source_unit", "plain_character_extensible",
                   "closer_or_terminal_extensible")
ENDPOINT_BUCKETS = ("all", "interior", *ENDPOINT_FIELDS)
PUBLIC_PAGE_TYPES = frozenset(("talk", "user_talk", "wikipedia_talk", "template_talk",
                               "article", "help_talk", "other_or_unknown"))


class EvaluationStopped(RuntimeError):
    """No partial prediction object is returned after a resource/control stop."""

    def __init__(self, reason):
        self.status = "stopped_resource_cap"
        self.reason = reason
        super().__init__(reason)


class _Budget:
    def __init__(self, control_hook=None, *, previous_wall_seconds=0.0):
        require(control_hook is None or callable(control_hook), "control_hook_must_be_callable")
        self.start = time.monotonic()
        self.previous = previous_wall_seconds
        self.control_hook = control_hook

    @property
    def elapsed(self):
        return self.previous + time.monotonic() - self.start

    def check(self):
        if self.control_hook is not None:
            self.control_hook()
        if self.elapsed >= MAX_WALL_SECONDS:
            raise EvaluationStopped("test_evaluation_wall_cap")
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > MAX_RSS_KIB:
            raise EvaluationStopped("test_evaluation_rss_cap")


@contextmanager
def _bounded_cpu_run(budget):
    """CPU2 and a wall timer, plus checked RSS; not a kernel memory sandbox.

    Stage-two allowance subtracts stage-one compute time. The caller must bound
    its own persistence/metadata IO between stages within its outer run budget.
    """
    require(threading.current_thread() is threading.main_thread(), "test_requires_main_thread")
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), "caller_timer_already_armed")
    # Install the interrupt before invoking a possibly blocking pause hook.
    if budget.elapsed >= MAX_WALL_SECONDS:
        raise EvaluationStopped("test_evaluation_wall_cap")
    if torch.get_num_interop_threads() != 2:
        try:
            torch.set_num_interop_threads(2)
        except RuntimeError:
            raise RuntimeError("cpu_interop_requires_fresh_process_with_two_threads") from None
    old_threads, old_handler = torch.get_num_threads(), signal.getsignal(signal.SIGALRM)

    def timeout(signum, frame):
        raise EvaluationStopped("test_evaluation_wall_cap")

    torch.set_num_threads(2)
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(1e-6, MAX_WALL_SECONDS - budget.elapsed))
    try:
        budget.check()
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        torch.set_num_threads(old_threads)


@dataclass(frozen=True)
class TestCoverage:
    records: int
    eligible_records: int
    units: int
    candidate_pairs: int
    eligible_pairs: int
    unit_status_counts: tuple[tuple[str, int], ...]
    unit_failure_reason_counts: tuple[tuple[str, int], ...]
    pair_missing_reasons: tuple[tuple[str, int], ...]
    channel_present_counts: tuple[int, ...]
    channel_unknown_opportunity_counts: tuple[int, ...]
    channel_missing_reason_counts: tuple[tuple[tuple[str, int], ...], ...]

    def as_dict(self):
        return {
            "records": self.records, "eligible_records": self.eligible_records,
            "zero_eligible_records": self.records - self.eligible_records,
            "units": self.units, "candidate_pairs": self.candidate_pairs,
            "eligible_pairs": self.eligible_pairs,
            "unit_status_counts": dict(self.unit_status_counts),
            "unit_failure_reason_counts": dict(self.unit_failure_reason_counts),
            "pair_missing_reasons": dict(self.pair_missing_reasons),
            "channel_present_counts": list(self.channel_present_counts),
            "channel_unknown_opportunity_counts": list(self.channel_unknown_opportunity_counts),
            "channel_missing_reason_counts": [dict(x) for x in self.channel_missing_reason_counts],
        }


@dataclass(frozen=True)
class TestRecordLedger:
    ordinal: int
    record_id: str = field(repr=False)
    component_id: str = field(repr=False)
    ledger: tuple[PredictionPair, ...] = field(repr=False)


@dataclass(frozen=True)
class TargetPrediction:
    target_id: tuple[str, int, int] = field(repr=False)
    target_composition: tuple[float, ...] = field(repr=False)
    logits: tuple[float, ...] = field(repr=False)
    probabilities: tuple[float, ...] = field(repr=False)
    ce: float = field(repr=False)
    per_bin_absolute_error: tuple[float, ...] = field(repr=False)


@dataclass(frozen=True)
class RecordPrediction:
    ordinal: int
    targets: tuple[TargetPrediction, ...] = field(repr=False)
    ce: float | None = field(repr=False)
    per_bin_absolute_error: tuple[float, ...] | None = field(repr=False)


@dataclass(frozen=True)
class PredictionSeries:
    arm: str
    seed: int | None
    diagnostic_only: bool
    records: tuple[RecordPrediction, ...] = field(repr=False)


@dataclass(frozen=True)
class FrozenTestPredictions:
    status: str
    synthetic_only: bool
    coverage: TestCoverage
    records: tuple[TestRecordLedger, ...] = field(repr=False)
    series: tuple[PredictionSeries, ...] = field(repr=False)
    prediction_wall_seconds: float = field(repr=False)


@dataclass(frozen=True)
class TestEvaluationSummary:
    public_report: dict
    private_details: dict = field(repr=False)


def _validate_transform(transform):
    require(type(transform) is TrainTransform, "frozen_train_transform_required")
    require(type(transform.train_record_count) is int and transform.train_record_count > 0,
            "invalid_frozen_transform_support")
    for item in fields(TrainTransform):
        if item.name == "train_record_count":
            continue
        values = getattr(transform, item.name)
        require(type(values) is tuple and len(values) == 68, "frozen_transform_shape")
        require(all(finite(x) for x in values), "nonfinite_frozen_transform")
        if "support_records" in item.name or "observation_count" in item.name:
            require(all(type(x) is int and x >= 0 for x in values), "frozen_transform_count")
        if "scale" in item.name:
            require(all(x >= 0 for x in values), "frozen_transform_scale")


def _models(checkpoints, prior, budget):
    require(isinstance(checkpoints, Mapping), "checkpoint_mapping_required")
    expected = {(arm, seed) for arm in ARMS for seed in SEEDS}
    require(set(checkpoints) == expected and len(checkpoints) == 15,
            "exact_fifteen_frozen_checkpoints_required")
    # Baseline constructors validate CPU, shape, finiteness and positivity.
    result = [("constant_prior", None, ConstantPrior(prior)),
              ("latest_state", None, LatestState(prior))]
    for arm in ARMS:
        for seed in SEEDS:
            budget.check()
            model = make_model(arm, seed=seed)
            state, shapes = checkpoints[(arm, seed)], model.state_dict()
            require(isinstance(state, Mapping) and set(state) == set(shapes),
                    "checkpoint_state_keys")
            copied = {}
            for name, value in state.items():
                require(isinstance(value, Tensor) and value.device.type == "cpu",
                        "checkpoint_cpu_tensor_required")
                require(value.shape == shapes[name].shape and value.dtype == shapes[name].dtype,
                        "checkpoint_shape_or_dtype")
                require(torch.isfinite(value).all().item(), "nonfinite_checkpoint")
                copied[name] = value.detach().clone()
            model.load_state_dict(copied, strict=True)
            model.requires_grad_(False)
            result.append((arm, seed, model))
    return tuple(result)


def _prepare(records, transform, budget):
    ledgers, prepared, pair_reasons, statuses, failures = [], [], Counter(), Counter(), Counter()
    present, unknown, missing = [0] * 68, [0] * 68, [Counter() for _ in range(68)]
    unit_count = 0
    for ordinal, record in enumerate(records):
        budget.check()
        ledger = pair_ledger(record)
        ledgers.append(TestRecordLedger(ordinal, record.provenance.record_id,
                                        record.provenance.component_id, ledger))
        pair_reasons.update(p.missing_reason for p in ledger if not p.eligible)
        encoded, compositions = {}, {}
        targets = []
        for pair in ledger:
            budget.check()
            if not pair.eligible:
                continue
            # Only visible rows are encoded; neither a target row nor a later
            # row is passed to transform.encode for this prediction opportunity.
            for index in pair.input_indices:
                if index not in encoded:
                    unit = record.units[index]
                    encoded[index] = transform.encode(unit.row)
                    counts = unit.target_counts
                    compositions[index] = None if counts is None or sum(counts) == 0 else (
                        torch.tensor(counts, dtype=torch.float64) / sum(counts))
            targets.append(PreparedTarget(
                ("test", ordinal, pair.target_index),
                torch.tensor([encoded[i] for i in pair.input_indices], dtype=torch.float32),
                torch.tensor(prefix_lengths(record, pair), dtype=torch.float32),
                torch.tensor(pair.target_composition, dtype=torch.float64),
                tuple(compositions[i] for i in pair.input_indices)))
        prepared.append(tuple(targets))
        for unit in record.units:
            unit_count += 1
            statuses[unit.status] += 1
            if unit.failure_reason is not None:
                failures[unit.failure_reason] += 1
            for j, (value, opportunity, reason) in enumerate(zip(
                    unit.row.values, unit.row.opportunities, unit.row.missing_reasons)):
                present[j] += int(value is not None)
                unknown[j] += int(opportunity is None)
                if reason is not None:
                    missing[j][reason] += 1
    coverage = TestCoverage(
        len(records), sum(bool(x) for x in prepared), unit_count,
        sum(len(x.ledger) for x in ledgers), sum(map(len, prepared)),
        tuple(sorted(statuses.items())), tuple(sorted(failures.items())),
        tuple(sorted(pair_reasons.items())), tuple(present), tuple(unknown),
        tuple(tuple(sorted(x.items())) for x in missing))
    return tuple(ledgers), tuple(prepared), coverage


def _mean(values):
    return math.fsum(values) / len(values) if values else None


def _record_prediction(ordinal, predictions):
    predictions = tuple(predictions)
    return RecordPrediction(
        ordinal, predictions, _mean([p.ce for p in predictions]),
        tuple(_mean([p.per_bin_absolute_error[j] for p in predictions]) for j in range(14))
        if predictions else None)


def predict_frozen_test(test_records: Sequence[ObservedRecord], *, transform: TrainTransform,
                        prior: Tensor, checkpoints: Mapping,
                        root_approved: bool = False, synthetic_only: bool = False,
                        control_hook: Callable[[], None] | None = None) -> FrozenTestPredictions:
    """Predict all 17 main series and three separate fixed-weight perturbations.

    checkpoints is exactly {(arm, seed): state_dict}, five frozen ARMS x SEEDS.
    No endpoint, speaker, page, final-length, or target metadata enters forward.
    The shuffled training control uses the existing _predict(..., epoch=0).
    The perturbation applies a separately seeded row permutation to ordinary GRU.

    Zero-eligible records retain all ledger/coverage rows and None losses. An
    entirely zero-eligible split returns stopped_zero_eligible_records, never a
    successful evaluation with a fabricated zero score. There are no partial
    results on exceptions. Calls and control-hook pauses share the resource cap.
    """
    require(type(root_approved) is bool and type(synthetic_only) is bool, "approval_type")
    require(synthetic_only or root_approved, "natural_test_requires_separate_root_go")
    budget = _Budget(control_hook)
    with _bounded_cpu_run(budget):
        records = tuple(test_records)
        # Reject TRAIN/dev before reading record measurements or building models.
        require(all(isinstance(r, ObservedRecord) for r in records), "observed_record_required")
        require(all(r.provenance.partition == "test" for r in records), "test_only_entry")
        require(len({r.provenance.record_id for r in records}) == len(records), "duplicate_source_record")
        for record in records:
            budget.check()
            record.validate()
        if records:
            require(len({(r.provenance.archive_sha256, r.parser_profile_sha256,
                          r.measurement_schema_sha256) for r in records}) == 1,
                    "source_archive_or_producer_profile_changed")
        wanted = "synthetic_fixture" if synthetic_only else "automatic_unvalidated"
        require(all(u.analysis_status == wanted for r in records for u in r.units),
                "synthetic_only_required" if synthetic_only else "natural_test_requires_natural_records")
        _validate_transform(transform)
        models = _models(checkpoints, prior, budget)
        ledgers, prepared, coverage = _prepare(records, transform, budget)
        # Reuse the exact three loaded ordinary GRUs; never create altered weights.
        diagnostics = tuple((PERTURBATION_ARM, seed, model)
                            for arm, seed, model in models if arm == "gru")
        series = []
        with torch.no_grad():
            for arm, seed, model in models + diagnostics:
                budget.check()
                model.eval()
                record_predictions = []
                for ordinal, targets in enumerate(prepared):
                    budget.check()
                    target_predictions = []
                    for target in targets:
                        budget.check()
                        if arm == PERTURBATION_ARM:
                            shuffled = shuffle_prefix(target.prefix, shuffle_seed=_scheduled_seed(
                                seed, PERTURBATION_PURPOSE, 0, *target.target_id))
                            logits = model(shuffled, target.lengths)
                        else:
                            logits = _predict(model, target, seed or 0, epoch=0)
                        loss = soft_target_cross_entropy(logits, target.target).item()
                        probabilities = logits.softmax(-1).double()
                        errors = (probabilities - target.target).abs()
                        target_predictions.append(TargetPrediction(
                            target.target_id, tuple(target.target.tolist()), tuple(logits.tolist()),
                            tuple(probabilities.tolist()), loss, tuple(errors.tolist())))
                    record_predictions.append(_record_prediction(ordinal, target_predictions))
                series.append(PredictionSeries(arm, seed, arm == PERTURBATION_ARM,
                                                tuple(record_predictions)))
        budget.check()
        return FrozenTestPredictions(
            "predictions_frozen" if coverage.eligible_records else "stopped_zero_eligible_records",
            synthetic_only, coverage, ledgers, tuple(series), budget.elapsed)


def _metric(records, *, selected_ids=None, ordinals=None):
    groups, errors, pairs = [], [], 0
    for record in records:
        if ordinals is not None and record.ordinal not in ordinals:
            continue
        targets = tuple(t for t in record.targets
                        if selected_ids is None or t.target_id in selected_ids)
        if targets:
            groups.append(_mean([t.ce for t in targets]))
            errors.append(tuple(_mean([t.per_bin_absolute_error[j] for t in targets])
                                for j in range(14)))
            pairs += len(targets)
    return {"conditional_record_equal_ce": _mean(groups),
            "record_equal_per_bin_absolute_error": tuple(
                _mean([row[j] for row in errors]) for j in range(14)) if errors else None,
            "eligible_records": len(groups), "eligible_pairs": pairs}


def _average_seed_metrics(metrics):
    require(len(metrics) == 3, "exact_three_seed_metrics_required")
    require(len({(m["eligible_records"], m["eligible_pairs"]) for m in metrics}) == 1,
            "seed_target_ledger_mismatch")
    return {
        "conditional_record_equal_ce": _mean([m["conditional_record_equal_ce"] for m in metrics])
        if metrics[0]["eligible_records"] else None,
        "record_equal_per_bin_absolute_error": tuple(_mean([
            m["record_equal_per_bin_absolute_error"][j] for m in metrics]) for j in range(14))
        if metrics[0]["eligible_records"] else None,
        "eligible_records": metrics[0]["eligible_records"],
        "eligible_pairs": metrics[0]["eligible_pairs"],
        "aggregation": "mean_of_three_separately_scored_seed_losses_and_errors",
    }


def _percentile(sorted_values, probability):
    index = (len(sorted_values) - 1) * probability
    lo, hi = math.floor(index), math.ceil(index)
    return sorted_values[lo] + (index - lo) * (sorted_values[hi] - sorted_values[lo])


def _group_sort_key(key):
    raw = json.dumps((BOOTSTRAP_HASH_DOMAIN, key), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).digest(), raw


def _grouped_bootstrap(values, groups, *, seed, budget):
    """Resample clusters, retaining every record and each repeated occurrence.

    The ratio of all sampled record sums/counts estimates the declared record-
    equal statistic. An unweighted mean of cluster means is a different estimand.
    """
    eligible = set(values)
    require(set(groups) == eligible, "bootstrap_group_coverage_mismatch")
    clusters = defaultdict(list)
    for ordinal in sorted(values):
        require(finite(values[ordinal]), "nonfinite_paired_delta")
        clusters[groups[ordinal]].append(ordinal)
    keys = sorted(clusters, key=_group_sort_key)
    base = {
        "point_estimate": _mean(list(values.values())), "eligible_records": len(values),
        "eligible_clusters": len(keys), "replicates": BOOTSTRAP_REPLICATES,
        "seed": seed, "percentile_probabilities": PERCENTILE_PROBABILITIES,
        "percentile_method": "linear_interpolation_at_(replicates-1)*probability",
        "statistic": "mean_of_all_record_deltas_in_sampled_clusters_with_multiplicity",
        "interpretation": "descriptive_conditional_on_fixed_fitted_models_and_eligible_records",
        "training_or_measurement_uncertainty_included": False,
    }
    if len(keys) < 2:
        return {**base, "interval": None, "status": "undefined_fewer_than_two_clusters"}, ()
    sums = [math.fsum(values[i] for i in clusters[key]) for key in keys]
    sizes = [len(clusters[key]) for key in keys]
    rng = random.Random(seed)
    distribution = []
    for _ in range(BOOTSTRAP_REPLICATES):
        budget.check()
        selected = [rng.randrange(len(keys)) for _ in keys]
        distribution.append(math.fsum(sums[i] for i in selected) / sum(sizes[i] for i in selected))
    ordered = sorted(distribution)
    return {**base, "interval": tuple(_percentile(ordered, p) for p in PERCENTILE_PROBABILITIES),
            "status": "descriptive_interval"}, tuple(distribution)


def _validate_predictions(predictions):
    require(type(predictions) is FrozenTestPredictions, "frozen_test_predictions_required")
    require(tuple((s.arm, s.seed) for s in predictions.series) == COMPARATOR_KEYS + DIAGNOSTIC_KEYS,
            "exact_frozen_prediction_series_required")
    require(tuple(r.ordinal for r in predictions.records) == tuple(range(len(predictions.records))),
            "record_ordinal_mismatch")
    expected = tuple(tuple(("test", record.ordinal, pair.target_index)
                           for pair in record.ledger if pair.eligible) for record in predictions.records)
    for series in predictions.series:
        require(series.diagnostic_only == (series.arm == PERTURBATION_ARM), "diagnostic_label_mismatch")
        require(tuple(r.ordinal for r in series.records) == tuple(range(len(expected))),
                "prediction_record_ledger_mismatch")
        require(tuple(tuple(t.target_id for t in r.targets) for r in series.records) == expected,
                "prediction_target_ledger_mismatch")
        for record in series.records:
            require(record.ce is None if not record.targets else finite(record.ce),
                    "invalid_record_prediction_loss")
    return {t for ids in expected for t in ids}


def summarize_predictions(predictions: FrozenTestPredictions, *,
                          endpoint_flags: Mapping | None = None,
                          speaker_keys: Mapping[int, str | None] | None = None,
                          page_types: Mapping[int, str] | None = None,
                          control_hook: Callable[[], None] | None = None) -> TestEvaluationSummary:
    """Aggregate an already frozen prediction artifact, never make predictions.

    Caller must hash/persist all series BEFORE computing/passing endpoint flags.
    Endpoint mapping keys are exact eligible target_id tuples; values are the
    three bool fields returned by diagnostics.endpoint_flags. Page/speaker maps
    cover every record ordinal exactly when provided, including zero-eligible
    records. Missing speaker values (None or empty string) each form a separate
    per-record cluster. These keys are metadata proxies, not author identities.
    """
    require(type(predictions) is FrozenTestPredictions, "frozen_test_predictions_required")
    budget = _Budget(control_hook, previous_wall_seconds=predictions.prediction_wall_seconds)
    with _bounded_cpu_run(budget):
        target_ids = _validate_predictions(predictions)
        ordinals = set(range(len(predictions.records)))
        endpoint_sets = None
        if endpoint_flags is not None:
            require(isinstance(endpoint_flags, Mapping) and set(endpoint_flags) == target_ids,
                    "endpoint_mapping_must_cover_exact_eligible_targets")
            endpoint_sets = {name: set() for name in ENDPOINT_BUCKETS}
            for target_id, flags in endpoint_flags.items():
                require(isinstance(flags, Mapping) and set(flags) == set(ENDPOINT_FIELDS),
                        "endpoint_flag_fields")
                require(all(type(x) is bool for x in flags.values()), "endpoint_flags_must_be_bool")
                require(flags["terminal_source_unit"] or not any(flags.values()),
                        "extensibility_requires_terminal_source_unit")
                endpoint_sets["all"].add(target_id)
                endpoint_sets["terminal_source_unit" if flags["terminal_source_unit"] else
                              "interior"].add(target_id)
                for name in ENDPOINT_FIELDS[1:]:
                    if flags[name]:
                        endpoint_sets[name].add(target_id)
        for mapping, name in ((speaker_keys, "speaker"), (page_types, "page_type")):
            if mapping is not None:
                require(isinstance(mapping, Mapping) and set(mapping) == ordinals,
                        name + "_mapping_must_cover_all_records")
        if speaker_keys is not None:
            require(all(value is None or type(value) is str for value in speaker_keys.values()),
                    "speaker_keys_must_be_strings_or_missing")
        if page_types is not None:
            require(all(type(value) is str for value in page_types.values()), "page_type_must_be_string")
            # Unknown upstream labels must never become arbitrary public text.
            page_types = {i: value if value in PUBLIC_PAGE_TYPES else "other_or_unknown"
                          for i, value in page_types.items()}
        by_key = {(s.arm, s.seed): s for s in predictions.series}
        metrics, endpoints, strata = [], [], []
        for series in predictions.series:
            budget.check()
            identity = {"arm": series.arm, "seed": series.seed, "diagnostic_only": series.diagnostic_only}
            metrics.append({**identity, **_metric(series.records)})
            if endpoint_sets is not None:
                endpoints.append({**identity, "buckets": {
                    name: _metric(series.records, selected_ids=selected)
                    for name, selected in endpoint_sets.items()}})
            if page_types is not None:
                strata.append({**identity, "strata": {
                    page: {**_metric(series.records, ordinals={i for i, p in page_types.items() if p == page}),
                           "selected_records": sum(p == page for p in page_types.values())}
                    for page in sorted(set(page_types.values()))}})
        seed_averages = [{"arm": arm, **_average_seed_metrics([
            _metric(by_key[(arm, seed)].records) for seed in SEEDS])} for arm in ARMS]
        paired, deltas, seedwise = [], {}, []
        for metadata in predictions.records:
            budget.check()
            ordinal = metadata.ordinal
            ds = tuple(by_key[("deepsets", seed)].records[ordinal].ce for seed in SEEDS)
            gru = tuple(by_key[("gru", seed)].records[ordinal].ce for seed in SEEDS)
            if ds[0] is None:
                require(all(x is None for x in ds + gru), "paired_record_eligibility_mismatch")
                continue
            differences = tuple(d - g for d, g in zip(ds, gru))
            delta = _mean(differences)
            deltas[ordinal] = delta
            paired.append({"ordinal": ordinal, "record_id": metadata.record_id,
                           "component_id": metadata.component_id, "seeds": SEEDS,
                           "deepsets_seed_ce": ds, "gru_seed_ce": gru,
                           "seedwise_delta": differences, "seed_averaged_delta": delta})
        for index, seed in enumerate(SEEDS):
            seedwise.append({"seed": seed, "mean_record_delta": _mean([
                row["seedwise_delta"][index] for row in paired]), "eligible_records": len(paired)})
        components = {i: ("component", predictions.records[i].component_id) for i in deltas}
        component_interval, component_replicates = _grouped_bootstrap(
            deltas, components, seed=COMPONENT_BOOTSTRAP_SEED, budget=budget)
        speaker_interval, speaker_replicates = None, ()
        if speaker_keys is not None:
            speakers = {i: ("speaker", speaker_keys[i]) if speaker_keys[i] else
                        ("missing_speaker_record", predictions.records[i].record_id) for i in deltas}
            speaker_interval, speaker_replicates = _grouped_bootstrap(
                deltas, speakers, seed=SPEAKER_BOOTSTRAP_SEED, budget=budget)
            speaker_interval["missing_key_singleton_records"] = sum(not speaker_keys[i] for i in deltas)
            speaker_interval["cluster_role"] = "declared_top_speaker_metadata_proxy_not_author_truth"
        budget.check()
        report = {
            "status": "completed_frozen_test_summary" if deltas else "stopped_zero_eligible_records",
            "synthetic_only": predictions.synthetic_only,
            "target_weighting": "mean_eligible_targets_within_record_then_mean_eligible_records",
            "primary_comparison": "DeepSets_minus_GRU_mean_of_three_separately_scored_seed_record_losses",
            "positive_delta_favors": "gru", "probability_ensemble_evaluated": False,
            "seeds": SEEDS, "main_comparator_count": 17, "perturbation_series_count": 3,
            "coverage": predictions.coverage.as_dict(), "comparator_metrics": metrics,
            "learned_arm_seed_average_metrics": seed_averages,
            "paired_comparison": {"seed_averaged_record_delta": _mean(list(deltas.values())),
                                  "seedwise": seedwise,
                                  "component_bootstrap": component_interval,
                                  "speaker_key_cluster_sensitivity": speaker_interval},
            "posthoc_endpoint_metrics": endpoints if endpoint_flags is not None else None,
            "source_page_type_metrics": strata if page_types is not None else None,
            "endpoint_flags_in_model_inputs": False, "no_new_fit": True,
            "author_or_human_truth_admission": False, "comparison_eligible_promoted": False,
            "bootstrap_hash_domain": BOOTSTRAP_HASH_DOMAIN,
            "perturbation_seed_purpose": PERTURBATION_PURPOSE,
            "resources": {"cpu_threads": 2, "interop_threads": 2, "gpu": False,
                          "maximum_wall_seconds": MAX_WALL_SECONDS,
                          "stage_compute_wall_seconds": budget.elapsed,
                          "maximum_rss_kib": MAX_RSS_KIB,
                          "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          "new_download_bytes": 0},
        }
        return TestEvaluationSummary(report, {"paired_record_deltas": tuple(paired),
                                             "component_bootstrap_replicates": component_replicates,
                                             "speaker_bootstrap_replicates": speaker_replicates})
