# 可执行自查约定

脚本依赖Python 3标准库。每篇正文配一个JSON：

```json
{
  "mode": "exposition",
  "text_sha256": "填写正文UTF-8字节SHA-256",
  "checks": {
    "goal": {"status":"pass", "quote":"正文中的逐字短片段", "reason":"具体说明为什么目标清楚"},
    "assumptions": {"status":"pass", "quote":"逐字片段", "reason":"核对对象与量词"},
    "reasoning": {"status":"pass", "quote":"逐字片段", "reason":"实际复算关键步骤，不只评价文字"},
    "boundary": {"status":"pass", "quote":"逐字片段", "reason":"限制或反例具体说明"},
    "originality": {"status":"pass", "quote":"逐字片段", "reason":"来源对照与原创范围"}
  }
}
```

learning模式还须有`learning_test`项。允许`fail`或`unresolved`，会阻止全项通过；这不要求隐瞒或强行修好无法解决的问题。程序会检查必需项、状态、非空具体解释、引用确实出现在正文，以及正文指纹是否匹配。正文修改后旧审核必定失效。

这些检查能抓住漏填、空话式省略、引用错位、未决项冒充完成及正文与审核不同步。它不能识别填入的理由是否诚实，也不能证明数学真伪、核实全部来源或辨识作者。`mechanical_contract_pass`仅表示审核合同完整。不要改称“数学正确率”或“风格相似度”。

实际验证：`python scripts/test_audit.py`。它会在临时文件中测试合法输入、错误指纹、缺少条件、伪造引用、未决推理和学习任务缺失；不更改用户文件。
