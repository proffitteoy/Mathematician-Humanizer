import sys
from pathlib import Path
import unittest
from style_compiler.editorial import lint

def check(a,b,locks=()):return lint(a.encode(),b.encode(),locks)
class Tests(unittest.TestCase):
    def test_plain_unchanged(self):self.assertEqual(check('今天下雨。','今天下雨。')['status'],'NO_MECHANICAL_FINDINGS')
    def test_not_ban_punctuation(self):self.assertFalse(check('然而——“可行”。','然而——“可行”。')['warnings'])
    def test_code_protected(self):self.assertTrue(check('```py\nx=1\n```','```py\nx=2\n```')['blockers'])
    def test_tilde_protected(self):self.assertTrue(check('~~~\nx\n~~~','~~~\ny\n~~~')['blockers'])
    def test_indented_fence(self):self.assertTrue(check('  ```text\n旧值\n  ```','  ```text\n新值\n  ```')['blockers'])
    def test_multitick(self):self.assertTrue(check('``a`b``','``a`c``')['blockers'])
    def test_minus(self):self.assertTrue(check('x−y','x-y')['warnings'])
    def test_math_protected(self):self.assertTrue(check('若 $x>0$。','若 $x>=0$。')['blockers'])
    def test_quote_protected(self):self.assertTrue(check('> 不超过3人\n','> 3人\n')['blockers'])
    def test_url_protected(self):self.assertTrue(check('https://a.test/?x=1','https://a.test/?x=2')['blockers'])
    def test_protected_not_style_flagged(self):self.assertFalse(check('`In conclusion`','`In conclusion`')['warnings'])
    def test_number_drift(self):self.assertIn('quantity_changed',[x['id'] for x in check('计划最多10人。','计划20人。')['warnings']])
    def test_negation_drift(self):self.assertIn('logic_or_uncertainty_changed',[x['id'] for x in check('不能得出结论。','能得出结论。')['warnings']])
    def test_unicode_not_mutated(self):
        s='👩\u200d💻';r=check(s,s);self.assertEqual(r['warnings'][0]['codepoint'],'U+200D');self.assertFalse(r['blockers'])
    def test_bidi_warning(self):self.assertTrue(check('abc','ab\u202ec')['warnings'])
    def test_explicit_lock(self):self.assertTrue(check('所有正整数','部分正整数',['所有'])['blockers'])
    def test_absent_lock(self):
        with self.assertRaises(ValueError):check('甲','乙',['丙'])
    def test_not_detector(self):self.assertIsNone(check('综上所述','综上所述')['quality_or_authorship_score'])
    def test_same_number_wrong_actor_not_proven(self):self.assertFalse(check('甲给乙10元。','乙给甲10元。')['semantic_equivalence_proven'])
    def test_duplicate_paragraph(self):self.assertIn('repeated_paragraph',[x['id'] for x in check('甲。','甲。\n\n甲。')['warnings']])
    def test_quote_reordering_blocked(self):self.assertTrue(check('`a`，`b`','`b`，`a`')['blockers'])
if __name__=='__main__':unittest.main()
