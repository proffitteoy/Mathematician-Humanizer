"""Small deterministic CPU-only fixtures; all text is synthetic."""
import copy
import random
import unittest
from lxml import html
from native_adapter import (adapt_html, adapt_draftjs, measure, content_chars,
                            check_partition, punctuation_spans)


def view(markup):
    text = html.fromstring(markup).text_content()
    return text, adapt_html(markup, text)


def values(markup):
    text, v = view(markup)
    return measure(text, v)['features']


def draft(blocks, entities=None):
    b = [{'key': str(i), 'text': txt, 'type': typ, 'depth': depth, 'entityRanges': [], 'inlineStyleRanges': []}
         for i, (txt, typ, depth) in enumerate(blocks)]
    return {'blocks': b, 'entityMap': entities or {}}


class NativeTests(unittest.TestCase):
    def test_lossless_body_partition_includes_all_inline_gaps_and_repeated_text(self):
        text, v = view('<div>gap<p>同。<strong>同。</strong>同。</p>tail<p>同。</p>done</div>')
        self.assertEqual(''.join(u['text'] for u in v['units']), text)
        self.assertEqual(sum(u['end']-u['start'] for u in v['units']), len(text))
        self.assertEqual([text[p['start']:p['end']] for p in v['paragraphs']], ['同。同。同。','同。'])
        self.assertEqual(sum(u['end']-u['start'] for u in v['units'] if u['role']=='inline_gap'), 11)

    def test_noncontiguous_overlapping_or_changed_partition_rejected(self):
        text, v = view('<div><p>甲。</p><p>乙。</p></div>')
        for change in ('duplicate', 'gap', 'text'):
            u = copy.deepcopy(v['units'])
            if change == 'duplicate': u.append(u[-1])
            elif change == 'gap': u[0]['start'] += 1
            else: u[0]['text'] += '丙'
            with self.assertRaises(ValueError): check_partition(text, u)

    def test_saved_body_mismatch_rejected(self):
        with self.assertRaises(ValueError): adapt_html('<p>甲。</p>', '乙。')
        with self.assertRaises(ValueError): adapt_draftjs(draft([('甲。','unstyled',0)]), '乙。')

    def test_generic_wrapper_invariance_and_typed_quote_containment(self):
        a='<div><h2>題</h2><p>甲。乙？</p><blockquote><p>引用。</p></blockquote><p>丙。</p></div>'
        b='<section><div><h2><span>題</span></h2></div><div><p><span>甲。</span><em>乙？</em></p></div><div><blockquote><div><p><strong>引用。</strong></p></div></blockquote></div><div><p>丙。</p></div></section>'
        self.assertEqual(values(a), values(b))
        _, v = view(b)
        quote = [p for p in v['paragraphs'] if p['role']=='marked_quotation'][0]
        self.assertFalse(quote['eligible'])
        self.assertTrue(v['nodes'][quote['node_id']]['quoted_container_ids'])

    def test_line_wrap_and_whitespace_invariance_all_features(self):
        source='甲第一句。第二句有3.14單位！Third. A. U.S. 尾句？'
        baseline=values('<p>'+source+'</p>')
        for i in range(len(source)+1):
            self.assertEqual(baseline, values('<p>'+source[:i]+'\r\n'+source[i:]+'</p>'))
        self.assertEqual(baseline,values('<p>'+source.replace(' ','\r\n')+'</p>'))

    def test_native_boundaries_stay_distinct_without_newlines(self):
        a=values('<div><p>甲。</p><p>乙。</p></div>')
        b=values('<div><p>甲。乙。</p></div>')
        self.assertEqual(a['NP002']['raw_numerator'],2)
        self.assertEqual(b['NP002']['raw_numerator'],1)
        self.assertEqual(a['NP003']['value'],1)
        self.assertEqual(b['NP003']['value'],0)

    def test_role_sensitive_denominators(self):
        base='<div><p>甲。乙。</p><p>丙。</p></div>'
        rich='<div><h1>長長標題</h1><blockquote><p>引文引文。</p></blockquote><ul><li>項目。</li></ul><figure><figcaption>圖說。</figcaption></figure><pre>CODE</pre>unowned<p>甲。乙。</p><p>丙。</p></div>'
        self.assertEqual(values(base), values(rich))
        text, v = view(rich)
        result=measure(text,v)
        self.assertEqual(result['counts']['selected_LN'],3)
        self.assertGreater(result['counts']['excluded_LN'],0)
        self.assertEqual({u['role'] for u in v['units']}, {'heading','marked_quotation','list_item','caption','code_or_table','inline_gap','paragraph_mixed_attribution'})

    def test_no_paragraph_evidence_typed_missing_not_zero(self):
        for markup in ('<div>甲。乙。</div>', '<blockquote><p>甲。</p></blockquote>', '<p>！？</p>'):
            text,v=view(markup); result=measure(text,v)
            self.assertEqual(result['features']['NP002']['status'],'unavailable')
            self.assertIsNone(result['features']['NP003']['value'])
            self.assertEqual(result['counts']['eligible_paragraphs'],0)

    def test_semantic_hierarchy_not_fabricated(self):
        _,v=view('<div><h2>題</h2><ul><li>甲<ul><li>乙</li></ul></li></ul></div>')
        self.assertEqual([n['heading_level'] for n in v['nodes'] if n['heading_level']], [2])
        self.assertEqual([n['list_nesting_level'] for n in v['nodes'] if n['source_type']=='li'], [1,2])
        for key in ('rhetorical_hierarchy','argument_structure','quotation_attribution','semantic_paragraphs'):
            self.assertIsNone(v['unsupported'][key]['value'])

    def test_nested_list_no_double_count(self):
        text,v=view('<ul><li>外<ul><li>內</li></ul>尾</li></ul>')
        self.assertEqual(text,'外內尾')
        self.assertEqual(sum(len(u['text']) for u in v['units']),3)
        self.assertEqual([u['owner_id'] for u in v['units']], [1,3,1])

    def test_empty_nodes_and_zero_width_br_retained(self):
        text,v=view('<div><p></p><p>甲<br>乙。</p></div>')
        self.assertEqual(len(v['paragraphs']),2)
        self.assertEqual(len([p for p in v['paragraphs'] if p['eligible']]),1)
        self.assertEqual(v['inline_annotations'][0]['start'],v['inline_annotations'][0]['end'])
        self.assertEqual(text,'甲乙。')

    def test_draft_caption_not_injected_or_duplicated(self):
        s=draft([('甲。','unstyled',0),(' ','atomic',0),('','unstyled',0),('乙。','unstyled',0)],
          {'0': {'type':'image','data':{'desc':'圖說。','captionRichText':{'blocks':[{'text':'圖說。'}]}}}})
        s['blocks'][1]['entityRanges']=[{'key':0,'offset':0,'length':1}]
        text='甲。\n\n \n\n乙。'; v=adapt_draftjs(s,text)
        self.assertEqual(''.join(u['text'] for u in v['units']),text)
        self.assertEqual(len(v['nodes']),4)
        self.assertEqual(len(v['out_of_body_entity_text']),1)
        self.assertIsNone(v['out_of_body_entity_text'][0]['body_start'])
        self.assertEqual(measure(text,v)['counts']['selected_LN'],2)

    def test_utf16_ranges_converted_without_surrogate_splitting(self):
        s=draft([('甲😀乙。','unstyled',0)])
        s['blocks'][0]['inlineStyleRanges']=[{'offset':1,'length':2,'style':'BOLD'}]
        v=adapt_draftjs(s,'甲😀乙。')
        self.assertEqual((v['inline_annotations'][0]['start'],v['inline_annotations'][0]['end']),(1,2))
        s['blocks'][0]['inlineStyleRanges'][0]['length']=1
        with self.assertRaises(ValueError): adapt_draftjs(s,'甲😀乙。')

    def test_unknown_draft_types_not_silently_paragraphs(self):
        s=draft([('甲。','custom-thing',0),('乙。','unstyled',0),('項目','unordered-list-item',2)])
        text='甲。\n\n乙。\n\n項目';v=adapt_draftjs(s,text)
        self.assertEqual(measure(text,v)['counts']['eligible_paragraphs'],1)
        self.assertEqual(v['nodes'][0]['role'],'unknown_block')
        self.assertEqual(v['nodes'][2]['list_nesting_level'],2)
        self.assertIsNone(v['nodes'][2]['parent_relation']['value'])

    def test_html_draftjs_equivalence_on_matching_source_roles(self):
        markup='<div><h2>題</h2><p>甲。乙！</p><blockquote>引文。</blockquote><p>末句。</p></div>'
        s=draft([('題','header-two',0),('甲。乙！','unstyled',0),('引文。','blockquote',0),('末句。','unstyled',0)])
        text='\n\n'.join(b['text'] for b in s['blocks'])
        self.assertEqual(values(markup),measure(text,adapt_draftjs(s,text))['features'])

    def test_sentence_pairs_never_cross_paragraph_or_excluded_context(self):
        text,v=view('<div><p>甲。</p><blockquote>引文。</blockquote><p>乙。</p></div>')
        m=measure(text,v)
        self.assertEqual(m['counts']['within_paragraph_pairs'],0)
        self.assertIsNone(m['features']['NP024']['value'])

    def test_formula_hand_calculation(self):
        m=values('<div><p>甲。乙乙。</p><p>丙丙丙。</p></div>')
        self.assertAlmostEqual(m['NP002']['value'],1000*2/6)
        self.assertEqual(m['NP003']['value'],.5)
        self.assertEqual(m['NP013']['value'],2)
        self.assertEqual(m['NP014']['value'],1)
        self.assertEqual(m['NP015']['value'],2.8)
        self.assertEqual(m['NP016']['value'],.5)
        self.assertEqual(m['NP024']['value'],.5)
        self.assertIsNone(m['NP025']['value'])

    def test_mutated_native_view_rejected(self):
        text,v=view('<p>甲。</p>')
        v['paragraphs'][0]['content_chars']=999
        with self.assertRaises(ValueError): measure(text,v)

    def test_deterministic_wrapping_property(self):
        rng=random.Random(20261002)
        for _ in range(50):
            parts=[''.join(rng.choice('甲乙丙ABC123') for _ in range(rng.randint(1,20)))+rng.choice('。？！') for _ in range(5)]
            body=''.join(parts)
            marked='<div><p>'+body+'</p><p>尾。</p></div>'
            wrapped='<section><div><p>'+''.join('<span>'+x+'</span>\n' for x in parts)+'</p></div><p>尾。</p></section>'
            self.assertEqual(values(marked),values(wrapped))


if __name__=='__main__': unittest.main()
