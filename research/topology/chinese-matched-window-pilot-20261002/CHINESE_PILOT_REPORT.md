# Chinese topology-feature adaptation: small, inconclusive incremental gain

Date: 2026-10-02. Status: **48-pair bounded development pilot completed**. This is a
new Chinese experiment, not recovery of the earlier 32 English pairs. It is a
human/chatgpt-origin diagnostic, not an integration into the original 21 Chinese core
next-unit predictors or validation of writing quality.

## Result and decision

Adding the mean direct MST scaling slope to the same-window linguistic baseline
reduced DEV log loss from **0.304441 to 0.297077**, an improvement of **0.007365**.
The prespecified fixed-TRAIN, stratified pair-composition range is
**[-0.013971, 0.032642]**. It crosses zero. This small experiment therefore does not
establish an incremental benefit beyond the linguistic/length/tokenization baseline.

The uncertainty-only arm slightly worsened log loss. Adding both mean slope and
schedule SD gave a smaller point improvement than mean slope alone. Keep topology
as an unvalidated candidate; do not promote it into a quality objective or the
existing next-unit model on the strength of this result. This does not establish
that topology can never help under a different, independently tested design.

## Prespecified experiment

- Frozen M4 Chinese corpus, revision `628bf0fcb2e8c6b7ffa71fd1af6be413aced8f7d`,
  existing TRAIN/DEV copy-component split, human/chatgpt arms only
- Exactly 32 TRAIN components and 16 DEV components, equally split between baike
  and web. One hash-selected representative per component; no result-driven
  replacement. The metadata-only selection excluded one mixed-source component
- Cohort selection and all statistical choices were fixed before topology measurement
- Chinese BERT revision `84b432f646e4047ce1b5db001d43a348cd3f6bd0`, CPU float32 final
  token states, special tokens removed, Euclidean distance, no pooling or vector
  normalization. Official model/wheel identities were checked before use
- Pair-matched prefixes of at most 256 content WordPieces, fresh independent
  re-encoding and exact tokenizer/Unicode-window round-trip verification. The
  pinned linguistic instrument was rerun on the exact same substring
- Twenty fixed schedules, three reruns each, fixed seven-fraction scale grid,
  three subsets per scale and dense deterministic Prim MST with real zero-distance
  edges. Features are the mean direct slope and its across-schedule SD; no
  reciprocal PHD transform is used for prediction
- The baseline uses 68 non-history window-level linguistic measurements, window
  and lexical-token lengths, WordPiece count, unknown-token fraction and source.
  Typed nulls, opportunities and missing indicators are preserved
- Fixed L2 logistic regression, C=1, half weight per arm, TRAIN-only median
  imputation/scaling, no parameter search. Five arms and twenty single-schedule
  sensitivity models were frozen before any DEV window was measured

