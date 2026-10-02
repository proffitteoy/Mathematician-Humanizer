"""Build metadata-only admission from the preserved, previously reviewed cache.

This reads local catalogs and bodies, never downloads or fits. Reacquisition is
separate and must honor source restrictions; changed bytes require a new version.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit
from loader import RECORD_VERSION, REGISTRY_VERSION, OPERATIONAL_POLICY, STRICT_POLICY, sha256, read_jsonl, summarize, validate_record

SOURCE_COMMIT = "e1119c802ac0c6e42a8e2a0c243ed6b9e3598027"
RELEASE = "human-publications-20261002.1"
PACKAGE_REPO_PATH = "research/corpora/human-admission-20261002/public"
APPROVED_CATALOGS = {
    "ARTICLE_CATALOG.jsonl": "7dede27001f502b3a1d7baf11a5defbcd7139413a9cbbb972b9e6267b3c89d44",
    "EINFO_ARTICLE_CATALOG.jsonl": "a9e0b86be4b143a2ac6de43d2fb5cd0546044b8f61af34332b139f0dfd260c9c",
}


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_ref(root, path):
    data = (root / path).read_bytes()
    return {"path": path, "bytes": len(data), "sha256": sha256(data)}


def canonical_url(url):
    p = urlsplit(url)
    return "https://" + p.netloc.lower() + p.path.replace("/index.php/", "/").rstrip("/")


def author_id(source, name):
    return source + ":person:" + sha256(name.encode("utf-8"))[:20]


def verify_reviewed_catalogs(source_root):
    for name, digest in APPROVED_CATALOGS.items():
        if sha256((Path(source_root) / "public" / name).read_bytes()) != digest:
            raise ValueError("Catalog changed since exact-47 review; create a separately reviewed release")


def build(source_root, output):
    source_root, output = Path(source_root), Path(output)
    verify_reviewed_catalogs(source_root)
    output.mkdir(parents=True, exist_ok=True)
    original_catalogs = ["ARTICLE_CATALOG.jsonl", "EINFO_ARTICLE_CATALOG.jsonl"]
    catalogs = [r for name in original_catalogs for r in read_jsonl(source_root / "public" / name)]
    if len(catalogs) != 47 or len({canonical_url(r['url']) for r in catalogs}) != 47:
        raise ValueError("This reviewed release requires exactly 47 unique works")
    receipts = {r["url"]: r for r in read_jsonl(source_root / "public/REQUEST_RECEIPTS.jsonl") if r["status"] == 200}
    metadata = {r["url"]: r for r in json.loads((source_root / "private/structural_receipts.json").read_text())}
    metadata.update({r["url"]: r for r in read_jsonl(source_root / "private/einfo_document_receipts.jsonl")})
    records = []
    for row in catalogs:
        source = row["source_id"]
        item = row["url"].rsplit("/", 1)[-1]
        did = "human-publication:" + source + ":" + item
        coauthored = source == "guava" and row.get("sole_author_eligible") is False
        names = row["article_byline"][0].split("、") if coauthored else row["article_byline"]
        if coauthored and (item != "6907" or names != ["蔡侑霖", "傅偉哲", "鄧家洋", "莊雅仲"]):
            raise ValueError("Unexpected coauthor attribution needs review")
        members = [{"author_id": author_id(source, name), "name": name,
                    "role": "reporter" if source == "einfo" else "coauthor" if coauthored else "author",
                    "identity_url": row["author_url"] if name == row["author"] else None,
                    "identity_evidence": "repeated byline and author profile" if name == row["author"] else "named article byline only; no separate trajectory established"}
                   for name in names]
        original = receipts[row["url"]]
        private = metadata[row["url"]]
        key = sha256(row["url"].encode())[:20]
        body_path = f"private/text/{key}.body-text.txt"
        structure_path = f"private/text/{key}.blocks.json" if source == "guava" else private["draftjs_path"]
        content = {"original_html": file_ref(source_root, original["private_path"]),
                   "body_text": file_ref(source_root, body_path),
                   "structure": file_ref(source_root, structure_path),
                   "structure_format": "html_leaf_blocks/1.0.0" if source == "guava" else "draftjs/1.0.0",
                   "body_text_representation": "exact HTML body text_content" if source == "guava" else "source nonempty DraftJS text fields joined by two LF; whitespace-only atomic blocks preserved"}
        if source == "guava":
            content["body_html"] = file_ref(source_root, private["body_html_path"])
        if content["original_html"]["sha256"] != row["original_html_sha256"] or content["original_html"]["sha256"] != original["sha256"]:
            raise ValueError("Source response lineage mismatch")
        if content["body_text"]["sha256"] != private["body_text_sha256"]:
            raise ValueError("Preserved complete body checksum mismatch")
        restrictions = ["Attribution required", "Noncommercial scope only", "No-derivatives restriction retained",
                        "No source prose or private sample export to the public repository",
                        "Third-party quotations and images retain separate rights",
                        "No commercial training or new redistribution permission inferred from corpus admission"]
        if source == "guava":
            rights_urls = [row["url"], "https://creativecommons.org/licenses/by-nc-nd/3.0/tw/", "https://guavanthropology.tw/robots.txt"]
        else:
            rights_urls = [row["url"], "https://e-info.org.tw/copyright", "https://tnf.org.tw/faq", "https://e-info.org.tw/robots.txt"]
        known_group = row.get("dedup_group", did)
        # Conservative known series grouping; no claim of completed cross-corpus dedup.
        series_group = "guava:pan-meiling:tibet-india-fieldwork-series" if row["author"] == "潘美玲" else known_group
        r = {"schema_version": RECORD_VERSION, "release_id": RELEASE, "document_id": did,
             "title": row["title"],
             "admission": {"status": "admitted", "cohort": "H_G", "population_policy": OPERATIONAL_POLICY,
                           "single_author_cohort_eligible": not coauthored,
                           "decision_basis": "Explicit human-corpus admission clarification; identified human byline and publishing-source evidence",
                           "date_cutoff_required": False, "historical_snapshot_required": False},
             "source": {"source_id": source, "source_family": row["source_class"], "source_item_id": item,
                        "canonical_url": canonical_url(row["url"]), "acquired_url": row["url"],
                        "response_final_url": original["final_url"], "retrieved_at_utc": original["retrieved_at_utc"],
                        "source_catalog_path": "research/corpora/author-genre-expansion-20261002/public/" + original_catalogs[source == "einfo"],
                        "source_catalog_commit": SOURCE_COMMIT},
             "author_unit": {"kind": "coauthored" if coauthored else "single_byline", "members": members,
                             "unit_id": did + ":coauthor-unit" if coauthored else members[0]["author_id"],
                             "individual_author_id": None if coauthored else members[0]["author_id"],
                             "source_byline_literal": row["article_byline"],
                             "discovery_index_author": row["author"],
                             "byline_role_fields": row.get("byline_roles", {"authors": [{"name": n} for n in names]}),
                             "role_note": row.get("role_note", "Byline attribution only; quoted speakers are not article authors")},
             "human_origin_evidence": {"assessment": "supported_by_human_byline_and_publishing_source",
                                       "byline_verified": True, "source_verified": True,
                                       "evidence_urls": [row["url"], row["author_url"]],
                                       "scope": "Operational published-human research population; no claim of unassisted composition or word-level authorship"},
             "assistance_status": "unknown", "assistance_evidence_note": row["assistance_status"],
             "language": {"tag": "zh-Hant-TW", "description": "Predominantly Taiwan traditional-character Chinese publishing context",
                          "inference_scope": "publication/orthographic variety, not the personal identity or language of every span"},
             "genre": row["genre"], "genre_label_status": row.get("genre_label_status", "provisional editorial/source classification"),
             "topic_tags": row["topic_tags"],
             "dates": {"publication_date_claim": row["article_date_claim"],
                       "publication_timestamp": row.get("publication_timestamp"),
                       "current_page_updated_at": row.get("current_page_updated_at"),
                       "historical_snapshot_status": "not_verified", "historical_evidence": row["historical_evidence"],
                       "current_bytes_are_historical_snapshot": False},
             "publication_roles": {key: row.get(key) for key in ("publication_role", "earlier_outlet", "earlier_date_claim", "embedded_material", "structure_note")},
             "content_roles": {"structural_roles_preserved": True, "inline_quotation_attribution": "unresolved",
                               "clean_author_span_annotation": False,
                               "quoted_or_borrowed_text_may_be_present": True,
                               "translation_note": row.get("role_note") if item == "6605" else "No sentence-level translation audit performed",
                               "privacy_review_required_before_broader_use": True,
                               "specific_privacy_flag": "additional_span_review_required" if row.get("privacy_review") else None},
             "rights": {"license_claim": row["license"], "evidence_urls": rights_urls, "evidence_reviewed": True,
                        "scope": "bounded private noncommercial research admission; use-specific and third-party exceptions remain",
                        "article_notice_present": row.get("article_level_license_notice_present"),
                        "site_default_exceptions": source == "einfo", "restrictions": restrictions,
                        "raw_text_publication_allowed": False, "commercial_training_authorized": False,
                        "derivative_text_publication_authorized": False},
             "content": content,
             "leakage": {"work_id": did, "lineage_id": known_group, "content_group_id": series_group,
                         "near_duplicate_group_id": known_group, "prompt_family_id": None},
             "deduplication_status": "canonical URLs and exact body hashes checked within this admission; cross-corpus near-duplicate review pending before a new experimental split",
             "analysis_assignment": {"experiment_id": None, "split": None, "fit_authorized": False}}
        validate_record(r)
        records.append(r)
    records.sort(key=lambda r: r["document_id"])
    catalog = output / "ADMITTED_DOCUMENTS.jsonl"
    catalog.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records), encoding="utf-8")
    registry = {"schema_version": REGISTRY_VERSION, "release_id": RELEASE, "status": "operational_general_human_corpus_admitted",
                "admitted_on_utc": "2026-10-02", "catalog": file_ref(output, catalog.name), "counts": summarize(records),
                "default_analysis_policy": OPERATIONAL_POLICY,
                "optional_stricter_policy": STRICT_POLICY,
                "date_cutoff": None, "requires_pre2022_snapshot": False,
                "source_lineage": {"repository": "proffitteoy/style-compiler", "commit": SOURCE_COMMIT,
                                   "catalogs": [file_ref(source_root, "public/" + p) for p in original_catalogs]},
                "benchmark_effect": "none; no frozen split, feature cache, fit inputs or prior result labels changed",
                "private_body_distribution": "not included; local authorized cache required",
                "experiment_assignment": None}
    dump(output / "REGISTRY.json", registry)
    return registry, records


def integrate_source_registry(base_path, output, registry):
    base = json.loads(Path(base_path).read_text(encoding="utf-8"))
    existing = {r["source_id"] for r in base["sources"]}
    if existing & {"guava", "einfo"}:
        raise ValueError("Source IDs already exist; review instead of appending duplicates")
    result = json.loads(json.dumps(base))
    result.update({"schema_version": "source-registry/1.2.0", "updated_on": "2026-10-02",
                   "status": "source_research_with_explicit_general_human_admission",
                   "purpose": "Source-specific research records plus explicitly admitted human-publication strata; earlier source decisions retained unchanged"})
    result["policy"]["general_human_admission"] = {
        "policy_id": OPERATIONAL_POLICY, "date_cutoff": None, "historical_snapshot_required": False,
        "assistance_unknown_is_not_blanket_exclusion": True,
        "basis": "Reviewed named-human byline, publishing source, rights and preserved source lineage",
        "optional_strict_estimand": STRICT_POLICY,
        "previous_source_decisions": "retained; no automatic retrospective reclassification"}
    result["policy"]["bounded_pilots"] = "source-specific rights, byte caps and checksummed acquisition provenance required; historical bytes only when required by a specific historical estimand"
    for source, name, count, sole, authors, url in [
        ("guava", "芭樂人類學 / Guava Anthropology", 41, 40, 10, "https://guavanthropology.tw"),
        ("einfo", "環境資訊中心 / Environmental Information Center", 6, 6, 2, "https://e-info.org.tw")]:
        result["sources"].append({"source_id": source, "name": name,
            "research_domain": "public_humanities" if source == "guava" else "environmental_journalism",
            "primary_urls": [url], "record_unit": "bylined published article, with quotations and other contribution roles retained",
            "acquisition": {"status": "bounded_acquired_local", "works": count,
                            "report": "research/corpora/author-genre-expansion-20261002/public/REPORT.md"},
            "provenance": {"generation_origin": "supported_human_publication", "assistance_status": "unknown", "historical_snapshot_required": False},
            "rights": {"license_claim": "CC BY-NC-ND 3.0 Taiwan" if source == "guava" else "CC BY-NC-ND 4.0 with site exceptions",
                       "intended_use_review": "bounded private noncommercial research", "raw_text_redistribution": "not_authorized_by_this_registry"},
            "admission": {"general_human_corpus": "admitted", "cohort": "H_G", "analysis_policy": OPERATIONAL_POLICY,
                          "works": count, "single_author_documents": sole, "repeated_author_trajectories": authors,
                          "measurement_validation": "not_claimed", "population_fit": "not_run_or_authorized",
                          "registry": PACKAGE_REPO_PATH + "/REGISTRY.json"}})
    dump(Path(output) / "source-registry.updated.json", result)
    top = {"schema_version": "corpus-registry/1.0.0", "updated_on": "2026-10-02",
           "purpose": "Explicit operational intake entries; not a count or retrospective relabeling of all prior inventories",
           "admission_policy": OPERATIONAL_POLICY, "date_cutoff": None,
           "entries": [{"release_id": RELEASE, "registry": PACKAGE_REPO_PATH + "/REGISTRY.json", "counts": registry["counts"]}],
           "previous_source_inventory": "research/source-registry.json",
           "frozen_experiment_policy": "Existing frozen datasets and reported results remain unchanged; new studies must explicitly select a corpus version and create their own leakage-reviewed split"}
    dump(Path(output) / "corpus-registry.json", top)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-registry-base", type=Path)
    args = parser.parse_args()
    registry, records = build(args.source_root, args.output)
    if args.source_registry_base:
        integrate_source_registry(args.source_registry_base, args.output, registry)
    print(json.dumps(registry["counts"], ensure_ascii=False, indent=2))
