# PHD paired reproduction pilot: measured result and limitations

Date: 2026-10-02. Status: 32 frozen human/AI prompt-pairs measured, analysis complete. This is a partial empirical method reproduction on the original authors' released benchmark. It is not a full-paper reproduction, an independently held-out detector evaluation, a Chinese-language result, or learned-style-model integration.

## Bottom line

The historical benchmark shows a higher average PHD for human completions in this small sample. The size and apparent reliability of the contrast depend materially on text length, estimator stability handling and random seed. Equal-length re-encoding weakens separation. The upstream-style unguarded, equal-length audit includes all 32 pairs and has a paired-gap interval crossing zero. These results do not justify admitting PHD as a validated human-style feature or optimizing writing toward larger PHD.

The crucial method-alignment result uses the exact upstream mean-slope algebra on all 32 pairs: original-window human/AI means 10.360/8.119, paired gap 2.242 with 95% interval [.400, 4.392], descriptive AUROC .776. After independently re-encoding equal token counts, means are 10.235/8.302, gap 1.934 [-.113, 4.340], AUROC .687. This is explicitly a post-hoc audit of unchanged saved slopes, not a newly selected primary analysis. The full-cohort maximum seed shift is 24.595. Bootstrap intervals condition on fixed numeric outputs and do not incorporate Monte Carlo, encoder or corpus-shift uncertainty.

## What was actually run

