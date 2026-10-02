# Prospective protocol for learning natural Chinese measurement sequences

Version 1.1, 2026-10-02. Prospective covariance clarification; see AMENDMENT_1_COVARIANCE.md. Design only. No empirical extraction, fitting, test inspection, new download, owner-text use, or remote write is authorized by this document. The coordinator must approve execution. This protocol supplements, never replaces, the frozen cohort protocol.

## 1 Decision and endpoints

The implementable core is a label-blind, small-data conditional-prediction experiment. It learns from natural released answers, not templates, rule-generated labels, rewritten examples, or synthetic text. Synthetic fixtures are used solely to test the implementation.

Primary endpoints on the fresh seen-generator panel:

1. Explicit covariance increment: `Delta_cov = L_mean - L_cov`
2. Learned set increment beyond declared second moments: `Delta_set = L_cov - L_set`
3. Order increment beyond those same moments and set representation: `Delta_order = L_set - L_order`

`L_mean - L_set` remains a descriptive total composition increment. It is not uniquely attributed to covariance.

`L` is the family-balanced next-unit squared prediction score defined below. Positive increments mean lower error. Report human, ChatGPT, their equal-arm mean, and their within-question paired difference. The primary target is the equal-arm mean, with human/ChatGPT differences secondary. A 1% relative reduction against the comparison model is the predeclared smallest useful predictive increment for this pilot, an engineering choice rather than a linguistic truth. Define relative reduction as (aggregate baseline loss − aggregate new loss) / aggregate baseline loss on the same paired question population, after equal-arm and seed averaging; never average per-document percentage gains. If aggregate baseline loss is zero, report the absolute increment and relative reduction as undefined. Bootstrap this exact aggregate ratio. Report point estimates and component-bootstrap intervals regardless of threshold. For the three primary endpoints use 98.333333% intervals (Bonferroni two-sided family alpha0.05); do not search alternative thresholds after seeing test.

Secondary endpoints are last-unit versus longer-memory increment; cross-family versus independent-family dynamics; source transfer; davinci transfer; length/missingness sensitivities; and exact-bag conditional order log score. Source-block analyses are explicitly low-support exploratory endpoints. No detector AUROC, accuracy, or human-class cluster separation is an acceptance criterion.

The primary score estimates conditional means of fixed instrument outputs. It does not estimate a full joint density, human quality, a causal production effect, or identifiable author/style factors.

## 2 Frozen population and permitted access

Use the frozen `m4_chinese_paired_20261002` release, exact pinned raw files, and existing private identity manifest. Read-only audit metadata are permitted now; raw/test bodies are not needed to review this protocol.

- Training: 1,806 question families, 1,816 answer records, human and ChatGPT only
- Development: 590 families, 591 answer records, human and ChatGPT only
- Seen-generator test: 296 families, 297 answer records, human and ChatGPT
- Generator-transfer test: 295 families, 296 answer records, human, ChatGPT and davinci
- davinci train/dev and davinci on the seen-generator test are not processed for this experiment

This maximum planned measurement population is 6,296 arm-texts: 3,000 human, 3,000 ChatGPT, and 296 transfer davinci. Blank/unusable arms remain explicit missing records, not replacement observations. The two whitespace-only davinci outputs may or may not occur in the transfer panel; do not inspect them now to find out.

Use typed `(source, type(source_ID), source_ID)` question identities; preserve answer-variant identity and component membership. Join through original offsets and frozen composites, never row order. Human is stored/scored once per answer variant. For each view, compute within-question means over jointly supported answer variants before giving each eligible question equal weight. Copy components are inference clusters, not equally weighted observations. No support-based resplit, seed search, or replacement of inconvenient records.

Existing support counts describe the preparation segmenter. Actual instrument counts may differ. Publish the crosswalk and denominators without changing either definition retrospectively.

## 3 Measurement and model data contracts

### 3.1 Audit record kept outside the model

Every record retains private provenance: source archive/member and byte offsets, typed question identity, answer identity, component, split/panel, arm, exact source/projection/profile/annotation hashes, measurement schema, restoration runtime, view availability, and failure ledger. These are required for joining and audit, forbidden as learned inputs.

Keep the exact 71-channel global and sentence measurements: value, numerator, denominator, opportunity count, status, missing reason, and comparison eligibility. Current `comparison_eligible=false` is not changed merely because a tensor exists. An approved experimental analysis adapter may use `candidate_unvalidated` observations with explicit scope; it must not relabel them validated or synthetic, or bypass the old synthetic-only learned module.

### 3.2 Local safe values

