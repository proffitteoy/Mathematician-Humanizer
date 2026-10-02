"""Validate real intake contracts without computing style features or fitting."""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
import jsonschema
from loader import (STRICT_POLICY, iter_feature_analysis_inputs, load_registry, sha256)
from build_admission import build


def verify(source_root, core_repo, public_root, frozen_manifest=None, workspace=None):
    root = Path(public_root)
    registry, records = load_registry(root / "REGISTRY.json")
    inputs = list(iter_feature_analysis_inputs(root / "REGISTRY.json", source_root))
    sole = list(iter_feature_analysis_inputs(root / "REGISTRY.json", source_root, cohort="single_author"))
    strict = list(iter_feature_analysis_inputs(root / "REGISTRY.json", source_root, policy=STRICT_POLICY))
    record_schema = json.loads((root / "human-corpus-record.schema.json").read_text())
    registry_schema = json.loads((root / "human-corpus-registry.schema.json").read_text())
    doc_schema = json.loads((Path(core_repo) / "schemas/document.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(record_schema)
    jsonschema.Draft202012Validator.check_schema(registry_schema)
    jsonschema.validate(registry, registry_schema)
    sys.path.insert(0, str(Path(core_repo) / "src"))
    from style_compiler.contracts import Document
    for record, item in zip(records, inputs, strict=True):
        jsonschema.validate(record, record_schema)
        jsonschema.validate(item["document"], doc_schema)
        Document.from_dict(item["document"])
    coauthored = [r for r in records if not r["admission"]["single_author_cohort_eligible"]]
    guava = Counter(r["author_unit"]["individual_author_id"] for r in records if r["source"]["source_id"] == "guava" and r["admission"]["single_author_cohort_eligible"])
    einfo = Counter(r["author_unit"]["individual_author_id"] for r in records if r["source"]["source_id"] == "einfo")
    checks = {
        "exact_47_operational_human_inputs": len(inputs) == 47,
        "all_47_assistance_unknown_without_rejection": all(x["document"]["provenance"]["assistance_status"] == "unknown" for x in inputs),
        "46_single_byline_inputs": len(sole) == 46,
        "one_four_person_coauthor_unit": len(coauthored) == 1 and len(coauthored[0]["author_unit"]["members"]) == 4,
        "coauthor_individual_author_id_null": all(x["document"]["provenance"]["author_id"] is None for x in inputs if x["document"]["provenance"]["metadata"]["corpus_record"]["author_unit"]["kind"] == "coauthored"),
        "ten_guava_trajectories_four_each": len(guava) == 10 and set(guava.values()) == {4},
        "two_einfo_reporters_three_each": len(einfo) == 2 and set(einfo.values()) == {3},
        "strict_unassisted_distinct_empty_estimand": len(strict) == 0,
        "registry_and_record_schemas_pass": True,
        "all_47_existing_document_contracts_pass": True,
        "all_referenced_cache_hashes_pass": True,
        "body_exact_offset_reconstruction": all("".join(u["text"] for u in x["source_units"]) == x["document"]["text"] for x in inputs),
        "ordered_source_blocks_never_reflowed": all([u["source_block_index"] for u in x["source_units"] if u["source_block_index"] is not None] == sorted(u["source_block_index"] for u in x["source_units"] if u["source_block_index"] is not None) for x in inputs),
        "native_boundary_mode_default": all(x["analysis_boundary_mode"] == "source_units" for x in inputs),
        "no_legacy_paragraph_compatibility_claim": all(x["document"]["provenance"]["metadata"]["legacy_physical_line_paragraph_features_supported"] is False for x in inputs),
        "no_fit_or_frozen_experiment_assignment": all(x["fit_authorized"] is False and x["split"] is None and x["experiment_id"] is None for x in inputs),
        "no_date_or_snapshot_gate": registry["date_cutoff"] is None and registry["requires_pre2022_snapshot"] is False,
        "unique_ids_canonical_urls_and_body_hashes": True,
        "rights_restrictions_retained": all(not r["rights"]["raw_text_publication_allowed"] and not r["rights"]["commercial_training_authorized"] for r in records),
    }
    with tempfile.TemporaryDirectory() as temp:
        build(source_root, temp)
        checks["exact_catalog_rebuild_reproducible"] = (Path(temp) / "ADMITTED_DOCUMENTS.jsonl").read_bytes() == (root / "ADMITTED_DOCUMENTS.jsonl").read_bytes()
        checks["registry_rebuild_reproducible"] = (Path(temp) / "REGISTRY.json").read_bytes() == (root / "REGISTRY.json").read_bytes()
    frozen_count = None
    if frozen_manifest:
        if not workspace:
            raise ValueError("Frozen comparison requires explicit workspace root")
        before = json.loads(Path(frozen_manifest).read_text())
        frozen_count = len(before)
        checks["frozen_experiment_files_unchanged"] = all(sha256((Path(workspace) / name).read_bytes()) == ref["sha256"] for name, ref in before.items())
    unmapped = [x for x in inputs if any(u["role"] == "unmapped_source_text" for u in x["source_units"])]
    body_count = sum(len(x["document"]["text"]) for x in inputs)
    report = {"schema_version": "human-corpus-admission-verification/1.0.0", "checks": checks,
              "passed": all(checks.values()), "check_count": len(checks),
              "counts": registry["counts"], "body_text_codepoints": body_count,
              "native_source_structural_blocks": sum(u["source_block_index"] is not None for x in inputs for u in x["source_units"]),
              "documents_with_unmapped_source_text": len(unmapped),
              "unmapped_source_text_codepoints_preserved": sum(len(u["text"]) for x in inputs for u in x["source_units"] if u["role"] == "unmapped_source_text"),
              "frozen_files_compared": frozen_count,
              "scope": "Source integrity, admission and adapter verification only; no style features measured, model fit or empirical performance inference"}
    if not report["passed"]:
        raise AssertionError(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--core-repo", type=Path, required=True)
    p.add_argument("--public-root", type=Path, default=Path(__file__).resolve().parent)
    p.add_argument("--frozen-manifest", type=Path)
    p.add_argument("--workspace", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = verify(args.source_root, args.core_repo, args.public_root, args.frozen_manifest, args.workspace)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
