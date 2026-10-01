import copy
import hashlib
import unittest
from sample_metadata import allocate, QUOTAS, rank, member_key, freeze_components, wiki_member_key


def row(i, source="discussion", group=None):
    return {"record_key": str(i), "component_id": str(i) if group is None else group,
            "source_frame": source, "source_sha256": hashlib.sha256(str(i).encode()).hexdigest(),
            "projection_sha256": "a"*64, "projection_profile": "fixture/1",
            "preparse_eligible": True}


SMALL = {k: (2, 1, 1) for k in QUOTAS}


def fixture():
    return [row(f"{s}:{i}", s) for s in QUOTAS for i in range(6)]


class AllocationTests(unittest.TestCase):
    def test_quota_counts(self):
        result = allocate(fixture(), set(), SMALL)
        self.assertEqual(result["status"], "proposal_complete_not_admitted")
        self.assertEqual(len(result["selected_records"]), 12)
        for s in QUOTAS:
            for p, n in zip(("train", "development", "test"), SMALL[s]):
                self.assertEqual(sum(r["source_frame"] == s and r["partition"] == p
                                     for r in result["selected_records"]), n)
    def test_order_invariant(self):
        rows = fixture()
        self.assertEqual(allocate(rows, set(), SMALL), allocate(rows[::-1], set(), SMALL))
    def test_no_mutation(self):
        rows = fixture(); old = copy.deepcopy(rows)
        allocate(rows, set(), SMALL)
        self.assertEqual(rows, old)
    def test_exclude_full_group(self):
        rows = fixture() + [row("extra", "news_prose", "discussion:0")]
        out = allocate(rows, {"discussion:0"}, SMALL)
        self.assertNotIn("discussion:0", {r["component_id"] for r in out["selected_records"]})
    def test_cross_source_component_single_owner(self):
        rows = [row("a", "discussion", "shared"), row("b", "news_prose", "shared")]
        out = allocate(rows, set(), SMALL)
        self.assertEqual(len(out["selected_records"]), 1)
        expected = min(rows, key=lambda r: rank("representative", r["record_key"]))
        self.assertEqual(out["selected_records"][0]["record_key"], expected["record_key"])
    def test_underfill_not_cross_source_filled(self):
        out = allocate([row(i) for i in range(20)], set(), SMALL)
        self.assertEqual(out["status"], "underfilled_stop")
        self.assertEqual(len(out["selected_records"]), 4)
    def test_parser_fields_rejected(self):
        for name in ("text", "tokens", "target", "loss", "author_score"):
            r = row(1); r[name] = []
            with self.assertRaises(ValueError): allocate([r], set(), SMALL)
    def test_duplicate_record_rejected(self):
        with self.assertRaises(ValueError): allocate([row(1), row(1)], set(), SMALL)
    def test_hash_rejected(self):
        r = row(1); r["source_sha256"] = "bogus"
        with self.assertRaises(ValueError): allocate([r], set(), SMALL)
    def test_flag_not_truthiness(self):
        r = row(1); r["preparse_eligible"] = "false"
        with self.assertRaises(ValueError): allocate([r], set(), SMALL)
    def test_ineligible_preserved_count(self):
        r = row(1); r["preparse_eligible"] = False
        out = allocate([r], set(), SMALL)
        self.assertEqual(out["counts"]["preparse_ineligible"], 1)
        self.assertFalse(out["fit_authorized"])
    def test_no_source_relabel(self):
        r = row(1); r["source_frame"] = "academic"
        with self.assertRaises(ValueError): allocate([r], set(), SMALL)
    def test_exclusion_follows_member_when_component_hash_changes(self):
        old = member_key("wikiconv", "zhwiki", "page:7")
        new = member_key("wikinews", "zhwikinews", "page:8")
        before, excluded_before = freeze_components([old], [], [], {old})
        after, excluded_after = freeze_components([old, new], [(old, new)], [], {old})
        self.assertNotEqual(before[old], after[old])
        self.assertIn(after[new], excluded_after)
        self.assertNotIn(before[old], excluded_after)
    def test_same_integer_page_in_distinct_wikis_not_unioned(self):
        a = member_key("mediawiki", "zhwikinews", "7")
        b = member_key("mediawiki", "zhwikivoyage", "7")
        mapping, excluded = freeze_components([a, b], [], [], set())
        self.assertNotEqual(mapping[a], mapping[b])
        self.assertFalse(excluded)
    def test_specific_unresolved_edge_cannot_cross_splits(self):
        a = member_key("wikiconv", "zhwiki", "page:7")
        b = member_key("mediawiki", "zhwikinews", "page:8")
        mapping, _ = freeze_components([a, b], [], [(a, b)], set())
        self.assertEqual(mapping[a], mapping[b])
        out = allocate([row("a", group=mapping[a]), row("b", "news_prose", mapping[b])], set(), SMALL)
        self.assertEqual(len(out["selected_records"]), 1)
    def test_missing_excluded_ancestor_stops(self):
        with self.assertRaises(ValueError): freeze_components([], [], [], {member_key("x", "y", "z")})
    def test_generator_exclusion_equals_list_and_set(self):
        a, b = [wiki_member_key("wikiconv", "zhwiki", str(i)) for i in (1, 2)]
        expected = freeze_components([a, b], [(a, b)], [], {a})
        for exclusions in ([a], (x for x in [a])):
            self.assertEqual(expected, freeze_components([a, b], ((x, y) for x, y in [(a, b)]), iter([]), exclusions))
        self.assertEqual(len(expected[1]), 1)
    def test_order_invariant_multihop_exposure(self):
        a, b, c, d = [wiki_member_key("mediawiki", "zhwiki", str(i)) for i in range(4)]
        first = freeze_components([a, b, c, d], [(a,b),(b,c)], [(c,d)], {a})
        second = freeze_components([d,c,b,a], [(c,b),(b,a)], [(d,c)], [a])
        self.assertEqual(first, second)
        self.assertEqual(len(set(first[0].values())), 1)
        self.assertIn(first[0][d], first[1])
    def test_source_alias_registry_canonicalizes_same_page(self):
        keys = {wiki_member_key(alias, "zhwiki", "0007")
                for alias in ("wikiconv", "discussion", "mediawiki", "wikimedia")}
        self.assertEqual(keys, {wiki_member_key("wikimedia", "zhwiki", "7")})
        self.assertNotIn(wiki_member_key("mediawiki", "zhwikinews", "7"), keys)
    def test_unknown_alias_rejected(self):
        with self.assertRaises(ValueError): wiki_member_key("guessed", "zhwiki", "7")


if __name__ == "__main__": unittest.main()
