# Final independent core audit after reconstruction

## Decision

The reviewed source is suitable for the narrowly bounded, non-optimizing TRAIN/DEV resource profile, conditional on restored exact inputs, complete extraction verification, fresh coordinator approval, and the process-tree watchdog. Execution remains blocked on complete, verified4,814-arm measurement. The coordinator reports that base inputs have been restored and verified; this audit has not read their bodies. No real profile, natural optimizer fit, TEST access, or davinci access is approved by this report.

This is an instrument-level sequence-prediction implementation review. It does not establish a full style, author, discourse, causal-prefix or psychological model.

## Fresh results on current reconstructed code

- 63/63 primary implementation, watchdog and freeze tests independently rerun: pass
- 23/23 independent core/math/trainer tests: pass
- 8/8 independent synthetic cache/firewall tests: pass
- 2/2 independent profile prerequisite/selection tests: pass
- Two tiny synthetic Adam runs within each checkpoint-test replay reproduce selected epoch, development score and restored checkpoint tensors exactly
- Runtime directly checked: Python 3.12.14, Torch 2.3.1+cpu, NumPy 1.26.4
- The latest standard-library watchdog source was inspected; its parent/CPU-child accounting and simulated CPU/RSS kill regressions passed, and its recorded self-test exited successfully with two-core affinity and explicit metrics
- Auditor natural record-body reads, TEST/davinci reads, natural fits, downloads and remote writes: zero

The original frozen design hash remains `2729b1608397be1d45e3620c86ec7b3ae1f21fdc9e28c70bc942c41b0a122444`. Fresh source hashes are in FINAL_AUDIT_MANIFEST.json. Historical pre-reset hashes and checks are separately labeled in PRE_RESET_AUDIT_SNAPSHOT.json and do not validate reconstructed files.

## Correctness and information boundaries

The model receives only the five-field prefix packet, with separately owned prefix-only tensor storage. Full record metadata, source/arm labels, raw text, global vectors, future values/masks and final document lengths do not enter the forward path. The adapter verifies the exact71 instrument catalog, removes exactly the three history channels, and joins local68 plus two structural counts by audited unit identity and span rather than row order. TEST/davinci descriptors fail before body opening. Unknown opportunities remain unknown; encoder log1p is applied once. Typed measurement records remain in the original hash-verified private cache. Failed parsing preserves null lexical T and direct span lengths; genuine structural zero receives no invented denominator.

Transforms are TRAIN-only. Constant/unobserved value paths stay zero in every split, without test clipping. Input normalization uses all declared TRAIN units with fixed question→answer→H/ChatGPT half-slots before observed-channel normalization; blank arms or entire blank variants never reallocate weight. Main fitting/scoring uses exactly jointly supported answer variants, then equal questions and arms, equal valid targets within document, and equal observed families after within-family channel averaging.

The coordinator-approved target clarification is implemented and tested: only observed next-unit targets at index1 or later can satisfy the50-component target gate. Counts are recomputed on the actual jointly eligible H/ChatGPT training population and monotonically iterated to a fixed point. First-unit-only observations and observations in excluded unpaired answers cannot create an untrained output head. A cascade regression verifies that dropping one unsupported family can trigger the required subsequent support removal. All-unit input support remains separately reported and does not alter normalization.

F1 shares pair supports, covariance-validity indicators and joint-conditioned first moments with covariance models. Explicit joint-centered sample covariance passes missing-pair and n=0/1/2 hand checks and constant-extreme regressions. Fcov/F2/F3/F4 share the same covariance inputs. Shuffling averages losses, never predictions. Set/moment invariance, last-preserving permutations, family ablation and independent-family value isolation pass. Unscored outputs, whole unscored independent branches, and frozen-zero value/moment paths are removed before active-capacity brackets are recomputed.

Fixed-seed factories, transform signatures, source-specific scope, checkpoint restoration, failed/interrupted-attempt accounting and the three-seed component bootstrap have executable checks. Primary intervals retain98.333333% coverage. Seeds are not treated as independent data.

## Resource-profile review

The entrypoint requires all4,814 approved TRAIN/DEV cache records to be verified, pins frozen cohort metadata and cache hashes, and commits32-TRAIN/16-DEV component selection before cache reads. All TRAIN alone supplies pooled and source-specific transforms. The profile retains32 forward graphs until a single backward, samples up to16 DEV forward calls for cost only, makes no optimizer or measured-outcome comparison, and reports both CPU and wall forecasts for all72 runs×100 epochs with the shuffle multiplier and1.5 safety factor. The separate watchdog enforces two-core affinity and samples process-tree memory/CPU against2GiB/20-minute ceilings.

## Remaining limits and gates

1. No actual natural eligibility, length distribution, memory demand, runtime feasibility or model performance is asserted; complete4,814-arm extraction verification is still pending
2. Full optimizer fitting needs a separate decision based on the empirical profile and study-wide CPU/wall/disk/fit ceilings
3. The identified freeze provenance gap is repaired: checkpoint hashes, run/seed/DEV decisions, source transforms, architecture and target mappings are checked against successful fit records; later ledger mutation is rejected. Synthetic negative checks pass. The separate controlled held-out evaluator and actual complete-fit freeze remain unrun; no TEST/davinci access is authorized
4. Independent-family models expose the underlying nuisance data but use different explicit nuisance summaries from shared F4. That limitation is disclosed in the implementation/execution notes and must qualify future cross-family attribution
5. All scientific natural comparisons and final test panels remain unrun. Optional retrospective, sparse, block and residualization extensions are not prerequisites for this bounded core resource profile

## Runnable checks

From the study directory:

```sh
runtime/venv/bin/python -m unittest discover -s tests -v
runtime/venv/bin/python independent_audit/audit_synthetic_checks.py
runtime/venv/bin/python independent_audit/audit_cache_adapter.py
runtime/venv/bin/python independent_audit/audit_profile_gate.py
runtime/venv/bin/python independent_audit/reproduce_first_unit_target_gap.py
```

The last reproducer now reports `issue_reproduced:false`, zero eligible support for the first-unit-only channel, and no optimizer step. Its pre-fix receipt is retained separately. These checks read no natural bodies. Any subsequent source change requires affected tests and hashes to be refreshed.
