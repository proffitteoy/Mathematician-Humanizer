# Prospective amendment 1 explicit covariance comparison

Date: 2026-10-02. Version:1.0→1.1. Reason: the requested research distinguishes means, covariance and temporal structure; Deep Sets versus means alone cannot uniquely attribute its improvement to covariance. This clarification is prospective. This design work has accessed no test bodies or results and performed no empirical fit. Separately approved train/dev instrument extraction does not estimate or choose this amendment from outcomes.

## What changes

1. Add Fc, an explicit centered observed-pair covariance predictor. For the fixed70 input coordinates, its2,485 variance/covariance entries use joint-observed, visible-prefix units, pair-specific means, and denominator n−1 only when n≥2
2. All mean/covariance/set/order models share the same first-moment and missing-support information, including the two pair-conditioned means, n/t, log1p(n), mean-valid and covariance-valid flags. Fc adds covariance values only
3. F2/F3/F4 receive the exact same covariance summary as Fc. Thus F2 tests learned multiset information beyond declared first/second moments, and F4 versus F2 tests order with those moments held available to both
4. Check Fc↔F2 active capacity before fitting, selecting any necessary Fc width from parameter formulas only. F1-wide brackets Fc/F2; F2-wide brackets F4. No result-based width search or extra fits
5. Preserve all pure-mask, mask/opportunity, length, shuffled-order, last-preserving, independent-family and source/generator controls. Extend each ablation to its pairwise-moment paths so values cannot bypass suppression
6. Primary contrasts become F1−Fc, Fc−F2 and F2−F4. The overall F1−F2 contrast remains descriptive and is not uniquely covariance. Use98.333333% two-sided intervals for the three registered primary endpoints; positive and≥1% useful gains remain separate decisions
7. Add only three pooled Fc seed fits. Replace the optional fitted block-order allocation rather than expanding the cap: core72; core+full permutation96; alternative core+sparse≤81. All are bounded by the existing100-fit ceiling and20 separately capped low-capacity stability resamples. Block work becomes train/dev descriptive only. Optional branches cannot be cumulatively added beyond the cap

## Exact support definitions

`n_jk` counts jointly observed VALUES. It does not depend on whether their original opportunity count is known. Pair means exist for n≥1, covariance for n≥2. The six shared pair fields are `[n/t, log1p(n), mean_valid, cov_valid, mean_j, mean_k]`; Fc and richer models receive one additional covariance value. No second covariance-valid field or pairwise opportunity-known count is added.

Missing values are tensor placeholders under explicit shared flags, not observed zeros. The matrix assembled using pairwise deletion can be non-PSD. The claim concerns observed-pair second-moment predictive information, not complete-population covariance, independent factors, causal coupling or author latent identity. No covariance inverse, Cholesky assumption or eigenvector style-axis interpretation is permitted.

The additional source-only fits remain F1/F2/F4; both F2/F4 include the same covariance summary. Fc is not separately fitted in these source-only arms, so a covariance-specific source-transfer increment is not claimed. Pooled-fit covariance increments can still be evaluated by source and on the held-out davinci panel.

## Required implementation checks

- Hand-computed means, variances and cross-covariances at n=0/1/2
- Same matched means/support with different covariance changes the covariance path, not F1 inputs
- Reordering an identical prefix multiset leaves every first/second-moment summary identical
- Hidden suffix changes cannot change a prefix summary
- Mask-only controls never receive pair means/covariance values
- Length-only controls derive moments only from their two length coordinates
- Family ablation removes pair summaries touching the family; independent-family states cannot receive off-family value moments; sparse gates act before every value summary

No new data, text annotation, parser channel, private author label, graph producer or writing operation is introduced. Exact definitions, channel IDs, resources and models are in PROTOCOL.md and training_contract.json. The reviewer’s version1.1 disposition is appended to REVIEW.md.

Final implementation clarifications: the first-moment/support vector has15,331 entries and Fc adds2,485 covariance values for17,816. Supplied opportunities are logged once; no opportunity denominator is invented for supplemental lengths. Shuffled-training evaluation averages10 permutation losses, not predictions before loss. Empirical fitting remains blocked pending coordinator review of runnable synthetic tests and the bounded throughput pilot.
