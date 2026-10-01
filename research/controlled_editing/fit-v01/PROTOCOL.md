# Controlled structural condition baseline: frozen wrapper v1

## Status and limits of claim

This package prepares a single future empirical condition-only fit. It does not authorize or contain an empirical fit. Preparation and verification used only public source code and synthetic fixtures. Do not create an empirical ROOT_GO just to test the pipeline. There is no test-data reader or inference-candidate generator in this package.

The model is the minimum 12-descriptor linear softmax baseline, not the 71-descriptor linguistic multiview model, a natural-author style model, 1280 natural works, generic stage 1 acceptance, personalization, or a human writing-quality model. The 384 assistant-authored fictional drafts remain controlled artifacts. Training and development retain 256 and 64 original slots across 32 and 8 families; all 64 slots in the 8 test families remain sealed.

No pair-preference judgments have been collected. The only admitted training call is fit(train_rows, preference_pairs=[], epochs=150, lr=0.05). All condition and preference weights start at zero. Condition loss weights each eligible training family equally, then each eligible row in that family equally. Scaling is fitted on eligible training rows only. Preference weights must remain exactly zero. They must never be described as a learned preference model, and fabricated independently-reviewed preferences are forbidden.

## Frozen implementation and one logical fit

- controller_v03.py is a new isolated version copied from frozen style-edit-controller-v02/controller.py. The old directory is never edited. The only behavioral changes are exact six-key semantic-review receipts (no extra label channel) and boolean-only constant-feature masks when loading checkpoints; its version/schema identifier changes to 0.3
- labels_v02.py is a byte-identical copy of the authorized public v02 operational label code
- FILE_HASHES.json pins every executable, protocol, tests and synthetic evidence file by byte size and SHA256. The ROOT_GO must independently bind its exact file hash and protocol.json hash
- Only one C.fit invocation occurs. A separate independent numerical recurrence replays the same zero-initialized, 150-step full-batch update to verify the saved weights, with maximum absolute weight difference <=1e-12. This is a verification computation, not an alternate candidate model or a second selected fit
- There is no hyperparameter search, random initialization, early stopping, seed selection, development-based retry, threshold change or post-development editing of the frozen implementation. Development metrics are diagnostics only
- The first gradient must be nonzero, final condition weights must be nonzero, all weights finite, the saved checkpoint must round-trip exactly, and u must be exactly zero
- C.edit loads its actual file-hash-bound checkpoint. Synthetic tests verify actual selection, candidate-order invariance, strict candidate fields, strict semantic-review receipts, abstention, and refusal to use synthetic checkpoints in empirical mode. These are software tests, not empirical K=4 candidate generation

## Exact TRAIN+DEV handoff

The coordinator creates a separate sanitized input directory containing exactly the five required input files below plus ROOT_GO.json. The wrapper opens only those fixed names; it never discovers original drafts, family plans, blind packets, test labels or other private files. The coordinator is responsible for preserving and hashing the frozen original authoring and split manifests. Hashes prove binding, not that the underlying reviewers were independent or correct.

1. train_dev.json

Top-level keys must be exactly:

- schema: "sanitized-controlled-train-dev/v1"
- provenance: "assistant_authored_controlled"
- source_draft_manifest_sha256: SHA256 of the frozen original-draft manifest
- family_split_manifest_sha256: SHA256 of the frozen original family/split manifest
- slots: all 320 original TRAIN+DEV slots, in a frozen deterministic order

Each slot has exactly these keys:

- id: unique nonempty opaque string
- family: nonempty family ID; no family may cross partitions or genres
- partition: "train" or "dev" only
- genre: one of general_explanation, process_description, event_summary, reflective_commentary
- status: completed, generation_failed, technical_failed or unfinished
- text: exact completed prose, otherwise null
- text_sha256: UTF-8 SHA256 of text, otherwise null
- mainpoint_exact: original exact main claim, otherwise null
- fact_ids: ["P1","P2","P3","P4","P5","P6"] for completed slots, otherwise []
- review_id: unique opaque ID for the corresponding pair of blind reviews, otherwise null
- realized_condition: short_early, short_late, mixed_early or mixed_late only when the frozen dual-review adjudication accepts; otherwise null
- exclusion_reason: null for eligible rows; nonempty explicit reason for excluded or unproduced slots

There must be exactly 32 train families and 8 development families, exactly eight original slots per family, and train/dev genre balance 8/2 families per genre. Do not include nominal_target, pass, template, test rows, original content plans, or unrelated metadata. Technical failures stay in their original denominators. No resampling, replacing or hiding failed slots.

2. labels_a.json and labels_b.json

