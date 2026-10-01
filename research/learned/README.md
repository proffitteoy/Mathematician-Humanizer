# Trainable multi-view dynamics mechanics prototype

Status, 1 October 2026: **synthetic-only G1/G2 plumbing subset** implemented. Genuine
PyTorch parameters receive prediction gradients and pass a one-step optimizer
smoke test. No empirical author/human distribution was fitted, no text encoder
was downloaded here, and no trained weights are shipped. This does not mark the
full measurement, data-admission, generalization or compiler stage gates passed.

[Architecture and estimands](../../docs/design/learned-style-dynamics-v0.1.zh.md) ·
[Execution plan](../../docs/EXECUTION_PLAN.zh.md) ·
[Independent PH0/MST numerical module](../topology/README.md)

## Run

From the repository root, activate a CPU environment with the versions listed below:

```sh
python -m unittest discover -s research/learned -p 'test_*.py' -v
python -m research.learned.demo
```

The checked environment is Python 3.12, PyTorch 2.14.1+cpu, NumPy 2.3.5 and SciPy
1.17.0. The module itself imports PyTorch; actual topology fixtures additionally
use the existing NumPy/SciPy estimator. Nothing installs, downloads, scans data,
trains at import, or saves weights. The default `src/style_compiler` package and
its standard-library extraction path are unchanged. Tests and demo perform
explicitly synthetic backward/optimizer checks; they are not empirical training.

## Actual model, rather than interface stubs

- A prefix global MLP recomputes masked means, coverage and opportunity summaries
  from the supplied prefix. It cannot accept a caller-supplied full-document vector
- A one-layer, dropout-free causal Transformer has learned position embeddings
  and an explicit upper-triangular forbidden-attention mask
- A typed graph branch has trainable node-type embeddings, self transforms and
  relation-specific directed message transforms, followed by normalized incoming
  aggregation and permutation-invariant node pooling
- An optional trainable topology adapter consumes the independent alpha=1 PH0
  report: dimension, mean slope, slope dispersion, mean descriptive R² and point
  count. These are one correlated group, not five independent language constructs
- Learned fusion produces a query-prefix state. `z_stable` is inferred exclusively
  from other support works using permutation-invariant mean aggregation; an empty
  support set returns an explicitly labeled unfitted population-prior parameter
- `context_adaptation` is centered over the explicitly supplied reference contexts
  and weights. `z_context` adds a query residual. This is a coordinate convention,
  not evidence of independently recovered style/content or a full hierarchical posterior.
  The current context head is shared across authors; it does **not** implement an
  author-specific adaptation matrix/function B_A
- A learned next-action head emits independent Bernoulli logits conditional on the
  representation. Masked BCE admits overlapping positive actions and unknown labels.
  It is a conditional multilabel predictive loss, not a joint text likelihood.
  This prefix action predictor is **not yet** a learned full author-conditional
  transition-density model q_A(z,T | C); it has no learned stopping distribution

The width can be 16 or 32; these are engineering configurations, not demonstrated
intrinsic style dimensions. The fixtures have **four `toy:` channels**, not F001–F100
measurements and not an expansion from 8 to 64 operational features.

## Gates and honest information accounting

Each explicit channel has one shared, exactly binary forward gate across global,
sequence and graph-node values, presence flags, opportunity values and opportunity
availability flags. The topology group has another gate. A sigmoid straight-through
surrogate supplies gradients; this is a **biased optimization surrogate**, not the
paper's hard-concrete distribution, a calibrated selection probability or an L0
consistency guarantee. Fixed deployment masks can be set with `gates.freeze(...)`.

Effective entry weights have an explicit column-norm cap. A closed gate cannot be
compensated by multiplying downstream weights; no continuous gate amplitude is
advertised as importance. This does not make deep-network parameters identifiable.

Graph structure/node types, sequence order and declared context remain separate
paths, returned as `remaining_information_paths`. Thus four explicit channels being
closed does not imply the system has no information. No claim of empirical sparse
selection, causal feature importance or cross-domain stability is made. The gates start open; tests demonstrate
optimization connectivity and closure behavior, not a useful learned subset.

## Contracts and prefix protection

