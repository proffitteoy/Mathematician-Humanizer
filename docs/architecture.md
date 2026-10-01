# Architecture and contracts

## Implemented path

`Document → extract → MeasurementBundle → explicit goal → candidate plan → semantic review → apply → remeasure`

The optional population branch is `rights/provenance review → leakage groups → frozen partition → training-only extraction/design/scaling → experimental ridge residual reference → support-gated assessment`. It does not set editing targets or run a detector. All operations are local; nothing downloads models, text, or sends API generation calls.

- `contracts.py`: strict, versioned metadata and null semantics; personal cohort gate
- `segmentation.py`: reproducible punctuation-based spans with unchanged source offsets
- `features.py`: the initial eight measures; explicit unavailable dependencies
- `leakage.py`: derivative/duplicate components and declared holdout axes
- `model.py`: guarded population-only conditional baseline; no author model
- `planner.py`: one small structural candidate, checks and review-gated execution
- `cli.py`: JSON/JSONL local interface

## Frozen projection and segmentation

`all_input_unicode_LN/1.0.0` counts Unicode categories L (letters) and N (numbers) as content characters. This is not Chinese word segmentation or a grapheme count. Combining marks, symbols, emoji and punctuation are excluded; fullwidth digits count. No normalization occurs in measurement. Only duplicate screening uses NFKC, case folding and whitespace removal.

`punctuation-lines/1.0.0` treats each nonempty physical line with content characters as a paragraph. It detects terminals `。！？!?．` and selected ASCII full stops, retaining closing quotes. Decimal points and single-letter ASCII initials receive narrow guards. Headings, quotations, abbreviations, lists and mixed-language boundaries are not reliably understood. All input is measured: authorial versus quoted prose attribution is unavailable. Adjacency refers to the resulting ordered input sequence, including paragraph transitions; it must not be described as validated authorial-prose dynamics.

Offsets are half-open Python Unicode code-point positions `[start,end)` into the unchanged input. JavaScript consumers must convert from UTF-16 indexing before using these offsets. Ordered sentence and paragraph records retain content length, paragraph membership and original position. Text itself is not echoed in a measurement bundle.

## Eight initial measures

Let C be content characters, P eligible paragraphs, L the ordered positive sentence lengths, and n their count. Quantiles use linear interpolation at `(n−1)q`.

| ID | Definition | Raw mathematical support | Provisional comparison support |
|---|---|---|---|
| F002 | 1000P/C | C>0 | P≥5, C≥200 |
| F003 | single-sentence paragraphs/P | P>0 | P≥5, C≥200 |
| F013 | median(L) | n≥1 | n≥10, C≥200 |
| F014 | Q.75(L)−Q.25(L) | n≥1 | n≥10, C≥200 |
| F015 | Q.90(L) | n≥1 | n≥20, C≥200 |
| F016 | median(abs(L−median(L)))/median(L) | n≥1 | n≥10, C≥200 |
| F024 | mean(abs(diff(L)))/median(L) | n≥2 | 19 adjacent pairs, C≥200 |
| F025 | Spearman(L[:-1],L[1:]), average tied ranks | ≥3 pairs and nonconstant ranks | 19 pairs, C≥200 |

These gates are provisional engineering policy, not validated power calculations. Raw values from little support are retained but marked ineligible for comparison. Zero variation is an observed zero; correlation of constant vectors is undefined and remains null. No absent dependency is zero-filled. No percentage, source verdict or “normal human” range is invented.

Each measurement has raw numerator/denominator where algebraically relevant, unit, eligible count, status, comparison eligibility, missing reason, dependency version, uncertainty fields and references. Sequence references locate evidence; corpus-derived reference fields remain null. Exact arithmetic does not remove boundary/construct uncertainty. Per-feature measurement-error and reference prediction intervals are different quantities, and neither is currently estimated.

## Data and leakage

Every input has context (language, genre, topic, task), provenance, rights declaration, assistance status, and work/lineage/content/near-duplicate identifiers. Metadata flags are reviewed declarations, not machine-certified truth. See `schemas/document.schema.json`. Store source/license URLs, timestamps, original revision, sampling settings and quote/template annotations in provenance metadata pending a later dedicated collection contract.

Hard groups always bind versions, excerpts, translations, rewrites, same-brief derivatives and supplied near-duplicate clusters. The local O(n²) lexical screen additionally catches normalized exact copies and high-overlap five-character shingles; semantic near-duplicate review remains required. It is a pilot algorithm, not a web-scale deduplicator.

The default split declares author and prompt-family holdout simultaneously; source/topic/generator are optional explicit stress-test axes. If these links collapse a crossed dataset into one component, splitting fails. Do not silently drop an axis to obtain a flattering benchmark. Separate research questions may legitimately use separate preregistered designs; report what each split tests. Topic is not indiscriminately unioned with every other axis.

## Population baseline limits

Only H_G, A_G, A_H or A_C can be fitted, one cohort at a time. Synthetic tests, uncertain/unverified provenance and rights, personal cohorts, and insufficient feature support are ineligible. H_G requires declared unassisted authorship and an author ID; generated cohorts require a generator snapshot and prompt family. No corpus ships in this repository, and no model has been empirically fitted or evaluated.

The executable model uses exact joint language/genre/topic/task dummy variables plus standardized log(1+C), training-only feature scaling, ridge regression and a fixed diagonal shrinkage of pooled residual covariance. Each leakage component has total fitting weight one. It is a deliberately simple experimental baseline, not the proposed hierarchical count/proportion model. Fixed shrinkage and sample gates are declared in ModelSpec and require prospective validation; shrinkage makes a matrix better conditioned, not the evidence more abundant.

No missing-value imputation, feature selection, testing-set transforms, per-author covariance or author profile is performed. Constant dimensions, no length variation, sparse context support and out-of-range assessment cause abstention. Any available residual distance uses a frozen feature subspace and is uncalibrated; no chi-square or authorship-probability interpretation is permitted. Calibration, bootstrap uncertainty, hierarchical effects, distributional diagnostics and model selection remain unimplemented.

## Editing boundaries

Only insertion of one newline at an existing sentence boundary is executable. The caller supplies the paragraph sentence cap; it is not a learned human norm. Unbalanced quotations/brackets and locked spans trigger abstention. Non-whitespace code points and locked-string occurrence counts must be unchanged. The review flag is an acknowledgment, not a semantic oracle.

Candidate deltas are deterministic remeasurements on that single candidate. `expected_feature_changes` remains null, `evidence_status` remains proposed, and semantic equivalence remains unverified. Structural emphasis, scope and argument can still change without altering words. The original hash, exact insertion and candidate hash prevent accidental application to a stale or edited source; keep the original for rollback.