These are coordinator-projected TRAIN+DEV-only subsets. Never hand the fit worker the original 384-row files, which include TEST. Each has exactly {"schema":"sanitized-blind-reviews/v1","reviews":[...]}. Each reviews list covers exactly the completed exported slots, including disagreements and excluded drafts. No test review may be present. Each review has exactly the public labels.py adjudicate_pair fields:

- review_id
- rater_id
- fact_labels: keys P1 through P6, each preserved / changed_or_missing / uncertain
- semantic_axes: facts, unsupported_additions, negation, modality, quantifiers and scope, each pass / fail / uncertain
- mainpoint_is_real_main_claim: yes / no / uncertain
- rhythm_label: short / mixed / outside_support / uncertain
- placement_label: early / late / outside_support / uncertain

The wrapper recomputes observed_properties from each text and mainpoint, runs the frozen adjudicate_pair function using both raw reviews, and requires its realized condition to exactly match the export. It does not infer a label from a nominal request, accept an isolated "verified" boolean, or adjudicate a disagreement itself. Both reviewers must preserve every fact, pass every semantic axis, agree on supported actual structural properties, and confirm the actual main claim. Missing, uncertain, disagreeing or unsupported outcomes remain excluded.

3. label_receipts.json

Exact structure:

- schema: "dual-blind-label-receipts/v1"
- dataset_file_sha256: byte hash of train_dev.json
- review_files_sha256: {a: byte hash of labels_a.json, b: byte hash of labels_b.json}
- review_scope: "all_completed_train_dev_slots_only_test_sealed"
- raters: two entries in a,b order, each with exactly rater_id, review_context_id, independent_of_authoring:true, independent_of_fit:true, blind_to and review_file_sha256
- blind_to must be ["nominal_target","template","pass","partition","model_scores","other_rater_labels"] in that order

The top-level receipt also requires projection_receipt, with exactly:

- schema: "root-train-dev-review-projection/v1"
- actor: "root"
- original_review_files_sha256: {a: hash of the frozen original 384-row A file, b: hash of the frozen original 384-row B file}
- original_review_row_counts: {a:384,b:384}
- subset_review_files_sha256: identical to the top-level review_files_sha256
- selected_review_ids: sorted exact list of opaque review IDs for the completed TRAIN+DEV slots
- selected_review_ids_sha256: SHA256 of that list canonicalized by controller_v03.canonical
- test_rows_exported: integer 0

Original source files stay coordinator-only. Their hashes are attested references, never paths to open. No original path field is allowed. The wrapper verifies subset contents, exact selected IDs and every subset hash against the root-approved projection receipt, without reading original files or TEST rows. This cannot independently verify the withheld source-to-subset projection; root's custody and attestation are required. No nominal targets enter these files.

Rater IDs and review-context IDs must differ. The corresponding review file must contain exactly that rater ID. Root approval binds the entire receipt's canonical-object SHA256. These root-approved provenance attestations are required but cannot mechanically prove true independence or semantic correctness. No claim of a semantic guarantee is warranted.

4. storage_receipt.json

The worker may not inspect other controlled directories. Therefore the coordinator measures all controlled artifacts, including authoring v1/v2, blind-label derivatives, sanitized exports and any transient copies, then reserves the package's remaining output budget. This receipt must be fresh (<=10 minutes), root-approved and exclusive: no other controlled writes may occur until root releases the reservation.

Exact keys and values:

- schema: "controlled-artifact-budget-receipt/v1"
- actor: "root"
- measured_at_utc: ISO8601 timestamp with timezone
- excluded_root: "/workspace/shared/style-controlled-fit-v01"
- external_controlled_bytes: measured integer bytes for all controlled artifacts outside excluded_root, INCLUDING this input directory and GO/receipt allowance
- controlled_byte_cap: 33554432
- exclusive_budget_reservation: true
- reserved_output_bytes: 1048576
- no_other_controlled_writes_until_release: true

The wrapper counts every byte in its own directory without following symlinks. External measured bytes + its current tree + 1 MiB reserved outputs must fit under 32 MiB. After the run it checks actual combined usage and output size. This is coordinated snapshot accounting, not an OS-wide disk quota. Root must ensure the count and exclusive reservation are true; provider transcripts are not locally measured. The package never reads forbidden directories to validate the receipt. A cap amendment requires a revised protocol/package and fresh approval, not a silent command-line override.

5. ROOT_GO.json

Exact keys:

- schema: "root-controlled-fit-go/v1"
- action: "CONTROLLED_STYLE_TRAIN_GO"
- actor: "root"
- run_id: a unique 1–64 character alphanumeric/underscore/hyphen identifier
- package_manifest_sha256: byte hash of this package's FILE_HASHES.json
- protocol_sha256: byte hash of protocol.json
- input_sha256: exact five-key map for train_dev.json, labels_a.json, labels_b.json, label_receipts.json and storage_receipt.json, each a SHA256 of that file's final bytes
- review_approval_sha256: SHA256 of label_receipts.json parsed and canonicalized by controller_v03.canonical
- training_scope: "single_condition_only_fit_train256_dev64_no_test_no_inference"
- issued_at_utc: root approval timestamp