`contracts.py` uses frozen tuple-based records for measurement identity, opportunities,
missing reasons, local observations, exact-prefix graphs, topology snapshots,
work/lineage/content/dependency groups, release cutoffs and support/query episodes.

- Non-synthetic, personal and multi-producer documents are rejected. All channels
  must carry `toy:` identities, and the model pins their exact order and profile
- Observed zero requires a positive opportunity; unavailable measurements require
  a reason. Missing labels never contribute to BCE. An all-missing or noncontiguous
  target is rejected instead of silently returning a reassuring zero loss
- Graphs require an exact matching `prefix_recomputed` snapshot and input cutoff.
  Full graphs are never sliced into purported causal graphs. Future edges/nodes,
  duplicate typed edges, retrospective local measurements and future topology are rejected
- Graph IDs are dense and document-local. Author/lineage/topic strings are only
  eligibility metadata and are never embedded as model inputs
- Support cannot overlap the query or another support in work, lineage, content
  family or declared hard dependency groups. Support is same-author, cross-topic,
  same partition and available by the episode's cutoff; unrelated authors are not
  silently substituted as style positives
- Topology is taken only from the exact prefix and pinned representation/profile.
  Disabling its group or configuration is an actual ablation
- Whole-document length, future rows, future graphs and target labels are not read
  by prediction. Validation may reject malformed future records, but valid suffix
  replacements/appends leave prefix outputs unchanged
- Explicit resource guards bound documents, supports, graph size, sequence length
  and toy numeric range. These are engineering guards, not linguistic support criteria

These checks verify **declared** provenance. They cannot prove that an upstream
parser did not secretly use later text, discover undeclared near-duplicates, or
verify who wrote a work. A trusted, versioned extraction pipeline and independent
source/role/measurement audit remain necessary before empirical admission.

## Verified scope

39 synthetic tests currently cover active branch gradients, one optimizer update,
causal attention, suffix/length invariance, future graph/topology rejection, exact
prefix requirements, support/query and hard-dependency isolation, support-only
stable output, mask/value distinctions, unavailable inputs, shared binary gate
closure, weight caps, reference centering and overflow/underflow guards, multilabel missing-label gradients,
real numerical PH0 report integration, topology ablations, graph relation sensitivity
and local-node permutation invariance. The test count is not an empirical sample size.

`smoke-receipt.json` records a reproducible seeded synthetic run, branch gradients,
parameter count and scope. Its loss value is a mechanics check, not a model-quality
benchmark or evidence of generalized learning.

## Still deliberately missing

No automatic Chinese measurement extraction, 64-channel implementation, corpus
pair miner, source/near-duplicate auditor, actual author×topic identification,
contrastive/domain-adversarial objective, cross-domain stability selection, SSM
comparison, uncertainty/calibration model, variational hierarchy, observation-error
model, stop/censoring likelihood, full graph generation, edit ranker or semantic
preservation guarantee is implemented here. The stable/context heads may remain
confounded even though the information paths and centering are controlled.

## Next empirical gate

1. Resolve source versions and single-producer roles; establish independent works,
   task/topic labels, genuine crossed support and full hard leakage groups. The
   WikiConv structural count/repeated speaker keys alone are insufficient
2. Validate local measurement/action/graph annotations and their uncertainty in
   the intended domains; require verified prefix-local producers and explicit gaps
3. Freeze external splits, support/query episodes, actual feature identities,
   permitted uses and train-only transforms. Create a separately reviewed empirical
   admission path; do not bypass this prototype's synthetic gate by relabeling data
4. Before full-model claims, implement the preregistered static/ordered and typed-
   graph controls, topology controls, capacity/tuning budgets and selection-stability
   evaluation. A narrow approved empirical pilot is distinct from the ≥64-channel
   full-model gate; neither has been passed by these tests
5. Keep personal writings/blogs excluded until explicit final-personalization approval

Primary implementation references: [PyTorch TransformerEncoder](https://docs.pytorch.org/docs/2.14/generated/torch.nn.TransformerEncoder.html)
and [BCEWithLogitsLoss](https://docs.pytorch.org/docs/2.14/generated/torch.nn.BCEWithLogitsLoss.html).
The architecture document separates research-paper claims from project hypotheses.
