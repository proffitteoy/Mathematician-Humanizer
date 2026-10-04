import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import test_measurement_loop as fixtures
from check_editorial_revision import editorial_check,warning_id
from prose_lint import lint
from measure_text import sha
class GateTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.LoopTests();fixture.setUp();self.raw=fixture.raw;self.receipt=fixture.receipt;self.review=fixture.review
        self.review.update(editorial_context='technical',protected_literals=[],unchanged_content_reviewed=True,unsupported_stance_or_experience=False,editorial_review=[])
    def run_gate(self,a,b):
        before=copy.deepcopy(self.receipt);after=copy.deepcopy(self.receipt);before['text_sha256']=sha(a);after['text_sha256']=sha(b)
        self.review.update(original_sha256=sha(a),candidate_sha256=sha(b))
        return editorial_check(before,after,a,b,self.review)
    def test_valid(self):self.assertEqual(self.run_gate(self.raw,self.raw)['status'],'MEASURED_AND_EDITORIALLY_REVIEWED')
    def test_protected_cannot_self_approve(self):self.assertIn('protected_content_changed',self.run_gate(b'$x>0$',b'$x>=0$')['blockers'])
    def test_unreviewed_soft(self):self.assertTrue(any(x.startswith('unreviewed_lint') for x in self.run_gate('可能。'.encode(),'确定。'.encode())['blockers']))
    def test_reviewed_soft(self):
        a=b'In conclusion.';w=lint(a,a)['warnings'][0];self.review['editorial_review']=[{'warning_id':warning_id(w),'decision':'retain_for_meaning_or_voice','reason':'The user explicitly requested a conclusion label.'}]
        self.assertEqual(self.run_gate(a,a)['status'],'MEASURED_AND_EDITORIALLY_REVIEWED')
    def test_missing_stance_review(self):
        self.review.pop('unsupported_stance_or_experience');self.assertIn('stance_or_experience_not_reviewed',self.run_gate(self.raw,self.raw)['blockers'])
    def test_semantic_rejection(self):
        self.review['meaning_preserved']=False;self.assertNotEqual(self.run_gate(self.raw,self.raw)['status'],'MEASURED_AND_EDITORIALLY_REVIEWED')
    def test_stale_hash(self):
        self.review['candidate_sha256']='0'*64
        self.assertNotEqual(editorial_check(self.receipt,self.receipt,self.raw,self.raw,self.review)['status'],'MEASURED_AND_EDITORIALLY_REVIEWED')
if __name__=='__main__':unittest.main()
