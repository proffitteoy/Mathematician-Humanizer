# PHD estimator stability on the fixed 32 pair pilot

Date: 2026-10-02. Status: one prespecified 20-seed run completed; saved-energy arithmetic and aggregate uncertainty checks passed. This report contains aggregate evidence only. Detailed per-text and per-seed measurements are retained locally and are excluded from publication.

## Main finding

Computational randomness is large enough to reverse the equal-length **cohort mean dimension contrast** on one of the 20 fixed schedules, although the cohort mean **slope contrast** remains positive on all 20. The equal-length dimension gap averages 1.066, with across-seed SD 0.553 and full range −0.560 to 1.708. Eighteen of the 32 individual pairs change sign across schedules. The original-window dimension gap remains positive on all 20, averaging 1.588 with SD 0.358.

This is evidence that the reciprocal dimension transform amplifies finite-cloud measurement variability. It is not evidence that the human-minus-AI slope contrast vanishes: its pooled mean is positive under every measured schedule in both conditions. It also does not validate a universal human geometry, a detector, writing quality, or a transferable style feature. These are the same 32 exposed historical benchmark pairs, not a new validation set.

## What was fixed and verified

The [prior audited pilot](https://github.com/proffitteoy/style-compiler/tree/47c8923ced59229cfa4cc6c34bcf03ea74d73dfe/research/topology/paired-pilot-20261002) motivated the question. A separate [protocol](STABILITY_PROTOCOL.md) was frozen before new measurement, SHA-256 `2636a1371c5454512e3f13e0cfd3313804e4ab0faf4adda62a0773d59e4eaaf9`. The protocol is prospective for this run, not a claim of preregistration before seeing the pilot.

- Same 16 Wikipedia and 16 Reddit train-split prompt pairs; same original windows and independently re-encoded equal-length windows L=min(256,human length,AI length)
- Same RoBERTa-base revision `e2da8e2f811d1448a5b465c236feacd80ffbac7b`, tokenizer, cleaning, CPU float32 encoder, runtime and token-state convention
- Twenty new seeds fixed in advance: 20261010–20261029, three reruns per seed; no selected seeds, added runs, result-based omissions or guard-based complete cases
- Released-notebook grid and 9/3 subset draws; explicit upstream OLS slope formula; final D=1/(1−mean of three slopes), with no stability guard or [2,18] filter
- All 128 text-condition cloud hashes equal the corresponding pilot hashes. There are 102 distinct clouds; 26 identical within-text windows reuse the exact same estimate
- No new AUROC, threshold, fitted classifier, generated text, downloads, controlled TEST access, paper-prose profile switch, or remote write

The [released notebook](https://github.com/ArGintum/GPTID/blob/8c8759ef94c8769e2f40f3e507f270e4c948a562/example.ipynb) supplies the grid and extraction convention; the [released estimator](https://github.com/ArGintum/GPTID/blob/8c8759ef94c8769e2f40f3e507f270e4c948a562/IntrinsicDim.py) supplies the mean-slope transform. As in the pilot, local seeded NumPy schedules replace upstream global-RNG/thread interleaving. Same-N clouds share subset-index schedules; aggregate calculations retain that covariance. Shared indices do not align token meanings.

## Conditional computational variation

Gaps are human minus AI. Each row averages the same 32 pairs under each of 20 schedules. Seed SD and full seed range describe computational variation of that fixed cohort, not uncertainty about a population.

| Condition | Quantity | Mean gap across seeds | Seed SD | Full seed range | Negative cohort means |
|---|---|---:|---:|---:|---:|
| Original window | Log-log slope | 0.02560 | 0.00317 | 0.01990 to 0.03332 | 0/20 |
| Equal length | Log-log slope | 0.01998 | 0.00337 | 0.01453 to 0.02644 | 0/20 |
| Original window | Transformed dimension | 1.588 | 0.358 | 0.990 to 2.168 | 0/20 |
| Equal length | Transformed dimension | 1.066 | 0.553 | −0.560 to 1.708 | 1/20 |

The dimension MC SD is about 23% of the original-window mean gap and 52% of the equal-length mean gap. At the individual-pair level, original windows have 19 pairs positive under every seed, 2 always negative, and 11 changing sign; equal-length windows have 13 always positive, 1 always negative, and 18 changing sign. Since all final mean slopes are below 1, the transform preserves each individual pair's sign. A mean across pairs can nevertheless reverse because the nonlinear transform magnifies different pair differences by different amounts.

Domain detail is retained in [aggregate-results.json](aggregate-results.json). Original-window dimension gaps average 1.468 for Wikipedia and 1.707 for Reddit; equal-length gaps average 0.950 and 1.181. The equal-length Reddit cohort changes sign across seeds; Wikipedia does not. These 16-pair domain summaries are descriptive.

### All outcomes retained

The two condition columns each contain 64 text cells × 20 seeds = 1,280 final estimates, with 3,840 individual rerun slopes. Combined counts include the 26 reused windows.

| Outcome | Original window | Equal length | Both conditions |
|---|---:|---:|---:|
| Nonfinite or undefined mean slopes | 0 | 0 | 0/2,560 |
| Mean slopes below 0 or at/above 1 | 0 | 0 | 0/2,560 |
| Nonfinite or undefined individual rerun slopes | 0 | 0 | 0/7,680 |
| Individual rerun slopes below 0 | 0 | 0 | 0/7,680 |
| Individual rerun slopes at/above 1 | 8 | 12 | 20/7,680 |
| Nonfinite or undefined final dimensions | 0 | 0 | 0/2,560 |
| Negative final dimensions | 0 | 0 | 0/2,560 |
| Final dimensions below 2 | 0 | 0 | 0/2,560 |
| Final dimensions above 18 | 9 | 13 | 22/2,560 |

All individual rerun transforms are finite. The 20 individual slopes above 1 have negative individual transforms, all retained locally. These do not make the corresponding final three-slope-mean transform negative. Counting each distinct cloud only once gives 2,040 final estimates, 6,120 individual slopes, 12 individual slopes above 1/negative individual transforms, and 13 final dimensions above 18. No final dimension is negative or undefined. The historical [2,18] band is an annotation, not a criterion for correctness or eligibility.

## Why the transform matters

For slope s, D(s)=1/(1−s) and D′(s)=1/(1−s)². Small slope changes can produce large dimension changes as s approaches 1. Transforming an average slope is not the same as averaging its transformed values.

Across original-window texts, median within-text slope SD is 0.00528, while median dimension SD is 0.325 and maximum dimension SD is 6.264. Equal-length windows have median slope SD 0.00812, median dimension SD 0.611 and maximum dimension SD 9.773. All observed final dimension values range from 4.158 to 27.371 in original windows and from 4.158 to 48.967 in equal-length windows. These are aggregate extrema, not censored estimates.

The first-order prediction SD(D)≈SD(s)/(1−mean(s))² is close for typical cells: median observed/predicted SD ratios are 1.011 and 1.018. The maximum ratios are 1.539 and 2.071, so local linearization materially understates some tails. No final mean slope crosses 1 in these 20 schedules, but individual reruns do. Twenty schedules cannot calibrate rare pole-near outcomes or establish finite-moment convergence.

As a predeclared diagnostic only, transforming each text's average slope across all 20 schedules yields cohort gaps 1.661 and 1.188, versus 1.588 and 1.066 when averaging the original three-rerun dimension estimates. This aggregation-order difference is retained; the diagnostic is not substituted as a newly selected estimator.

## Relation to available token count

Longer available clouds have lower measured MC variation in this cohort. Spearman correlations of N with slope SD are −0.910 (original) and −0.925 (equal length); with dimension SD they are −0.668 and −0.836. The narrower short-cloud scale span is also associated with higher SD. These are descriptive associations, not causal estimates.

| Available N | Original cells | Original median slope SD | Original median D SD | Equal-length cells | Equal-length median slope SD | Equal-length median D SD |
|---|---:|---:|---:|---:|---:|---:|
| 50–79 | 7 | 0.01935 | 1.708 | 14 | 0.02237 | 1.717 |
| 80–159 | 17 | 0.00877 | 0.606 | 34 | 0.00819 | 0.595 |
| 160–255 | 3 | 0.00579 | 0.289 | 4 | 0.00565 | 0.506 |
| 256–510 | 37 | 0.00375 | 0.289 | 12 | 0.00449 | 0.263 |

Every observed individual rerun slope above 1 occurs in the 50–79 bin. However, the bins were fixed for description, and sample sizes are small and uneven. Nothing here identifies a universal minimum length. The association is not uniform in every original-window subgroup: Wikipedia human texts have N/slope-SD correlation −0.093 and N/dimension-SD correlation −0.227. The full domain/label correlation breakdown is in the aggregate JSON. Equal-length subgroup N/slope-SD correlations remain strongly negative (approximately −0.85 to −0.96).

Equal-length re-encoding changes both available N and contextualized geometry. There is no known intrinsic-dimension ground truth or independent token resampling model here. Therefore finite-N bias, its direction and its contribution to the substantive contrast cannot be identified by this experiment.

## Separating seed variation from pair variation

Let δ(i,k) be pair i's human-minus-AI difference at seed k, C its across-seed covariance matrix, and a the vector with all entries 1/32. The empirical single-schedule cohort MC variance is a′Ca. It includes common-seed covariance. The variance of averaging 20 schedules is estimated as a′Ca/20, conditional on this procedure and these observed schedules. Between-pair variance is calculated separately from the 32 seed-averaged pair contrasts.

| Condition and quantity | Cohort single-seed MC variance | MC variance of 20-seed mean | Between-pair variance of seed means | Finite-MC correction | Corrected pair heterogeneity |
|---|---:|---:|---:|---:|---:|
| Original slope | 0.00001004 | 0.000000502 | 0.00082324 | 0.00000957 | 0.00081367 |
| Equal-length slope | 0.00001134 | 0.000000567 | 0.00124612 | 0.00001646 | 0.00122966 |
| Original dimension | 0.12798 | 0.00640 | 3.93935 | 0.14400 | 3.79535 |
| Equal-length dimension | 0.30589 | 0.01529 | 7.06190 | 0.31801 | 6.74389 |

Pair-level heterogeneity and variance of a cohort average are different scales and should not be compared as interchangeable quantities. The correction is trace(P C)/(20×31), P=I−11′/32. It removes the estimated contribution of finite seed averaging to observed pair variance; it is not a population variance estimate. Ignoring cross-pair computational covariance would give dimension cohort MC variances 0.09119 and 0.20211, both below the covariance-aware results.

### Fixed empirical pair-composition sensitivity

The prespecified 10,000 stratified bootstrap compositions reuse only these 32 pairs. Each composition is evaluated against each complete 20-seed vector. Exact two-way centering of the resulting 10,000×20 table separates pair-composition, seed and interaction components. Their variance fractions are:

| Quantity | Condition | Pair-composition main effect | Seed main effect | Interaction |
|---|---|---:|---:|---:|
| Slope | Original | 62.1% | 24.3% | 13.6% |
| Slope | Equal length | 65.2% | 18.8% | 16.0% |
| Dimension | Original | 36.8% | 38.0% | 25.2% |
| Dimension | Equal length | 31.2% | 42.4% | 26.4% |

For equal-length dimension, the seed main effect plus interaction contributes 68.8% of this joint empirical spread. The 95% empirical range for seed-averaged pair compositions is [0.145,1.928]; including seed variation gives [−0.997,2.284]. Original-window dimension ranges are [0.905,2.244] and [0.329,2.572]. For pooled slope, the joint empirical ranges remain positive: original [0.01330,0.03798], equal length [0.00493,0.03466].

These are descriptive ranges and an algebraic variance decomposition on a finite resampling table. They are not population confidence intervals, a random-seed bootstrap claim of generalization, or an independently validated performance result. One negative seed out of 20 is an observed count, not a calibrated 5% reversal probability. The seed main effect in this table averages over bootstrap weights; it need not numerically equal the sample variance of the original equal-weight cohort's seed means.

## Scientific consequence

The evidence does not support saying that all topology contrast is computational noise. A positive mean slope contrast persists in these fixed pairs. It does support saying that a single three-rerun dimension measurement can be unreliable for short clouds, that individual-pair direction is frequently seed-sensitive, and that the equal-length cohort dimension contrast is not sign-stable across the prespecified schedules. The nonlinear dimension scale is substantially more sensitive than the underlying slope scale.

This remains a measurement-reliability finding on one historical generator, two English domains and one encoder. It does not authorize feature admission, a universal length threshold, a quality objective, or population generalization. Finite-N bias and domain/encoder/generator shifts remain unresolved. No further measurement run is launched here.

## Execution and reproducibility

The single measurement process completed encoding, estimation and planned analysis in 164.65 seconds, pinned to two CPUs, with peak RSS 1,339,944 KiB (1.28 GiB). New derived files at run completion were 9,689,130 bytes; the existing pilot working tree was 1,433,506,117 bytes. These are below the 1,800-second, 3-GiB RSS, 500-MiB new-derived and 3-GB combined-working limits. No data or model download was made.

All 47 baseline non-runtime pilot files, including source/model/data/result files, are unchanged. The saved-energy audit independently reproduces 7,680 rerun slopes and all 2,560 final transforms, cohort seed means, covariance-based MC variances and variance-component totals. Maximum upstream-vs-centered slope discrepancy is about 1.28×10⁻¹². The old pilot's guarded and unguarded results are preserved unchanged.

Published files include this report, the frozen protocol, runner/analysis/audit code, aggregate results, run/verification metadata and an aggregate-only release manifest. Raw text, source archives, model weights, clouds, per-text/seed numeric evidence, per-pair differences and identity-bearing diagnostics are intentionally not distributed. Consequently the aggregate release supports checking methods and summary arithmetic, but does not by itself permit an independent reconstruction of every local measurement. A separate reviewer with authorized local access can inspect the retained detailed evidence.