Google documents Chinese BERT for Simplified and Traditional Chinese with
character-aware WordPiece handling. That establishes language suitability, not
valid geometry or language-invariant dimensionality. [Official model](https://huggingface.co/google-bert/bert-base-chinese/tree/84b432f646e4047ce1b5db001d43a348cd3f6bd0),
[language/tokenization documentation](https://github.com/google-research/bert/blob/master/multilingual.md).
The data source is the [pinned M4 release](https://github.com/mbzuai-nlp/M4/tree/628bf0fcb2e8c6b7ffa71fd1af6be413aced8f7d).

## All fixed DEV arms

Human is the positive class. Lower log loss/Brier is better. The improvement is
baseline log loss minus the arm's log loss; positive means improvement. Ranges are
10,000 fixed-TRAIN pair-composition resamples, stratified by source, **not population
confidence intervals**. No model is refitted during this resampling.

| Arm | DEV log loss | Brier loss | Descriptive AUROC | Log-loss improvement | Pair-composition 95% range |
|---|---:|---:|---:|---:|---:|
| Linguistic baseline | 0.304441 | 0.087213 | 0.957031 | — | — |
| Baseline + mean slope | 0.297077 | 0.086512 | 0.960938 | +0.007365 | [-0.013971, 0.032642] |
| Baseline + schedule SD | 0.305119 | 0.089745 | 0.960938 | -0.000677 | [-0.012836, 0.011070] |
| Baseline + slope + SD | 0.301603 | 0.090679 | 0.960938 | +0.002838 | [-0.024797, 0.030617] |
| Length/tokenization/source only | 0.671687 | 0.240206 | 0.613281 | -0.367245 | [-0.554080, -0.091960] |

The primary slope improvement is **0.000178 in baike** and **0.014552 in web**, with
only eight DEV pairs in each stratum. The combined slope+SD arm worsens baike loss
by 0.012196 and improves web by 0.017872. These are descriptive domain differences,
not a reason to select only the favorable source. Full values are in
[DEV_AGGREGATE.json](results/DEV_AGGREGATE.json).

The high baseline AUROC describes this small, already-exposed development corpus.
It is not independently validated detector performance and does not measure writing
quality, competence, factuality or a personal author's style.

## Numerical sensitivity

Using each complete shared schedule's slope instead of the 20-schedule mean, the
prespecified twenty baseline+slope models produce DEV log-loss improvements ranging
from **-0.001174 to 0.016051**, with sample SD **0.004686**. Nineteen improve the
point score; one worsens it. All schedules are retained.

This is single-schedule feature sensitivity with fixed training rules. Its SD is
not the standard error of the primary twenty-schedule-mean model, not twenty new
datasets, and not population uncertainty. Shared same-length index schedules are
preserved rather than treated as independent per-text noise.

## Coverage, alignment and remaining confounds

All **96 text windows** passed exact alignment. Topology was finite for **31/32
TRAIN pairs** and **16/16 DEV pairs**. One selected TRAIN pair had a matched
23-token window and failed the fixed operational N>=50 gate. It was retained with
unavailable topology on both arms, explicit masks and TRAIN-only imputation; no
replacement or complete-case resampling occurred. N=50 is an engineering rule for
this pilot, not a universally valid minimum text length.

| Split / source | Selected pairs | Finite topology pairs | Matched WordPiece range | Mean matched WordPieces |
|---|---:|---:|---:|---:|
| TRAIN / baike | 16 | 15 | 23–256 | 159.3125 |
| TRAIN / web | 16 | 16 | 127–200 | 187.2500 |
| DEV / baike | 8 | 8 | 102–256 | 167.2500 |
| DEV / web | 8 | 8 | 65–205 | 177.0000 |

Unknown-token rates were not uniformly zero: the maximum in the DEV human-web
stratum was 11.7%. Unknown-token fraction is included in the baseline, but that
linear covariate does not remove every tokenization/content interaction. No exact
repeated contextual-vector rows were observed; this says nothing about repeated
words. The full source/arm coverage and token/grid/Han/unknown/repetition summaries
are in [TRAIN_MEASUREMENT.json](results/TRAIN_MEASUREMENT.json) and
[DEV_MEASUREMENT.json](results/DEV_MEASUREMENT.json).

Equal WordPiece count does not imply equal characters, lexical words, topic,
semantic complexity, syntactic opportunities or content quality. The 68-channel
instrument remains unvalidated, and its missingness can itself be predictive. The
known availability problems of length-100 features in the earlier local-unit
study should not be confused with evidence of linguistic validity here: these
were newly measured global windows, and all nulls/opportunities were retained.
The small TRAIN sample relative to baseline dimensionality is an additional limit.

DEV had already been exposed in the broader linguistic study. The new comparison
was frozen before topology measurement and scored once, but DEV is not a pristine
external holdout. There is one historical generator family, one encoder, two
sources and no independent generator/author/domain validation.

## Design integrity

The 48-pair selection was fixed before measurement. All TRAIN preprocessing and all
25 models (five fixed arms and twenty sensitivity models) were frozen before DEV
measurement. The fixed four-TRAIN-pair feasibility stage did not expose DEV results.
TEST/davinci bodies stayed closed. No replacement, complete-case fit, encoder
fine-tuning, hyperparameter search, favorable-source selection or favorable-seed
selection was used. The unavailable TRAIN pair remained in every fit.

## Release boundary and scientific consequence

The release contains the unchanged scientific measurement/evaluation modules,
source/model/dependency pins, synthetic scientific tests, methods, aggregate
scientific results and this report. Operational execution records and raw or
per-sample data are excluded. Exact per-source grid histograms are coarsened to
counts of realized distinct scales; individual grids are not released.

An independent replay of retained measurements and frozen coefficients reproduced
all five arms, all twenty sensitivity gains, source/pooled metrics and the
prespecified composition ranges. TRAIN-only preprocessing matched independent
recomputation using all 64 TRAIN rows, with both unavailable arms masked. Saved MST
energies reproduced the slopes for all 94 finite clouds. This replay did not refit
models, regenerate embeddings or remeasure linguistic values; it therefore checks
numerical consistency rather than the underlying instrument's validity. The
public-only checker has a narrower scope: content hashes and aggregate arithmetic.

This pilot demonstrates a working Chinese, same-window topology/linguistic
measurement path. It does **not** establish enough added predictive signal to
justify feature admission. A later next-unit experiment would additionally need
observed-prefix-only encoding, the unchanged target/split boundary, and a separately
frozen additive comparison. Full-answer bidirectional states would leak future
text into that objective. No further experiment is launched here.
