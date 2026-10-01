"""Unfitted CPU comparators for the observed-sequence proposal.

This module only operates on caller-provided tensors. It performs no I/O, source
parsing, transform estimation, training, or evaluation at import. The caller must
enforce split/target-ledger admission and supply an actual boundary-validated,
contiguous observed prefix tensor, not a source record. Passing a full record
and cutting model outputs is not supported.

Each of the 68 channel encodings is interleaved as value, presence, scaled
log-opportunity, opportunity-known. Missingness is retained in the two flags;
this module never imputes, rescales, or replaces non-finite data. The only global
inputs are log1p(observed units) and log1p(observed source codepoints).
"""

from __future__ import annotations

from collections.abc import Sequence
import math

import torch
from torch import Tensor, nn
from torch.nn import functional as F


LOCAL_CHANNELS = 68
INPUT_WIDTH = 4 * LOCAL_CHANNELS
OUTPUT_BINS = 14
LENGTH_WIDTH = 2
ARM_PARAMETER_COUNTS = {
    "mask_length_mlp": 6134,
    "pooled_raw_mlp": 4638,
    "deepsets": 5966,
    "gru": 6266,
    "shuffled_gru": 6266,
}
_INTEGER_DTYPES = (torch.uint8, torch.int8, torch.int16, torch.int32, torch.int64)


class ModelInputError(ValueError):
    """The supplied tensor violates the frozen model/loss contract."""


def _cpu_tensor(value: Tensor, name: str, *, floating: bool = True) -> None:
    if not isinstance(value, Tensor):
        raise ModelInputError(f"{name} must be a torch.Tensor")
    if value.device.type != "cpu":
        raise ModelInputError(f"{name} must be on CPU")
    if floating and value.dtype not in (torch.float32, torch.float64):
        raise ModelInputError(f"{name} must use float32 or float64")
    if not torch.isfinite(value).all().item():
        raise ModelInputError(f"{name} must be finite; missingness needs explicit flags")


def _composition(value: Tensor, name: str) -> None:
    _cpu_tensor(value, name)
    if value.ndim not in (1, 2) or value.shape[-1] != OUTPUT_BINS:
        raise ModelInputError(f"{name} must have shape [14] or [N,14]")
    if value.ndim == 2 and value.shape[0] == 0:
        raise ModelInputError(f"{name} must contain at least one valid target")
    if (value < 0).any().item():
        raise ModelInputError(f"{name} must be nonnegative")
    total = value.sum(dim=-1)
    if not torch.allclose(total, torch.ones_like(total), atol=1e-6, rtol=0):
        raise ModelInputError(f"{name} must be normalized; zero targets are missing")


def counts_to_soft_targets(counts: Tensor) -> Tensor:
    """Normalize nonnegative integer counts; zero-token targets are rejected.

    Float64 output avoids unnecessary roundoff when building a composition. No
    target length is returned as a feature, nor used again as a loss multiplier.
    """
    _cpu_tensor(counts, "counts", floating=False)
    if counts.dtype not in _INTEGER_DTYPES:
        raise ModelInputError("counts must use an integer dtype")
    if counts.ndim not in (1, 2) or counts.shape[-1] != OUTPUT_BINS:
        raise ModelInputError("counts must have shape [14] or [N,14]")
    if counts.ndim == 2 and counts.shape[0] == 0:
        raise ModelInputError("counts must contain at least one valid target")
    if (counts < 0).any().item():
        raise ModelInputError("counts must be nonnegative")
    values = counts.to(torch.float64)
    totals = values.sum(dim=-1, keepdim=True)
    if (totals <= 0).any().item():
        raise ModelInputError("zero-token target is missing, not a zero composition")
    return values / totals


def prefix_length_features(
    observed_units: int,
    observed_source_codepoints: int,
    *,
    dtype: torch.dtype = torch.float32,
) -> Tensor:
    """Encode only the supplied visible-prefix counts, never final-record length.

    Source-codepoint count includes any already observed closing whitespace. The
    caller, which owns source spans, must verify that count at the prefix cutoff.
    """
    if type(observed_units) is not int or observed_units < 1:
        raise ModelInputError("observed_units must be a positive integer")
    if (
        type(observed_source_codepoints) is not int
        or observed_source_codepoints < observed_units
    ):
        raise ModelInputError("observed_source_codepoints must cover the observed units")
    if dtype not in (torch.float32, torch.float64):
        raise ModelInputError("length features must use float32 or float64")
    return torch.tensor(
        [math.log1p(observed_units), math.log1p(observed_source_codepoints)],
        dtype=dtype,
    )


