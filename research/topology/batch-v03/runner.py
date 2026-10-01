"""Portable, one-shot topology batch ledger; frozen T1 is never edited.

CLI requires a caller-authorized manifest and existing pinned local model files.
No file/model/network work occurs at import. Test injection is Python-only.
"""
from __future__ import annotations
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, asdict
import argparse
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import socket
import sys
import time
import uuid
from unittest.mock import patch

CORE_SHA256 = {
    'encoder.py': 'ed29a303783cdbf16c1426807014850960970315907ae6286f30f784bae7c783',
    'phd.py': '44b8a8fcf9f4e1c14c6473aa610f423fe28b8a67f4fbf4e6de208e46c0ad4bd8',
    'encoder-profile.json': '0250576a0cf872ea57115fce0f2663ebaf2a2976a349b35b5d5e1352c7d8d29f',
}
PHD_PROFILE = dict(protocol='paper_prose_v1', seed=20261001, reruns=3,
                   max_cloud_points=512, slope_margin=.001)
UNAVAILABLE_REASONS = frozenset(('fewer_than_50_points', 'resource_cap',
    'invalid_or_insufficient_sampling_grid', 'zero_or_nonfinite_mst_energy',
    'insufficient_distinct_points', 'distance_overflow',
    'slope_outside_stable_profile', 'a_rerun_outside_stable_profile'))


def digest(blob): return hashlib.sha256(blob).hexdigest()
def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf-8')
def require(value, reason):
    if not value: raise FatalRunError(reason)


class FatalRunError(RuntimeError):
    """Integrity, network, resource or persistence error: stop the whole batch."""
    def __init__(self, reason): self.reason = reason; super().__init__(reason)


class RecordError(ValueError):
    """Expected record-local input/output problem; keep the selected record."""
    def __init__(self, reason): self.reason = reason; super().__init__(reason)


@dataclass(frozen=True)
class Limits:
    wall_seconds: float = 1800
    rss_mib: int = 3072
    private_bytes: int = 50_000_000
    max_records: int = 10_000
    source_bytes: int = 1_048_576
    cpu_threads: int = 2

    def validate(self):
        require(type(self.wall_seconds) in (int, float) and
                math.isfinite(self.wall_seconds) and self.wall_seconds > 0,
                'invalid_wall_budget')
        require(all(type(x) is int and x > 0 for x in
                    (self.rss_mib, self.private_bytes, self.max_records, self.source_bytes)),
                'invalid_resource_budget')
        require(self.cpu_threads == 2 and self.source_bytes <= 1_048_576,
                'unsupported_execution_profile')


def peak_rss_kib():
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (ImportError, AttributeError):
        raise FatalRunError('rss_monitor_unavailable') from None
    return int(math.ceil(value / 1024)) if sys.platform == 'darwin' else int(value)


