# Research protocol: measure first, validate before intervention

Status: evolving design, 2026-10-01. Bounded provenance and annotation-contract probes have been executed; no empirical reference, author model, validated linguistic measurement or writing intervention has been fitted/validated. The eight implemented dimensions are baseline candidates, not the final representation. The learned multi-view/hierarchical/dynamic model and the active topology replication follow the [execution plan](EXECUTION_PLAN.zh.md). Earlier endpoints below describe baseline substudies, not a substitute for that main model.

## Questions and falsifiable hypotheses

1. **Measurement:** The frozen punctuation/character pipeline approximates the intended sentence/paragraph rhythm sufficiently for each chosen Chinese register. Blind manual annotation must audit boundary errors, quoted matter, titles/lists and script/segmentation sensitivity. Drop or change a measure if its error can reverse the substantive comparison.
2. **Marginal versus ordered rhythm:** F024/F025 add held-out information beyond F013–F016 and nuisance metadata, for prespecified human judgments of rhythm/task fit. Preserve lengths but shuffle their order as a negative control. If the added value disappears across length/genre/topic or segmentation controls, retain ordered measures as description only.
3. **Context dependence:** Between-cohort differences in paragraph and sentence distributions vary by genre, topic, task, length, period and source. Neither “AI is uniformly less variable” nor the opposite is a built-in direction. Null or reversed effects are valid outcomes.
4. **Intervention:** For eligible texts and an explicitly chosen task, a paragraph-boundary operation improves blind task-fit/readability ratings without meaning loss. Moving a feature value is insufficient. Reject the operation as a generally recommended strategy if benefit does not replicate or semantic damage rises.

F013/F014 are proposed primary marginal endpoints; F024/F025 are proposed primary ordered endpoints; F002/F003 test paragraph structure. F015/F016 are complementary robustness/distribution endpoints. Freeze final endpoint roles, formulas, support gates and multiplicity handling before data inspection. Do not treat a hundred available feature definitions as permission to search for significant results.

## Corpus design and admission

Use a small, rights-checked Chinese pilot across chosen registers. Prefer prospective matched facts/briefs, audience, length and task, with several human writers and several model families/settings. Historical cohorts may be useful but retain selection, editing, era and content-card extraction confounds. Match or explicitly model both content and task; titles alone do not make outputs semantically equivalent.

Keep cohort meanings distinct: H_G=general human; A_G=baseline generation; A_H=humanize-prompt condition; H_U=real target-author work; A_U=imitation; optional A_C=compiler output. H_U/A_U and personal style inputs remain forbidden in this implementation until final-personalization authorization. Generated imitations cannot define a human author's target distribution.

Record original URL, publication and collection times, exact text hash/revision, author pseudonym where appropriate, rights basis/notice/scope, authoring assistance uncertainty, genre/topic/task/language, generator snapshot/settings, prompt family, and all derivative relationships. A public page or software license does not automatically license copied prose. Quarantine ambiguous rights/origin instead of inventing labels. No mass downloading or external LLM generation is part of this prototype.

Candidate audit outcomes: WikiConv Chinese may support conversation research under content-specific reuse terms after reconstruction/filtering; CSL metadata abstracts require license-scope checks and missing author/journal identifiers; UD Chinese GSD can help annotation auditing rather than intact author-level style; broad web and personal-blog pools are not an admitted reference. PKU restricted corpus and unresolved LCMC rights are not admitted. See [evidence audit](evidence-audit.md).

## Splits and estimation

Freeze derivative/near-duplicate grouping before extraction and split authors, briefs and prompt families according to the declared estimand. Report infeasible fully crossed designs. Prespecify separate source-, topic-, generator- and future-time stress tests rather than conflating every axis into one claim. All learned vocabularies, scaling, hyperparameters, feature selection, density/distance calibration and prompts belong to training or inner development partitions only.

Report documents and independent authors/briefs/lineages, conditional coverage, missingness, zero mass and length support. Sentences and overlapping windows are not independent author samples. Use original-unit effects, robust distribution summaries and cluster-aware uncertainty; pair within actual shared briefs when defensible. Prespecify multiplicity control and effect-size relevance. Plan sample size by simulated uncertainty/power under realistic clustering and annotation errors, not “one sample per feature.”

The implemented ridge baseline conditions on language/genre/topic/task and continuous length. It is not a complete statistical research solution. The target model may use negative-binomial exposure models for counts, beta-binomial proportions, robust transformed continuous outcomes, and supported author/brief/generator effects. Author-topic confounding needs crossed data or a narrower question; a mutual-information inequality does not cure it. Numerical covariance shrinkage does not create evidence for personal covariance.

## Optional geometry: postponed and falsifiable

Attention-graph topology, embedding-cloud PH0/MST scaling, sentence-embedding trajectories and scalar-feature covariance measure different objects. No topology value is available without a frozen representation, rights-checked input and estimator validation. PH dimension is not the number of ideas or a writing-quality score. Permuting already-computed points should not change point-cloud geometry; sentence shuffling must occur before re-encoding to test order.

Compare nuisance-only, interpretable, ordered and geometry-augmented models with matched capacity and frozen splits. Test multiple encoders, point counts, lengths, registers, script/tokenization choices and random seeds; use boilerplate, nonsense and duplication controls. Drop geometry from the compiler if it offers no incremental held-out reader-quality/task-fit value or reverses under nuisance controls. Human/AI separability alone is not sufficient.

## Promotion gates

- **Implemented measurement:** unit/property tests pass; the formula and projection are frozen. This repo reaches this software stage for eight measures only
- **Validated measurement:** blind target-domain annotation, error/sensitivity report and adequate support justify a particular use. Not reached
- **Supported distribution:** real eligible corpus, leakage-screened held-out evaluation, coverage and cluster-aware uncertainty. Not reached
- **Measured operation:** randomized eligible operations with before/after features and independent semantic/task outcomes. Candidate remeasurement alone does not reach this stage
- **Validated intervention:** beneficial effect replicates on held-out text without unacceptable semantic loss. Not reached
- **Personal strategy:** separately authorized real author data and cross-topic/time evidence. Disabled

## Protected meaning and failure criteria

Lock names/identities, numbers/units/ranges, time, quotations/citations, negation and quantifier scope, conditions, modality, evidence strength, causal versus temporal relations, commitments and claim/evidence/objection structure. Epistemic uncertainty, vague reference and approximate quantities are different; do not replace them with fabricated specificity.

Mechanical diff checks detect some failures but cannot prove equivalence. Future NLI/embedding/LLM checks are warning signals until validated against blinded human review. Preserve original texts, record candidates and outcomes, and reject/revert edits when meaning, task fit or author approval worsens. Never insert errors, invented experiences, arbitrary noise or detector-targeted changes to imitate “human writing.”

## Reproducibility release

Publish code, contracts, preregistered protocol, licensed metadata/derived aggregates where allowed, exact versions and held-out results including nulls. Keep raw corpora and fitted artifacts outside version control by default. Separate source licenses from code licenses. Tests here use synthetic fixtures only and establish no empirical writing claim.
