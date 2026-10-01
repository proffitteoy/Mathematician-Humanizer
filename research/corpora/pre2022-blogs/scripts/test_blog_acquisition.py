"""Synthetic tests; contains no source-corpus examples or held-out material."""
import hashlib, unittest
from acquire_blog_texts import git_blob, tree_root_sha1
from census_blog_texts import canonical, code_structure, frontmatter, member, normalize, norm_hash, structural_row

class Contracts(unittest.TestCase):
    def test_blob(self):
        self.assertEqual(git_blob(b'test content\n'),'d670460b4b4aece5915caf5c68d12f560a9fe3e4')
    def test_canonical_member(self):
        self.assertEqual(member('owner/repo','_posts/a.md'),'["gitblog","owner/repo","post:_posts/a.md"]')
    def test_member_commit_independent(self):
        self.assertNotIn('commit',member('owner/repo','a.md'))
    def test_normalization(self):
        self.assertEqual(normalize('Ａ\t中\u3000文\n'),'A中文')
        self.assertEqual(norm_hash('Ａ\n'), hashlib.sha256(b'nfkc-no-ws/v1\0A').hexdigest())
    def test_nfkc_does_not_remove_punctuation(self):
        self.assertEqual(normalize('A, A.'),'A,A.')
    def test_frontmatter(self):
        raw, fields, unclosed = frontmatter('---\nauthor: Example\nlicense: separate\n---\nBody')
        self.assertEqual(fields,{'author':['Example'],'license':['separate']})
        self.assertFalse(unclosed)
    def test_frontmatter_no_yaml_execution(self):
        self.assertEqual(frontmatter('---\na: !!python/object:evil\n---\n')[1]['a'],['!!python/object:evil'])
    def test_frontmatter_unclosed(self):
        self.assertTrue(frontmatter('---\na: b')[2])
    def test_fences(self):
        x=code_structure('```py\nx=1\n```\nprose\n')
        self.assertEqual(x['fenced_block_markers'],1)
        self.assertFalse(x['unclosed_fence'])
    def test_fence_length(self):
        self.assertTrue(code_structure('````\nx\n```\n')['unclosed_fence'])
    def test_structural_flags_are_hints(self):
        x=structural_row('翻译\n转载\n禁止转载'.encode(),'_posts/2020-01-02-a.md')
        self.assertTrue(x['structural_flags']['translation_marker'])
        self.assertTrue(x['structural_flags']['license_exception_review_marker'])
        self.assertEqual(x['claimed_path_date'],'2020-01-02')
    def test_truncated_tree_rejected(self):
        with self.assertRaises(ValueError):tree_root_sha1({'truncated':True,'tree':[]})

if __name__ == '__main__':unittest.main()
