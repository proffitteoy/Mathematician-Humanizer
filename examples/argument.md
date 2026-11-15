# 可重放的论证结构示例

这是本项目编写的有限维最小二乘小型论证片段，不是研究论文或效果实验。原文见 [argument.tex](argument.tex)，带原文锚点的标注见 [argument.annotations.json](argument.annotations.json)，讲解草稿见 [argument.exposition.txt](argument.exposition.txt)。标注是示例自查，不是独立专家金标。

主结果为所有最优系数构成核的平移。内部结构区分两个用途：正交投影确定唯一最优拟合向量，核的纤维刻画全部最优系数。最后的 remark 不在主结果的必要闭包中。

```mermaid
flowchart TD
  D[有限维线性映射与像空间] --> P[最优拟合向量唯一]
  D --> K[同一原像的差属于核]
  P --> T[最优系数是核的平移]
  K --> T
```

从仓库根目录运行，先准备已忽略的输出目录。每次用不存在的回执文件名，命令不会覆盖已有回执：

```sh
python -m pip install -e .
mkdir artifacts
style-compiler read-paper examples/argument.tex -o artifacts/argument.document.json
style-compiler reconstruct artifacts/argument.document.json examples/argument.annotations.json
style-compiler prepare-explanation motivation artifacts/argument.document.json --annotations examples/argument.annotations.json --reader "熟悉线性代数，不熟悉该证明"
style-compiler prepare-explanation exposition artifacts/argument.document.json --annotations examples/argument.annotations.json --known-node n1
```

`reconstruct` 应返回 `prerequisite_order=[n1,n2,n4,n6]`、空 findings 和 `mathematical_validity=not_certified`。已知 n1 只减少背景讲解，不从图中删除它。原文和讲解的公式可能重排，保护基线使用本轮讲解草稿。

```sh
style-compiler audit-exposition artifacts/argument.document.json examples/argument.annotations.json examples/argument.exposition.txt examples/argument.exposition.txt
```

这一步会真实测量草稿并返回 `editorial_revision_allowed=false`，退出码为 2：还没有提交五类数学审查回执。不得把“草稿没变化”和“保护检查通过”当成数学审核通过。

然后调用 `prepare-explanation mathematical_audit`，提供 `--baseline` 和 `--candidate` 为上述讲解草稿。按任务检查条件、依赖、机制、归属和范围，以 `review` 格式保存真实审查；再传给 `audit-exposition --review ...`。只有审查当前稿、五项 pass、无图 findings 和受保护内容变化，才能准备 editorial 任务。这里刻意不分发一份假装已经独立审核的 pass 文件。

可尝试的负例：修改某个 evidence.quote；给图添加反向边形成环；删除正文中部 reading_coverage；把 mathematical_motivation 改成 author_motivation 而保留 reconstruction；向候选加入与基线不同的公式。它们分别触发证据拒绝、环路拒绝、未读缺口、归属 findings 和保护阻塞。

这些例子验证程序能检查工作材料，不验证模型真的理解任意论文。三篇真实论文的盲评和消融仍待执行，见 [评价方案](../docs/prompt-engineering.md)。
