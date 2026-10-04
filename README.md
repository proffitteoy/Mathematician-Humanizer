# Mathematician Humanizer

把中文或英文的数学说明、学习札记、讲义和技术文章，改写为 **one of the mathematicians** 公开博客中的解释风格：从具体问题进入，说明关键选择的动机，展开决定性步骤，并交代结论的适用范围。

基于 [blader/humanizer 3.1.0](https://github.com/blader/humanizer/tree/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8) 改编：26 项清理规则及其编号、分组来自上游，工作流与内容保护要求也据此调整。上游版权为 Siqi Chen（2025），保留完整 [MIT 通知](references/upstream-LICENSE.txt)；本项目增补固定参考风格的六项论证习惯与示例。

## 快速使用

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

## 安装

下载或克隆本仓库，将 `SKILL.md`、`references/` 和 `agents/` 复制到目标工具的 `mathematician-humanizer` 技能目录。普通改写直接使用这些文件，无需安装 Python 或下载模型。

Codex 用户可在仓库根目录运行：

```powershell
$skillTarget = Join-Path $HOME ".agents/skills/mathematician-humanizer"
New-Item -ItemType Directory -Force $skillTarget | Out-Null
Copy-Item .\SKILL.md -Destination $skillTarget
Copy-Item .\references -Destination $skillTarget -Recurse -Force
Copy-Item .\agents -Destination $skillTarget -Recurse -Force
```

重启或刷新技能后调用 `$mathematician-humanizer`。其他支持 `SKILL.md` 的工具使用各自的技能目录。

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

- [研究与来源说明](docs/research.md)：研究路线、规则依据、上游 26 项对应与验证范围。
- [维护工具与运行协议](docs/architecture.md)：可选统计、风格卡更新和内容检查。
- [验收条件](docs/ACCEPTANCE.zh.md)与[变更记录](CHANGELOG.md)。

上游许可适用于其沿用和改编内容；其他项目代码没有额外声明统一授权。
