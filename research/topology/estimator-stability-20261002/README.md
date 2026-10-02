# Fixed cohort PHD measurement reliability

A separately frozen 20-seed follow-up to the audited 32-pair pilot. Read [the report](STABILITY_REPORT.md) for the result and [the protocol](STABILITY_PROTOCOL.md) for the design fixed before measurement.

The key result is that the equal-length mean dimension contrast ranges from −0.560 to 1.708 across the 20 predetermined schedules, while its mean slope contrast remains positive. This is conditional measurement evidence, not a detector evaluation or a universal human-style claim.

This release contains aggregate evidence only. The detailed per-text and per-seed numerical files stay local. No source text, embeddings, model weights, source indices or cloud identifiers are included.

## Files

- STABILITY_REPORT.md: findings, limitations and complete aggregate outcome counts
- STABILITY_PROTOCOL.md: frozen design and resource bounds
- aggregate-results.json: domain/condition summaries, seed-level cohort means, N-bin summaries and covariance/empirical-composition decompositions
- run_stability.py and analyze_stability.py: measurement and predeclared analysis code, hashes frozen at run admission
- audit_saved_results.py: separate saved-energy/provenance/statistical audit
- prepare_aggregate_release.py: strips local rows and creates aggregate-only outputs
- run-manifest.json and verification.json: run identities, limits and completed checks
- RELEASE_MANIFEST.json: release allowlist and file SHA-256 identities

## Reproduction limits

The runner expects the original pilot's pinned local runtime, model files, private source archives, selection manifest and saved cloud hashes in a sibling directory named topology-replication-20261002. These inputs and full local results are not bundled. No network fallback is provided. Running the script writes local per-text diagnostics and refuses to overwrite an existing measurement run; do not mistake those local diagnostics for publication-authorized files.

The old pilot is preserved unchanged. Publishing is a separate decision; preparing this directory did not push or upload anything.