`local_value_ids` is the exact ordered 71-ID catalog minus:

- `zh:lexical.content_overlap`
- `zh:lexical.trigram_reuse`
- `zh:syntax.initial_pos_reuse`

The remaining 68 values are sentence-local formulae. Supplement them with two separately named structural measurements: original sentence span codepoint length and nonpunctuation lexical-token count T. They remain length/opportunity measurements, not new independently validated style channels. T is unavailable when parsing cannot establish it; original source-span length remains a direct operational segmentation measurement when a source unit exists.

Primary targets are these 68 candidates and the two length measurements. Train-defined constant/unobserved channels are unscored and listed, not silently replaced. The three excluded history channels remain descriptive measurements and may be prospective secondary *targets*, but they do not enter the core objective or input. No pretrained lexical/semantic embeddings, raw token forms, prompt text or question-ID embeddings enter the core.

### 3.3 Mask and opportunity handling

`observed[j] = value[j] is not null`. Preserve missing reasons and unknown opportunity counts in the audit record. Observed zero requires an audited positive opportunity. Do not add epsilon to denominators or convert failed/missing measurements to observed zeros.

For computation only, set unavailable standardized values to zero and concatenate the explicit observation mask. This is a neutral tensor placeholder, never a measurement. Add the log1p opportunity count only where known, with its separate known-opportunity mask. Unknown opportunity becomes a tensor placeholder plus `known=false`, not an asserted zero. No detailed failure reason is a core model covariate; reason-specific analyses remain in the evaluator.

All models receive the same allowed masks/opportunities. Parallel mask-only and length-only models are mandatory. For a feature-family ablation, remove that family's values, masks, opportunities, count summaries, encoder channels, and all pair means/support/covariance entries touching it together. There is no graph branch through which removed information can survive.

### 3.4 Forbidden feature fields

Reject by schema, do not merely ask implementers to ignore: original sentence/block indices; absolute spans/start/end; source/answer/question/component IDs; hash values; source/generator/arm labels; file paths/row order; original-next edges; coverage and parse-audit totals; document-total length/counts; raw complete-source global vectors; future value rows; future masks; final sentence count; normalized original position; original candidate storage position; any graph or node IDs.

Sentence codepoint *length* may be derived from span width; the span location must then be dropped. Prefix unit count is observable and shared by all prefix baselines. In a retrospective bag test, total bag cardinality is observable and shared. Neither permits a candidate's original ordinal.

### 3.5 Prefix packet

A model call consumes only `{prefix_values, prefix_observed, prefix_opportunity, prefix_opportunity_known, prefix_unit_count}` for one cut with t≥1. Value order is the exact68 safe IDs followed by original sentence-span codepoints and lexical T. `prefix_values` are already train-transformed/standardized with masked0 placeholders; opportunities retain original nonnegative counts with known flags, and encoders apply log1p exactly once. The supplemental lengths have no invented opportunity denominator; if their extraction contract supplies none, opportunity-known is false. Derived first/second-moment summaries are computed inside the model from this packet. With70 coordinates, the matched first-moment/support vector has6×70+6×2485+1=15,331 entries; adding covariance values gives17,816. Covariance validity is already shared, not duplicated as extra information. The target and target mask exist only in the loss/evaluator. Construct a separate variable-length packet for each prefix; do not pass full-document packed lengths, trailing padding shape, final count or position/N to the model. Batch-normalization across full documents is prohibited. Randomize batch and storage order independently of arm/source.

This is prediction on supplied complete-unit annotation sequences. Full-source operational segmentation and resource guards are not certified causal, even though local parsing receives one complete sentence. No live-prefix, streaming or intervention claim is allowed. Implementing an actual-prefix resegmentation/parse producer would be a distinct preregistered experiment and resource request.

## 4 Transformations and training measure

Fit all transformations only on the permitted training arms, with equal question then equal answer then equal arm then equal unit weight. Use log1p for the two lengths and other nonnegative unbounded count/geometry channels; use the recorded raw scale for proportions and normalized entropies. List transformations by ID in the frozen config. Do not clip test extremes. Center/scale by training means and standard deviations; an exactly constant or wholly unobserved training coordinate is excluded from scoring and its value path is frozen to tensor0 in every split; its declared masks/opportunities remain part of the separately audited nuisance path. Do not invent a fitted scale or expose unseen test variation through an untrained value channel. Do not use test or davinci values to choose channels.

A target channel is eligible for learned prediction if its training observations span at least 50 independent copy components; this is a practical minimum to fit an output, not a power certificate. Rare channels remain in the measurement report and have no predictive claim. The gate applies per channel, not to all texts or all views. Recompute eligibility independently in each source-holdout fit using only its training source.

