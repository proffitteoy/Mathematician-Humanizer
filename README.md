# Mathematician Humanizer v2

当前版本：**v2（2.0.1）**。

帮助 GPT 阅读、重建和解释数学论证：以主定理为目标建立带原文证据的证明依赖，分析数学障碍与方法选择，再生成连贯讲解并实际测量表达。**数学理解是核心，讲解是输出，Humanizer 是表达辅助。**

表达部分基于 [blader/humanizer 3.1.0](https://github.com/blader/humanizer/tree/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8) 改编：26 项规则及编号、分组来自上游，保留 Siqi Chen（2025）的完整 [MIT 通知](references/upstream-LICENSE.txt)。本项目增补数学理解协议和从 **one of the mathematicians** 博客提炼的六项论证习惯。

## 快速使用

支持本地 skill 的助手可直接读取 [SKILL.md](SKILL.md)。完整计算工作流使用下方[本地工具与 MCP](#本地工具与-mcp)。[公网站点与 MCP](#通过-mcp-使用)已更新至 v2，提供数学结构、证据依赖、阶段任务和真实测量工具。

让助手读取 [SKILL.md](SKILL.md)，或者在安装后直接调用：

```text
$mathematician-humanizer

阅读这篇论文，先准确记录主要定理的条件与结论，重建证明依赖，
解释关键引理解决的障碍及数学方法为什么有效，再生成连贯讲解。
读者熟悉线性代数，不熟悉代数拓扑；只补目标定理需要的背景。
区分作者明说的动机、数学重建和未核实联系。

[附论文或可解析原文]
```

也可以指定文件：

```text
用 mathematician-humanizer 改写 docs/article.md 的正文。
保留公式、引用与链接。
```

也保留中英文短文改写：按参考博客的论证习惯组织说明，再用 Humanizer 清理空泛表达。默认返回完整终稿，内部保存证据材料；重大数学缺口明确说明。

## 本地工具与 MCP

Python 3.11+，从仓库根目录安装；核心 CLI 只用标准库，PDF 和 MCP 为可选依赖：

```sh
python -m pip install -e ".[mcp,pdf]"
style-compiler read-paper examples/argument.tex -o paper.json
style-compiler reconstruct paper.json examples/argument.annotations.json
style-compiler prepare-explanation motivation paper.json --annotations examples/argument.annotations.json
mathematician-humanizer-mcp --resources .
```

`paper.json` 等回执拒绝覆盖已有文件。示例是原创小型最小二乘论证，用于检查协议，不是三篇真实论文的效果实验。完整步骤见[可重放例子](examples/argument.md)。

Codex 可连接本地 stdio 服务，路径替换为实际仓库位置；此命令只供用户选择运行：

```sh
codex mcp add mathematician-humanizer-local -- mathematician-humanizer-mcp --resources /absolute/path/to/style-compiler
```

也可运行 `mathematician-humanizer-mcp --resources . --transport streamable-http`，端点为 `http://127.0.0.1:8765/mcp`。本地服务仅绑定回环地址，不自动部署或上传论文。

| 新工具 | 实际执行的工作 |
|---|---|
| `analyze_paper` / `upload_paper_chunk` | 保留全文，提取数学环境、编号与引用候选；分块按索引精确拼接 |
| `read_paper_source` | 按原始 Unicode 码点位置重读证据窗口 |
| `query_proof_dependencies` | 校验引文、环路、覆盖与 MAR，计算目标定理前置知识闭包 |
| `prepare_explanation_task` | 返回版本化阶段 Prompt 和实际图分析，执行写作/审核门槛 |
| `audit_mathematical_exposition` | 分别返回数学审查记录、内容保护和当前正文真实统计 |

保留 `get_writing_guide`、`get_reference`、`prepare_mathematical_rewrite` 兼容入口。新本地服务最多在进程内保留 64 份文档，每份上限 2,000,000 码点；长文可分块提交并分页读取。进程退出后材料清除，不在后台调用其他模型。PDF 用本地 CLI 提取，核对公式后提交提取文本；远程工具不任意读取服务端文件。

证明依赖由模型根据原文标注，程序不会从引用编号自动推断数学关系，也不认证数学正确性。**数学审核未记录或存在缺口时，不进入最终语言修订。** 详细 MAR、门槛和 Prompt 设计见[架构](docs/architecture.md)与[Prompt 工程](docs/prompt-engineering.md)。

## 通过 MCP 使用

[在线服务](https://mathematician-humanizer.proffitteoy.chatgpt.site/)已发布 **Mathematician Humanizer v2（2.0.0）**。优先使用 Sites 为该站点创建的同名个人插件，已有连接无需更换站点地址。公网 MCP 端点：

```text
https://mathematician-humanizer.proffitteoy.chatgpt.site/mcp
```

传输协议为 **Streamable HTTP**。Sites 负责 MCP 连接的 **OAuth 身份验证**；无需另配模型 API 密钥。站点网页公开不等于 MCP 允许匿名直连：未认证请求返回 401，并提供 OAuth 资源发现地址。旧版文档中的 No Auth 配置不再适用于当前站点。

### ChatGPT

1. 在 Plugins / Apps 的个人或 Created by you 列表中启用 **Mathematician Humanizer v2**。已连接者继续使用原插件。
2. 发布时会刷新站点工具；若当前聊天仍只显示旧版三个入口，重新打开聊天或重新扫描工具以加载新增工具。
3. 先调用 `get_writing_guide`，确认返回 skill 2.0.0，再按阶段提交论文。手动添加自定义远程 MCP 时，使用支持 OAuth 自动发现的连接方式完成登录。

```text
使用 Mathematician Humanizer v2 阅读附上的论文。
先 analyze_paper，再分阶段重建主要定理的依赖、数学障碍和方法动机，
生成连贯讲解，最后分别审核数学内容与实际统计。
读者熟悉线性代数。保留条件、公式和来源，区分数学解释与作者明说的动机。

[附论文或可解析原文]
```

### Codex

在 Codex 中直接启用该站点已有的个人插件即可，平台负责连接身份验证。

使用独立 CLI 手动配置远程 MCP 时，添加端点并完成 OAuth 登录，再重新打开对话：

```powershell
codex mcp add mathematician-humanizer-online --url https://mathematician-humanizer.proffitteoy.chatgpt.site/mcp
codex mcp login mathematician-humanizer-online
```

### 工具与使用边界

| 工具 | 用途 |
|---|---|
| `get_writing_guide` | 读取完整 v2 数学理解工作流、六项习惯和 26 项规则 |
| `prepare_mathematical_rewrite` | 保留短文改写入口，并返回原文的真实表层测量 |
| `get_reference` | 读取 style、statistics、example、understanding 或 license |
| `analyze_paper` | 实际解析数学环境、章节、编号和引用候选 |
| `read_paper_source` | 按 Unicode 码点位置重读原文证据 |
| `query_proof_dependencies` | 检查证据、DAG、阅读覆盖、MAR 和归属，计算目标闭包 |
| `prepare_explanation_task` | 准备七阶段任务并执行写作/审核门槛 |
| `audit_mathematical_exposition` | 分别执行数学审查回执、内容保护和当前稿测量 |
| `measure_exposition` | 单独测量八项中文表层特征，按需返回描述性参考 |

公网论文工具使用 `paper={"text":"原文","format":"latex","source":"来源标识"}`，也可把 text 替换为有序的 chunks 字符串数组。每次调用都携带同一原文，服务不保存论文，也不把文档 ID 当成持久存储。单篇最多 2,000,000 码点，请求另受 8 MiB 限制，超限明确拒绝。旧短文改写入口仍限 30,000 码点。

稿件会发送到远程服务；应用不落盘保存，客户端和托管平台按各自策略处理请求。PDF、固定语言学解析器及更细的词面诊断在本地使用。服务不认证数学证明、作者身份或写作质量，统计不代替数学审核。

每次托管发布都固定到一个 Git 提交，不会自动同步后续仓库变更。当前版本、九个工具及实际 `source_commit` 可查看[服务状态](https://mathematician-humanizer.proffitteoy.chatgpt.site/health)。已在线验证站点版本、现有插件的完整 v2 规则和八项实际测量；新增工具的解析、图和测量已通过 Worker/Python 对照测试。三篇真实论文的独立理解效果评价仍未完成。

## 本地 skill 安装

普通改写需要一个支持 `SKILL.md` 的 AI 助手；无需安装 Python、依赖包或下载模型。下面以 Codex 为例。

### 1. 获取仓库

已安装 Git 时，运行：

```sh
git clone https://github.com/proffitteoy/Mathematician-Humanizer.git
cd Mathematician-Humanizer
```

也可以在 [GitHub 仓库页面](https://github.com/proffitteoy/Mathematician-Humanizer)选择 **Code → Download ZIP**，解压后在包含 `SKILL.md` 的目录打开终端。以下安装命令都从这个目录运行。

### 2. 安装到 Codex

以下安装到当前用户的技能目录 `~/.agents/skills/mathematician-humanizer/`，供该用户的项目使用。

**Windows（PowerShell）：**

```powershell
$skillTarget = Join-Path $HOME ".agents/skills/mathematician-humanizer"
New-Item -ItemType Directory -Force $skillTarget, "$skillTarget/references", "$skillTarget/agents" | Out-Null
Copy-Item .\SKILL.md -Destination $skillTarget -Force
Copy-Item .\references\* -Destination "$skillTarget/references" -Recurse -Force
Copy-Item .\agents\* -Destination "$skillTarget/agents" -Recurse -Force
```

**macOS / Linux（终端）：**

```sh
skill_target="$HOME/.agents/skills/mathematician-humanizer"
mkdir -p "$skill_target"
cp SKILL.md "$skill_target/"
cp -R references agents "$skill_target/"
```

只想在单个项目中使用时，将上面的目标路径改为该项目根目录下的 `.agents/skills/mathematician-humanizer/`。

手动安装或使用其他支持 `SKILL.md` 的工具时，将以下内容复制到该工具的技能目录，保留目录结构和上游许可文件：

```text
mathematician-humanizer/
├── SKILL.md
├── references/    # 完整复制，包含风格卡和 upstream-LICENSE.txt
└── agents/        # 包含 Codex 的 openai.yaml
```

其他工具的技能目录与调用方式以其文档为准。

### 3. 确认安装并调用

确认目标目录下直接包含 `SKILL.md`，而不是多嵌套一层仓库目录。Windows 可在同一 PowerShell 窗口运行：

```powershell
Test-Path (Join-Path $skillTarget "SKILL.md")
Test-Path (Join-Path $skillTarget "references/upstream-LICENSE.txt")
Test-Path (Join-Path $skillTarget "agents/openai.yaml")
```

三项都应返回 `True`。macOS / Linux 可用 `ls "$skill_target" "$skill_target/references" "$skill_target/agents"` 查看文件。

重启 Codex，再按上面的[快速使用](#快速使用)调用 `$mathematician-humanizer`，粘贴一段原稿试用。若仍未识别，检查安装路径、文件层级，以及当前项目是否使用了所安装的技能目录；也可以直接让助手读取本仓库的 [SKILL.md](SKILL.md) 完成改写。

### 更新已安装的技能

通过 Git 获取仓库时，在仓库根目录运行 `git pull --ff-only`；通过 ZIP 获取时，重新下载并解压。然后重新执行对应系统的复制命令，再重启 Codex。

复制命令会覆盖目标目录中的同名文件。若手动修改过已安装的技能，请先备份这些修改。

## 改写示例

**改前：**

> 最小二乘不仅是寻找答案的工具，更是理解唯一性的窗口。拟合向量唯一，但系数的唯一性需要满列秩。这一点至关重要。

**改后：**

> 正交投影确定唯一的最优拟合向量。恢复系数时，沿矩阵的核移动不会改变拟合结果，因此所有最优系数组成核的一个平移。满列秩使核只含零向量，系数随之唯一。

完整演示见[原稿、终稿与内容复核](examples/rewrite.md)。

## 改写原则

正文直接展开数学关系，不预设读者问答，减少习惯性的“不是……而是……”转折。短等式优先行内，独立公式默认全文最多 3 块；presentation 返回实际计数与位置，必要推导和受保护原文的例外需记录理由。

整篇文章保持同一参考风格。先明确对象和问题，再解释选择、展开机制、检查条件，最后回答原问题。按读者的理解困难分配篇幅，必要的例子、回顾和证明细节要保留。

在这个基础上，用 Humanizer 的 26 项规则清理空泛强调、机械排比、虚饰、装饰性版式和聊天残留。规则按表达的作用使用；真实的对比、限定和动机可以保留。

事实、量词、否定、数学条件、定义域和证明依赖优先于风格。公式、代码、逐字引文和链接目标保持。中文按中文表达习惯改写，不套用英语统计阈值。

完整工作流、六项论证习惯和逐项例子都在 [SKILL.md](SKILL.md)。

## 进一步阅读

需要数学结构与审核工具或统计测量时，另备 Python 3.11+，在仓库根目录用 `python -m pip install -e .` 安装；MCP/PDF 按上方安装可选依赖。独立 skill 仍可不安装 Python，但不能因此声称执行了自动解析和测量。

- [研究与来源说明](docs/research.md)：研究路线、规则依据、上游 26 项对应与验证范围。
- [维护工具与运行协议](docs/architecture.md)：可选统计、风格卡更新和内容检查。
- [验收条件](docs/ACCEPTANCE.zh.md)与[变更记录](CHANGELOG.md)。
- [Prompt 工程与评价方案](docs/prompt-engineering.md)：分阶段合同、动机重建、失败案例和待执行消融实验。

上游许可适用于其沿用和改编内容；其他项目代码没有额外声明统一授权。
