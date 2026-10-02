#!/usr/bin/env python3
"""Reviewed-source-only extension for one already registered pure-mask replication.

Import and --plan are model-free. Real execution is separately authorized and
must be run through bounded_pure_followup_phase.py, on the unchanged original ledger.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import time

ROOT = Path(__file__).resolve().parent
DAY = 86400
BASE_SOURCE_MANIFEST_SHA256 = '6a2f74b87bf202c9791f8e7fd570cabb69590c84870c35c79e403623a1d43501'
CONTROL_SOURCE_MANIFEST_SHA256 = '45a8ce48db4d755a654a12d670e9f9e92c6b634e7cefc20fbc0fd68f73dd3fa9'
BASE_CONTRACT_SHA256 = '2729b1608397be1d45e3620c86ec7b3ae1f21fdc9e28c70bc942c41b0a122444'
NUISANCE_SOURCE_MANIFEST_SHA256 = 'a34cfda1658196413d557b208d0d2c3b03fa4c5d51a50511c07692fd663ec15e'
LENGTH_REPLICATION_SOURCE_MANIFEST_SHA256 = 'a25402e45a988161827b9bb3c9bc9b832839c0e1a8af3e13af29547ec91928a4'
MASK_FOLLOWUP_SOURCE_MANIFEST_SHA256 = '5972386cb86111aa8b878653b78f58847c342cf4ac43b52d2a6bb950efb9d8c3'
PHASE_ID = 'pooled_pure_mask_F4_seed1702'
CONTROL_ORDER = ('pooled.pure_mask.F4.1702',)
CONTROL_MODES = ('pure_mask',)
CONTROL_SEEDS = (1702,)
RUN_CAPS = (10800,)
NONFIT_RESERVE = 600
PHASE_CAP = sum(RUN_CAPS) + NONFIT_RESERVE
PREREQUISITES = ('pooled.mask_opportunity.F4.1701', 'pooled.pure_mask.F4.1701', 'pooled.length.F4.1701', 'pooled.length.F4.1702', 'pooled.length.F4.1703', 'pooled.mask_opportunity.F4.1702')
BACKUP_IDS = ('resource.private_backup_io', 'resource.private_backup_maintenance')
REQUIRED_FLAGS = ('approved', 'optimizer_fits_approved', 'full_train_dev_features_approved',
                  'publication_verified', 'independent_review_passed',
                  'prune_obsolete_recovery_snapshots_approved',
                  'current_fit_and_backup_accounting_complete', 'tensor_integration_passed',
                  'numerical_slot_idle_confirmed', 'all_prior_selected_latest_two_backups_verified')


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def number(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PermissionError('Invalid numeric accounting field: ' + label)
    if value < 0 or (positive and value == 0):
        raise PermissionError('Invalid nonnegative accounting field: ' + label)
    return float(value)


def execution_bindings(approval, amendment=None):
    """Require explicit local history, bound by the approved source manifest.

    No execution origin or receipt digest is stored in publishable source.
    Missing, malformed or mismatched local bindings always fail closed.
    """
    bindings = approval.get('execution_history')
    fields = {'original_first_attempt_unix', 'preceding_report_sha256',
              'proposal_sha256', 'completed_registered_fits', 'terminal_resource_filename',
              'terminal_resource_sha256', 'post_mask_accounting_sha256'}
    if not isinstance(bindings, dict) or set(bindings) != fields:
        raise PermissionError('Complete explicit local execution-history bindings required')
    number(bindings['original_first_attempt_unix'], 'original execution origin', True)
    for key in ('preceding_report_sha256', 'proposal_sha256', 'terminal_resource_sha256', 'post_mask_accounting_sha256'):
        if not isinstance(bindings[key], str) or re.fullmatch('[0-9a-f]{64}', bindings[key]) is None:
            raise PermissionError('Exact local execution-record digest required')
    name = bindings['terminal_resource_filename']
    if not isinstance(name, str) or re.fullmatch(r'mask_followup\.[0-9]+\.resources\.json', name) is None:
        raise PermissionError('Exact preceding terminal resource filename required')
    count = bindings['completed_registered_fits']
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise PermissionError('Explicit prior completed-run count required')
    if amendment is not None and amendment.get('execution_history') != bindings:
        raise PermissionError('Approval must match the source-bound local execution history')
    return bindings


def control_recipe(run_id):
    if run_id not in CONTROL_ORDER:
        raise PermissionError('Undeclared pure_followup control')
    return {'id': run_id, 'model': 'F4', 'mode': CONTROL_MODES[CONTROL_ORDER.index(run_id)],
            'seed': CONTROL_SEEDS[CONTROL_ORDER.index(run_id)], 'source': None}


def validate_registry(run_id, registry):
    recipe = control_recipe(run_id)
    if registry.get(run_id) != recipe:
        raise PermissionError('Registered pure_followup recipe differs from fixed recipe')
    return recipe


def control_training_arguments(run):
    if run != control_recipe(run['id']):
        raise PermissionError('Training recipe changed')
    return {'seed': run['seed'], 'run_id': run['id'], 'source': None, 'shuffle_training': False}


def validate_approval(approval, amendment, phase):
    execution_bindings(approval, amendment)
    if not all(approval.get(key) is True for key in REQUIRED_FLAGS):
        raise PermissionError('Explicit independent-review, publication and reconciled-budget approval required')
    if re.fullmatch('[0-9a-f]{40}', approval.get('published_source_commit', '')) is None:
        raise PermissionError('Verified published source commit required')
    if re.fullmatch('[0-9a-f]{64}', approval.get('tensor_integration_receipt_sha256', '')) is None:
        raise PermissionError('Source-bound tensor integration receipt required')
    if approval.get('tensor_integration_source_manifest_sha256') != approval.get('source_manifest_sha256') or re.fullmatch('[0-9a-f]{64}', approval.get('source_manifest_sha256', '')) is None:
        raise PermissionError('Tensor integration must bind these exact source bytes')
    if not isinstance(approval.get('receipt'), str) or not approval['receipt'].strip():
        raise PermissionError('Explicit optimizer authorization receipt required')
    if phase.get('phase_id') != PHASE_ID or approval.get('phase_id') != PHASE_ID:
        raise PermissionError('Fixed pure_followup phase required')
    if [r['run_id'] for r in phase['runs']] != list(CONTROL_ORDER):
        raise PermissionError('Fixed pure_followup order changed')
    ids = approval.get('run_ids', [])
    if ids != list(CONTROL_ORDER):
        raise PermissionError('The exact one-run registered pure-mask batch is required')
    for key in ('max_phase_cpu_seconds', 'max_phase_wall_seconds'):
        if phase.get(key) != PHASE_CAP or number(approval.get(key), key) != PHASE_CAP:
            raise PermissionError('Phase ceiling changed or exceeded')
    for key in ('max_global_cpu_seconds', 'max_global_wall_seconds'):
        if approval.get(key) != DAY:
            raise PermissionError('Original global budgets cannot reset or enlarge')
    for kind in ('cpu', 'wall'):
        key = 'nonfit_reserve_' + kind + '_seconds'
        if number(approval.get(key), key) != NONFIT_RESERVE or phase.get('minimum_' + key) != NONFIT_RESERVE:
            raise PermissionError('Exactly 600 seconds of explicit nonfit/backup reserve required')
    expected = {'base_source_manifest_sha256': BASE_SOURCE_MANIFEST_SHA256,
                'control_source_manifest_sha256': CONTROL_SOURCE_MANIFEST_SHA256,
                'nuisance_source_manifest_sha256': NUISANCE_SOURCE_MANIFEST_SHA256,
                'length_replication_source_manifest_sha256': LENGTH_REPLICATION_SOURCE_MANIFEST_SHA256,
                'mask_followup_source_manifest_sha256': MASK_FOLLOWUP_SOURCE_MANIFEST_SHA256,
                'base_contract_sha256': BASE_CONTRACT_SHA256,
                'max_epochs': 100, 'patience': 10, 'full_TRAIN_and_DEV': True,
                'unchanged_objectives_and_typed_masks': True,
                'original_global_CPU_and_elapsed_wall_seconds': DAY,
                'optimizer_execution_authorized_by_this_definition': False,
                'TEST_or_davinci_execution': False, 'source_bound_tensor_integration_required': True}
    if any(amendment.get(k) != v for k, v in expected.items()):
        raise PermissionError('Frozen scientific contract or scope changed')
    if approval.get('amendment_sha256') != digest((ROOT / 'PURE_FOLLOWUP_EXECUTION_AMENDMENT.json').read_bytes()):
        raise PermissionError('Approved amendment bytes required')
    for item, cap in zip(phase['runs'], RUN_CAPS):
        if item['max_cpu_seconds'] != cap or item['max_wall_seconds'] != cap or item['recipe'] != control_recipe(item['run_id']):
            raise PermissionError('Prespecified run recipe or proposed cap changed')
    return ids


def safe_source_path(name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] == 'private':
        raise PermissionError('Unsafe or private path in public source manifest')
    path = ROOT / p
    if path.resolve() != ROOT.resolve() / p:
        raise PermissionError('Source symlink forbidden')
    return path


PUBLIC_SOURCE_ALLOWLIST = (
    'run_pure_followup_phase.py', 'bounded_pure_followup_phase.py',
    'check_pure_followup_compatibility.py', 'tests/test_pure_followup_runner.py',
    'tests/test_pure_followup_tensor_integration.py')


def verify_public_source(approval):
    """Bind all unchanged prior bytes plus the exact local/public additive files.

    Only PUBLIC_SOURCE_ALLOWLIST is eligible for publication. Manifests and
    amendments contain local execution bindings and remain local.
    """
    previous = []
    for filename, expected, key in (
            ('STAGED_SOURCE_MANIFEST.json', BASE_SOURCE_MANIFEST_SHA256, 'base_source_manifest_sha256'),
            ('CONTROL_SOURCE_MANIFEST.json', CONTROL_SOURCE_MANIFEST_SHA256, 'control_source_manifest_sha256'),
            ('NUISANCE_SOURCE_MANIFEST.json', NUISANCE_SOURCE_MANIFEST_SHA256, 'nuisance_source_manifest_sha256'),
            ('LENGTH_REPLICATION_SOURCE_MANIFEST.json', LENGTH_REPLICATION_SOURCE_MANIFEST_SHA256, 'length_replication_source_manifest_sha256'),
            ('MASK_FOLLOWUP_SOURCE_MANIFEST.json', MASK_FOLLOWUP_SOURCE_MANIFEST_SHA256, 'mask_followup_source_manifest_sha256')):
        blob = (ROOT / filename).read_bytes()
        if digest(blob) != expected or approval.get(key) != expected:
            raise PermissionError('Frozen earlier source binding changed')
        previous.append(json.loads(blob))
    base, control, nuisance, length, mask = previous
    if len(base['files']) != 20 or len(nuisance['files']) != 32 or len(length['files']) != 39 or len(mask['files']) != 46:
        raise PermissionError('Original20, nuisance32, length39 and mask46 source identities required')
    for older, newer in zip(previous, previous[1:]):
        if any(newer['files'].get(n) != h for n, h in older['files'].items()):
            raise PermissionError('Existing source omitted or replaced')
    blob = (ROOT / 'PURE_FOLLOWUP_SOURCE_MANIFEST.json').read_bytes()
    if digest(blob) != approval.get('source_manifest_sha256'):
        raise PermissionError('Approved pure-followup source manifest required')
    manifest = json.loads(blob)
    for key, expected in (('base_source_manifest_sha256', BASE_SOURCE_MANIFEST_SHA256),
                          ('control_source_manifest_sha256', CONTROL_SOURCE_MANIFEST_SHA256),
                          ('nuisance_source_manifest_sha256', NUISANCE_SOURCE_MANIFEST_SHA256),
                          ('length_replication_source_manifest_sha256', LENGTH_REPLICATION_SOURCE_MANIFEST_SHA256),
                          ('mask_followup_source_manifest_sha256', MASK_FOLLOWUP_SOURCE_MANIFEST_SHA256)):
        if manifest.get(key) != expected:
            raise PermissionError('Wrong previous source identity')
    if any(manifest['files'].get(n) != h for n, h in mask['files'].items()):
        raise PermissionError('Existing source omitted or replaced')
    expected_files = set(mask['files']) | set(PUBLIC_SOURCE_ALLOWLIST) | {
        'MASK_FOLLOWUP_SOURCE_MANIFEST.json', 'PURE_FOLLOWUP_EXECUTION_AMENDMENT.json'}
    if set(manifest['files']) != expected_files or manifest.get('public_source_allowlist') != list(PUBLIC_SOURCE_ALLOWLIST):
        raise PermissionError('Exact additive source and privacy allowlist required')
    for name, expected in manifest['files'].items():
        if digest(safe_source_path(name).read_bytes()) != expected:
            raise PermissionError('Source bytes changed: ' + name)
    return digest(blob), manifest


TENSOR_CHECKS = ('registered_factory', 'typed_masks', 'full_target_support',
                 'forward_loss_gradient', 'unchanged_optimizer_contract',
                 'direct_vs_cached_dev', 'prohibited_path_invariance')


def verify_tensor_integration(approval, source_hash):
    path = ROOT / 'private/staged/PURE_FOLLOWUP_TENSOR_INTEGRATION.json'
    blob = path.read_bytes()
    if digest(blob) != approval['tensor_integration_receipt_sha256']:
        raise PermissionError('Tensor integration receipt bytes changed')
    receipt = json.loads(blob)
    if (receipt.get('status') != 'passed' or receipt.get('source_manifest_sha256') != source_hash
            or receipt.get('run_ids') != list(CONTROL_ORDER)
            or receipt.get('synthetic_only') is not True or receipt.get('empirical_reads') != 0):
        raise PermissionError('Passed synthetic tensor integration for the exact source and recipes required')
    if not all(receipt.get('checks', {}).get(key) is True for key in TENSOR_CHECKS):
        raise PermissionError('Incomplete tensor integration coverage')
    return receipt


def ledger_costs(rows):
    costs = {}
    for row in rows:
        rid = row['run_id']
        cost = max(number(row.get('cpu_seconds', 0), 'cpu_seconds'),
                   number(row.get('cpu_seconds_current_fit', 0), 'cpu_seconds_current_fit'))
        costs[rid] = max(costs.get(rid, 0), cost)
    return costs


def ledger_rows(blob):
    if not blob or not blob.endswith(b'\n'):
        raise PermissionError('Complete append-only ledger required')
    rows = [json.loads(line) for line in blob.splitlines() if line]
    ledger_costs(rows)
    return rows


def global_wall(rows, now):
    starts = [number(e['started_unix'], 'original attempt start', True) for e in rows if e['event'] == 'attempt_started']
    if not starts or min(starts) > now:
        raise PermissionError('Original study clock required')
    return max(now - min(starts), max((number(e.get('global_wall_seconds', 0), 'global wall') for e in rows), default=0))


def verify_accounting_receipt(approval, blob, report, resources):
    """Bind a passed post-mask reconciliation to an immutable ledger prefix.

    Later validation, backup and invocation costs may only append. Neither the
    original report nor the original study clock is rewritten to reset spending.
    The resources argument retains the audited interface and now carries the
    explicit post-mask accounting receipt.
    """
    history = execution_bindings(approval)
    a = approval['accounting']
    size = a.get('ledger_prefix_bytes')
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= len(blob):
        raise PermissionError('Approved original ledger prefix required')
    prefix = blob[:size]
    if digest(prefix) != a.get('ledger_prefix_sha256'):
        raise PermissionError('Original global ledger deleted, replaced or rolled back')
    old = ledger_rows(prefix)
    costs = ledger_costs(old)
    starts = [number(e['started_unix'], 'start', True) for e in old if e['event'] == 'attempt_started']
    if (not starts or min(starts) != history['original_first_attempt_unix']
            or min(starts) != a.get('original_first_attempt_unix')):
        raise PermissionError('Original elapsed-wall origin changed')
    if sum(costs.values()) != a.get('accounted_cpu_seconds'):
        raise PermissionError('Approved ledger CPU reconciliation differs')
    completed = {e['run_id'] for e in old if e['event'] == 'completed'}
    started = {e['run_id'] for e in old if e['event'] == 'attempt_started'}
    terminal = {e['run_id'] for e in old if e['event'] in ('completed', 'failed')}
    if started - terminal or not set(PREREQUISITES) <= completed:
        raise PermissionError('All preceding fits must be terminal and preceding controls complete')
    if (report.get('status') != 'one_fixed_mask_followup_completed'
            or report.get('source_manifest_sha256') != MASK_FOLLOWUP_SOURCE_MANIFEST_SHA256
            or report.get('all46_source_config_hashes_verified') is not True):
        raise PermissionError('Preceding mask report or source identity differs')
    budget = report['global_budget']
    if (number(budget.get('recorded_CPU_used_seconds'), 'preceding report CPU') > sum(costs.values())
            or budget.get('original_first_attempt_unix') != history['original_first_attempt_unix']
            or budget.get('CPU_and_elapsed_wall_ceiling_seconds') != DAY):
        raise PermissionError('Preceding report and original ledger accounting differ')
    terminal_resources = report.get('resources', {})
    if not terminal_resources or any(r.get('exit_code') != 0 or r.get('stopped_reason') is not None
                                     or r.get('status') != 'completed' for r in terminal_resources.values()):
        raise PermissionError('Successful preceding outer-watchdog receipts required')
    if report.get('completed_registered_fits') != history['completed_registered_fits']:
        raise PermissionError('Preceding report completed-fit count differs')
    required = {'status': 'passed', 'mask_followup_report_sha256': history['preceding_report_sha256'],
                'mask_followup_source_manifest_sha256': MASK_FOLLOWUP_SOURCE_MANIFEST_SHA256,
                'terminal_resource_filename': history['terminal_resource_filename'],
                'terminal_resource_sha256': history['terminal_resource_sha256'],
                'original_first_attempt_unix': history['original_first_attempt_unix'],
                'global_CPU_and_elapsed_wall_ceiling_seconds': DAY,
                'no_fit_active': True, 'all_prior_selected_latest_two_backups_verified': True,
                'completed_registered_fits': history['completed_registered_fits']}
    if any(resources.get(k) != v for k, v in required.items()):
        raise PermissionError('Passed post-mask accounting and backup receipt required')
    for key in ('ledger_prefix_bytes', 'ledger_prefix_sha256', 'accounted_cpu_seconds', 'backup_cpu_seconds'):
        if resources.get(key) != a.get(key):
            raise PermissionError('Post-mask accounting receipt must bind the approved ledger prefix')
    if (len(completed) != history['completed_registered_fits'] or resources.get('verified_backup_run_ids') != sorted(completed)):
        raise PermissionError('All preceding selected/latest-two backup identities required')
    for rid in BACKUP_IDS:
        if rid not in costs or costs[rid] != a.get('backup_cpu_seconds', {}).get(rid):
            raise PermissionError('Final measured backup CPU not reconciled')
    return old


def assert_remaining_allocation(rows, remaining, approval, state=None, now=None):
    now = time.time() if now is None else number(now, 'current clock', True)
    costs = ledger_costs(rows)
    cpu, wall = sum(costs.values()), global_wall(rows, now)
    if cpu >= DAY or wall >= DAY:
        raise RuntimeError('Original global CPU or elapsed-wall budget exhausted')
    started = {e['run_id'] for e in rows if e['event'] == 'attempt_started'}
    terminal = {e['run_id'] for e in rows if e['event'] in ('completed', 'failed')}
    if (started - terminal) - set(CONTROL_ORDER):
        raise PermissionError('An earlier fit is still active or unreconciled')
    if any(e['event'] == 'failed' and e['run_id'] in CONTROL_ORDER for e in rows):
        raise PermissionError('Failed pure_followup fits cannot silently be retried or omitted')
    required_cpu = 0
    required_wall = 0
    for run in remaining:
        own = [e for e in rows if e['run_id'] == run['run_id']]
        origins = [e['started_unix'] for e in own if e['event'] == 'attempt_started']
        run_wall = max([now - min(origins)] if origins else [0])
        run_wall = max(run_wall, max((number(e.get('wall_seconds', 0), 'run wall') for e in own), default=0))
        if costs.get(run['run_id'], 0) >= run['max_cpu_seconds'] or run_wall >= run['max_wall_seconds']:
            raise RuntimeError('Run ceiling exhausted; retry cannot reset its clocks')
        required_cpu += run['max_cpu_seconds'] - costs.get(run['run_id'], 0)
        required_wall += run['max_wall_seconds'] - run_wall
    reserve_cpu = approval['nonfit_reserve_cpu_seconds']
    reserve_wall = approval['nonfit_reserve_wall_seconds']
    phase_cpu = 0 if state is None else max(0, cpu - state['cpu_baseline'])
    phase_wall = 0 if state is None else max(now - state['started_unix'], max((number(e.get('phase_wall_seconds', 0), 'phase wall') for e in rows if e.get('phase_id') == PHASE_ID), default=0))
    for required, used, ceiling, reserve, label in (
            (required_cpu, cpu, DAY, reserve_cpu, 'global CPU'),
            (required_wall, wall, DAY, reserve_wall, 'original elapsed wall'),
            (required_cpu, phase_cpu, approval['max_phase_cpu_seconds'], 0, 'phase CPU'),
            (required_wall, phase_wall, approval['max_phase_wall_seconds'], 0, 'phase elapsed wall')):
        if required + reserve > ceiling - used:
            raise RuntimeError('Approved batch caps plus nonfit reserve exceed remaining ' + label)
    return {'CPU_used_seconds': cpu, 'CPU_remaining_seconds': DAY-cpu,
            'elapsed_wall_used_seconds': wall, 'elapsed_wall_remaining_seconds': DAY-wall,
            'required_remaining_run_CPU_seconds': required_cpu,
            'required_remaining_run_wall_seconds': required_wall,
            'nonfit_reserve_cpu_seconds': reserve_cpu, 'nonfit_reserve_wall_seconds': reserve_wall}


def preflight(approval, phase, state=None):
    history = execution_bindings(approval)
    private = ROOT / 'private/staged'
    blob = (private / 'fit_ledger.jsonl').read_bytes()
    report_blob = (private / 'MASK_FOLLOWUP_REPORT.json').read_bytes()
    if digest(report_blob) != history['preceding_report_sha256']:
        raise PermissionError('Pinned final mask-followup report changed')
    if digest((private / 'PURE_FOLLOWUP_PROPOSAL.json').read_bytes()) != history['proposal_sha256']:
        raise PermissionError('Pinned registered replication proposal changed')
    resources_blob = (private / 'PURE_FOLLOWUP_ACCOUNTING.json').read_bytes()
    if digest(resources_blob) != history['post_mask_accounting_sha256']:
        raise PermissionError('Source-bound post-mask accounting receipt changed')
    terminal_blob = (private / history['terminal_resource_filename']).read_bytes()
    if digest(terminal_blob) != history['terminal_resource_sha256']:
        raise PermissionError('Pinned terminal mask resource receipt changed')
    report = json.loads(report_blob)
    terminal = json.loads(terminal_blob)
    if report.get('resources', {}).get(history['terminal_resource_filename']) != terminal:
        raise PermissionError('Preceding report and terminal resource receipt differ')
    for data, key in ((report_blob, 'mask_followup_report_sha256'), (resources_blob, 'post_mask_accounting_sha256'),
                      (terminal_blob, 'terminal_resource_sha256')):
        if digest(data) != approval['accounting'].get(key):
            raise PermissionError('Final accounting receipt changed')
    verify_accounting_receipt(approval, blob, json.loads(report_blob), json.loads(resources_blob))
    rows = ledger_rows(blob)
    completed = {e['run_id'] for e in rows if e['event'] == 'completed'}
    remaining = [r for r in phase['runs'] if r['run_id'] in approval['run_ids'] and r['run_id'] not in completed]
    return rows, remaining, assert_remaining_allocation(rows, remaining, approval, state)


def get_phase_state(approval, source_hash, phase, create=False):
    private = ROOT / 'private/staged'
    path = private / (PHASE_ID + '.json')
    if path.exists():
        state = read_json(path)
        expected = {'phase_id': PHASE_ID, 'source_manifest_sha256': source_hash,
                    'accounting_origin_sha256': approval['accounting']['ledger_prefix_sha256'],
                    'max_phase_cpu_seconds': approval['max_phase_cpu_seconds'],
                    'max_phase_wall_seconds': approval['max_phase_wall_seconds']}
        if any(state.get(k) != v for k, v in expected.items()):
            raise PermissionError('Cannot reset or replace an existing pure_followup phase')
        number(state.get('cpu_baseline'), 'original phase CPU baseline')
        if number(state.get('started_unix'), 'original phase start', True) > time.time():
            raise PermissionError('Original phase clock is in the future')
        rows, _, _ = preflight(approval, phase, state)
        expected_phase = {'started_unix':state['started_unix'], 'cpu_baseline':state['cpu_baseline'],
                          'cpu_limit_seconds':approval['max_phase_cpu_seconds'],
                          'wall_limit_seconds':approval['max_phase_wall_seconds']}
        if any(e.get('phase') != expected_phase for e in rows if e.get('phase_id') == PHASE_ID and 'phase' in e):
            raise PermissionError('Original recorded phase clocks or ceilings changed')
        if state['cpu_baseline'] > sum(ledger_costs(rows).values()):
            raise PermissionError('Phase CPU baseline exceeds recorded original spending')
        return state
    rows, _, _ = preflight(approval, phase)
    if any(e.get('phase_id') == PHASE_ID for e in rows):
        raise PermissionError('Missing original pure_followup phase state cannot be recreated')
    if not create:
        return None
    state = {'phase_id': PHASE_ID, 'started_unix': time.time(),
             'cpu_baseline': sum(ledger_costs(rows).values()),
             'source_manifest_sha256': source_hash,
             'accounting_origin_sha256': approval['accounting']['ledger_prefix_sha256'],
             'max_phase_cpu_seconds': approval['max_phase_cpu_seconds'],
             'max_phase_wall_seconds': approval['max_phase_wall_seconds']}
    with path.open('x') as f:
        json.dump(state, f, sort_keys=True, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approval')
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--resume-run')
    parser.add_argument('--reconciled-cpu-seconds', type=float)
    args = parser.parse_args()
    amendment = read_json(ROOT / 'PURE_FOLLOWUP_EXECUTION_AMENDMENT.json')
    phase = amendment['phases'][0]
    if args.plan:
        print(json.dumps(phase, indent=2))
        return
    if not args.approval:
        raise PermissionError('No optimizer authorization supplied')
    approval = read_json(args.approval)
    run_ids = validate_approval(approval, amendment, phase)
    source_hash, _ = verify_public_source(approval)
    verify_tensor_integration(approval, source_hash)
    state = get_phase_state(approval, source_hash, phase)
    if state is None or os.environ.get('PURE_FOLLOWUP_SUPERVISOR_PID') != str(os.getppid()):
        raise PermissionError('The reviewed bounded pure_followup supervisor is required')
    preflight(approval, phase, state)
    import torch
    from dataclasses import replace
    from profile_natural import descriptors,deny,EXPECTED_COHORT,canonical
    from experimental_natural.schema import Catalog,FitAuthorization,validate_cohort
    from experimental_natural.cache_adapter import load_train_dev_cache
    from experimental_natural.transforms import FrozenTransform
    from experimental_natural.plan import registered_run_grid,build_registered_model,transform_signature
    from experimental_natural.train import FitLedger,TrainingConfig
    from experimental_natural.staged_training import train_one_staged
    from experimental_natural.static_prefix_cache import CacheNamespace,StaticPrefixCache
    torch.set_num_threads(2);torch.set_num_interop_threads(2);os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
    socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
    extraction=ROOT.parent/'chinese-extraction-recovery-20261002'
    private=ROOT/'private/staged'
    full=read_json(extraction/'public/full_receipt.json');verification=read_json(extraction/'public/verification_receipt.json')
    if full.get('arm_records')!=4814 or verification.get('records')!=4814 or verification.get('verified') is not True or verification.get('all_cache_hashes_and_annotation_fingerprints_verified') is not True:
        raise PermissionError('Complete verified4814-arm extraction required')
    if verification.get('test_raw_bodies_read')!=0 or verification.get('davinci_bodies_read')!=0:raise PermissionError('Unexpected extraction access')
    protocol_data=read_json(extraction/'public/extraction_protocol.json')
    if protocol_data.get('cohort_manifest_sha256')!=EXPECTED_COHORT:raise PermissionError('Frozen cohort changed')
    protocol=digest(canonical(protocol_data))
    if digest((extraction/'public/verification_receipt.json').read_bytes())!=approval.get('verification_receipt_sha256'):
        raise PermissionError('Verified measurement receipt changed')
    for flag in ('cache_commit_unit_counts_verified','all_structural_span_widths_verified','equal_question_family_weights_verified'):
        if verification.get(flag) is not True:raise PermissionError('Incomplete structural/cohort verification')
    transform_path=ROOT/'private/transform.pooled.json';transform_blob=transform_path.read_bytes()
    if digest(transform_blob)!=approval.get('pooled_transform_file_sha256'):raise PermissionError('Frozen pooled transform changed')
    if digest((ROOT/'training_contract.json').read_bytes())!=amendment['base_contract_sha256']:raise PermissionError('Base scientific contract changed')
    transform=FrozenTransform.from_dict(json.loads(transform_blob));catalog=Catalog.from_contract()
    if len(catalog.ids) != 70 or int(transform.score_eligible.sum()) != 67:
        raise PermissionError('Unchanged70-channel catalog and67 eligible targets required')
    desc=descriptors(extraction,protocol)
    data_digest=digest('\n'.join(d.sha256 for d in desc).encode())
    if data_digest!=approval.get('train_dev_cache_manifest_sha256'):raise PermissionError('Approved TRAIN/DEV cache population changed')
    if len([d for d in desc if d.split=='train'])!=3632 or len([d for d in desc if d.split=='dev'])!=1182:raise ValueError('Unexpected full TRAIN/DEV population')
    ledger=FitLedger(private/'fit_ledger.jsonl',max_fits=100,max_cpu_seconds=24*3600)
    rows, remaining, allocation = preflight(approval, phase, state)
    completed={e['run_id'] for e in rows if e['event']=='completed'}
    if args.resume_run and args.resume_run not in run_ids:
        raise PermissionError('Resume run not authorized in fixed batch')
    auth=FitAuthorization(True,approval['receipt'],('read_train_dev_features','train_model','prune_obsolete_recovery_snapshots'))
    records=[load_train_dev_cache(d,catalog,auth) for d in desc];validate_cohort(records)
    train=[r for r in records if r.split=='train'];dev=[r for r in records if r.split=='dev']
    profile=full['measurement_profile_sha256']
    if len(profile)!=1:raise ValueError('Ambiguous measurement profile')
    namespace=CacheNamespace(transform_signature(transform),profile[0]);cache=StaticPrefixCache(70,namespace,1<<30)
    bindings={'contract_sha256':amendment['base_contract_sha256'],'source_manifest_sha256':source_hash,
              'amendment_sha256':approval['amendment_sha256'],'train_dev_cache_manifest_sha256':data_digest,
              'verification_receipt_sha256':approval['verification_receipt_sha256'],'transform_sha256':transform_signature(transform)}
    # The already-reported analyticF0 remains unchanged; this phase does not recompute or overwrite it.
    grid={r['id']:r for r in registered_run_grid()};outdir=private/'checkpoints'
    for limits in phase['runs']:
        run_id=limits['run_id']
        if run_id not in run_ids or run_id in completed:continue
        if args.resume_run and run_id!=args.resume_run:
            if run_id not in completed:raise PermissionError('Cannot skip an earlier pending run to resume later')
            continue
        preflight(approval, phase, state)
        run=validate_registry(run_id,grid);model=build_registered_model(catalog,run,transform)
        config=replace(TrainingConfig(),max_fit_seconds=limits['max_wall_seconds'])
        prior=max((max(e.get('cpu_seconds',0),e.get('cpu_seconds_current_fit',0)) for e in ledger.events() if e['run_id']==run_id),default=0)
        if args.resume_run == run_id and args.reconciled_cpu_seconds is not None:
            prior=max(prior, number(args.reconciled_cpu_seconds, 'reconciled CPU'))
        active={'run_id':run_id,'phase_id':phase['phase_id'],'started_unix':time.time(),'process_pid':os.getpid(),
                'process_cpu_seconds_at_start':time.process_time(),'prior_run_cpu_seconds':prior}
        temporary=private/'ACTIVE_PURE_FOLLOWUP_RUN.tmp';temporary.write_text(json.dumps(active)+'\n');os.replace(temporary,private/'ACTIVE_PURE_FOLLOWUP_RUN.json')
        result=train_one_staged(model,train,dev,transform,**control_training_arguments(run),outdir=outdir,ledger=ledger,
            run_cpu_limit_seconds=limits['max_cpu_seconds'],phase_started_unix=state['started_unix'],phase_cpu_baseline=state['cpu_baseline'],
            cache=cache,cache_namespace=namespace,bindings=bindings,phase_id=phase['phase_id'],
            phase_cpu_limit_seconds=approval['max_phase_cpu_seconds'],phase_wall_limit_seconds=approval['max_phase_wall_seconds'],
            config=config,authorization=auth,resume=(args.resume_run==run_id),reconciled_cpu_seconds=args.reconciled_cpu_seconds,
            derived_root=private)
        print(json.dumps({'stage':'fit_completed','run_id':run_id,'selected_epoch':result['selected_epoch'],
            'global_cpu_seconds_used':ledger.consumed_cpu(),'global_cpu_seconds_remaining':24*3600-ledger.consumed_cpu()}),flush=True)
        args.resume_run=None;args.reconciled_cpu_seconds=None
    print(json.dumps({'phase_id':phase['phase_id'],'status':'authorized_batch_complete','global_cpu_seconds_used':ledger.consumed_cpu(),
        'scope':'one_registered_pure_mask_seed1702',
        'remaining_registered_controls':'pending','full_study_complete':False,'style_claim':False}),flush=True)

if __name__ == '__main__':
    main()