The invoking root separately provides the exact ROOT_GO file SHA256. A self-declared actor field alone does not establish authorization. This is an auditable engineering guard, not a cryptographic identity service or an operating-system isolation boundary. Caller authorization and custody of the supplied hash remain essential.

## Support gate and fixed metrics

Before a fit, every realized condition must have >=16 distinct eligible training families and >=4 distinct eligible development families. Two rows from one family count once. If any threshold fails, stop without fitting. Do not tune thresholds, relabel toward nominal targets, replace drafts or silently broaden support.

For each train/dev partition, report:

1. Family-macro cross-entropy: mean of per-family mean -log predicted probability of actual label, over families with at least one eligible row
2. Family-macro accuracy: mean of per-family mean correctness on eligible rows; ties deterministically choose the first frozen condition
3. Family-macro coverage: mean of eligible/original slot fraction over ALL original families, including zero-eligible families

Always report eligible/all row counts and eligible/all family counts beside conditional metrics. Save per-family components. Zero-eligible families are excluded from conditional CE/accuracy, included with zero in coverage. Exclusions and per-condition family support are separate audit outputs. Do not claim conditional accuracy describes the dropped drafts.

The exact-threshold comparator independently recomputes the public definition from text/mainpoint and uses its one-hot class with a 1e-15 floor then renormalization for CE. Its accuracy on accepted labels is tautologically 1 because the label definition itself requires agreement with those exact thresholds. It is explicitly a class-definition comparator, not evidence of human style, preferences, natural-author attribution, language understanding or added semantic preservation. Its coverage shares the same dual-review gate; semantic effects must not be attributed to the learned ranker.

## Execution, budgets and failure semantics

Only after root approval and a frozen independent code/protocol review:

PYTHONDONTWRITEBYTECODE=1 python fit_wrapper.py --run --input-dir /ROOT/PROVIDED/SANITIZED/DIRECTORY --expected-go-sha256 ROOT_SUPPLIED_64_HEX_HASH

Never run that command with placeholders or invented approval. The current package has no empirical ROOT_GO, inputs, run marker or empirical checkpoint.

The Linux process is pinned to at most two available CPUs, capped at 512 MiB address space and 60 CPU seconds, with a 60-second wall alarm encompassing fit, replay, checkpoint and diagnostics. No networking, remote writes, downloads, external APIs, new drafts or candidate generation occurs. Imported code has no I/O side effect.

The wrapper validates all hashes, labels, support and budget before creating run_state/EMPIRICAL_START.json with exclusive creation. That global marker is never deleted. It prevents another run even with a different run_id. Output directory and every file are exclusively created. A crash, timeout, failed verification, already-existing output or uncertain start fails closed. Do not retry or remove markers; root must review the failure and authorize a new version if a repeat is justified. Only a matching EMPIRICAL_COMPLETE.json and verified FIT_RECEIPT.json make a checkpoint available for the next separately approved stage. A partial checkpoint or FAILED.json never does.

Outputs are a condition-only checkpoint, a detailed fit receipt, and completion/failure marker. The wrapper does not autonomously deploy the model. Root must retain the frozen GO, all hashes and source provenance with those outputs.

## TEST and inference remain separately sealed

No TEST evaluation runs here. A future, separate one-time CONTROLLED_STRUCTURAL_TEST_GO must bind the exact completed-fit receipt and checkpoint, the frozen evaluation code/metrics, full 64-slot sealed test export, raw dual-label receipts and a globally exclusive TEST_START marker. The evaluator must refuse any fit, tuning, replacement or reread-for-selection after opening the test. Eight test families support exploratory family-level feasibility only, not confirmatory generalization, a semantic guarantee or stage-1 acceptance.

Future K=4 inference candidates, generator configuration, requests, independent candidate-semantic reviews and candidate selection comparison arms require their own frozen package and authorization. None are generated now. All comparison arms must use identical candidate sets and the same fallible independent semantic gate, and the gate's misses/false rejections need independent evaluation. The current tests use explicitly synthetic strings and synthetic receipts solely to exercise software contracts.

## Reproduction of current synthetic verification

PYTHONDONTWRITEBYTECODE=1 python -m unittest -v test_fit_wrapper.py

The tests create synthetic in-memory rows and temporary synthetic checkpoints under this package, never read empirical data, never claim fixture reviews are actual independent judgments, never create an empirical GO or empirical run marker, and clean temporary files. synthetic-evidence.json records the bounded synthetic fit/replay check. synthetic-only.weights.json is visibly synthetic and refused in empirical editing mode.
