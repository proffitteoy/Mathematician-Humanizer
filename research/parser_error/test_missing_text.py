"""Synthetic v0.1.1 failure-accounting regressions, no corpus examples."""
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from dataclasses import replace
from research.parser_error.evaluate import evaluate,read_records,select_records,sha
from research.parser_error.freeze_selection import freeze_bytes
from research.parser_error.test_evaluate import sent


def fixture(kind='missing'):
    blocks=[]
    for prefix in ('n','w'):
        for i in range(32):
            header=f'# sent_id = {prefix}{i:03}\n'
            if (prefix,i)!=('n',0) or kind=='present':header+='# text = 甲\n'
            elif kind=='empty':header+='# text = \n'
            blocks.append(header+'1\t甲\t_\tNOUN\t_\t_\t0\troot\t_\t_')
    return ('\n\n'.join(blocks)+'\n\n').encode()

class TestMissingText(unittest.TestCase):
    def run_case(self,kind):
        raw=fixture(kind)
        selection={'selection':[{'sent_id':x['meta']['sent_id']} for x in select_records(read_records(raw))]}
        class Fake:
            vocabulary={'pos':{'upos':['NOUN']},'depparse':{'deprel':['root']}}
            def __init__(self):self.calls=0
            def parse(self,obs):
                self.calls+=1
                if not obs.text:return SimpleNamespace(sentences=[])
                return SimpleNamespace(sentences=[replace(sent(text='甲',heads=(0,),pos=('NOUN',),relations=('root',)),status='ok')])
        parser=Fake()
        with patch('research.parser_error.evaluate.control_parse',side_effect=lambda p,r,t:r) as control:
            result,records=evaluate(raw,selection,parser)
        return result,records,parser.calls,control.call_count

    def test_missing_preserves_all_selected_and_skips_both_arms(self):
        r,units,calls,controls=self.run_case('missing');c=r['coverage']
        self.assertEqual((c['selected_records'],c['selected_reference_integer_rows'],len(units)),(64,64,64))
        self.assertEqual((c['common_gate_records'],c['common_gate_reference_tokens'],c['excluded_reference_integer_rows']),(63,63,1))
        self.assertEqual((c['boundary_exact_records'],c['boundary_mismatch_records'],c['boundary_not_evaluable_records']),(63,0,1))
        self.assertEqual((calls,controls,c['production_source_units'],c['control_success_records']),(63,63,63,63))
        self.assertEqual(c['reference_failed_records'],1);self.assertEqual(r['reference_failures'],{'missing_text':1})
        for key in ('source_text_unavailable_records','production_not_attempted_missing_text_records','control_not_attempted_missing_text_records'):self.assertEqual(c[key],1)
        self.assertEqual(c['production_failed_source_units'],0)
        failed=[u for u in units if u.get('source_text_failure')=='missing_text'];self.assertEqual(len(failed),1)
        self.assertIsNone(failed[0]['boundary_exact'])
        for key in ('reference','production','control'):self.assertNotIn(key,failed[0])

    def test_empty_present_text_is_not_missing(self):
        r,units,calls,controls=self.run_case('empty');c=r['coverage']
        self.assertEqual(c['selected_records'],64);self.assertEqual(c['source_text_unavailable_records'],0)
        self.assertEqual(c['boundary_mismatch_records'],1);self.assertEqual(c['boundary_not_evaluable_records'],0)
        self.assertEqual(c['reference_failed_records'],1);self.assertEqual((calls,controls),(64,63))
        self.assertEqual(c['common_gate_records'],63)

    def test_freeze_missing_is_deterministic_and_source_hash_required(self):
        raw=fixture();pre=b'original synthetic contract'
        with self.assertRaisesRegex(ValueError,'corpus_hash_mismatch'):freeze_bytes(raw,pre)
        with patch('research.parser_error.freeze_selection.SOURCE_SHA',sha(raw)):
            a=freeze_bytes(raw,pre);self.assertEqual(a,freeze_bytes(raw,pre))
            with self.assertRaisesRegex(ValueError,'legacy_missing_text'):freeze_bytes(raw,pre,version='legacy')
        d=json.loads(a);self.assertEqual(d['schema_version'],'pud-selection/1.1.0');self.assertEqual(len(d['selection']),64)
        missing=[x for x in d['selection'] if x['source_text_status']=='missing'];self.assertEqual(len(missing),1)
        self.assertIsNone(missing[0]['text_sha256'])

    def test_legacy_present_manifest_retains_exact_fields(self):
        raw=fixture('present')
        with patch('research.parser_error.freeze_selection.SOURCE_SHA',sha(raw)):
            old=json.loads(freeze_bytes(raw,b'x',version='legacy'));new=json.loads(freeze_bytes(raw,b'x'))
        self.assertNotIn('schema_version',old)
        for a,b in zip(old['selection'],new['selection']):
            self.assertEqual(b.pop('source_text_status'),'present');self.assertEqual(a,b)

    def test_freeze_empty_has_present_empty_digest(self):
        raw=fixture('empty')
        with patch('research.parser_error.freeze_selection.SOURCE_SHA',sha(raw)):d=json.loads(freeze_bytes(raw,b'x'))
        empty=[x for x in d['selection'] if x['source_text_status']=='empty'];self.assertEqual(len(empty),1)
        self.assertEqual(empty[0]['text_sha256'],sha(b''))

if __name__=='__main__':unittest.main()
