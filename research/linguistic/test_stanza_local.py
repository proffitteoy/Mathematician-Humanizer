"""Offline producer contract tests without requiring Stanza or downloaded weights."""
from dataclasses import replace
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from .fixtures import source,annotated,BASIC
from .stanza_local import LocalStanza,verify_models
from .contracts import MAX_SENTENCE_TOKENS

class StanzaProducer(unittest.TestCase):
    def parser(self,pipeline):
        obj=object.__new__(LocalStanza);obj.pipeline=pipeline
        obj.profile=annotated([BASIC])[2].profile;return obj
    def words(self,text):
        return NS(sentences=[NS(words=[NS(id=i+1,text=c,upos='PUNCT' if c=='。' else 'NOUN',
                  head=0 if i==0 else 1,deprel='root' if i==0 else ('punct' if c=='。' else 'conj'),
                  start_char=i,end_char=i+1,feats=None) for i,c in enumerate(text)])])
    def test_each_sentence_independent_input(self):
        calls=[]
        def pipeline(text):calls.append(text);return self.words(text)
        o=source('甲。\r\n乙。');a=self.parser(pipeline).parse(o)
        self.assertEqual(calls,['甲。','乙。']);self.assertEqual([s.start for s in a.sentences],[0,4])
    def test_normalization_alignment_abstains(self):
        def pipeline(text):
            result=self.words(text);result.sentences[0].words[0].text='另';return result
        a=self.parser(pipeline).parse(source('甲。'));self.assertEqual(a.sentences[0].reason,'alignment_failed')
    def test_unexpected_sentence_split_abstains(self):
        a=self.parser(lambda t:NS(sentences=[])).parse(source('甲。'))
        self.assertEqual(a.sentences[0].reason,'parse_failed')
    def test_runtime_failure_kept(self):
        def pipeline(t):raise RuntimeError('do not echo source text')
        a=self.parser(pipeline).parse(source('甲。'));self.assertEqual(a.sentences[0].status,'failed')
        self.assertNotIn('echo',str(a))
    def test_resource_guard_no_parser_call(self):
        def pipeline(t):raise AssertionError('must not be called')
        a=self.parser(pipeline).parse(source('字'*(MAX_SENTENCE_TOKENS+1)+'。'))
        self.assertEqual(a.sentences[0].reason,'resource_limit')
    def test_mwt_offsets_unavailable_abstains(self):
        def pipeline(text):
            d=self.words(text);d.sentences[0].words[0].start_char=None;return d
        a=self.parser(pipeline).parse(source('甲。'));self.assertEqual(a.sentences[0].reason,'alignment_failed')
    def test_missing_model_never_downloads(self):
        with self.assertRaisesRegex(ValueError,'local_model_hash_mismatch'):
            verify_models('/workspace/shared/intentionally-missing-model-directory')
    def test_supplementary_han_emoji_combining_exact(self):
        # Token POS merely fixture labels. This checks offsets, not segmentation
        # correctness of a real parser on combining sequences/emoji.
        o=source('𠀀🙂e\u0301。');a=self.parser(self.words).parse(o)
        self.assertEqual(a.sentences[0].status,'ok')
        self.assertEqual([t.start for t in a.sentences[0].tokens],list(range(5)))

if __name__=='__main__':unittest.main()
