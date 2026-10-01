import unittest
from fingerprint import normalize,norm_hash,gram_hash,pack_ids,unpack_ids,wiki_member
class Tests(unittest.TestCase):
 def test_normalization(self): self.assertEqual(normalize('Ａ \nＢ'), 'AB')
 def test_full_and_gram_domains_differ(self): self.assertNotEqual(norm_hash('abcde'),gram_hash('abcde'))
 def test_id_roundtrip(self): self.assertEqual(unpack_ids(pack_ids([1000000,1,129,128,1])),[1,128,129,1000000])
 def test_empty_id_set(self): self.assertEqual(unpack_ids(pack_ids([])),[])
 def test_id_order_invariance(self): self.assertEqual(pack_ids([8,3,1]),pack_ids([1,8,3]))
 def test_invalid_id(self):
  with self.assertRaises(ValueError):pack_ids([0])
 def test_wiki_namespace(self): self.assertNotEqual(wiki_member('zhwiki','7'),wiki_member('zhwikinews','7'))
 def test_wiki_normalization(self): self.assertEqual(wiki_member('zhwiki','0007'),wiki_member('zhwiki','7'))
if __name__=='__main__':unittest.main()