For target sentence t+1, calculate squared error per observed channel, then average within the eight original measurement families and a ninth structural-length family. Average over observed eligible families. This prevents 27 dependency proportions outweighing an entire rhythm view solely by count. All models use the same target coordinates and masks. Report per-family scores and coverage; a pooled score never implies that every family is supported.

Average valid target positions within a document; average jointly eligible answer variants within a question; average eligible questions equally; average H and ChatGPT equally for the primary overall score. Training minibatches sample questions uniformly, answer variants uniformly within the question, arms with probability one half, then valid target positions uniformly within that document. Incomplete paired support is handled with the declared view-specific question set, never with a model-specific set. A model's numeric failure invalidates that comparison rather than deleting its hard rows.

Documents with one unit stay in the cohort and global/descriptive analyses. They have no next-unit transition. Two-unit documents contribute one transition and the two-unit permutation experiment. Longer-memory comparisons require prefix length at least two because that is their mathematical opportunity, not an eight-unit corpus gate. Report both all-transition and prefix-at-least-two results; early transitions must not conceal or inflate the latter.

## 5 Fixed model ladder

All models are trained from scratch and label-blind. The explicit pairwise-moment input increases parameter counts; record actual counts and verify the unchanged memory/CPU cap rather than continuing to assume the old small-input runtime. The initial registered architecture width is 32. No pretrained LLM, detector, author embedding, external download or generated-text augmentation is used.

- **F0 Training mean:** unconditional per-target training mean. Reference for absolute predictability; not the comparator for the main order claim
- **F1 Matched first moments:** the common first-moment/support summary defined below, through a two-layer width32 MLP to all targets. It contains no second products or temporal markers
- **Fc Explicit second moments:** the exact F1 summary plus the declared centered pairwise covariance values and their shared validity mask, through a width32 MLP to all targets. This is the explicit covariance baseline
- **F2 Set composition:** the same first-moment/support summary AND exact covariance summary supplied to Fc, plus a shared width32 point encoder `phi(local packet)` with sum/mean pooling. This tests information learned from the multiset beyond the registered first/second moments
- **F3 Last plus set:** F2's same summaries and the complete last local packet, followed by a width32 head. Isolates recency from longer memory
- **F4 Ordered state:** F2's same summaries and a width32 GRU over exactly the same prefix packets, followed by a width32 head. No extra covariance information is exclusive to F4

### 5.1 Explicit observed-pair covariance contract

Use the fixed70 input coordinates (68 safe local channels plus two structural lengths), after the train-only transformations. For each upper-triangle pair j≤k, define `I_jk={i≤t: observed_ij and observed_ik}`, `n_jk=|I_jk|`, and the two means `mu_j|jk` and `mu_k|jk` over that identical joint-observed set. If n≥2, define `C_jk = sum_{i in I_jk}[(z_ij−mu_j|jk)(z_ik−mu_k|jk)]/(n_jk−1)`. For j=k this is the usual sample variance. For n=0 both pair means are unavailable; for n=1 the pair means exist but covariance is unavailable. No epsilon denominator, missing-value-as-zero product, or whole-document centering is allowed.

The common first-moment/support summary supplied to F1/Fc/F2/F3/F4 is:

- Each coordinate's masked value mean, observed fraction C_j/t, log1p(C_j), mean log1p opportunity over known opportunities, known-opportunity fraction K_j/t, and log1p(K_j)
- Each pair's two joint-observed means, its n_jk/t and log1p(n_jk), a `pair_mean_known` indicator and a `covariance_defined` indicator
- log1p(t), never total document N

Unavailable pair means/covariances use tensor0 with their separate availability indicators. Every comparator gets the same support and covariance-defined indicators, including F1 without covariance values. Therefore Fc cannot improve just by disclosing pairwise mask counts, a different observation subset, or pair-conditioned first moments. Covariance itself uses only the transformed *values*, not missingness, parser-reason codes or opportunity magnitudes. All70 coordinates remain in the fixed schema; constant/unobserved training value paths stay frozen0 as already specified.

There are70×71/2=2,485 declared variance/covariance entries, without fitting pair selection. This is an observed-pair second-moment array: with heterogeneous missingness, different entries condition on different observed subsets and the assembled array need not be positive semidefinite. Do not invert it, run Cholesky/eigen style-factor claims, pretend it is a complete-population covariance estimate, or interpret off-diagonal entries causally. Shared-denominator POS/dependency compositions remain constrained. The estimate tested is the predictive increment of these explicit centered second-moment statistics beyond matched first moments/support.

