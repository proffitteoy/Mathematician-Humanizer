# 数学理解工作协议

此协议支持论文理解任务，普通短文改写不必虚构论文结构。数学内容和解释仍由调用模型完成；程序核对源文、偏移、图结构和测量，不证明数学命题。

## 原文与证据

保留全文及其 UTF-8 SHA-256。位置统一为未经归一化的 Unicode 码点半开区间，CRLF、BOM 和公式均占据原位置。证据写为：

```json
{"document_id":"原文SHA256","start":100,"end":120,"quote":"该区间逐字原文"}
```

不要手算后猜偏移；从实际文本切片。PDF 的位置属于提取文本，另有文件指纹和页码范围；公式还需对照页面。解析器不展开宏、不读取 include、不执行 OCR。无自动节点时可手工锚定结果和条件。

长论文先建立完整材料目录，按章节和证明分块读取，登记已读与缺失范围。每阶段重新读取关键证据，不把上阶段摘要当成原文。工具窗口读取不能保证模型已完整阅读，应检查尚未读到的附录和中间证明。

## MAR：内部数学论证表示

按主定理保存准确 Statement、Hypotheses、Conclusion、Dependencies、Obstruction、Mechanism、Idea、Origin 和 Verification status。

- 陈述、条件和结论逐字锚定，包含环境之外的全局假设。
- 每条依赖说明前提建立了什么、目标在哪一步使用它、该步解决了什么障碍。
- 显式引用与数学重建分别记录。引用可能只是比较、前向引用或例子，不能自动成为证明边。
- 重要局部步骤可另设 proof 节点；外部结果锚定实际读取的来源。
- 思想从具体机制归纳；作者动机、数学上的用途解释和未核实联系分别记录。
- reviewed 表示一次实际核查记录，不表示已经获得独立数学认证。

程序 annotations 的结构为：

```text
document_id, main_theorems: [目标ID], reading_coverage: [已读原文anchor]
nodes: [{id, kind, anchor}]                    # 解析器之外的手工节点
edges: [{from, to, kind, role, basis, evidence: [anchor]}]
coverage: {节点ID: {status, evidence: [anchor], note}}
arguments: {目标ID: {
  statement: anchor, hypotheses: [anchor], conclusion: anchor,
  obstruction: {text, evidence: [anchor]},
  mechanism: {text, evidence: [anchor]}, idea: {text, evidence: [anchor]},
  status: reviewed | unresolved
}}
claims: [{kind, text, nodes: [ID], basis, evidence: [anchor]}]
external_sources: [已解析的完整外部文档]
```

from 是前提，to 是使用它的结果。basis 为 explicit_source、reconstruction；概念 claims 还可为 unverified。coverage 为 reviewed、assumed、gap。外部结果仅知道编号但未检查适用条件时应标 assumed。无父节点的结果在 note 中说明独立证明及其前提，不能用空图假装完成理解。

## 阶段交接

| 阶段 | 必须读入 | 产物与完成条件 | 失败后的处理 |
|---|---|---|---|
| structure | 全文、解析警告、读者目标 | 准确主结果、全局假设、阅读范围与缺材料 | 原文缺页/损坏则缩小范围，保留缺口 |
| proof | 主结果、定义、对应证明与外部条件 | 有数学用途和证据的 DAG；局部步骤、覆盖状态和 MAR | 环路需分解归纳/分步命题；不能删边掩盖 |
| motivation | 已核对依赖与关键构造 | 障碍→选择→机制→思想；准确归属；待核文献问题 | 不足时保留 unresolved，不凭领域标签补解释 |
| literature | 针对关键步骤的待核问题 | 实际读取的来源、条件比较、沿用与修改的区分 | 无来源则保留限制，删去未经支持的历史断言 |
| exposition | MAR、必要闭包、读者知识 | 连贯正文、断言映射；必要背景足够而不复述教材 | 有证明/归属缺口先回前阶段 |
| mathematical_audit | 正文、原文、MAR、保护基线 | 条件/依赖/机制/归属/范围五类检查与当前稿回执 | fail/unresolved 不进入最终润色 |
| editorial | 同稿数学回执、真实测量、表达规则 | 有具体阅读收益的局部修改与变更记录 | 改稿后重新数学/保护审核和测量 |

阶段 Prompt 由可选运行工具返回，模型不需要另外启动多个实例。没有工具时仍按这些条件工作，不能宣称完成了未运行的自动检查。

## 数学动机的完成标准

“使用代数拓扑把拓扑问题代数化”没有指出实际障碍。需要核对：不变量保留多少信息、是否足以分类、代数态射能否实现、空间条件或系数选择在哪一步起作用。只有论文涉及这些问题时才分析它们。

同样，`P²=P` 只给出幂等性。若要解释规范代表选择，还需核对像与核、等价关系的相容性以及后续证明如何使用这些性质。

删假设后现有证明失败，只说明这个证明的限制；证明条件必要需要反例或其他论证。局部作用重要不等于不存在其他证明。作者心理动机和历史继承关系必须有相应原文，数学重建不能替代它们。

## 双重审核与交付

数学审核应先提出独立验证问题，再回原文检查，不能把草稿作为自身证据。审核回执绑定当前候选 SHA 与 reconstruction_sha256；正文、证明图或 MAR 改变后旧回执失效。五类检查均应记录所查正文区间、理由和源文证据。

统计阶段实际测量当前稿。句长、物理行和词性只是观察量；不能从中自动推断遗漏条件、语义段落负担或数学正确性。英文不能套中文参考。没有测量环境就明确未测量，不声称统计优化。

内部保留图、证据、断言映射和变更记录，最终交付连贯数学讲解。重大缺口需告知用户；不在正文机械罗列检查问题。
