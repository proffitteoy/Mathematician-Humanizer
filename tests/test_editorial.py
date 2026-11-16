import sys
from pathlib import Path
import unittest
from style_compiler.editorial import lint, presentation

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


class PresentationTests(unittest.TestCase):
    def test_inline_equations_code_and_block_quotes_do_not_inflate_budget(self):
        text = '若 $x>0$，则 \\(x^2>0\\)。\n```tex\n$$code$$\n为什么这样？\n```\n> $$quote$$\n> 你可能会问，这不是条件，而是猜测。'
        result = presentation(text)
        self.assertEqual(result['display_math_blocks'], 0)
        self.assertEqual(result['findings'], [])

    def test_each_supported_standalone_form_has_exact_unicode_offsets(self):
        forms = ['$$a=b$$', r'\[c=d\]', '$e=f$', r'\(g=h\)', r'\begin{equation}i=j\end{equation}']
        text = '😀说明。\r\n' + '\n继续解释。\n'.join(forms)
        result = presentation(text)
        self.assertEqual(result['display_math_blocks'], 5)
        self.assertTrue(result['over_display_math_limit'])
        self.assertEqual([text[s['start']:s['end']] for s in result['display_math_spans']], forms)

    def test_three_separated_blocks_fit_the_default_budget(self):
        result = presentation('引入。\n$$a=b$$\n解释一。\n\\[c=d\\]\n解释二。\n$$e=f$$\n结束。')
        self.assertEqual(result['display_math_blocks'], 3)
        self.assertFalse(result['over_display_math_limit'])
        self.assertFalse(result['review_required'])

    def test_adjacent_blocks_are_reported_even_under_budget(self):
        result = presentation('$$a=b$$\n\n$$c=d$$')
        self.assertEqual(result['findings'][0]['id'], 'adjacent_display_math')

    def test_presumed_questions_and_reframing_are_located_for_contextual_review(self):
        text = '😀你可能会问，为什么要投影？这不是口号，而是技巧。'
        result = presentation(text)
        self.assertEqual({f['id'] for f in result['findings']},
                         {'presumed_reader_question', 'staged_why_question', 'forced_reframing'})
        for finding in result['findings']:
            self.assertEqual(text[finding['start']:finding['end']], finding['span'])

    def test_real_question_is_not_deleted_or_declared_a_semantic_error(self):
        text = '为什么这个条件必要？可用反例检查其作用。'
        result = check(text, text)
        self.assertTrue(result['presentation']['review_required'])
        self.assertFalse(result['blockers'])
        self.assertEqual(result['original_sha256'], result['candidate_sha256'])
        self.assertFalse(result['semantic_equivalence_proven'])

    def test_direct_mathematical_prose_needs_no_presentation_flag(self):
        self.assertFalse(presentation('投影确定最优拟合向量，核刻画系数的自由度。')['review_required'])
if __name__=='__main__':unittest.main()