The two original English archive files at [GPTID commit 8c8759ef](https://github.com/ArGintum/GPTID/tree/8c8759ef94c8769e2f40f3e507f270e4c948a562/data) contain 2,317 Wikipedia continuation pairs and 2,144 Reddit question-answer pairs. Sixteen distinct original train prompts from each domain were selected by a frozen seeded hash ordering. We encoded the human and generated completion from the same row. No old controlled TEST, original validation/test rows, paid service, new generation or result-driven resampling was used.

The recorded selection SHA-256 is a4b31b5982c5107adab88a2fca25989c19df4e3b193ceedea50ba946cce5f1b5. The runner verifies that identity before inference. All 32 prompt hashes, 32 human text hashes and 32 generated text hashes are distinct. Raw text and model weights remain local.

The [released notebook](https://github.com/ArGintum/GPTID/blob/8c8759ef94c8769e2f40f3e507f270e4c948a562/example.ipynb) defines the practical extraction and grid used for the primary calculation. Its RoBERTa tokenizer cleaning/truncation/input construction matches our implementation for all 64 texts. We use final token states, remove boundary tokens, and estimate alpha=1 Euclidean MST scaling. Exact sampling, seed and window conventions are in the frozen PILOT_PROTOCOL.md.

## Our predeclared safeguarded variant

The following 29-pair result is our predeclared safeguarded variant, not an unqualified reproduction of the upstream estimator. Mean differences below are human minus AI. Intervals are 10,000 paired bootstrap draws; pooled resampling preserves each domain's available-pair count. AUROC is descriptive, with human-positive orientation; no threshold or probability was fitted. Intervals condition on this model, seed, selected sample and availability rule. They do not integrate estimator-seed uncertainty, encoder/checkpoint uncertainty or corpus shift; two seeds cannot calibrate Monte Carlo error.

| Condition and domain | Usable/selected pairs | Human / AI mean | Paired mean gap (95% interval) | AUROC |
|---|---:|---:|---:|---:|
| Original window, Wikipedia | 14/16 | 9.736 / 7.479 | 2.257 [1.157, 3.158] | .852 |
| Original window, Reddit QA | 15/16 | 9.277 / 7.349 | 1.927 [.705, 3.437] | .778 |
| Original window, pooled | 29/32 | 9.498 / 7.412 | 2.087 [1.269, 2.988] | .822 |
| Equal-length re-encoded, Wikipedia | 14/16 | 9.316 / 7.427 | 1.889 [1.046, 2.753] | .750 |
| Equal-length re-encoded, Reddit QA | 15/16 | 9.416 / 7.888 | 1.528 [-.512, 3.697] | .684 |
| Equal-length re-encoded, pooled | 29/32 | 9.367 / 7.665 | 1.702 [.551, 2.893] | .717 |

Equal length means L=min(256, human length, AI length) token IDs separately re-encoded with fresh context for each text. L ranges 55–256; these are not uniformly 256-token texts. This is a declared extension to the original calculation. It controls within-pair token count and shared prompt/domain, not semantic equivalence, topic drift, token rarity, repetition or lexical diversity.

### The guard matters: upstream-algebra audit

Our inherited numerical module abstains if any rerun slope is outside its stable interval. The [authors' estimator](https://github.com/ArGintum/GPTID/blob/8c8759ef94c8769e2f40f3e507f270e4c948a562/IntrinsicDim.py) simply transforms the mean slope. The three affected primary texts have finite upstream-algebra values 15.917 and 20.264 (AI), and 37.655 (human). They were not replaced.

After seeing this discrepancy's realized effect, we performed an explicitly post-hoc method audit: apply the upstream mean-slope formula to the saved slopes, without new inference, reruns, filtering or selection. This is essential sensitivity reporting, not a new primary result.

| Upstream-algebra audit | Pairs | Human / AI mean | Paired mean gap (95% interval) | AUROC |
|---|---:|---:|---:|---:|
| Original window, pooled | 32/32 | 10.360 / 8.119 | 2.242 [.400, 4.392] | .776 |
| Equal-length re-encoded, pooled | 32/32 | 10.235 / 8.302 | 1.934 [-.113, 4.340] | .687 |

The complete-case guarded contrast cannot be treated as unbiased population performance: availability depends on the observed estimator. The all-pair audit has high-variance outliers and does not establish a robust equal-length separation.

### Other predeclared sensitivities

- A second independent estimator seed retains all 32 pairs. Original-window pooled gap 1.695 [1.040, 2.311], AUROC .820; equal-length gap 1.531 [.536, 2.467], AUROC .717
- With seed two, the equal-length Wikipedia interval crosses zero; with seed one, the equal-length Reddit interval crosses zero
- Among estimates passing both seeds' guards, one 66-token human text moves from 17.561 to 8.263, a 9.298-point change. Across the full cohort under upstream algebra, a 63-token human text instead moves from 37.655 to 13.060, a 24.595-point change. The smaller guarded maximum must not be represented as the full-cohort maximum. Three-rerun numerical repetition does not remove short-cloud instability
- Independent auditing finds that any-rerun guards select the same three failures for slope margins 0 through .02, while mean-slope-only guards retain all 32. The decisive issue is guarding each rerun rather than only the mean, not the precise .001 margin
- The endpoint-inclusive paper-prose profile retains all 32 original-window pairs: pooled gap 1.818 [1.127, 2.483], AUROC .801. It is deliberately labeled a different estimator profile

## Main confounds and reproducibility deviations

1. Length imbalance is large. Wikipedia mean lengths are human 475.4 versus AI 130.1 content tokens; Reddit QA means are human 220.1 versus AI 284.1. Two human texts truncate at the 510-content-token first window; no AI texts truncate. A high original-window separation alone is not a length-controlled finding
2. This is a 32-pair train-split pilot with one historical generation model, text-davinci-003, two English domains and one encoder. No model fitting occurs, but it is not held-out feature admission, Chinese validation or modern-generator generalization
3. Original encoder checkpoint revision, package lockfile and seeds are unpublished. We pin [FacebookAI/roberta-base e2da8e2f](https://huggingface.co/FacebookAI/roberta-base/tree/e2da8e2f811d1448a5b465c236feacd80ffbac7b), verify safetensors and tokenizer identities, and record the modern runtime. Original model identity is matched at the published model-family level, not historical-byte identity
4. The paper's endpoint prose, printed grid and released notebook disagree. The source uses variable 9/3 draws, while the paper describes 7 per scale. We do not silently equate them. The paper mentions additional outlier-correction restarts without a reproducible trigger/rule; none is invented here
5. Our explicit local seeded subset schedules differ from upstream shared-global-RNG multithreading. Seeds reset per text, so same-length clouds use identical subset-index schedules, including within matched pairs. This induces shared computational randomness without token-semantic alignment. All diagnostics are saved; no bitwise upstream RNG equivalence is claimed
6. Archive Wikipedia validation/test counts are 260/259, whereas paper Table 10 lists 259/260. We preserve the released split labels and use train only
7. The runtime virtual environment inherits existing base scientific packages; it is write-isolated, not a fully hermetic environment. Unused base packages complain about NumPy 1.26 versus their NumPy 2 requirements, and generic Torch requirements jinja2/networkx are absent. The exact inference path imports, executes and passes checks; broader environment health is not asserted

The primary paper establishes the model/estimator idea and reported benchmark effects, but does not make this pilot's downstream admission claim: [Tulchinskii et al., NeurIPS 2023](https://papers.neurips.cc/paper_files/paper/2023/file/7baa48bc166aa2013d78cbdc15010530-Paper-Conference.pdf). Its scope excludes arbitrary broken/high-temperature generations. The later [Pedashenko et al., EACL 2026](https://aclanthology.org/2026.eacl-long.370/) supplies further reasons to require domain and length controls rather than a universal human constant.

## Resource, rights and verification record

- CPU inference/estimation completed in 71.101 seconds; peak observed RSS 1,308,240 KiB; one process pinned to 2 cores; 1800s hard timeout never reached
- Torch 2.3.1+cpu, Transformers 4.41.2, NumPy 1.26.4, SciPy 1.17.0, Python 3.12.14; no GPU, training, remote model code or inference network fallback
- Official CPU wheel 190,367,618 bytes; model files 501,538,643 bytes; data archives 8,782,376 bytes. Additional wheels total roughly 33 MB by pip's download log; network metadata overhead is not exactly instrumented. Total remains below 1.2 GB; working directory approximately 1.4 GiB, below 3 GB
- Both source archives match pinned Git blob hashes; all model assets match published Git/LFS identities; restored own-code files match repository Git blob hashes; 38 numerical/model-free tests pass both in base and restored runtime
- All 64 token input sequences match the released notebook convention; 32 selected pair identities verified; matched lengths and absence of literal internal special tokens verified
- Model card declares MIT; upstream software license is MIT. Wiki40B human material inherits CC-BY-SA. The archive release has no separate granular license for Reddit extracts/generated completions. Research data were read privately from the authors' published replication archive; raw text, model weights and embeddings are not redistributed. Public metadata preserves attribution and hashes

## What this changes in style-compiler

The research repository can now truthfully record a paired empirical pilot instead of smoke-only progress. It still cannot mark topology as validated, train on this pilot as if it were a reference corpus, equate PHD with human writing quality, or claim the multi-view style model has incorporated a replicated feature. The immediate next scientific question is finite-sample/Monte Carlo stability and its interaction with length and domain. No larger run is launched here. A fixed next experiment should be reviewed after these findings are frozen, before downstream feature admission or detector integration.
