# Active topology replication: H0/MST scaling

Status (2026-10-01): independent **numerical estimator**, portable pinned encoder adapter, and constructed-Chinese pipeline smoke checks implemented. XLM-R has run locally on a synthetic fixture. No natural-text detector result has been reproduced, no human reference fitted, and no writing intervention validated. This is an active workstream in the [execution plan](../../docs/EXECUTION_PLAN.zh.md), not a retained-feature decision.

## Measured object and provenance

Tulchinskii et al., [Intrinsic Dimension Estimation for Robust Detection of AI-Generated Texts, NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/file/7baa48bc166aa2013d78cbdc15010530-Paper-Conference.pdf), §§3–4, Appendix A.2/B, Table 4 and §6. The alpha=1 sum of finite H0 lifetimes equals total Euclidean minimum-spanning-tree length. Estimate its log-length/log-subsample-size slope, average the rerun slopes, then transform with 1/(1−slope).

Official source inspected (not executed or vendored): [IntrinsicDim.py](https://github.com/ArGintum/GPTID/blob/8c8759ef94c8769e2f40f3e507f270e4c948a562/IntrinsicDim.py) and [example.ipynb](https://github.com/ArGintum/GPTID/blob/8c8759ef94c8769e2f40f3e507f270e4c948a562/example.ipynb), commit `8c8759ef94c8769e2f40f3e507f270e4c948a562`. Upstream is MIT licensed; this independently written module makes no new repository-wide license grant. Source datasets and model weights need separate rights/version records.

## Three distinct sampling profiles

They are named separately because the paper prose, printed grid formula and released example are not identical.

- `paper_prose_v1`: eight nearest-integer equally spaced sizes including 40 and N; seven subsets per size, three reruns. This follows the stated endpoints in Appendix B. Its printed `(i−1)(n−40)/k+40` formula does not reach n when i=k, contrary to its stated last endpoint; our rounding/endpoint resolution is explicit, not claimed to be the authors' exact hidden run
- `gptid_notebook_v1`: step `(N−40)//7`, sizes `range(40,N−step,step)`; nine subsets when N>2n, otherwise three; three reruns. This follows the inspected notebook's explicit call. The realized grid is not always eight points
- `gptid_class_defaults_v1`: sizes `range(50,512,40)`; seven or three subsets under the same half-cloud rule. Reject if the input is smaller than the requested grid; do not silently change it

All implement only alpha=1, Euclidean distance. The source exposes alpha but returns `1/(1−m)` even outside alpha=1; we make no general-alpha replication claim. Source threads share NumPy's global RNG; this implementation uses explicitly spawned local generators, so it does not promise bitwise identity with upstream random schedules. Caller-supplied subset schedules support matched numerical comparisons.

## Run numerical checks

The unit tests and numerical demo use NumPy and SciPy; they do not require Torch, Transformers, model files, or a network service.

```sh
python -m unittest discover -s research/topology -p 'test_*.py' -v
python research/topology/demo.py
```

From Python, put this directory on the import path and call `estimate(points, Config(...))`. Input is a finite numeric N×D array, not raw text. The caller owns encoder/checkpoint/layer, token selection, length and source metadata. An optional `plan` has shape `[rerun][scale][draw][point index]`; it must use unique in-range indices of the configured lengths.

`mst_edges` implements dense Prim and includes zero-length edges. Sparse-matrix MST routines can interpret stored zeros as missing edges, so duplicate-point behavior must not be inherited silently. Independent Kruskal tests cover distances and ties.

## Portable local encoder extraction

`encoder.py` and [encoder-profile.json](encoder-profile.json) define `xlmr_base_last_hidden_cpu_v1`. The pinned [XLM-R model card](https://huggingface.co/FacebookAI/xlm-roberta-base/blob/e73636d4f797dec63c3081bb6ed5c7b0bb3f2089/README.md) declares MIT licensing. Checkpoint `FacebookAI/xlm-roberta-base`, revision `e73636d4f797dec63c3081bb6ed5c7b0bb3f2089`, is loaded from an **existing local directory only**. The manifest records byte sizes and SHA-256 hashes for the weights, configuration, tokenizer assets, and model card. Every file is checked before loading; additional top-level files are rejected because extra tokenizer/config files could change extraction. Model weights and cloud arrays are not bundled or uploaded.

Profile:

- Safetensors only, no remote code, no authentication token, local-files-only loaders and offline flags
- CPU float32, two Torch threads, deterministic algorithms requested, eager attention, `eval()` and `inference_mode()`
- Final `last_hidden_state`, 768 dimensions, no pooling, normalization or layer mixing
- Original Unicode text preserved, including whitespace and line breaks; unlike the upstream notebook, no whitespace-cleaning pass
- Right truncation at 512 input tokens, including added boundary tokens; single-document inference with no padding
- Exclude attention-mask zeros, tokenizer-marked special tokens, and every special token ID, including an explicitly written special token. The latter is stricter than upstream's `[1:-1]` boundary removal
- A 1 MiB UTF-8 input guard; the CLI checks size before allocation and also uses a bounded read

`LocalEncoder(model_dir).encode(text)` returns `(cloud, metadata)`. The CLI writes only JSON diagnostics and the numerical estimate. It never saves or uploads cloud arrays. Metadata records the full pre-truncation token count, retained-window count, actual truncation flag, number of discarded tokens, source hash, cloud serialization hash, profile hash, and runtime versions. It contains neither raw text nor token IDs. Source text and model files must already be available locally.

Use an encoder-capable Python environment matching the recorded smoke runtime: Python 3.12.14, Torch 2.14.1+cpu, Transformers 5.18.0, NumPy 2.3.5, SciPy 1.17.0, Tokenizers 0.23.2, and Safetensors 0.8.0. The base numerical environment is sufficient for unit tests. Dependencies are not installed by these scripts; no model download fallback exists. Torch's thread/determinism settings and offline flags are process-wide, so use a dedicated process when the caller needs different settings.

```sh
# Set XLMR_LOCAL_DIR to the existing six-file, hash-matching model directory.
# Run with the Python interpreter from the encoder-capable environment.
python research/topology/encoder_smoke.py --model-dir "$XLMR_LOCAL_DIR" \
  --output /tmp/encoder-smoke-results.json

python research/topology/encoder.py --model-dir "$XLMR_LOCAL_DIR" \
  --text-file /path/to/authorized-local-text.txt --output /tmp/extraction.json
```

The fixture [synthetic-zh.txt](fixtures/synthetic-zh.txt) is assistant-constructed technical prose, not a sampled human document. [encoder-smoke-results.json](encoder-smoke-results.json) records 297 input tokens, two excluded boundary tokens, and a 295×768 float32 cloud; truncation was configured but **did not occur**. Its finite-cloud estimate is 11.171305964851257. Repeated inference in the same process produced the same cloud hash, and this portable run exactly reproduced the earlier one-off smoke's cloud hash and numerical diagnostics. The same real-model run also checks a short constructed input that correctly abstains and a tripled fixture that actually truncates to 512 input tokens and 510 retained tokens. This checks the pipeline, not a Chinese reference distribution, detector threshold, style quality, or natural-language validity. Exact floating-point identity across hardware and package versions is not guaranteed.

### Full-context and causal leakage limits

XLM-R is bidirectional: each retained token state can depend on later tokens in the same retained window. Truncation does not make those states causal. Do not reuse full-document embeddings, pooled features, or PHD values as prefix-only evidence, early predictions, or causal temporal states. Re-encode each permitted prefix/window independently for those experiments and keep the target/future text outside its context. A late slice of an already encoded document is not equivalent to encoding that slice alone. The retained first window also does not represent omitted later text; record truncation and use a separately declared windowing design when full-document coverage matters.

## Outputs and failures

The output includes every subsample energy, median energy, slope, intercept, descriptive R², seed/profile, number of distinct points and finite estimate when available. It never returns an AI probability or a quality score.

- Fewer than 50 points, invalid/repeated/oversized grids, zero MST energy, fewer distinct points than the minimum subsample, or resource overflow return unavailable. The distinct-point rule is an additional conservative guard, not an upstream setting
- Nonfinite/invalid input raises explicit errors. Supplied schedules are validated after cloud eligibility checks; ineligible short or degenerate clouds return unavailable first
- The default maximum is 512 points; an explicit cap up to 2,048 is supported. Complete-distance storage and repeated dense MST operations are quadratic; this is not an unlimited-document service
- Mean slope or any rerun outside `[0,1−margin)` causes abstention. The default margin .001 is an **engineering guard**, not a validated statistical threshold or an upstream rule
- Rerun dispersion is Monte Carlo variation conditional on one fixed cloud. It is not a population interval, author uncertainty or estimator-bias correction; three reruns are not enough to establish calibrated coverage
- Reordering a cloud leaves its exact geometry unchanged. A fixed seed applied to permuted rows selects different points, however. Compare matched transformed subset schedules or sampling distributions, not unequal samples mistaken for order sensitivity
- Translation/rotation/uniform-scaling invariance is mathematical and subject to floating-point range and precision; extreme scales may abstain through zero energies or distance overflow
- Finite estimates are not universal intrinsic dimensions. Duplicates, short clouds and alpha/theoretical-dimension boundary cases remain relevant

## Checked and untested

38 tests currently pass: 21 numerical tests cover MST/Kruskal comparison, duplicates/ties, matched permutations, translation/rotation/scaling, repeatability, mean-slope aggregation, profiles, failure states and input preservation. Seventeen model-free adapter tests cover token/special/padding masks, empty content, invalid states, hash verification and tampering, extra-file rejection, local-only loader settings, actual truncation accounting, unchanged source bytes, and bounded input reads. Synthetic 256-point square and cube estimates are about 1.893 and 2.719 with the committed seed; these illustrate finite-sample bias, not empirical human/AI results. The constant-cloud control abstains. The separate real-model smoke confirms extraction and same-process repeatability; unit-test doubles alone do not verify Transformers behavior. None of these tests certify the paper's detector accuracy or Chinese applicability.

Still required:

1. Reproduce document-cloud extraction on rights-checked non-personal natural text, recording unavailability/selection rates for short texts and actual truncation rates
2. Independently validate corpus provenance, extraction choices, and a held-out reference design; the constructed fixture is not a substitute
3. Compare repeat seeds, lengths, encoders, scripts and nuisance controls; do not import English dimension thresholds
4. Evaluate topology's held-out added value in the learned multi-view style/dynamics model, with capacity-matched baselines and source/author/topic/time splits
5. Test semantics-preserving edits independently before any use in the compiler. Random-token dimension can be high; maximizing PHD is not a writing objective

See [the broader topology evidence and ablations](../../docs/topology-component.md). No H1/H2 descriptors, learned topology encoder or downstream homology-operator repository dependency is introduced here.
