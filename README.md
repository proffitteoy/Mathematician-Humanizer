# Style Compiler

把可测量的写作选择，转成受语义约束、可复测、可回退的编辑操作。

**当前状态：研究原型，尚未经文体效果验证。** 已有八个字级/句段序列指标，另有[71维语言学候选模块](research/linguistic/README.zh.md)与实际可运行的本地中文解析。学习型多视图原型和拓扑分支已完成合成机制测试；尚无真实总体/作者模型拟合、校准概率或改写效果结论。

[来源登记](research/source-registry.json)现涵盖WikiConv年度快照、39个固定版本开放许可博客文件及6份学术全文试点。版本、内容角色、辅助生产证据和测量覆盖分别审计；这些数量不等同独立作者或已验证人类参考，原文不入仓库。

The statistical core and research protocol are separate: executable code establishes reproducible measurements and explicit failure states; only future, rights-checked experiments can establish construct validity or writing benefits.

## Active model and execution

The final model is the learned **Sparse Multi-view Hierarchical Style Dynamics Model**: global observables, linguistic sequences and discourse graphs, with stable/context representations and conditional dynamics. The present statistical code is a baseline. See the [learned-model architecture](docs/design/learned-style-dynamics-v0.1.zh.md) and [active execution plan](docs/EXECUTION_PLAN.zh.md). The [trainable mechanics prototype](research/learned/README.md) now connects global, causal sequence, typed graph and optional topology branches, with synthetic-only gradient/leakage tests. The [topology replication track](research/topology/README.md) includes a pinned local encoder and reproducible synthetic Chinese extraction. Neither establishes natural-text validity or held-out incremental value.

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

- Eight legacy operational metrics: paragraph density, single-sentence paragraph share, sentence-length median/IQR/p90/normalized MAD, adjacent length change, and lag-1 rank correlation
- Unchanged-input offsets and ordered sentence/paragraph sequences; empty, short, constant and dependency-missing cases remain distinguishable
- Hard work/lineage/content/near-duplicate grouping; explicit author/prompt/source/topic/generator holdout axes, lexical duplicate screening and infeasibility reporting
- Experimental regularized conditional mean and pooled residual covariance code, using language/genre/topic/task strata and continuous log length, with training-only transforms and out-of-support abstention
- An experimental paragraph-boundary plan with protected-content checks, mandatory semantic review and stale/tampered-plan rejection
- A separate 71-channel POS/dependency/lexical candidate vector, sentence sequences and typed syntax graph; these are correlated sensors, not a validated combined79-channel model
- Separate synthetic-only trainable multi-view mechanics and pinned local Chinese-encoder topology extraction; see their research READMEs for dependencies and scope
- Synthetic unit tests that verify software behavior, **not empirical evidence about writing**

## What remains unavailable

Validated Chinese segmentation and POS/dependency accuracy, discourse and stance annotation, empirical embeddings/topology validity, measurement error, fitted hierarchical effects, cluster-aware intervals, calibration, learned intervention effects, and a general semantic rewrite engine. Installing a parser alone would not validate its outputs in the target genre.

Personal voice compilation is deliberately disabled. Personal writings and `proffitteoy/nothing-new` are excluded until explicit final-personalization authorization and a separately reviewed implementation. Do not use a “human style” target to overwrite individual choices.

## Read next

- [Architecture and exact measurement definitions](docs/architecture.md)
- [Research protocol, hypotheses and promotion gates](docs/research-protocol.md)
- [Primary-source audit](docs/evidence-audit.md)
- [Optional skill entrypoint](.agents/skills/style-compiler/SKILL.md)

No raw corpus, third-party implementation, pretrained model or fitted result is committed. The repository currently makes no software-license grant; decide licensing before redistribution.

Research detail: [100-candidate registry](docs/design/feature-schema-100.zh.json), [measurement conventions](docs/design/feature-schema-guide.zh.md), [proposed preregistration](docs/design/research-preregister.zh.md), [statistical design](docs/design/statistical-model.zh.md), [topology evidence](docs/topology-component.md), [corpus provenance](docs/corpus-provenance.md), and [restricted-corpus addendum](docs/corpus-admission-addendum.md). The catalogue is not an implementation checklist: the legacy core exposes eight metrics, and the separate research module implements 71 candidate channels; neither count establishes validated style dimensions.

## Modeling research notes

These are research contracts and hypotheses, not fitted models or validated features.

- [Competing models and identifiability](docs/design/modeling-dossier-v0.1.zh.md)
- [Chinese construct diagnostics](docs/design/diagnostic-construct-map-v0.1.zh.md)
- [Dispersion and mixture composition](docs/design/dispersion-mixtures-v0.1.zh.md)
- [Referential continuity measurement contracts](docs/design/referential-continuity-contract-v0.1.zh.md)
- [Production provenance and reader perception](docs/design/provenance-perception-register-v0.1.zh.md)
- [Observational references and partial identification](docs/design/observational-reference-admission-v0.1.zh.md)

The [2017 annual-view census](research/audits/wikiconv-2017-execution.zh.md) records 525,984 source records, including 178,894 nonempty explicit nonheaders. These are structural source counts, not verified human samples or validated linguistic observations.


## 当前验收与测量证据

[两阶段验收条件](docs/ACCEPTANCE.zh.md)由项目所有者最终判断，模型分数不能代替验收；个人阶段按该文档的条件授权启动。

[固定PUD64解析测量试点](research/parser_error/PUBLICATION_STATUS.zh.md)已独立复算；生产分词及标注约定造成明显的测量差异。请同时阅读冻结方法、复审和已知缺字段健壮性缺陷，不将本次结果当作通用文体模型验证。


[测量识别与联合观测模型](docs/design/measurement-identification/MEASUREMENT_IDENTIFICATION_DRAFT_ZH.md)及[独立复核](docs/design/measurement-identification/FINAL_RECHECK_ZH.md)明确区分回顾解析与前缀预测，处理相关仪器、机会、失败和桥接选择。它们是尚未拟合的数学接口；不会因架构更复杂而自动恢复真实文体。技能入口已同步现有71通道、本地解析与拓扑能力，未宣称最终编译器完成。


## 首轮真实观测模型结果

[十五次train/dev拟合与独立复核](research/observed_sequence/results/train-dev-v01/README.zh.md)已完成：固定160条来源、2480单元、68项局部输入；目标是下一操作单元的观测POS组成。顺序GRU相对DeepSets的开发收益很小且种子方向不一致，不能据此宣称稳定文体动力学。测试仍按冻结流程单独评估。该窄实验不等于完整风格模型或写作技能验收。
