import unittest
from sampler import DSU, allocate,copy_edge,norm,rank,shingles,fulltext_copy_key,han_ln_fraction
class TestSampler(unittest.TestCase):
 def test_transitive_minimum_component(self):
  d=DSU(['3','2','1']);d.union('3','2');d.union('2','1');self.assertEqual({d.key(x) for x in ['1','2','3']},{'1'})
 def test_exposure_closure(self):
  d=DSU(['a','b','c']);d.union('a','b');s,g,e=allocate([{'id':'r','page_id':'b'},{'id':'q','page_id':'c'}],d,{'a'});self.assertEqual(len(s),1);self.assertEqual(s[0]['id'],'q')
 def test_one_record_per_group(self):
  d=DSU(['a']);s,*_=allocate([{'id':'x','page_id':'a'},{'id':'y','page_id':'a'}],d,set());self.assertEqual(len(s),1)
 def test_repeatable_order(self):
  rs=[{'id':str(i),'page_id':str(i)} for i in range(220)];d=DSU([r['page_id'] for r in rs]);a,*_=allocate(rs,d,set());b,*_=allocate(list(reversed(rs)),d,set());self.assertEqual(a,b);self.assertEqual(len(a),192);self.assertEqual([sum(r['partition']==p for r in a) for p in ['train','development','test']],[128,32,32])
 def test_underfill_not_replaced(self):
  d=DSU(['a']);s,*_=allocate([{'id':'x','page_id':'a'}],d,set());self.assertEqual(len(s),1)
 def test_nfkc_for_copy_only(self):self.assertEqual(norm('Ａ B\n'),'AB')
 def test_copy_containment_and_absolute_floor(self):
  self.assertTrue(copy_edge(set(range(50)),set(range(40))));self.assertFalse(copy_edge(set(range(50)),set(range(39))));self.assertFalse(copy_edge(set(range(100)),set(range(30,130))))
 def test_short_normalized_full_copy_key(self):
  a='甲。\n'*8+' '*200;b='甲。\n'*8+'\t'*200;self.assertEqual(fulltext_copy_key(a),fulltext_copy_key(b));self.assertIsNotNone(fulltext_copy_key(a));self.assertLess(len(norm(a)),200)
 def test_han_fraction_denominator_domain(self):
  test_script=lambda c,s:c in '⼀甲乙';self.assertEqual(han_ln_fraction('⼀⼀a',test_script),0);self.assertEqual(han_ln_fraction('甲a',test_script),.5);self.assertEqual(han_ln_fraction('⼀',test_script),0)
 def test_fivegrams(self):self.assertEqual(shingles('abcdef'),{'abcde','bcdef'});self.assertEqual(shingles('abc'),set())
if __name__=='__main__':unittest.main()
