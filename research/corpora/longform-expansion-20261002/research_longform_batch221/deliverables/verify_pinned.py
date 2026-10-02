#!/usr/bin/env python3
"""Offline invariants and synthetic role regressions; no source prose output."""
import collections,hashlib,importlib.util,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];P=ROOT/'private';D=ROOT/'deliverables';PREV=ROOT.parent/'research_longform_acquisition'
spec=importlib.util.spec_from_file_location('audit_pinned',D/'audit_pinned.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
def load(p):return json.loads(p.read_text())
class Tests(unittest.TestCase):
 def test_original_denominator_identities_and_no_replacements(self):
  s=load(P/'final_identity_manifest.json');original=load(P/'proposal_frozen.json')['files'];self.assertEqual(len(s['candidates']),221)
  self.assertEqual([(r['source_id'],r['source_path'],r['git_blob_sha1']) for r in s['candidates']],[(r['source_id'],r['source_path'],r['git_blob_sha1']) for r in original])
  for r in s['candidates']:
   self.assertLessEqual(r['attempts'],2);self.assertNotIn('/kids/',r['source_path']);self.assertTrue(r['source_path'].endswith('.md'))
   if r['status']=='verified':
    b=(P/r['private_relative_path']).read_bytes();self.assertEqual(len(b),r['declared_bytes']);self.assertEqual(hashlib.sha256(b).hexdigest(),r['sha256']);self.assertEqual(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),r['git_blob_sha1'])
 def test_all_spans_cover_original_bytes(self):
  rows={x['id']:x for x in load(P/'document_measurements.json')}
  for doc in load(P/'structure_spans.json'):
   r=rows[doc['id']];b=(P/'payloads'/r['source_id']/r['source_path']).read_bytes();pos=0
   for s in doc['spans']:
    self.assertEqual(s['start_byte'],pos);chunk=b[pos:s['end_byte']];self.assertEqual(hashlib.sha256(chunk).hexdigest(),s['sha256']);self.assertEqual(len(chunk),s['utf8_bytes']);pos=s['end_byte']
   self.assertEqual(pos,len(b));self.assertEqual(sum(x['utf8_bytes'] for x in r['role_totals'].values()),len(b))
 def test_longer_fence_is_not_closed_by_shorter_fence(self):
  spans,flags=audit.blocks('````python\n```\nx=1\n````\n正文\n'.encode());self.assertEqual([s['role'] for s in spans],['fenced_code','prose_candidate']);self.assertFalse(flags['unclosed_code_fence'])
 def test_list_continuations_and_boundaries(self):
  spans,_=audit.blocks('1. 论点\n\n    论述甲\n\n    论述乙\n\n> 引文\n\n正文\n'.encode());self.assertEqual(sum(s['role']=='list_continuation_prose' for s in spans),2);self.assertEqual(sum(s['role']=='marked_quote' for s in spans),1)
 def test_html_math_reference_are_separate(self):
  spans,_=audit.blocks('<script>\n代码\n</script>\n\n$$\n公式\n$$\n\n[^1]: 注释\n\n[x]: https://example.com\n\n正文\n'.encode());roles={x['role'] for x in spans};self.assertTrue({'html_block','display_math','footnote_definition','reference_definition','prose_candidate'}<=roles)
 def test_aggregate_exact_arithmetic(self):
  a=load(D/'aggregate_audit.json');r=load(D/'final_acquisition_receipt.json');self.assertEqual(a['acquired_verified_measured'],r['verified_documents']);self.assertEqual(a['overall']['raw_source_bytes'],r['verified_source_bytes']);self.assertLessEqual(r['cumulative_conservative_accounted_bytes'],r['cap_bytes'])
  for key in ['documents','raw_source_bytes','longform_screen_ge1000han_ge8blocks']:
   self.assertEqual(a['overall'][key],sum(a['by_source'][s][key] for s in a['by_source']))
 def test_original_13_frozen_unchanged(self):
  frozen=load(PREV/'deliverables/sample_freeze.json')
  # Supports the exact recorded filename-to-digest representation.
  hashes=frozen.get('sha256',frozen.get('files',{}))
  self.assertTrue(hashes)
  for name,expected in hashes.items():
   if isinstance(expected,dict):expected=expected['sha256']
   self.assertEqual(hashlib.sha256((PREV/'deliverables'/name).read_bytes()).hexdigest(),expected)
 def test_preserved_first_pass_and_authorized_retry(self):
  first=load(D/'acquisition_receipt.json');retry=load(P/'retry_receipt.json');final=load(D/'final_acquisition_receipt.json')
  self.assertEqual(first['verified_documents'],217);self.assertEqual(first['attempted_requests'],221);self.assertEqual(len(retry['attempts']),4);self.assertEqual(final['verified_documents'],221);self.assertEqual(final['attempted_requests'],225)
  self.assertEqual(hashlib.sha256((D/'acquisition_receipt.json').read_bytes()).hexdigest(),retry['first_pass_receipt_sha256']);self.assertEqual(hashlib.sha256((P/'acquisition_state.json').read_bytes()).hexdigest(),retry['first_pass_state_sha256']);self.assertLess(final['total_elapsed_from_first_acquisition_start_seconds'],590)
 def test_bibliographic_labels_not_prose(self):
  spans,_=audit.blocks('推荐人：甲\n\n链接：https://example.com\n\n题目：A Study\n\n作者论述\n'.encode());self.assertEqual(sum(x['role']=='bibliographic_or_contributor_label' for x in spans),3);self.assertEqual(sum(x['role']=='prose_candidate' for x in spans),1)
 def test_resource_and_publication_boundaries(self):
  a=load(D/'aggregate_audit.json');r=load(D/'final_acquisition_receipt.json')
  for res in [a['resources'],r]:self.assertLess(res['elapsed_seconds'],600);self.assertLess(res['max_rss_kib'],512*1024)
  derived=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file() and 'payloads' not in p.parts);self.assertLess(derived,50*1024**2)
  self.assertFalse(any('payloads' in p.parts for p in D.rglob('*')))
  self.assertEqual(a['model_admitted_documents'],0);self.assertEqual(a['verified_unaided_human_documents'],0)
if __name__=='__main__':unittest.main(verbosity=2)
