# 可执行诊断与人工审核

运行（skill目录内）：

```sh
python scripts/prose_lint.py original.txt candidate.txt --locks locks.json --output candidate.lint.json
```

`locks.json`是原稿中必须字面保留的非空字符串数组，例如公式外的“若且唯若”、引述、人物名及精确金额。只锁真正不可重写的文本；一般语义义务仍放内容账本。锁不存在会报错，不假装检查成功。

脚本只读原稿与候选，并独占新建报告，绝不替换原稿/正规化字符。自动冻结Markdown代码围栏、行内代码、常见美元/LaTeX公式、引用块和URL；片段内容及顺序变更会阻塞。围栏/URL/公式解析是保守启发式，不覆盖所有格式，嵌套Markdown、复杂LaTeX及普通引号要人工审查和显式锁定。若任务本来要求改公式/URL，应把那次修改作为独立、授权的内容编辑先验证，再建立新的风格编辑基线；不得偷偷关保护器。

数量、否定/限定/不确定标记变化给出人工复核提示；等计数不能证明相同含义，近义改写也会触发。例：“甲给乙10元”改成“乙给甲10元”不一定命中数字检查，但必须被内容账本拦截。语义判断从来不是正则测试。

Unicode报告码位/位置而不删除。模板词、重复段落仅提示；不要求清零。`NO_MECHANICAL_FINDINGS`也不等于语义、数学或编辑质量通过。句段长度是表面计数，混用汉字与词，只供定位；不是固定中文解析器量值，不能同统计参考分位比较。

收据状态：
- `BLOCKED_PROTECTED_CHANGE`：需恢复/核实保护内容，退出码2
- `REVIEW_REQUIRED`：发现软提示，需逐项解释，退出码0不代表交付通过
- `NO_MECHANICAL_FINDINGS`：机械层未发现问题，仍需语义审核

在原有语义审核JSON另加`editorial_review`数组，记录关键诊断、处理/保留/回滚理由与体裁依据。原`check_revision.py`保持兼容，它不会自动验证这份新增编辑判断；人工需真实做完。

中文必须另运行原`measure_text.py`和`check_revision.py`，不能拿本脚本代替固定解析器。交付前检查：保护器无阻塞、软提示已判断、内容账本和声音审核无悬项、最终精确字节有正确量测收据。任何收据生成后再动一个字都需新收据。

自测：`python -m unittest discover -s tests -v`。覆盖保护区、数字/否定变化、Unicode、合法标点保留、无作者评分、同数值但主体交换的能力边界和原统计链回归。外部运行时集成测试需要manifest指定环境；未运行时如实记录skip。

## 集成最终门禁（交付必须运行）

旧`check_revision.py`保留原统计闭环兼容性，其`MEASURED_AND_REVIEWED`不足以宣布本次集成流程完成。使用严格门禁：

```sh
python scripts/check_editorial_revision.py original.measurement.json final.measurement.json --original-text original.txt --candidate-text final.txt --review final.semantic-review.json --locks locks.json --output final.integrated-check.json
```

它现场重新运行lint，不信任已保存的lint结论；检查原统计门禁、保护区阻塞和软提示的逐项处置。语义review增加：`editorial_context`（essay/technical/mathematical/procedural/other）、`protected_literals`（与locks精确相同，未指定则[]）、`unchanged_content_reviewed: true`、`unsupported_stance_or_experience: false`及`editorial_review`。后者每项含`warning_id`（对该warning的排序紧凑JSON取SHA256，脚本`warning_id`函数可复用）、`decision`（retain_for_meaning_or_voice或reviewed_no_semantic_change）、具体`reason`。首次门禁输出会列出各warning_id，人工核查后生成新的review和门禁收据，不能编造审核。

只有`MEASURED_AND_EDITORIALLY_REVIEWED`表示统计与编辑流程都已记录；它仍是自查，不是独立真实性/质量认证。没有软提示也必须完成体裁、原文未改处和新增态度/经历的审核。保护内容变更不可用一句“已看过”消除。
