# PUD64：解析引入的测量差异与覆盖审计

2026-10-01。**这是固定的小样本测量误差基准，不是作者／人类来源模型，也不把树库人工标注当作文体真值。** 未拟合、调阈值、下载新模型或修改71通道模块。原文、句号标识、逐句位置与解析保存在仓库外；本目录仅含方法、原创合成测试和汇总。

## 主要发现

64个固定记录全部原文对齐、全部操作句界相符、全部解析成功；这不等于词或依存正确。1,307个参考token中，生产解析只对齐1,004个精确跨度。词分割微平均F1为**71.74%**，303个参考token未匹配，488个预测token未匹配。

| 比较口径（含标点） | 正确数／分母 | 结果 |
|---|---:|---:|
| 生产token精确跨度 precision | 1,004／1,492 | 67.29% |
| 生产token精确跨度 recall | 1,004／1,307 | 76.82% |
| 生产UPOS一致，仅精确匹配dependent | 832／1,004 | 82.87% |
| 生产UPOS正确／全部参考token | 832／1,307 | 63.66% |
| 生产head跨度一致，仅精确匹配dependent | 506／1,004 | 50.40% |
| 生产head跨度正确／全部参考token | 506／1,307 | 38.71% |
| 生产head＋完整关系一致，仅匹配dependent | 377／1,004 | 37.55% |
| 生产head＋完整关系正确／全部参考token | 377／1,307 | 28.84% |
| 生产head＋关系主类正确／全部参考token | 410／1,307 | 31.37% |
| 参考token控制：UPOS一致 | 1,067／1,307 | 81.64% |
| 参考token控制：head跨度一致 | 919／1,307 | 70.31% |
| 参考token控制：head＋完整关系一致 | 678／1,307 | 51.87% |
| 参考token控制：head＋关系主类一致 | 723／1,307 | 55.32% |

这些是本审计明确定义的**跨度对齐协议分数**，不是官方CoNLL评测器的UAS/LAS成绩。输出字段中的 `head`／`full_las`／`base_las` 仅为内部量名；不能略去“匹配条件”或“全部参考token”分母。生产词汇参考子集共有1,126token，对齐824个；UPOS正确652个、head＋完整关系正确304个，分别为全部词汇参考token的57.90%和27.00%。完整分母、新闻／百科分层、端点机会与标签混淆见[汇总JSON](pud64.aggregate.json)。

控制实验只把参考分词提供给同一套POS／依存权重，不提供参考POS、lemma、FEATS、HEAD或DEPREL。控制组相对生产组的改善是这批文本上的诊断，不是独立因果误差分解：分词改变还会改变后续模型输出。生产组82.87%的匹配token UPOS一致率不能与控制组81.64%的全token一致率直接比较。两组同用全部参考token分母时，UPOS由63.66%升至81.64%。

## 冻结来源、许可与训练关系

