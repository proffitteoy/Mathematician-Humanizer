# Mathematician Humanizer

一个从 **one of the mathematicians** 的公开博客中提炼论证习惯的改写 skill。围绕具体问题展开，解释关键步骤的动机，让读者能跟随推演；用 [Humanizer](https://github.com/blader/humanizer) 的编辑规则清理模板化表达，保留事实、数学条件与结论。

**改前：**

> 最小二乘不仅是寻找答案的工具，更是理解唯一性的窗口。拟合向量唯一，但系数的唯一性需要满列秩。这一点至关重要。

**改后：**

> 最小二乘的答案是否唯一，取决于我们把什么看作答案。先看拟合向量：正交投影保证它唯一。再问同一个拟合向量能否来自不同系数；沿着矩阵的核移动系数不会改变拟合结果，所以系数唯一还需要满列秩。

这是原创演示。完整[原稿、终稿与内容复核](examples/rewrite.md)展开了投影与核各自承担的作用；这个例子没有接受独立的模仿效果评价。

## 使用

让助手读取根目录 [SKILL.md](SKILL.md)，然后给出原稿；已经安装的环境可直接调用：

```text
$mathematician-humanizer

按参考数学博客的风格改写下面的文字。保留事实、数学条件和结论。
[粘贴原稿]
```

改写文件：

```text
用 mathematician-humanizer 改写 docs/article.md 的正文。
读者熟悉线性代数，但不熟悉这个证明。保留公式、引用与链接。
```

默认返回完整终稿。指定文件时只修改正文，再简述改动；需要修改说明或审计时可以明确要求。普通改写无需安装 Python、运行统计程序或下载模型。

## 本地安装

技能包只有根目录的 `SKILL.md`、`references/` 和 `agents/`。把它们复制到目标工具的 `mathematician-humanizer` 技能目录即可。Codex 用户可在本仓库根目录运行以下 PowerShell 命令，安装到用户级目录：

```powershell
$skillTarget = Join-Path $HOME ".agents/skills/mathematician-humanizer"
New-Item -ItemType Directory -Force $skillTarget | Out-Null
Copy-Item .\SKILL.md -Destination $skillTarget
Copy-Item .\references -Destination $skillTarget -Recurse -Force
Copy-Item .\agents -Destination $skillTarget -Recurse -Force
```

其他支持 `SKILL.md` 的工具使用各自的技能目录。重启或刷新技能后调用 `$mathematician-humanizer`；具体发现方式以工具为准。这里提供本地文件安装，未配置插件市场。

## 改写怎样推进

正文给出完整工作流：读原稿和保护内容 → 按问题重组 → 清理表达 → 复核条件与推导 → 交付终稿。

六项论证习惯贯穿全文：

1. 从对象和具体问题进入。
2. 让关键选择有动机。
3. 有用时逐步加强结论。
4. 把篇幅给决定性机制。
5. 把条件和结论一起说清楚。
6. 回到问题，说明实际所得。

Humanizer 的 26 项规则覆盖强调、节奏、虚饰、版式、写作残留和读者背景。每项都有原创前后例子。必要的对比、限定、教学回顾和证明细节要保留，不靠禁词、固定段落或长短句交替制造风格。

本 skill 使用同一份匿名化参考风格。数学说明、讲义、札记和技术文章共享这套底色，按读者困难决定展开程度。中文迁移参考博客的论证和表达习惯；没有参考作者亲笔中文语料，不把英语统计阈值搬到中文。

## 仓库结构

参考 Humanizer 的根目录单一技能入口，维护说明与技能正文分开；研究工具支持这个 skill。

| 位置 | 用途 |
|---|---|
| [SKILL.md](SKILL.md) | 唯一技能正文，包含工作流、六项论证习惯、26 项规则与交付要求 |
| `references/` | 已生成的博客风格卡、中文统计补充和上游 MIT 通知 |
| `agents/openai.yaml` | 技能显示名称和默认调用提示 |
| [CHANGELOG.md](CHANGELOG.md) | 行为与结构变更记录 |
| `src/style_compiler/` | 测量、分组汇总、风格卡生成和改稿检查 |
| `research/`、`build.json` | 冻结研究证据、来源绑定与风格卡构建指纹 |
| `examples/`、`tests/` | 原创改写、历史失败证据和可执行检查 |
| `docs/`、`AGENT.md` | 研究协议、适用范围、验收条件和维护约定 |

## 更新统计卡与运行检查

研究主线为 **文本统计 → 风格总结 → Mathematician Humanizer → 实际改稿与内容复核**。Python 3.11+，默认只用标准库；从仓库根目录运行：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m style_compiler --help
python -m style_compiler compile
python -m style_compiler analyze examples/mathematician/chinese-least-squares.txt
python -m style_compiler check examples/rewrite.original.txt examples/rewrite.final.txt
```

也可在已有 Python 环境运行 `python -m pip install -e .`，使用 `style-compiler` 命令。`compile` 核对冻结输入指纹，只更新两张统计卡和 `build.json`，不改写 `SKILL.md`。

`summarize observations.jsonl -o summary.json` 汇总实际测量的 TRAIN/DEV 导出，保留来源分组、分量等权、配对差值和缺失。输入协议、`--skill` 输出目录、可选本地解析与命令范围见[架构与协议](docs/architecture.md)。这些工具不会生成文章，词面检查也不能认证数学证明。

## 证据与范围

中文 TRAIN/DEV 汇总支持检查句长变化和衔接；段落密度随来源改变方向，不能写成统一处方。参考博客的历史快照登记 1,234 个记录，测量 1,114 份，开发侧 1,040 份，另有 74 份年份/文章级留出。

本次沿用冻结汇总，没有重新解析语料。涉及作者的名称、目录和来源定位统一匿名化；[来源清单](research/manifest.json)分别保留原始指纹、当前文件指纹和转换字段，统计数值与测量参数保持原样。统计观察与博客阅读总结的论证习惯分开记录；真人偏好、风格保持程度和跨主题效果仍需实际改稿评价。见[研究证据](docs/research.md)与[验收条件](docs/ACCEPTANCE.zh.md)。

Humanizer 参考版本为 [3.1.0 的固定提交](https://github.com/blader/humanizer/tree/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8)。保留其 [MIT 通知](references/upstream-LICENSE.txt)，Unicode 数据保留原通知，其他项目代码没有额外声明统一授权。不分发参考博客全文、原始语料和模型权重。

旧模型、拓扑、动力学、历史探索脚本和其他写作 skills 可从重建前提交 `62b31458185e20d4ba88a667adbc6b7c0f14b14f` 追溯。
