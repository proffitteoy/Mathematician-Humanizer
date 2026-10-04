#!/usr/bin/env python3
"""Compare frozen measurements and require a content/voice review before delivery."""
import argparse
import json
from pathlib import Path
from measure_text import ROOT, SCHEMA, sha, read_json, save_new, diagnose, validate_measurements, validate_coverage


def check(before, after, original_bytes, candidate_bytes, review):
    manifest = read_json(ROOT / 'references/runtime-manifest.json')
    result = {'schema': 'statistical-writing-revision-check/1', 'status': 'NOT_VERIFIED',
              'semantic_review_is_automated_proof': False, 'quality_or_human_score': None,
              'original_sha256': sha(original_bytes), 'candidate_sha256': sha(candidate_bytes)}
    problems = []
    if review is not None and not isinstance(review, dict):
        result['blockers'] = ['semantic_review_not_object']
        return result
    for name, receipt, raw in [('original', before, original_bytes), ('candidate', after, candidate_bytes)]:
        if not isinstance(receipt, dict):
            result['blockers'] = [name + ':measurement_receipt_not_object']
            return result
        try:
            validate_measurements(receipt.get('measurements'))
            validate_coverage(receipt.get('coverage'))
        except ValueError as exc:
            problems.append(name + ':' + str(exc))
        if receipt.get('schema') != SCHEMA or receipt.get('status') not in ('MEASURED', 'MEASURED_REUSED'):
            problems.append(name + ':measurement_not_verified')
        if receipt.get('text_sha256') != sha(raw):
            problems.append(name + ':text_changed_since_measurement')
        if receipt.get('profile_sha256') != manifest['measurement_profile_sha256']:
            problems.append(name + ':profile_mismatch')
        if receipt.get('reference_sha256') != manifest['reference_sha256']:
            problems.append(name + ':reference_mismatch')
    if before.get('source') != after.get('source') or before.get('band') != after.get('band'):
        problems.append('reference_changed_between_versions')
    if problems:
        result['blockers'] = problems
        return result
    diagnosis = diagnose(after['measurements'], after['source'], after['band'])
    rows = []
    for row in diagnosis['rows']:
        previous = before['measurements'].get(row['id'], {}).get('value')
        current = row['value']
        row = dict(row, previous_value=previous,
                   actual_change=None if previous is None or current is None else current - previous)
        rows.append(row)
    result['dimensions'] = rows
    if any(r['value'] is None for r in rows):
        result['blockers'] = ['candidate:reference_dimension_unavailable']
        return result
    result['measurement_gate'] = 'MEASURED'
    if review is None:
        result['status'] = 'NEEDS_SEMANTIC_REVIEW'
        result['blockers'] = ['Content and voice must be explicitly reconciled against the original.']
        return result
    if (review.get('schema') != 'statistical-writing-semantic-review/1' or
        review.get('original_sha256') != sha(original_bytes) or
        review.get('candidate_sha256') != sha(candidate_bytes)):
        problems.append('semantic_review_not_bound_to_exact_texts')
    if review.get('reviewer_kind') not in ('author_self_check', 'independent_human_review'):
        problems.append('reviewer_kind_missing')
    ledger = review.get('ledger', [])
    if not ledger or not all(isinstance(x, dict) and x.get('id') and x.get('original_claim')
                            and x.get('candidate_evidence') and x.get('verdict') == 'preserved' for x in ledger):
        problems.append('content_ledger_incomplete_or_not_preserved')
    if (review.get('meaning_preserved') is not True or review.get('voice_preserved') is not True or
        review.get('unsupported_additions') is not False or review.get('unresolved_items') != []):
        problems.append('semantic_or_voice_issue_unresolved')
    dispositions = {x.get('feature_id'): x for x in review.get('dimensional_review', []) if isinstance(x, dict)}
    for row in rows:
        if row['diagnostic_status'] in ('BELOW_Q10', 'ABOVE_Q90'):
            d = dispositions.get(row['id'], {})
            if d.get('decision') != 'retain_for_meaning_or_voice' or not d.get('reason'):
                problems.append('diagnostic_needs_revision_or_explanation:' + row['id'])
    result['reviewer_kind'] = review.get('reviewer_kind')
    result['status'] = 'NEEDS_REVISION_OR_REVIEW' if problems else 'MEASURED_AND_REVIEWED'
    result['blockers'] = problems
    result['meaning_gate'] = 'SELF_REVIEWED' if not problems and review.get('reviewer_kind') == 'author_self_check' else 'SEE_REVIEW'
    result['interpretation'] = ('Delivery workflow receipt, not semantic equivalence proof, quality validation, joint statistical acceptance, or authorship evidence. '
                                'Out-of-range dimensions can be retained for meaning/voice with an explicit reason; do not force all means.')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('original_measurement', type=Path)
    p.add_argument('candidate_measurement', type=Path)
    p.add_argument('--original-text', required=True, type=Path)
    p.add_argument('--candidate-text', required=True, type=Path)
    p.add_argument('--review', type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        p.error('output exists; use a new version name')
    try:
        result = check(read_json(args.original_measurement), read_json(args.candidate_measurement),
                       args.original_text.read_bytes(), args.candidate_text.read_bytes(),
                       read_json(args.review) if args.review else None)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'schema': 'statistical-writing-revision-check/1', 'status': 'NOT_VERIFIED',
                  'blockers': [type(exc).__name__], 'quality_or_human_score': None}
    save_new(args.output, result)
    print(json.dumps({'status': result['status'], 'output': str(args.output),
                      'blockers': result.get('blockers', [])}, ensure_ascii=False))
    return 0 if result['status'] == 'MEASURED_AND_REVIEWED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
