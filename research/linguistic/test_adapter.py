"""Synthetic executable correctness/edge checks, never empirical validation."""
from dataclasses import replace,FrozenInstanceError
import json,math,unittest
from research.surface.adapter import Interval,make_projection
from .fixtures import annotated,BASIC,source,full
from .contracts import ParsedSource,ParserProfile,SentenceParse,Token
from .adapter import measure,_aggregate,vectors,lexical
from .schema import SENSORS,CHANNEL_IDS,POS,RELATIONS,CUES,schema_document

class Measurements(unittest.TestCase):
    def setUp(self):self.obs,self.proj,self.parsed=annotated([BASIC])
    def values(self,obs=None,proj=None,parsed=None):
        return measure(obs or self.obs,proj or self.proj,parsed or self.parsed)['target']['global_measurements']
    def test_count_actual_unique(self):
        self.assertEqual(len(SENSORS),71);self.assertEqual(len(set(CHANNEL_IDS)),71)
        self.assertEqual(len(self.values()),71)
    def test_basic_pos(self):
        r=self.values();self.assertAlmostEqual(r['zh:upos.PRON']['value'],1/3)
        self.assertEqual(r['zh:upos.ADJ']['value'],0)
        self.assertEqual(r['zh:upos.ADJ']['status'],'zero_observed')
        self.assertEqual(r['zh:upos.ADJ']['denominator'],3)
    def test_dependency_ratios(self):
        r=self.values();self.assertEqual(r['zh:deprel.nsubj']['value'],.5)
        self.assertEqual(r['zh:deprel.obj']['value'],.5)
        self.assertEqual(r['zh:dependency.span_mean']['value'],1)
        self.assertEqual(r['zh:dependency.span_normalized']['value'],.5)
        self.assertAlmostEqual(r['zh:dependency.depth_mean']['value'],2/3)
        self.assertEqual(r['zh:dependency.maxdepth_median']['value'],1)
    def test_predicate_no_zero_subject_claim(self):
        r=self.values();self.assertEqual(r['zh:syntax.predicate_heads']['value'],1)
        self.assertEqual(r['zh:syntax.verb_root_without_subject']['value'],0)
        self.assertEqual(r['zh:syntax.nominal_modifier_size']['value'],0)
    def test_absent_denom_missing(self):
        r=self.values();self.assertIsNone(r['zh:syntax.preposed_modifiers']['value'])
        self.assertEqual(r['zh:syntax.preposed_modifiers']['missing_reason'],'zero_denominator')
        self.assertEqual(r['zh:lexical.mattr100']['opportunities'],0)
    def test_subordinate_per100_sentence_units(self):
        o,p,a=annotated([[('想','VERB',0,'root'),('读','VERB',1,'xcomp'),('。','PUNCT',1,'punct')]])
        r=self.values(o,p,a)['zh:syntax.subordinate_arcs']
        self.assertEqual((r['value'],r['numerator'],r['denominator'],r['opportunities']),(100,100,1,1))
    def test_original_adjacent_overlap(self):
        o,p,a=annotated([BASIC,BASIC]);r=self.values(o,p,a)
        self.assertEqual(r['zh:lexical.content_overlap']['value'],1)
        self.assertEqual(r['zh:lexical.trigram_reuse']['value'],.5)
        self.assertEqual(r['zh:syntax.initial_pos_reuse']['value'],1)
        seq=measure(o,p,a)['target']['sequence']
        self.assertIsNone(seq[0]['measurements']['zh:lexical.content_overlap']['value'])
        self.assertEqual(seq[1]['measurements']['zh:lexical.trigram_reuse']['value'],1)
    def test_deleted_sentence_no_false_pair_or_history(self):
        o,p,a=annotated([BASIC,BASIC,BASIC]);s=a.sentences
        p=make_projection(o.source,(Interval(s[0].start,s[0].end),Interval(s[2].start,s[2].end)),annotation_profile='test',annotation_status='synthetic_fixture')
        r=measure(o,p,a)['target'];self.assertIsNone(r['global_measurements']['zh:lexical.content_overlap']['value'])
        self.assertEqual(r['global_measurements']['zh:lexical.trigram_reuse']['value'],0)
        self.assertFalse(any(e['relation']=='original_next_sentence' for e in r['graph']['edges']))
    def test_excluded_whitespace_blocks_pair(self):
        o,p,a=annotated([BASIC,BASIC]);s=a.sentences
        with self.assertRaises(ValueError):
            replace(p,targets=(Interval(s[0].start,s[0].end),Interval(s[1].start,s[1].end)),excluded_context=())
        p=make_projection(o.source,(Interval(s[0].start,s[0].end),Interval(s[1].start,s[1].end)),annotation_profile='test')
        self.assertIsNone(self.values(o,p,a)['zh:lexical.content_overlap']['value'])
    def test_touching_ranges_no_fake_gap(self):
        o,p,a=annotated([BASIC,BASIC]);p=make_projection(o.source,(Interval(0,2),Interval(2,len(o.text))),annotation_profile='test')
        self.assertEqual(self.values(o,p,a)['zh:lexical.content_overlap']['value'],1)
    def test_clipped_global_abstention(self):
        o,p,a=annotated([BASIC,BASIC]);p=make_projection(o.source,(Interval(1,len(o.text)),),annotation_profile='test')
        r=measure(o,p,a)['target'];self.assertTrue(all(x['missing_reason']=='ineligible_structure' for x in r['global_measurements'].values()))
        self.assertEqual(len(r['sequence']),1);self.assertTrue(r['sequence'][0]['subset_only_if_global_ineligible'])
    def test_failed_complete_sentence_abstains(self):
        s=replace(self.parsed.sentences[0],tokens=(),status='failed',reason='parse_failed')
        a=replace(self.parsed,sentences=(s,));r=self.values(parsed=a)
        self.assertTrue(all(x['value'] is None and x['missing_reason']=='parse_failed' for x in r.values()))
    def test_adjacent_overlap_recovers_after_older_failed_parse(self):
        o,p,a=annotated([BASIC,BASIC,BASIC]);s=a.sentences[0]
        a=replace(a,sentences=(replace(s,tokens=(),status='failed',reason='alignment_failed'),)+a.sentences[1:])
        rows=measure(o,p,a)['target']['sequence']
        self.assertEqual(rows[1]['measurements']['zh:lexical.content_overlap']['missing_reason'],'alignment_failed')
        self.assertEqual(rows[2]['measurements']['zh:lexical.content_overlap']['value'],1)
        self.assertEqual(rows[2]['measurements']['zh:lexical.trigram_reuse']['missing_reason'],'alignment_failed')
    def test_excluded_failed_sentence_not_in_target(self):
        o,p,a=annotated([BASIC,BASIC]);s=a.sentences[1]
        a=replace(a,sentences=(a.sentences[0],replace(s,tokens=(),status='failed',reason='parse_failed')))
        p=make_projection(o.source,(Interval(0,a.sentences[0].end),),annotation_profile='test')
        self.assertEqual(self.values(o,p,a)['zh:word_length.mean']['value'],1)
    def test_pos_only_keeps_pos_but_dep_null(self):
        s=self.parsed.sentences[0];s=replace(s,tokens=tuple(replace(t,head=None,deprel=None) for t in s.tokens),status='pos_only',reason='dependency_unavailable')
        r=self.values(parsed=replace(self.parsed,sentences=(s,)))
        self.assertEqual(r['zh:word_length.mean']['value'],1)
        self.assertEqual(r['zh:dependency.depth_mean']['missing_reason'],'dependency_unavailable')
    def test_cues_not_substrings_or_negation_scope(self):
        o,p,a=annotated([[('我们','PRON',2,'nsubj'),('没有','VERB',0,'root'),('不','ADV',2,'advmod'),('。','PUNCT',2,'punct')]])
        r=self.values(o,p,a);self.assertAlmostEqual(r['zh:cue.pronoun_first']['value'],1/3)
        self.assertAlmostEqual(r['zh:cue.negator']['value'],1/3)
    def test_de_sconj_supported(self):
        o,p,a=annotated([[('的','SCONJ',2,'mark:rel'),('话','NOUN',0,'root'),('。','PUNCT',2,'punct')]])
        self.assertEqual(self.values(o,p,a)['zh:cue.de_function_form']['value'],.5)
    def test_fixed_windows_correct(self):
        spec=[('字','NOUN',0 if i==0 else 1,'root' if i==0 else 'conj') for i in range(100)]+[('。','PUNCT',1,'punct')]
        o,p,a=annotated([spec]);r=self.values(o,p,a)
        self.assertEqual(r['zh:lexical.mattr100']['value'],.01)
        self.assertEqual(r['zh:lexical.entropy100']['value'],0)
        self.assertEqual(r['zh:upos.bigram_entropy100']['value'],0)
        self.assertEqual(r['zh:lexical.mattr100']['opportunities'],1)
    def test_no_windows_cross_projection_gap(self):
        spec=[('字','NOUN',0 if i==0 else 1,'root' if i==0 else 'conj') for i in range(50)]+[('。','PUNCT',1,'punct')]
        o,p,a=annotated([spec,spec]);self.assertEqual(self.values(o,p,a)['zh:lexical.mattr100']['opportunities'],1)
        p=make_projection(o.source,tuple(Interval(s.start,s.end) for s in a.sentences),annotation_profile='test')
        self.assertIsNone(self.values(o,p,a)['zh:lexical.mattr100']['value'])
    def test_categorical_sensor_positive_witnesses(self):
        # Each counted POS/dep/cue has a valid synthetic positive witness. These
        # are combinatorial program fixtures, not plausible Chinese treebank data.
        seen=set()
        for pos in POS:
            o,p,a=annotated([[('项',pos,0,'root'),('。','PUNCT',1,'punct')]])
            if self.values(o,p,a)['zh:upos.'+pos]['value']>0:seen.add('zh:upos.'+pos)
        for rel in RELATIONS:
            o,p,a=annotated([[('甲','NOUN',2,rel),('说','VERB',0,'root'),('。','PUNCT',2,'punct')]])
            if self.values(o,p,a)['zh:deprel.'+rel]['value']>0:seen.add('zh:deprel.'+rel)
        for name,(pos,forms) in CUES.items():
            pos=pos if type(pos)is str else pos[0]
            o,p,a=annotated([[(forms[0],pos,0,'root'),('。','PUNCT',1,'punct')]])
            if self.values(o,p,a)['zh:cue.'+name]['value']>0:seen.add('zh:cue.'+name)
        self.assertEqual(len(seen),50)
    def test_remaining21_numeric_sensors_have_positive_witness(self):
        spec=[('非常长的词','ADJ',3,'amod'),('AB12','PROPN',3,'nmod'),
              ('书','NOUN',4,'obj'),('读','VERB',0,'root'),('写','VERB',4,'conj'),
              ('说','VERB',4,'advcl')]
        spec += [(f'项{i}','NOUN',4,'obl') for i in range(94)]
        spec += [('。','PUNCT',4,'punct')]
        o,p,a=annotated([spec,spec]);r=self.values(o,p,a)
        numeric=[s.id for s in SENSORS if s.family not in {'upos_composition','dependency_composition','closed_class_cues'}]
        self.assertEqual(len(numeric),21)
        for key in numeric:
            with self.subTest(key=key):self.assertGreater(r[key]['value'],0)
    def test_latin_script_not_name_substring(self):
        for form in ('K','ª','º','A'):
            o,p,a=annotated([[(form,'NOUN',0,'root'),('。','PUNCT',1,'punct')]])
            self.assertEqual(self.values(o,p,a)['zh:word.latin']['value'],1)
        o,p,a=annotated([[('甲','NOUN',0,'root'),('。','PUNCT',1,'punct')]])
        self.assertEqual(self.values(o,p,a)['zh:word.latin']['value'],0)
    def test_han_script_includes_ideographic_zero(self):
        o,p,a=annotated([[('〇','NUM',0,'root'),('。','PUNCT',1,'punct')]])
        self.assertEqual(self.values(o,p,a)['zh:word.single_han']['value'],1)
    def test_failed_rows_keep_denominator_identity(self):
        s=replace(self.parsed.sentences[0],tokens=(),status='failed',reason='parse_failed')
        r=self.values(parsed=replace(self.parsed,sentences=(s,)))
        self.assertTrue(all('opportunity_type' in v for v in r.values()))
    def test_no_source_text_echo(self):
        output=json.dumps(measure(self.obs,self.proj,self.parsed),ensure_ascii=False)
        self.assertNotIn('我读书',output);self.assertNotIn('"form"',output)
    def test_graph_full_subtype_and_direction(self):
        o,p,a=annotated([[('书','NOUN',2,'nsubj:pass'),('读','VERB',0,'root'),('。','PUNCT',2,'punct')]])
        g=measure(o,p,a)['target']['graph'];edge=next(e for e in g['edges'] if e['relation']=='ud:nsubj:pass')
        self.assertEqual(g['nodes'][edge['source']]['source_span'],[1,2]);self.assertEqual(g['nodes'][edge['target']]['source_span'],[0,1])
    def test_empty_source(self):
        o=source('');a=replace(self.parsed,source=o.source,sentences=());r=self.values(o,full(o),a)
        self.assertTrue(all(x['value'] is None for x in r.values()))
    def test_prefix_local_row_suffix_invariance(self):
        o,p,a=annotated([BASIC,BASIC]);first=measure(o,p,a)['target']['sequence'][0]['vector']
        self.assertEqual(first,measure(self.obs,self.proj,self.parsed)['target']['sequence'][0]['vector'])