No additional empirical covariance fitting is needed to create this deterministic prefix summary. It must be recomputed from each actual visible prefix, not sliced from a full-document covariance matrix. Its low-support entries may be noisy; missingness-only controls and common-support sensitivity remain mandatory. Report Delta_cov on all supported transitions and separately on prefix t≥2; two-unit documents are retained although their only forecast prefix cannot estimate covariance.

First verify Fc versus F2 active parameter counts are within10%, because Fc→F2 is now a primary contrast. Keep F2 width32 fixed; if Fc width32 fails this band, choose Fc's width deterministically from architecture parameter formulas to reach the smallest active-capacity bracket of F2 before any fitting. This replaces the same three Fc fits, adds no search, and is unrelated to dev/test outcomes. If discrete widths cannot meet the band, report the upper-bracket mismatch and withhold an unqualified capacity-separated set-beyond-moments claim. Then F1-wide must actively capacity-bracket BOTH realized Fc and F2, with counts within10% when feasible. Their shared large summary should make these counts close, but this must be verified from actual implementation before fitting. Choose the first-moment width deterministically from parameter formulas, never dev/test scores. If no single width brackets both within10%, choose the smallest first-moment architecture with at least the larger active parameter count, report both mismatches, and treat it as a conservative capacity upper bracket; do not add unbudgeted fits. Do not pad unused weights. F2-wide still brackets F4.

Fc versus F1 is the explicit covariance increment; F2 versus Fc is learned set information beyond the registered second moments. F4 versus F2 is the primary order increment conditional on the same covariance summary. F3 versus F2 quantifies last-unit information; F4 versus F3 tests longer memory. F1 versus F2 compares means with a learned multiset representation, not uniquely covariance. Saved parameter counts and optimizer budgets are mandatory. A covariance claim requires surviving Fc versus the matched F1-wide comparison; the total composition claim must also survive F2 versus F1-wide. An order claim requires surviving F4 versus F2-wide. If exact matching is impossible, report the mismatch and an active-parameter upper bracket.

Models train with Adam, learning rate 0.001, weight decay 0.001, batch32 questions, gradient norm cap1, maximum100 epochs, and patience10 on development family-balanced score. One epoch contains exactly the number of eligible training questions in independently seeded question draws, grouped into minibatches; it is not one pass over every sentence. Use fixed seeds 1701, 1702, 1703, and compare mean losses across seeds; seed counts are not independent data samples. Width, optimizer and preprocessing are not searched on test. Early stopping chooses an epoch on permitted dev only. Record every attempt, including divergence; no seed replacement because of result quality.

Minimum initial fit is F1/Fc/F2/F3/F4 plus F1-wide and F2-wide for each seed. F0 needs no optimizer. MSE predicts conditional means; do not describe the GRU hidden state as a discovered style coordinate.

## 6 Mandatory controls and interpretable learning

### 6.1 Information controls

Run F1, F2 and F4 using only masks, opportunity-known masks and known opportunities. Values are removed, not set to their real zeros. Remove every value-dependent pair mean and covariance as well; retain the exact pair-support counts and defined/known indicators, so the nuisance control has identical support information. Pure-mask controls retain pair co-observation patterns but not opportunity magnitudes. A separate pure-mask variant removes opportunity magnitudes. Run F1/F2/F4 with only the two length measurements, their availability and the moments computed only from those two coordinates; no linguistic pair means/covariances or linguistic masks remain in the length-only input. Report value-model gain beyond these controls, not just raw predictability.

Restrict a common-support sensitivity to records without parse/resource/alignment failures and to a core channel set selected solely for at least90% unit availability in *each* H/ChatGPT × source training cell. Keep that exact set at test, score shared observed coordinates, and disclose loss of population coverage. This is a sensitivity population, not a substitute main cohort. If no useful common set exists, report that rather than relaxing the threshold after test. Complete-case all68 is not required; it would mostly select long sentences because of100-token windows.

### 6.2 Order controls

1. Refit F4 with fresh random prefix permutations at each training presentation, target unchanged, and score10 fixed seeded prefix permutations and average their LOSSES for each target/document, not their predictions before computing loss. This estimates expected random-order score without introducing a prediction-ensemble variance-reduction advantage. This preserves available-prefix membership, values and masks while removing order, with the same architecture/capacity
2. Evaluate original F4 with shuffled prefix order, target unchanged; this is a perturbation diagnostic and may be out of distribution
3. Preserve the last unit and permute only earlier units. A surviving advantage may be pure recency
4. Apply synthetic fixtures with identical value bags and random independent target/order; order gains must disappear in expectation. These test code, not natural-text results

