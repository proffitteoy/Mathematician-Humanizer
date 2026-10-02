"""Evaluation-only integration of reviewed prefix reuse and fixed score reduction.

This module performs no I/O or fitting. Learned causal state lives only in one
document's prefix iterator; only parameter-independent summaries enter ``cache``.
TEST and davinci records are outside this development scorer's scope.
"""
import math

import torch

from .evaluation_reuse import evaluate_permutations, evaluate_prefix_stream
from .models import IndependentFamilies, PrefixModel, TrainingMean
from .objectives import DocumentScore, family_loss
from .plan import transform_signature
from .schema import make_model_packet, permute_packet
from .static_prefix_cache import StaticPrefixCache


def _orders(count, prefix_length, seed, preserve_last):
    """Separate seeded draws, including repeated orders on very short prefixes."""
    for rep in range(count):
        generator = torch.Generator().manual_seed(seed + rep)
        if preserve_last:
            yield torch.cat([torch.randperm(prefix_length - 1, generator=generator),
                             torch.tensor([prefix_length - 1])])
        else:
            yield torch.randperm(prefix_length, generator=generator)


def _permuted_predictions(model, packet, orders, cache):
    if type(model) is PrefixModel and model.name == 'F4':
        return evaluate_permutations(model, packet, orders, summary_cache=cache)
    if type(model) is IndependentFamilies:
        # Every branch sees the same ten declared orders. Its local outputs
        # are restored to their global coordinates before family reduction.
        outputs = torch.zeros((len(orders), model.dimensions))
        for branch, indices in zip(model.models, model.target_indices):
            local = evaluate_permutations(branch, packet, orders, summary_cache=cache)
            index = torch.tensor(indices)[None, :].expand(len(orders), -1)
            outputs = outputs.scatter(1, index, local)
        return outputs
    # F0 and nonrecurrent permutation controls retain their reference forward.
    return torch.stack([model(permute_packet(packet, order)) for order in orders])


def _progress(progress_guard):
    if progress_guard is not None:
        progress_guard()


def _ordered_predictions(model, record, positions, transform, cache, progress_guard):
    if type(model) is TrainingMean:
        for position in positions:
            _progress(progress_guard)
            prediction = model(make_model_packet(record, position, transform))
            _progress(progress_guard)
            yield position, prediction
        return
    # Missing targets and min_prefix can leave gaps. Advance the causal state
    # through those observed units, without inventing scored targets for them.
    def packets():
        for cutoff in range(1, positions[-1] + 1):
            _progress(progress_guard)
            yield make_model_packet(record, cutoff, transform)
    wanted = iter(positions)
    position = next(wanted)
    for cutoff, prediction in enumerate(
            evaluate_prefix_stream(model, packets(), head_batch_size=32, summary_cache=cache), start=1):
        # The reviewed stream computes a whole batch before its first yield.
        # Check immediately then, including the shorter final batch.
        if (cutoff - 1) % 32 == 0:
            _progress(progress_guard)
        if cutoff == position:
            yield position, prediction
            position = next(wanted, None)
    if position is not None:
        raise AssertionError('Prefix evaluation did not cover the fixed target positions')


def _validate_plan(model, plan, cache, permutations, preserve_last, shuffle_seed):
    if type(permutations) is not int or permutations < 0:
        raise ValueError('Permutation count must be a nonnegative integer')
    if type(preserve_last) is not bool or type(shuffle_seed) is not int:
        raise ValueError('A boolean last-preserving flag and integer seed are required')
    if type(cache) is not StaticPrefixCache:
        raise TypeError('A StaticPrefixCache with exact transform provenance is required')
    signature = transform_signature(plan.transform)
    if cache.namespace.transform_sha256 != signature:
        raise ValueError('Static cache does not match the plan TRAIN transform')
    if cache.dimensions != len(plan.transform.ids):
        raise ValueError('Static cache and plan dimensions differ')
    if type(model) not in (PrefixModel, IndependentFamilies, TrainingMean):
        raise TypeError('Only registered prefix architectures or TrainingMean are supported')
    if getattr(model, 'transform_signature', signature) != signature:
        raise ValueError('Model does not match the plan TRAIN transform')
    record_indices = tuple(plan.record_indices)
    if any(type(i) is not int or not 0 <= i < len(plan.records) for i in record_indices):
        raise ValueError('Invalid fixed record index')
    if len(set(record_indices)) != len(record_indices):
        raise ValueError('Duplicate fixed record index')
    # Check metadata for the entire selected population before touching any
    # selected record's measurement tensors or invoking the model.
    for i in record_indices:
        record = plan.records[i]
        if record.split not in ('train', 'dev') or record.arm not in ('human', 'chatgpt'):
            raise ValueError('Development scoring excludes TEST and davinci')
    positions = {}
    for i in record_indices:
        declared = tuple(plan.positions[i])
        if not declared:
            raise ValueError('Selected record has no fixed target positions; cannot omit it')
        if any(type(t) is not int or not 1 <= t < len(plan.records[i].values) for t in declared):
            raise ValueError('Invalid fixed target position')
        if any(a >= b for a, b in zip(declared, declared[1:])):
            raise ValueError('Fixed target positions must be strictly increasing')
        positions[i] = declared
    return record_indices, positions


