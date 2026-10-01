# 一次性 controlled TEST 评估器独立审计

## 结论

**通过最终修订版的代码与协议审查；未授权、未执行 empirical TEST。**

2026-10-01 UTC，最终冻结包通过 80 项合成测试：作者 49 项，独立审查新增 31 项。整个测试进程实际设置了 CPU affinity `[0,1]`、512 MiB 地址空间、60 CPU 秒及 60 秒墙钟限制，并另有外层 60 秒超时；80 项运行约 0.531 秒，0 failure、0 error。

本结论仅适用于下列精确字节哈希。任何后续代码或协议修改都使本次批准失效；TEST 仍须 root 另行签发、冻结并绑定正式 GO、六文件交接及新鲜独占存储回执。审查从未读取 empirical TEST 正文、实际 TEST 标签、私有 authoring、原始 384 行审阅文件或导出数据；未执行新 FIT，也未创建真实 ROOT_GO、真实 TEST_START 或实证预测输出。

## 最终冻结身份

- FILE_HASHES.json：`11d6e1e8e7251e8fc7d884ab1defce2f2b7618f8550cfc745889d77350984e4d`
- test_evaluator.py：`0fa01328dc0df91b1c00ae18bd61839511c3c8b6c74bf56b81b4db26a8c7522a`
- protocol.json：`25d68451a217d1500ba38b89336fc93def2c49526a801aaa5398bb10519c68c9`
- PROTOCOL.md：`bdfa2abc376fd971dbb415f5d05d4bfcf6f6eac70daedf2a483d460ac88615c3`
- inference_core.py：`902cfa829557c602d8ed78e764ce143fe664daac1d3a490e0c5cf240832bd9b7`
- labels_v02.py：`4160778e11a16c79b58349ceeadf36c0e633474a9f39f16191211cacade9d1f8`

独立核对固定 FIT 产物：

- checkpoint：`c2d6d4352c0209d78f221ede226301fa835fa80c679a77b6f09bd9544aabc83b`
- FIT_RECEIPT：`96283df19251dabc0b4e416d8745e4dd80db227be35b3982489d8f9e3eb5887b`
- EMPIRICAL_COMPLETE：`5e3069433e398b1dc07026d2bc9b6409d18b9e0cf377bdf40ea71286c701279e`

checkpoint 内模型 canonical hash、FIT 回执与完成记录相互一致；训练变换明确来自 train，固定 150 epochs、lr=0.05、preference weights 精确为零。评估器只可加载上述固定路径及哈希，无候选 checkpoint 选择接口。

## 已修复的阻断项

最初候选只对输出文件及其直接父目录 fsync，未保证新建 run_state、runs、run-ID 目录在上级目录中的条目已持久化，因此不能完整支持崩溃后全局一次性标记及预测冻结的承诺。

最终版本新增 durable_mkdir：每个目录创建后都 fsync 本目录和父目录。run_state 与 runs 在 START 前完成持久化；run-ID 目录在 START 后、首次 TEST 读取前完成持久化。独立故障注入验证：

1. START 前父目录 fsync 失败：没有 START，没有 TEST 读取
2. START 后输出目录父级 fsync 失败：START 保留，写 FAILED，无 TEST 读取；不同 GO 也无法重试
3. TEST_COMPLETE 文件出现后，真实的父目录 fsync 调用失败：保留 FAILED，并抛出失败，不能因完成文件存在而视作成功
4. 正常持久化完成后 stdout BrokenPipeError：不再倒置为失败，也不创建矛盾的 FAILED

同时复核了作者的两项边界加固：输入目录必须为 canonical 路径，拒绝 `..` 别名；原始审阅行数必须是真正整数 384，拒绝 384.0。

## 一次性开封与预测冻结

- run 先施加资源限制，随后验证外部提供的 GO 字节哈希、精确 schema/action/scope、manifest/code/protocol、输入哈希集合、固定 FIT 产物和新鲜独占预算
- 上述 preflight 不打开或哈希 TEST 正文及 A/B 标签，只读取批准的 GO、storage receipt、公共包和固定 FIT 产物
- 固定全局 TEST_START 使用 O_EXCL 创建并 fsync；现存或不确定 START 永远禁止第二次调用，不允许新 run ID、新 GO 或新版本绕过
- START 后才读取、哈希及验证 test.json；精确十字段 slot schema 禁止 realized_condition、semantic flags、exclusion_reason、nominal target、template、pass 和 source path
- 64 个原始 slot 全部产生冻结记录。完成且主张定位唯一的文本先计算四类概率；未产出或无法唯一定位的 slot 保留明确 null 状态。不能先按语义审核或实际类别筛掉文本
- PREDICTIONS_FROZEN 独占只读创建、fsync、读回及哈希核验后，才打开 A/B 审阅子集及 label receipt，继而做实际标签裁决与诊断
- 指标只使用已保存概率；不重新评分、不重新拟合 scaler，也不做调参、重采样、替换、候选生成或选择