The F2 prediction must be numerically invariant to prefix permutations. The F4 shuffled-training result is compared with F4 and F2; do not attribute a simple F4 perturbation loss entirely to natural dynamics.

### 6.3 Cross-family dynamics

Fit an F4-independent-family control with separate states for each family. Each target family can use only its own past values plus the same permitted length and mask control branch; no other family's values are available. Remove all pair means and covariance entries touching another value family; otherwise the shared moment summary would bypass this control. The separately declared mask/length branch remains identical. Match active parameter budget to the shared model. Compare per-target-family losses to the shared F4 and report the extra inputs explicitly. This tests cross-family predictive dependence, not psychological coupling. A compact ridge VAR with diagonal versus unrestricted/rank-limited cross-family lag coefficients may be added as an interpretable sensitivity; it is not necessary to replace the main set baseline.

### 6.4 Sparse selection subexperiment

After the dense ladder, an optional declared ablation adds nonnegative gates on standardized *value* families in both the prefix summary and sequence encoder, with L1 gate penalty over `{0,0.001,0.01}` selected by permitted development predictive loss. Apply value gates before all value-dependent summaries, including joint-observed means and covariances; covariance between gated values carries both endpoint gates. A precomputed covariance branch must not bypass a zero gate. Target scales/weights are fixed and cannot be gated down. Keep mask/opportunity/length controls in an explicitly separate branch. Such gates select value information conditional on that branch; they do not erase the whole family. Full-family ablations must remove all paths as specified above.

For selection stability, refit a low-capacity gated/linear variant on20 fixed half-samples of training copy components; report family selection frequency, effect direction where defined, held-out loss increment, and substitution among correlated families. Do not claim classical stability-selection false-discovery bounds without checking their assumptions. Do not name individual71 sensors independent axes.

This is a sparse prefix-global-plus-sequence ablation. It is not the unimplemented full-source-global + sequence + discourse model, and it creates no author labels.

## 7 Proper retrospective bag-conditioned order experiment

This is separately scored and clearly labelled retrospective. A document with N at least2 eligible local units supplies a multiset of the same allowed local packets to every comparator. All target candidates, including future candidates, are visible equally. Do not combine these scores with the prefix scores.

At each step k, select a measured-value equivalence class c from the remaining multiset R. A learned candidate score gives

`p(c | selected history, R) = sum_{j in c} exp(score_j) / sum_{j in R} exp(score_j)`.

Define one common target equivalence partition once, from exact equality of the FULL allowed local packets, including values, local masks and opportunities, before any comparator or ablation removes inputs. P0–P4 and every mask/length-only control score these same classes. A mask-only model may assign equal logits to several distinct target classes; it must not merge those classes and thereby score an easier event space. Identical full-packet candidates are exchangeable; their original IDs cannot create false ordering targets. Remove one member of the selected class. The product defines a proper distribution on observable multiset permutations. Uniform comparator probability is class multiplicity / remaining cardinality, so its document negative log probability is `log(N! / product_c multiplicity_c!)`. Fit and select using document negative log probability divided by max(N−1,1), a normalizer fixed by the conditioned bag. Report bits per N−1 choice slots and unnormalized bits per document, then family-balance. Do not divide by the realized number of nontrivial choices: duplicate order can change that denominator and destroy propriety. A common positive bag-fixed weight preserves the conditional scoring target. If all packets are identical there is no observable order opportunity; return uninformative support, not fake success or a loss for unknown identities.

Comparators:

- P0 uniform remaining-class choice
- P1 candidate packet plus coordinate means/effective counts of selected and remaining sets, with step count
- P2 candidate packet plus Deep Sets summaries of exactly those selected/remaining packets and step count
- P3 P2 plus last selected packet
- P4 P2 plus ordered GRU state of selected packets

P1–P4 receive the same full candidate information; only the declared representation restrictions differ. P1 is a mean-conditioned **placement** baseline, not a pure document-mean model. Use the same hidden width, fit regime and seed policy as the core, with an active-capacity bracket for P2 versus P4. P1 versus P2 is a secondary placement comparison, not a second unqualified means-versus-composition confirmation; if claiming it independently, add its own P1 capacity bracket in a separately budgeted revision. Mandatory P1/P2/P4 mask-plus-opportunity controls use exactly the full-packet target classes and scoring denominator. Do not rank a small cherry-picked negative candidate set: all remaining units are in the exact softmax.

