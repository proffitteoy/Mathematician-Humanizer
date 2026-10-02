"""Additive, explicitly gated training with durable epoch-boundary recovery.

TRAIN uses the reference packet/forward/loss path. DEV evaluates the complete
fixed plan through ``score_model_reuse``. Only static summaries survive updates.
An interrupted epoch is replayed from the last ledger-committed snapshot; its
already-spent CPU is never replayed backwards. No imports read empirical data.
"""
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
import copy
import fcntl
import hashlib
import json
import math
import os
import random
import re
import resource
import sys
import time
import uuid

import torch

from .objectives import BalancedPlan, aggregate_document_scores, family_loss
from .plan import transform_signature
from .schema import FitAuthorization, assert_fit_scope, make_model_packet, validate_cohort
from .static_prefix_cache import CacheNamespace, StaticPrefixCache
from .train import FIXED_SEEDS, FitLedger, TrainingConfig, _shuffle, deterministic_seed


DAY_SECONDS = 24 * 3600
PHASE_SECONDS = 18 * 3600
HARD_BYTES = 2 * 1024**3
SNAPSHOT_VERSION = 'staged-epoch-recovery/1'


class ResourceStop(RuntimeError):
    """A logged, resumable resource interruption (never a numerical failure)."""


class RecoveryError(ValueError):
    """Recovery identity, integrity, or accounting has not been established."""


