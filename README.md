# Mathematician Humanizer v2

阅读数学论文，重建证明依赖与方法动机，生成有原文依据、推导连贯的讲解。支持中文和英文，也可用于已有数学文本的改写。当前版本：**2.0.2**。

表达规则改编自 [Humanizer 3.1.0](https://github.com/blader/humanizer/tree/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8)，保留全部 26 项主题及 [Siqi Chen（2025）的 MIT 通知](references/upstream-LICENSE.txt)；本项目增补数学理解协议和论证习惯。

[在线使用](https://mathematician-humanizer.proffitteoy.chatgpt.site/) · [快速开始](#快速开始) · [示例](#讲解示例) · [文档](#文档) · [变更记录](CHANGELOG.md)

## 快速开始

在 ChatGPT 或 Codex 中启用 **Mathematician Humanizer v2** 插件，附上论文原文或已核对的提取文本，并说明读者背景：

```text
阅读这篇论文，准确记录主要定理的条件与结论，
先检索并阅读相关原始资料，比较方法及其适用条件，
重建关键引理的依赖和作用，再面向熟悉线性代数的读者生成讲解。
直接展开推导，区分作者明说的动机与数学重建。
短等式优先行内排版，独立公式只保留主要结论和关键推导。
```

已有插件继续使用原连接。首次连接由 Sites 完成 OAuth 身份验证；使用 `get_writing_guide` 可查看完整规则。当前聊天若仍显示旧的三个入口，重新打开聊天或扫描工具。站点的实际版本与来源提交见[服务状态](https://mathematician-humanizer.proffitteoy.chatgpt.site/health)。

也可让支持本地 skill 的助手读取 [SKILL.md](SKILL.md)，安装后通过 `$mathematician-humanizer` 调用。完整安装步骤见[本地 skill 安装](docs/architecture.md#本地-skill-安装)。

## 讲解示例

对最小二乘唯一性的说明可以直接连接数学对象与证明机制：

> 正交投影确定唯一的最优拟合向量。恢复系数时，沿矩阵的核移动不会改变拟合结果，因此所有最优系数组成核的一个平移。满列秩使核只含零向量，系数随之唯一。

讲解正文直接陈述条件、用途和推导。短符号与等式优先行内排版，默认全文最多 **3 个独立公式块**；必要推导与受保护原文形成的例外应明确记录。工具提供真实计数和位置，供模型结合内容复核。

段落围绕完整论证展开，让条件、关键推导和结果连起来。用户要求调研时先实际查资料，记录独立作品与读取范围；同一文章的镜像和版本合并处理。检索由调用助手使用可用工具执行，MCP 本身只准备任务和检查工作材料。

- [同题改写](examples/rewrite.md)：完整原稿、终稿与内容保护回执。
- [论证结构示例](examples/argument.md)：原文锚点、依赖图、阶段任务及审核门槛。

这些是可检查的小型演示。真实论文的独立数学审阅与读者评价仍待完成。

## 运行方式

| 方式 | 适用任务 | 环境与数据处理 |
|---|---|---|
| 在线插件 | 论文阅读、阶段讲解、证据检查与表层测量 | Sites OAuth；每次调用携带原文，应用不保存论文 |
| 独立 skill | 使用助手阅读材料和改写文本 | 无需 Python；自动测量需另接工具 |
| 本地 Python / MCP | 本地解析、证据图、统计与审核 | Python 3.11+；PDF/MCP 为可选依赖，材料留在本地进程 |

### 本地工具

```sh
git clone https://github.com/proffitteoy/Mathematician-Humanizer.git
cd Mathematician-Humanizer
python -m pip install -e ".[mcp,pdf]"
style-compiler read-paper examples/argument.tex -o paper.json
style-compiler reconstruct paper.json examples/argument.annotations.json
```

最后一条命令返回主定理的前置节点顺序和实际检查结果。回执文件拒绝覆盖，重复运行时选择新路径。完整工作流与预期输出见[可重放例子](examples/argument.md)。

本地 MCP 默认使用 stdio：

```sh
mathematician-humanizer-mcp --resources .
```

### 公网 MCP

```text
https://mathematician-humanizer.proffitteoy.chatgpt.site/mcp
```

服务使用 Streamable HTTP，Sites 负责 OAuth 验证，无需另配模型 API 密钥。网页公开访问与 MCP 的连接认证分别处理；匿名 MCP 请求会返回 OAuth 发现信息。

工具覆盖原文解析与重读、证明依赖检查、七阶段任务、数学审查回执、表层测量及兼容改写入口。精确参数、九个工具的区别和本地接口见[运行协议](docs/architecture.md#工具与输入)。

公网论文输入使用 `paper={"text":"原文","format":"latex","source":"来源标识"}`，也可提供有序 `chunks` 数组。单篇上限 2,000,000 个 Unicode 码点，请求另受 8 MiB 限制。PDF 应先本地提取并核对公式；客户端和托管平台按各自策略处理请求。

## 验证范围

解析器保留原文和位置；模型标注数学依赖，程序核对引文、环路、阅读覆盖与审核回执。数学解释和终稿由调用模型完成，证明正确性仍需内容审阅。

统计反馈报告当前稿的实际观察量。独立公式数量与句型提示属于表达检查，不用来推断作者身份或给文章打分。固定语言学解析器仅在本地使用；三篇真实论文的盲评与消融方案见[评价计划](docs/prompt-engineering.md#工程与行为评价)。

## 文档

| 文档 | 内容 |
|---|---|
| [SKILL.md](SKILL.md) | 助手的完整工作流、表达规则与示例 |
| [数学理解协议](references/mathematical-understanding.md) | MAR、原文锚点与阶段交接 |
| [安装与运行协议](docs/architecture.md) | 安装、工具参数、输入限制与维护命令 |
| [Prompt 工程](docs/prompt-engineering.md) | 阶段合同、动机重建与评价方法 |
| [数学理解的研究依据](docs/proof-understanding-research.md) | 独立原始资料、方法比较、限制及 Cauchy 定理案例 |
| [研究与来源](docs/research.md) | 冻结统计、规则依据及证据范围 |
| [验收条件](docs/ACCEPTANCE.zh.md) | 数学内容、表达与工程检查标准 |

## 开发与反馈

报告问题时请附最小原文、读者背景、实际输出和需要修正的位置。涉及数学错误时，附上条件、证明步骤或原文证据。

```sh
python -m unittest discover -s tests -v
```

维护者还需核对生成卡、文档链接和示例回执；托管构建与跨运行时对照命令见[运行协议](docs/architecture.md#维护与发布)。

## 来源与许可

Humanizer 的 26 项主题、编号与分组及部分通用工作流来自固定上游版本。数学理解协议、测量实现和示例由本项目增补，参考数学博客统一以 **one of the mathematicians** 代指。

完整上游版权与许可随技能和站点分发。该许可适用于沿用和改编内容；仓库其他代码尚未声明统一授权。
