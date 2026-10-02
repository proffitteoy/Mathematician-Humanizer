# Experimental natural sequence implementation

This public source was reconstructed after the execution workspace replacement. It is a separately named experimental module, leaving the original instrument's synthetic-only learned-model contract untouched. It predicts fixed candidate-instrument observations; it is not a validated style, author, streaming, or discourse model.

## Fresh validation

The replacement runtime uses Torch2.3.1+cpu and NumPy1.26.4. Run:

    runtime/venv/bin/python run_synthetic_checks.py

Fresh checks:66 primary implementation/watchdog/freeze/profile-count tests,23 independent math/trainer checks,8 independent cache-adapter checks, and2 profile-prerequisite checks pass. No natural cache, prospective TEST body or davinci body was read. Primary tests perform no optimizer fit. Independent trainer checks use two tiny synthetic Adam fits in temporary directories to verify deterministic checkpoint restoration; these are not natural empirical fits.

## Modules

- schema: private audit records and exact five-field prefix packets; tensors own prefix-only storage, have no trailing padding and cannot expose document suffixes
- cache_adapter: verified TRAIN/DEV descriptor firewall; exact71-channel provenance,68 safe values plus2 structural counts; original validation flags, typed missingness and unknown opportunities preserved
- transforms: TRAIN-only frozen hierarchy weighting, declared transforms, constant/unobserved value freeze,50-independent-component output gate and fixed90% common-support gate
- models: F1/Fcov/F2/F3/F4; mask/opportunity, pure-mask and length views; active capacity brackets; independent-family states
- objectives: model-independent paired population, question/answer/arm/unit sampling, family-balanced loss and component bootstrap after three-seed averaging
- train: fixed Adam settings, permitted DEV early stopping, permanent attempt/failure ledger, checkpoint restoration and resource checks
- plan: all72 registered core runs and deterministic construction after TRAIN-only eligible-target selection
- freeze: immutable hashes, complete-run requirements and controlled-evaluator handoff
- report: aggregate-only serialization, rejecting private record objects and known raw/per-record payload fields

## Information and numerical details

The full70 first-moment/joint-support summary has15331 entries; covariance adds2485. Pairwise sample covariance uses joint-specific means and explicit joint-centered products in128-pair chunks. It does not assume positive semidefiniteness, invert covariance, clip TEST extremes or substitute marginal means.

Packets always retain70 coordinates. TRAIN-unobserved/constant value paths remain frozen zero across all splits. Their identically-zero value/moment network paths are removed internally while masks, opportunities and shared support remain available as specified. Heads contain only eligible target coordinates, then a fixed scatter returns70-wide predictions. Entire unscored family branches disappear. Active widths are recomputed from these shapes before fitting; current all70 parameter counts are architecture upper bounds.

The two structural fields are direct counts with unknown opportunity denominators. A successfully measured structural zero stays an observed direct count without inventing an opportunity. Ratio/sensor zeros still require positive audited opportunities.

Preprocessing gives every declared question and answer variant a fixed HUMAN/ChatGPT half-slot before masking. Blank arms contribute no unit mass and never reassign their slot. Observed-channel mass is normalized only after these weights are fixed. Main training/scoring still uses jointly supported answer variants.

F1/Fcov/F2 are permutation invariant. F3 adds the last packet; F4 adds a GRU. Shuffled-training F4 is scored by averaging10 permutation losses, not predictions. Full-family ablations remove every associated value, mask, opportunity and pair field. Independent-family states never receive another family's values or cross-family value moments; all nuisance local inputs remain available. Its deterministic nuisance summaries currently differ from sharedF4 pair-support summaries, a limitation that must be disclosed or prospectively resolved before interpreting cross-family gains.

## Unrun and blocked

Natural optimizer fitting and prospective evaluation remain unrun. The lost partial extraction was not complete or verified. A resource-only natural pass must wait for exact input restoration, completed extraction, independent integrity verification and a fresh gate review. Retrospective permutation likelihood, sparse/stability extensions, block-model fits, smooth cross-fitted residualization and natural annotation reliability are explicitly unrun. None can substitute for failed core evidence.

## Prospective next-unit support clarification

Input normalization still uses every declared TRAIN unit with the fixed hierarchy. Output eligibility now counts only components with observed next-unit targets at index1 or later; first units cannot satisfy the50-component target gate. All-unit input support and next-unit target support are reported separately. This coordinator-approved clarification predates all natural fitting/test access and includes first-unit-only and49-versus50 boundary regressions. Actual active parameter counts must be recalculated after this gate.

Target-component counts also use the trainer’s exact jointly supported HUMAN/ChatGPT answer population. A monotone fixed-point application of the same eligibility rule removes any output whose apparent support disappears after paired-variant restrictions; no threshold or population is selected from outcomes. Unpaired or blank counterpart arms cannot create supervised target support.

Cost forecasts explicitly expose training question/prefix draws, available training prefixes, jointly scored DEV prefixes and forward-call counts (including10shuffle calls). DEV counts can be exact from independently verified commit-unit metadata when the direct span target is TRAIN-eligible; otherwise they are labeled upper bounds. Additional DEV bodies are not read for this computation. No speculative compute optimization is applied before profiling.