def _json_copy(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def _hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _data_digest(records):
    """Bind the already-loaded ordered TRAIN/DEV measurements, never read bodies."""
    digest = hashlib.sha256()
    for record in records:
        meta = {name: getattr(record, name) for name in
                ('question', 'answer', 'component', 'source', 'split', 'arm',
                 'kind', 'panel', 'exposed', 'direct_count_indices', 'measurement_audit')}
        digest.update(json.dumps(meta, sort_keys=True, allow_nan=False).encode())
        for tensor in (record.values, record.opportunity):
            if tensor.device.type != 'cpu':
                raise ValueError('The registered training runtime is CPU only')
            digest.update(str((tuple(tensor.shape), str(tensor.dtype))).encode())
            digest.update(tensor.detach().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _model_identity(model):
    branches = list(model.models) if hasattr(model, 'models') else [model]
    return _json_copy({
        'class': type(model).__module__ + '.' + type(model).__qualname__,
        'representation': repr(model),
        'branches': [{name: (asdict(getattr(branch, name)) if name == 'view'
                            else getattr(branch, name))
                      for name in ('name', 'view', 'width', 'targets', 'target_indices')
                      if hasattr(branch, name)} for branch in branches],
        'state': {name: {'shape': list(value.shape), 'dtype': str(value.dtype),
                         'fixed_indices': value.tolist() if name.endswith('output_indices') else None}
                  for name, value in model.state_dict().items()},
    })


def _code_identity():
    root = Path(__file__).parent
    names = ('staged_training.py', 'train.py', 'schema.py', 'plan.py', 'models.py',
             'objectives.py', 'transforms.py', 'scoring_reuse.py',
             'static_prefix_cache.py', 'evaluation_reuse.py')
    return {name: _hash_file(root / name) for name in names}


def _cpu_for_run(events, run_id):
    return max((max(float(e.get('cpu_seconds', 0)), float(e.get('cpu_seconds_current_fit', 0)))
                for e in events if e.get('run_id') == run_id), default=0.)


def _total_cpu(events):
    return sum(_cpu_for_run(events, run_id) for run_id in {e['run_id'] for e in events})


def _disk_bytes(root):
    return sum(path.stat().st_size for path in Path(root).rglob('*') if path.is_file())


def _peak_rss_bytes():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


@contextmanager
def _ledger_lock(ledger):
    """Serialize staged attempts without replacing the existing global ledger."""
    with ledger.path.with_name(ledger.path.name + '.staged.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RecoveryError('Another staged attempt owns this global ledger') from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


class StagedResourceGuard:
    """Original run/study clocks plus a separately bounded declared phase.

    The global ledger is serialized for the session. Costs of every preceding
    run, including failures, are retained. Call before/after TRAIN batches and
    before every DEV prefix; interruption accounting is durably logged by the
    caller. A hard crash still needs explicit CPU reconciliation.
    """
    def __init__(self, *, config, ledger, run_id, derived_root, events,
                 session_cpu_started, session_monotonic_started, cpu_baseline,
                 run_started_unix, run_cpu_limit_seconds, phase, phase_id):
        self.config = config
        self.ledger = ledger
        self.run_id = run_id
        self.derived_root = Path(derived_root)
        self.session_cpu_started = session_cpu_started
        self.session_monotonic_started = session_monotonic_started
        self.cpu_baseline = cpu_baseline
        self.run_started_unix = run_started_unix
        self.run_cpu_limit_seconds = run_cpu_limit_seconds
        self.phase = phase
        self.phase_id = phase_id
        self._disk_measured_at = None
        self._disk_inventory = None
        self.other_cpu = _total_cpu(events) - _cpu_for_run(events, run_id)
        starts = [float(e['started_unix']) for e in events if e['event'] == 'attempt_started']
        self.global_started_unix = min(starts or [run_started_unix])
        session_unix = time.time() - max(0., time.monotonic() - session_monotonic_started)
        self.run_wall_baseline = max(session_unix - run_started_unix,
            max((float(e.get('wall_seconds', 0)) for e in events if e['run_id'] == run_id), default=0.))
        self.global_wall_baseline = max(session_unix - self.global_started_unix,
            max((float(e.get('global_wall_seconds', 0)) for e in events), default=0.))
        self.phase_wall_baseline = max(session_unix - phase['started_unix'],
            max((float(e.get('phase_wall_seconds', 0)) for e in events
                 if e.get('phase_id') == phase_id), default=0.))

    def accounting(self):
        elapsed = max(0., time.monotonic() - self.session_monotonic_started)
        cpu = self.cpu_baseline + max(0., time.process_time() - self.session_cpu_started)
        now = time.time()
        return {
            'cpu_seconds': cpu,
            'cpu_seconds_current_fit': cpu,
            'wall_seconds': max(now - self.run_started_unix, self.run_wall_baseline + elapsed),
            'global_cpu_seconds': self.other_cpu + cpu,
            'global_wall_seconds': max(now - self.global_started_unix, self.global_wall_baseline + elapsed),
            'phase_id': self.phase_id,
            'phase_cpu_seconds': max(0., self.other_cpu + cpu - self.phase['cpu_baseline']),
            'phase_wall_seconds': max(now - self.phase['started_unix'], self.phase_wall_baseline + elapsed),
        }

    def check(self):
        a = self.accounting()
        ceilings = (
            ('Global CPU ceiling reached', a['global_cpu_seconds'], min(self.ledger.max_cpu_seconds, DAY_SECONDS)),
            ('Global wall ceiling reached', a['global_wall_seconds'], DAY_SECONDS),
            ('Phase CPU ceiling reached', a['phase_cpu_seconds'], self.phase['cpu_limit_seconds']),
            ('Phase wall ceiling reached', a['phase_wall_seconds'], self.phase['wall_limit_seconds']),
            ('Per-run CPU ceiling reached', a['cpu_seconds'], self.run_cpu_limit_seconds),
            ('Per-run wall ceiling reached', a['wall_seconds'], self.config.max_fit_seconds),
            ('RSS ceiling reached', _peak_rss_bytes(), self.config.max_rss_bytes),
            ('Derived-disk ceiling reached', self.disk_bytes(), self.config.max_output_bytes),
        )
        for reason, value, limit in ceilings:
            if value >= limit:
                raise ResourceStop(reason)
        return a

    def disk_bytes(self, refresh=False):
        now = time.monotonic()
        if (not refresh and self._disk_measured_at is not None
                and 0 <= now - self._disk_measured_at < 1.):
            return self._disk_inventory
        ledger_extra = (self.ledger.path.stat().st_size if self.ledger.path.exists()
                        and not self.ledger.path.resolve().is_relative_to(self.derived_root.resolve()) else 0)
        self._disk_inventory = _disk_bytes(self.derived_root) + ledger_extra
        self._disk_measured_at = now
        return self._disk_inventory


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class _BoundedWriter:
    """Torch's sequential zip writer cannot overshoot the derived disk limit."""
    def __init__(self, stream, available):
        self.stream = stream
        self.available = available
        self.written = 0
        self.exceeded = False

    def write(self, data):
        if self.written + len(data) > self.available:
            self.exceeded = True
            raise ResourceStop('Derived-disk ceiling would be exceeded by checkpoint')
        written = self.stream.write(data)
        self.written += written
        return written

    def flush(self):
        return self.stream.flush()

    def tell(self):
        return self.stream.tell()


def _save_immutable(payload, destination, guard):
    """Fsync data and containing directory before publishing its ledger hash."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.tmp')
    guard.check()
    try:
        # Leave bounded headroom for commit/interruption ledger metadata.
        available = max(0, guard.config.max_output_bytes - guard.disk_bytes(refresh=True) - 65536)
        with temporary.open('xb') as stream:
            writer = _BoundedWriter(stream, available)
            try:
                torch.save(payload, writer)
            except RuntimeError as error:
                # The zip footer can mask the original bounded-writer failure.
                if writer.exceeded or isinstance(error.__context__, ResourceStop):
                    raise ResourceStop('Derived-disk ceiling would be exceeded by checkpoint') from error
                raise
            stream.flush()
            os.fsync(stream.fileno())
        digest = _hash_file(temporary)
        os.chmod(temporary, 0o444)
        os.link(temporary, destination)  # Exclusive publication; never overwrite a generation.
        temporary.unlink()
        _fsync_directory(destination.parent)
        guard._disk_measured_at = None
        return digest
    finally:
        if temporary.exists():
            temporary.unlink()


def _secondary_receipt(entry, snapshots):
    """Require the parent's readback attestation before deleting a primary copy.

    Remote store keys are attestations supplied by the parent; this engine has
    no remote storage capability. Local secondary paths are independently
    rehashed here. A receipt never claims executor-independent durability for
    a local path.
    """
    receipt_path = snapshots / (entry['snapshot_sha256'] + '.secondary.json')
    if not receipt_path.is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text())
    except (OSError, ValueError):
        return None
    primary = Path(entry['snapshot_path'])
    if (type(receipt) is not dict or receipt.get('readback_verified') is not True
            or receipt.get('snapshot_sha256') != entry['snapshot_sha256']
            or receipt.get('snapshot_bytes') != primary.stat().st_size):
        return None
    if receipt.get('secondary_path'):
        secondary = Path(receipt['secondary_path'])
        if (not secondary.is_absolute() or not secondary.is_file()
                or secondary.resolve().is_relative_to(snapshots.resolve())
                or secondary.stat().st_size != receipt['snapshot_bytes']
                or _hash_file(secondary) != receipt['snapshot_sha256']):
            return None
    elif not isinstance(receipt.get('secondary_store_key'), str) or not receipt['secondary_store_key'].strip():
        return None
    return receipt


def _commit_snapshot(*, model, optimizer, state, identity, guard, ledger, snapshots):
    guard.check()
    payload = {
        'version': SNAPSHOT_VERSION,
        'identity': identity,
        'epoch': state['epoch'],
        'next_epoch': state['epoch'] + 1,
        'next_sampler_seed': identity['seed'] * 100000 + state['epoch'] + 1,
        'state_dict': copy.deepcopy(model.state_dict()),
        'optimizer_state_dict': copy.deepcopy(optimizer.state_dict()),
        'python_rng_state': random.getstate(),
        'torch_rng_state': torch.get_rng_state(),
        'best_state_dict': state['best_state_dict'],
        'best_optimizer_state_dict': state['best_optimizer_state_dict'],
        'best_dev_score': state['best_dev_score'],
        'best_epoch': state['best_epoch'],
        'stale_epochs': state['stale_epochs'],
        'transform': identity['transform'],
        'accounting': guard.accounting(),
    }
    path = snapshots / ('epoch-%03d-%s.pt' % (state['epoch'], uuid.uuid4().hex))
    digest = _save_immutable(payload, path, guard)
    ledger.append({'event': 'snapshot_committed', 'run_id': identity['run_id'],
                   'epoch': state['epoch'], 'next_epoch': state['epoch'] + 1,
                   'snapshot_path': str(path.resolve()), 'snapshot_sha256': digest,
                   'snapshot_bytes': path.stat().st_size,
                   **guard.accounting()})
    print(json.dumps({'event': 'snapshot_committed', 'run_id': identity['run_id'],
                      'epoch': state['epoch'], 'snapshot_path': str(path.resolve()),
                      'snapshot_sha256': digest, 'snapshot_bytes': path.stat().st_size},
                     sort_keys=True), flush=True)
    # Keep at least two committed primary generations. Older generations are
    # removable only once an independently verified secondary copy exists.
    events = ledger.events()
    commits = [e for e in events if e['event'] == 'snapshot_committed'
               and e['run_id'] == identity['run_id']]
    requested = {e.get('snapshot_sha256') for e in events if e['event'] == 'backup_needed'}
    for entry in commits[:-2]:
        old = Path(entry['snapshot_path'])
        if old.exists():
            if old.parent.resolve() != snapshots.resolve():
                raise RecoveryError('Unexpected recovery snapshot location')
            receipt = _secondary_receipt(entry, snapshots)
            if receipt is None:
                if entry['snapshot_sha256'] not in requested:
                    notice = {'event': 'backup_needed', 'run_id': identity['run_id'],
                              'epoch': entry['epoch'], 'snapshot_path': str(old),
                              'snapshot_sha256': entry['snapshot_sha256'], 'snapshot_bytes': old.stat().st_size}
                    ledger.append({**notice, **guard.accounting()})
                    print(json.dumps(notice, sort_keys=True), flush=True)
                continue
            if _hash_file(old) != entry['snapshot_sha256']:
                raise RecoveryError('An obsolete primary snapshot changed before verified pruning')
            ledger.append({'event': 'snapshot_pruned', 'run_id': identity['run_id'],
                           'snapshot_path': str(old), 'snapshot_sha256': entry['snapshot_sha256'],
                           'snapshot_bytes': old.stat().st_size, 'secondary_recovery_receipt': receipt,
                           **guard.accounting()})
            old.unlink()
            guard._disk_measured_at = None
    _fsync_directory(snapshots)
    return payload


def _load_snapshot(events, identity, snapshots):
    commits = [e for e in events if e['event'] == 'snapshot_committed'
               and e['run_id'] == identity['run_id']]
    if not commits:
        raise RecoveryError('No committed epoch snapshot; cannot silently restart this attempt')
    entry = commits[-1]
    path = Path(entry['snapshot_path'])
    if path.parent.resolve() != snapshots.resolve() or not path.is_file():
        raise RecoveryError('Last committed snapshot is missing or outside the run directory')
    if _hash_file(path) != entry['snapshot_sha256']:
        raise RecoveryError('Last committed snapshot hash mismatch')
    try:
        saved = torch.load(path, map_location='cpu', weights_only=True)
    except Exception as error:
        raise RecoveryError('Last committed snapshot is unreadable') from error
    if saved.get('version') != SNAPSHOT_VERSION or saved.get('identity') != identity:
        raise RecoveryError('Snapshot run/config/transform/bindings identity mismatch')
    epoch = saved.get('epoch')
    if (epoch != entry['epoch'] or saved.get('next_epoch') != epoch + 1
            or saved.get('next_sampler_seed') != identity['seed'] * 100000 + epoch + 1):
        raise RecoveryError('Snapshot epoch/sampler continuity mismatch')
    return saved


def _validate_config(config, natural):
    if not isinstance(config, TrainingConfig):
        raise TypeError('The shared TrainingConfig is required')
    for name in ('learning_rate', 'gradient_norm_cap', 'max_fit_seconds'):
        value = getattr(config, name)
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid ' + name)
    if not math.isfinite(config.weight_decay) or config.weight_decay < 0:
        raise ValueError('Invalid weight_decay')
    for name, maximum in (('max_cpu_threads', 2), ('max_epochs', 100), ('patience', 100),
                          ('max_rss_bytes', HARD_BYTES), ('max_output_bytes', HARD_BYTES)):
        value = getattr(config, name)
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError('Registered resource/epoch ceiling exceeded: ' + name)
    if type(config.batch_questions) is not int or config.batch_questions < 1:
        raise ValueError('Positive batch_questions required')
    if config.max_fit_seconds > DAY_SECONDS:
        raise ValueError('Per-run wall ceiling cannot exceed the original 24 hours')
    if natural:
        fixed = TrainingConfig()
        for name in ('learning_rate', 'weight_decay', 'batch_questions', 'gradient_norm_cap',
                     'max_epochs', 'patience', 'profile'):
            if getattr(config, name) != getattr(fixed, name):
                raise ValueError('Unregistered natural training hyperparameter: ' + name)


def train_one_staged(model, train_records, dev_records, transform, *, seed, run_id,
                     outdir, ledger, run_cpu_limit_seconds, phase_started_unix,
                     phase_cpu_baseline, cache_namespace=None, cache=None, bindings,
                     phase_id='staged', phase_cpu_limit_seconds=PHASE_SECONDS,
                     phase_wall_limit_seconds=PHASE_SECONDS, source=None,
                     shuffle_training=False, config=TrainingConfig(),
                     authorization=FitAuthorization(), resume=False,
                     reconciled_cpu_seconds=None, derived_root=None):
    """Fit one registered model, or explicitly recover its committed epoch.

    ``bindings`` is the runner's JSON contract/code/data receipt. In addition,
    this engine binds exact ordered in-memory TRAIN/DEV tensors, source scope,
    frozen transform, model architecture, implementation hashes, and runtime.
    ``phase_cpu_baseline`` is cumulative global CPU at the start of the named
    phase, not process CPU. Use one global ``FitLedger`` and derived output root
    for every phase. A later phase may change phase_id, never the run's limits.

    A hard crash has unknown work after its last durable event. Recovery then
    requires an explicit *cumulative per-run* ``reconciled_cpu_seconds`` at least
    as large as every checkpoint/ledger/resource observation. No natural fit
    starts without the usual train_model authorization and factory gates.
    """
    session_cpu_started = time.process_time()
    session_monotonic_started = time.monotonic()
    session_started_unix = time.time()
    if not isinstance(run_id, str) or re.fullmatch(r'[A-Za-z0-9_.-]+', run_id) is None:
        raise ValueError('Unsafe run identifier')
    train_records, dev_records = tuple(train_records), tuple(dev_records)
    authorization.require(train_records + dev_records, 'train_model')
    assert_fit_scope(train_records, 'train', source)
    assert_fit_scope(dev_records, 'dev', source)
    validate_cohort(train_records + dev_records)
    natural = any(r.kind == 'natural' for r in train_records + dev_records)
    _validate_config(config, natural)
    if not isinstance(ledger, FitLedger):
        raise TypeError('The original global FitLedger is required')
    if seed not in FIXED_SEEDS:
        raise ValueError('Seed replacement/search forbidden')
    if transform.source_scope != source or set(transform.training_sources) != {r.source for r in train_records}:
        raise ValueError('Wrong TRAIN transform source scope')
    transform_hash = transform_signature(transform)
    if natural and (getattr(model, 'initialization_seed', None) != seed or
                    getattr(model, 'transform_signature', None) != transform_hash):
        raise ValueError('Fixed-seed model factory and exact TRAIN transform required')
    authorization.require(train_records + dev_records, 'prune_obsolete_recovery_snapshots')
    if any(value.device.type != 'cpu' for value in model.state_dict().values()):
        raise ValueError('The registered model runtime is CPU only')
    if type(bindings) is not dict or not bindings:
        raise ValueError('Explicit nonempty contract/code/data bindings required')
    bindings = _json_copy(bindings)
    for label, value, ceiling in (
            ('run CPU', run_cpu_limit_seconds, DAY_SECONDS),
            ('phase CPU', phase_cpu_limit_seconds, PHASE_SECONDS),
            ('phase wall', phase_wall_limit_seconds, PHASE_SECONDS)):
        if isinstance(value, bool) or not math.isfinite(value) or not 0 < value <= ceiling:
            raise ValueError('Invalid ' + label + ' ceiling')
    if not isinstance(phase_id, str) or not phase_id:
        raise ValueError('A stable named phase is required')
    if (not math.isfinite(phase_started_unix) or phase_started_unix > session_started_unix
            or not math.isfinite(phase_cpu_baseline) or phase_cpu_baseline < 0):
        raise ValueError('Invalid original phase clocks')
    if cache is not None:
        if type(cache) is not StaticPrefixCache:
            raise TypeError('Registered static prefix cache required')
        if cache_namespace is not None and cache.namespace != cache_namespace:
            raise ValueError('Conflicting cache namespace')
        cache_namespace = cache.namespace
    if type(cache_namespace) is not CacheNamespace or cache_namespace.transform_sha256 != transform_hash:
        raise ValueError('Cache namespace must bind the exact TRAIN transform and measurement profile')
    if cache is None:
        cache = StaticPrefixCache(len(transform.ids), cache_namespace)
    if cache.dimensions != len(transform.ids):
        raise ValueError('Cache coordinate mismatch')
    from .scoring_reuse import score_model_reuse

    train_plan, dev_plan = BalancedPlan(train_records, transform), BalancedPlan(dev_records, transform)
    if not train_plan.questions or not dev_plan.questions:
        raise ValueError('No joint TRAIN/DEV support')
    outdir = Path(outdir).resolve()
    derived_root = outdir if derived_root is None else Path(derived_root).resolve()
    if not outdir.is_relative_to(derived_root):
        raise ValueError('All fit artifacts must be inside the derived resource root')
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / (run_id + '.pt')
    snapshots = outdir / '.recovery' / run_id
    phase = {'started_unix': float(phase_started_unix), 'cpu_baseline': float(phase_cpu_baseline),
             'cpu_limit_seconds': float(phase_cpu_limit_seconds), 'wall_limit_seconds': float(phase_wall_limit_seconds)}
    identity = _json_copy({
        'run_id': run_id, 'seed': seed, 'config': asdict(config), 'source_scope': source,
        'shuffle_training': bool(shuffle_training), 'run_cpu_limit_seconds': run_cpu_limit_seconds,
        'transform_sha256': transform_hash, 'transform': transform.to_dict(),
        'cache_namespace': asdict(cache_namespace), 'bindings': bindings,
        'train_sha256': _data_digest(train_records), 'dev_sha256': _data_digest(dev_records),
        'model': _model_identity(model), 'implementation_sha256': _code_identity(),
        'runtime': {'torch': str(torch.__version__), 'python': sys.version},
        'train_execution': 'reference_packet_forward_loss', 'dev_execution': 'full_fixed_plan_reuse',
        'derived_root': str(derived_root), 'outdir': str(outdir),
    })

    with _ledger_lock(ledger):
        events = ledger.events()
        attempts = [e for e in events if e['event'] == 'attempt_started']
        previous = [e for e in attempts if e['run_id'] == run_id]
        existing_phase = [e['phase'] for e in events if e.get('phase_id') == phase_id and 'phase' in e]
        if existing_phase and any(entry != phase for entry in existing_phase):
            raise RecoveryError('A phase cannot reset its original clocks or ceilings')
        if phase_cpu_baseline > _total_cpu(events):
            raise RecoveryError('Phase CPU baseline cannot omit unrecorded study spending')
        saved = None
        cpu_baseline = 0.
        if resume:
            if len(previous) != 1:
                raise RecoveryError('Exactly one original attempt is required for resume')
            if previous[0].get('staged_identity') != identity:
                raise RecoveryError('Run/seed/config/transform/bindings changed on resume')
            own = [e for e in events if e['run_id'] == run_id]
            if any(e['event'] in ('failed', 'completed') for e in own):
                raise RecoveryError('Failed/completed fits cannot be silently retried')
            saved = _load_snapshot(events, identity, snapshots)
            cpu_baseline = max(_cpu_for_run(events, run_id), float(saved['accounting']['cpu_seconds']))
            activity = [e for e in own if e['event'] not in ('snapshot_pruned', 'backup_needed')]
            clean_interruption = activity and activity[-1]['event'] == 'interrupted'
            if reconciled_cpu_seconds is None and not clean_interruption:
                raise RecoveryError('Crash CPU is unknown; explicit reconciled_cpu_seconds required')
            if reconciled_cpu_seconds is not None:
                if (not math.isfinite(reconciled_cpu_seconds) or reconciled_cpu_seconds < cpu_baseline):
                    raise RecoveryError('Reconciled CPU cannot roll back any recorded spending')
                cpu_baseline = float(reconciled_cpu_seconds)
            run_started_unix = previous[0]['started_unix']
        else:
            if previous:
                raise RecoveryError('Run already attempted; explicit resume is required')
            if reconciled_cpu_seconds is not None:
                raise ValueError('CPU reconciliation applies only to recovery')
            if len(attempts) >= min(ledger.max_fits, 100):
                raise ResourceStop('Original optimizer-fit budget exhausted')
            if path.exists() or snapshots.exists():
                raise RecoveryError('Unbound existing fit artifacts cannot be overwritten')
            ledger.begin(run_id, {
                'started_unix': session_started_unix, 'seed': seed, 'source_scope': source,
                'shuffle_training': shuffle_training, 'config': asdict(config),
                'kind': 'natural' if natural else 'synthetic',
                'train_questions': len(train_plan.questions), 'dev_questions': len(dev_plan.questions),
                'staged_identity': identity, 'phase_id': phase_id, 'phase': phase,
            })
            run_started_unix = session_started_unix
            events = ledger.events()
        guard = StagedResourceGuard(
            config=config, ledger=ledger, run_id=run_id, derived_root=derived_root, events=events,
            session_cpu_started=session_cpu_started, session_monotonic_started=session_monotonic_started,
            cpu_baseline=cpu_baseline, run_started_unix=run_started_unix,
            run_cpu_limit_seconds=run_cpu_limit_seconds, phase=phase, phase_id=phase_id)
        try:
            if resume:
                ledger.append({'event': 'resume_started', 'run_id': run_id, 'phase_id': phase_id,
                               'phase': phase, 'resume_from_epoch': saved['epoch'],
                               'reconciled_cpu_seconds': reconciled_cpu_seconds, **guard.accounting()})
            guard.check()
            torch.set_num_threads(config.max_cpu_threads)
            if torch.get_num_interop_threads() > config.max_cpu_threads:
                torch.set_num_interop_threads(config.max_cpu_threads)
            if hasattr(os, 'sched_setaffinity'):
                os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:config.max_cpu_threads])
            deterministic_seed(seed)
            optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate,
                                         weight_decay=config.weight_decay)
            if saved is None:
                state = {'epoch': 0, 'best_state_dict': None, 'best_optimizer_state_dict': None,
                         'best_dev_score': None, 'best_epoch': None, 'stale_epochs': 0}
                _commit_snapshot(model=model, optimizer=optimizer, state=state, identity=identity,
                                 guard=guard, ledger=ledger, snapshots=snapshots)
            else:
                model.load_state_dict(saved['state_dict'], strict=True)
                optimizer.load_state_dict(saved['optimizer_state_dict'])
                random.setstate(saved['python_rng_state'])
                torch.set_rng_state(saved['torch_rng_state'])
                state = {name: saved[name] for name in ('epoch', 'best_state_dict',
                         'best_optimizer_state_dict', 'best_dev_score', 'best_epoch', 'stale_epochs')}
            for epoch in range(state['epoch'] + 1, config.max_epochs + 1):
                if state['stale_epochs'] >= config.patience:
                    break
                model.train()
                draws = list(train_plan.draws(seed * 100000 + epoch))
                batch_losses = []
                for offset in range(0, len(draws), config.batch_questions):
                    guard.check()
                    optimizer.zero_grad(set_to_none=True)
                    losses = []
                    for draw_index, (i, cutoff) in enumerate(draws[offset:offset + config.batch_questions], start=offset):
                        record = train_records[i]
                        packet = make_model_packet(record, cutoff, transform)
                        if shuffle_training:
                            packet = _shuffle(packet, seed * 10**9 + epoch * 10**6 + draw_index)
                        target, observed = transform.target(record.values[cutoff])
                        loss, _ = family_loss(model(packet), target, observed, transform.families)
                        if loss is None:
                            raise AssertionError('Training support changed')
                        losses.append(loss)
                    batch = torch.stack(losses).mean()
                    if not torch.isfinite(batch):
                        raise FloatingPointError('Nonfinite objective')
                    batch.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), config.gradient_norm_cap,
                                                   error_if_nonfinite=True)
                    optimizer.step()
                    batch_losses.append(float(batch.detach()))
                    guard.check()
                dev_rows = score_model_reuse(model, dev_plan, cache=cache,
                    permutations=10 if shuffle_training else 0, progress_guard=guard.check)
                dev = aggregate_document_scores(dev_rows)['equal_arm_mean']
                if dev is None or not math.isfinite(dev):
                    raise FloatingPointError('Invalid DEV score')
                improved = state['best_dev_score'] is None or dev < state['best_dev_score']
                if improved:
                    state.update(best_dev_score=dev, best_epoch=epoch, stale_epochs=0,
                                 best_state_dict=copy.deepcopy(model.state_dict()),
                                 best_optimizer_state_dict=copy.deepcopy(optimizer.state_dict()))
                else:
                    state['stale_epochs'] += 1
                state['epoch'] = epoch
                _commit_snapshot(model=model, optimizer=optimizer, state=state, identity=identity,
                                 guard=guard, ledger=ledger, snapshots=snapshots)
                ledger.append({'event': 'epoch', 'run_id': run_id, 'epoch': epoch,
                               'sampler_seed': seed * 100000 + epoch, 'draws': len(draws),
                               'batch_mean_diagnostic': sum(batch_losses) / len(batch_losses),
                               'dev_score': dev, 'dev_prefixes': sum(len(dev_plan.positions[i]) for i in dev_plan.record_indices),
                               'checkpoint_selected': improved, 'stale_epochs': state['stale_epochs'],
                               **guard.accounting()})
                guard.check()
            if state['best_state_dict'] is None:
                raise RecoveryError('No completed DEV selection is available')
            guard.check()
            final = {'state_dict': state['best_state_dict'], 'seed': seed, 'epoch': state['best_epoch'],
                     'dev_score': state['best_dev_score'], 'run_id': run_id, 'transform': transform.to_dict()}
            if path.exists():
                # A crash between publishing final bytes and the completed
                # event can resume only if those bytes represent this selection.
                prior = torch.load(path, map_location='cpu', weights_only=True)
                if ({key: value for key, value in prior.items() if key != 'state_dict'} !=
                    {key: value for key, value in final.items() if key != 'state_dict'} or
                    set(prior['state_dict']) != set(final['state_dict']) or
                    any(not torch.equal(prior['state_dict'][key], value) for key, value in final['state_dict'].items())):
                    raise RecoveryError('Existing final checkpoint differs from the committed DEV selection')
                digest = _hash_file(path)
            else:
                digest = _save_immutable(final, path, guard)
            guard.check()
            model.load_state_dict(state['best_state_dict'], strict=True)
            result = {'event': 'completed', 'run_id': run_id, 'selected_epoch': state['best_epoch'],
                      'best_dev_score': state['best_dev_score'], 'checkpoint_sha256': digest,
                      'checkpoint_path': str(path), 'engine': SNAPSHOT_VERSION,
                      'train_execution': 'reference_packet_forward_loss',
                      'dev_execution': 'full_fixed_plan_reuse', **guard.accounting()}
            ledger.append(result)
            return result
        except BaseException as error:
            resumable = isinstance(error, (ResourceStop, KeyboardInterrupt))
            ledger.append({'event': 'interrupted' if resumable else 'failed', 'run_id': run_id,
                           'resumable': resumable, 'error_type': type(error).__name__, 'error': str(error),
                           'cpu_accounting_complete': True, **guard.accounting()})
            raise