def _prefix(prefix: Tensor, lengths: Tensor) -> None:
    _cpu_tensor(prefix, "prefix")
    _cpu_tensor(lengths, "prefix_length_features")
    if prefix.ndim != 2 or prefix.shape[1] != INPUT_WIDTH or prefix.shape[0] < 1:
        raise ModelInputError("prefix must have shape [T,272] with T >= 1")
    if lengths.shape != (LENGTH_WIDTH,) or lengths.dtype != prefix.dtype:
        raise ModelInputError("prefix_length_features must be [2] and match prefix dtype")
    expected = lengths.new_tensor(math.log1p(prefix.shape[0]))
    if not torch.isclose(lengths[0], expected, atol=1e-6, rtol=0).item():
        raise ModelInputError("unit-length feature must count this prefix only")
    if (lengths[1] < lengths[0]).item():
        raise ModelInputError("source-length feature cannot be shorter than unit count")
    flags = prefix.reshape(-1, LOCAL_CHANNELS, 4)[:, :, (1, 3)]
    if not ((flags == 0) | (flags == 1)).all().item():
        raise ModelInputError("presence and opportunity-known flags must be binary")


class _PrefixModel(nn.Module):
    def _check(self, prefix: Tensor, lengths: Tensor) -> None:
        _prefix(prefix, lengths)
        parameter = next(self.parameters())
        if parameter.device.type != "cpu" or prefix.dtype != parameter.dtype:
            raise ModelInputError("prefix must match the CPU model parameter dtype")


class MaskLengthMLP(_PrefixModel):
    """Mean presence/known flags (136) plus visible lengths: 138 -> 40 -> 14."""

    def __init__(self) -> None:
        super().__init__()
        self.head = nn.Sequential(nn.Linear(138, 40), nn.GELU(), nn.Linear(40, 14))

    def forward(self, prefix: Tensor, prefix_length_features: Tensor) -> Tensor:
        self._check(prefix, prefix_length_features)
        flags = prefix.reshape(-1, LOCAL_CHANNELS, 4)[:, :, (1, 3)]
        pooled = flags.mean(dim=0).reshape(136)
        return self.head(torch.cat((pooled, prefix_length_features)))


class PooledRawMLP(_PrefixModel):
    """Mean of the prepared 272 features plus visible lengths: 274 -> 16 -> 14."""

    def __init__(self) -> None:
        super().__init__()
        self.head = nn.Sequential(nn.Linear(274, 16), nn.GELU(), nn.Linear(16, 14))

    def forward(self, prefix: Tensor, prefix_length_features: Tensor) -> Tensor:
        self._check(prefix, prefix_length_features)
        return self.head(torch.cat((prefix.mean(dim=0), prefix_length_features)))


class DeepSets(_PrefixModel):
    """Nonlinear independent unit map, then mean pool and 18 -> 48 -> 14 head."""

    def __init__(self) -> None:
        super().__init__()
        self.unit_map = nn.Sequential(nn.Linear(272, 16), nn.GELU())
        self.head = nn.Sequential(nn.Linear(18, 48), nn.GELU(), nn.Linear(48, 14))

    def forward(self, prefix: Tensor, prefix_length_features: Tensor) -> Tensor:
        self._check(prefix, prefix_length_features)
        pooled = self.unit_map(prefix).mean(dim=0)
        return self.head(torch.cat((pooled, prefix_length_features)))


class GRUPredictor(_PrefixModel):
    """Independent GELU(272 -> 16), one GRU16 layer, and 18 -> 14 head."""

    def __init__(self) -> None:
        super().__init__()
        self.unit_map = nn.Sequential(nn.Linear(272, 16), nn.GELU())
        self.gru = nn.GRU(input_size=16, hidden_size=16, num_layers=1, batch_first=True)
        self.head = nn.Linear(18, 14)

    def _forward_valid_prefix(self, prefix: Tensor, lengths: Tensor) -> Tensor:
        # No hidden state survives between prefixes or records.
        _, hidden = self.gru(self.unit_map(prefix).unsqueeze(0))
        return self.head(torch.cat((hidden[0, 0], lengths)))

    def forward(self, prefix: Tensor, prefix_length_features: Tensor) -> Tensor:
        self._check(prefix, prefix_length_features)
        return self._forward_valid_prefix(prefix, prefix_length_features)


def _seed(seed: int) -> None:
    if type(seed) is not int or not 0 <= seed < 2**63:
        raise ModelInputError("seed must be an integer in [0, 2**63)")


def shuffle_prefix(prefix: Tensor, *, shuffle_seed: int) -> Tensor:
    """Return a seeded row permutation, preserving all channel encodings.

    This helper is also usable for the separate test-time perturbation diagnostic
    of the ordinary GRU. A shuffled training arm is not that diagnostic. The
    caller must schedule seeds per prefix/epoch independently of future content.
    """
    _cpu_tensor(prefix, "prefix")
    if prefix.ndim != 2 or prefix.shape[1] != INPUT_WIDTH or prefix.shape[0] < 1:
        raise ModelInputError("prefix must have shape [T,272] with T >= 1")
    _seed(shuffle_seed)
    generator = torch.Generator(device="cpu").manual_seed(shuffle_seed)
    order = torch.randperm(prefix.shape[0], generator=generator)
    return prefix.index_select(0, order)


