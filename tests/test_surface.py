"""Original synthetic fixtures only: implementation tests, not corpus validation."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
import json
import math
import unittest

from style_compiler.contracts import Context, Document, Leakage, Provenance, text_hash
from style_compiler.features import PRIMARY_IDS, extract
from style_compiler.surface import (
    BUNDLE_VERSION, ContextRegion, Interval, MeasurementProfile, Projection,
    SourceObservation, SourceView, make_projection, measure,
)


def source(text: str, **changes) -> SourceObservation:
    fields = dict(
        archive_sha256=text_hash("original synthetic archive fixture"),
        member_name="synthetic-records.jsonl", record_index=0, record_byte_offset=0,
        scanner_version="synthetic-scanner/1.0.0", view_index=0,
        json_pointer="/text", role="synthetic-current", text_sha256=text_hash(text),
        text_codepoints=len(text),
    )
    return SourceObservation(SourceView(**(fields | changes)), text)


def project(observation: SourceObservation, *intervals: tuple[int, int]) -> Projection:
    return make_projection(observation.source, tuple(Interval(a, b) for a, b in intervals),
                           annotation_profile="original-synthetic-fixture/1.0.0",
                           annotation_status="synthetic_fixture")


def full(observation: SourceObservation) -> Projection:
    return project(observation, (0, len(observation.text))) if observation.text else project(observation)


def baseline(text: str) -> dict:
    return extract(Document(
        "synthetic-measurement-fixture", text,
        Context("zh", "synthetic_test", "synthetic_test", "synthetic_test"),
        Provenance("synthetic_test", "synthetic-source", "original synthetic fixture", True, True),
        Leakage("synthetic-work", "synthetic-lineage", "synthetic-content", "synthetic-duplicate"),
    ))


class ImmutableSourceTests(unittest.TestCase):
    def test_exact_text_hash_and_length_required(self):
        original = source("甲。\r\n乙🙂e\u0301。")
        for changed in (original.text.replace("\r\n", "\n"), original.text.replace("e\u0301", "é"),
                        original.text + " ", "错" + original.text[1:]):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "hash/length mismatch"):
                SourceObservation(original.source, changed)
        with self.assertRaisesRegex(ValueError, "hash/length mismatch"):
            SourceObservation(replace(original.source, text_codepoints=len(original.text) + 1), original.text)

    def test_same_text_does_not_authorize_another_view(self):
        obs = source("正文。"); projection = full(obs)
        changes = (
            {"archive_sha256": text_hash("another archive")}, {"member_name": "other.jsonl"},
            {"record_index": 1}, {"record_byte_offset": 2}, {"scanner_version": "other/2"},
            {"view_index": 1}, {"json_pointer": "/original/0/text"}, {"role": "original"},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "Exact source-view/version mismatch"):
                measure(source(obs.text, **change), projection)

    def test_changed_text_with_reused_locator_rejected(self):
        obs = source("提问？")
        with self.assertRaisesRegex(ValueError, "Exact source-view/version mismatch"):
            measure(source("明白。"), full(obs))

    def test_versions_fail_closed(self):
        obs = source("甲。")
        with self.assertRaises(ValueError):
            replace(obs.source, schema_version="immutable-source-view/0.2.0")
        with self.assertRaises(ValueError):
            replace(full(obs), schema_version="source-span-projection/0.2.0")
        for field, value in (
            ("version", "other/1"), ("segmenter_version", "punctuation-lines/2.0.0"),
            ("operational_feature_version", "character-core/2.0.0"),
            ("unicode_version", "0.0.0"), ("offset_unit", "utf16"),
            ("normalization", "NFC"), ("unit_policy", "resegment_chunks"),
            ("pair_policy", "concatenate"),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "profile/version mismatch"):
                replace(MeasurementProfile(), **{field: value})

    def test_strict_source_fields(self):
        obs = source("甲。")
        for field, value in (
            ("archive_sha256", "x"), ("text_sha256", "A" * 64),
            ("record_index", True), ("view_index", -1), ("record_byte_offset", 1.0),
            ("scanner_version", ""), ("role", " "), ("json_pointer", "text"),
            ("json_pointer", "/bad~2"), ("json_pointer", "/bad~"),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                replace(obs.source, **{field: value})
        self.assertEqual(replace(obs.source, json_pointer="").json_pointer, "")
        self.assertEqual(replace(obs.source, json_pointer="/a~1b/~0").json_pointer, "/a~1b/~0")

    def test_lone_surrogate_rejected_without_replacement(self):
        obs = source("甲")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            SourceObservation(obs.source, "\ud800")

    def test_immutable_input_and_no_result_aliasing(self):
        obs = source("正文。\n署名。\n补充。")
        projection = project(obs, (0, 3), (8, 11))
        before = deepcopy((asdict(obs), asdict(projection)))
        result = measure(obs, projection)
        result["projection"]["source"]["role"] = "tampered-output"
        result["projection"]["targets"][0]["start"] = 100
        self.assertEqual(before, (asdict(obs), asdict(projection)))
        for target, field, value in ((obs, "text", "different"), (obs.source, "role", "different"),
                                     (projection, "targets", ()), (projection.targets[0], "start", 2)):
            with self.assertRaises(FrozenInstanceError):
                setattr(target, field, value)


class IntervalContractTests(unittest.TestCase):
    def test_invalid_ranges_rejected(self):
        for a, b in ((0, 0), (2, 1), (-1, 2), (True, 2), (0, False), (0.0, 2), (0, "2")):
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                Interval(a, b)
        obs = source("甲乙丙丁")
        for ranges in (((0, 5),), ((2, 4), (0, 1)), ((0, 3), (2, 4)), ((0, 2), (0, 2))):
            with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                project(obs, *ranges)

    def test_mutable_nested_inputs_rejected(self):
        obs = source("甲。")
        with self.assertRaises(ValueError):
            make_projection(obs.source, [Interval(0, 2)], annotation_profile="test/1")
        with self.assertRaises(ValueError):
            ContextRegion(Interval(0, 2), ["signature"])
        with self.assertRaises(ValueError):
            replace(full(obs), excluded_context=[])
        with self.assertRaises(ValueError):
            measure(obs, full(obs), profile={})

    def test_context_complement_is_complete_and_separate(self):
        obs = source("甲。\n签名像一句话。\n乙。")
        start = obs.text.index("乙")
        projection = project(obs, (0, 2), (start, len(obs.text)))
        self.assertEqual(projection.excluded_context, (ContextRegion(Interval(2, start)),))
        self.assertEqual(obs.text[projection.excluded_context[0].interval.start:start], "\n签名像一句话。\n")
        labeled = replace(projection, excluded_context=(ContextRegion(Interval(2, start),
                                                                     ("signature_candidate", "sentence_shaped")),))
        result = measure(obs, labeled)
        self.assertEqual(result["projection"]["excluded_context"][0]["labels"],
                         ("signature_candidate", "sentence_shaped"))
        self.assertNotIn(obs.text, json.dumps(result, ensure_ascii=False))

    def test_missing_overlapping_or_target_overlapping_context_rejected(self):
        obs = source("甲乙丙丁")
        projection = project(obs, (0, 1))
        for regions in ((), (ContextRegion(Interval(2, 4)),),
                        (ContextRegion(Interval(0, 4)),),
                        (ContextRegion(Interval(1, 3)), ContextRegion(Interval(2, 4)))):
            with self.subTest(regions=regions), self.assertRaises(ValueError):
                replace(projection, excluded_context=regions)

    def test_context_labels_can_overlay_without_overlapping_ranges(self):
        obs = source("签名。")
        projection = project(obs)
        replacement = (ContextRegion(Interval(0, 3), ("signature_candidate", "quote_candidate")),)
        self.assertEqual(len(replace(projection, excluded_context=replacement).excluded_context), 1)
        for labels in ((), ("",), ("a", "a")):
            with self.assertRaises(ValueError):
                ContextRegion(Interval(0, 1), labels)

    def test_touching_intervals_preserve_real_adjacency(self):
        obs = source("甲。甲甲。甲甲甲。甲甲甲甲。")
        # Arbitrary annotation splits can fall inside units; their union is whole.
        split = project(obs, (0, 1), (1, 7), (7, len(obs.text)))
        first, second = measure(obs, full(obs)), measure(obs, split)
        self.assertEqual(first["target_component_text_sha256"], second["target_component_text_sha256"])
        self.assertNotEqual(first["projection_sha256"], second["projection_sha256"])
        self.assertEqual(first["target_projection"]["features"], second["target_projection"]["features"])
        self.assertEqual(second["target_projection"]["counts"]["target_connected_components"], 1)

    def test_empty_target_retains_all_context(self):
        obs = source("全部排除。")
        projection = project(obs)
        self.assertEqual(projection.excluded_context[0].interval, Interval(0, len(obs.text)))
        target = measure(obs, projection)["target_projection"]
        self.assertEqual(target["counts"]["target_codepoints"], 0)
        self.assertTrue(all(item["value"] is None for item in target["features"].values()))


class OperationalMeasurementTests(unittest.TestCase):
    def test_full_source_reuses_exact_eight_baseline_values(self):
        for text in ("", " \r\n🙂!?。", "甲。", "甲。甲甲。甲甲甲。甲甲甲甲。",
                     "  第一行。第二句！\r\n\r\n新的段落？还有一句。  ",
                     "The value is 3.14. Another value is 9.2.\nA. Smith waits."):
            with self.subTest(text=text):
                obs = source(text); actual = measure(obs, full(obs))
                expected = baseline(text)
                self.assertEqual(set(actual["target_projection"]["features"]), set(PRIMARY_IDS))
                for name in ("raw_source", "target_projection"):
                    for key in PRIMARY_IDS:
                        self.assertEqual(actual[name]["features"][key]["value"], expected["features"][key]["value"])
                        self.assertEqual(actual[name]["features"][key]["status"], expected["features"][key]["status"])
                self.assertEqual(actual["schema_version"], BUNDLE_VERSION)
                self.assertNotIn("feature_schema_version", actual)  # not a baseline model bundle
                json.dumps(actual, ensure_ascii=False, allow_nan=False)

    def test_known_arithmetic_and_denominators(self):
        obs = source("甲。甲甲。甲甲甲。甲甲甲甲。")
        result = measure(obs, full(obs))["target_projection"]
        features = result["features"]
        expected = {"F002": 100.0, "F003": 0.0, "F013": 2.5, "F014": 1.5,
                    "F015": 3.7, "F016": .4, "F024": .4, "F025": 1.0}
        for key, value in expected.items():
            self.assertAlmostEqual(features[key]["value"], value)
        self.assertEqual([features[key]["opportunity"]["observed_count"] for key in PRIMARY_IDS],
                         [10, 1, 4, 4, 4, 4, 3, 3])
        self.assertEqual(features["F024"]["raw_numerator"], 1)
        self.assertEqual(features["F024"]["denominator"], 2.5)
        self.assertEqual(result["pair_absolute_difference_sum"], 3)
        self.assertTrue(all(not item["eligible_for_comparison"] for item in features.values()))

    def test_gap_never_creates_sentence_or_pair(self):
        obs = source("甲。中间句。乙乙。")
        result = measure(obs, project(obs, (0, 2), (6, 9)))["target_projection"]
        self.assertEqual([s["index"] for s in result["sentences"]], [0, 2])
        self.assertEqual(result["adjacent_pairs"], [])
        self.assertEqual(result["features"]["F013"]["value"], 1.5)
        self.assertIsNone(result["features"]["F024"]["value"])
        self.assertEqual(result["features"]["F024"]["opportunity"]["observed_count"], 0)
        self.assertEqual(result["features"]["F002"]["missing_reason"], "partial_source_paragraphs")

    def test_excluded_whitespace_breaks_pair_even_with_complete_endpoints(self):
        obs = source("甲。\r\n乙乙。")
        target = measure(obs, project(obs, (0, 2), (4, 7)))["target_projection"]
        self.assertEqual(target["counts"]["source_pairs_with_complete_target_endpoints"], 1)
        self.assertEqual(target["counts"]["endpoint_complete_pairs_blocked_by_excluded_gap"], 1)
        self.assertEqual(target["adjacent_pairs"], [])
        self.assertEqual(target["features"]["F003"]["value"], 1)
        self.assertIsNone(target["features"]["F024"]["value"])
        whole = measure(obs, full(obs))["target_projection"]
        self.assertEqual(len(whole["adjacent_pairs"]), 1)

    def test_pairs_pool_within_components_only(self):
        # Components have lengths [1, 2] and [3, 4, 5], yielding three real pairs.
        text = "甲。甲甲。\n署名。\n甲甲甲。甲甲甲甲。甲甲甲甲甲。"
        obs = source(text); boundary = text.index("甲甲甲。")
        result = measure(obs, project(obs, (0, 5), (boundary, len(text))))["target_projection"]
        self.assertEqual(result["adjacent_pairs"], [
            {"left_source_sentence_index": 0, "right_source_sentence_index": 1},
            {"left_source_sentence_index": 3, "right_source_sentence_index": 4},
            {"left_source_sentence_index": 4, "right_source_sentence_index": 5},
        ])
        self.assertEqual(result["features"]["F024"]["opportunity"]["observed_count"], 3)
        self.assertAlmostEqual(result["features"]["F024"]["value"], 1 / 3)
        self.assertAlmostEqual(result["features"]["F025"]["value"], 1)

    def test_pair_statistics_do_not_flatten_components(self):
        first = "甲。" + "甲" * 10 + "。"
        second = "甲甲。甲甲甲。" + "甲" * 20 + "。"
        text = first + "\n署名。\n" + second
        obs = source(text)
        target = measure(obs, project(obs, (0, len(first)), (len(text) - len(second), len(text))))["target_projection"]
        self.assertEqual(target["features"]["F024"]["raw_numerator"], 9)
        self.assertEqual(target["features"]["F024"]["denominator"], 3)
        self.assertEqual(target["features"]["F024"]["value"], 3)
        self.assertAlmostEqual(target["features"]["F025"]["value"], .5)
        flattened = baseline(first + second)["features"]
        self.assertNotEqual(target["features"]["F024"]["value"], flattened["F024"]["value"])
        self.assertNotEqual(target["features"]["F025"]["value"], flattened["F025"]["value"])

    def test_counts_partition_source_and_pair_opportunities(self):
        text = "甲。\r\n乙乙。丙丙丙。\n丁丁丁丁。"
        obs = source(text)
        for projection in (full(obs), project(obs), project(obs, (0, 2), (4, 7), (11, len(text))),
                           project(obs, (1, len(text) - 1))):
            result = measure(obs, projection)
            for view in ("raw_source", "target_projection"):
                c = result[view]["counts"]
                self.assertEqual(c["source_codepoints"], c["target_codepoints"] + c["excluded_codepoints"])
                self.assertEqual(c["source_content_chars"], c["target_content_chars"] + c["excluded_content_chars"])
                self.assertEqual(c["source_adjacent_pairs"], c["eligible_adjacent_pairs"]
                                 + c["endpoint_complete_pairs_blocked_by_excluded_gap"]
                                 + c["source_pairs_without_complete_target_endpoints"])
                self.assertEqual(c["eligible_adjacent_pairs"], len(result[view]["adjacent_pairs"]))

    def test_combined_observation_key_binds_all_manifests(self):
        obs = source("甲。乙。")
        projection = project(obs, (0, 2))
        a = measure(obs, projection)
        b = measure(obs, replace(projection, annotation_profile="revised-synthetic-fixture/2.0.0"))
        self.assertEqual(a["source_view_sha256"], b["source_view_sha256"])
        self.assertEqual(a["measurement_profile_sha256"], b["measurement_profile_sha256"])
        self.assertNotEqual(a["projection_sha256"], b["projection_sha256"])
        self.assertNotEqual(a["observation_key_sha256"], b["observation_key_sha256"])
        self.assertEqual(a["target_component_text_sha256"], b["target_component_text_sha256"])

    def test_clipped_sentence_abstains_without_discarding_it(self):
        obs = source("完整。部分句。")
        result = measure(obs, project(obs, (0, 5)))["target_projection"]
        self.assertEqual(result["counts"]["complete_target_sentences"], 1)
        self.assertEqual(result["counts"]["clipped_target_sentences"], 1)
        self.assertEqual(result["features"]["F013"]["opportunity"]["observed_count"], 1)
        for key in PRIMARY_IDS:
            self.assertIsNone(result["features"][key]["value"])
            self.assertEqual(result["features"][key]["applicability"], "inapplicable_clipped_units")

    def test_removed_terminal_does_not_become_new_complete_fragment(self):
        obs = source("正文。")
        result = measure(obs, project(obs, (0, 2)))["target_projection"]
        self.assertEqual(result["counts"]["target_content_chars"], 2)
        self.assertEqual(result["counts"]["complete_target_sentences"], 0)
        self.assertEqual(result["counts"]["clipped_target_sentences"], 1)
        self.assertIsNone(result["features"]["F013"]["value"])

    def test_decimal_and_initial_guard_never_recomputed_at_cut(self):
        obs = source("3.14 is a number. A. Name waits.")
        start = obs.text.index("14")
        result = measure(obs, project(obs, (start, len(obs.text))))["target_projection"]
        self.assertEqual(result["counts"]["clipped_target_sentences"], 1)
        self.assertIsNone(result["features"]["F013"]["value"])

    def test_raw_and_target_distinct_with_prose_signature_and_following_body(self):
        text = "正文。\n签名里也有完整的句子。\n后续正文仍然保留。"
        obs = source(text); after = text.index("后续")
        result = measure(obs, project(obs, (0, 3), (after, len(text))))
        self.assertEqual(result["raw_source"]["counts"]["source_sentences"], 3)
        self.assertEqual(result["target_projection"]["counts"]["complete_target_sentences"], 2)
        self.assertNotEqual(result["raw_source"]["features"]["F013"]["value"],
                            result["target_projection"]["features"]["F013"]["value"])
        self.assertEqual(result["target_projection"]["sentences"][-1]["end"], len(text))

    def test_signature_attached_to_unterminated_body_remains_inapplicable(self):
        obs = source("正文未有句号 署名末尾")
        result = measure(obs, project(obs, (0, 6)))["target_projection"]
        self.assertEqual(result["counts"]["clipped_target_sentences"], 1)
        self.assertIsNone(result["features"]["F013"]["value"])

    def test_unicode_codepoints_crlf_and_no_normalization(self):
        text = "  甲🙂e\u0301９。\r\n\r\n乙𠀀。 "
        obs = source(text); result = measure(obs, full(obs))["target_projection"]
        self.assertEqual(result["counts"]["target_codepoints"], len(text))
        self.assertEqual(result["counts"]["target_content_chars"], 5)
        self.assertEqual([text[item["start"]:item["end"]] for item in result["sentences"]],
                         ["甲🙂e\u0301９。", "乙𠀀。"])
        self.assertEqual(len(result["paragraphs"]), 2)
        self.assertNotEqual(len(text), len(text.encode("utf-8")))
        self.assertNotEqual(len(text), len(text.encode("utf-16-le")) // 2)

    def test_quantile_support_and_undefined_correlation_are_not_fake_zero(self):
        obs = source("甲。甲。甲。甲。")
        features = measure(obs, full(obs))["target_projection"]["features"]
        self.assertEqual(features["F016"]["status"], "zero_observed")
        self.assertEqual(features["F024"]["status"], "zero_observed")
        self.assertIsNone(features["F025"]["value"])
        self.assertEqual(features["F025"]["missing_reason"], "constant_adjacent_rank_vector")
        short = source("甲。甲甲。甲甲甲。")
        feature = measure(short, full(short))["target_projection"]["features"]["F025"]
        self.assertEqual(feature["opportunity"]["observed_count"], 2)
        self.assertEqual(feature["missing_reason"], "fewer_than_three_source_contiguous_pairs")

    def test_projection_hash_covers_context_annotation_and_source(self):
        obs = source("甲。乙。")
        p = project(obs, (0, 2)); first = measure(obs, p)
        p2 = replace(p, excluded_context=(ContextRegion(Interval(2, 4), ("signature_candidate",)),))
        second = measure(obs, p2)
        self.assertNotEqual(first["projection_sha256"], second["projection_sha256"])
        self.assertEqual(first["target_component_text_sha256"], second["target_component_text_sha256"])
        self.assertEqual(first["target_projection"], second["target_projection"])

    def test_chunk_hash_preserves_gaps_and_is_not_a_source_identity(self):
        obs = source("甲X乙")
        separate = measure(obs, project(obs, (0, 1), (2, 3)))
        joined_obs = source("甲乙")
        joined = measure(joined_obs, full(joined_obs))
        self.assertNotEqual(separate["target_component_text_sha256"], joined["target_component_text_sha256"])
        # Equal content hash still cannot authorize a different source view.
        other = source("甲乙", role="synthetic-original")
        self.assertEqual(joined["target_component_text_sha256"], measure(other, full(other))["target_component_text_sha256"])
        self.assertNotEqual(joined["projection_sha256"], measure(other, full(other))["projection_sha256"])

    def test_deterministic_and_finite(self):
        obs = source("甲。甲甲。\n🙂\n甲甲甲。")
        self.assertEqual(measure(obs, full(obs)), measure(obs, full(obs)))
        result = measure(obs, full(obs))
        json.dumps(result, allow_nan=False)
        for view in ("raw_source", "target_projection"):
            for feature in result[view]["features"].values():
                for key in ("value", "raw_numerator", "denominator"):
                    self.assertTrue(feature[key] is None or math.isfinite(feature[key]))


class NestedBoundaryRevalidationTests(unittest.TestCase):
    def test_tampered_nested_source_version_rejected(self):
        obs = source("甲。乙。")
        projection = full(obs)
        object.__setattr__(obs.source, "schema_version", "unsupported/99")
        with self.assertRaisesRegex(ValueError, "source-view version"):
            measure(obs, projection)

    def test_tampered_nested_target_integer_rejected(self):
        obs = source("甲。乙。")
        projection = full(obs)
        object.__setattr__(projection.targets[0], "start", False)
        with self.assertRaisesRegex(ValueError, "start must be an integer"):
            measure(obs, projection)

    def test_tampered_nested_context_labels_rejected(self):
        obs = source("甲。乙。")
        projection = project(obs, (0, 2))
        object.__setattr__(projection.excluded_context[0], "labels", ())
        with self.assertRaisesRegex(ValueError, "nonempty immutable tuple"):
            measure(obs, projection)


if __name__ == "__main__":
    unittest.main()
