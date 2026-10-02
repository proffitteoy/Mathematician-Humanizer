# Chinese matched-window topology pilot: scientific methods

This publication excerpt preserves the choices fixed before measurement. It is a
methods description, not a new preregistration. Editorial changes remove execution
procedures and retain the estimator, sample, missingness, fitting and evaluation
rules. The three scientific Python modules are unchanged from those used.

## Question and endpoint

Can mean MST scaling slope, accompanied by its Monte Carlo uncertainty, improve a
small, fixed human/chatgpt-origin diagnostic beyond linguistic measurements taken
from exactly the same Chinese prefix windows? This is an instrument/additive-signal
pilot. It does not integrate topology into the existing 21 next-unit predictors,
validate human writing quality, or give independent detector performance.

A Chinese result on already exposed DEV is development evidence. The prior project
has already used TRAIN/DEV linguistic measurements. Freeze this new comparison
before topology measurement, but never label DEV a pristine independent holdout.
Only a later independently frozen dataset can establish transfer/generalization.

## Smallest useful cohort

- Existing M4 Chinese `qazh_chatgpt.jsonl`, revision
  `628bf0fcb2e8c6b7ffa71fd1af6be413aced8f7d`; reuse the frozen source and cohort metadata
- Exactly **32 TRAIN components and 16 DEV components**, with both human/chatgpt
  arms: 48 pairs, at most 96 window clouds
- Stratify each split equally by the recorded `baike` and `web` source:
  TRAIN 16+16, DEV 8+8
- Within each copy component choose the lexicographically smallest pair ID; then
  order component representatives by SHA-256 of
  `topology-zh-matched-prefix-v1-20261002` + NUL + split + NUL + source + NUL +
  component ID. Take the stated counts. Exclude a component only if frozen metadata
  records conflicting source/split membership; report count/reason before selection
- Selection uses metadata only. No quality, slope, parse-success, length, label-
  separation or existing-model result selection. No replacement of selected pairs
- Freeze metadata selection before any text read; publish aggregate counts and retain
  row IDs/byte locators/content hashes privately. Keep the chosen rows unchanged
- Use the exact source accessor: assert split is selected TRAIN or DEV, arm set is
  human/chatgpt, and file is exactly qazh_chatgpt.jsonl **before seek/read**; read only
  each selected byte span; check frozen hashes, source and question identity
- TEST, davinci and all nonselected text bodies remain unopened. Do not decode the
  whole raw archive. Existing linguistic models and caches are outside this diagnostic

## Encoder and aligned windows

Candidate: `google-bert/bert-base-chinese` revision
`84b432f646e4047ce1b5db001d43a348cd3f6bd0`. Official Google documentation specifies
Simplified and Traditional Chinese and character-aware WordPiece tokenization.
Use CPU float32 final token states, eval/inference mode, no pooling or L2
normalization, special tokens removed, ordinary Euclidean distances. This is a
language-suitable model candidate, not evidence of valid or language-invariant PHD.

Use safetensors only, no remote code or model execution from a pickle. Verify
published Git/LFS identities and record SHA-256 for weights, tokenizer and config.
No English RoBERTa substitution. No automatic network fallback during measurement.

Tokenization/window alignment is a real execution gate:
1. Preserve original text. Fast-tokenizer offsets select the first at most 256
   content tokens of each answer without changing Chinese punctuation or applying
   an extra segmentation/normalization heuristic
