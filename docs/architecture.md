# 结构与运行协议

## 一条研究链，一个写作入口

`本地文本/冻结测量 → 统计汇总 → 可解释的风格卡 → mathematician-humanizer 改稿 → 内容复核`

根目录 `SKILL.md` 是唯一技能正文，包含完整的参考数学家改写工作流、六项论证习惯与 Humanizer 26 项清理规则。`references/` 中的两张生成卡供核对研究范围与体裁差异。普通写作直接使用技能正文；分析工具用于研究更新、示例评估或用户明确要求的核验。

最小安装内容为 `SKILL.md`、`references/` 与 `agents/openai.yaml`。不需要复制 `src/`、`research/` 或安装 Python。根目录单一入口、技能元数据与具体前后例子的写法参考 Humanizer；本项目不承诺未经验证的平台插件兼容性。

## 代码职责

| 文件 | 职责 |
|---|---|
| `segmentation.py`、`features.py` | 原始码点跨度、8 项字级/句段测量与缺失原因 |
| `contracts.py`、`surface.py` | 不变文本、来源身份和保留缺口的投影；内部研究合同 |
| `linguistic/` | 71 项 POS/依存/词汇观测；可选固定本地 Stanza 适配器 |
| `statistics.py` | 文档先在分量内合并，再对分量等权；来源内配对与探索性区间 |
| `profiles.py` | 核对冻结输入，编译参考博客风格卡与中文统计补充 |
| `editorial.py` | 不修改文本的差异与内容保护检查 |
| `english.py` | 可选的固定英语量测，与参考博客英语条件参考比较 |
| `cli.py` | 四个研究命令：analyze、summarize、compile、check |

依赖方向为 `contracts/segmentation → features/surface → linguistic`；统计与风格卡生成不用解析器。无模型、语料或联网操作发生在 import 时。

## analyze

```sh
style-compiler analyze input.txt -o measurement.json
style-compiler analyze input.txt --models /existing/stanza-models -o parsed.json
```

输入为 UTF-8 原文件；保留 BOM、CRLF、空白和公式，SHA-256 绑定实际字节，偏移为 Python Unicode 码点半开区间。JSON 包含表层量及可选语言学量；无解析器时明确返回 unavailable。自然测量结果可能包含原跨度和来源信息，研究时保存在本地。

8 项字级指标沿用 `character-core/1.0.0` 与 `punctuation-lines/1.0.0`：F002 段落密度、F003 单句段占比、F013 句长中位数、F014 四分位距、F015 90 分位数、F016 归一 MAD、F024 相邻句长变化、F025 相邻句长秩相关。内容字符是 Unicode L/N 类别；每个含内容的物理行算操作段，标点形成操作句。它们不是词数、语义段落或质量指标。

71 项语言学量保留固定通道、原文身份、机会数、零/缺失区别、句级行和基本依存图；共享分母和相关分量不构成 71 个独立风格维度。依存图也不是论证图。公式集中在 `linguistic/schema.py`。

## summarize

每行声明一条文档全局测量，示例（数值仅为合成协议示范）：

```json
{"schema":"style-observation/1","id":"example-1","component_id":"work-1","source":"web","condition":"HUMAN","split":"TRAIN","profile":"explicit-instrument-identity","units":{"F013":"content_chars"},"features":{"F013":28}}
```

`id` 唯一。`component_id` 表示调用方已审查的版本、复制或衍生分量；代码检查已声明分量是否跨划分，不能自动发现漏标的近重复。所有记录必须有相同仪器 profile、特征集与单位。缺失写 `null`，不补零；每项报告缺失文档和不可用分量。

在每个 TRAIN/DEV、来源、条件、分量中先平均有效文档值，再等权汇总分量；这是文档描述子汇总，不是把不同机会的计数直接混成词元概率。只在同来源、同划分、同分量内计算 HUMAN − CHATGPT 的配对差值。标签由调用方提供，不认证作者身份。

默认 400 次固定种子的分量重抽样，返回探索性区间；不能解释成多重比较校正、因果效应或改写成功率。重复调用相同输入得到相同输出。TEST 导出拒绝进入此命令。

## compile

```sh
style-compiler compile
```

读取 `research/manifest.json` 绑定的四份汇总，核对实际文件 SHA 后生成：

- `references/statistical-style.md`
- `references/mathematician-style.md`
- 根目录 `build.json`，记录输入与输出指纹

从仓库根目录运行。`--research` 指定冻结证据目录，`--skill` 指定单个 skill 的输出目录，默认分别为 `research` 和当前目录。编译不生成或覆盖 `SKILL.md`；正文与例子人工维护。

这一步可以重建受管理的风格卡；普通 measurement/check 输出拒绝覆盖已有文件。统计到编辑建议的映射在 `profiles.py`，明确标为解释性建议，没有用观察差值声称干预效果。新研究导出先独立检查再登记，不能靠更新指纹把旧数据改名成新证据。

## check

```sh
style-compiler check original.txt final.txt --locks locks.json -o review.json
```

`locks.json` 是必须保持出现次数的字符串列表。工具比较代码、公式、块引文、URL 与锁定字符串；数量、否定/限定、数学符号和部分模板表达变化产生复核提示。它不自动改稿；相同词频也不证明施受关系或语义相同。受保护内容改变时退出 2；其他情况的退出 0 只表示检查完成，不能代替内容审查。

## 可选解析

中文：Stanza 1.10.1，zh-hans GSDSimp nocharlm，固定模型提交 `82f2856d1cf4f933738a8a84b5ad959d156040a0`。`LocalStanza` 核对已有模型及资源哈希，逐源句解析，禁用下载。权重来源和各自许可记录在 `research/general/parser-profile.json`；71 通道聚合还有明确的 Unicode 15.0.0 和跨度要求，不匹配时拒绝。

英语使用已有、与 `research/mathematician/measurement-contract.json` 完全匹配的环境和权重：

```sh
style-compiler-english input.txt --models /existing/en-models --contract research/mathematician/measurement-contract.json --profile research/mathematician/development-profiles.json --genre math_exposition --out english.json
```

公式投影和短块排除会影响分母；英语数值不移植到中文。历史记录保留原仪器哈希；迁移后的源码有新的字节身份，不能冒充原实验重跑。

旧版本的 extract/split/fit/plan/apply 已退出当前接口。旧数据和代码可从重建前 Git 提交追溯，不在当前目录保留另一套运行路径。
