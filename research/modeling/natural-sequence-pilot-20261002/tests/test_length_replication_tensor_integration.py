#!/usr/bin/env python3
"""Idle-gated, synthetic-only integration for the fixed two registered length-control replications.

Importing this file is model-free. Invoke the CLI only after the parent confirms
an idle numerical slot. The receipt is evidence, never optimizer authorization.
Only frozen public source is read; no empirical transform/cache/ledger is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

FIELDS = ('prefix_values', 'prefix_observed', 'prefix_opportunity', 'prefix_opportunity_known')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_sources(source_root, candidate_root):
    manifest_path = candidate_root / 'LENGTH_REPLICATION_SOURCE_MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or 'private' in relative.parts:
            raise AssertionError('Only frozen public source may be inspected')
        path = candidate_root / relative
        if not path.is_file():
            path = source_root / relative
        if sha(path) != expected:
            raise AssertionError('Source binding failed: ' + name)
    harness_name = 'tests/test_length_replication_tensor_integration.py'
    if manifest['files'].get(harness_name) != sha(__file__):
        raise AssertionError('This exact tensor harness must be in the reviewed manifest')
    return sha(manifest_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--candidate-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--idle-slot-approved', action='store_true')
    parser.add_argument('--cpu-core', type=int, required=True)
    args = parser.parse_args()
    if not args.idle_slot_approved:
        raise PermissionError('A separately confirmed idle numerical slot is required')
    if args.cpu_core not in os.sched_getaffinity(0):
        raise PermissionError('Requested CPU is outside the current allowed affinity')
    os.sched_setaffinity(0, {args.cpu_core})
    # Tiny forward/backward checks; no optimizer is instantiated or updated.
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    source_root, candidate_root = args.source_root.resolve(), args.candidate_root.resolve()
    manifest_hash = verify_sources(source_root, candidate_root)
    sys.path[:0] = [str(candidate_root), str(source_root)]
    import torch
    from experimental_natural.schema import Catalog, PrefixPacket
    from experimental_natural.transforms import FrozenTransform
    from experimental_natural.plan import registered_run_grid, build_registered_model, transform_signature
    from experimental_natural.objectives import family_loss
    from experimental_natural.train import TrainingConfig
    from experimental_natural.static_prefix_cache import StaticPrefixCache, CacheNamespace
    from experimental_natural.evaluation_reuse import evaluate_prefix_stream, evaluate_cached_batch, _cached_batch_impl
    import run_length_replication_phase as runner

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    catalog = Catalog.from_contract(source_root / 'training_contract.json')
    dimensions = len(catalog.ids)
    assert dimensions == 70
    active = torch.ones(dimensions, dtype=torch.bool)
    active[5] = False
    eligible = active.clone()
    eligible[3] = False
    eligible[4] = False
    assert int(eligible.sum()) == 67
    transform = FrozenTransform(
        catalog.ids, catalog.families, catalog.transforms, catalog.structural_indices,
        torch.zeros(dimensions, dtype=torch.float64), torch.ones(dimensions, dtype=torch.float64),
        active, eligible, tuple([50] * dimensions), None, ('baike', 'web'), 50, 50,
        tuple([50] * dimensions))
    # Entirely synthetic values. No transform fitting or empirical file reads.
    gen = torch.Generator().manual_seed(731)
    values = torch.randn((4, dimensions), generator=gen)
    observed = torch.rand((4, dimensions), generator=gen) > .2
    known = torch.rand((4, dimensions), generator=gen) > .25
    opportunity = torch.randint(1, 20, (4, dimensions), generator=gen).float()
    # Explicit typed cases: observed zero; missing but known opportunity; and
    # missing opportunity, with distinct mask paths retained by the controls.
    values[0, 0] = 0; observed[0, 0] = True; known[0, 0] = True
    observed[0, 1] = False; known[0, 1] = True
    observed[0, 2] = False; known[0, 2] = False
    values[:, ~active] = 0
    values[~observed] = 0
    opportunity[~known] = 0
    packet = PrefixPacket(values, observed, opportunity, known, 4).validate(dimensions)
    packets = [PrefixPacket(*(getattr(packet, field)[:n].clone() for field in FIELDS), n)
               for n in range(1, 5)]
    for p in packets: p.validate(dimensions)
    raw_targets = torch.arange(1, dimensions + 1).float() / dimensions
    target, target_mask = transform.target(raw_targets)
    assert torch.equal(target_mask, eligible)
    expected_targets = tuple(torch.where(eligible)[0].tolist())
    namespace = CacheNamespace(transform_signature(transform), '7' * 64)
    registry = {run['id']: run for run in registered_run_grid()}
    config = TrainingConfig()
    assert (config.learning_rate, config.weight_decay, config.batch_questions,
            config.gradient_norm_cap, config.max_epochs, config.patience) == (.001, .001, 32, 1., 100, 10)
    contract = json.loads((source_root / 'training_contract.json').read_text())
    assert contract['training']['optimizer'] == 'Adam'
    checks = {name: True for name in ('registered_factory', 'typed_masks', 'full_target_support',
              'forward_loss_gradient', 'unchanged_optimizer_contract', 'direct_vs_cached_dev',
              'prohibited_path_invariance')}
    outcomes = []

    def altered(original, *, change_values=False, change_opportunity=False, nonstructural_only=False):
        fields = {field: getattr(original, field).clone() for field in FIELDS}
        selected = list(range(dimensions))
        if nonstructural_only:
            selected = [i for i in selected if i not in catalog.structural_indices]
            fields['prefix_observed'][:, selected] = ~fields['prefix_observed'][:, selected]
            fields['prefix_opportunity_known'][:, selected] = ~fields['prefix_opportunity_known'][:, selected]
        if change_values:
            fields['prefix_values'][:, selected] += 17
        if change_opportunity:
            fields['prefix_opportunity'][:, selected] += 41
        fields['prefix_values'][~fields['prefix_observed']] = 0
        fields['prefix_values'][:, ~active] = 0
        fields['prefix_opportunity'][~fields['prefix_opportunity_known']] = 0
        return PrefixPacket(*(fields[field] for field in FIELDS), original.prefix_unit_count).validate(dimensions)

    for run_id in runner.CONTROL_ORDER:
        recipe = runner.validate_registry(run_id, registry)
        assert runner.control_training_arguments(recipe) == {'seed': recipe['seed'], 'run_id': run_id, 'source': None, 'shuffle_training': False}
        model = build_registered_model(catalog, recipe, transform)
        assert model.name == 'F4' and model.width == 32 and model.initialization_seed == recipe['seed']
        assert model.transform_signature == transform_signature(transform)
        assert model.target_indices == expected_targets and model.targets == dimensions
        assert tuple(model.output_indices.tolist()) == expected_targets
        if recipe['mode'] == 'length':
            assert model.view.indices == catalog.structural_indices
        else:
            assert model.view.indices == tuple(range(dimensions))
        reference = torch.stack([model(p) for p in packets])
        assert reference.shape == (4, dimensions)
        assert torch.equal(reference[:, ~eligible], torch.zeros_like(reference[:, ~eligible]))
        losses = [family_loss(row, target, target_mask, catalog.families)[0] for row in reference]
        reference_loss = torch.stack(losses).mean()
        reference_loss.backward()
        gradients = {name: parameter.grad.clone() for name, parameter in model.named_parameters()}
        assert all(torch.isfinite(g).all() for g in gradients.values())
        model.zero_grad(set_to_none=True)
        model.eval()
        cache = StaticPrefixCache(dimensions, namespace, 1 << 20)
        projected = cache.project(cache.get(packet), model.view, model.include_covariance)
        torch.testing.assert_close(projected, model.view.summarize(packet, model.include_covariance), atol=1e-6, rtol=1e-6)
        reused = _cached_batch_impl(model, packets, cache)
        reused_loss = torch.stack([family_loss(row, target, target_mask, catalog.families)[0] for row in reused]).mean()
        reused_loss.backward()
        torch.testing.assert_close(reused, reference, atol=1e-6, rtol=1e-6)
        torch.testing.assert_close(reused_loss, reference_loss, atol=1e-6, rtol=1e-6)
        gradient_max = 0.
        for name, parameter in model.named_parameters():
            torch.testing.assert_close(parameter.grad, gradients[name], atol=1e-5, rtol=1e-5)
            gradient_max = max(gradient_max, float((parameter.grad - gradients[name]).abs().max()))
        cached_dev = evaluate_cached_batch(model, packets, cache)
        streamed_dev = torch.stack(list(evaluate_prefix_stream(model, packets, head_batch_size=2, summary_cache=cache)))
        torch.testing.assert_close(cached_dev, reference.detach(), atol=1e-6, rtol=1e-6)
        torch.testing.assert_close(streamed_dev, reference.detach(), atol=1e-6, rtol=1e-6)
        if recipe['mode'] == 'mask_opportunity':
            mutant = altered(packet, change_values=True)
        elif recipe['mode'] == 'pure_mask':
            mutant = altered(packet, change_values=True, change_opportunity=True)
        else:
            mutant = altered(packet, change_values=True, change_opportunity=True, nonstructural_only=True)
        # Path removal must be exact, independent of head cancellation.
        assert torch.equal(model.view.local(mutant), model.view.local(packet))
        assert torch.equal(model.view.summarize(mutant, model.include_covariance), model.view.summarize(packet, model.include_covariance))
        with torch.no_grad():
            assert torch.equal(model(mutant), model(packet))
        if recipe['mode'] != 'length':
            local = model.view.local(packet)
            # Nuisance views retain observed and known mask types in registered order.
            assert torch.equal(local[:, :dimensions], observed.float())
            assert torch.equal(local[:, -dimensions:], known.float())
            if recipe['mode'] == 'pure_mask':assert local.shape[1] == 2 * dimensions
            else:assert local.shape[1] == 3 * dimensions
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 < 768 * 1024**2
        outcomes.append({'run_id': run_id, 'eligible_targets': len(expected_targets),
                         'direct_cached_max_abs_error': float((cached_dev-reference.detach()).abs().max()),
                         'direct_stream_max_abs_error': float((streamed_dev-reference.detach()).abs().max()),
                         'gradient_max_abs_error': gradient_max})
        del cache, model, reference, reused, gradients, cached_dev, streamed_dev
    assert verify_sources(source_root, candidate_root) == manifest_hash
    result = {'status': 'passed', 'source_manifest_sha256': manifest_hash,
              'run_ids': list(runner.CONTROL_ORDER), 'synthetic_only': True,
              'empirical_reads': 0, 'TEST_reads': 0, 'optimizer_steps': 0, 'optimizer_fits': 0,
              'checks': checks, 'outcomes': outcomes, 'harness_sha256': sha(__file__),
              'measured_CPU_seconds': time.process_time(),
              'peak_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              'assigned_cpu_core': args.cpu_core,
              'limitations': ['Synthetic tensor integration only; no empirical fit, outcome, or budget-admission evidence']}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
