"""Bounded, caller-fed TRAIN/development runner; no I/O or fitting at import.

Usage: decode_record(payload["record"]) decodes a private extraction payload.
fit_train_dev(..., root_approved=True) is an explicit natural-data entry point;
the flag records caller approval, and does not grant it. There is deliberately
no filesystem CLI, test-data loader, test evaluator, or automatic run here.
fit_synthetic_smoke is a reduced-epoch TEST CONFIGURATION, not the experiment.

Returned transforms and checkpoint tensors are private caller-owned artifacts.
Only public_report is intended for publication; it contains aggregate results,
never source text, source identifiers, or per-record predictions/losses.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, fields
import hashlib
import json
import math
import resource
import signal
import threading
import time

import torch
from torch import Tensor

from .contracts import (
    ObservedRecord, ObservedUnit, PredictionPair, Provenance, SensorRow,
    check_known_split_isolation, require,
)
from .models import (
    ARM_PARAMETER_COUNTS, ConstantPrior, LatestState, ShuffledGRU,
    make_model, record_equal_smoothed_prior, record_equal_soft_target_ce,
    soft_target_cross_entropy,
)
from .prepare import TrainTransform, fit_train_transform, pair_ledger, prefix_lengths

SEEDS = (1729, 2718, 3141)
ARMS = tuple(ARM_PARAMETER_COUNTS)
EPOCHS = 40
BATCH_RECORDS = 16
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
GRADIENT_CLIP = 1.0
MAX_UPDATES = 4800
MAX_WALL_SECONDS = 3600
MAX_RSS_KIB = 3 * 1024**2


def _fields(value, cls):
    require(isinstance(value, Mapping), "serialized_object_required")
    require(set(value) == {f.name for f in fields(cls)}, "serialized_fields_mismatch")
    return dict(value)


def _sequence(value):
    require(type(value) in (list, tuple), "serialized_sequence_required")
    return tuple(value)


def decode_record(value: Mapping) -> ObservedRecord:
    """Strictly decode one caller-provided asdict/JSON record, without file reads.

    Decoding validates provenance and exact source hashes but does not admit any
    partition for fitting. Unknown/missing fields are rejected, not guessed.
    """
    record = _fields(value, ObservedRecord)
    record["provenance"] = Provenance(**_fields(record["provenance"], Provenance))
    units = []
    for value in _sequence(record["units"]):
        unit = _fields(value, ObservedUnit)
        row = _fields(unit["row"], SensorRow)
        unit["row"] = SensorRow(**{key: _sequence(item) for key, item in row.items()})
        if unit["target_counts"] is not None:
            unit["target_counts"] = _sequence(unit["target_counts"])
        units.append(ObservedUnit(**unit))
    record["units"] = tuple(units)
    result = ObservedRecord(**record)
    result.validate()
    return result


def encode_record(record: ObservedRecord) -> dict:
    """Return a JSON-compatible PRIVATE record value; never write or publish it."""
    record.validate()
    return json.loads(json.dumps(asdict(record), ensure_ascii=False, allow_nan=False))


@dataclass(frozen=True)
class PreparedTarget:
    # Ordinals bind all comparators to the same ledger, never enter a model.
    target_id: tuple[str, int, int]
    prefix: Tensor = field(repr=False)
    lengths: Tensor = field(repr=False)
    target: Tensor = field(repr=False)
    visible_compositions: tuple[Tensor | None, ...] = field(repr=False)


@dataclass(frozen=True)
class PreparedRecord:
    ordinal: int
    ledger: tuple[PredictionPair, ...] = field(repr=False)
    targets: tuple[PreparedTarget, ...] = field(repr=False)


@dataclass(frozen=True)
class PreparedSplit:
    partition: str
    records: tuple[PreparedRecord, ...] = field(repr=False)
    coverage: dict

    @property
    def eligible_records(self):
        return tuple(record for record in self.records if record.targets)


@dataclass(frozen=True)
class PreparedData:
    transform: TrainTransform = field(repr=False)
    train: PreparedSplit = field(repr=False)
    development: PreparedSplit = field(repr=False)
    synthetic_only: bool


def _admit(train_records, development_records, *, root_approved, synthetic_only):
    require(type(root_approved) is bool and type(synthetic_only) is bool, "approval_type")
    require(synthetic_only or root_approved, "natural_fit_requires_separate_root_go")
    train, development = tuple(train_records), tuple(development_records)
    for partition, records in (("train", train), ("development", development)):
        require(bool(records), "empty_train_or_development_partition")
        for record in records:
            require(isinstance(record, ObservedRecord), "observed_record_required")
            require(record.provenance.partition == partition, "train_development_only_test_sealed")
            record.validate()
        require(len({r.provenance.record_id for r in records}) == len(records), "duplicate_source_record")
    records = train + development
    check_known_split_isolation(records)
    require(len({(r.provenance.archive_sha256, r.parser_profile_sha256,
                  r.measurement_schema_sha256) for r in records}) == 1,
            "source_archive_or_producer_profile_changed")
    wanted = "synthetic_fixture" if synthetic_only else "automatic_unvalidated"
    require(all(u.analysis_status == wanted for r in records for u in r.units),
            "synthetic_only_required" if synthetic_only else "natural_run_requires_natural_records")
    return train, development


def _prepare_split(records, partition, transform):
    prepared, reasons, statuses = [], Counter(), Counter()
    unit_count = 0
    for ordinal, record in enumerate(records):
        ledger = pair_ledger(record)
        encoded = tuple(transform.encode(unit.row) for unit in record.units)
        compositions = tuple(
            None if unit.target_counts is None or sum(unit.target_counts) == 0 else
            torch.tensor(unit.target_counts, dtype=torch.float64) / sum(unit.target_counts)
            for unit in record.units
        )
        targets = tuple(PreparedTarget(
            (partition, ordinal, pair.target_index),
            torch.tensor([encoded[i] for i in pair.input_indices], dtype=torch.float32),
            torch.tensor(prefix_lengths(record, pair), dtype=torch.float32),
            torch.tensor(pair.target_composition, dtype=torch.float64),
            tuple(compositions[i] for i in pair.input_indices),
        ) for pair in ledger if pair.eligible)
        prepared.append(PreparedRecord(ordinal, ledger, targets))
        reasons.update(pair.missing_reason for pair in ledger if not pair.eligible)
        statuses.update(unit.status for unit in record.units)
        unit_count += len(record.units)
    eligible = sum(bool(record.targets) for record in prepared)
    coverage = {
        "records": len(prepared), "eligible_records": eligible,
        "zero_eligible_records": len(prepared) - eligible,
        "units": unit_count, "unit_status_counts": dict(sorted(statuses.items())),
        "candidate_pairs": sum(len(record.ledger) for record in prepared),
        "eligible_pairs": sum(len(record.targets) for record in prepared),
        "pair_missing_reasons": dict(sorted(reasons.items())),
    }
    require(eligible > 0, "partition_zero_valid_source_records")
    return PreparedSplit(partition, tuple(prepared), coverage)


def prepare_train_dev(train_records, development_records, *, root_approved=False,
                      synthetic_only=False) -> PreparedData:
    """Explicit train-only transform estimation and shared ledger preparation.

    This is itself an empirical fit for natural data and needs the same GO.
    Test records are rejected before fitting even a transform.
    """
    train, development = _admit(train_records, development_records,
                               root_approved=root_approved, synthetic_only=synthetic_only)
    transform = fit_train_transform(train)
    return PreparedData(transform, _prepare_split(train, "train", transform),
                        _prepare_split(development, "development", transform), synthetic_only)


class FitStopped(RuntimeError):
    """Fail-closed resource stop; partial models are not experiment results."""
    def __init__(self, reason, *, optimizer_updates=0):
        self.status = "stopped_resource_cap"
        self.reason = reason
        self.optimizer_updates = optimizer_updates
        super().__init__(reason)


class _Budget:
    def __init__(self, control_hook=None):
        require(control_hook is None or callable(control_hook), "control_hook_must_be_callable")
        self.start = time.monotonic()
        self.updates = 0
        self.control_hook = control_hook

    def check(self):
        if self.control_hook is not None:
            self.control_hook()
        if time.monotonic() - self.start >= MAX_WALL_SECONDS:
            raise FitStopped("fit_wall_cap", optimizer_updates=self.updates)
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > MAX_RSS_KIB:
            raise FitStopped("fit_rss_cap", optimizer_updates=self.updates)

    def before_update(self):
        self.check()
        if self.updates >= MAX_UPDATES:
            raise FitStopped("fit_optimizer_update_cap", optimizer_updates=self.updates)


@contextmanager
def _bounded_cpu_run(budget):
    # SIGALRM adds a wall-clock interrupt to per-prefix/update resource checks.
    # This Linux runner requires the main thread and does not replace a caller's
    # armed timer. The RSS guard is runtime checking, not an OS memory sandbox.
    require(threading.current_thread() is threading.main_thread(), "fit_requires_main_thread")
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), "caller_timer_already_armed")
    if torch.get_num_interop_threads() != 2:
        try:
            torch.set_num_interop_threads(2)
        except RuntimeError:
            raise RuntimeError("cpu_interop_requires_fresh_process_with_two_threads") from None
    old_threads = torch.get_num_threads()
    old_handler = signal.getsignal(signal.SIGALRM)

    def timeout(signum, frame):
        raise FitStopped("fit_wall_cap", optimizer_updates=budget.updates)

    torch.set_num_threads(2)
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, MAX_WALL_SECONDS)
    try:
        budget.check()
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        torch.set_num_threads(old_threads)


def _scheduled_seed(seed, purpose, *coordinates):
    # Ordinals/epoch determine randomization, not raw source IDs or future data.
    value = "|".join(map(str, (seed, purpose, *coordinates)))
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big") % 2**63


def _predict(model, target, seed, epoch):
    if isinstance(model, LatestState):
        return model(target.visible_compositions)
    if isinstance(model, ConstantPrior):
        return model()
    if isinstance(model, ShuffledGRU):
        return model(target.prefix, target.lengths, shuffle_seed=_scheduled_seed(
            seed, "prefix", epoch, *target.target_id))
    return model(target.prefix, target.lengths)


def _batch_loss(model, records, seed, epoch, budget):
    logits, targets, groups = [], [], []
    for group, record in enumerate(records):
        require(bool(record.targets), "zero_eligible_record_cannot_have_loss")
        for target in record.targets:
            budget.check()
            logits.append(_predict(model, target, seed, epoch))
            targets.append(target.target)
            groups.append(group)
    return record_equal_soft_target_ce(torch.stack(logits), torch.stack(targets),
                                       torch.tensor(groups, dtype=torch.int64))


def _aggregate_metrics(model, split, seed, budget):
    require(split.partition in {"train", "development"}, "test_evaluation_not_implemented")
    model.eval()
    record_losses, record_errors = [], []
    with torch.no_grad():
        for record in split.eligible_records:
            budget.check()
            losses, errors = [], []
            for target in record.targets:
                budget.check()
                # Fixed evaluation shuffles across epochs make checkpoint
                # selection compare like with like. Training reshuffles epochs.
                logits = _predict(model, target, seed, epoch=0)
                losses.append(soft_target_cross_entropy(logits, target.target).item())
                errors.append((logits.softmax(-1).double() - target.target).abs())
            record_losses.append(math.fsum(losses) / len(losses))
            record_errors.append(torch.stack(errors).mean(0))
    require(bool(record_losses), "partition_zero_valid_source_records")
    return {
        "conditional_record_equal_ce": math.fsum(record_losses) / len(record_losses),
        "record_equal_per_bin_absolute_error": torch.stack(record_errors).mean(0).tolist(),
        "eligible_records": len(record_losses),
        "eligible_pairs": split.coverage["eligible_pairs"],
    }


@dataclass(frozen=True)
class FittedArm:
    arm: str
    seed: int
    best_epoch: int
    best_state: dict[str, Tensor] = field(repr=False)
    train_metrics: dict
    development_metrics: dict


@dataclass(frozen=True)
class FitResult:
    transform: TrainTransform = field(repr=False)
    prior: Tensor = field(repr=False)
    fits: tuple[FittedArm, ...] = field(repr=False)
    public_report: dict


def _fit(train_records, development_records, *, epochs, seeds, synthetic_only, root_approved,
         control_hook=None):
    budget = _Budget(control_hook)
    with _bounded_cpu_run(budget):
        prepared = prepare_train_dev(train_records, development_records,
                                     root_approved=root_approved, synthetic_only=synthetic_only)
        eligible = prepared.train.eligible_records
        expected_updates = math.ceil(len(eligible) / BATCH_RECORDS) * epochs * len(seeds) * len(ARMS)
        if expected_updates > MAX_UPDATES:
            raise FitStopped("fit_optimizer_update_cap_before_training")
        prior = record_equal_smoothed_prior(tuple(
            torch.stack([target.target for target in record.targets]) for record in eligible))
        baselines = {}
        for name, model in (("constant_prior", ConstantPrior(prior)), ("latest_state", LatestState(prior))):
            baselines[name] = {
                "train": _aggregate_metrics(model, prepared.train, 0, budget),
                "development": _aggregate_metrics(model, prepared.development, 0, budget),
            }
        fits, summaries = [], []
        for arm in ARMS:
            for seed in seeds:
                budget.check()
                model = make_model(arm, seed=seed)
                optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE,
                                               weight_decay=WEIGHT_DECAY)
                best_loss, best_epoch, best_state, history = math.inf, None, None, []
                start_updates = budget.updates
                for epoch in range(1, epochs + 1):
                    budget.check()
                    model.train()
                    generator = torch.Generator(device="cpu").manual_seed(
                        _scheduled_seed(seed, "record_order", epoch))
                    order = torch.randperm(len(eligible), generator=generator).tolist()
                    for offset in range(0, len(order), BATCH_RECORDS):
                        budget.check()
                        batch = tuple(eligible[i] for i in order[offset:offset + BATCH_RECORDS])
                        optimizer.zero_grad(set_to_none=True)
                        loss = _batch_loss(model, batch, seed, epoch, budget)
                        loss.backward()
                        torch.nn.utils.clip_grad_norm_(model.parameters(), GRADIENT_CLIP,
                                                       error_if_nonfinite=True)
                        budget.before_update()
                        optimizer.step()
                        budget.updates += 1
                        budget.check()
                    dev = _aggregate_metrics(model, prepared.development, seed, budget)
                    dev_loss = dev["conditional_record_equal_ce"]
                    require(math.isfinite(dev_loss), "nonfinite_development_loss")
                    history.append({"epoch": epoch, "development_record_equal_ce": dev_loss})
                    # Strict comparison deliberately retains the earliest exact tie.
                    if dev_loss < best_loss:
                        best_loss, best_epoch = dev_loss, epoch
                        best_state = {key: value.detach().cpu().clone()
                                      for key, value in model.state_dict().items()}
                require(best_state is not None, "missing_development_checkpoint")
                model.load_state_dict(best_state)
                train_metrics = _aggregate_metrics(model, prepared.train, seed, budget)
                development_metrics = _aggregate_metrics(model, prepared.development, seed, budget)
                fits.append(FittedArm(arm, seed, best_epoch, best_state, train_metrics, development_metrics))
                summaries.append({
                    "arm": arm, "seed": seed, "best_epoch": best_epoch,
                    "parameter_count": ARM_PARAMETER_COUNTS[arm],
                    "optimizer_updates": budget.updates - start_updates,
                    "train": train_metrics, "development": development_metrics,
                    "development_history": history,
                })
        require(budget.updates == expected_updates, "optimizer_update_accounting")
        budget.check()
        transform = prepared.transform
        report = {
            "status": "completed_synthetic_smoke" if synthetic_only else "completed_train_development",
            "configuration_kind": "reduced_epoch_test_configuration_not_approved_experiment"
                if synthetic_only else "fixed_observed_sequence_training_development",
            "optimizer": "AdamW", "seeds": list(seeds), "epochs": epochs,
            "batch_records": BATCH_RECORDS, "learning_rate": LEARNING_RATE,
            "weight_decay": WEIGHT_DECAY, "gradient_norm_clip": GRADIENT_CLIP,
            "checkpoint_rule": "lowest_development_record_equal_ce_earliest_exact_tie",
            "target_weighting": "mean_targets_within_record_then_mean_eligible_records",
            "target_ledger_shared_by_all_seven_arms": True,
            "coverage": {"train": prepared.train.coverage, "development": prepared.development.coverage},
            "normalization": {
                "train_records": transform.train_record_count,
                "value_support_records": list(transform.value_support_records),
                "opportunity_support_records": list(transform.opportunity_support_records),
                "value_observation_count": list(transform.value_observation_count),
                "opportunity_observation_count": list(transform.opportunity_observation_count),
                "frozen_zero_value_channels": sum(x == 0 for x in transform.value_scale),
                "frozen_zero_opportunity_channels": sum(x == 0 for x in transform.opportunity_scale),
            },
            "baselines": baselines, "fits": summaries,
            "resources": {"cpu_threads": 2, "interop_threads": 2, "gpu": False,
                "optimizer_updates": budget.updates, "maximum_optimizer_updates": MAX_UPDATES,
                "wall_seconds": time.monotonic() - budget.start,
                "maximum_wall_seconds": MAX_WALL_SECONDS,
                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "new_download_bytes": 0},
            "test_evaluated": False, "comparison_eligible_promoted": False,
            "author_or_human_truth_admission": False,
        }
        return FitResult(transform, prior.clone(), tuple(fits), report)


def fit_train_dev(train_records: Sequence[ObservedRecord], development_records: Sequence[ObservedRecord],
                  *, root_approved: bool = False,
                  control_hook: Callable[[], None] | None = None) -> FitResult:
    """Run exactly 5 arms x 3 seeds x 40 epochs, only after separate root GO.

    No knobs for tuning, replacing arms, reducing epochs, or inspecting test data.
    CPU inter-op threads are set to two for the process on this explicit call.
    control_hook() runs before every epoch, batch, evaluation record, and at
    additional safe boundaries. The caller may block or raise to pause/stop;
    exceptions propagate unchanged. The 60-minute wall cap includes pauses.
    This module never reads a flag file or implements external control I/O.
    """
    require(root_approved is True, "natural_fit_requires_separate_root_go")
    return _fit(train_records, development_records, epochs=EPOCHS, seeds=SEEDS,
                synthetic_only=False, root_approved=root_approved, control_hook=control_hook)


def fit_synthetic_smoke(train_records: Sequence[ObservedRecord],
                        development_records: Sequence[ObservedRecord], *, epochs: int = 2,
                        control_hook: Callable[[], None] | None = None) -> FitResult:
    """All five arms, seed1729 and 1-2 epochs; original synthetic fixtures ONLY."""
    require(type(epochs) is int and 1 <= epochs <= 2, "synthetic_smoke_epochs_must_be_one_or_two")
    return _fit(train_records, development_records, epochs=epochs, seeds=SEEDS[:1],
                synthetic_only=True, root_approved=False, control_hook=control_hook)