Candidate storage order is freshly randomized before each step, with evaluation mapping kept outside the network. Original indices, spans, block IDs and first/last flags are prohibited. All three historical channels, full globals and graph edges are prohibited. Since resource-limit masks may encode original progress, the whole permutation view is unavailable for any record with cumulative/source resource failure or any local parse/alignment failure. Keep the record's other supported views. Positive local denominators and short-window masks may move with their candidate because they are candidate-local; retain mask-only P models to test them.

Mandatory tests: random candidate reindexing leaves probabilities unchanged; identical candidates have identical logits; normalized probabilities sum to1; sum over all distinct multiset permutations is1 on N≤6 fixtures, without recounting labeled permutations of tied packets; means/P2 remain invariant to selected-history permutation; no field named index/span/hash/source/arm reaches the model; adding/removing hidden future rows cannot change a prefix-task prediction; shuffled independent bags show no spurious order information.

The original-order probability tests predictive nonexchangeability of supplied measurements. It does not establish coherence, originality, human preference or a generator intervention.

## 8 Source blocks and hierarchy boundary

A secondary Baike-only view uses original blank-line source blocks, preserving CR/LF provenance and listing untyped source role. No blank lines are synthesized, and Web is not assigned a semantic single-paragraph label.

For each block, use current-block local-value means/dispersion, observed counts, block sentence count, and first/last *within-block* local packets. These summaries are a declared extra representation, not the71 global sensor vector. Internal sentence order is preserved when the whole block is moved. In version1.1 do not fit a separate block-order ladder: its optional optimizer allocation is replaced by the explicit covariance stage. Keep bounded train/dev descriptive block summaries and sentence/whole-block perturbation diagnostics; report them as exploratory measurement descriptions, not fitted block-order likelihood results. Fitted block-order learning requires a later separately approved substitution or budget. Retain the already frozen preparation-only test support counts as a feasibility warning, but produce no new test block-score estimates in this version. Train/dev descriptive intervals do not establish broad paragraph generalization.

Distinguish perturbations: sentence shuffling within each block holds block membership fixed; permuting complete blocks holds internal sentence order fixed. Raw original block ordinals, original document positions, native graph size and unavailable rhetorical labels are excluded. A later flat-versus-block-reset sequence comparison would have to expose the same observed boundary markers to both models and remain on the same Baike subset; it is unrun and outside this version's fit allocation.

This measures released block organization and observed feature transitions. Entity continuity, implicit relation type, claim/evidence support and typed rhetorical hierarchy are not measured. `discourse_graph` is null with reason `no_validated_M4_producer`. No substitution by UD, lexical recurrence or topology is allowed. The typed GCDT quotient is the future structural contract, not an input available now.

## 9 Estimands and lengths

### 9.1 Total paired association

For observable f, use `D_total(g) = mean_q mean_joint_answer_variants [f(q,r,g) - f(q,r,H)]`, separately by source and on the declared finite cohort mixture. For prediction, f is the document-level composition/order increment or loss. Use the same human observation and same supported variants in each comparison. This retains naturally different lengths; it is observational, not a causal total effect.

### 9.2 Length-conditioned sensitivities

Keep the original outcome and define a predeclared close-length paired population: both arms nonblank, original Unicode codepoint lengths have ratio in[0.8,1.25], and their actual measured sentence counts lie in the same bin `{1,2,3–4,5–8,9+}`. Keep exact within-question pairing; reweight variants within eligible questions. Report this conditional association and actual coverage, including zero support, with no claim of nonparametric same-question/same-length identification.

For a smoother length-adjustment diagnostic, fit one arm-blind ridge regression for each outcome/feature on training H+ChatGPT, separately by source, using `[1, log1p(chars), log1p(chars)^2, log1p(sentences), log1p(sentences)^2]`, penalty1 excluding intercept. For model losses/increments, obtain training outcomes by5 fixed component folds so the nuisance regression does not model in-sample fit optimism. Residualize each test arm with the same fixed source function, and take the original paired contrast. Limit this sensitivity to both arms within training source pooled5th–95th-percentile ranges of each length covariate; report omissions. The raw main result is unchanged.

This estimates a train-defined length-residual contrast, not a causal direct effect and not a generally identifiable author-style component. Never fit a test/davinci-specific length curve. Do not supply total length to prefix models; evaluator conditioning is not a predictor input. If executing cross-fitted nuisance fits would exceed budget, report close-length and source-stratified results and label the smooth diagnostic unrun rather than use in-sample loss residuals.

## 10 Source and generator transfer

