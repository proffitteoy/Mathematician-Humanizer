# 结构与运行协议

## 技能交付与可选维护工具

根目录 `SKILL.md` 是唯一技能正文，包含数学理解工作流、六项论证习惯与 Humanizer 26 项表达规则。`references/mathematical-understanding.md` 给出 MAR 与阶段合同；两张生成卡保留描述性研究依据。独立 skill 可不安装运行时；完整工具闭环需要 Python 和实际调用。

最小安装内容为 `SKILL.md`、`references/` 与 `agents/openai.yaml`。不需要复制 `src/`、`research/` 或安装 Python。根目录单一入口、技能元数据与具体前后例子的写法参考 Humanizer；本项目不承诺未经验证的平台插件兼容性。

### 托管 MCP

[README 的 MCP 连接入口](../README.md#通过-mcp-使用)提供显式选择的远程用法。Sites 站点已同步 v2（2.0.0）Worker；本地 skill 安装仍不涉及远程调用。

托管服务保留固定 Git 来源和全部许可，提供九个工具。当前 source_commit 由 `/health` 实际返回，仓库变更不会自动部署。Sites 为 `/mcp` 做 OAuth 身份验证，现有个人插件复用原连接；匿名直连返回带资源发现地址的 401。早期 0.2.1 的 No Auth 说明已由实际连接结果取代，不改变站点公开访问范围。

MCP 适配层的构建与协议测试、ChatGPT 的工具扫描与实际调用分别验证；统计工具的测试不代表远程 MCP 已连接。更新 skill 时须另行更新和部署托管服务，并同步 README 的来源提交；不得将固定版本描述为实时同步。

### 2.0.0 本地 MCP

安装 `.[mcp]` 后运行 `mathematician-humanizer-mcp --resources .`，默认 stdio；`--transport streamable-http` 仅监听 `127.0.0.1:8765/mcp`。资源根固定由启动者指定，参考工具仅允许四个命名资源，不暴露任意文件读取。PDF 提取另装 `.[pdf]`，用 CLI 在本地执行，不通过 MCP 读取任意服务端路径。

`analyze_paper` 接收原文并在进程内建立索引；`upload_paper_chunk` 支持 0 起始索引、乱序传输和一致重试，拼接不加换行。最多 16 个未完成上传、64 份文档、每份 2,000,000 码点；超限明确拒绝，不静默截断。重启清空内存，没有自动远端上传或落盘。HTTP 部署到公网仍需单独设计认证、隔离和资源限制，本实现不自动做该部署。

`read_paper_source` 返回最多 20,000 码点的原文窗口、准确起止与后续游标；`query_proof_dependencies` 实际检查注释与源文，返回闭包、拓扑序、缺口和归属问题。外部来源先用同样工具提交，注释可用 `external_document_ids` 引用本进程已登记文档；CLI 则使用 `external_sources` 内嵌文档。

`prepare_explanation_task` 载入版本化 Prompt 并执行对应门槛；`audit_mathematical_exposition` 执行图、内容保护与实际统计。原来的三个入口仍保留，兼容改写入口现在返回真实表层量，但不会由短文改写自动产生论文图。

### v2 托管 Worker 适配

`site/worker.mjs` 实现 Cloudflare Worker 的无状态版本，`site/build.py` 从当前 Git 提交导出完整 skill、阶段 Prompt、许可、冻结参考及 Unicode 15.0 测量表，不调用其他模型或下载资料。分发文档通过 `git show <commit>:<path>` 读取固定提交的 blob，避免 Windows 工作区换行转换冒充原始提交字节。构建需要 Python 3.12（Unicode 15.0.0）和 Node；运行时不需要 Python。`python site/build.py` 与 `node --test site/test.mjs` 核对解析、图、规范哈希及八项量测与 Python 合成基准的一致性，不代表任意论文的数学语义验证。

公网工具每次接收 `paper={text,format,source}` 或 `paper={chunks,format,source}`，不会用不可靠的 Worker 内存假装持久保存论文。chunks 按给定数组顺序精确拼接，不额外插入字符。单篇上限 2,000,000 码点，请求另受 8 MiB 限制；数学节点最多 50,000，测量最多 20,000 个操作段和 50,000 个操作句，超限明确拒绝，不静默截断。原文读取也是无状态的，需要再次携带 paper。

托管服务提供九个工具：保留三个旧入口，增加 analyze_paper、read_paper_source、query_proof_dependencies、prepare_explanation_task、audit_mathematical_exposition 和 measure_exposition。本地版用 upload_paper_chunk 管理进程内上传，公网版用有序 chunks 和单独测量工具；两种接口不能混用。PDF 和固定语言学解析器仅在本地使用，公网只处理已核对的提取文本与八项字级量测。

托管保护器检查公式、代码、引文和 URL 的准确序列，并将正文变化统一标为待复核；本地 check 还提供更细的词面和 Unicode 诊断。两者都不证明语义保留。发布前将导出结果写入既有 Sites 检出，使用官方 source workflow 推送、保存和部署；Windows 检出用 `/upstream/** -text` 保留上游文件原始字节，防止 Git 换行转换破坏固定来源指纹。不能把 GitHub 合并或本地构建写成线上发布成功。

### 维护环境与检查

以下命令供维护者更新统计卡和检查仓库使用。Python 3.11+，默认只用标准库；从仓库根目录运行：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m style_compiler --help
python -m style_compiler compile
python -m style_compiler analyze examples/rewrite.final.txt
python -m style_compiler check examples/rewrite.original.txt examples/rewrite.final.txt
```

也可在已有 Python 环境运行 `python -m pip install -e .`，使用 `style-compiler` 命令。写作由调用 skill 的语言模型完成；这些工具用于测量、参考卡更新和内容检查，不生成文章。研究路线、冻结结果与验证边界见[研究说明](research.md)。

## 表达与版式反馈

当前稿的 presentation 与八项统计分开报告：独立公式默认最多 3 块，并给出实际计数、位置、相邻堆叠及需复核句型。正文采用直接陈述；真实问题、实质数学对比和受保护公式需结合上下文处理。数学审核通过只允许进入编辑阶段，表达检查仍需独立完成。

## 代码职责

| 文件 | 职责 |
|---|---|
| `math_reader/document.py` | 原文身份、数学环境/标题、编号引用候选、可选 PDF 页码 |
| `math_reader/graph.py` | 精确证据、DAG、必要闭包、阅读覆盖、MAR 与归属检查 |
| `math_exposition/prompts.py` | 总控与七个可独立调用的阶段 Prompt，显式版本 |
| `math_exposition/workflow.py` | 任务门槛、数学审查回执、真实统计反馈与保护审核 |
| `math_exposition/mcp.py` | 本地 MCP 传输、内存原文与分块接口 |
| `segmentation.py`、`features.py` | 原始码点跨度、8 项字级/句段测量与缺失原因 |
| `contracts.py`、`surface.py` | 不变文本、来源身份和保留缺口的投影；内部研究合同 |
| `linguistic/` | 71 项 POS/依存/词汇观测；可选固定本地 Stanza 适配器 |
| `statistics.py` | 文档先在分量内合并，再对分量等权；来源内配对与探索性区间 |
| `profiles.py` | 核对冻结输入，编译参考博客风格卡与中文统计补充 |
| `editorial.py` | 不修改文本的差异与内容保护检查 |
| `english.py` | 可选的固定英语量测，与参考博客英语条件参考比较 |
| `style_compiler/cli.py` | 保留四个统计命令，增加 read-paper、reconstruct、prepare-explanation、audit-exposition |

依赖方向为 `contracts/segmentation → features/surface → linguistic`；统计与风格卡生成不用解析器。无模型、语料或联网操作发生在 import 时。

理解层的依赖方向为 `document → graph → workflow → mcp/cli`。workflow 复用现有 features/editorial，统计模块不反向依赖数学理解。无需为每个 Prompt 新建模型类型、调度器或数据库。

## 数学理解 CLI 与回执

```sh
style-compiler read-paper examples/argument.tex -o paper.json
style-compiler reconstruct paper.json examples/argument.annotations.json
style-compiler prepare-explanation motivation paper.json --annotations examples/argument.annotations.json
style-compiler audit-exposition paper.json examples/argument.annotations.json examples/argument.exposition.txt examples/argument.exposition.txt
```

最后一项没有数学 review 回执，按约定返回 JSON 并退出 2，表示还不能润色。`reconstruct` 发现未读区间、MAR 缺失、proof gap、assumed 外部条件或归属未核实时，也返回 findings 并退出 2；引文错误和图环路作为无效输入直接拒绝。退出 0 只表示当前机械检查无阻塞，不是证明有效。

schema 为 `math-document/1`、`proof-reconstruction/1`、`mathematical-task/1`、`exposition-audit/1`。详细字段在随 skill 分发的[数学理解协议](../references/mathematical-understanding.md)。所有文件输出拒绝覆盖，原文和注释由使用者显式保存。

### 门槛与审查边界

structure/proof 可以在未完成的材料上准备任务；motivation/literature 可以收到缺口用于修复。exposition/editorial 要求目标闭包有 MAR 和 coverage，全文已读覆盖无空洞，图与归属 findings 清空。coverage 是模型或审阅者的声明，工具只检查这些声明的源文绑定，不证明人或模型真正阅读理解了内容。

数学审核独立记录 hypotheses、dependencies、mechanisms、attribution、scope 五类实际检查，包含候选片段、理由和原文证据。候选 SHA、源文 ID 与 reconstruction_sha256 必须匹配；证明图/MAR 改变也使旧审核失效。只要存在 fail/unresolved、图 findings 或受保护内容改变，就不允许进入语言修订。回执可以由模型提交，不能称为独立专家审查。

统计审核对当前候选实际运行八项字级量并返回句级位置。显式选择 `--reference-source baike/web` 时核验冻结结果指纹，只比较研究支持的特征；短稿未满足比较支持门时不产生区间判断。该来源不是论文讲解体裁的已验证目标。默认不选参考，不将所有体裁挤进一个数值分布。英文无固定本地仪器时返回 unavailable，沿用下文单独的英语命令。

baseline 指本轮开始时已核对的讲解草稿；整篇论文与解释稿的公式序列本来可能不同，不应直接用论文全文当保护基线。授权的公式更正需要明确核查并建立新基线。程序没有自动证明语义保留。

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

读取 `research/manifest.json` 绑定的最终结果与两份测量合同，核对实际文件 SHA。`research/results.json` 提供中文表层、词汇、博客体裁和留出结果；该文件保留当前规则使用的字段，历史完整导出通过清单追溯。生成：

- `references/statistical-style.md`
- `references/mathematician-style.md`

构建回执默认输出到 stdout，不在源码目录新增文件。需要保存时使用 `style-compiler compile -o artifacts/style-cards-build.json`；指定的回执文件必须尚不存在。

从仓库根目录运行。`--research` 指定冻结证据目录，`--skill` 指定单个 skill 的输出目录，默认分别为 `research` 和当前目录。编译不生成或覆盖 `SKILL.md`；正文与例子人工维护。

这一步可以重建受管理的风格卡；普通 measurement/check 输出拒绝覆盖已有文件。统计到编辑建议的映射在 `profiles.py`，明确标为解释性建议，没有用观察差值声称干预效果。新研究导出先独立检查再登记，不能靠更新指纹把旧数据改名成新证据。

## check

```sh
style-compiler check original.txt final.txt --locks locks.json -o review.json
```

`locks.json` 是必须保持出现次数的字符串列表。工具比较代码、公式、块引文、URL 与锁定字符串；数量、否定/限定、数学符号和部分模板表达变化产生复核提示。它不自动改稿；相同词频也不证明施受关系或语义相同。受保护内容改变时退出 2；其他情况的退出 0 只表示检查完成，不能代替内容审查。

## 可选解析

中文：Stanza 1.10.1，zh-hans GSDSimp nocharlm，固定模型提交 `82f2856d1cf4f933738a8a84b5ad959d156040a0`。`LocalStanza` 核对已有模型及资源哈希，逐源句解析，禁用下载。权重来源和各自许可记录在 `research/chinese-parser.json`；71 通道聚合还有明确的 Unicode 15.0.0 和跨度要求，不匹配时拒绝。

英语使用已有、与 `research/english-contract.json` 完全匹配的环境和权重：

```sh
style-compiler-english input.txt --models /existing/en-models --contract research/english-contract.json --profile research/results.json --genre math_exposition --out english.json
```

当前结果包含四类体裁的参考，按体裁的 q10/q90 检查边际差异。历史长度、时期和主题分层已退出当前目录；传入历史 profile 时仍可使用其已有长度分层。公式投影和短块排除会影响分母；英语数值不移植到中文。合同的 `contract_sha256` 保留匿名化前的历史仪器身份，当前合同字节由清单绑定；迁移后的源码有新的字节身份，不能冒充原实验重跑。

旧版本的 extract/split/fit/plan/apply 已退出当前接口。旧数据和代码可从重建前 Git 提交追溯，不在当前目录保留另一套运行路径。