class Budget:
    """Checked limits, including each operation's before/after boundary.

    No claim of a kernel memory cap or preemption inside arbitrary extension code.
    A separate reserved terminal receipt remains writable after a normal cap stop.
    """
    def __init__(self, out, limits, *, clock=time.monotonic, rss=peak_rss_kib):
        limits.validate(); self.out = Path(out); self.limits = limits
        self.clock = clock; self.rss = rss; self.start = clock(); self.network_attempts = 0
        self.reserve = 0; self.peak = 0

    def size(self):
        return sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())

    def check(self):
        if self.network_attempts: raise FatalRunError('network_attempt')
        if self.clock() - self.start >= self.limits.wall_seconds:
            raise FatalRunError('wall_cap')
        self.peak = max(self.peak, self.rss())
        if self.peak > self.limits.rss_mib * 1024: raise FatalRunError('rss_cap')
        if self.size() > self.limits.private_bytes - self.reserve:
            raise FatalRunError('private_disk_cap')

    def reserve_finalization(self, skeleton):
        # Compact ledger retains all selected rows even if finalization is needed
        # after a resource stop; estimate using worst terminal stage/reason strings.
        inflated = json.loads(json.dumps(skeleton))
        for row in inflated['records']:
            row.update(status='not_run', stage='run_control', reason='x' * 96,
                private_result={'file': 'result-000000.private.json', 'sha256': 'f'*64},
                dimension=1.7976931348623157e308,
                tokenization={key: 2**63-1 for key in (
                    'untruncated_tokens_including_specials',
                    'input_tokens_including_specials_and_padding', 'retained_tokens',
                    'excluded_special_or_padding_tokens', 'tokens_removed_by_truncation',
                    'truncation_configured', 'was_truncated')})
        self.reserve = 2 * len(encoded(inflated)) + 65_536
        require(self.reserve < self.limits.private_bytes // 2, 'ledger_reserve_exceeds_budget')

    def write(self, path, blob, *, replace=False, terminal=False):
        path = Path(path)
        if not terminal: self.check()
        require(path.parent == self.out or self.out in path.parents, 'output_path_escape')
        if not replace and path.exists(): raise FatalRunError('output_already_exists')
        ceiling = self.limits.private_bytes if terminal else self.limits.private_bytes - self.reserve
        # Atomic temp file coexists with old target; count that transient disk use.
        if self.size() + len(blob) > ceiling: raise FatalRunError('private_disk_cap')
        # Each commit owns a unique sibling. A failed previous replace/link must
        # not prevent the reserved terminal ledger from being persisted.
        temp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
        failure = None
        try:
            with temp.open('xb') as stream:
                stream.write(blob); stream.flush(); os.fsync(stream.fileno())
            if replace: os.replace(temp, path)
            else:
                # link is exclusive even against a competing writer.
                os.link(temp, path)
            require(digest(path.read_bytes()) == digest(blob), 'output_readback_mismatch')
        except FatalRunError as error: failure = error
        except OSError: failure = FatalRunError('output_io_failure')
        finally:
            try: temp.unlink(missing_ok=True)
            except OSError:
                # Keep the original failure if any; an orphan is still counted
                # by size(). Never silently report a successful cleanup.
                if failure is None: failure = FatalRunError('output_temp_cleanup_failure')
        if failure is not None: raise failure from None
        # A file fsync alone does not commit its directory entry after link or
        # rename. Fail explicitly if this local filesystem cannot provide it.
        descriptor = None
        try:
            descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            os.fsync(descriptor)
        except OSError: raise FatalRunError('output_directory_sync_failure') from None
        finally:
            if descriptor is not None: os.close(descriptor)
        return digest(blob)

    def resources(self):
        return {'wall_seconds': max(0., self.clock() - self.start),
                'peak_rss_kib': self.peak, 'network_attempts': self.network_attempts,
                'private_bytes': self.size(), 'budgets': asdict(self.limits),
                'limits_kind': 'checked_at_safe_boundaries_not_kernel_prevention',
                'new_download_bytes': 0, 'gpu': False}


@contextmanager
def offline_guard(budget):
    def deny(*args, **kwargs):
        budget.network_attempts += 1
        raise FatalRunError('network_attempt')
    # The counter remains fatal even when an encoder catches the raised exception.
    with patch.object(socket.socket, 'connect', deny), \
         patch.object(socket.socket, 'connect_ex', deny), \
         patch.object(socket.socket, 'sendto', deny), \
         patch.object(socket, 'create_connection', deny), \
         patch.object(socket, 'getaddrinfo', deny):
        yield


def validate_manifest(value, limits):
    """Manifest identity is batch-level; absent source paths are record failures."""
    require(type(value) is dict and value.get('schema') == 'topology-fixed-inputs/0.2',
            'manifest_schema')
    require(set(value) == {'schema', 'data_kind', 'records'}, 'manifest_fields')
    require(value['data_kind'] in ('synthetic_fixture', 'licensed_natural'), 'manifest_data_kind')
    rows = value['records']
    require(type(rows) is list and 0 < len(rows) <= limits.max_records, 'manifest_record_count')
    ids = set()
    for row in rows:
        require(type(row) is dict and set(row) <= {'record_id', 'relative_path', 'sha256'},
                'manifest_record_fields')
        require(type(row.get('record_id')) is str and 0 < len(row['record_id']) <= 256,
                'manifest_record_identity')
        require(row['record_id'] not in ids, 'duplicate_selected_record'); ids.add(row['record_id'])
        sha = row.get('sha256')
        require(type(sha) is str and len(sha) == 64 and all(c in '0123456789abcdef' for c in sha),
                'missing_or_invalid_source_digest')
        if row.get('relative_path') is not None:
            require(type(row['relative_path']) is str and len(row['relative_path']) <= 4096,
                    'manifest_source_path_type')
    return rows


def source_text(entry, root, cap):
    relative = entry.get('relative_path')
    if relative is None: raise RecordError('missing_source_path')
    if not relative: raise RecordError('empty_source_path')
    path = Path(relative)
    require(not path.is_absolute() and '..' not in path.parts, 'source_path_escape')
    root = Path(root).resolve(); path = (root / path).resolve()
    require(root in path.parents, 'source_path_escape')
    try:
        if not path.is_file(): raise RecordError('missing_source')
        if path.stat().st_size > cap: raise RecordError('source_byte_cap')
        with path.open('rb') as stream: raw = stream.read(cap + 1)
    except (FileNotFoundError, NotADirectoryError): raise RecordError('missing_source') from None
    except PermissionError: raise RecordError('source_unreadable') from None
    except OSError: raise RecordError('source_read_failure') from None
    if len(raw) > cap: raise RecordError('source_byte_cap')
    require(digest(raw) == entry['sha256'], 'source_hash_mismatch')
    try: text = raw.decode('utf-8')
    except UnicodeDecodeError: raise RecordError('invalid_utf8') from None
    if not text or text.isspace(): raise RecordError('empty_source')
    return text


def verify_core_files(directory):
    directory = Path(directory).resolve()
    for name, sha in CORE_SHA256.items():
        try: raw = (directory / name).read_bytes()
        except OSError: raise FatalRunError('core_file_missing') from None
        require(digest(raw) == sha, 'core_hash_mismatch')


def load_core(directory):
    """Only the existing pinned encoder/PHD core may be executed by the CLI."""
    directory = Path(directory).resolve(); verify_core_files(directory)
    modules = {}
    for name in ('encoder', 'phd'):
        key = '_topology_batch_pinned_' + name
        spec = importlib.util.spec_from_file_location(key, directory / (name + '.py'))
        module = importlib.util.module_from_spec(spec); sys.modules[key] = module
        spec.loader.exec_module(module); modules[name] = module
    def factory(model_dir):
        # Check pinned local assets before initializing a library model loader.
        enc = modules['encoder']
        try: enc.verify_model_files(model_dir, enc.load_profile())
        except (OSError, ValueError): raise FatalRunError('model_asset_verification_failed') from None
        import torch
        torch.set_num_threads(2)
        if torch.get_num_interop_threads() != 2:
            try: torch.set_num_interop_threads(2)
            except RuntimeError: raise FatalRunError('fresh_cpu2_process_required') from None
        return enc.LocalEncoder(model_dir)
    factory.verify_assets = lambda model_dir: modules['encoder'].verify_model_files(
        model_dir, modules['encoder'].load_profile())
    def estimator(cloud): return modules['phd'].estimate(cloud, modules['phd'].Config(**PHD_PROFILE))
    return factory, estimator


def validate_extraction(cloud, meta, text):
    import numpy as np
    if not isinstance(cloud, np.ndarray) or cloud.ndim != 2 or cloud.shape[1] != 768:
        raise RecordError('invalid_extraction')
    if cloud.dtype != np.float32 or not np.isfinite(cloud).all() or len(cloud) > 512:
        raise RecordError('invalid_extraction')
    try:
        require(meta['profile_sha256'] == CORE_SHA256['encoder-profile.json'], 'encoder_profile_mismatch')
        require(meta['source']['utf8_sha256'] == digest(text.encode()), 'encoder_source_hash_mismatch')
        t = meta['tokenization']; full = t['untruncated_tokens_including_specials']
        count = t['input_tokens_including_specials_and_padding']; retained = t['retained_tokens']
        excluded = t['excluded_special_or_padding_tokens']; removed = t['tokens_removed_by_truncation']
        if t['truncation_configured'] is not True: raise RecordError('invalid_extraction')
        if not all(type(v) is int and v >= 0 for v in (full, count, retained, excluded, removed)):
            raise RecordError('invalid_extraction')
        if not (retained == len(cloud) and retained + excluded == count <= min(full, 512)
                and removed == full - count and type(t['was_truncated']) is bool
                and t['was_truncated'] == (full > count)):
            raise RecordError('invalid_extraction')
        blob = io.BytesIO(); np.save(blob, cloud, allow_pickle=False); raw = blob.getvalue()
        require(meta['cloud']['npy_sha256'] == digest(raw), 'cloud_hash_mismatch')
        if meta['cloud']['shape'] != list(cloud.shape) or meta['cloud']['dtype'] != str(cloud.dtype):
            raise RecordError('invalid_extraction')
        encoded(meta)  # Metadata must be finite JSON; no implicit stringification.
        return raw
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, (FatalRunError, RecordError)): raise
        raise RecordError('invalid_extraction') from None