def _parameter_versions(model):
    return tuple((id(parameter), parameter._version) for parameter in model.parameters())


def _check_evaluation_state(model, versions):
    if any(module.training for module in model.modules()) or _parameter_versions(model) != versions:
        raise RuntimeError('Evaluation state cannot survive parameter updates or training-mode changes')


def _finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise FloatingPointError('Nonfinite loss invalidates the fixed comparison')
    return value


def score_model_reuse(model, plan, *, cache, permutations=0, preserve_last=False,
                      shuffle_seed=47011, progress_guard=None):
    """Return reference-compatible private DocumentScores on the unchanged plan.

    With ``permutations=10``, score all ten separately seeded predictions and
    average their losses. Never deduplicate coincident orders or average
    predictions. Empty joint plans return []; an empty/unsupported target in a
    selected record fails instead of silently changing the population.
    ``progress_guard`` is a zero-argument resource guard called before each
    prefix and immediately after each computed output batch; exceptions pass
    through after the caller's module modes have been restored.
    """
    if progress_guard is not None and not callable(progress_guard):
        raise TypeError('Progress guard must be callable')
    record_indices, positions = _validate_plan(
        model, plan, cache, permutations, preserve_last, shuffle_seed)
    modes = tuple((module, module.training) for module in model.modules())
    versions = _parameter_versions(model)
    rows = []
    try:
        model.eval()
        with torch.no_grad():
            for i in record_indices:
                _check_evaluation_state(model, versions)
                record = plan.records[i]
                losses, families, family_counts = [], {}, {}
                observations = 0
                if permutations:
                    def shuffled_predictions():
                        for position in positions[i]:
                            _progress(progress_guard)
                            packet = make_model_packet(record, position, plan.transform)
                            orders = list(_orders(permutations, position,
                                shuffle_seed + 104729 * i + 15485863 * position, preserve_last))
                            outputs = _permuted_predictions(model, packet, orders, cache)
                            _progress(progress_guard)
                            yield position, outputs
                    predictions = shuffled_predictions()
                else:
                    predictions = ((position, prediction.unsqueeze(0)) for position, prediction in
                        _ordered_predictions(model, record, positions[i], plan.transform, cache, progress_guard))
                for position, outputs in predictions:
                    _check_evaluation_state(model, versions)
                    target, observed = plan.transform.target(record.values[position])
                    if plan.score_indices is not None:
                        keep = torch.zeros_like(observed)
                        keep[list(plan.score_indices)] = True
                        observed &= keep
                    if not torch.isfinite(target[observed]).all():
                        raise FloatingPointError('Nonfinite observed target invalidates comparison')
                    if len(outputs) != (permutations or 1):
                        raise AssertionError('Fixed permutation population changed')
                    parts, family_parts = [], {}
                    for prediction in outputs:
                        loss, by_family = family_loss(
                            prediction, target, observed, plan.transform.families)
                        if loss is None:
                            raise AssertionError('Fixed target support changed')
                        parts.append(_finite(loss))
                        for family, value in by_family.items():
                            family_parts.setdefault(family, []).append(_finite(value))
                    losses.append(_finite(sum(parts) / len(parts)))
                    observations += int(observed.sum())
                    for family, values in family_parts.items():
                        families[family] = families.get(family, 0) + sum(values) / len(values)
                        family_counts[family] = family_counts.get(family, 0) + 1
                if len(losses) != len(positions[i]):
                    raise AssertionError('Fixed target population changed')
                rows.append(DocumentScore(
                    record.question, record.answer, record.component, record.source, record.arm,
                    _finite(sum(losses) / len(losses)), len(losses),
                    {family: _finite(value / family_counts[family]) for family, value in families.items()},
                    family_counts, len(record.values), observations))
            _check_evaluation_state(model, versions)
    finally:
        # Preserve even a caller's mixed child-module modes, including failures.
        for module, was_training in modes:
            module.training = was_training
    return rows
