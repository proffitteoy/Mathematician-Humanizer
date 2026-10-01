# Frozen controlled structural TEST evaluator v1

## Preparation status and scope

This package prepares one future heldout evaluation. It is not authority to open TEST. No empirical test export, empirical ROOT_GO, TEST_START, prediction output or TEST_RECEIPT is created during preparation. Only public fit code, public protocol, the approved completed-fit receipt/checkpoint/completion record, and explicitly synthetic fixtures are used. No original authoring, train/dev data, full blind-review files or sealed TEST is inspected.

This is the frozen 12-descriptor condition-only linear-softmax baseline, fitted once for 150 epochs at learning rate 0.05, with preference weights exactly zero. It is not the 71-descriptor linguistic model, a natural-author style model, a learned preference ranker, 1280 natural works, stage-1 acceptance or personalization. Eight test families support exploratory family-level feasibility only. No semantic guarantee or human-style claim is authorized. The independent semantic gate is fallible; its effect cannot be credited to the model.

There is no fitter, scaler-fitting function, editor or candidate generator in the imported inference module. Descriptor/scaling/softmax functions are exact AST-equivalent extracts from frozen controller_v03.py. Public labels_v02.py is copied byte-for-byte. No network, remote write, model download, K=4 candidate generation, refit, seed search, threshold tuning, early stopping, checkpoint choice, discarded test attempt or replacement draft is permitted.

## Fixed approved prior artifacts

Only these prior-stage artifacts may be read; their complete byte hashes are hard-coded and independently repeated in ROOT_GO:

- /workspace/shared/style-controlled-fit-v01/runs/controlled_v1_20261001/condition-only.weights.json
  - c2d6d4352c0209d78f221ede226301fa835fa80c679a77b6f09bd9544aabc83b
- /workspace/shared/style-controlled-fit-v01/runs/controlled_v1_20261001/FIT_RECEIPT.json
  - 96283df19251dabc0b4e416d8745e4dd80db227be35b3982489d8f9e3eb5887b
- /workspace/shared/style-controlled-fit-v01/run_state/EMPIRICAL_COMPLETE.json
  - 5e3069433e398b1dc07026d2bc9b6409d18b9e0cf377bdf40ea71286c701279e

The wrapper verifies checkpoint payload hash/schema, fixed epochs and rate, train-only transform, finite tensors, boolean constant mask and exact-zero preference weights. FIT_RECEIPT and EMPIRICAL_COMPLETE must agree on the complete checkpoint and receipt hashes. No alternate paths or checkpoints can be supplied.

## Exact sanitized coordinator handoff

Root must create one separate canonical non-symlink directory (no parent-traversal aliases), outside this evaluator and the fit package, containing exactly these six files. The evaluator never discovers original manifests, source content, private plans, train/dev data or full 384-review files. Root alone verifies the selected eight families and 64 original slots actually belong to the original sealed TEST split and attests the source hashes. Hashes bind bytes; they cannot prove independent review, semantic correctness or the truth of root's withheld-source projection.

### 1. test.json: text-only prediction input

Top-level keys exactly:

- schema: "sanitized-controlled-test/v1"
- provenance: "assistant_authored_controlled"
- source_draft_manifest_sha256: 64 lowercase hexadecimal SHA256 of the frozen original draft manifest, as a reference only
- family_split_manifest_sha256: 64 lowercase hexadecimal SHA256 of the frozen original split manifest, as a reference only
- slots: all 64 original TEST slots, in frozen deterministic order

Each slot has exactly these ten keys:

- id: unique nonempty opaque ID
- family: nonempty original family ID
- partition: "test" only
- genre: general_explanation, process_description, event_summary or reflective_commentary
- status: completed, generation_failed, technical_failed or unfinished
- text: exact original completed prose; null otherwise
- text_sha256: SHA256 of UTF-8 text; null otherwise
- mainpoint_exact: original exact main claim string; null otherwise
- fact_ids: ["P1","P2","P3","P4","P5","P6"] for completed slots; [] otherwise
- review_id: unique nonempty opaque review ID for a completed slot; null otherwise