2. Set pair length L=min(256, each arm's available content tokens). Use character
   prefix endpoints corresponding to the first L tokens. Tokenize each resulting
   exact character substring afresh, then require it reproduces those exact L token
   IDs. If an endpoint inside a WordPiece sequence breaks round-trip equality,
   reduce L in both arms to the greatest common valid count. Save realized L and
   the deterministic reason; never search by measured slope or label performance
3. Contextually encode each exact resulting prefix independently. Token IDs,
   raw-window SHA-256, special-token masks and linguistic input SHA-256 must agree
   with the window receipt. No full-answer hidden-state cropping
4. Re-run the pinned Chinese linguistic instrument on the same exact substring;
   do not join its old full-answer measurement to a truncated topology window
5. Keep the existing frozen Chinese segmenter for linguistic measurement. The new
   heuristic segmenter is a tested adapter experiment, not a silent pipeline change
6. Record window characters/Han count, lexical token count, WordPiece count,
   unknown-token rate, repeated-vector fraction and valid grid; these are potential
   confounds. Different tokenizers' token counts are not treated as equal linguistic
   quantities. Unknown tokens and degenerate clouds are visible failure diagnostics

## Fixed estimator, failure behavior and reliability

This new encoder/window experiment is not an upstream-method reproduction. Declare
its finite-cloud grid explicitly: seven fractions of N,
{1/4, 3/8, 1/2, 5/8, 3/4, 7/8, 1}; floor to integers and remove duplicates. Attempt
only N>=50 with at least four distinct scales of size>=2. This is an operational
pilot gate, not a claim that N=50 is universally reliable.

For each of 20 fixed schedule seeds 20261100 through 20261119, use three independent
reruns, three uniformly sampled without-replacement subsets per scale, average MST
energy at each scale, and fit the centered OLS log(energy) versus log(scale) slope.
Use alpha=1, explicit Euclidean MST, and a separately tested zero-distance/duplicate-
vector policy. Precompute one distance matrix per cloud and reuse full-N energy.
Same-N clouds use the same index schedules; retain this covariance in comparisons.

The feature is the mean over all 20 three-rerun mean slopes. SD across schedule
means is its reliability covariate; SD/sqrt(20) is conditional MC SE. Keep finite
slopes outside [0,1]. No reciprocal dimension, inverse-variance weighting, selected
seeds, outcome-based guard or PHD objective. Invalid energies/nonfinite slopes make
that cloud unavailable with a reason, not a substituted zero. The full-N MST energy is reused without resampling;
all lower scales use the fixed without-replacement schedule.

The selected cohort is never resampled to replace failures. If topology fails for
one arm, mark both arms' topology coordinates unavailable for the primary paired
comparison. Missingness is modeled as below; publish coverage by split/source/arm.
No secondary complete-pair score is included in this experiment. If
fewer than 24 TRAIN and 12 DEV pairs have finite matched topology, stop at a coverage/
reliability report and do not fit the additive diagnostic. This is a feasibility
threshold, not an adequacy/power guarantee. No DEV result can trigger an extra run.

## Linguistic baseline and evaluation

Measure the 68 non-history channels in the existing instrument on each exact
window, retaining typed missingness/opportunity records. Use the global window
measurement of each channel, not a mislabeled next-unit feature. Add two lengths:
log1p(window codepoints), log1p(instrument lexical-token count), plus log1p(Chinese
WordPiece count), unknown-token fraction and a source indicator. The first two
lengths follow the same measurement meanings as the core's structural features,
but this window-level origin task is a new endpoint.

Missing scalar values: TRAIN-only median; use zero only if the entire TRAIN channel
is missing, and freeze that channel's numeric contribution to zero. Append one
missing indicator per channel. Treat a typed observed zero with valid opportunity
as observed. Fit all centering/scaling on TRAIN only. Logistic fitting assigns sample_weight=0.5
to each arm, giving component weight 1; the stated C=1 is relative to those
unnormalized weights, not implicit unit weight per arm. No DEV feature selection,
transformation choice, threshold or parameter tuning. No empirical instrument
eligibility or quality flag is promoted by this experiment.

Fixed arms: linguistic baseline; baseline+slope; baseline+SD;
baseline+slope+SD; and lengths/tokenization/source only. Use L2 logistic regression
with C=1, lbfgs, intercept, max_iter=2000, tol=1e-9. Equal weight per component and
one-half per arm. The small n relative to the baseline dimension is an acknowledged
limitation; regularization is fixed, not tuned until a favorable result appears.

Fit TRAIN once and evaluate DEV once. Primary endpoint is the DEV pair-mean
log-loss improvement, baseline minus baseline+slope. Also report Brier loss and
descriptive AUROC, pooled and by source. Pair-stratified 10,000-draw composition
ranges use seed 20261120, fixed TRAIN fits, and are explicitly not population CIs.
Report all five arms, full coverage and both source strata, even if topology hurts.

Numerical sensitivity: fit/evaluate the baseline+slope arm for each complete
schedule vector with all else fixed; report the 20 DEV improvements and range.
This preserves shared schedule dependence and is not 20 independent datasets.
No training on DEV or choosing a seed/encoder/grid after those scores are observed.

## Feasibility ordering and fixed unavailable-value behavior

Before expansion, exactly four selected TRAIN pairs, two per source in selection
order, were the fixed feasibility subset. The integrity gate required verified
alignment and finite topology for all eight arms. Failure would stop the pilot
without replacement. This subset was retained as part of the final 32 TRAIN pairs.
The remaining TRAIN measurements preceded fitting. All TRAIN preprocessing and the
five main plus twenty sensitivity models were frozen before any DEV measurement.

At least 24 finite TRAIN pairs are required before fitting; fewer than 12 finite DEV
pairs suppresses performance scoring. These are operational feasibility rules, not
power calculations. Failed pairs remain selected. Both topological coordinates
are unavailable on both arms when either arm fails. A blank window has observed
zero character/WordPiece counts and unavailable lexical/linguistic/topological
measurements. Typed zero requires positive audited opportunity. All wholly missing
TRAIN numeric channels stay zero under the frozen imputer, even if observed on DEV.

## Scientific implementation and reproducibility

- `source/pilot_core.py`: component selection; unbuffered exact-span source access;
  Unicode/WordPiece matching; deterministic dense Prim; twenty-schedule estimation;
  typed values and aggregate coverage
- `source/pilot_measure.py`: offline, pinned Chinese BERT and existing Stanza
  instrument adapters, sequential model loading and exact-input alignment checks
- `source/pilot_evaluation.py`: design matrices, paired missingness, TRAIN-only
  transformations, fixed models, frozen prediction and complete aggregate evaluation
- `source/test_scientific.py`: synthetic selection, alignment, missingness, estimator
  and evaluation tests; operational supervisor tests are outside this excerpt
- `source/MODEL_LOCK.json`, `source/DEPENDENCY_LOCK.json` and
  `source/INSTRUMENT_LOCK.json`: fixed scientific dependencies and feature identities. The dependency declaration
  retains scientific pins and omits installer-specific execution details

The 68 linguistic channel names and source hashes are in INSTRUMENT_LOCK.json.
The Chinese model revision is immutable; weights are safetensors, remote model
code is disabled, and measurement has no network fallback. Expected package pins
include Torch 2.3.1+cpu, NumPy 1.26.4, Stanza 1.10.1, Transformers 4.41.2,
tokenizers 0.19.1, safetensors 0.4.5, SciPy 1.14.1 and scikit-learn 1.5.2.
Pins specify reproducibility requirements, not an actual runtime execution record.

Public aggregate JSON retains all five arms, both source strata, all twenty seed
results, coverage and confound summaries. Exact realized-grid histograms are
coarsened to the number of distinct scales, without changing any fitted result.
The public checker does not recreate private measurements or coefficients.

## Boundary for any future next-unit study

The present endpoint concerns answer origin. A next-unit experiment would need
observed-prefix-only encoding, slicing before tokenization, identical linguistic
context, unchanged target/split boundaries, and a separately frozen additive
comparison. Full-answer bidirectional embeddings would expose future text.

## Sources

- [Pinned Chinese BERT model](https://huggingface.co/google-bert/bert-base-chinese/tree/84b432f646e4047ce1b5db001d43a348cd3f6bd0)
- [Google BERT language/tokenization documentation](https://github.com/google-research/bert/blob/master/multilingual.md)
- [Pinned M4 source](https://github.com/mbzuai-nlp/M4/tree/628bf0fcb2e8c6b7ffa71fd1af6be413aced8f7d)
- [Linguistic source baseline](https://github.com/proffitteoy/style-compiler/tree/283b61c58345697fe492d2dcbd8410f245615922)