- 官方 **UD_Chinese-PUD r2.15**，提交 `0fac7efa55abcb79e07ba1ceefe1139f9f0c58b9`，不是浮动master
- [固定版本README](https://github.com/UniversalDependencies/UD_Chinese-PUD/blob/0fac7efa55abcb79e07ba1ceefe1139f9f0c58b9/README.md)与[许可](https://github.com/UniversalDependencies/UD_Chinese-PUD/blob/0fac7efa55abcb79e07ba1ceefe1139f9f0c58b9/LICENSE.txt)声明 **CC BY-SA 3.0**；底层文字与转换标注的来源／保证限制仍保留，未重新分发语料
- [固定语料文件](https://github.com/UniversalDependencies/UD_Chinese-PUD/blob/0fac7efa55abcb79e07ba1ceefe1139f9f0c58b9/zh_pud-ud-test.conllu)：2,169,911字节，SHA-256 `d3393dd44eb9ae71a6eaa626581c1f760db6148f0d2c6378c2200835e2ede37a`
- 上游有1,000个记录，新闻／百科各500；UPOS和基本依存是从人工非UD标注转换而来。文本来自专业翻译的PUD新闻／百科材料；记录不保证一条就是一个完整原作品或真实句子，也不保证相邻
- 参考它作为语言学标注基准，不推断作者、自然人生产历史、未获辅助创作或风格代表性。官方标为test不证明对当前模型真正未见
- 生产配置固定 **Stanza1.10.1 / resources1.10.0 / zh-hans GSDSimp nocharlm**，复用既有五个摘要核验通过的权重，CPU2线程。Stanza[发布记录](https://stanfordnlp.github.io/stanza/release_history.html)把该系列关联到UD2.15；详细权重身份沿用[已审查profile](../linguistic/parser-profile.json)
- GSDSimp是另一个具名监督训练树库；PUD不是该profile列出的训练树库。但未比对完整监督训练文本、训练管线的所有历史用途或预训练文本。fastText官方说明其[词向量用Common Crawl与Wikipedia训练](https://fasttext.cc/docs/en/crawl-vectors.html)，因此文本重叠未知，**不称“真正未见”**

[来源收据](source-receipt.public.json)记录原始响应摘要及字节。总新增获取2,225,977字节，包含标签元数据、README、许可、语料和三个官方注释元数据文件；低于5MB上限。浏览查询与HTTP协议开销不计入文件字节。没有执行下载的脚本，没有新模型／软件下载，没有凭据、付费或远端写入。

## 预注册、单位与匹配规则

[预注册](preregister.public.json)于第一次解析输出前冻结。按公开固定seed与sent_id的SHA-256排序，在news/wiki各取前32记录；不因失败替换。私有选择清单摘要见JSON。该单位是树库记录，**不是64个已证实独立作品**；newdoc标签不能补足来源独立性，故不报句子IID置信区间。

1. 从原始UTF-8 CoNLL-U的精确 `# text` 字段取输入，只去掉容器LF边框。不做NFC、空白、标点、简繁或换行规范化
2. 参考整数token行逐项匹配FORM，仅越过输入中已有的token间空白。不模糊搜索、不重建句子、不丢掉不匹配字符；额外multiword或empty-node行使该记录参考不可用
3. 检查稠密ID、合法head、唯一root和无环。参考使用独立 `ReferenceSentence`，明确标注 `converted_manual_treebank_reference`；不冒充生产契约中的synthetic或automatic状态
4. 原生产 `LocalStanza` 对完整原文按既有 `punctuation-lines/1.0.0` 运行。只有其恰为一个覆盖完整记录的源句、参考可对齐且两臂都成功时才进共同比较集。其他记录／token仍留在覆盖分母，不能修改参考树迎合边界
5. token只按原码点半开跨度一一匹配；head只按原head跨度或明确root标志比较。关系同时报完整子类型与主类，不把未匹配token／head当作正确
6. 全部记录包括标点；另报按**参考定义**确定的词汇token子集。词汇条件不因预测标签而改变评分分母
7. 显式区分64条记录、1,307个参考token、1,492个预测token、1,004个匹配dependent，以及658个两侧head跨度都可找到的匹配dependent。端点“可找到”不是依附正确

本次0条参考对齐失败、0条句界不符、0条生产／控制解析失败，因而全部64条进入共同集。失败支路仍有原创合成测试；本次0个失败并不验证其他文本的边界准确率。

## 标注口径与模型错误分开解释

GSDSimp r2.15沿用2.13对PART／ADV改为SCONJ的变更；PUD r2.15保留不同口径。固定官方统计中，PUD的“的”为PART 1,361、X 1；GSDSimp为PART 3,232、SCONJ 2,405。这些是**上游整树库统计**，不是本次样本计数或某个功能的错误率。参见[GSDSimp变更](https://github.com/UniversalDependencies/UD_Chinese-GSDSimp/blob/r2.15/README.md)、[PUD固定PART统计](https://github.com/UniversalDependencies/docs/blob/r2.15/treebanks/zh_pud/zh_pud-pos-PART.md)、[GSDSimp固定PART统计](https://github.com/UniversalDependencies/docs/blob/r2.15/treebanks/zh_gsdsimp/zh_gsdsimp-pos-PART.md)。

本次已对齐token的UPOS分歧中，PART→SCONJ有48次、ADV→SCONJ有43次；全部UPOS分歧为172次。它们与口径风险相容，但**没有逐项人工裁定，不能把91次全部归因为约定差异**。也没有为了提高分数映射或合并标签。

另有88个参考token的完整关系不在已加载依存模型词表：obl:tmod 12、case:loc 20、flat 5、mark:prt 24、dep 27。取主类后仍有27个dep不在模型主类库存。此类能力／口径不兼容必须先披露；合法参考标签不会被改成模型支持的标签。句界、分词、字形、翻译体／体裁、参考转换和预测误差在这个小基准中仍然混杂，**不能由这些分数单独辨认真正的解析失误占比**。

## 下游71通道：差异而非通过清单

使用冻结 `_aggregate` 公式对每条参考／预测分析分别计算。每个通道记录双方机会与分母、配对条数、带符号偏差、逐记录MAE、最大绝对差、同一配对子集重新汇聚的值。没有把不同尺度平均成总分，没有为了对齐删掉模型多出的token。

| 通道 | 配对记录 | 生产MAE | 参考token控制MAE | 说明 |
|---|---:|---:|---:|---|
| NOUN份额 | 64 | 0.0901 | 0.0368 | 生产约9.01个百分点 |
| SCONJ份额 | 64 | 0.0750 | 0.0758 | 固定分词后口径／POS分歧仍在 |
| 平均词码点长 | 64 | 0.2473 | 0.0047 | 控制仍受预测PUNCT排除影响 |
| 单Han token份额 | 64 | 0.1863 | 0.0039 | 显著依赖分词 |
| 依存跨度均值 | 64 | 0.4647 | 0.3894 | 单位为各分析的非标点token秩 |
| 依存深度均值 | 64 | 0.3545 | 0.2943 | 各分析原基本树的root距离 |
| VERB根无subject子边 | 46 | 0.2391 | 0.1739 | 仅46条两边都有该机会；不是零主语率 |

例如控制组的VERB根无subject子边同支持汇总与参考同为0.1087，但逐记录MAE仍为0.1739。**聚合均值相等可掩盖个体记录抵消，不能据此证明通道正确。**

生产词汇分母T为1,303，参考T为1,126；控制虽使用相同token跨度，T仍为1,120，原因是预测POS影响PUNCT排除。基本非标点弧分母A依次为1,239、1,062、1,056。不能假设给定参考分词就固定了所有特征分母。

- 71个通道都有覆盖账目，65个存在至少一个有效数值配对；这**不是65个已验证通道**
- **6个无支持**：MATTR100、100-token词形熵、100-token POS二元熵，以及相邻内容词重合、先前句三词串复用、句首POS复用。前三项没有实际百词窗；后三项没有可信的连续先前语境。不缩窗、不拼随机记录、不把第一条的空历史当成已验证0
- 在有机会的通道中，生产臂dislocated关系全部为0，属于无正事件证据；控制臂另有iobj、guo辅助形式两项无正事件证据。机会大于0的零可以保留为观察，但不能证明事件检测可靠
- 分母为0的句级通道仍为缺失。例如VERB根指标仅46／64条双边可比；完整逐通道覆盖在JSON中，不以64概括全部通道

## 实现、验证与复跑

[评测程序](evaluate.py)只消费本地文件与已核验权重，整个加载／推理期间禁止socket连接。未进入真实分布fit、学习门控、个人作品或改写路径；所有 `comparison_eligible` 仍为false。已对审计期冻结模块源文件逐个摘要，不修改生产状态枚举。

```sh
PYTHONPATH=src:. python -m unittest research.parser_error.test_evaluate -v
PYTHONPATH=src:. python -m research.parser_error.freeze_selection \
  --private-dir /path/outside/repo/pud-audit
PYTHONPATH=src:. /path/to/existing/python -m research.parser_error.evaluate \
  --private-dir /path/outside/repo/pud-audit \
  --models /path/to/existing/stanza-models \
  --output research/parser_error/pud64.aggregate.json
PYTHONPATH=src:. python -m research.parser_error.verify_aggregate \
  --private-records /path/outside/repo/pud-audit/per-record.private.json \
  --aggregate research/parser_error/pud64.aggregate.json
```

复跑需要外部固定语料和私有选择清单；程序不下载它们。`freeze_selection`可按公开预注册规则生成清单，拒绝覆盖已有清单；已有清单用`--verify-existing`核对。清单只保存私有ID／原始位置／摘要，公开规则足以重新产生同一集合。14项原创合成测试覆盖错位、未匹配head、标点分母、子类型区别、短窗、伪历史、句界／参考／解析失败保留。另一独立实现不用生产评分函数／71通道聚合器，重算评分与六个下游量，共120项汇总比较通过。测试是实现核对，不是额外自然样本。

本次结果只能支持“在这个预先固定的PUD切片上，生产分词和标注口径给这些候选测量带来可观差异”。下一次应另行预注册能区分字形／体裁／标注口径的对照；不得在本切片调标签映射、阈值或选指标后再称独立验证。