There are exactly eight families, eight original slots per family and two families per genre. Families cannot change genre. No nominal target, requested condition, realized_condition, semantic eligibility/exclusion, review decision, template, pass, source path or unrelated metadata is admitted. This deliberately differs from the fit export by removing realized_condition and exclusion_reason, so review labels cannot affect prediction selection. Technical/generation failures and unfinished slots remain present. No replacement or resampling is allowed.

The evaluator records one frozen prediction outcome for each of the 64 slots. Every completed slot with a unique mainpoint gets the fixed model's four probabilities and predicted class, even when its format/length/structural support is later rejected or the reviewers later reject it. There is no semantic or realized-label prefilter. A missing/duplicate mainpoint has a null prediction with reason mainpoint_span_unavailable; an unproduced slot has a null prediction with reason unproduced_original_slot. These slots remain in coverage. Structural schema/hash errors fail the entire already-started attempt. A unique mainpoint is required only because the frozen model's feature definition requires that span.

### 2–3. labels_a.json and labels_b.json: TEST-only projected subsets

Each file has exactly {"schema":"sanitized-blind-reviews/v1","reviews":[...]} and covers exactly the completed exported slots, including uncertain, disagreeing and unsupported rows. For a fully completed 64-slot export each file has exactly 64 reviews. No train/dev review may appear. Never give this evaluator original 384-row files.

Each review has exactly:

- review_id
- rater_id
- fact_labels: exactly P1 through P6, each preserved / changed_or_missing / uncertain
- semantic_axes: exactly facts, unsupported_additions, negation, modality, quantifiers, scope; each pass / fail / uncertain
- mainpoint_is_real_main_claim: yes / no / uncertain
- rhythm_label: short / mixed / outside_support / uncertain
- placement_label: early / late / outside_support / uncertain

Actual realized condition is recomputed only after freezing predictions: the frozen public observed_properties and adjudicate_pair functions require both reviewers' fact preservation, all semantic passes, supported actual rhythm/placement agreement and main-claim confirmation. Uncertainty, disagreement, semantic failure or unsupported structure is excluded from conditional metrics, never changed to a nominal target.

### 4. label_receipts.json

Exact top-level keys:

- schema: "dual-blind-label-receipts/v1"
- dataset_file_sha256: byte hash of test.json
- review_files_sha256: exactly {a: byte hash of labels_a.json, b: byte hash of labels_b.json}
- review_scope: "all_completed_test_slots_only_train_dev_excluded"
- raters: two entries in A/B order with exactly rater_id, review_context_id, independent_of_authoring:true, independent_of_fit:true, blind_to and review_file_sha256
- projection_receipt: object below

The two rater IDs and two review-context IDs must be distinct. Each review subset must contain exactly the associated rater. blind_to must equal ["nominal_target","template","pass","partition","model_scores","other_rater_labels"] in that order. Rater file hashes must match review_files_sha256.

projection_receipt exact keys:

- schema: "root-test-review-projection/v1"
- actor: "root"
- original_review_files_sha256: exactly {a: original frozen 384-review A hash, b: original frozen 384-review B hash}; hash references only, never source paths
- original_review_row_counts: exactly {a:384,b:384}
- subset_review_files_sha256: exact copy of review_files_sha256
- selected_review_ids: sorted exact review IDs for all completed exported TEST slots
- selected_review_ids_sha256: SHA256 of selected_review_ids canonicalized with inference_core.canonical
- train_dev_rows_exported: integer 0

Root approves this entire label receipt by canonical-object SHA256 in ROOT_GO. The full original files remain coordinator-only. The evaluator checks exact subset coverage and every subset hash but cannot independently prove source-to-subset correspondence without violating custody.

### 5. storage_receipt.json

