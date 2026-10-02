#!/usr/bin/env python3
import copy,json,unittest
import evaluate as ev

# Invented fixture, no corpus text: four distinct one-character sentences.
XML='<text id="fixture">甲。\n乙。\n\n丙。\n丁。</text>'.encode()
TOK='甲 。\n乙 。\n丙 。\n丁 。'
HEADER='<header><relations><rel name="joint-list" type="multinuc"/><rel name="joint-sequence" type="multinuc"/><rel name="elaboration-additional" type="rst"/></relations></header>'

def rs3(shape='balanced'):
 parents=({'1':'5','2':'5','3':'6','4':'6','5':'7','6':'7'} if shape=='balanced' else {'1':'7','2':'6','3':'5','4':'5','5':'6','6':'7'})
 body=''.join(f'<segment id="{i}" parent="{parents[str(i)]}" relname="joint-list">{s}</segment>' for i,s in enumerate(['甲。','乙。','丙。','丁。'],1))
 body+=''.join(f'<group id="{i}" type="multinuc"'+(f' parent="{parents[str(i)]}" relname="joint-list"' if i!=7 else '')+'/>' for i in [5,6,7])
 return f'<rst>{HEADER}<body>{body}</body></rst>'.encode()

class StructuralViews(unittest.TestCase):
 def setUp(self):
  self.l=ev.load_layout(XML,TOK);self.g=ev.read_graph(rs3());self.v=ev.view(self.l,self.g)
 def test_roundtrip_native_projection(self):
  r=ev.retention(self.v,rs3());self.assertTrue(all(r.values()));self.assertEqual(r['projected_vertex_recall'],1);self.assertEqual(r['projected_labelled_edge_recall'],1)
 def test_same_bag_same_histogram_different_hierarchy(self):
  v2=ev.view(self.l,ev.read_graph(rs3('right')))
  self.assertEqual(sorted(self.v['sentence_keys']),sorted(v2['sentence_keys']))
  a,b=ev.measure(self.v),ev.measure(v2)
  self.assertEqual(a['relation_counts'],b['relation_counts']);self.assertEqual(a['satellite_edge_fraction'],b['satellite_edge_fraction'])
  self.assertNotEqual(self.v['nodes'],v2['nodes']);self.assertNotEqual(a['native_max_edu_depth'],b['native_max_edu_depth'])
 def test_same_bag_changed_order_with_same_length_sequence(self):
  l=copy.deepcopy(self.l);l['sentence_keys'].reverse()
  self.assertEqual(sorted(l['sentence_keys']),sorted(self.l['sentence_keys']));self.assertEqual(l['sentences'],self.l['sentences']);self.assertNotEqual(l['sentence_keys'],self.l['sentence_keys'])
 def test_paragraph_boundary_changes_only_paragraph_layer(self):
  l=copy.deepcopy(self.l);l['paragraphs']=[[0,2],[2,8]];v=ev.view(l,self.g)
  self.assertEqual(v['nodes'],self.v['nodes']);self.assertEqual(v['sentence_keys'],self.v['sentence_keys']);self.assertNotEqual(v['paragraphs'],self.v['paragraphs'])
 def test_relation_label_is_retained_when_topology_same(self):
  g=copy.deepcopy(self.g)
  for k in ['1','2']:g['nodes'][k]['relation']='joint-sequence'
  v=ev.view(self.l,g);self.assertEqual(v['structure'],self.v['structure']);self.assertNotEqual(v['nodes'],self.v['nodes'])
  a,b=ev.signatures(self.g),ev.signatures(g)
  self.assertEqual(ev.f1(a['native_edge_span'],b['native_edge_span'])['f1'],1);self.assertLess(ev.f1(a['native_edge_full'],b['native_edge_full'])['f1'],1)
 def test_nuclearity_change_retained_with_topology_same(self):
  # A valid span group with one nucleus and one satellite replaces a two-nucleus group.
  g=copy.deepcopy(self.g);g['nodes']['5']['group_type']='span';g['nodes']['1']['relation']='span';g['nodes']['2']['relation']='elaboration-additional';v=ev.view(self.l,g)
  self.assertEqual(v['structure']['yields'],self.v['structure']['yields']);self.assertNotEqual(v['structure']['nuclearities'],self.v['structure']['nuclearities'])
 def test_segment_can_have_dependents(self):
  g=copy.deepcopy(self.g);g['nodes']['2']['parent']='1';g['nodes']['2']['relation']='elaboration-additional';e=ev.enrich(g)
  self.assertEqual(e['yields']['1'],[0,1]);self.assertEqual(len(e['paths']['2']),4)
 def test_discontinuous_yield_keeps_gap(self):
  g=copy.deepcopy(self.g);g['nodes']['2']['parent']='6';g['nodes']['3']['parent']='5';e=ev.enrich(g)
  self.assertEqual(e['yields']['5'],[0,2]);self.assertEqual(ev.merge_intervals([g['edu_spans'][i] for i in e['yields']['5']]),((0,2),(4,6)))
 def test_no_fuzzy_alignment(self):
  l=copy.deepcopy(self.l);l['text']=l['text'].replace('甲','戊')
  with self.assertRaisesRegex(AssertionError,'layout_edu_stream_mismatch'):ev.view(l,self.g)
 def test_missing_layers_are_null_not_zero(self):
  for layer in self.v['missing_layers'].values():self.assertIsNone(layer['value']);self.assertEqual(layer['reason'],'no_gold_layer')
 def test_duplicate_segmentation_boundary_scores(self):
  self.assertEqual(ev.boundary_scores('abcd',[[0,2],[2,4]],'abcd',[[0,1],[1,2],[2,4]])['f1'],2/3)
 def test_cycle_rejected(self):
  g=copy.deepcopy(self.g);g['nodes']['7']['parent']='1'
  with self.assertRaises(AssertionError):ev.enrich(g)

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(StructuralViews);result=unittest.TextTestRunner(verbosity=2).run(suite)
 (ev.HERE/'synthetic_results.json').write_text(json.dumps({'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'successful':result.wasSuccessful(),'note':'All examples invented; structural controls imply no perceptual quality judgement.'},indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful() else 1)
