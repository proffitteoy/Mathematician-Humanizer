#!/usr/bin/env python3
"""Import one exact previously frozen measurement without rerunning its parser.

The provenance hash is an integrity link, not independent authenticity proof.
Only use a trusted measurement produced by the documented frozen instrument.
"""
import argparse
from pathlib import Path
from measure_text import ROOT, SCHEMA, sha, read_json, save_new, diagnose, validate_measurements, validate_coverage


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--receipt', required=True, type=Path)
    p.add_argument('--receipt-sha256', required=True, help='Previously recorded trusted measurement SHA-256')
    p.add_argument('--id', required=True)
    p.add_argument('--source', required=True, choices=('web', 'baike'))
    p.add_argument('--band', default='reference', choices=('reference', 'lower_single_han_share', 'middle_single_han_share', 'upper_single_han_share'))
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    if a.output.exists():
        p.error('output exists; use a new version name')
    out = {'schema': SCHEMA, 'status': 'NOT_VERIFIED', 'source': a.source, 'band': a.band,
           'semantic_gate': 'NOT_REVIEWED', 'quality_or_human_score': None}
    try:
        raw, receipt_raw = a.input.read_bytes(), a.receipt.read_bytes()
        if sha(receipt_raw) != a.receipt_sha256:
            raise ValueError('saved_receipt_hash_mismatch')
        receipt = read_json(a.receipt)
        rows = [r for r in receipt['results'] if r['id'] == a.id]
        if len(rows) != 1:
            raise ValueError('saved_id_not_unique')
        r = rows[0]
        manifest = read_json(ROOT / 'references/runtime-manifest.json')
        if r['text_sha256'] != sha(raw):
            raise ValueError('saved_text_hash_mismatch')
        if (r['profile_sha256'] != manifest['measurement_profile_sha256'] or
            receipt['joint_card_sha256'] != manifest['reference_sha256']):
            raise ValueError('saved_profile_or_reference_mismatch')
        coverage = r['coverage']
        validate_coverage(coverage)
        validate_measurements(r['measurements'])
        out.update({'status': 'MEASURED_REUSED', 'text_sha256': sha(raw), 'codepoints': len(raw.decode('utf-8')),
                    'utf8_bytes': len(raw), 'input_unchanged': True, 'profile_sha256': r['profile_sha256'],
                    'reference_sha256': receipt['joint_card_sha256'],
                    'values': r['values'], 'measurements': r['measurements'], 'parse_audit': r['parse_audit'],
                    'coverage': coverage, 'instrument_measurement_status': r['measurement_status'],
                    'provenance': {'reused_receipt_sha256': sha(receipt_raw), 'id': a.id,
                                   'runtime_reexecuted': False, 'trusted_prior_receipt_required': True}})
        out['diagnostics'] = diagnose(r['measurements'], a.source, a.band)
        if any(x['value'] is None for x in out['diagnostics']['rows']):
            raise ValueError('saved_reference_dimension_unavailable')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        out.update(status='NOT_VERIFIED', reason=str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
    save_new(a.output, out)
    print(out['status'])
    return 0 if out['status'] == 'MEASURED_REUSED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