For source A→B, fit preprocessing, channel eligibility, models and early-stopping decisions only on sourceA training/dev. Evaluate sourceB rows from the original component-disjoint test panels. Run Baike→Web and Web→Baike for F1/F2/F4 with fixed architecture and training settings. F2 and F4 carry the same explicit covariance summary in these source-only fits. Fc is not separately fitted in these extra source-transfer arms, so a covariance-specific transfer increment is not isolated there; only the set/order comparison and pooled-fit source-stratified covariance results are available. Do not reuse a pooled model's tuned epoch or a vocabulary/normalizer learned from sourceB. Component grouping remains intact; report source mixed components and any unavailable cells rather than altering the frozen split. Source-only training may produce different eligible target sets; report those sets and do not compare absolute pooled losses across fits as if they scored identical outcomes. This is source transfer within Chinese QA, with unknown semantic topics and authors.

For generator transfer, davinci never participates in measurement calibration, active channel selection, threshold choice, training, dev, early stopping, feature gates or resource-profile selection. Use only the transfer panel at final evaluation. Evaluate frozen human and ChatGPT on those identical question families too, so davinci versus ChatGPT increments are paired within this panel. The seen-panel ChatGPT value is not the only comparator, because that would mix question-population changes with generator change.

A paragraph source-holdout is unsupported because Web's original writer structure is unknown. An author/chronology/topic/broad-domain holdout is unavailable because labels do not exist. Do not manufacture these panels.

## 11 Inference, reporting and falsifiers

Compute95% component-bootstrap intervals with2,000 resamples for secondary endpoints, and98.333333% for the three primary endpoints. Each resample draws components and includes all their questions/variants/arms; recompute the within-question means and denominators. Average the three seed-specific losses before population inference, and separately show seed spread. Report number of components, questions, variants, units and target observations for every score. A component with30 questions stays one bootstrap cluster while each question remains equally weighted in the estimand.

Distinguish two decisions: evidence of a positive predictive increment requires the98.333333% lower interval of the aggregate relative reduction to exceed0; evidence that the increment reaches the predeclared useful margin requires that lower interval to exceed1%. A point estimate above1% with a lower interval between0 and1% supports positivity but not established useful magnitude. Failure does not prove equivalence. Without measurement reliability, call it evidence about fixed instrument outputs. Cross-source/generator persistence is a separate endpoint; do not let a pooled aggregate conceal reversal. Secondary multiple comparisons are labelled exploratory; report all predefined ablations, including negative results. Do not select the best seed or best subset for the abstract.

Falsifiers include no order gain, gains explainable by matched-capacity sets, masks/opportunities/length alone, only last-unit information, failure after source/generator holdout, or differential parsing error. A permutation effect alone is not a human/AI finding. Shared regularities across H and generators are a legitimate result. No trained model is used to rewrite, recommend edits, or score writing quality.

## 12 Prospective execution and resource limits

Proposed bounded execution, requiring approval:

1. Implement schema firewall and runnable synthetic invariance tests; never run empirical bodies through the synthetic-only smoke path. No empirical model fitting may start until the coordinator has reviewed these runnable tests and the bounded throughput pilot receipt; a design-review pass alone does not open the fit gate
2. Profile at most32 deterministic training components, H+ChatGPT only, selected by frozen hash without viewing outcomes. Extract no dev/test/davinci during profiling. Preserve successful measured rows for the later train run so profiling does not duplicate cost
3. Measure approved train/dev H+ChatGPT with one persistent restored parser, using the exact existing guards, no model downloads/network/API. Log projected/full cost and every failed source
4. Train the core ladder and mandatory controls. Export a code/config/model/profile hash manifest and dev decision ledger. Freeze all choices and the target IDs
5. Hand the frozen bundle to the controlled evaluator. It alone may read authorized test bodies, generate private measurements and score exactly the registered panels. Return aggregates only; retain private per-record values for reproducibility, never export them publicly
6. Mark any requested optional sparse/permutation stage and descriptive block analysis run or unrun; they cannot replace a failed primary result

Proposed hard ceilings:2 CPU cores/threads;2 GiB process-tree RSS;2 GiB new derived disk;24 aggregate CPU-hours and24 wall-hours; maximum100 optimizer fits plus20 low-capacity stability resamples. No GPU, paid service, new software/model/corpus download, or remote write. All attempts and cross-fits count against the budget. Before full execution, project cost from the declared training profile and seek a smaller explicitly declared scope or additional approval if infeasible. Do not truncate sources, shorten windows, change corpus support, relax guards, or raise resources silently. Exhausting the cap yields an incomplete registered experiment, not permission to stop after a favorable subset.

