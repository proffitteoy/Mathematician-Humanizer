#!/usr/bin/env python3
"""Offline pinned measurement and dimensional diagnosis; no writing/authorship score."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from show_reference import load_card, BANDS, EXPECTED_SHA256
MANIFEST = ROOT / 'references/runtime-manifest.json'
SCHEMA = 'statistical-writing-measurement/1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def save_new(path, data):
    # Never overwrite a measurement receipt, even on failed verification.
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def validate_measurements(measurements):
    if not isinstance(measurements, dict):
        raise ValueError('measurement_rows_not_object')
    for feature, row in measurements.items():
        if not isinstance(row, dict):
            raise ValueError('measurement_row_not_object:' + str(feature))
        value = row.get('value')
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError('nonfinite_or_invalid_measurement:' + str(feature))


def validate_coverage(coverage):
    if not isinstance(coverage, dict):
        raise ValueError('parse_coverage_not_object')
    counts = ('source_sentences', 'complete_target_sentences', 'clipped_target_sentences',
              'excluded_sentences', 'complete_parse_failures', 'complete_pos_only')
    if any(type(coverage.get(k)) is not int or coverage[k] < 0 for k in counts):
        raise ValueError('parse_coverage_invalid_counts')
    if (coverage['source_sentences'] <= 0 or
        coverage['complete_target_sentences'] != coverage['source_sentences'] or
        any(coverage[k] != 0 for k in counts[2:])):
        raise ValueError('incomplete_parser_coverage')


def diagnose(measurements, source, band):
    validate_measurements(measurements)
    r = load_card(source, band)
    rows = []
    for i, f in enumerate(r['features']):
        m = measurements.get(f['id'], {})
        value = m.get('value')
        lo, hi = r['card']['q10'][i], r['card']['q90'][i]
        status = ('UNAVAILABLE' if value is None else
                  'BELOW_Q10' if value < lo else 'ABOVE_Q90' if value > hi else
                  'WITHIN_MARGINAL_Q10_Q90')
        rows.append(dict(f, value=value, q10=lo, q90=hi,
                         reference_components=r['card']['components'],
                         numerator=m.get('numerator'), denominator=m.get('denominator'),
                         opportunities=m.get('opportunities'),
                         missing_reason=m.get('missing_reason'), diagnostic_status=status))
    return {'source': source, 'band': band, 'rows': rows,
            'interpretation': 'Marginal diagnostics only. Outside is a review signal, not a failure. Inside is not joint acceptance, quality or authorship evidence.',
            'quality_or_human_score': None}


def verified_files(manifest):
    for rel, expected in manifest['source_files_sha256'].items():
        p = ROOT / rel
        if not p.is_file() or sha(p.read_bytes()) != expected:
            raise ValueError('instrument_source_hash_mismatch:' + rel)
    if sha((ROOT / 'references/human-joint-reference.json').read_bytes()) != manifest['reference_sha256']:
        raise ValueError('reference_hash_mismatch')


def actual_runtime(manifest):
    versions = {}
    for name, expected in manifest['package_versions'].items():
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            raise ValueError('missing_dependency:' + name) from None
        if versions[name] != expected:
            raise ValueError('dependency_version_mismatch:' + name)
    if platform.python_version() != manifest['python']:
        raise ValueError('python_version_mismatch')
    if unicodedata.unidata_version != manifest['unicode']:
        raise ValueError('unicode_version_mismatch')
    return {'python': platform.python_version(), 'unicode': unicodedata.unidata_version,
            'package_versions': versions, 'threads': 2, 'device': 'cpu'}


def worker(request, result):
    """Runs with caller-selected Python -I; strict checks precede model loading."""
    req = read_json(request)
    out = {'status': 'NOT_VERIFIED'}
    try:
        manifest = read_json(MANIFEST)
        verified_files(manifest)
        runtime = actual_runtime(manifest)
        # Disable implicit download/network access. Models are verified by LocalStanza.
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                          OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
        import socket
        def deny(*args, **kwargs):
            raise RuntimeError('measurement_is_offline')
        socket.socket.connect = deny
        socket.socket.connect_ex = deny
        socket.create_connection = deny
        sys.path.insert(0, str(ROOT / 'scripts/vendor'))
        from research.surface.adapter import SourceView, SourceObservation, Interval, make_projection
        from research.linguistic.stanza_local import LocalStanza
        from research.linguistic.adapter import measure
        raw = Path(req['input']).read_bytes()
        if sha(raw) != req['text_sha256']:
            raise ValueError('input_changed_before_measurement')
        text = raw.decode('utf-8')  # No strip, newline conversion, normalization or extraction.
        parser = LocalStanza(req['models'], threads=2)
        import torch, numpy, stanza
        if (str(torch.__version__) != runtime['package_versions']['torch'] or
                numpy.__version__ != runtime['package_versions']['numpy'] or
                stanza.__version__ != runtime['package_versions']['stanza']):
            raise ValueError('imported_dependency_identity_mismatch')
        sv = SourceView(sha(raw), 'input.txt', 0, 0, 'exact-utf8-file/1', 0, '',
                        'user_supplied_unchanged_text', sha(raw), len(text))
        obs = SourceObservation(sv, text)
        projection = make_projection(sv, (Interval(0, len(text)),),
            annotation_profile='whole-unchanged-text/1', annotation_status='provisional')
        parsed = parser.parse(obs)
        bundle = measure(obs, projection, parsed)
        if bundle['identity']['profile_sha256'] != manifest['measurement_profile_sha256']:
            raise ValueError('measurement_profile_mismatch')
        if sha(Path(req['input']).read_bytes()) != req['text_sha256']:
            raise ValueError('input_changed_during_measurement')
        rows = bundle['target']['global_measurements']
        validate_measurements(rows)
        coverage = bundle['target']['coverage']
        complete = (coverage['source_sentences'] > 0 and coverage['complete_parse_failures'] == 0
                    and coverage['complete_pos_only'] == 0 and coverage['clipped_target_sentences'] == 0
                    and coverage['complete_target_sentences'] == coverage['source_sentences'])
        out = {'status': 'MEASURED' if complete else 'NOT_VERIFIED',
               'reason': None if complete else 'incomplete_parser_coverage',
               'runtime': runtime, 'profile': bundle['profile'],
               'profile_sha256': bundle['identity']['profile_sha256'],
               'instrument_measurement_status': bundle['measurement_status'],
               'values': {k: v['value'] for k, v in rows.items()},
               'measurements': rows, 'coverage': coverage, 'parse_audit': bundle['parse_audit'],
               'quality_or_semantic_validation': False}
    except Exception as exc:
        # Do not echo arbitrary third-party exceptions which may include input prose.
        known = isinstance(exc, (ValueError, FileNotFoundError, ImportError))
        reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        out = {'status': 'NOT_VERIFIED', 'reason': reason if known else type(exc).__name__}
    save_new(result, out)
    return 0 if out['status'] == 'MEASURED' else 2


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        return worker(sys.argv[2], sys.argv[3])
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path, help='Exact UTF-8 text file. Read unchanged; never overwritten.')
    p.add_argument('--source', required=True, choices=('web', 'baike'))
    p.add_argument('--band', choices=BANDS, default='reference')
    p.add_argument('--python', default=os.environ.get('STYLE_PYTHON', sys.executable),
                   help='Pinned Python executable, or STYLE_PYTHON; no built-in private path.')
    p.add_argument('--models', default=os.environ.get('STYLE_MODELS'),
                   help='Existing official Stanza model root, or STYLE_MODELS. No downloads.')
    p.add_argument('--output', required=True, type=Path, help='New immutable JSON receipt')
    p.add_argument('--previous', type=Path, help='Previous measurement receipt for revision provenance')
    p.add_argument('--timeout', type=int, default=300, help='Maximum worker wall seconds')
    args = p.parse_args()
    if args.output.exists():
        p.error('output exists; use a new version name')
    out = {'schema': SCHEMA, 'status': 'NOT_VERIFIED',
           'source': args.source, 'band': args.band,
           'reference_sha256': EXPECTED_SHA256, 'semantic_gate': 'NOT_REVIEWED',
           'acceptance': None, 'quality_or_human_score': None}
    try:
        raw = args.input.read_bytes()
        text = raw.decode('utf-8')
        if not text.strip():
            raise ValueError('empty_input')
        out['text_sha256'] = sha(raw)
        out['utf8_bytes'] = len(raw)
        out['codepoints'] = len(text)
        out['input_unchanged'] = True
        if args.previous:
            previous_raw = args.previous.read_bytes()
            previous = json.loads(previous_raw)
            if previous.get('schema') != SCHEMA:
                raise ValueError('previous_receipt_schema_mismatch')
            out['previous'] = {'receipt_sha256': sha(previous_raw), 'text_sha256': previous['text_sha256']}
        if not args.models:
            raise ValueError('models_not_configured')
        if not Path(args.models).is_dir():
            raise ValueError('models_directory_missing')
        verified_files(read_json(MANIFEST))
        with tempfile.TemporaryDirectory(prefix='statistical-writing-') as temp:
            request, result = Path(temp) / 'request.json', Path(temp) / 'result.json'
            save_new(request, {'input': str(args.input.resolve()), 'text_sha256': sha(raw),
                               'models': str(Path(args.models).resolve())})
            env = os.environ.copy()
            env.pop('PYTHONPATH', None)
            try:
                process = subprocess.run([args.python, '-I', str(Path(__file__).resolve()),
                                          '--worker', str(request), str(result)],
                                         capture_output=True, text=True, timeout=args.timeout, env=env)
            except subprocess.TimeoutExpired:
                raise ValueError('parser_timeout') from None
            if not result.is_file():
                raise ValueError('parser_process_failed:' + str(process.returncode))
            out.update(read_json(result))
        out['diagnostics'] = diagnose(out.get('measurements', {}), args.source, args.band)
        if any(r['value'] is None for r in out['diagnostics']['rows']):
            out['status'] = 'NOT_VERIFIED'
            out['reason'] = out.get('reason') or 'reference_dimension_unavailable'
    except (OSError, ValueError, KeyError, TypeError) as exc:
        out['status'] = 'NOT_VERIFIED'
        out['reason'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        try:
            out['diagnostics'] = diagnose({}, args.source, args.band)
        except Exception:
            pass
    save_new(args.output, out)
    print(json.dumps({'status': out['status'], 'reason': out.get('reason'),
                      'output': str(args.output), 'text_sha256': out.get('text_sha256')}, ensure_ascii=False))
    return 0 if out['status'] == 'MEASURED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
