# 中文语言学测量：解析器与来源审计

审计日期：2026-10-01（UTC）。本报告只确立版本、资源身份、许可出处和标注口径，不确立解析准确率、测量效度、作者识别效度或各通道的独立性。未获取自然语料文件；仅检查官方文档、发布元数据和聚合统计。权重下载、安装、哈希实测与运行测试由独立的执行记录负责。

## 1. 固定配置与下载预算

选用 **Stanza 1.10.1 / resources 1.10.0 / zh-hans GSDSimp nocharlm**。代码中的[版本声明](https://raw.githubusercontent.com/stanfordnlp/stanza/v1.10.1/stanza/_version.py)固定资源版本；[发布记录](https://stanfordnlp.github.io/stanza/release_history.html)说明 1.10 系列按 UD 2.15 重建。只启用 tokenize、pos、lemma、depparse；共享 fasttext157 预训练词向量，不启用默认完整包、NER、情感、成分句法、charlm 或 transformer。

[官方模型仓库元数据](https://huggingface.co/api/models/stanfordnlp/stanza-zh-hans/revision/v1.10.0)将 v1.10.0 解析到提交 `82f2856d1cf4f933738a8a84b5ad959d156040a0`，且 public、ungated。[官方文件清单](https://huggingface.co/api/models/stanfordnlp/stanza-zh-hans/tree/v1.10.0/models?recursive=true&expand=false)提供逐文件字节数和 LFS SHA-256：

| 文件（models/ 下） | 字节数 |
| --- | ---: |
| tokenize/gsdsimp.pt | 1,383,326 |
| pos/gsdsimp_nocharlm.pt | 21,285,503 |
| lemma/gsdsimp_nocharlm.pt | 6,592,066 |
| depparse/gsdsimp_nocharlm.pt | 103,928,202 |
| pretrain/fasttext157.pt | 306,614,467 |
| 五个模型合计 | **439,803,564** |

`parser-profile.json` 保存每个文件的完整官方 URL、大小和 SHA-256，以及 [resources 清单](https://raw.githubusercontent.com/stanfordnlp/stanza-resources/main/resources_1.10.0.json)的内容摘要。清单 URL 使用可变的 main 分支，须按记录的 SHA-256 核验，不能仅凭文件名认为版本固定。

环境已具备 Torch、NumPy、NetworkX、tqdm。以审计时 PyPI 的 Linux/Python3.12 兼容 wheel 元数据计算，模型、resources、Stanza 和缺失依赖共 **442,976,779 字节**，低于十进制 1 GB。依赖版本表用于可核算的预算快照，不是已验证的环境锁；该数字不表示安装占用或运行内存。

## 2. 许可必须分层记录

- Stanza 代码：[Apache-2.0](https://github.com/stanfordnlp/stanza/blob/v1.10.1/LICENSE)
- [HF 模型卡](https://huggingface.co/stanfordnlp/stanza-zh-hans/blob/v1.10.0/README.md)声明 Apache-2.0；不能据此将所有上游资源统一标为 Apache
- [Stanford 模型说明](https://stanfordnlp.github.io/stanza/performance.html)明确提示 UD 模型的许可问题，并仅对 Stanford 有权处分的语言包权益提供 ODC Attribution 1.0
- [GSDSimp r2.15 README](https://raw.githubusercontent.com/UniversalDependencies/UD_Chinese-GSDSimp/r2.15/README.md)：标注为 CC BY-SA 4.0；历史 NC 限制的移除针对 UD 标注，不代表 Google 拥有底层文章版权
- [fastText 157-language vectors](https://fasttext.cc/docs/en/crawl-vectors)：CC BY-SA 3.0

保留来源、署名与各层许可，勿将整个包描述为统一的宽松许可。备选 [UDPipe 1](https://ufal.mff.cuni.cz/udpipe/1/models) 的代码许可与模型许可不同：代码 MPL-2.0，官方 UD2.5 模型 CC BY-NC-SA；本审计未核实单个官方模型文件的下载大小，故未选用。

## 3. 标注清单与测量子集

依据[固定的 r2.15 stats.xml](https://raw.githubusercontent.com/UniversalDependencies/UD_Chinese-GSDSimp/r2.15/stats.xml)，完整树库含 16 个 UPOS（含 PUNCT）、43 个完整依存标签，去掉冒号子类型后为 32 个主类（含 root、punct）。这不是模型输出词表的实测，也不是仅训练集统计。

测量设计采用 13 个词汇/功能 POS 分量；SYM、X 不计标量通道，但保留在解析、图和质量统计，PUNCT 不进词汇分母。依存组成采用 27 个主类分量：在 32 类中排除 root、punct、orphan、reparandum、vocative，但图中仍保留它们及所有完整子类型。后三类在全树库只有 2、1、1 例，不应靠扩充稀有标签制造通道宽度。INTJ、expl、fixed、goeswith、dep 等通用合法标签不能自动视作本模型可测项目；须另行冻结实际加载词表。合法但模型不支持、解析缺失、确实观察到零是三种不同状态。

## 4. 的／地／得：以 r2.15 为准

通用中文 UD 页有部分旧口径，不能覆盖固定版本的树库证据。GSDSimp README 记录：2.8 统一若干关系名；2.13 将部分 PART/ADV 改为 SCONJ。下面引用的是官方 docs 仓库 **r2.15**，提交 `930595812fe33764cc2625ec9b7b36f7136b05db`，不是会变化的当前网页；每份文档的字节数和摘要均在 JSON 中。

- **的**：[r2.15 PART 统计](https://raw.githubusercontent.com/UniversalDependencies/docs/r2.15/treebanks/zh_gsdsimp/zh_gsdsimp-pos-PART.md)明确给出 PART 3,232、SCONJ 2,405。名词属格相关用法可为 PART/case；[mark:rel 统计](https://raw.githubusercontent.com/UniversalDependencies/docs/r2.15/treebanks/zh_gsdsimp/zh_gsdsimp-dep-mark-rel.md)的全部 2,427 个依存项为 SCONJ。`的 ∧ POS∈{PART,SCONJ}` 有版本依据，但混合多个功能，不是属格、关系从句或名词化构式识别器。
- **地**：[r2.15 mark:adv 文档](https://raw.githubusercontent.com/UniversalDependencies/docs/r2.15/treebanks/zh_gsdsimp/zh_gsdsimp-dep-mark-adv.md)明确展示 地/SCONJ；全部 104 个 mark:adv 项均为 SCONJ，也展示以“的”实现此关系的情况。因而 `地 ∧ SCONJ` 是固定版本的方式标记证据；加入 PART 只能称宽口径/旧版兼容门，不应声称本审计证明 r2.15 的方式“地”为 PART。单独按“地”统计还会漏掉异形用字。
- **得**：[r2.15 compound:ext 文档](https://raw.githubusercontent.com/UniversalDependencies/docs/r2.15/treebanks/zh_gsdsimp/zh_gsdsimp-dep-compound-ext.md)明确展示 得/PART；全部 25 项为 PART，中心词 24 项 VERB、1 项 ADJ。`得 ∧ PART` 可作为该表面标记的候选计数，不能证明获得/情态等其他“得”用法均已覆盖，更不能仅凭 POS 宣称完整程度/状态补语构式。

这里的总数属于关系或全树库统计，不能误写成某个字在训练集或模型预测中的召回率。

## 5. 十个闭类线索的解释边界

所有线索均须明确命名为**不完整的“精确表面词形＋预测 POS”代理量**，而非语法角色或完整构式。

1. 第一、第二、第三人称：PRON 门控的显式词表只覆盖列出的显现形式，不解析零主语、指称对象、引语发言者、句法角色或共指
2. ADV 否定词：只计词表中的 ADV 形式；会漏掉 AUX/VERB/PART 否定及不同切词结果，不能称“总否定率”
3. 的、地、得：上节门控保留语境差异；不得对子串匹配，或把同形 token 的所有用途强制合并为一种构式
4. 了、着/著、过/過：AUX 门控排除句末 PART 等用途，但不等于完整体貌识别；通用[句末粒子说明](https://universaldependencies.org/zh/dep/discourse-sp.html)特别指出“了”的语境歧义
5. 简体模型加入繁体形式词表不证明繁体覆盖；不得静默转换输入；保留来源字符、token 范围、原始完整关系和质量信息
6. 本树库 PART 包括许多类似词缀的单位，因此 PART 组成分量也不能直接解释为传统“虚词/助词率”

其他典型歧义包括在的介词/动词用法、和/与/跟的连接/介词用法、被的不同被动结构，以及 classifiers 的 NOUN/clf 分离。参见[中文 ADP](https://universaldependencies.org/zh/pos/ADP.html)、[CCONJ](https://universaldependencies.org/zh/pos/CCONJ.html)、[中文总览](https://universaldependencies.org/zh/index.html)。这些语言学说明用于解释风险，不替代本模型的输出审计。

## 6. 运行与效度限制

Stanza 1.10.1 的 [POS](https://raw.githubusercontent.com/stanfordnlp/stanza/v1.10.1/stanza/models/pos/trainer.py)和[依存加载器](https://raw.githubusercontent.com/stanfordnlp/stanza/v1.10.1/stanza/models/depparse/trainer.py)显式使用 `weights_only=True`；[历史 pretrain 加载器](https://raw.githubusercontent.com/stanfordnlp/stanza/v1.10.1/stanza/models/common/pretrain.py)有回退到 `weights_only=False` 的路径，因此仅加载官方、摘要核验通过的资源。需要单独完成安装 smoke test、加载词表审计和源文本范围对齐测试。本报告没有执行模型。

[公开性能表](https://stanfordnlp.github.io/stanza/performance.html)描述 v1.5.1 / UD2.12 的 charlm 配置，不能把其分数移植到本 nocharlm 配置。解析器能输出某种标签、合成测试能通过、统计分量数量增加，均不构成人工标注一致性、体裁迁移、风格区分或作者相关效度证据。

## 主要方法文献

- Qi, Peng, Yuhao Zhang, Yuhui Zhang, Jason Bolton, and Christopher D. Manning. 2020. [Stanza: A Python Natural Language Processing Toolkit for Many Human Languages](https://aclanthology.org/2020.acl-demos.14/). ACL System Demonstrations
- Nivre, Joakim, et al. 2020. [Universal Dependencies v2: An Evergrowing Multilingual Treebank Collection](https://aclanthology.org/2020.lrec-1.497/). LREC

上述论文支持工具和标注框架的来源，不为当前测量设计提供已完成的效度验证。
