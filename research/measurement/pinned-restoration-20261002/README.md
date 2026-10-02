# Pinned input restoration, 2026-10-02

This is a local-only reconstruction of lost measurement prerequisites. No fitting, full extraction, corpus resampling, synthetic replacement, or remote write is included. Raw source files and private identities stay local. Historical private caches remain unavailable.

Sources: style-compiler instrument revision 2c3eeb0bcf3020fcba36f13b2bc6bab490b3f1ae; public cohort preparation revision 93b60d334c20148e3cea61afc8aaa8c1e861901f; M4 corpus revision 628bf0fcb2e8c6b7ffa71fd1af6be413aced8f7d; official stanfordnlp/stanza-zh-hans model commit 82f2856d1cf4f933738a8a84b5ad959d156040a0; resources version 1.10.0.

All restored files must match original pinned Git blob or SHA256 identities before use. The existing CPU-only Torch2.3.1+cpu / NumPy1.26.4 runtime is reused. Download cap is 700MiB, new disk cap 2GiB, and restoration wall budget 30 minutes. An in-progress file or historical receipt is never a current readiness claim.

Commands and source plans are preserved here as they are prepared. Exact sources and verification results will be recorded in RESTORATION_RECEIPT.json. Prospective TEST/davinci bodies may be processed only for deterministic original cohort metadata restoration, never for analysis, feature extraction, model fitting or tuning.

## Verified outcome

RESTORATION_RECEIPT.json is the fresh readiness receipt. All five original model files and resources.json match original SHA256. Both M4 raw files match the fixed revision's Git blobs. Both original128-row exposure prefixes match their published byte counts and SHA256. All three reconstructed private cohort files reproduce their original SHA256 byte-for-byte, and every frozen public aggregate field matches the published record. The eligible population remains1,816 TRAIN +591 DEV pairs, or4,814 HUMAN/ChatGPT arms.

The restored measurement profile hash also matches the previous run exactly:221323897ea20205d0801383537558b4411cb47eb945c2deac51e24ccb2549a3. This is a profile identity statement, not a claim that every historical dependency file/environment byte was recovered. The functional instrument inventory has49 blob-verified files at the original instrument commit. The original48-file inventory list itself was lost; this reconstruction includes an explicit functional superset.

Fresh model-free tests:164 ran,163 passed, the original optional full Unicode table check skipped, no failures/errors. Synthetic parser smoke:2 original synthetic sentences parsed,71 channels, no corpus bodies. No natural feature extraction or fitting was run here. Metadata restoration and verification necessarily reread TEST/davinci source bytes for original grouping, identities and integrity only; they did not parse those texts into the71 features or fit/tune anything.

## Reproduction

1. Materialize each public source in source_plan.json and the sibling cohort public/source_plan.json using the authorized read-only GitHub connector at its pinned revision. Preserve UTF-8 bytes and verify the stated Git blob SHA1. Anonymous raw.githubusercontent.com access to the private style-compiler repository returns404; this is not a source-identity failure. restore_sources.py verifies already-materialized files and offers an anonymous raw URL route only if that repository is publicly readable.
2. Preserve resources.json from https://raw.githubusercontent.com/stanfordnlp/stanza-resources/main/resources_1.10.0.json only if its SHA256 is3efb2833a67c0184fac2ea9986c04f9585bfb89fb943a4ab1a6bcbed641d6be0. Then run restore_models.py. Reuse the separately restored CPU Torch2.3.1+cpu / NumPy1.26.4 interpreter. Run restore_stanza_runtime.py and restore_schema_runtime.py for the small official-PyPI dependencies. They record immutable wheel SHA256 and install offline with--no-deps, never CUDA.
3. Run the cohort's unmodified public/acquire.py for the two original raw files. Materialize the published chinese-benchmark-audit-20261002/combined_manifest.json to /tmp/zh-corpus-audit/combined_manifest.json; run restore_exposure_prefixes.py. Save original aggregate outputs under the cohort published_receipts directory before rebuilding.
4. Run the original cohort public/prepare_cohort.py and public/verify_preparation.py. These perform only original deterministic metadata reconstruction and identity/integrity checking. Require all original private file hashes and aggregate split counts before any downstream use.
5. Using the restored CPU interpreter, run ../chinese-extraction-recovery-20261002/public/run_tests.py, verify_synthetic_parser.py, then the original extract.py predeclare. The wrapper bytes, protocol digest and deterministic private pilot-plan digest must match their originals.
6. Run verify_restoration.py to produce the fresh RESTORATION_RECEIPT.json. The natural feature extraction pilot/full phases need their separate authorization, budget gate, private-cache backup and coverage verification; restoration readiness does not claim extraction completion.

All commands here use their recorded local directories; invoke scripts via their full path or from the shared workspace root. The main runtime is ../natural-text-learning-pilot-20261002/runtime/venv/bin/python. No raw bodies, record IDs, offsets, per-record measurements or parse caches may be committed or uploaded. Any source/test receipts inside the restored repo are historical evidence, not fresh passes.
