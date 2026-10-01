# Style Compiler

把可测量的写作选择，转成受语义约束、可复测、可回退的编辑操作。

**当前状态：研究原型，不是经过验证的风格模型。** 已实现八个字级/句段序列指标、可追溯数据契约、泄漏分组、真实数据门控的条件总体模型，以及一种需要语义复核的段落边界操作。研究侧已对一个22,364字节的官方历史对话派生包做[本地来源/格式审计](docs/design/provenance-feasibility-v0.1.zh.md)，发现版本与上下文限制；原文不入仓库，H_G准入为零。没有拟合任何总体或作者分布，没有“人类概率”、校准百分位或干预效果结论。

The statistical core and research protocol are separate: executable code establishes reproducible measurements and explicit failure states; only future, rights-checked experiments can establish construct validity or writing benefits.

## Active model and execution

The final model is the learned **Sparse Multi-view Hierarchical Style Dynamics Model**: global observables, linguistic sequences and discourse graphs, with stable/context representations and conditional dynamics. The present statistical code is a baseline. See the [active execution plan](docs/EXECUTION_PLAN.zh.md). The [topology replication track](research/topology/README.md) now has a runnable H0/MST numerical component; Chinese text replication and incremental-value testing remain unperformed.

## Run locally

Python 3.11+. Extraction, partitioning and constrained editing use only the standard library. NumPy is optional and used only for the experimental model.

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
style-compiler --help
```

Without installing anything:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m style_compiler --help
```

A document must explicitly provide the [versioned JSON contract](schemas/document.schema.json). Supply a local document file; extraction does not fetch a corpus, install a model, or call a language-model service.

```sh
style-compiler extract document.json -o measurement.json
style-compiler split corpus.jsonl -o partition.json
style-compiler fit corpus.jsonl --partition partition.json --cohort H_G -o population-model.json
style-compiler plan document.json --max-sentences 4 --protect '约三人' -o plan.json
```

`fit` returns an explicit unavailable result unless declared non-synthetic, non-personal training data and a leakage-screened partition meet the support policy. The H_G gate checks declared metadata, including a nonempty author ID and an unassisted label. Rights/provenance flags record an external review claim; the code does not independently verify identity, production history, or the absence of assistance. Install `.[model]` to enable the optional numerical dependency. No fitted artifacts are included.

`plan` proposes one paragraph break for an explicitly supplied structural constraint. It reports exact candidate deltas, never learned causal effects. Applying an inspected candidate requires a separate deliberate action:

```sh
style-compiler apply document.json --plan plan.json --semantic-review-approved -o revised-document.json
```

The flag records the caller's approval; the software cannot verify that a human actually reviewed meaning. Keep the original document for rollback. A repeated `plan` call is needed for any further edit.

## What exists

- Eight operational metrics: paragraph density, single-sentence paragraph share, sentence-length median/IQR/p90/normalized MAD, adjacent length change, and lag-1 rank correlation
- Unchanged-input offsets and ordered sentence/paragraph sequences; empty, short, constant and dependency-missing cases remain distinguishable
- Hard work/lineage/content/near-duplicate grouping; explicit author/prompt/source/topic/generator holdout axes, lexical duplicate screening and infeasibility reporting
- Experimental regularized conditional mean and pooled residual covariance code, using language/genre/topic/task strata and continuous log length, with training-only transforms and out-of-support abstention
- An experimental paragraph-boundary plan with protected-content checks, mandatory semantic review and stale/tampered-plan rejection
- Synthetic unit tests that verify software behavior, **not empirical evidence about writing**

## What remains unavailable

Chinese word segmentation, POS/dependency parsing, discourse and stance annotation, embeddings/topology, validated measurement error, hierarchical effects, cluster-aware intervals, calibration, learned intervention effects, and a general semantic rewrite engine. Installing a parser alone would not validate its outputs in the target genre.

Personal voice compilation is deliberately disabled. Personal writings and `proffitteoy/nothing-new` are excluded until explicit final-personalization authorization and a separately reviewed implementation. Do not use a “human style” target to overwrite individual choices.

## Read next

- [Architecture and exact measurement definitions](docs/architecture.md)
- [Research protocol, hypotheses and promotion gates](docs/research-protocol.md)
- [Primary-source audit](docs/evidence-audit.md)
- [Optional skill entrypoint](.agents/skills/style-compiler/SKILL.md)

No raw corpus, third-party implementation, pretrained model or fitted result is committed. The repository currently makes no software-license grant; decide licensing before redistribution.

Research detail: [100-candidate registry](docs/design/feature-schema-100.zh.json), [measurement conventions](docs/design/feature-schema-guide.zh.md), [proposed preregistration](docs/design/research-preregister.zh.md), [statistical design](docs/design/statistical-model.zh.md), [topology evidence](docs/topology-component.md), [corpus provenance](docs/corpus-provenance.md), and [restricted-corpus addendum](docs/corpus-admission-addendum.md). The catalogue is not an implementation checklist: only eight metrics are active.

## Modeling research notes

These are research contracts and hypotheses, not fitted models or validated features.

- [Competing models and identifiability](docs/design/modeling-dossier-v0.1.zh.md)
- [Chinese construct diagnostics](docs/design/diagnostic-construct-map-v0.1.zh.md)
- [Dispersion and mixture composition](docs/design/dispersion-mixtures-v0.1.zh.md)
- [Referential continuity measurement contracts](docs/design/referential-continuity-contract-v0.1.zh.md)
- [Production provenance and reader perception](docs/design/provenance-perception-register-v0.1.zh.md)
- [Observational references and partial identification](docs/design/observational-reference-admission-v0.1.zh.md)