Root measures every controlled artifact outside this evaluator, including authoring versions, labels, exports, prior fit artifacts, transient copies and the finalized ROOT_GO itself. The evaluator never scans those private directories. Root reserves exclusive controlled storage, with no concurrent controlled writes until root releases the reservation.

Exact keys:

- schema: "controlled-artifact-budget-receipt/v1"
- actor: "root"
- measured_at_utc: timezone-aware ISO8601 timestamp, no more than 600 seconds old and not in the future
- excluded_root: "/workspace/shared/style-controlled-test-v01"
- external_controlled_bytes: nonnegative integer total outside that root
- controlled_byte_cap: integer 33554432
- exclusive_budget_reservation: true
- reserved_output_bytes: integer 1048576
- no_other_controlled_writes_until_release: true

The evaluator requires external bytes + current package bytes + 1 MiB reservation <=32 MiB. All newly produced predictions, metrics, global start/completion markers and failure output combined fit within 1 MiB. Each output write checks cumulative generated bytes before writing, reserving 4096 bytes for a possible failure record. Root must conservatively account for receipt/GO file final sizes when constructing the storage receipt to avoid a self-accounting omission.

### 6. ROOT_GO.json

Exact keys and values:

- schema: "root-controlled-test-go/v1"
- action: "CONTROLLED_STRUCTURAL_TEST_GO"
- actor: "root"
- run_id: 1–64 characters from A–Z, a–z, 0–9, underscore, hyphen
- package_manifest_sha256: byte hash of the final FILE_HASHES.json
- protocol_sha256: byte hash of protocol.json
- code_sha256: exactly the three file-name/hash pairs for test_evaluator.py, inference_core.py, labels_v02.py
- input_sha256: exactly five file-name/hash pairs for test.json, labels_a.json, labels_b.json, label_receipts.json, storage_receipt.json, using their final byte hashes
- review_approval_sha256: canonical-object SHA256 of label_receipts.json, using inference_core.canonical
- checkpoint_sha256: fixed approved checkpoint hash above
- fit_receipt_sha256: fixed approved FIT_RECEIPT hash above
- fit_complete_sha256: fixed EMPIRICAL_COMPLETE hash above
- global_test_start_path: "/workspace/shared/style-controlled-test-v01/run_state/TEST_START.json"
- test_scope: "one_time_frozen_condition_checkpoint_test64_eight_families_no_fit_no_tuning_no_inference"
- issued_at_utc: timezone-aware approval timestamp, no more than 600 seconds old and not in the future

Invoking root must separately provide the exact byte SHA256 of ROOT_GO. Do not manufacture a GO for synthetic verification. An actor string is not a cryptographic identity mechanism; caller authorization, root custody, the independently supplied GO hash and prior independent code review are essential. Permission to prepare is not permission to evaluate.

## Irrevocable order and global one-shot gate

1. Start a 60-second wall alarm and enforce <=2 available CPU affinity, 512 MiB address space and 60 CPU seconds. These cover authorization, input validation, predictions, diagnostics and output.
2. Reject immediately if the fixed global TEST_START already exists. Verify the externally supplied GO hash, exact GO schema/scope, frozen package/code/protocol hashes, fresh exclusive storage receipt, and completed frozen-fit artifacts. No TEST text/review bytes are opened or hashed in this preflight.
3. Create needed directories durably, fsyncing each directory and its parent entry. Exclusively create run_state/TEST_START.json with O_CREAT|O_EXCL|O_NOFOLLOW; fsync contents and parent directory. It binds exact GO, code, input, checkpoint and fit hashes. Two concurrent invocations cannot both win. Its mode is read-only and it is never deleted, reset, relocated or replaced. This literal marker path remains mandatory for every future evaluator version, even if the package version changes. The executable refuses relocation.
4. Only after START and durable per-run directory creation, read/hash/validate test.json and calculate all original-slot prediction outcomes. Exclusively create and fsync PREDICTIONS_FROZEN.json, then verify its hash and read back the frozen object. It has no labels or review diagnostics.
5. Only then open/hash the separate A/B label subsets and label receipt, recompute actual consensus, compute fixed metrics from the persisted predictions and save all-slot eligibility/exclusion audit.
6. Exclusively create TEST_RECEIPT.json, verify output/shared storage limits, then create TEST_COMPLETE.json. A result is successful only when the invocation is known to have returned successfully (exit 0), this completion record matches receipt/prediction/START hashes, and no FAILED.json exists. A nonzero or uncertain return is failed-closed even if completion bytes are present after an interrupted or failed fsync. Stdout reporting occurs after the durable commit; an output-channel OSError is ignored and cannot create a contradictory FAILED marker.

