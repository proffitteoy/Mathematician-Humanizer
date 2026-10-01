# PUD评测器v0.1.1：缺text分支与兼容性独立复审

2026-10-01。**结论：本次窄范围修补通过。缺少text的入选记录现可在分段／解析前进入失败账本；旧64条选择和既有科学汇总未改变。最终版本说明也已复核通过，明确旧收据不覆盖新源码。**

本复审未改被审文件。没有新语料／模型下载，没有经验拟合或远端写入，没有输出自然文本、逐记录标识、偏移或解析。复审参照原 `PATCH_RECOMMENDATION_ZH.md`，但结果以实际新实现为准。

## 1. 被审版本与旧证据边界

| 文件 | v0.1.1 SHA-256 |
|---|---|
| evaluate.py | 9bb5645316f7228c399e062c9da5197a7ed0590e53b8c87264e7545cf7bb9ecc |
| freeze_selection.py | 2497225d40dfc4feacbea62195ea94b8c8a94958cb04ab4b6b3cdb6344a039b0 |
| test_missing_text.py | e6b2fd7ea4788035019de42151a72c0b1750c47c11bade7749fd1e3b94a7ba5f |

已检查保存的原版evaluate.py、freeze_selection.py及test_evaluate.py，摘要分别与原收据的 `add6c269…`、`e45b1185…`、`873559f2…` 完全一致。旧预注册、pud64.aggregate.json、source-receipt.public.json、verification-receipt.public.json没有改动。旧测试文件与独立汇总核验器也未改变。

完整新旧文件摘要见 `checks.public.json`。**旧verification-receipt.public.json只证明它列出的旧源码，不证明v0.1.1源码。** 本报告及新收据单独记录这次变更。科学结果不变不等于文件身份不变。

## 2. 补丁是否修到准确位置

evaluate.py先计入入选记录、stratum和整数token行数，然后用 `meta.get('text')` 检查。缺text时：

- 标记source_text_unavailable与boundary_not_evaluable
- 计入reference_failed及missing_text原因
- 记录production/control未尝试，未伪装为实际解析失败
- 将该记录全部整数行计入excluded_reference_integer_rows
- 保存boundary_exact=None及失败状态，并continue

该分支在任何segment、SourceObservation构造、生产或控制解析之前，符合建议。它没有用token FORM拼回缺失文本，没有删去或替换所选记录，也没有把“无法判断边界”计成“边界不一致”。

显式空字符串仍被视为“存在但为空”，不误标缺字段：正常边界／参考路径会表明它不可比较。freeze对empty保存空字符串摘要并标empty，对missing保存None并标missing，二者清楚区分。

## 3. 冻结清单的向后兼容

新版 `freeze_bytes(..., version='1.1.0')` 默认产生 `pud-selection/1.1.0`，增加source_text_status；原sent_id、原始位置、字节数、原文摘要、stratum及预注册摘要信息保留。该清单仍是私有材料，不随本报告发布。

`--verify-existing`读取清单schema：无schema时按legacy生成进行逐字比较；已知1.1.0时按新版生成；未知schema显式拒绝。测试确认：

1. 当前旧64条清单重新生成后**原始字节完全一致**
2. 新版64条清单只增加版本／状态字段，去掉这些字段后与旧清单内容完全相同
3. CLI新建、验证新版、验证legacy均成功
4. 新建已有清单仍抛FileExistsError，内容未覆盖
5. 未知schema被拒绝，固定语料SHA校验没有放松

这证明同样样本和旧选择身份可继续核验；不是修改旧清单或重新选样。新版清单因显式多出字段，其整体摘要自然不同，若使用新清单生成新结果，必须记录它自己的摘要。

## 4. 测试与固定64条重放

- parser测试19项通过：原14项加新5项
- parser及冻结语言模块／独立公式检查共80项全部通过，使用现有固定Unicode源，0项跳过；19项包含在80项中，不能相加宣称99个测试
- 额外原创合成压力测试：64条全部缺text，segment、生产parse、control均设置为一旦调用就报错；最终仍返回64条失败记录，64个整数行全保留，所有通道配对数为0
- 五项冻结CLI行为检查通过，实际在临时隔离目录执行；临时原料与清单自动清理，没有放进公开复审目录

固定PUD64的重放采用**之前保存的两臂解析缓存**，重新执行新版参考重建、gate、计分、混淆和全部71通道汇总。这次没有重新运行神经解析器；原版完整同权重推理已经在先前独立审查中复现，新补丁没有改变模型或推理实现。

结果：

- 64条生产、64条控制均按缓存重放
- 保存的三臂分析逐项不变
- 所有既有coverage字段不变
- 评分分层、标签混淆、支持库存、失败字典和两臂全部通道汇总精确相同
- 唯一新增公开字段为以下四个coverage计数，本64条均为0：source_text_unavailable_records、boundary_not_evaluable_records、production_not_attempted_missing_text_records、control_not_attempted_missing_text_records

原pud64.aggregate.json保持原字节，不用新零字段覆盖历史结果。机器重放结果见 `checks.public.json`，复查脚本见 `check_v011.py`。

## 5. 发布文档分版复核

初审时PUBLICATION_STATUS尚未分版，与活动源码已改动的状态不符。提交方随后新增VERSION_0_1_1并修订PUBLICATION_STATUS，本复审已完整阅读最终文字。两份文件明确：

1. v0.1.0历史源码与旧收据由固定提交链接定位；原科学结果／预注册不改
2. 当前活动源码为v0.1.1，绑定本新复审与收据，不能拿旧源码摘要验证新代码
3. 历史缺text缺陷继续披露，并明确它现已修复；没有改写成原执行时已实现
4. 19／80测试、全部缺text合成反例、缓存回放不同于再次完整推理、4个新coverage零值与容器限制均和完成检查一致

最终文字摘要：VERSION_0_1_1.zh.md为 `d24787bcccf7c5bceb48d1100f50ff082f5107de66d4ccf055a207686b10955d`；PUBLICATION_STATUS.zh.md为 `683309759fc45aca4829fd376ff1e766a4c71e0a2380ead1de6f67df994e9da1`。本次核验本地原版备份摘要及发布文字，未另访问远端固定提交。发布打包时须随附已链接的V011_INDEPENDENT_REVIEW_ZH.md及v011-review-receipt.public.json。

旧复审脚本应在相应历史快照上运行；遇到新源码摘要不符应选择正确版本，不能跳过核验。未发现需要再次改动本窄补丁代码或上述版本文字的发布阻断。

## 6. 仍保留的范围限制

本修补只处理可选中记录的text缺失／空值区别。缺sent_id、非法UTF-8、损坏列数等容器前提仍可导致整批拒绝，不宣称所有畸形输入都能记录后继续。

全失败合成批次中，未触发的其他零计数字段仍可能缺省；调用方若需要固定完整JSON schema，未来应另行统一零字段并测试。当前补丁新增四项零字段已显式存在，固定64条全部科学结果不受影响。

没有新增经验样本，没有修复标注约定／字形／领域混杂，没有改变自定义跨度分数为官方LAS，也没有验证65个通道或打开自然数据拟合／个人化入口。原PUD解释限制继续有效。

建议发布身份：**v0.1.1健壮性与清单兼容补丁，通过独立实现／缓存回放核对；v0.1.0固定科学结果保持原样。**
