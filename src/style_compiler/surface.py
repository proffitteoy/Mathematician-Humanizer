"""Measure unchanged source units under an explicit, gap-preserving projection.

No corpus access, inference of roles, normalization, fitting, or text rewriting.
Outputs contain source locators and offsets: keep real-data outputs private.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
import re
import statistics
import unicodedata

from style_compiler.contracts import FEATURE_VERSION, text_hash
from style_compiler.features import PRIMARY_IDS, quantile, ranks
from style_compiler.segmentation import SEGMENTER_VERSION, Span, content_chars, segment

SOURCE_VERSION = "immutable-source-view/0.1.0"
PROJECTION_VERSION = "source-span-projection/0.1.0"
PROFILE_VERSION = "source-units-gap-safe/0.1.0"
BUNDLE_VERSION = "research-surface-bundle/0.1.0"


def _nonempty(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _integer(value: object, name: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _sha256(value: object, name: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def _digest(value: object) -> str:
    return text_hash(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


@dataclass(frozen=True)
class SourceView:
    """Exact serialized view locator plus UTF-8 text hash; equality is not identity inference.

    record_index and view_index are zero-based. json_pointer is an exact RFC 6901
    pointer within the source record; the empty string denotes its root. The
    caller must verify these locators against the frozen source separately.
    """

    archive_sha256: str
    member_name: str
    record_index: int
    record_byte_offset: int
    scanner_version: str
    view_index: int
    json_pointer: str
    role: str
    text_sha256: str
    text_codepoints: int
    schema_version: str = SOURCE_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SOURCE_VERSION:
            raise ValueError("Unsupported source-view version")
        for name in ("archive_sha256", "text_sha256"):
            _sha256(getattr(self, name), name)
        for name in ("member_name", "scanner_version", "role"):
            _nonempty(getattr(self, name), name)
        for name in ("record_index", "record_byte_offset", "view_index", "text_codepoints"):
            _integer(getattr(self, name), name)
        if (not isinstance(self.json_pointer, str)
                or (self.json_pointer and not self.json_pointer.startswith("/"))
                or re.search(r"~(?:[^01]|$)", self.json_pointer)):
            raise ValueError("json_pointer must be an exact RFC 6901 pointer")


@dataclass(frozen=True)
class SourceObservation:
    source: SourceView
    text: str = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.source) is not SourceView or not isinstance(self.text, str):
            raise ValueError("SourceObservation requires SourceView and text")
        self.source.__post_init__()
        try:
            digest = text_hash(self.text)
        except UnicodeEncodeError as exc:
            raise ValueError("Source text must be encodable as UTF-8 without replacement") from exc
        if digest != self.source.text_sha256 or len(self.text) != self.source.text_codepoints:
            raise ValueError("Source text hash/length mismatch; no normalization or repair is permitted")


@dataclass(frozen=True)
class Interval:
    start: int
    end: int

    def __post_init__(self) -> None:
        _integer(self.start, "start")
        _integer(self.end, "end")
        if self.end <= self.start:
            raise ValueError("Intervals must be nonempty, half-open original-codepoint ranges")


@dataclass(frozen=True)
class ContextRegion:
    interval: Interval
    labels: tuple[str, ...] = ("unclassified_excluded",)

    def __post_init__(self) -> None:
        if type(self.interval) is not Interval or type(self.labels) is not tuple or not self.labels:
            raise ValueError("Context requires an Interval and nonempty immutable tuple of labels")
        self.interval.__post_init__()
        for label in self.labels:
            _nonempty(label, "context label")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("Duplicate context labels")


def _intervals(values: tuple[Interval, ...], length: int, name: str) -> None:
    if type(values) is not tuple:
        raise ValueError(f"{name} must be an immutable tuple")
    previous = 0
    for value in values:
        if type(value) is not Interval:
            raise ValueError(f"{name} must contain Interval values")
        value.__post_init__()
        if value.start < previous or value.end > length:
            raise ValueError(f"{name} must be sorted, disjoint, and inside the source")
        previous = value.end


def _components(intervals: tuple[Interval, ...]) -> tuple[Interval, ...]:
    """Touching intervals are one source-contiguous component, never a fake gap."""
    result: list[Interval] = []
    for interval in intervals:
        if result and result[-1].end == interval.start:
            result[-1] = Interval(result[-1].start, interval.end)
        else:
            result.append(interval)
    return tuple(result)


@dataclass(frozen=True)
class Projection:
    source: SourceView
    targets: tuple[Interval, ...]
    excluded_context: tuple[ContextRegion, ...]
    annotation_profile: str
    annotation_status: str = "provisional"
    schema_version: str = PROJECTION_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PROJECTION_VERSION:
            raise ValueError("Unsupported projection version")
        if type(self.source) is not SourceView:
            raise ValueError("Projection requires an immutable SourceView")
        self.source.__post_init__()
        _nonempty(self.annotation_profile, "annotation_profile")
        if self.annotation_status not in {"synthetic_fixture", "provisional", "reviewed"}:
            raise ValueError("Unknown annotation status; reviewed is a declaration, not certification")
        _intervals(self.targets, self.source.text_codepoints, "targets")
        if type(self.excluded_context) is not tuple or any(
                type(region) is not ContextRegion for region in self.excluded_context):
            raise ValueError("excluded_context must be an immutable tuple of ContextRegion values")
        for region in self.excluded_context:
            region.__post_init__()
        context = tuple(region.interval for region in self.excluded_context)
        _intervals(context, self.source.text_codepoints, "excluded_context")
        cursor = 0
        for interval in sorted(self.targets + context, key=lambda item: item.start):
            if interval.start != cursor:
                raise ValueError("Targets and visible excluded context must partition the entire source")
            cursor = interval.end
        if cursor != self.source.text_codepoints:
            raise ValueError("Targets and visible excluded context must partition the entire source")


@dataclass(frozen=True)
class MeasurementProfile:
    version: str = PROFILE_VERSION
    segmenter_version: str = SEGMENTER_VERSION
    operational_feature_version: str = FEATURE_VERSION
    unicode_version: str = unicodedata.unidata_version
    offset_unit: str = "unicode_codepoint"
    normalization: str = "none"
    unit_policy: str = "segment_full_source_then_select_complete_units"
    pair_policy: str = "original_consecutive_sentences_in_one_target_component"

    def __post_init__(self) -> None:
        supported = {
            "version": PROFILE_VERSION, "segmenter_version": SEGMENTER_VERSION,
            "operational_feature_version": FEATURE_VERSION,
            "unicode_version": unicodedata.unidata_version,
            "offset_unit": "unicode_codepoint", "normalization": "none",
            "unit_policy": "segment_full_source_then_select_complete_units",
            "pair_policy": "original_consecutive_sentences_in_one_target_component",
        }
        if asdict(self) != supported:
            raise ValueError("Measurement profile/version mismatch; no implicit migration")


def make_projection(source: SourceView, targets: tuple[Interval, ...], *,
                    annotation_profile: str, annotation_status: str = "provisional") -> Projection:
    """Retain every complement range as visible, unclassified excluded context.

    Use Projection directly to provide more specific reviewed context labels.
    This helper infers no signature, quotation, template, voice, or body boundary.
    """
    if type(source) is not SourceView:
        raise ValueError("Expected SourceView")
    _intervals(targets, source.text_codepoints, "targets")
    context: list[ContextRegion] = []
    cursor = 0
    for interval in targets:
        if cursor < interval.start:
            context.append(ContextRegion(Interval(cursor, interval.start)))
        cursor = interval.end
    if cursor < source.text_codepoints:
        context.append(ContextRegion(Interval(cursor, source.text_codepoints)))
    return Projection(source, targets, tuple(context), annotation_profile, annotation_status)


def _contained(start: int, end: int, components: tuple[Interval, ...]) -> bool:
    return any(part.start <= start and end <= part.end for part in components)


def _selected(units: list[Span], components: tuple[Interval, ...]) -> tuple[list[Span], list[Span]]:
    complete, partial = [], []
    for unit in units:
        if _contained(unit.start, unit.end, components):
            complete.append(unit)
        elif any(part.start < unit.end and unit.start < part.end for part in components):
            partial.append(unit)
    return complete, partial


def _measure(text: str, targets: tuple[Interval, ...], *, name: str) -> dict:
    # Segment only the unchanged source. Never concatenate/resegment target chunks.
    paragraphs, sentences = segment(text)
    components = _components(targets)
    ps, partial_ps = _selected(paragraphs, components)
    ss, partial_ss = _selected(sentences, components)
    selected_ids = {s.index for s in ss}
    pair_candidates = [(a, b) for a, b in zip(sentences, sentences[1:])
                       if a.index in selected_ids and b.index in selected_ids]
    pairs = [(a, b) for a, b in pair_candidates if _contained(a.start, b.end, components)]
    lengths = [float(s.content_chars) for s in ss]
    chars = sum(content_chars(text[part.start:part.end]) for part in targets)
    codepoints = sum(part.end - part.start for part in targets)
    p, n = len(ps), len(ss)
    med = statistics.median(lengths) if n else None
    mad = statistics.median(abs(length - med) for length in lengths) if n else None
    single = sum(sum(s.paragraph_index == paragraph.index for s in sentences) == 1 for paragraph in ps)
    difference_sum = sum(abs(b.content_chars - a.content_chars) for a, b in pairs)
    mean_difference = difference_sum / len(pairs) if pairs else None
    rho_numerator = rho_denominator = rho = None
    if len(pairs) >= 3:
        left = ranks(a.content_chars for a, _ in pairs)
        right = ranks(b.content_chars for _, b in pairs)
        lm, rm = statistics.mean(left), statistics.mean(right)
        rho_numerator = sum((a - lm) * (b - rm) for a, b in zip(left, right))
        rho_denominator = math.sqrt(sum((a - lm) ** 2 for a in left) * sum((b - rm) ** 2 for b in right))
        rho = rho_numerator / rho_denominator if rho_denominator else None

    features: dict[str, dict] = {}

    def add(identifier: str, value: float | None, unit: str, opportunity_unit: str,
            opportunity_count: int, partial_count: int, reason: str | None,
            numerator: float | None = None, denominator: float | None = None) -> None:
        if partial_count:
            value = numerator = denominator = None
            reason = "partial_source_paragraphs" if identifier in {"F002", "F003"} else "partial_source_sentences"
        features[identifier] = {
            "feature_id": identifier,
            "operational_feature_version": FEATURE_VERSION,
            "measurement_profile_version": PROFILE_VERSION,
            "value": value,
            "unit": unit,
            "status": "unavailable" if value is None else "zero_observed" if value == 0 else "observed",
            "applicability": "inapplicable_clipped_units" if partial_count else "applicable",
            "missing_reason": reason if value is None else None,
            "opportunity": {"unit": opportunity_unit, "observed_count": opportunity_count,
                            "completeness": "incomplete_clipped_units" if partial_count else "complete_for_declared_projection",
                            "clipped_unit_count": partial_count},
            "raw_numerator": numerator,
            "denominator": denominator,
            "eligible_for_comparison": False,
            "comparison_reason": "Research projection; no matched reference or validated support policy",
            "measurement_error_interval": None,
        }

    add("F002", 1000 * p / chars if chars else None, "paragraphs_per_1000_content_chars",
        "target_content_codepoints", chars, len(partial_ps), "no_content_characters", p, chars)
    add("F003", single / p if p else None, "share", "complete_source_paragraphs", p,
        len(partial_ps), "no_complete_paragraphs", single, p)
    add("F013", med, "content_chars", "complete_source_sentences", n,
        len(partial_ss), "no_complete_sentences")
    add("F014", quantile(lengths, .75) - quantile(lengths, .25) if n else None,
        "content_chars", "complete_source_sentences", n, len(partial_ss), "no_complete_sentences")
    add("F015", quantile(lengths, .9) if n else None, "content_chars",
        "complete_source_sentences", n, len(partial_ss), "no_complete_sentences")
    add("F016", mad / med if n else None, "ratio", "complete_source_sentences", n,
        len(partial_ss), "no_complete_sentences", mad, med)
    add("F024", mean_difference / med if pairs else None, "ratio",
        "source_contiguous_sentence_pairs", len(pairs), len(partial_ss),
        "no_source_contiguous_sentence_pairs", mean_difference, med)
    add("F025", rho, "spearman_rho", "source_contiguous_sentence_pairs", len(pairs), len(partial_ss),
        "fewer_than_three_source_contiguous_pairs" if len(pairs) < 3 else "constant_adjacent_rank_vector",
        rho_numerator, rho_denominator)
    assert tuple(features) == PRIMARY_IDS
    return {
        "observation_name": name,
        "counts": {
            "source_codepoints": len(text), "source_content_chars": content_chars(text),
            "target_codepoints": codepoints, "excluded_codepoints": len(text) - codepoints,
            "target_content_chars": chars, "excluded_content_chars": content_chars(text) - chars,
            "target_interval_count": len(targets),
            "target_connected_components": len(components),
            "source_paragraphs": len(paragraphs), "source_sentences": len(sentences),
            "complete_target_paragraphs": p, "clipped_target_paragraphs": len(partial_ps),
            "complete_target_sentences": n, "clipped_target_sentences": len(partial_ss),
            "source_adjacent_pairs": max(0, len(sentences) - 1),
            "source_pairs_with_complete_target_endpoints": len(pair_candidates),
            "eligible_adjacent_pairs": len(pairs),
            "endpoint_complete_pairs_blocked_by_excluded_gap": len(pair_candidates) - len(pairs),
            "source_pairs_without_complete_target_endpoints": max(0, len(sentences) - 1) - len(pair_candidates),
        },
        "paragraphs": [span.to_dict() for span in ps],
        "sentences": [span.to_dict() for span in ss],
        "clipped_paragraph_indices": [span.index for span in partial_ps],
        "clipped_sentence_indices": [span.index for span in partial_ss],
        "adjacent_pairs": [{"left_source_sentence_index": a.index, "right_source_sentence_index": b.index}
                           for a, b in pairs],
        "pair_absolute_difference_sum": difference_sum,
        "features": features,
    }


def measure(observation: SourceObservation, projection: Projection, *,
            profile: MeasurementProfile | None = None) -> dict:
    """Return separate raw-source and declared-target observations, never text.

    Exact SourceView equality is required, even when two views have equal text.
    This projection bundle keeps its own measurement profile. Do not merge its
    observations with another instrument solely because the source text matches.
    """
    if type(observation) is not SourceObservation or type(projection) is not Projection:
        raise ValueError("Expected immutable SourceObservation and Projection")
    if observation.source != projection.source:
        raise ValueError("Exact source-view/version mismatch, even if the text hash is equal")
    if profile is None:
        profile = MeasurementProfile()
    elif type(profile) is not MeasurementProfile:
        raise ValueError("Expected immutable MeasurementProfile")
    # Recheck at the boundary; no trusted state is inferred from a filename or ID.
    observation.__post_init__()
    projection.__post_init__()
    profile.__post_init__()
    source = observation.source
    source_payload = asdict(source)
    profile_payload = asdict(profile)
    projection_payload = asdict(projection)
    text = observation.text
    full = (Interval(0, len(text)),) if text else ()
    components = _components(projection.targets)
    chunks = [text[part.start:part.end] for part in components]
    return {
        "schema_version": BUNDLE_VERSION,
        "source": source_payload,
        "source_view_sha256": _digest(source_payload),
        "measurement_profile": profile_payload,
        "measurement_profile_sha256": _digest(profile_payload),
        "projection": projection_payload,
        "projection_sha256": _digest(projection_payload),
        "observation_key_sha256": _digest({"source": source_payload, "profile": profile_payload,
                                          "projection": projection_payload}),
        # JSON array framing distinguishes ["ab", "c"] from ["a", "bc"] and
        # ["a", "b"] from ["ab"]. It is not a hash of concatenated pseudo-text.
        "target_component_text_sha256": _digest(chunks),
        "target_hash_encoding": "sha256-of-canonical-utf8-json-array-of-source-contiguous-chunks",
        "raw_source": _measure(text, full, name="raw_source_all_input"),
        "target_projection": _measure(text, projection.targets, name="declared_target_source_units"),
        "reference_statistics": None,
        "warnings": [
            "Private research output: source locators, hashes and offsets are not a public aggregate",
            "Context labels and source locators are caller declarations; no role or historical event is inferred",
            "Complete units are defined by the original punctuation segmenter, not linguistic or voice boundaries",
            "Clipped units make the corresponding projection-wide measures inapplicable; they are not silently discarded",
            "Gap-restricted pairs describe selected source-text order, never historical conversation transitions",
            "No normalization, rendering, signature regex stripping, model fitting, authorship or human-style inference",
            "The original eight operational features remain eight; counts and metadata are not extra style channels",
        ],
    }
