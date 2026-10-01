"""Experimental, review-gated structural edits with measured local consequences.

The only executable operation inserts a paragraph boundary at an existing
sentence boundary. It changes no non-whitespace code points. That invariant is
useful but does NOT prove preservation of implication, emphasis or discourse.
"""
from __future__ import annotations
from dataclasses import replace
import hashlib
import re
from .contracts import Document, text_hash
from .features import extract
from .segmentation import segment

PROTECTED_SEMANTICS = (
    "entities and identities", "numbers, units and ranges", "dates and sources",
    "quotations", "negation and quantifier scope", "conditions", "modality and uncertainty",
    "evidence strength", "causal versus temporal relations", "claim-evidence-objection structure",
    "author commitments and privacy",
)


def _nonwhitespace(text: str) -> str:
    return "".join(text.split())


def semantic_guard(before: str, after: str, protected_strings: tuple[str, ...] = ()) -> dict:
    missing = [s for s in protected_strings if before.count(s) != after.count(s)]
    same = _nonwhitespace(before) == _nonwhitespace(after)
    return {"mechanical_checks_pass": same and not missing,
            "nonwhitespace_sequence_identical": same,
            "protected_string_count_changes": missing,
            "semantic_equivalence": "unverified",
            "requires_semantic_review": True,
            "warning": "Lexical identity does not prove preserved discourse, scope, or meaning"}


def propose_paragraph_break(document: Document, *, max_sentences: int,
                            protected_strings: tuple[str, ...] = ()) -> dict:
    """Compile one explicit user's structural goal into a reviewable candidate.

    max_sentences is supplied by the caller, never inferred as a human/author
    norm. One small edit per proposal makes measurement and rollback auditable.
    Quotes/bracketed scope spanning the boundary trigger abstention.
    """
    if type(max_sentences) is not int or max_sentences < 1:
        raise ValueError("max_sentences must be a positive integer explicitly chosen for the task")
    if any(not s or s not in document.text for s in protected_strings):
        raise ValueError("Every protected string must be nonempty and present in the source")
    base = {"schema_version": "intervention-plan/1.0.0", "document_id": document.document_id,
            "source_sha256": text_hash(document.text), "evidence_status": "proposed",
            "goal_origin": "explicit_caller_constraint", "max_sentences": max_sentences,
            "author_profile": None, "expected_feature_changes": None,
            "protected_semantics": list(PROTECTED_SEMANTICS),
            "protected_strings": list(protected_strings), "risk": "paragraph boundaries can alter discourse emphasis",
            "dependencies": ["character-core/1.0.0"],
            "acceptance_checks": ["unchanged source hash", "exactly the declared insertion",
                                  "unchanged non-whitespace sequence", "protected strings unchanged",
                                  "human semantic and task-fit review"],
            "rollback_conditions": ["any changed protected content", "unsupported goal", "semantic review rejects change"]}
    paragraphs, sentences = segment(document.text)
    for paragraph in paragraphs:
        members = [s for s in sentences if s.paragraph_index == paragraph.index]
        if len(members) <= max_sentences:
            continue
        boundary = members[max_sentences - 1].end
        prefix = document.text[:boundary]
        # Deliberately conservative: unbalanced explicit pairs or odd ASCII
        # quotes may indicate a boundary inside an utterance/qualification.
        pairs = (("（", "）"), ("(", ")"), ("[", "]"), ("【", "】"),
                 ("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"))
        if any(prefix.count(a) != prefix.count(b) for a, b in pairs) or prefix.count('"') % 2:
            return base | {"status": "abstained", "reason": "Candidate boundary may be inside quotation or bracketed scope",
                           "candidate": None}
        if any(match.start() < boundary < match.start() + len(s)
               for s in protected_strings for match in re.finditer("(?=" + re.escape(s) + ")", document.text)):
            return base | {"status": "abstained", "reason": "Boundary intersects a protected string", "candidate": None}
        candidate = document.text[:boundary] + "\n" + document.text[boundary:]
        checks = semantic_guard(document.text, candidate, protected_strings)
        if not checks["mechanical_checks_pass"]:
            return base | {"status": "abstained", "reason": "Protected-content checks failed", "candidate": None}
        before = extract(document)
        after = extract(replace(document, text=candidate))
        deltas = {key: after["features"][key]["value"] - before["features"][key]["value"]
                  for key in before["features"]
                  if after["features"][key]["value"] is not None and before["features"][key]["value"] is not None}
        return base | {"status": "review_required", "reason": None,
                       "operation_id": "insert_paragraph_boundary/1.0.0",
                       "trigger_evidence": {"paragraph_index": paragraph.index,
                                            "observed_sentences": len(members), "requested_max": max_sentences},
                       "eligible_spans": [{"start": boundary, "end": boundary}],
                       "edit": {"offset": boundary, "insert": "\n"},
                       "candidate": candidate, "candidate_sha256": text_hash(candidate),
                       "measured_candidate_deltas": deltas,
                       "delta_interpretation": "Deterministic before/after measurement for this candidate, not a learned effect",
                       "checks": checks}
    return base | {"status": "no_change", "reason": "No paragraph exceeds the explicit sentence-count constraint", "candidate": None}


def apply_reviewed_plan(document: Document, plan: dict, *, semantic_review_approved: bool) -> str:
    """Apply only the exact reviewed candidate; refuse stale or altered plans."""
    if semantic_review_approved is not True:
        raise ValueError("Semantic/task-fit review is required; mechanical checks alone cannot approve an edit")
    if plan.get("status") != "review_required" or plan.get("operation_id") != "insert_paragraph_boundary/1.0.0":
        raise ValueError("No supported executable candidate")
    if plan.get("document_id") != document.document_id or plan.get("source_sha256") != text_hash(document.text):
        raise ValueError("Source changed or document mismatch; recompile and review")
    fresh = propose_paragraph_break(document, max_sentences=plan.get("max_sentences"),
                                    protected_strings=tuple(plan.get("protected_strings", [])))
    if fresh != plan:
        raise ValueError("Candidate changed after compilation; recompile and review the complete plan")
    edit = plan.get("edit", {})
    offset = edit.get("offset")
    if type(offset) is not int or not 0 < offset < len(document.text) or edit.get("insert") != "\n":
        raise ValueError("Invalid paragraph-boundary insertion")
    _, sentences = segment(document.text)
    if offset not in {s.end for s in sentences}:
        raise ValueError("Insertion is not at an observed sentence boundary")
    candidate = document.text[:offset] + "\n" + document.text[offset:]
    if plan.get("candidate") != candidate or plan.get("candidate_sha256") != text_hash(candidate):
        raise ValueError("Candidate changed after compilation")
    if not semantic_guard(document.text, candidate, tuple(plan.get("protected_strings", [])))["mechanical_checks_pass"]:
        raise ValueError("Protected-content checks failed")
    return candidate


def personalize(*args, **kwargs):
    raise NotImplementedError("Personalization is disabled; do not access personal style corpora before explicit final authorization")
