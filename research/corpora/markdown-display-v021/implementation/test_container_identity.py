"""Source-free regression for distinct AST container identities."""
import unittest
import continuity_projection as p

class ContainerIdentityTests(unittest.TestCase):
    def texts(self,text):
        result=p.project_bytes(text.encode())
        p.validate_projection(text.encode(),result)
        return [s['text'] for s in result['segments']]
    def absent(self,text):
        self.assertFalse(any('注释残留' in x for x in self.texts(text)))

    def test_sibling_list_item_heading_does_not_reset(self):
        self.absent('- Caption\n\n  |a|b|\n  |---|---|\n  |x|y|\n\n- # Other item\n\n  注释残留\n\nRoot tail')
    def test_separate_list_heading_does_not_reset(self):
        self.absent('- Caption\n\n  |a|b|\n  |---|---|\n  |x|y|\n\nBetween lists\n\n- # Other list\n\n  注释残留')
    def test_separate_blockquote_heading_does_not_reset(self):
        self.absent('> |a|b|\n> |---|---|\n> |x|y|\n\n> # Other quote\n> quoted\n\n注释残留')
    def test_sibling_ordered_list_item_does_not_reset(self):
        self.absent('1. Caption\n\n   |a|b|\n   |---|---|\n   |x|y|\n\n2. # Other item\n\n   注释残留')
    def test_outer_heading_cannot_close_nested_table_scope(self):
        self.absent('- Caption\n\n  |a|b|\n  |---|---|\n  |x|y|\n\n# Root heading\n\n注释残留')
    def test_nested_heading_cannot_close_root_table_scope(self):
        self.absent('|a|b|\n|---|---|\n|x|y|\n\n- # Nested heading\n\n注释残留')
    def test_sibling_nested_item_does_not_reset(self):
        self.absent('- Outer\n  - Caption\n\n    |a|b|\n    |---|---|\n    |x|y|\n\n  - # Other inner item\n\n    注释残留')
    def test_same_list_item_heading_resets(self):
        self.assertEqual(self.texts('- Caption\n\n  |a|b|\n  |---|---|\n  |x|y|\n\n  # Same item\n\n  正文'),['正文'])
    def test_same_root_heading_resets(self):
        self.assertEqual(self.texts('|a|b|\n|---|---|\n|x|y|\n\nNote\n\n# Root heading\n\n正文'),['正文'])
    def test_same_blockquote_heading_resets(self):
        self.assertEqual(self.texts('> |a|b|\n> |---|---|\n> |x|y|\n>\n> # Same quote\n> quoted\n\n正文'),['正文'])

if __name__=='__main__':unittest.main(verbosity=2)
