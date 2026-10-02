#!/usr/bin/env python3
"""Separate fixed-command supervisor retaining all original study/phase clocks.

No models are imported here. This is a candidate, not an authorization. It only
launches the exact reviewed pure_followup runner after final preceding-phase receipts,
publication, independent review, and a budget allocation check all pass.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

import run_pure_followup_phase as runner


def append(path, value):
    with path.open('a') as f:
        f.write(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def live_accounting(before, rows, tree_cpu, state, now):
    """Avoid double-charging fit heartbeats, include appended external costs.

    Only this invocation's increases for fixed pure_followup run IDs may offset its
    process-tree measurement. Backup/reconciliation/other spending never can.
    """
    old, current = runner.ledger_costs(before), runner.ledger_costs(rows)
    if any(current.get(rid, 0) < cost for rid, cost in old.items()):
        raise PermissionError('Global ledger costs rolled back')
    # A resume may disclose historical crash CPU above the previously recorded
    # high-water mark. That increase is prior work, never fresh-process work.
    floors = dict(old)
    for e in rows:
        rid = e['run_id']
        if rid not in runner.CONTROL_ORDER:
            continue
        prior = e.get('historical_cpu_floor', 0)
        if e.get('event') == 'resume_started' and e.get('reconciled_cpu_seconds') is not None:
            prior = max(prior, runner.number(e['reconciled_cpu_seconds'], 'historical reconciled CPU'))
        floors[rid] = max(floors.get(rid, 0), runner.number(prior, 'historical CPU floor'))
    if any(floors.get(rid, 0) > current.get(rid, 0) for rid in runner.CONTROL_ORDER):
        raise PermissionError('Historical crash reconciliation must be durably charged')
    fit_delta = sum(max(0, current.get(rid, 0)-floors.get(rid, 0)) for rid in runner.CONTROL_ORDER)
    uncharged = max(0, runner.number(tree_cpu, 'process tree CPU')-fit_delta)
    total = sum(current.values()) + uncharged
    wall = runner.global_wall(rows, now)
    phase_wall = max(now-state['started_unix'], max((e.get('phase_wall_seconds', 0) for e in rows if e.get('phase_id') == runner.PHASE_ID), default=0))
    return {'global_cpu_seconds': total, 'global_wall_seconds': wall,
            'phase_cpu_seconds': total-state['cpu_baseline'], 'phase_wall_seconds': phase_wall,
            'uncharged_invocation_cpu_seconds': uncharged}


def compact_accounting_rows(rows):
    """Retain accounting high-water marks without repeatedly scanning identities."""
    costs = runner.ledger_costs(rows)
    starts = [e['started_unix'] for e in rows if e['event'] == 'attempt_started']
    if not starts:
        raise PermissionError('Original attempt history required')
    floors = {}
    for e in rows:
        floor = e.get('historical_cpu_floor', 0)
        if e.get('event') == 'resume_started' and e.get('reconciled_cpu_seconds') is not None:
            floor = max(floor, runner.number(e['reconciled_cpu_seconds'], 'historical reconciled CPU'))
        floors[e['run_id']] = max(floors.get(e['run_id'], 0), floor)
    out = [{'event':'cpu_highwater', 'run_id':rid, 'cpu_seconds':cost,
            'historical_cpu_floor':floors.get(rid, 0)} for rid, cost in costs.items()]
    out.append({'event':'attempt_started', 'run_id':next(iter(costs)), 'started_unix':min(starts),
                'global_wall_seconds':max((e.get('global_wall_seconds', 0) for e in rows), default=0),
                'phase_id':runner.PHASE_ID,
                'phase_wall_seconds':max((e.get('phase_wall_seconds', 0) for e in rows if e.get('phase_id') == runner.PHASE_ID), default=0)})
    return out


class LedgerObserver:
    """Reparse only changed ledger bytes; tolerate an in-progress append."""
    def __init__(self, path):
        self.path = path
        self.signature = None
        self.rows = None
        self.previous_size = 0
        self.inode = None
        self.verified_prefix = b''

    def read(self):
        stat = self.path.stat()
        inode = (stat.st_dev, stat.st_ino)
        if self.inode is not None and (inode != self.inode or stat.st_size < self.previous_size):
            raise PermissionError('Ledger replaced or truncated during supervision')
        signature = (inode, stat.st_size, stat.st_mtime_ns)
        if signature != self.signature:
            blob = self.path.read_bytes()
            if not blob.startswith(self.verified_prefix):
                raise PermissionError('Append-only ledger history changed during supervision')
            if blob.endswith(b'\n'):
                self.rows = compact_accounting_rows(runner.ledger_rows(blob))
                self.signature = signature
                self.previous_size = len(blob)
                self.inode = inode
                self.verified_prefix = blob
            elif self.rows is None:
                raise PermissionError('Incomplete initial ledger')
        return self.rows


def stop_reason(accounting, rss, approval):
    limits = (('original_global_CPU_limit', accounting['global_cpu_seconds'], runner.DAY),
              ('original_global_wall_limit', accounting['global_wall_seconds'], runner.DAY),
              ('original_phase_CPU_limit', accounting['phase_cpu_seconds'], approval['max_phase_cpu_seconds']),
              ('original_phase_wall_limit', accounting['phase_wall_seconds'], approval['max_phase_wall_seconds']),
              ('2GiB_process_tree_RSS', rss, 2*1024**3))
    return next((reason for reason, used, cap in limits if used >= cap), None)



def own_rss_bytes():
    """Supervisor memory is part of the same bounded process tree."""
    return int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')


def main():
    # Dedicated command-line execution charges the entire process lifetime,
    # including interpreter startup, imports, source checks and admission work.
    own_cpu_origin = 0.
    parser = argparse.ArgumentParser()
    parser.add_argument('--approval', required=True)
    parser.add_argument('--resume-run')
    parser.add_argument('--reconciled-cpu-seconds', type=float)
    args = parser.parse_args()
    cores = sorted(os.sched_getaffinity(0))[:2]
    os.sched_setaffinity(0, cores)
    approval_path = Path(args.approval).resolve()
    approval = runner.read_json(approval_path)
    amendment = runner.read_json(runner.ROOT/'PURE_FOLLOWUP_EXECUTION_AMENDMENT.json')
    phase = amendment['phases'][0]
    ids = runner.validate_approval(approval, amendment, phase)
    source_hash, _ = runner.verify_public_source(approval)
    runner.verify_tensor_integration(approval, source_hash)
    private = runner.ROOT/'private/staged'
    ledger = private/'fit_ledger.jsonl'
    lock = (private/'pure_followup_supervisor.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise PermissionError('Another pure_followup supervisor is active') from error
    # Admission is complete before making durable startup records. Denied
    # admission does not create a fit or modify an unverified global ledger.
    existing_state = runner.get_phase_state(approval, source_hash, phase)
    before, remaining, _ = runner.preflight(approval, phase, existing_state)
    if not remaining:
        print(json.dumps({'status':'approved_batch_already_completed', 'full_study_complete':False}))
        return
    if args.reconciled_cpu_seconds is not None and args.resume_run is None:
        raise PermissionError('Crash reconciliation applies only to an explicit resume')
    pending = {e['run_id'] for e in before if e['event'] == 'attempt_started'} - {e['run_id'] for e in before if e['event'] in ('completed', 'failed')}
    if pending and pending != {args.resume_run}:
        raise PermissionError('Exact pending pure_followup identity must be explicitly resumed')
    if args.resume_run is not None and (args.resume_run not in pending or args.resume_run != remaining[0]['run_id']):
        raise PermissionError('Resume must target the first existing unfinished approved run')
    if args.resume_run is not None and args.resume_run not in ids:
        raise PermissionError('Undeclared resume identity')
    if args.reconciled_cpu_seconds is not None:
        floor = runner.number(args.reconciled_cpu_seconds, 'reconciled CPU')
        if floor < runner.ledger_costs(before).get(args.resume_run, 0):
            raise PermissionError('Reconciled historical CPU cannot roll back spending')
    identity = str(time.time_ns())
    resource_id = 'resource.pure_followup_watchdog.'+identity
    journal = private/('pure_followup_watchdog.'+identity+'.jsonl')
    child_usage_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    state, child, peak_rss, peak_cpu, reason = existing_state, None, own_rss_bytes(), 0., None
    exception_type, exit_code, admitted_started = None, 1, False
    try:
        state = runner.get_phase_state(approval, source_hash, phase, create=True)
        append(ledger, {'event':'supervisor_attempt_started', 'run_id':resource_id,
                        'phase_id':runner.PHASE_ID, 'cpu_seconds':0,
                        'started_unix':time.time(), 'source_manifest_sha256':source_hash,
                        'original_phase_started_unix':state['started_unix']})
        admitted_started = True
        if args.reconciled_cpu_seconds is not None:
            # Charge historical crash work BEFORE choosing the fresh-process
            # offset baseline and before the final prelaunch allocation check.
            append(ledger, {'event':'prelaunch_cpu_reconciliation', 'run_id':args.resume_run,
                            'phase_id':runner.PHASE_ID, 'cpu_seconds':floor,
                            'historical_cpu_floor':floor})
        runner.preflight(approval, phase, state)
        before = runner.ledger_rows(ledger.read_bytes())
        compact_before = compact_accounting_rows(before)
        observer = LedgerObserver(ledger)
        observer.read()
        # This frozen sampler is bound by the verified original source.
        from bounded_profile import process_tree
        command = [sys.executable, str(runner.ROOT/'run_pure_followup_phase.py'), '--approval', str(approval_path)]
        if args.resume_run:
            command += ['--resume-run', args.resume_run]
        if args.reconciled_cpu_seconds is not None:
            command += ['--reconciled-cpu-seconds', str(args.reconciled_cpu_seconds)]
        environment = {**os.environ, 'OMP_NUM_THREADS':'2', 'MKL_NUM_THREADS':'2',
                       'OPENBLAS_NUM_THREADS':'2', 'NUMEXPR_NUM_THREADS':'2',
                       'PURE_FOLLOWUP_SUPERVISOR_PID':str(os.getpid())}
        # The try/finally begins before Popen: a spawn failure is a charged,
        # terminal startup failure with preserved original phase state.
        child = subprocess.Popen(command, env=environment, start_new_session=True,
                                 preexec_fn=lambda: os.sched_setaffinity(0, cores))
        seen, last, start = {}, 0., time.monotonic()
        while child.poll() is None:
            child_rss, cpu = process_tree(child.pid, seen)
            rss = child_rss + own_rss_bytes()
            peak_rss, peak_cpu = max(peak_rss, rss), max(peak_cpu, cpu)
            rows = observer.read()
            accounting = live_accounting(compact_before, rows, peak_cpu + time.process_time()-own_cpu_origin, state, time.time())
            reason = stop_reason(accounting, rss, approval)
            elapsed = time.monotonic()-start
            if elapsed-last >= 10:
                append(journal, {'event':'resource_heartbeat', 'pid':child.pid, 'rss_bytes':rss,
                                 'process_tree_cpu_seconds':peak_cpu, **accounting})
                last = elapsed
            if reason:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(.05)
    except BaseException as error:
        exception_type = type(error).__name__
        reason = 'startup_failure' if child is None else 'supervisor_exception'
        if child is not None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        raise
    finally:
        if child is not None:
            child.wait()
        child_usage_end = resource.getrusage(resource.RUSAGE_CHILDREN)
        waited_cpu = (child_usage_end.ru_utime-child_usage_start.ru_utime +
                      child_usage_end.ru_stime-child_usage_start.ru_stime)
        peak_cpu = max(peak_cpu, waited_cpu)
        peak_rss = max(peak_rss, own_rss_bytes())
        # A phase-state creation failure is still recorded after verified
        # admission; it does not invent a new recoverable phase clock.
        if state is None:
            path = private/(runner.PHASE_ID+'.json')
            state = runner.read_json(path) if path.exists() else {
                'started_unix':time.time(), 'cpu_baseline':sum(runner.ledger_costs(before).values())}
        active_path = private/'ACTIVE_PURE_FOLLOWUP_RUN.json'
        if child is not None and active_path.exists():
            active = runner.read_json(active_path)
            if active.get('process_pid') == child.pid and active.get('run_id') in ids:
                actual = active['prior_run_cpu_seconds'] + max(0, peak_cpu-active['process_cpu_seconds_at_start'])
                append(ledger, {'event':'watchdog_cpu_reconciliation', 'run_id':active['run_id'],
                                'cpu_seconds':actual, 'phase_id':runner.PHASE_ID,
                                'watchdog_pid':child.pid, 'interruption_reason':reason})
        rows = runner.ledger_rows(ledger.read_bytes())
        accounting = live_accounting(before, rows, peak_cpu+time.process_time()-own_cpu_origin, state, time.time())
        append(ledger, {'event':'nonfit_resource_cpu', 'run_id':resource_id,
                        'cpu_seconds':accounting['uncharged_invocation_cpu_seconds'],
                        'phase_id':runner.PHASE_ID, 'global_wall_seconds':accounting['global_wall_seconds'],
                        'phase_wall_seconds':accounting['phase_wall_seconds'],
                        'purpose':'Measured full supervisor lifetime and uncharged child overhead through terminal reconciliation'})
        # Recheck every budget after waited-child CPU and reconciliation. A
        # zero child return code never overrides a final CPU/wall/RSS overrun.
        terminal_rows = runner.ledger_rows(ledger.read_bytes())
        terminal = {'global_cpu_seconds':sum(runner.ledger_costs(terminal_rows).values()),
                    'global_wall_seconds':runner.global_wall(terminal_rows, time.time()),
                    'phase_cpu_seconds':sum(runner.ledger_costs(terminal_rows).values())-state['cpu_baseline'],
                    'phase_wall_seconds':max(accounting['phase_wall_seconds'],time.time()-state['started_unix'])}
        final_stop = stop_reason(terminal, peak_rss, approval)
        if final_stop is not None:
            reason = final_stop
        child_exit = None if child is None else child.returncode
        exit_code = (0 if reason is None and child_exit == 0 else
                     (child_exit if child_exit not in (None,0) else (124 if final_stop else 1)))
        status = ('completed' if exit_code == 0 else
                  ('resource_interrupted' if final_stop else ('startup_failed' if child is None else 'failed')))
        append(ledger, {'event':'supervisor_attempt_terminal', 'run_id':resource_id,
                        'phase_id':runner.PHASE_ID, 'cpu_seconds':accounting['uncharged_invocation_cpu_seconds'],
                        'exit_code':exit_code, 'child_exit_code':child_exit, 'status':status,
                        'global_wall_seconds':terminal['global_wall_seconds'],
                        'phase_wall_seconds':terminal['phase_wall_seconds'], 'stopped_reason':reason})
        result = {'phase_id':runner.PHASE_ID, 'exit_code':exit_code, 'child_exit_code':child_exit,
                  'status':status, 'stopped_reason':reason, 'exception_type':exception_type,
                  'admitted_start_recorded':admitted_started,
                  'process_tree_cpu_seconds':peak_cpu, 'peak_process_tree_rss_bytes':peak_rss,
                  'supervisor_included_in_CPU_RSS_and_affinity':True, 'affinity_cores':cores,
                  'global_cpu_seconds_used':terminal['global_cpu_seconds'],
                  'global_wall_seconds_used':terminal['global_wall_seconds'],
                  'original_first_attempt_unix':approval['accounting']['original_first_attempt_unix'],
                  'original_phase_started_unix':state['started_unix'], 'full_study_complete':False}
        path = private/('pure_followup.'+identity+'.resources.json')
        with path.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        print(json.dumps(result), flush=True)
        lock.close()
    raise SystemExit(exit_code)


if __name__ == '__main__':
    main()
