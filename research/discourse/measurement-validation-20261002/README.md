# Aggregate-only discourse validation release

This is a publication-safe derivative of the original frozen local experiment. It contains aggregate findings and method code, with independent review. It deliberately excludes the original report's per-document score table, aggregate_summary.json (which despite its name contains per-document numerical records), dev_results.json, test_results.json, exposure/download manifests, raw corpus data, reconstructed annotation graphs, paragraph vectors, and sentence identity hashes.

Read PUBLIC_REPORT.md first. The original frozen result remains seven pair-rank reversals out of ten for one native group summary over five documents. Independent post-hoc grouping checks yield six reversals after group-yield deduplication and three after a narrow unary-span contraction. These exploratory checks diagnose representation dependence; they do not replace the original metric or isolate semantic disagreement.

The four original frozen method files and freeze.json are unchanged. No measurement was rerun or retuned to prepare this derivative. Original local artifacts remain unchanged. All ten consumed documents are exposed and unavailable for any future held-out claim.

The Python code uses the standard library. test_synthetic.py uses invented text, not corpus excerpts; its fixtures can be examined or run independently. The original corpus evaluator and downloader retain their original local paths and require the original selected-input metadata and privately acquired source files, which are not included in this release. This is an auditable method bundle, not a standalone data redistribution. The protocol describes private local computations, including document-level outputs; distributing this source code does not authorize uploading those outputs.

The independent review and aggregate checks are included unchanged. See PUBLIC_RELEASE_MANIFEST.json for the complete publication allowlist and hashes. No remote writes were made when constructing this bundle.