def validate_estimate(value, points):
    if type(value) is not dict or not {'status', 'n_points', 'dimension'} <= set(value):
        raise RecordError('invalid_estimate_result')
    if value.get('status') not in ('ok', 'unavailable') or value.get('n_points') != points:
        raise RecordError('invalid_estimate_result')
    if value['status'] == 'ok':
        d = value.get('dimension')
        if type(d) not in (float, int) or not math.isfinite(d) or d <= 0:
            raise RecordError('invalid_estimate_result')
    elif value.get('dimension') is not None or value.get('reason') not in UNAVAILABLE_REASONS:
        raise RecordError('invalid_estimate_result')
    try: encoded(value)
    except (TypeError, ValueError): raise RecordError('invalid_estimate_result') from None


def summarize(ledger, resources):
    rows = ledger['records']; good = [r['dimension'] for r in rows if r['status'] == 'ok']
    tok = [r['tokenization'] for r in rows if r.get('tokenization') is not None]
    def ranges(values): return [min(values), max(values)] if values else None
    sorted_good = sorted(good)
    median = None if not good else (sorted_good[(len(good)-1)//2] + sorted_good[len(good)//2]) / 2
    return {
        'schema': 'topology-batch-aggregate/0.3-draft', 'run_status': ledger['status'],
        'fixed_selection_processing_complete': ledger['status'] != 'stopped',
        'partial_numeric_diagnostics_only': ledger['status'] == 'stopped',
        'stop_reason': ledger['stop_reason'], 'manifest_sha256': ledger['manifest_sha256'],
        'runner_sha256': ledger['runner_sha256'], 'pinned_core_used': ledger['pinned_core_used'],
        'data_kind': ledger['data_kind'], 'selected_records': len(rows),
        'record_status_counts': dict(Counter(r['status'] for r in rows)),
        'record_failure_reasons': dict(Counter(r['reason'] for r in rows if r['status'] == 'failed')),
        'numerical_abstention_reasons': dict(Counter(r['reason'] for r in rows if r['status'] == 'unavailable')),
        'extraction_metadata_records': len(tok),
        'truncated_records': sum(x['was_truncated'] for x in tok),
        'truncation_unknown_records': len(rows) - len(tok),
        'untruncated_token_count_range': ranges([x['untruncated_tokens_including_specials'] for x in tok]),
        'retained_points_range': ranges([x['retained_tokens'] for x in tok]),
        'dimension_conditional_on_numerical_success':
            {'n': len(good), 'min': min(good) if good else None, 'max': max(good) if good else None, 'median': median},
        'repeat_first_selected': ledger['repeat_first_selected'],
        'repeat_status': ledger['repeat_status'],
        'resources': resources, 'core_sha256': CORE_SHA256, 'phd_profile': PHD_PROFILE,
        'scope': 'Exact source-view prefixes, possibly truncated; no human-origin, author, body-only style, classifier or fitted-model claim',
        'uncertainty_scope': 'Numerical rerun dispersion is conditional finite-cloud sampling variation, not population uncertainty',
        'new_fit': False,
    }


def run_batch(*, manifest, manifest_sha256, source_root, model_dir, topology_dir,
              out, limits=Limits(), save_clouds=False, repeat_first=True,
              core_loader=load_core, budget_factory=Budget):
    """One fixed selection, no replacement or automatic retry. Injection is for tests.

    The caller owns natural-data authorization; a local CLI flag does not grant it.
    Fatal stops retain prior results plus explicit failed/not_run rows. If the OS
    kills the process, the last durable ledger may contain in_progress/pending;
    those are incomplete, never implicitly successful or scored as zero.
    """
    limits.validate(); entries = validate_manifest(manifest, limits)
    require(type(save_clouds) is bool and type(repeat_first) is bool, 'boolean_option_required')
    require(type(manifest_sha256) is str and len(manifest_sha256) == 64 and
            all(c in '0123456789abcdef' for c in manifest_sha256), 'manifest_digest')
    out = Path(out).resolve(); source_root = Path(source_root).resolve()
    require(out != source_root and source_root not in out.parents, 'output_inside_source_tree')
    require(out != Path(topology_dir).resolve() and Path(topology_dir).resolve() not in out.parents,
            'output_inside_core_tree')
    out.mkdir(parents=True, exist_ok=True)
    require(not any(out.iterdir()), 'one_shot_output_directory_not_empty')
    runner_sha = digest(Path(__file__).read_bytes())
    ledger = {'schema': 'topology-fixed-ledger/0.3-draft', 'manifest_sha256': manifest_sha256,
              'runner_sha256': runner_sha, 'pinned_core_used': core_loader is load_core,
              'data_kind': manifest['data_kind'], 'status': 'running', 'stop_reason': None,
              'repeat_first_selected': repeat_first, 'repeat_status': 'pending' if repeat_first else 'not_requested',
              'records': [dict(index=i, record_id=e['record_id'], status='pending', stage=None,
                   reason=None, private_result=None, tokenization=None, dimension=None) for i, e in enumerate(entries)]}
    budget = budget_factory(out, limits); budget.reserve_finalization(ledger)
    budget.write(out/'run.started.private.json', encoded({'manifest_sha256': manifest_sha256,
        'selected_records': len(entries), 'core_sha256': CORE_SHA256, 'limits': asdict(limits),
        'save_clouds': save_clouds, 'repeat_first_selected': repeat_first}), terminal=True)
    def persist(terminal=False):
        return budget.write(out/'ledger.private.json', encoded(ledger), replace=True, terminal=terminal)
    persist(terminal=True); current = None; stage = 'core_admission'; encoder = None
    try:
        with offline_guard(budget):
            budget.check(); factory, estimate = core_loader(topology_dir); budget.check()
            for i, entry in enumerate(entries):
                current = i; row = ledger['records'][i]; row.update(status='in_progress', stage='input')
                persist(); budget.check(); stage = 'input'; detail = None
                try:
                    text = source_text(entry, source_root, limits.source_bytes); budget.check()
                    if encoder is None:
                        stage = 'model_initialization'
                        try: encoder = factory(model_dir)
                        except FatalRunError: raise
                        except Exception: raise FatalRunError('model_initialization_failed') from None
                        budget.check()
                    stage = 'encode'; row['stage'] = stage
                    try: cloud, meta = encoder.encode(text)
                    except (FatalRunError, MemoryError): raise
                    except Exception: raise RecordError('encode_exception') from None
                    budget.check(); raw_cloud = validate_extraction(cloud, meta, text)
                    row['tokenization'] = {key: meta['tokenization'][key] for key in (
                        'untruncated_tokens_including_specials',
                        'input_tokens_including_specials_and_padding', 'retained_tokens',
                        'excluded_special_or_padding_tokens', 'tokens_removed_by_truncation',
                        'truncation_configured', 'was_truncated')}
                    detail = {'index': i, 'extraction': meta, 'phd': None}
                    if i == 0 and repeat_first:
                        stage = 'repeat_encode'
                        try: other, meta2 = encoder.encode(text)
                        except (FatalRunError, MemoryError): raise
                        except Exception: raise RecordError('repeat_encode_exception') from None
                        budget.check(); repeated_raw = validate_extraction(other, meta2, text)
                        require(raw_cloud == repeated_raw, 'repeat_mismatch')
                        ledger['repeat_status'] = 'exact_same_process_cloud_match'
                    if save_clouds:
                        budget.write(out/f'cloud-{i:06d}.npy', raw_cloud)
                    stage = 'estimate'; row['stage'] = stage
                    try: result = estimate(cloud)
                    except (FatalRunError, MemoryError): raise
                    except Exception: raise RecordError('estimate_exception') from None
                    budget.check(); validate_estimate(result, len(cloud)); detail['phd'] = result
                    row.update(status=result['status'], reason=result.get('reason'), dimension=result['dimension'])
                except RecordError as error:
                    # A swallowed network failure is still a fatal whole-run stop.
                    budget.check(); row.update(status='failed', stage=stage, reason=error.reason, dimension=None)
                    if i == 0 and repeat_first and ledger['repeat_status'] == 'pending':
                        ledger['repeat_status'] = 'first_selected_unavailable'
                if detail is not None:
                    detail.update(status=row['status'], stage=row['stage'], reason=row['reason'])
                    name = f'result-{i:06d}.private.json'; sha = budget.write(out/name, encoded(detail))
                    row['private_result'] = {'file': name, 'sha256': sha}
                persist(); budget.check(); current = None
            stage = 'final_integrity'
            if core_loader is load_core:
                verify_core_files(topology_dir)
                if encoder is not None:
                    budget.check()
                    try: factory.verify_assets(model_dir)
                    except (OSError, ValueError): raise FatalRunError('model_asset_verification_failed') from None
                    budget.check()
            require(digest(Path(__file__).read_bytes()) == runner_sha, 'runner_changed_during_run')
            ledger['status'] = 'complete' if all(r['status'] == 'ok' for r in ledger['records']) else 'complete_with_unavailable_records'
    except BaseException as error:
        if budget.network_attempts: reason = 'network_attempt'
        elif isinstance(error, FatalRunError): reason = error.reason
        elif isinstance(error, MemoryError): reason = 'memory_error'
        elif isinstance(error, KeyboardInterrupt): reason = 'interrupted'
        else: reason = 'unexpected_batch_error'
        ledger['status'] = 'stopped'; ledger['stop_reason'] = reason
        for i, row in enumerate(ledger['records']):
            if i == current or row['status'] in ('pending', 'in_progress'):
                row.update(status='failed' if i == current else 'not_run', stage=stage if i == current else 'run_control', reason=reason if i == current else 'batch_stopped', dimension=None)
        if ledger['repeat_status'] == 'pending': ledger['repeat_status'] = 'not_completed'
    # Terminal writes bypass elapsed/RSS checks but remain within reserved bytes.
    ledger_hash = persist(terminal=True)
    report = summarize(ledger, budget.resources()); report['private_ledger_sha256'] = ledger_hash
    report_hash = budget.write(out/'aggregate.public.json', encoded(report), terminal=True)
    budget.write(out/'run-finished.private.json', encoded({'status': ledger['status'],
        'ledger_sha256': ledger_hash, 'aggregate_sha256': report_hash,
        'manifest_sha256': manifest_sha256, 'resources': budget.resources()}), terminal=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'source-root', 'model-dir', 'topology-dir', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--authorized-local-run', action='store_true', required=True,
                        help='Records caller approval; does not itself grant natural-data access')
    parser.add_argument('--save-clouds', action='store_true')
    args = parser.parse_args(argv)
    raw = args.manifest.read_bytes(); require(digest(raw) == args.manifest_sha256, 'manifest_hash_mismatch')
    report = run_batch(manifest=json.loads(raw), manifest_sha256=digest(raw), source_root=args.source_root,
        model_dir=args.model_dir, topology_dir=args.topology_dir, out=args.out, save_clouds=args.save_clouds)
    print(json.dumps({'status': report['run_status'], 'selected_records': report['selected_records'],
                      'record_status_counts': report['record_status_counts'], 'stop_reason': report['stop_reason']}))
    return 2 if report['run_status'] == 'stopped' else 0


if __name__ == '__main__':
    raise SystemExit(main())