代码静态检查及 AST 比对确认：inference_core 的描述符、缩放、softmax 与冻结 FIT 公共实现相同；评估包不导入 FIT/controller/editor/generator，不调用 fit、edit、generate 或 scale_fit。

## 标签、原始分母及指标

- 强制 8 个 TEST 家族、每家族 8 个原始 slot、总计 64、每 genre 两家族；失生成/技术失败/未完成仍占分母
- A/B 仅覆盖所有已完成 TEST slot，包括分歧和不确定项；多余或缺失 review、TRAIN/DEV 行、重复 ID、同一 rater/context、缺失独立盲审声明均拒绝
- 原始 384 行文件只能以哈希和整数行数引用，不能携带路径。root projection receipt 绑定精确排序 IDs、IDs 哈希和子集哈希
- 冻结预测后才由原始双审阅与机械定义裁决实际实现条件；semantic fail、uncertain、分歧或结构不支持均排除于条件指标，不改写成名义目标
- CE 与 accuracy 按每个有资格家族先做家族内平均，再做家族宏平均；无资格家族仍对 coverage 贡献零
- 全部无资格时 CE/accuracy 为 null、coverage 为零，仍报告 64 slot / 8 family。独立测试覆盖不均衡样本量，确认没有错误使用 pooled accuracy/CE
- 固定 tie break 为条件顺序第一项；模型 CE floor=1e-300；规则比较器使用 one-hot 加 1e-15 floor 后归一化
- 规则比较器明确标为同一标签定义造成的 tautological comparator；其正确率不能解释成人类风格能力、独立语义正确性或模型增益

## 资源、终态与 root 执行条件

评估器检查外部控制产物字节数 + 当前包 + 1 MiB 输出保留额不超过 32 MiB。每次输出都计算累计 run_state/runs 字节，包含 START、预测、回执、COMPLETE、FAILED；正常写入保留失败输出空间，完成前也显式计入终态文件。实际资源上限为 ≤2 CPU、512 MiB、60 秒；无网络、外部模型或生成器调用。

成功必须同时满足：

1. 调用已知正常返回，进程 exit 0
2. TEST_COMPLETE 与 START、预测和回执的哈希全部匹配
3. 没有 FAILED.json

非零返回、不确定返回、超时或 fsync 失败一律 fail closed，即使能看到 COMPLETE 字节。任何 START 后失败均消耗本次唯一授权；禁止删除标记或盲目重试。

## 必须保留的解释边界

本审查证明的是冻结程序及合成故障行为，不证明实际数据正确性。root 必须自行确认所选 8 家族/64 slot 确实来自原始封存划分，正确投影 A/B 子集，并真实测量全部 controlled artifacts、保持独占预算。这些外部事实及真正审阅独立性无法仅由哈希或自声明 actor 验证。

路径、marker、只读模式与预算是受信协调环境下的工程约束，不是对能改代码/文件或并发写入的恶意同机主体的 OS 隔离。未做实际断电测试；fsync 的持久化依赖宿主文件系统正常实现。

仅 8 个家族，结果最多是 exploratory feasibility。它不是 71 维语言模型、自然作者风格结论、1280 篇自然作品、semantic guarantee、通用阶段完成或个性化授权。

## 可复查证据

- test_independent_faults.py：31 项独立合成测试
- final-synthetic-tests.txt：最终 80 项合成测试与实际资源配置
- FIT_BINDING.json：审阅过的 FIT 公共代码、协议与批准产物哈希
- REVIEW_RECEIPT.json：最终决策及冻结输入/证据哈希
- FILE_HASHES.json：本审计交付物的字节大小与哈希

初始测试日志保留修订历史；其中 manifest drift 是作者重新冻结前有意存在的版本不匹配，不是最终版本失败。最终判断只依据 final-synthetic-tests.txt 和本次冻结哈希。
