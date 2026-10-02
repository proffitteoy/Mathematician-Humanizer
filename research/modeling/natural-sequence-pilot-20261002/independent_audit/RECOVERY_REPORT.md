# Independent audit recovery report

## Current decision: all execution gates remain closed

The executor was replaced at approximately 03:39 UTC on 2026-10-02. The study sources, measurement caches, restored runtime, and audit scripts disappeared. The extractor last confirmed 4,338 of 4,814 arm caches. No complete extraction or integrity-verification receipt was available. No natural resource profile or empirical optimizer fit was approved by this audit.

The scripts in this directory were reconstructed from the auditor's retained context after the replacement. Fresh replay after reconstruction now passes all 20 independent core tests and all eight cache-adapter tests on the restored Torch 2.3.1+cpu / NumPy 1.26.4 runtime. The fixed-slot correction and repeated synthetic checkpoints pass. Profile-gate tests and the implementation test replay still await reconstruction of their entrypoints. Historical results below remain separate from these new receipts; natural execution gates stay closed.

## Historical results before replacement

- 52 implementation tests passed when rerun independently
- 19 additional independent core checks passed
- Eight synthetic cache-adapter checks passed
- Two synthetic profile prerequisite/selection checks passed
- The core suite included two tiny synthetic Adam runs; selected epoch, development score and restored checkpoint tensors matched exactly
- The audit read no natural record bodies, raw corpus bodies, TEST bodies, or davinci bodies, and performed no natural fits, downloads, or remote writes
- Tests used the existing Python 3.12.14, Torch 2.3.1+cpu and NumPy 1.26.4 restoration runtime

The fixed design contract matched SHA-256 `2729b1608397be1d45e3620c86ec7b3ae1f21fdc9e28c70bc942c41b0a122444`.

## Verified repairs before replacement

1. Models previously counted TRAIN-ineligible output weights and whole unscored independent-family branches as active capacity. These were removed; frozen-zero value/moment paths were pruned internally while the fixed packet and nuisance semantics remained
2. Cohort validation now rejected a question mapping to different copy components or sources
3. Interrupted attempts blocked later fits pending reconciliation, retained recorded CPU, and could not silently disappear
4. The original covariance computation suffered cancellation: a constant 100-row prefix of float32 value 1e10 yielded variance approximately -42366.7. Explicit joint-centered products corrected this without clipping or clamping
5. The natural resource profile initially backpropagated individual prefixes immediately. It was changed to retain all 32 forward graphs and perform one backward, matching trainer memory behavior
6. Profile projections were expanded from wall time alone to both CPU and wall time for all 72 fits, with the 10-permutation development multiplier and a 1.5 safety factor

Core checks covered direct covariance with n=0/1/2 and missing pairs; matched support and joint means; exact 49/50 independent-component gating; equal-question/answer/arm main sampling; fixed target masks; permutation invariance; loss rather than prediction averaging; family ablations; model-independent support; interruption accounting; and deterministic checkpoints.

The adapter review confirmed exact 71-to-68+2 mapping, source-unit/span joins, typed missingness retained in the referenced original private cache, unknown opportunities, genuine structural T=0 without invented denominator, and preservation of source-span lengths when parsing failed. Synthetic tests verified TEST/davinci rejection before body opening and compressed-file hash checks.

## Unapplied weighting correction

The coordinator chose the literal hierarchy-before-mask interpretation: retain all declared question, answer and H/ChatGPT slots; an empty arm contributes zero unit mass without reallocating its weight. Normalize observed mass per channel afterward. The attempted implementation patch failed because its file had disappeared.

A new regression has been added to the reconstructed independent core suite:

- q0: H=10, GPT has zero units; q1: H=0, GPT=0
- q0 H base mass must equal 0.25, total nonempty unit mass 0.75, and the fitted mean 10/3
- A wholly empty answer variant must likewise retain its declared answer slot

The new suite therefore has 20 tests rather than the historical 19. All 20 passed on reconstructed code at approximately 03:52 UTC, including this correction.

## Revalidation commands

From the study directory, after restoring the authorized runtime and implementation:

```sh
runtime/venv/bin/python -m unittest discover -s tests -v
runtime/venv/bin/python independent_audit/audit_synthetic_checks.py
runtime/venv/bin/python independent_audit/audit_cache_adapter.py
runtime/venv/bin/python independent_audit/audit_profile_gate.py
```

The tests are synthetic-only. The core suite creates two tiny synthetic optimizer runs in temporary directories. The profile-gate test imports profile_natural.py but never invokes main. It creates only synthetic prerequisite receipts. None of these commands should read natural bodies.

## Conditions before a bounded real profile

- Restore and verify exact source, runtime, pinned cohort metadata and feature-cache identities
- Complete and verify all 4,814 allowed TRAIN/DEV H/ChatGPT cache records
- Apply the fixed-slot weighting interpretation and pass all reconstructed tests against current sources
- Obtain a fresh complete code/hash manifest and explicit coordinator approval
- Preserve deterministic 32-TRAIN/16-DEV component selection before feature reads; fit transforms on TRAIN only
- Perform no optimizer step, target-loss comparison or performance-based selection
- Launch under the existing two-core, process-tree 2 GiB RSS and 20-minute CPU/wall watchdog

Final optimizer fitting remains separately gated on the resulting empirical resource receipt and all study ceilings. Final TEST/davinci evaluation remains separately gated on a verified immutable model/transform/configuration freeze. The evaluator must match frozen checkpoint hashes and identities to successful fit-ledger events. The old synthetic throughput receipt predates the centered-covariance implementation and cannot establish current natural cost.

For future interpretation, the independent-family models expose all permitted nuisance data locally, but their explicit nuisance summary differs from shared F4's all-pair support summary. Disclose or align that representational difference before unqualified cross-family attribution. This is not a reason to require optional retrospective/sparse/block stages before a bounded core resource profile.

## Artifact status

PRE_RESET_AUDIT_SNAPSHOT.json contains historical source hashes, clearly labeled as historical rather than final. In particular, plan.py, train.py and profile_natural.py changed after some saved hashes, and final hashes could not be collected before replacement. RECONSTRUCTED_TEST_MANIFEST.json records this directory's reconstructed files and current partial-revalidation status. SYNTHETIC_AUDIT_RECEIPT.json and CACHE_AUDIT_RECEIPT.json contain fresh test outcomes and source hashes. No current profile or natural fit has run.