Any failure, interruption, timeout, malformed input, label mismatch, output collision, insufficient budget or uncertain outcome after START consumes the one permitted TEST attempt. It cannot be rerun under a different run ID, new GO, alternate checkpoint or changed code. Do not delete START, resample failed slots, tune after observations or use a new package version to evade it. Root must treat failure as the terminal outcome of this authorization. The marker is an auditable engineering guard, not an adversarial operating-system isolation boundary; an owner able to rewrite code or delete files must respect the protocol.

## Frozen metrics and reporting

The four conditions are ordered short_early, short_late, mixed_early, mixed_late. Prediction ties choose the first in this order. No condition-specific minimum TEST-family support gate is introduced; report all actual support counts without replacement.

- Family-macro CE: mean of each eligible family's mean -log(max(saved actual-label probability,1e-300))
- Family-macro accuracy: mean of each eligible family's fraction correct
- Family-macro coverage: mean eligible/original slot fraction across all eight original families, including zero-eligible families
- Report eligible/all rows and eligible/all families, per-family sums/counts, per-condition family support, total exclusion categories and every original slot's eligibility/reason
- Families with zero eligible rows are excluded from conditional CE/accuracy but contribute zero coverage; if all families have zero eligibility, CE/accuracy are null and coverage zero, retaining 64/8 denominators

The exact-threshold rule recomputes the public structural definition from text/mainpoint. Its one-hot class is floored at 1e-15 for other classes and renormalized for CE. Because accepted labels require the same exact definition, its perfect accuracy is tautological and does not demonstrate independent style prediction, human judgment, semantic preservation, or benefit over a rule. Both share the same fallible dual-review filter. No confidence interval or confirmatory-generalization claim is added for eight families.

## Invocation after separate explicit approval

Only root may invoke after freezing/reviewing the entire final package and preparing the exact six-file handoff:

    PYTHONDONTWRITEBYTECODE=1 python test_evaluator.py --run --input-dir /ROOT/APPROVED/SANITIZED/TEST/DIRECTORY --expected-go-sha256 ROOT_SUPPLIED_64_HEX_BYTE_HASH

Never run placeholders, a synthetic GO or an invented approval. No empirical test execution is part of package preparation.

## Synthetic-only verification

    PYTHONDONTWRITEBYTECODE=1 python -m unittest -v test_test_evaluator.py

All input examples are visibly synthetic in-memory fixtures. The analytic test model has uniform probabilities and is never fitted or deployed. Tests create only temporary synthetic files within this package and remove them afterward, use mock authorization/order events, and never create the actual global TEST_START or ROOT_GO. They cover schema and label-channel rejection, partition/split boundaries, dual-review/projection guards, original denominators, missing mainpoint and generation outcomes, rule/CE/macro arithmetic, prediction-before-review order, exclusive read-only writes, concurrent marker claims, durable directory creation and fsync-failure denial, failure/no-rerun order, symlinks, nonfinite/duplicate JSON, resource/storage bounds and exact descriptor extraction. Read-only public-source AST comparison is allowed. Synthetic reviews are fixtures, not real independent judgments or empirical evidence.