The core is F1/Fc/F2/F3/F4/F1-wide/F2-wide ×3 seeds, mask/opportunity and pure-mask controls F1/F2/F4 ×3 seeds each, length controls F1/F2/F4 ×3, shuffled-training F4 ×3, independent-family F4 ×3, and source-holdout F1/F2/F4 ×2 directions×3 =72 optimizer fits. The optional full P1–P4 ladder adds12, its P2 capacity bracket adds3, and its P1/P2/P4 mask-plus-opportunity controls add9, totaling96. The former six fitted block-order runs are removed prospectively; block work is descriptive only. A sparse extension adds at most9 fits and cannot be combined with the full permutation extension under100: choose and freeze either core+permutation (96) or core+sparse (81), or obtain approval for a different explicit substitution. The20 low-capacity stability resamples remain separately capped. Smooth loss residualization's cross-fits may exceed this budget; use the simpler registered length sensitivity or request separate approval, with no hidden extra search.

## 13 Minimum implementation acceptance contract

Implement a separate natural-research module; do not mutate the existing synthetic-only contract. Minimum files/interfaces:

- `NaturalMeasurementRecord`: frozen provenance + nullable exact measurements; private only
- `make_model_packet(record, cutoff, mode)`: allowlist-only values, masks and opportunities; mode is `supplied_annotation_prefix` or `retrospective_bag`
- `fit_transform(train_only_records)`: saves transforms, eligible target IDs, weights, source support and hashes
- `models.py`: F1/Fc/F2/F3/F4, active-capacity F1/F2 brackets, shared first/second-moment producer, nuisance controls; invariant pooling tested independently
- `train.py`: family/arm-balanced sampler, documented early stopping, seeds, failure handling, optimizer-fit ledger
- `freeze.py`: immutable configuration, model and measurement-profile hashes; explicit approved stages/panels
- `evaluate.py`: refuses train/dev operations or any model change; exact paired/common-support scorer and component bootstrap; no raw/text/per-sample output
- `report.py`: full registered endpoint table, support and missingness tables, negative controls, scope wording, all unrun stages

Required tests before natural fitting:

1. No question/component crosses frozen splits; exposed components cannot reach test; human arm not doubled; family weights sum1 after each view restriction
2. No davinci record can enter fit/normalizer/gate/nuisance/early-stop code paths
3. No target/future values or masks or full counts reach a prefix packet; changing hidden suffixes in a synthetic record cannot change its prediction packet
4. F1/Fc/F2 and their summaries remain invariant under prefix permutation while F4 may differ; capacity counts are honest. On tiny hand-computed fixtures verify means, diagonal variances, cross-covariances, n=0/1/2 behavior and pairwise missingness. Same marginal means with different covariance must change only Fc's covariance-value path, while F1 and all support fields stay fixed. Identical multisets in different orders have identical first/second moments. No suffix may influence prefix moments
5. All71 IDs match the restored catalog; exactly the three history IDs are removed from local-core input; local missing reasons survive audit
6. Unknown opportunities remain unknown; failed parsing does not create observed zeros; ratio channels never receive invented epsilon denominators
7. Singletons, two-unit sources, no-block sources, partial POS/dependency support and wholly missing arms are represented correctly; no eight-unit admission gate
8. Candidate reindexing, ties, duplicate vectors and normalization tests pass for permutation likelihood; resource-linked missingness cannot enter that view
9. Ablations remove every intended information path, including masks/opportunities/summary channels; no graph fallback exists
10. Reproducible family-level scoring and component resampling agree with hand-computed tiny fixtures; sentence count does not multiply independent sample size
11. Source-specific fitting cannot load the other source's fit statistics; source transfer is not advertised as topic or author transfer
12. Public export rejects raw text, IDs, hashes identifying individual documents, offsets, per-document measurements, predictions and graphs

## 14 Natural measurement reliability checkpoint

Implementation tests do not authorize strong linguistic interpretation. Before asserting that learned increments reflect true POS/syntax choices, request a blinded natural train/dev annotation audit stratified by source, H/ChatGPT, length and parse status. It must inspect segmentation, POS, dependency attachment and error rates for the selected measurement families, preserving disagreements and differential errors. Its size/power and qualified reviewers require a separately approved annotation plan; do not call an LLM's agreement an independent gold standard. No davinci/test audit is used to modify this version.

The training pilot may be reported as instrument-level evidence while this check is pending. If reliability work changes the definitions, issue a new profile and refit using train/dev before any prospective test opening. Without a predictive discourse producer and independent calibration, the full discourse/argument and stable-author model remains unavailable regardless of the sentence-model result.
