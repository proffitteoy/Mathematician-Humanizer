# Topology as a falsifiable Style Compiler component

Checked 1 October 2026. Primary source evidence and proposed modeling choices are separated below. This document does not define an AI-percentage score.

**Execution update (2026-10-01):** this is now an active parallel workstream, with an independent [numerical H0/MST implementation and tests](../research/topology/README.md). The [execution plan](EXECUTION_PLAN.zh.md) includes Chinese encoder replication, stability controls, and added-value tests in the learned multi-view/dynamics model; those text experiments have not run.

## 1. Classical primary literature and exact measured objects

### A. Attention-graph topology: Kushnareva et al., EMNLP 2021

[Paper, corrected v2](https://aclanthology.org/2021.emnlp-main.50v2.pdf), [record](https://aclanthology.org/2021.emnlp-main.50/). Object: BERT attention matrices over token vertices, truncated to 128 tokens. Thresholded directed graphs yield edge/cycle/component counts; undirected variants yield Betti numbers. Barcode construction reverses attention weights, `w -> 1-w`, for an increasing filtration; H0/H1 summaries and distances to attention patterns feed logistic regression. English datasets: WebText/GPT-2 Small 25k documents/class; Amazon/GPT-2 XL and RealNews/GROVER each 10k/class, with separate train/validation/test splits. Combined-feature accuracies: 87.7%, 61.1%, 63.6%; fully tuned BERT: 88.7%, 60.1%, 62.9%. Probes show surface/syntactic sensitivity rather than strong semantic coverage. Transfer tests use GPT-2 model sizes. These are older generators and English tasks. [Official code](https://github.com/danchern97/tda4atd) has no detected license. This is attention topology, not an embedding-cloud fractal dimension or discourse-quality metric.

### B. Embedding-cloud PH dimension: Tulchinskii et al., NeurIPS 2023

[Paper](https://proceedings.neurips.cc/paper_files/paper/2023/file/7baa48bc166aa2013d78cbdc15010530-Paper-Conference.pdf). Object: contextual token embeddings, excluding boundary tokens; RoBERTa-base for English, XLM-R for other languages; Euclidean geometry. H0 persistence reduces to MST edge lengths. Repeated subsampling estimates log-total-MST-length versus log-point-count slope; dimension is `1/(1-slope)`. Wikipedia, Reddit stories and StackExchange; GPT-2 XL, OPT-13B, text-davinci-003; ten-language WikiM uses GPT-3.5-turbo continuations from Wikipedia headers/first sentences. Chinese PHD AUROC: **.709**, not reliable individual attribution. Dimension depends on representation and estimator; it is stochastic and fragile for short or high-temperature/unfluent text. Random tokens can exceed natural-text dimension. No writing-quality causal test. [Code](https://github.com/ArGintum/GPTID) is [MIT licensed](https://github.com/ArGintum/GPTID/blob/main/LICENSE); source-corpus licenses remain separate.

### C. Short-text follow-up: Wei, Mao, Fang & Chau, 2025

[Short-PHD preprint](https://arxiv.org/abs/2504.02873); [COLM 2025 record](https://openreview.net/forum?id=IC2WwhUfQg); [code](https://github.com/djwei96/ShortPHD). The accessible preprint stabilizes short-text PH-dimension estimation by adding off-topic context before encoding. GPTID is supplemented with 500 human samples per domain from ELI5 and WikiHow and generations from five models, including GPT-4o. This is a detector-side measurement intervention, not evidence that putting unrelated content into user prose improves it. It is also not direct Chinese validation. The current official conference PDF could not be fetched (HTTP 403); exact preprint/conference equivalence remains unchecked. No repository license was detected. Treat preprint-specific measurements as version-qualified.

### D. Geometry and nuisance removal: Kuznetsov et al., Findings EMNLP 2024

[Robust AI-Generated Text Detection by Restricted Embeddings](https://aclanthology.org/2024.findings-emnlp.992.pdf), [code/data](https://github.com/SilverSolver/RobustATD). Transformer representation subspaces are removed to reduce domain-specific shortcuts in classifier transfer. Reported improvements are setting-specific and concern detection. This is useful motivation for testing nuisance-robust geometry but does not prove a particular Chinese manifold, covariance structure, or causal writing rule. It is representation geometry rather than persistent homology. Code/data license not inspected in this audit.

## 2. Prevent conceptual conflation

These are distinct research objects:

- H0 embedding-cloud topology: how contextual-token vectors connect as a metric threshold grows
- Attention-graph topology: how weighted token-to-token attention relationships connect
- Sentence-embedding trajectory: movement between ordered sentences; a proposed component here, not measured by the classic PHD paper
- Feature covariance: co-variation among interpretable scalar measurements across a defined unit
- Time: publication date, reply latency, token order, sentence order and rhetorical progression are different axes

A point cloud ignores the order in which its vectors are listed. Contextual encoding can embed order indirectly, but that does not turn the subsequent PHD calculation into an explicit measure of temporal dependence. To claim order sensitivity, perturb text order **before re-encoding** and compare with mere permutation of the already-computed vectors, which should leave a point-cloud score unchanged.

PH0/MST scaling is a fractal-dimension estimator under a specified finite-sample pipeline. It is not a count of ideas, truthfulness, consciousness, creativity or independently interpretable style dimensions. The word "invariant" in a paper title/argument should not be promoted into an encoder-free universal constant.

## 3. Proposed module: conditional geometric residuals

**Hypothesis:** geometry adds useful information about document-level coherence or style fit beyond interpretable surface/discourse variables, within a register and matched length. This remains untested.

The proposed module should be an optional diagnostic with uncertainty, not a rewrite objective. Its output is a small vector of standardized residuals relative to a matched reference stratum, plus stability intervals and applicable length range. If reliability is poor, return unavailable instead of manufacturing a score.

Start with an H0-only replication of the published estimator using frozen checkpoints and pinned settings. Keep an independent sentence-trajectory branch only if the research question needs order. Do not add H1, H2 or arbitrary topology features merely because they can be computed. Each additional dimension needs an incremental-value test and a stable estimator.

Reference strata should separate expository prose, academic abstracts, conversational comments, reflective essays and fictional narration. Do not use English Wikipedia dimension thresholds on Chinese comments. Avoid author-level conclusions from a register-level reference cloud.

## 4. Nuisance-control matrix

These are proposed controls, not claims that the cited papers already ran them all.

| Potential nuisance | Required control | Failure interpretation |
|---|---|---|
| Encoder/checkpoint/layer | Two independently trained Chinese-capable encoders; frozen versions; preregistered layers | Score may be an encoder artifact |
| Tokenization and script | Match Chinese character counts and independently match token counts; separate simplified/traditional; preserve raw version | Token count or script conversion explains signal |
| Number of points | Fixed-count subsampling; common range; repeated seeds and interval estimates | Finite-sample geometry explains signal |
| Length/position | Fixed windows sampled across document; opening-only separately labeled | Intro conventions or truncation explains signal |
| Topic/domain | Matched content briefs and held-out topics/sources | Semantic subject or website template explains signal |
| Punctuation/layout | Original plus controlled normalization ablation | Surface formatting explains apparent topology |
| Lexical variety/repetition | Compare against lexical diversity and repetition baselines | A cheaper feature is sufficient |
| Author/source overlap | Group splits by writer, source, near-duplicate cluster, document and prompt family | Memorization or leakage explains performance |
| Generation/revision | Multiple generators, prompts, temperatures and human revisions, recorded prospectively | Model/prompt-specific signature |
| Representation scaling | Pin raw Euclidean setup; predeclared normalized/cosine variants as sensitivity tests | Metric choice reverses conclusion |

## 5. Decisive ablation design

Create a small, provenance-checked Chinese pilot with multiple registers and content-matched briefs. Pre-register sample units and splitting before feature extraction. This avoids an expensive bulk-statistics exercise with no interpretable target.

Compare capacity-matched models:

1. Nuisance-only baseline: length, source/register, topic metadata
2. Interpretable baseline: character/word/part-of-speech profiles, function words, sentence/paragraph distributions, punctuation, repetition, stance and discourse-move transitions
3. Baseline plus feature covariance/ordered transitions
4. Baseline plus geometry (same data, capacity, tuning and split)
5. Geometry alone, as a diagnostic ablation rather than a product

Primary targets: blinded reader judgments of coherence, precision, voice consistency and task fit; semantic preservation assessed separately. Detector AUROC is at most an auxiliary historical replication metric. Report paired differences with author/document-cluster uncertainty; keep the test set untouched by feature selection.

Negative controls:

- Same embeddings permuted: exact cloud geometry must be unchanged; match transformed subset schedules or compare Monte Carlo distributions, since the same seed on permuted rows chooses different points
- Sentence-shuffled text re-encoded: tests sensitivity to coherence disruptions, with content held fixed
- Duplicate sentences, boilerplate insertion and formatting changes: tests shortcuts
- Random tokens and repetitive nonsense: can alter dimension without improving quality; must never receive a quality reward
- Semantically faithful editorial revisions: tests whether the signal aligns with actual improvements rather than arbitrary change

**Stop/drop criterion:** geometry adds no held-out reader-quality or style-fit value beyond surface/discourse baselines, or its direction changes across encoders/length controls. Retain it as descriptive research only if this happens. A significant human/AI difference alone is insufficient to retain it in a writing compiler.

## 6. Causal intervention requirement

Only after predictive added value is established, conduct controlled edits in matched pairs. Hold claims, evidence, audience and intended tone fixed. Randomize permissible editorial interventions, blind evaluators to condition, and compare quality gains and semantic damage. Do not directly optimize dimension or teach the editor to maximize a detector score. A correlation with provenance cannot identify the edit that helps a reader.
