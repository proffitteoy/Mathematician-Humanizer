# Mathematician Humanizer

把中文或英文的数学说明、学习札记、讲义和技术文章，改写为 **one of the mathematicians** 公开博客中的解释风格：从具体问题进入，说明关键选择的动机，展开决定性步骤，并交代结论的适用范围。

基于 [blader/humanizer 3.1.0](https://github.com/blader/humanizer/tree/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8) 改编：26 项清理规则及其编号、分组来自上游，工作流与内容保护要求也据此调整。上游版权为 Siqi Chen（2025），保留完整 [MIT 通知](references/upstream-LICENSE.txt)；本项目增补固定参考风格的六项论证习惯与示例。

## 快速使用

ChatGPT 用户可直接连接[在线 MCP](#通过-mcp-使用)。支持本地 skill 的助手可按下面的方式调用。

让助手读取 [SKILL.md](SKILL.md)，或者在安装后直接调用：

```text
$mathematician-humanizer

按参考数学博客的风格改写下面的文字。
读者熟悉线性代数，但不熟悉这个证明。
保留事实、数学条件、公式和结论。

[粘贴原稿]
```

也可以指定文件：

```text
用 mathematician-humanizer 改写 docs/article.md 的正文。
保留公式、引用与链接。
```

默认返回完整终稿。改写文件时只修改正文，再简述改动；需要修改说明或展示过程时，可以明确要求。

## 通过 MCP 使用

已在 Sites 发布[在线服务](https://mathematician-humanizer.proffitteoy.chatgpt.site/)，可直接连接以下公网 HTTPS 地址：

```text
https://mathematician-humanizer.proffitteoy.chatgpt.site/mcp
```

传输协议为 **Streamable HTTP**，认证选择 **No Auth / 无身份验证**。无需在本机启动服务器，也无需另配模型 API 密钥。

### ChatGPT

1. 在设置的 Apps / Plugins 中添加自定义远程 MCP；若账号需要，先开启 Developer mode。
2. 填入上述地址，认证选 **No Auth**，点击 **Scan Tools**。
3. 确认发现下面的三个工具，安装后在对话中启用该插件。
4. 先调用 `get_writing_guide` 检查连接，再提交原稿：

```text
使用 Mathematician Humanizer，调用 prepare_mathematical_rewrite 改写下面的文章。
读者熟悉线性代数，但不熟悉这个证明。
保留事实、数学条件、公式和结论，给出完整终稿。

[粘贴原稿]
```

### Codex

在本机终端添加远程服务，然后重新打开对话：

```powershell
codex mcp add mathematician-humanizer-online --url https://mathematician-humanizer.proffitteoy.chatgpt.site/mcp
```

### 工具与使用边界

| 工具 | 用途 |
|---|---|
| `get_writing_guide` | 读取完整 skill，包括六项论证习惯和 26 项清理规则 |
| `prepare_mathematical_rewrite` | 提交 `text`，返回完整规则和改写任务；由调用它的 GPT 生成终稿 |
| `get_reference` | 读取 style、statistics、example 或 license 参考文档 |

原稿最多 30,000 个 Unicode 码点。稿件会发送到远程 MCP 服务，应用不保存稿件；客户端和托管平台按各自策略处理请求。服务不认证数学证明或作者身份，终稿仍需内容复核。

当前托管服务固定使用 skill 0.2.1，来源提交为 [`3b8bded`](https://github.com/proffitteoy/Mathematician-Humanizer/tree/3b8bdeddb1a2d19149deab5e0ab4be2ec0fa420b)，不会自动同步仓库后续更新。连接入口因账号界面而异；浏览器直接打开 `/mcp` 的 GET 405 属于正常协议行为，实际连接以工具扫描和调用结果为准。

## 本地 skill 安装

普通改写需要一个支持 `SKILL.md` 的 AI 助手；无需安装 Python、依赖包或下载模型。下面以 Codex 为例。

### 1. 获取仓库

已安装 Git 时，运行：

```sh
git clone https://github.com/proffitteoy/style-compiler.git
cd style-compiler
```

也可以在 [GitHub 仓库页面](https://github.com/proffitteoy/style-compiler)选择 **Code → Download ZIP**，解压后在包含 `SKILL.md` 的目录打开终端。以下安装命令都从这个目录运行。

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

> 最小二乘的答案是否唯一，取决于我们把什么看作答案。先看拟合向量：正交投影保证它唯一。再问同一个拟合向量能否来自不同系数；沿着矩阵的核移动系数不会改变拟合结果，所以系数唯一还需要满列秩。

完整演示见[原稿、终稿与内容复核](examples/rewrite.md)。

## 改写原则

整篇文章保持同一参考风格。先明确对象和问题，再解释选择、展开机制、检查条件，最后回答原问题。按读者的理解困难分配篇幅，必要的例子、回顾和证明细节要保留。

在这个基础上，用 Humanizer 的 26 项规则清理空泛强调、机械排比、虚饰、装饰性版式和聊天残留。规则按表达的作用使用；真实的对比、限定和动机可以保留。

事实、量词、否定、数学条件、定义域和证明依赖优先于风格。公式、代码、逐字引文和链接目标保持。中文按中文表达习惯改写，不套用英语统计阈值。

完整工作流、六项论证习惯和逐项例子都在 [SKILL.md](SKILL.md)。

## 进一步阅读

需要运行统计、重建风格卡或检查原稿与终稿时，另备 Python 3.11+，在仓库根目录用 `python -m pip install -e .` 安装可选维护工具。安装后运行 `style-compiler --help` 查看命令；完整环境与使用说明见下方运行协议。普通改写无需这一步。

- [研究与来源说明](docs/research.md)：研究路线、规则依据、上游 26 项对应与验证范围。
- [维护工具与运行协议](docs/architecture.md)：可选统计、风格卡更新和内容检查。
- [验收条件](docs/ACCEPTANCE.zh.md)与[变更记录](CHANGELOG.md)。

上游许可适用于其沿用和改编内容；其他项目代码没有额外声明统一授权。
