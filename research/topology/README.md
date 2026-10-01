# Active topology replication: H0/MST scaling

Status (2026-10-01): independent **numerical estimator** and synthetic checks implemented. No Chinese encoder has been run, no paper detector result reproduced, no human reference fitted, and no writing intervention validated. This is an active workstream in the [execution plan](../../docs/EXECUTION_PLAN.zh.md), not a retained-feature decision.

## Measured object and provenance

Tulchinskii et al., [Intrinsic Dimension Estimation for Robust Detection of AI-Generated Texts, NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/file/7baa48bc166aa2013d78cbdc15010530-Paper-Conference.pdf), §§3–4, Appendix A.2/B, Table 4 and §6. The alpha=1 sum of finite H0 lifetimes equals total Euclidean minimum-spanning-tree length. Estimate its log-length/log-subsample-size slope, average the rerun slopes, then transform with 1/(1−slope).

Official source inspected (not executed or vendored): [IntrinsicDim.py](https://github.com/ArGintum/GPTID/blob/8c8759ef94c8769e2f40f3e507f270e4c948a562/IntrinsicDim.py) and [example.ipynb](https://github.com/ArGintum/GPTID/blob/8c8759ef94c8769e2f40f3e507f270e4c948a562/example.ipynb), commit `8c8759ef94c8769e2f40f3e507f270e4c948a562`. Upstream is MIT licensed; this independently written module makes no new repository-wide license grant. Source datasets and model weights need separate rights/version records.

## Three distinct sampling profiles

They are named separately because the paper prose, printed grid formula and released example are not identical.

- `paper_prose_v1`: eight nearest-integer equally spaced sizes including 40 and N; seven subsets per size, three reruns. This follows the stated endpoints in Appendix B. Its printed `(i−1)(n−40)/k+40` formula does not reach n when i=k, contrary to its stated last endpoint; our rounding/endpoint resolution is explicit, not claimed to be the authors' exact hidden run
- `gptid_notebook_v1`: step `(N−40)//7`, sizes `range(40,N−step,step)`; nine subsets when N>2n, otherwise three; three reruns. This follows the inspected notebook's explicit call. The realized grid is not always eight points
- `gptid_class_defaults_v1`: sizes `range(50,512,40)`; seven or three subsets under the same half-cloud rule. Reject if the input is smaller than the requested grid; do not silently change it

All implement only alpha=1, Euclidean distance. The source exposes alpha but returns `1/(1−m)` even outside alpha=1; we make no general-alpha replication claim. Source threads share NumPy's global RNG; this implementation uses explicitly spawned local generators, so it does not promise bitwise identity with upstream random schedules. Caller-supplied subset schedules support matched numerical comparisons.

## Run

Uses already installed NumPy and SciPy; no model or network service is called.

```sh
python -m unittest discover -s research/topology -p 'test_*.py' -v
python research/topology/demo.py
```

From Python, put this directory on the import path and call `estimate(points, Config(...))`. Input is a finite numeric N×D array, not raw text. The caller owns encoder/checkpoint/layer, token selection, length and source metadata. An optional `plan` has shape `[rerun][scale][draw][point index]`; it must use unique in-range indices of the configured lengths.

`mst_edges` implements dense Prim and includes zero-length edges. Sparse-matrix MST routines can interpret stored zeros as missing edges, so duplicate-point behavior must not be inherited silently. Independent Kruskal tests cover distances and ties.

## Outputs and failures

The output includes every subsample energy, median energy, slope, intercept, descriptive R², seed/profile, number of distinct points and finite estimate when available. It never returns an AI probability or a quality score.

- Fewer than 50 points, invalid/repeated/oversized grids, zero MST energy, fewer distinct points than the minimum subsample, or resource overflow return unavailable. The distinct-point rule is an additional conservative guard, not an upstream setting
- Nonfinite/invalid input and malformed supplied schedules raise explicit errors
- The default maximum is 512 points; an explicit cap up to 2,048 is supported. Complete-distance storage and repeated dense MST operations are quadratic; this is not an unlimited-document service
- Mean slope or any rerun outside `[0,1−margin)` causes abstention. The default margin .001 is an **engineering guard**, not a validated statistical threshold or an upstream rule
- Rerun dispersion is Monte Carlo variation conditional on one fixed cloud. It is not a population interval, author uncertainty or estimator-bias correction; three reruns are not enough to establish calibrated coverage
- Reordering a cloud leaves its exact geometry unchanged. A fixed seed applied to permuted rows selects different points, however. Compare matched transformed subset schedules or sampling distributions, not unequal samples mistaken for order sensitivity
- Finite estimates are not universal intrinsic dimensions. Duplicates, short clouds and alpha/theoretical-dimension boundary cases remain relevant

## Checked and untested

21 tests currently pass: MST/Kruskal comparison, duplicates/ties, matched permutations, translation/rotation/scaling, repeatability, mean-slope aggregation, profiles, failure states and input preservation. Synthetic 256-point square and cube estimates are about 1.893 and 2.719 with the committed seed; these illustrate finite-sample bias, not empirical human/AI results. The constant-cloud control abstains. Tests do not certify the paper's detector accuracy or Chinese applicability.

Still required:

1. Pin a Chinese-capable encoder, tokenizer/checkpoint/layer, inference mode and weight license; specify truncation and exclusion of special/padding tokens
2. Reproduce document-cloud extraction on rights-checked non-personal text, recording unavailability/selection rates for short texts
3. Compare repeat seeds, lengths, encoders, scripts and nuisance controls; do not import English dimension thresholds
4. Evaluate topology's held-out added value in the learned multi-view style/dynamics model, with capacity-matched baselines and source/author/topic/time splits
5. Test semantics-preserving edits independently before any use in the compiler. Random-token dimension can be high; maximizing PHD is not a writing objective

See [the broader topology evidence and ablations](../../docs/topology-component.md). No H1/H2 descriptors, learned topology encoder or downstream homology-operator repository dependency is introduced here.