class Contracts(unittest.TestCase):
    setUp = Measurements.setUp
    values = Measurements.values
    def mutate_token(self,**changes):
        s=self.parsed.sentences[0];return replace(self.parsed,sentences=(replace(s,tokens=(replace(s.tokens[0],**changes),)+s.tokens[1:]),))
    def test_identity_full_locator(self):
        for key,val in [('view_index',1),('record_index',1),('record_byte_offset',1),('role','other')]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'exact_source_view'):
                measure(self.obs,self.proj,replace(self.parsed,source=replace(self.obs.source,**{key:val})))
    def test_identity_measurement_changes_annotation(self):
        a=self.mutate_token(upos='NOUN');r1=measure(self.obs,self.proj,self.parsed);r2=measure(self.obs,self.proj,a)
        self.assertEqual(r1['identity']['source_projection_join_key_sha256'],r2['identity']['source_projection_join_key_sha256'])
        self.assertNotEqual(r1['identity']['observation_key_sha256'],r2['identity']['observation_key_sha256'])
    def test_no_bool_ids(self):
        for key in ['local_id','head','start','end']:
            with self.subTest(key=key),self.assertRaises(ValueError):self.mutate_token(**{key:True}).validate(self.obs)
    def test_cycle_rejected(self):
        a=self.mutate_token(head=3)
        s=a.sentences[0];a=replace(a,sentences=(replace(s,tokens=s.tokens[:2]+(replace(s.tokens[2],head=1),)+s.tokens[3:]),))
        with self.assertRaisesRegex(ValueError,'cyclic'):a.validate(self.obs)
    def test_multiple_roots_rejected(self):
        with self.assertRaisesRegex(ValueError,'single_root'):self.mutate_token(head=0,deprel='root').validate(self.obs)
    def test_unsupported_pos_rejected(self):
        with self.assertRaises(ValueError):self.mutate_token(upos='N').validate(self.obs)
    def test_unsupported_rel_rejected(self):
        with self.assertRaises(ValueError):self.mutate_token(deprel='not_ud').validate(self.obs)
    def test_text_substitution_rejected(self):
        with self.assertRaisesRegex(ValueError,'alignment'):self.mutate_token(form='你').validate(self.obs)
    def test_offsets_not_normalized(self):
        with self.assertRaises(ValueError):self.mutate_token(start=1).validate(self.obs)
    def test_sentence_manifest_complete(self):
        with self.assertRaisesRegex(ValueError,'every_source'):replace(self.parsed,sentences=()).validate(self.obs)
    def test_mutable_nested_object_rejected(self):
        with self.assertRaises(ValueError):self.mutate_token(feats=[]).validate(self.obs)
    def test_profile_mismatch(self):
        with self.assertRaises(ValueError):replace(self.parsed,profile=replace(self.parsed.profile,normalization='NFC')).validate(self.obs)
    def test_source_unknown_ud_normalization(self):
        a=self.mutate_token(form='我\u0301',end=2)
        with self.assertRaises(ValueError):a.validate(self.obs)

if __name__=='__main__':unittest.main()
