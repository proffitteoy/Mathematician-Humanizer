# Paired PHD pilot frozen 2026-10-02

This is a bounded empirical reproduction of a method-level contrast on the authors' released paired benchmark. It is not a replication of the entire paper, a trained detector evaluation, or evidence of style quality. No topology feature is admitted to the learned style model by this experiment.

## Sources and frozen selection

- Original release: ArGintum/GPTID commit 8c8759ef94c8769e2f40f3e507f270e4c948a562
- Two official archives: human_gpt3_davinci_003_wikip.zip (4,681,974 bytes) and human_gpt3_davinci_003_reddit.zip (4,100,402 bytes), verified against their Git blob identities
- Select 16 distinct prompts from each released train split. Sort SHA-256 of `20261002|domain|prefix`, keep first 16; no PHD, outcome, length or score selection. Pair human and generated completions from the same original row and preserve genre
- Selection file SHA-256: a4b31b5982c5107adab88a2fca25989c19df4e3b193ceedea50ba946cce5f1b5
- The old controlled TEST is not read or modified. Neither the original archive's validation nor test split is selected. No train/test detector fit is attempted
- Wikipedia archive has 2,317 pairs, with 1,798/260/259 train/validation/test; paper Table 10 reports 1,798/259/260. This discrepancy is recorded, not silently repaired. Reddit has 2,144 pairs, 1,677/232/235

## Extraction and estimator

English RoBERTa-base is used because this is the paper's English encoder. Pin FacebookAI/roberta-base revision e2da8e2f811d1448a5b465c236feacd80ffbac7b and verify safetensors/config/tokenizer hashes. The original paper/notebook does not supply a checkpoint revision, runtime lockfile or random seed, so exact historical bitwise replication is unavailable.

Match released notebook: RobertaTokenizer, one-pass newline-to-space then double-space-to-single-space replacement, right truncation to 512 input tokens, final unpooled 768-dimensional state, remove only the first/last boundary states, Euclidean distance, alpha=1. Content completion only is encoded; prompt is used for pairing, not prepended. Literal internal special tokens are retained, as in the notebook, and their presence is recorded.

Primary profile is `gptid_notebook_v1`: step=(N-40)//7, sizes=range(40,N-step,step), nine subset draws when N>2n and three otherwise, three reruns, median MST length at each scale, OLS log-length/log-size slope, average slopes then 1/(1-mean slope). Use independent recorded seeds 20261002 and 20261003 with local NumPy generators rather than upstream's shared thread/global RNG. Primary inference is seed20261002; the second is a sensitivity analysis, not an opportunity to select a better result.

Report `paper_prose_v1` for the original window as an explicit sensitivity: eight rounded equal-spaced endpoint-inclusive scales 40..N, seven draws, three reruns. This differs from both the paper's inconsistent printed endpoint formula and released notebook. No result-dependent extra restarts or outlier removal is allowed. Conservative estimator failure guards are retained and all failures reported; no [2,18] result filter is applied.

## Length sensitivity and outcomes

Separately re-encode each pair's first L=min(256, human content length, generated content length) token IDs, adding normal boundary tokens. Both texts have equal token counts and restricted context. Do not slice an embedding cloud computed with future tokens. This matched-length condition is an extension, not an original-paper convention. Pairing controls shared prompt/genre, not semantic equivalence of independently generated continuations.

For each domain and pooled: report human/AI means, paired mean/median difference (human minus AI), proportion of pairs with positive difference, descriptive AUROC using human-positive orientation, and paired bootstrap 95% intervals (10,000 draws, seed20261004). Pooled bootstrap is stratified by domain. Report both seed results, profile sensitivity, length/truncation statistics, missingness and within-cloud Monte Carlo variation. No optimized threshold, fitted probability, p-hacking, test-split score or generalization claim.

## Runtime and resource bounds

Official legacy PyTorch CPU wheel is 190,367,618 bytes, published at https://download.pytorch.org/whl/torch_stable.html . Use Torch2.3.1+cpu, Transformers4.41.2, Tokenizers0.19.1, Safetensors0.8.0, NumPy1.26.4 in an isolated local virtual environment. Newer official CPU wheel host returned HTTP403; the legacy CPU artifact is a distinct officially published supported distribution. Do not use the CUDA distribution or evade denied access.

No upstream executable scripts are run. Independent local runner and already reviewed own estimator only. One process pinned to two available CPU cores, Torch/BLAS threads2, CPU float32, eval/inference mode, deterministic algorithms requested, no GPU, no paid APIs, no remote model code, no inference network fallback. Hard wall timeout 1,800s; monitored peak RSS cap3GiB; total downloads≤1.2GB and working disk≤3GB. Check intermediate outputs after each completed pair. Stop on budget or integrity failure; report incomplete rows rather than replace them.

## Rights and release limits

Model card states MIT. GPTID code is MIT, but a software license alone is not treated as a blanket grant for the underlying corpus. Wiki40B source texts inherit Wikipedia CC-BY-SA; the released generated completions/Reddit extracts lack a separate granular data license in this release. Authors explicitly release these archives for research replication. This run uses them privately, with source attribution and source hashes; raw text, weights and embedding arrays are not redistributed. Only code, provenance metadata and numerical findings may be proposed to the root for review/publication.
