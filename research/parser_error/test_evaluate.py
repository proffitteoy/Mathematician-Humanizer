"""Original synthetic arithmetic checks; never evaluation-corpus examples."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from dataclasses import replace
from research.parser_error.evaluate import (ReferenceSentence,Token,reference,score_pair,
    score_summary,features,read_records,validate_tokens,HISTORY,WINDOWS,channel_report,evaluate,select_records)


def sent(text='甲乙丙', parts=None, heads=(2,0,2), pos=('NOUN','VERB','NOUN'), relations=('nsubj','root','obj')):
    if parts is None:parts=[(i,i+1) for i in range(len(text))]
    return ReferenceSentence(0,0,len(text),tuple(Token(i+1,a,b,text[a:b],pos[i],heads[i],relations[i]) for i,(a,b) in enumerate(parts)))


class TestEvaluator(unittest.TestCase):
    def test_reference_alignment_preserves_internal_whitespace(self):
        r={'meta':{'text':'甲 \t乙'},'rows':[['1','甲','_','NOUN','_','_','2','nsubj','_','_'],['2','乙','_','VERB','_','_','0','root','_','_']]}
        s=reference(r,0);self.assertEqual([(t.start,t.end) for t in s.tokens],[(0,1),(3,4)])
        self.assertEqual(s.annotation_provenance,'converted_manual_treebank_reference')

    def test_no_silent_form_repair(self):
        r={'meta':{'text':'甲乙'},'rows':[['1','乙','_','NOUN','_','_','0','root','_','_']]}
        with self.assertRaisesRegex(ValueError,'unaligned'):reference(r,0)

    def test_mwt_fails_explicitly(self):
        r={'meta':{'text':'甲乙'},'rows':[['1-2','甲乙','_','_','_','_','_','_','_','_']]}
        with self.assertRaisesRegex(ValueError,'mwt_or_empty_node'):reference(r,0)

    def test_reader_does_not_trim_text(self):
        raw='# sent_id = synthetic\n# text = 甲乙 \n1\t甲乙\t_\tNOUN\t_\t_\t0\troot\t_\t_\n\n'.encode()
        self.assertEqual(read_records(raw)[0]['meta']['text'],'甲乙 ')

    def test_cr_container_is_not_normalized(self):
        with self.assertRaisesRegex(ValueError,'CR'):read_records(b'# text = x\r\n')

    def test_perfect_scores(self):
        s=sent();counts,conf=score_pair(s,s);d=score_summary(counts['all'])
        self.assertEqual(d['token_span_f1'],1);self.assertEqual(d['full_las_agreement_aligned'],1)
        self.assertFalse(conf['upos'])

    def test_unmatched_dependent_and_head_are_counted(self):
        g=sent();p=sent(parts=[(0,2),(2,3)],heads=(0,1),pos=('VERB','NOUN'),relations=('root','obj'))
        counts,_=score_pair(g,p);d=score_summary(counts['all'])
        self.assertEqual(d['reference_tokens'],3);self.assertEqual(d['predicted_tokens'],2)
        self.assertEqual(d['aligned_dependents'],1);self.assertEqual(d['unmatched_reference_tokens'],2)
        self.assertEqual(d['unmatched_predicted_tokens'],1);self.assertEqual(d['upos_agreement_aligned'],1)
        self.assertEqual(d['upos_correct_per_reference_token'],1/3);self.assertEqual(d['head_correct'],0)
        self.assertEqual(d['reference_head_span_available'],0)

    def test_subtype_disagreement_is_separate(self):
        g=sent(relations=('nsubj:pass','root','obj'));p=sent()
        counts,conf=score_pair(g,p);d=score_summary(counts['all'])
        self.assertEqual(d['head_correct'],3);self.assertEqual(d['base_las_correct'],3);self.assertEqual(d['full_las_correct'],2)
        self.assertEqual(conf['deprel_full'][('nsubj:pass','nsubj')],1);self.assertFalse(conf['deprel_base'])

    def test_reference_lexical_denominator_does_not_follow_prediction(self):
        g=sent();p=replace(g,tokens=(replace(g.tokens[0],upos='PUNCT'),*g.tokens[1:]))
        counts,_=score_pair(g,p)
        self.assertEqual(counts['reference_lexical']['reference_tokens'],3)
        self.assertEqual(counts['reference_lexical']['upos_correct'],2)

    def test_short_windows_and_history_are_unavailable(self):
        values=features([sent()]);self.assertEqual(len(values),71)
        for key in HISTORY|WINDOWS:self.assertIsNone(values[key]['value'])
        self.assertEqual(values['zh:cue.pronoun_first']['value'],0)

    def test_records_never_form_fake_100_token_window(self):
        units=[replace(sent(),source_sentence_index=i) for i in range(40)]
        for key in WINDOWS:self.assertIsNone(features(units)[key]['value'])

    def test_invalid_cycle_rejected(self):
        s=sent(heads=(3,0,1))
        with self.assertRaisesRegex(ValueError,'cycle'):validate_tokens(s.tokens,'甲乙丙')

    def test_full_pipeline_retains_boundary_reference_and_parse_failures(self):
        blocks=[]
        for prefix in ('n','w'):
            for i in range(32):
                text='甲。乙' if (prefix,i)==('n',0) else '甲乙丙'
                forms=list(text)
                if (prefix,i)==('n',1):forms[0]='丁'
                rows=[f"{j+1}\t{form}\t_\tNOUN\t_\t_\t{0 if j==0 else 1}\t{'root' if j==0 else 'dep'}\t_\t_" for j,form in enumerate(forms)]
                blocks.append(f'# sent_id = {prefix}{i:03}\n# text = {text}\n'+'\n'.join(rows))
        raw=('\n\n'.join(blocks)+'\n\n').encode()
        records=read_records(raw);selection={'selection':[{'sent_id':x['meta']['sent_id']} for x in select_records(records)]}
        class Fake:
            vocabulary={'pos':{'upos':['NOUN']},'depparse':{'deprel':['root','dep']}}
            def parse(self,obs):
                if obs.source.record_index==2:
                    return SimpleNamespace(sentences=[replace(sent(),status='failed',reason='parse_failed',tokens=())])
                if obs.text=='甲。乙':return SimpleNamespace(sentences=[sent(),sent()])
                return SimpleNamespace(sentences=[sent()])
        with patch('research.parser_error.evaluate.control_parse',side_effect=lambda p,r,t:r):
            result,private=evaluate(raw,selection,Fake())
        self.assertEqual(result['coverage']['selected_records'],64)
        self.assertEqual(result['coverage']['common_gate_records'],61)
        self.assertEqual(result['coverage']['boundary_mismatch_records'],1)
        self.assertEqual(result['coverage']['reference_failed_records'],1)
        self.assertEqual(result['coverage']['production_failed_source_units'],1)
        self.assertEqual(result['coverage']['excluded_reference_integer_rows'],9)
        self.assertEqual(len(private),64)

    def test_feature_unmatched_denominators_remain_different(self):
        g=sent();p=sent(parts=[(0,2),(2,3)],heads=(0,1),pos=('VERB','NOUN'),relations=('root','obj'))
        item={'reference':g,'production':p,'features':{'reference':features([g]),'production':features([p])}}
        result=channel_report([item],'production')
        self.assertEqual(result['zh:upos.NOUN']['reference_denominator_sum'],3)
        self.assertEqual(result['zh:upos.NOUN']['model_denominator_sum'],2)
        self.assertEqual(result['zh:word_length.mean']['mae'],0.5)
        self.assertEqual(result['zh:lexical.mattr100']['evidence_status'],'unvalidated_no_support')
        self.assertEqual(result['zh:cue.pronoun_first']['evidence_status'],'no_positive_event_evidence')

if __name__=='__main__':unittest.main()
