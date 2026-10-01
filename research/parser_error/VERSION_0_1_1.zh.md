# 解析评测器 v0.1.1：缺失原文的记账修复

2026-10-01。仅修复评测器健壮性和选择清单版本兼容，不改变生产中文解析器、参考规范、71项公式、固定PUD64样本或其原始汇总。

## 变更

- 入选记录缺少`# text`时，在分段或两臂推理前保留记录和整数token行数，标记源文本不可用、边界不可评估、参考失败、两臂未尝试及排除行数；不重建原文、不补样
- `# text`存在但为空，与字段缺失分开；空文本进入原有边界/参考不适用处理
- 新选择清单schema为`pud-selection/1.1.0`，允许缺原文摘要为null并显式区分missing/empty/present
- `--verify-existing`按既有清单版本检查；无schema字段的旧清单保持逐字兼容，未知版本拒绝；新增文件仍exclusive-create，不覆盖私有原清单
- 固定真实SOURCE_SHA校验未放松；测试只在原创合成夹具内mock该常量

## 证据与版本

旧[源收据](source-receipt.public.json)、[执行收据](verification-receipt.public.json)、[复审](INDEPENDENT_REVIEW_ZH.md)与[原始汇总](pud64.aggregate.json)属于[v0.1.0提交](https://github.com/proffitteoy/style-compiler/tree/6e3004aac5bc9dce967c4d50ac3648adad606c7b/research/parser_error)。不要拿其中源码摘要验证v0.1.1。

新代码以[独立v0.1.1复审](V011_INDEPENDENT_REVIEW_ZH.md)和[v0.1.1收据](v011-review-receipt.public.json)绑定。19项parser测试、含Unicode原始来源的80项相关测试通过。固定64条的原始两臂推理结果缓存重放后，所有评分、混淆、71通道及私有分析完全一致，仅coverage新增4个零字段；这不是重新生成自然文本或增加样本量，也不是再次完整模型推理的声称。v0.1.0此前已经独立完整离线重推理复现。

额外独立反例验证全部64条都缺text时仍返回完整失败账本，并且分段、解析和控制均未启动。原始数值文件继续冻结，不为了把新零字段加入旧文件而重写其摘要。

仍需区分容器前提与记录级参考失败：损坏UTF-8、非法容器结构、缺少选样所需sent_id等不在本补丁承诺范围内。该修复不提高解析准确率、不补足六个无支持通道、不消除规范/字形/体裁混杂，也不开放个人阶段或经验拟合资格。
