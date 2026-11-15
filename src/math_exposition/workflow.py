"""Prepare evidence-bound tasks and keep mathematical and statistical audits separate."""
import hashlib
import json
from pathlib import Path

from math_reader.document import validate_document
from math_reader.graph import reconstruct, validate_evidence
from style_compiler.contracts import Context, Document, Leakage, Provenance, text_hash
from style_compiler.editorial import lint
from style_compiler.features import extract


def statistical_feedback(text, language="zh", genre="math_exposition", reader="unspecified",
                         research=None, reference_source=None):
    if language not in {"zh", "en"}:
        raise ValueError("Language must be zh or en")
    if reference_source not in {None, "baike", "web"}:
        raise ValueError("Chinese reference source must be explicitly baike or web")
    result = {"schema": "editorial-feedback/1", "text_sha256": text_hash(text),
              "language": language, "genre": genre, "reader": reader, "comparisons": [],
              "reference_source": reference_source,
              "quality_score": None,
              "limits": "Operational measurements locate review candidates; do not infer semantic paragraphs, missing conditions or prose quality"}
    if language == "en":
        result.update(status="unavailable", reason="Use style-compiler-english with pinned local models and its English contract; Chinese bands are not applicable")
        return result
    identity = text_hash(text)
    document = Document(identity, text, Context(language, genre, "unknown", "editorial_feedback"),
                        Provenance("unknown", identity, "caller-supplied draft", False, False),
                        Leakage(identity, identity, identity, identity))
    measured = extract(document)
    result.update(status="measured", measurement=measured)
    # Preserve exact locations for local review rather than inventing semantic diagnoses.
    lengths = [s["content_chars"] for s in measured["sentences"]]
    extremes = {min(lengths), max(lengths)} if lengths else set()
    result["review_locations"] = [s for s in measured["sentences"]
                                  if s["content_chars"] in extremes]
    result["reference_status"] = "not_selected"
    if research is not None and reference_source is not None:
        research = Path(research)
        manifest = json.loads((research / "manifest.json").read_text(encoding="utf-8"))
        raw = (research / "results.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["inputs"]["results.json"]["sha256"]:
            raise ValueError("Frozen research input changed: results.json")
        published = json.loads(raw)["chinese_surface"]
        dev = {r["feature_id"]: r for r in published["development_audit"]["features"]}
        for row in published["model"]["features"]:
            key = row["feature_id"]
            if not row["train_inspection_eligible"] or not dev[key]["inspection_supported"]:
                continue
            m = measured["features"][key]
            low, high = row["train_domains"][reference_source]["human_q10_q90"]
            result["comparisons"].append({"feature_id": key, "value": m["value"], "q10": low, "q90": high,
                "eligible": m["eligible_for_comparison"], "source": reference_source,
                "outside_descriptive_band": (not low <= m["value"] <= high) if m["eligible_for_comparison"] else None,
                "requires": "Read the located sentences in context; a mismatch is not a defect or an instruction to edit"})
        result["reference_status"] = "explicit_source_descriptive_only"
        result["reference_sha256"] = hashlib.sha256(raw).hexdigest()
    return result


def audit_exposition(document, annotations, baseline, candidate, language="zh", genre="math_exposition",
                     reader="unspecified", research=None, reference_source=None, review=None):
    graph = reconstruct(document, annotations)
    protected = lint(baseline.encode("utf-8"), candidate.encode("utf-8"))
    # Review receipts bind each assessment to an exact draft and unchanged source.
    accepted = False
    if review is not None:
        if review.get("candidate_sha256") != text_hash(candidate) or review.get("document_id") != document["document_id"]:
            raise ValueError("Mathematical review receipt does not belong to this draft/source")
        if review.get("reconstruction_sha256") != graph["reconstruction_sha256"]:
            raise ValueError("Mathematical review receipt is stale for this proof reconstruction")
        checks = review.get("checks", [])
        required = {"hypotheses", "dependencies", "mechanisms", "attribution", "scope"}
        if {c.get("id") for c in checks} != required or len(checks) != len(required):
            raise ValueError("Mathematical review needs five distinct content checks")
        sources = {d["document_id"]: d for d in [document, *annotations.get("external_sources", [])]}
        for check in checks:
            validate_evidence(check.get("evidence"), sources)
            start, end = check.get("start"), check.get("end")
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(candidate):
                raise ValueError("Mathematical review needs exact candidate spans")
            if candidate[start:end] != check.get("quote") or not str(check.get("reason", "")).strip():
                raise ValueError("Mathematical review must quote the checked draft and explain its assessment")
            if check.get("status") not in {"pass", "fail", "unresolved"}:
                raise ValueError("Unknown mathematical review status")
        accepted = all(c["status"] == "pass" for c in checks)
    mathematics = {"status": "review_recorded" if accepted else "review_required",
                   "graph_findings": graph["findings"], "review": review,
                   "mathematical_validity": "not_certified"}
    gate = accepted and not graph["findings"] and not protected["blockers"]
    return {"schema": "exposition-audit/1", "candidate_sha256": text_hash(candidate),
            "mathematics": mathematics, "content_protection": protected,
            "statistics": statistical_feedback(candidate, language, genre, reader, research, reference_source),
            "editorial_revision_allowed": gate,
            "next_action": "Inspect measurements and revise locally, then repeat both audits" if gate else "Resolve mathematical/source/protection findings before editorial revision",
            "limits": "A recorded model/human assessment is not independent mathematical certification"}


def prepare_stage(stage, document, annotations=None, reader="unspecified", known_nodes=None,
                  baseline=None, candidate=None, audit=None, research=None):
    from .prompts import PROMPTS, CONTROLLER, PROMPT_VERSION
    validate_document(document)
    if stage not in PROMPTS:
        raise ValueError("Unknown prompt stage: " + stage)
    result = {"schema": "mathematical-task/1", "prompt_version": PROMPT_VERSION,
              "stage": stage, "controller": CONTROLLER, "instruction": PROMPTS[stage],
              "document_id": document["document_id"], "reader": reader,
              "source_index": [{k: n[k] for k in ("id", "kind", "start", "end", "section")} for n in document["nodes"]],
              "sections": document["sections"],
              "source_warnings": document["warnings"],
              "source_access": "Re-read exact source spans; this index is not evidence of having read the full document"}
    if stage in {"structure", "proof"} and annotations is not None:
        if annotations.get("document_id") != document["document_id"]:
            raise ValueError("Starting annotations belong to another document")
        result["starting_annotations"] = annotations
    if stage in {"motivation", "literature", "exposition", "mathematical_audit", "editorial"}:
        if annotations is None:
            raise ValueError("This stage requires evidence-bound proof annotations")
        graph = reconstruct(document, annotations)
        known = set(known_nodes or [])
        if known - {n["id"] for n in graph["nodes"]}:
            raise ValueError("Reader knowledge refers to unknown nodes")
        if stage in {"exposition", "editorial"} and graph["findings"]:
            raise ValueError("Resolve proof/attribution findings before writing or polishing")
        result.update(reconstruction=graph,
                      explanation_order=[n for n in graph["prerequisite_order"] if n not in known],
                      known_nodes=sorted(known))
    if stage in {"mathematical_audit", "editorial"}:
        if candidate is None or baseline is None:
            raise ValueError("Audit and editorial tasks require the draft and its protected baseline")
        result.update(candidate=candidate, baseline=baseline)
    if stage == "editorial":
        if not isinstance(audit, dict) or audit.get("candidate_sha256") != text_hash(candidate):
            raise ValueError("Editorial task requires a current audit receipt")
        # Recompute gates rather than trusting a caller-supplied success boolean.
        supplied = audit.get("statistics", {})
        language, genre = supplied.get("language", "zh"), supplied.get("genre", "math_exposition")
        feedback_reader, refsource = supplied.get("reader", reader), supplied.get("reference_source")
        if refsource is not None and research is None:
            raise ValueError("Rechecking a selected reference requires the frozen research directory")
        checked = audit_exposition(document, annotations, baseline, candidate, language, genre,
                                   feedback_reader, research, refsource,
                                   review=audit.get("mathematics", {}).get("review"))
        if not checked["editorial_revision_allowed"]:
            raise ValueError("Mathematical audit has not cleared editorial revision")
        measured = checked["statistics"]
        if supplied != measured:
            raise ValueError("Statistics do not match the current draft")
        result["audit"] = checked
        result["measured_feedback"] = measured
    return result
