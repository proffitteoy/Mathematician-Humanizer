"""Synthetic integrity and Unicode cases; no acquired corpus content."""
import hashlib
import unittest
from unittest import mock
import independent_verify as v

class IntegrityCases(unittest.TestCase):
    def fixture(self):
        blob = v.object_sha('blob', b'example\n')
        sub_payload = b'100644 note.md\0' + bytes.fromhex(blob)
        subtree = v.object_sha('tree', sub_payload)
        return {'sha':'request-commit-reference', 'truncated':False, 'tree':[
            {'path':'folder/note.md','type':'blob','mode':'100644','sha':blob},
            {'path':'folder','type':'tree','mode':'040000','sha':subtree}]}

    def test_recursive_tree_does_not_trust_request_header(self):
        f = self.fixture()
        expected = v.object_sha('tree', b'40000 folder\0'+bytes.fromhex(f['tree'][1]['sha']))
        self.assertEqual(v.reconstruct_tree(f)[0], expected)

    def test_tree_child_tamper_fails(self):
        f = self.fixture(); f['tree'][0]['sha'] = '0'*40
        with self.assertRaises(AssertionError): v.reconstruct_tree(f)

    def test_duplicate_path_fails(self):
        f = self.fixture(); f['tree'].append(dict(f['tree'][0]))
        with self.assertRaises(AssertionError): v.reconstruct_tree(f)

    def test_path_escape_fails(self):
        f = self.fixture(); f['tree'][0]['path'] = '../note.md'
        with self.assertRaises(AssertionError): v.reconstruct_tree(f)

    def test_truncated_tree_fails(self):
        f = self.fixture(); f['truncated'] = True
        with self.assertRaises(AssertionError): v.reconstruct_tree(f)

    def test_duplicate_json_key_fails(self):
        with self.assertRaises(ValueError): v.decode_json('{"a":1,"a":2}')

    def test_nonfinite_json_fails(self):
        for value in ('NaN','Infinity','-Infinity'):
            with self.assertRaises(ValueError): v.decode_json(value)

    def test_nfkc_whitespace_keeps_punctuation(self):
        self.assertEqual(v.norm('Ａ\u00a0中\u3000文\n。'), 'A中文。')
        self.assertEqual(v.norm_sha('Ａ\n'),hashlib.sha256(b'nfkc-no-ws/v1\0A').hexdigest())

    def test_unicode_version_mismatch_fails(self):
        with mock.patch.object(v.unicodedata, 'unidata_version','different'):
            with self.assertRaises(ValueError): v.norm('x')

    def test_untrusted_yaml_remains_literal(self):
        text = '---\na: !!python/object:untrusted\n---\n````\nexample\n```\n'
        fm, claims, code, flags = v.structural(text)
        self.assertEqual(claims['a'],['!!python/object:untrusted'])
        self.assertTrue(code['unclosed_fence'])
        self.assertTrue(flags['fenced_code_marker'])

if __name__=='__main__': unittest.main()
