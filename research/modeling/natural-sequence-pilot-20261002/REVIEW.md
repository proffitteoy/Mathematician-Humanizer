# Independent design review

Date: 2026-10-02. Disposition: **the five substantive review findings are resolved; the design is suitable for bounded execution approval consideration.** This review neither grants execution approval nor establishes implementation correctness or empirical validity.

## Verified corrections

1. **Mean/set fairness:** F1 now explicitly summarizes values, observation counts and opportunities. F1-wide brackets F2's active capacity; F2-wide brackets F4. Representation claims must survive the corresponding bracket.
2. **Common permutation outcome:** all models and reduced-input controls use one equivalence partition fixed from full allowed packets. Controls cannot merge targets after removing their own inputs.
3. **Proper permutation score:** the class-multiplicity likelihood is normalized over remaining candidates. Training/selection uses document NLL divided by the bag-fixed `max(N−1,1)`, not a realized-order-dependent count. Enumeration tests sum over distinct multiset permutations, without recounting labeled duplicates.
4. **Evidence thresholds:** the relative gain is a ratio of aggregate paired, equal-arm, seed-averaged losses. Its 97.5% lower bound must exceed zero for positive evidence and 1% for established useful magnitude. Companion prose must preserve that distinction.
5. **Complete stated fit budget:** core fits total 69; permutation adds 24, reaching 93; block fits add six, reaching 99. Sparse fits cannot be silently added beyond the 100-fit ceiling. Optional stages must be frozen within the cap; failures and extra fits consume the ledger. Twenty low-capacity stability resamples remain separately capped, within the overall resource limits.

## Scope and limits

The review also checked the stated question/answer/arm weighting, component resampling, missingness controls, retrospective information boundary, source/generator holdouts, length-conditioned estimands, and limitations on linguistic, causal, author and discourse claims. No unresolved fatal design-level leakage was identified within those declared boundaries.

Only `RESEARCH_NOTE_ZH.md`, `PROTOCOL.md`, and the revised `training_contract.json` were inspected. No empirical text, feature extraction, model fitting, implementation tests, downloads or remote writes were performed. Dataset counts, actual leakage prevention, parameter counts, runtime feasibility and measurement reliability therefore remain unverified execution-stage obligations. This is a fixed-instrument prediction pilot, not evidence of stable author factors or a completed discourse model.

## Version 1.1 covariance amendment review

Date: 2026-10-02. **Design-review pass for bounded approval consideration**, subject to the unchanged execution and measurement obligations above. This section supersedes the earlier fit counts and primary confidence level. This narrow re-review inspected only the revised protocol's §§1, 5/5.1, 6 and 12; it did not independently audit the subsequently aligned contract or amendment note.

- The 70-coordinate upper triangle contains exactly 2,485 variance/covariance entries. Prefix-only centering, joint-observed subsets, `n−1` denominators, unavailable cases and non-PSD pairwise-deletion limitations are explicit.
- F1/Fc/F2/F3/F4 share the same pair-conditioned first moments, co-observation counts and validity indicators. Fc/F2/F3/F4 share identical explicit covariance information. Thus covariance is neither an exclusive order-model input nor a disguised support-information advantage.
- The new Fc→F2 primary comparison now has a deterministic pre-fit capacity check/bracket without additional fits. F1-wide brackets the realized Fc/F2 architectures; F2-wide brackets F4. Unsuitable discrete matches require disclosure and restricted claims.
- Mask/length controls, independent-family dynamics and gated ablations explicitly remove unintended value-dependent pair-summary paths. No unresolved fatal information-path leak was identified in these amended sections.
- The three primary endpoints use `1−0.05/3` confidence coverage, approximately 98.333333%, consistent with the declared two-sided Bonferroni family error rate. Core fits total 72; the full permutation extension totals 96; the alternative sparse extension totals 81. Fitted block-order runs are removed. These totals are arithmetically consistent with the stated cap and separate stability-resample allowance.

No corpus access, feature extraction, fitting or empirical tests occurred during this amendment review. Actual parameter counts, resource feasibility and scientific results remain unverified.