class ShuffledGRU(GRUPredictor):
    """Same architecture and parameter budget as GRU; each call must name its seed."""

    def forward(
        self,
        prefix: Tensor,
        prefix_length_features: Tensor,
        *,
        shuffle_seed: int,
    ) -> Tensor:
        self._check(prefix, prefix_length_features)
        shuffled = shuffle_prefix(prefix, shuffle_seed=shuffle_seed)
        return self._forward_valid_prefix(shuffled, prefix_length_features)


def make_model(arm: str, *, seed: int) -> _PrefixModel:
    """Initialize one independent arm reproducibly without changing global RNG state."""
    constructors = {
        "mask_length_mlp": MaskLengthMLP,
        "pooled_raw_mlp": PooledRawMLP,
        "deepsets": DeepSets,
        "gru": GRUPredictor,
        "shuffled_gru": ShuffledGRU,
    }
    if arm not in constructors:
        raise ModelInputError(f"unknown arm: {arm}")
    _seed(seed)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        return constructors[arm]()


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def record_equal_smoothed_prior(record_targets: Sequence[Tensor]) -> Tensor:
    """Estimate the declared total-pseudocount-one prior from eligible records.

    Supply one nonempty [targets,14] composition tensor per eligible TRAIN record.
    Every record gets weight one, irrespective of its target count or token count.
    Split authorization is deliberately outside this tensor-only primitive. The
    caller must retain zero-valid-target records in its separate coverage ledger.
    """
    if not record_targets:
        raise ModelInputError("prior requires at least one eligible training record")
    means = []
    for targets in record_targets:
        _composition(targets, "record_targets")
        if targets.ndim != 2:
            raise ModelInputError("record_targets entries must have shape [N,14]")
        means.append(targets.detach().to(torch.float64).mean(dim=0))
    return (torch.stack(means).sum(dim=0) + 1 / OUTPUT_BINS) / (len(means) + 1)


def _positive_prior(prior: Tensor) -> None:
    _composition(prior, "prior")
    if prior.ndim != 1 or not (prior > 0).all().item():
        raise ModelInputError("prior must be a strictly positive [14] composition")


class ConstantPrior(nn.Module):
    """Nontrainable logits whose softmax equals an explicitly supplied smoothed prior."""

    def __init__(self, prior: Tensor) -> None:
        super().__init__()
        _positive_prior(prior)
        self.register_buffer("prior", prior.detach().clone())

    def forward(self) -> Tensor:
        return self.prior.log()


class LatestState(ConstantPrior):
    """0.9 latest valid visible composition + 0.1 prior; prior if none is available.

    The sequence contains units of the same boundary-validated, contiguous visible
    prefix only. None means no available composition; it is not permission to
    bridge a failed-unit barrier. An invalid/all-zero composition is an error,
    never an invented observation.
    """

    def forward(self, visible_compositions: Sequence[Tensor | None]) -> Tensor:
        latest = None
        for composition in visible_compositions:
            if composition is not None:
                _composition(composition, "visible_composition")
                if composition.ndim != 1:
                    raise ModelInputError("visible_composition must have shape [14]")
                latest = composition.detach().to(self.prior.dtype)
        if latest is None:
            return self.prior.log()
        return (0.9 * latest + 0.1 * self.prior).log()


def soft_target_cross_entropy(logits: Tensor, targets: Tensor) -> Tensor:
    """Per-target -sum(q * log_softmax(logits)), without token-count weighting."""
    _cpu_tensor(logits, "logits")
    _composition(targets, "targets")
    if logits.shape != targets.shape:
        raise ModelInputError("logits and targets must have the same [14] or [N,14] shape")
    losses = -(targets.detach().to(logits.dtype) * F.log_softmax(logits, dim=-1)).sum(dim=-1)
    if not torch.isfinite(losses).all().item():
        raise ModelInputError("nonfinite loss; logits exceed usable numerical range")
    return losses


def per_record_soft_target_ce(
    logits: Tensor, targets: Tensor, record_ids: Tensor
) -> tuple[Tensor, Tensor]:
    """Return sorted grouping IDs and each source record's mean target loss.

    IDs are used only for grouping losses, never passed into a predictor. Records
    without available targets are not scoreable here and remain in caller coverage.
    """
    losses = soft_target_cross_entropy(logits, targets)
    if losses.ndim != 1:
        raise ModelInputError("record-equal loss requires [N,14] logits and targets")
    _cpu_tensor(record_ids, "record_ids", floating=False)
    if record_ids.dtype not in _INTEGER_DTYPES or record_ids.shape != losses.shape:
        raise ModelInputError("record_ids must be an integer [N] grouping tensor")
    if (record_ids < 0).any().item():
        raise ModelInputError("record_ids must be nonnegative grouping IDs")
    ids, inverse, counts = torch.unique(record_ids, sorted=True, return_inverse=True, return_counts=True)
    sums = losses.new_zeros(ids.numel()).scatter_add(0, inverse, losses)
    return ids, sums / counts.to(losses.dtype)


def record_equal_soft_target_ce(logits: Tensor, targets: Tensor, record_ids: Tensor) -> Tensor:
    """Mean within each eligible source record, then equal mean across records."""
    _, record_losses = per_record_soft_target_ce(logits, targets, record_ids)
    return record_losses.mean()
