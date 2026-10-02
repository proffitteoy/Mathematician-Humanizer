"""Offline, text-preserving human-publication intake; no fetching, splitting or fit.

Source bodies remain in an authorized local cache. Registry metadata is public.
Default policy admits documented human publications with assistance unknown.
The optional confirmed-unassisted population is a different research estimand.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath

REGISTRY_VERSION = "human-corpus-registry/1.0.0"
RECORD_VERSION = "human-corpus-record/1.0.0"
OPERATIONAL_POLICY = "operational-human-publication/1.0.0"
STRICT_POLICY = "confirmed-unassisted/1.0.0"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def checked_file(root, ref):
    """No traversal/symlink escape; verify bytes before interpreting content."""
    rel = PurePosixPath(ref["path"])
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError("Cache references must be safe relative paths")
    root = Path(root).resolve()
    path = (root / str(rel)).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Cache reference escapes authorized root")
    data = path.read_bytes()
    if len(data) != ref["bytes"] or sha256(data) != ref["sha256"]:
        raise ValueError("Cache hash/size mismatch: " + str(rel))
    return data


def validate_record(record):
    if record.get("schema_version") != RECORD_VERSION:
        raise ValueError("Unknown corpus record version")
    if record["admission"]["status"] != "admitted" or record["admission"]["cohort"] != "H_G":
        raise ValueError("Not an admitted general human record")
    if record["analysis_assignment"] != {"experiment_id": None, "split": None, "fit_authorized": False}:
        raise ValueError("Corpus intake cannot assign experimental splits or authorize fitting")
    evidence = record["human_origin_evidence"]
    if evidence["assessment"] != "supported_by_human_byline_and_publishing_source":
        raise ValueError("Human publication evidence required")
    if not evidence["byline_verified"] or not evidence["source_verified"] or not evidence["evidence_urls"]:
        raise ValueError("Incomplete byline/source evidence")
    if record["assistance_status"] not in {"unknown", "unassisted", "assisted"}:
        raise ValueError("Invalid assistance status")
    members = record["author_unit"]["members"]
    if not members or len({m["author_id"] for m in members}) != len(members):
        raise ValueError("Empty or duplicate author members")
    sole = record["author_unit"]["kind"] == "single_byline"
    if sole != (len(members) == 1) or record["admission"]["single_author_cohort_eligible"] != sole:
        raise ValueError("Single-author/coauthor mismatch")
    if not sole and record["author_unit"]["individual_author_id"] is not None:
        raise ValueError("Coauthored document cannot masquerade as an individual author")
    if sole and record["author_unit"]["individual_author_id"] != members[0]["author_id"]:
        raise ValueError("Incorrect individual author")
    rights = record["rights"]
    if not rights["evidence_reviewed"] or not rights["evidence_urls"] or rights["raw_text_publication_allowed"]:
        raise ValueError("Rights evidence and private-only text policy required")
    if not record["source"]["canonical_url"] or not record["genre"]:
        raise ValueError("Missing source or genre")
    for value in record["content"].values():
        if not isinstance(value, dict):
            continue
        if "sha256" in value and (len(value["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in value["sha256"])):
            raise ValueError("Invalid content hash")
    # Dates and historical snapshots are metadata, deliberately not gates.
    return record


def admission_reasons(record, *, policy=OPERATIONAL_POLICY, cohort="general_human"):
    validate_record(record)
    if policy not in {OPERATIONAL_POLICY, STRICT_POLICY}:
        raise ValueError("Unknown analysis population policy")
    if cohort not in {"general_human", "single_author"}:
        raise ValueError("Unknown analysis cohort")
    reasons = []
    if policy == STRICT_POLICY and record["assistance_status"] != "unassisted":
        reasons.append("Confirmed-unassisted estimand requires affirmative evidence of no assistance")
    if cohort == "single_author" and not record["admission"]["single_author_cohort_eligible"]:
        reasons.append("Coauthored work remains general-human evidence, not sole-author evidence")
    return reasons


def source_units(record, text, structure):
    """Exact source-text offsets, preserving order, inline text and unmapped gaps.

    A unit is a source structural block, never an assertion of one linguistic
    paragraph or one person's words. Gaps remain visible instead of being deleted.
    """
    if record["content"]["structure_format"] == "html_leaf_blocks/1.0.0":
        blocks = structure
        specs = [(i, block["text"], block["role"], {"source_tag": block["source_tag"]})
                 for i, block in enumerate(blocks)]
    elif record["content"]["structure_format"] == "draftjs/1.0.0":
        blocks = structure["blocks"]
        specs = []
        for i, block in enumerate(blocks):
            kind = block["type"]
            role = ("heading" if kind.startswith("header-") else
                    "marked_quotation" if kind == "blockquote" else
                    "atomic_entity" if kind == "atomic" else
                    "list_item" if "list-item" in kind else "paragraph_element_mixed")
            specs.append((i, block.get("text", ""), role,
                          {"source_key": block["key"], "source_type": kind,
                           "entity_ranges": block.get("entityRanges", []),
                           "inline_style_ranges": block.get("inlineStyleRanges", [])}))
    else:
        raise ValueError("Unsupported source structure")
    units = []
    cursor = 0
    for i, value, role, source in specs:
        if not value:
            # Empty native blocks are retained in the source structure sidecar.
            continue
        start = text.find(value, cursor)
        if start < 0:
            raise ValueError("Source block is absent, changed or out of order")
        if start > cursor:
            gap = text[cursor:start]
            units.append({"start": cursor, "end": start, "role": "source_separator" if not gap.strip() else "unmapped_source_text",
                          "source_block_index": None, "text": gap})
        end = start + len(value)
        units.append({"start": start, "end": end, "role": role,
                      "source_block_index": i, "text": value, **source})
        cursor = end
    if cursor < len(text):
        gap = text[cursor:]
        units.append({"start": cursor, "end": len(text), "role": "source_separator" if not gap.strip() else "unmapped_source_text",
                      "source_block_index": None, "text": gap})
    if "".join(unit["text"] for unit in units) != text:
        raise ValueError("Source view must reconstruct complete body text exactly")
    return units


def load_registry(registry_path):
    path = Path(registry_path)
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry["schema_version"] != REGISTRY_VERSION:
        raise ValueError("Unknown registry version")
    data = checked_file(path.parent, registry["catalog"])
    records = [validate_record(json.loads(line)) for line in data.decode("utf-8").splitlines() if line.strip()]
    for field in ("document_id",):
        if len({r[field] for r in records}) != len(records):
            raise ValueError("Duplicate document IDs")
    urls = [r["source"]["canonical_url"] for r in records]
    hashes = [r["content"]["body_text"]["sha256"] for r in records]
    if len(set(urls)) != len(urls) or len(set(hashes)) != len(hashes):
        raise ValueError("Duplicate canonical URLs or exact text bodies")
    counts = summarize(records)
    if counts != registry["counts"]:
        raise ValueError("Registry/catalog counts disagree")
    return registry, records


def summarize(records):
    sole = [r for r in records if r["admission"]["single_author_cohort_eligible"]]
    return {"general_human_documents": len(records), "single_author_documents": len(sole),
            "coauthored_general_human_documents": len(records) - len(sole),
            "repeated_named_author_trajectories": len({r["author_unit"]["individual_author_id"] for r in sole}),
            "by_source": dict(sorted(Counter(r["source"]["source_id"] for r in records).items())),
            "by_genre": dict(sorted(Counter(r["genre"] for r in records).items())),
            "assistance_status": dict(sorted(Counter(r["assistance_status"] for r in records).items()))}


def to_document(record, text, units):
    """Existing document/1.0.0 contract, with new evidence in its metadata slot."""
    return {"schema_version": "document/1.0.0", "document_id": record["document_id"], "text": text,
            "context": {"language": "zh-Hant-TW", "genre": record["genre"],
                        "topic": "|".join(record["topic_tags"]) or "unspecified", "task": "published_natural_prose"},
            "provenance": {"cohort": "H_G", "source_id": record["source"]["source_id"],
                           "rights_basis": record["rights"]["license_claim"] + "; private noncommercial research scope only",
                           "rights_verified": True, "is_synthetic": False,
                           "author_id": record["author_unit"]["individual_author_id"], "generator_id": None,
                           "provenance_verified": True, "assistance_status": record["assistance_status"],
                           "metadata": {"corpus_record": record, "source_units": units,
                                        "rights_verified_scope": "Observed article/site notices reviewed for bounded private research; no blanket clearance of all third-party spans or training uses",
                                        "provenance_verified_scope": "Named byline and source attribution, not unaided production or historical byte identity",
                                        "paragraph_contract": "Use ordered source_units; do not infer native paragraph count solely from text newlines",
                                        "legacy_physical_line_paragraph_features_supported": False,
                                        "clean_author_span_annotation": False}},
            "leakage": record["leakage"]}


def require_analysis_boundary(boundary_mode):
    if boundary_mode not in {"source_units", "full_text_character_only"}:
        raise ValueError("Use native source_units for structure; legacy physical-line paragraph extraction is unsupported")


def iter_feature_analysis_inputs(registry_path, source_root, *, policy=OPERATIONAL_POLICY, cohort="general_human", boundary_mode="source_units"):
    """47 general or 46 sole-byline inputs for this release; no hidden fit gate.

    Content-bearing results are private and are never emitted by the CLI.
    Known quotations/captions have structural roles; unmarked borrowed language
    remains unresolved. Individual-author intake is byline eligibility, not gold
    clean-author prose. Consumers must honor span/privacy and rights constraints.
    """
    require_analysis_boundary(boundary_mode)
    _, records = load_registry(registry_path)
    for record in records:
        if admission_reasons(record, policy=policy, cohort=cohort):
            continue
        for key in ("original_html", "body_html"):
            if key in record["content"]:
                checked_file(source_root, record["content"][key])
        text = checked_file(source_root, record["content"]["body_text"]).decode("utf-8")
        structure = json.loads(checked_file(source_root, record["content"]["structure"]).decode("utf-8"))
        units = source_units(record, text, structure)
        yield {"analysis_policy": policy, "analysis_cohort": cohort,
               "analysis_boundary_mode": boundary_mode,
               "document": to_document(record, text, units),
               "source_structure": structure, "source_units": units,
               "fit_authorized": False, "experiment_id": None, "split": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    _, records = load_registry(args.registry)
    report = {"metadata_validated": True, "counts": summarize(records)}
    if args.source_root:
        inputs = list(iter_feature_analysis_inputs(args.registry, args.source_root))
        report.update({"private_cache_validated": True, "feature_intake_records": len(inputs),
                       "source_body_codepoints": sum(len(x["document"]["text"]) for x in inputs),
                       "all_text_exactly_reconstructed": all("".join(u["text"] for u in x["source_units"]) == x["document"]["text"] for x in inputs)})
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
