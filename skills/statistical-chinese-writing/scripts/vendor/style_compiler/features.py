"""Eight preregisterable character-level measurements; no fitted references.

These are operational character/segmentation measures, not validated constructs
of cognition, naturalness, quality, author identity, or model origin.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict
import math
import statistics
from typing import Iterable

from .contracts import BUNDLE_VERSION, FEATURE_VERSION, Document, Measurement, text_hash
from .segmentation import SEGMENTER_VERSION, content_chars, segment

PRIMARY_IDS = ("F002", "F003", "F013", "F014", "F015", "F016", "F024", "F025")
# Provisional engineering support gates, not empirically validated thresholds.
COMPARISON_SENTENCES = 10
COMPARISON_PARAGRAPHS = 5
COMPARISON_CHARS = 200


def quantile(values: list[float], q: float) -> float:
    """Linear interpolation between order statistics: h=(n-1)*q."""
    if not values or not 0 <= q <= 1:
        raise ValueError("Quantile needs nonempty observations and q in [0,1]")
    ordered = sorted(values)
    h = (len(ordered) - 1) * q
    lo, hi = math.floor(h), math.ceil(h)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (h - lo)


def ranks(values: Iterable[float]) -> list[float]:
    values = list(values)
    groups: dict[float, list[int]] = {}
    for i, value in enumerate(values):
        groups.setdefault(value, []).append(i)
    result = [0.0] * len(values)
    offset = 1
    for value in sorted(groups):
        indices = groups[value]
        rank = offset + (len(indices) - 1) / 2
        for i in indices:
            result[i] = rank
        offset += len(indices)
    return result


def lag1_spearman(values: list[float]) -> float | None:
    if len(values) < 4:
        return None
    left, right = ranks(values[:-1]), ranks(values[1:])
    lm, rm = statistics.mean(left), statistics.mean(right)
    numerator = sum((a - lm) * (b - rm) for a, b in zip(left, right))
    scale = math.sqrt(sum((a - lm) ** 2 for a in left) * sum((b - rm) ** 2 for b in right))
    return numerator / scale if scale else None


def _measurement(feature_id: str, value: float | None, unit: str, level: str,
                 count: int, eligible: bool, reason: str | None = None,
                 numerator: float | None = None, denominator: float | None = None) -> dict:
    return Measurement(
        feature_id=feature_id, value=value, unit=unit, level=level,
        eligible_count=count,
        status="unavailable" if value is None else "zero_observed" if value == 0 else "observed",
        null_reason=reason if value is None else None,
        eligible_for_comparison=eligible and value is not None,
        comparison_reason=None if eligible and value is not None else reason or "Below provisional comparison support gate",
        raw_numerator=numerator, denominator=denominator,
    ).to_dict() | {
        "schema_version": FEATURE_VERSION,
        "dependencies": [{"id": "segmenter", "version": SEGMENTER_VERSION, "hash": None}],
        "sequence_ref": "paragraphs" if level == "paragraph" else "sentences",
        "reference_id": None,
        "reference_percentile": None,
    }


def extract(document: Document) -> dict:
    text = document.text
    paragraphs, sentences = segment(text)
    lengths = [float(s.content_chars) for s in sentences]
    n, p, chars = len(sentences), len(paragraphs), content_chars(text)
    per_paragraph = Counter(s.paragraph_index for s in sentences)
    single = sum(count == 1 for count in per_paragraph.values())
    sentence_ok = n >= COMPARISON_SENTENCES and chars >= COMPARISON_CHARS
    paragraph_ok = p >= COMPARISON_PARAGRAPHS and chars >= COMPARISON_CHARS
    med = statistics.median(lengths) if n else None
    mad = statistics.median([abs(x - med) for x in lengths]) if n else None
    adjacent = [abs(b - a) for a, b in zip(lengths, lengths[1:])]
    rho = lag1_spearman(lengths)
    features = {
        "F002": _measurement("F002", 1000 * p / chars if chars else None,
                              "paragraphs_per_1000_content_chars", "paragraph", p, paragraph_ok,
                              "No content characters" if not chars else None, p, chars),
        "F003": _measurement("F003", single / p if p else None,
                              "share", "paragraph", p, paragraph_ok,
                              "No eligible paragraphs" if not p else None, single, p),
        "F013": _measurement("F013", med, "content_chars", "sentence", n, sentence_ok,
                              "No eligible sentences" if not n else None),
        "F014": _measurement("F014", quantile(lengths, .75) - quantile(lengths, .25) if n else None,
                              "content_chars", "sentence", n, sentence_ok,
                              "No eligible sentences" if not n else None),
        "F015": _measurement("F015", quantile(lengths, .9) if n else None,
                              "content_chars", "sentence", n, n >= 20 and chars >= COMPARISON_CHARS,
                              "No eligible sentences" if not n else None),
        "F016": _measurement("F016", mad / med if n else None,
                              "ratio", "sentence", n, sentence_ok,
                              "No eligible sentences" if not n else None, mad, med),
        "F024": _measurement("F024", statistics.mean(adjacent) / med if adjacent else None,
                              "ratio", "sentence", len(adjacent), len(adjacent) >= 19 and chars >= COMPARISON_CHARS,
                              "Fewer than two eligible sentences" if not adjacent else None),
        "F025": _measurement("F025", rho, "spearman_rho", "sentence", max(0, n-1), n >= 20 and chars >= COMPARISON_CHARS,
                              "Fewer than three adjacent pairs or constant adjacent rank vector" if rho is None else None),
    }
    optional = {
        "word_tokenization": "No frozen Chinese word tokenizer/model configured; characters are not words",
        "pos_dependency": "No versioned POS/dependency model configured or domain validation supplied",
        "embeddings": "No versioned embedding model configured; no vectors fabricated",
        "discourse_stance": "No validated annotation model or manual annotations supplied",
        "reference_distribution": "No eligible reference corpus fitted",
        "personalization": "Disabled until explicit final-personalization authorization and a separate implementation",
    }
    return {
        "schema_version": BUNDLE_VERSION,
        "feature_schema_version": FEATURE_VERSION,
        "document_id": document.document_id,
        "text_sha256": text_hash(text),
        "context": asdict(document.context),
        "provenance": asdict(document.provenance),
        "leakage": asdict(document.leakage),
        "counts": {"content_chars": chars, "sentences": n, "paragraphs": p},
        "segmentation": {"version": SEGMENTER_VERSION,
                         "offset_unit": "unicode_codepoint",
                         "paragraph_rule": "each nonempty physical line",
                         "sentence_rule": "punctuation-based; not a linguistic sentence annotation",
                         "normalization": "none",
                         "projection": "all_input_unicode_LN/1.0.0",
                         "authorial_prose_attribution": "unavailable; all input is measured"},
        "paragraphs": [s.to_dict() | {"sentence_count": per_paragraph[s.index]} for s in paragraphs],
        "sentences": [s.to_dict() for s in sentences],
        "features": features,
        "optional_capabilities": {key: {"status": "unavailable", "value": None, "reason": reason}
                                  for key, reason in optional.items()},
        "reference_statistics": None,
        "warnings": [
            "Character-based operational measures; construct validity remains untested",
            "Sentence-boundary errors are possible for abbreviations, quotations, headings, lists, and mixed languages",
            "Provisional support gates are engineering policy, not validated sample-size requirements",
            "No author inference, human probability, quality score, or calibrated percentile is produced",
        ],
    }
