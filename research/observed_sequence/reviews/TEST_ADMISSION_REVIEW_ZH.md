# 固定测试集一次性评估：开封前独立准入审查

## 决定

**技术准入 GO，限本报告绑定的最终版本与 `TEST-RUN-COMMANDS.txt` 中的精确命令、固定输出目录。** 由 root 单独批准后，可一次性提取冻结的 32 条测试记录、至多 485 个原始操作单元，并用已冻结模型执行预定评估。本审查本身没有开封测试原文、目标或 endpoint 计数，没有自然测试推理或拟合；不设置新的经验效果门。

最终 112 项原创合成模块测试独立通过。另有独立合成 wrapper 联调及不等 cluster 大小的 2,000 次 bootstrap 算术复核。没有发现尚未解决的阻断项。需要完成后的实际结果读回，才能确认执行产物；准入不预先认证未知测试数值。

## 已核对的范围

1. **冻结样本与已有产物。** 只读取冻结元数据，确认 test32 条、原始单元 cap 合计485、32 个不同 source/copy component，与已知 train/dev component 和 exact-source 的交集均为0。元数据不含原文，本次没有打开原始 archive 或测试提取缓存。固定 manifest 哈希为 `ddbe04ae3a3a1d289fbb53e35872b2eb9df27407d92f6002066c992c1580b0b8`。15 个已选 state_dict、训练变换及先验逐项哈希验证通过；原拟合/提取代码绑定保持不变。资格、许可、既往暴露及未知复制的限制沿用原门审查，不能据此宣称全局无重复、未见作者或人类真值。

2. **禁止测试拟合与选择。** 只加载完整15个固定 checkpoint，基线用同一冻结先验；无 optimizer、变换或先验估计、校准、epoch选择。checkpoint 形状、dtype、有限性严格核验；模型参数禁用梯度。固定三 seed 的汇总是“分别评分后的损失均值”，不是平均概率 ensemble 的 CE。开发后冻结的 source-window 目标继续包含 EOF/censored 单元；没有重新定义为自然完整句子。

3. **共同目标清单与分母。** 17 个主系列（2基线、15checkpoint）及3个普通GRU测试时乱序诊断共享同一 target ledger。输入仅含闭合可见前缀、68本地通道的272维编码和该前缀的长度；目标/未来特征、最终总长、endpoint、speaker、source ID均不进入模型。失败单元仍为屏障，不跨越补齐；单个模型失败停止整个评估，不能改成模型各自支持子集。主指标先对记录内有效目标等权，再对有至少1个目标的记录等权；零目标记录保留覆盖、损失为未定义，不能赋0。若整批无有效记录则停止。

4. **先冻结所有预测，再算 endpoint。** 实际 wrapper 先保存包含20条系列的 `all-predictions.private.json`，再写其联合 SHA256 的 prediction-freeze，之后才调用 endpoint_flags。这是一个覆盖全部20系列的联合哈希，不是20个各自独立文件哈希。原创合成联调逐次截获4个 endpoint调用，均验证上述文件已存在、联合哈希吻合且20系列齐全。page/speaker元数据可在来源对齐时先读取，但只能供后置汇总；endpoint标签必须后算。3条普通GRU输入顺序扰动使用相同冻结权重及已声明的独立随机种子域，明确区别于已训练的 shuffled-GRU 臂。

5. **描述性不确定性。** DeepSets−GRU逐记录、逐seed先求差，再取三个seed均值；正值有利于GRU。按有目标的已声明component重抽cluster，保留抽到的每条记录及重复次数，重新计算记录等权比值，固定2,000次及线性2.5%/97.5%分位数。独立实现通过逐次展开大小2/1/3的合成cluster，2,000个draw及区间与实现逐项相等，证实不是cluster均值等权的另一指标。少于2个cluster区间未定义。speaker敏感性用声明的顶层speaker key，缺失key各自为单记录组；它不是作者真值或全部依赖结构。区间仅描述固定模型、固定受支持记录的重抽样，未包含训练集/参数选择、解析误差、未知复制或所有跨组依赖的不确定性。无p值，也不据区间改选模型。

6. **单次执行、停止与私有输出。** 同一固定输出目录的 `unseal.started.private.json` 以排他创建方式写入；合成联调确认第二次调用在提取前被拒绝。该保护按目录生效，不是系统全局锁，不能另换目录或删除marker绕过失败。run/pause/stop控制、缺失/非法控制停止、无网络下载、私有输出250MB上限及3GiB RSS检查已审。最终入口在模型加载/解析前设 intra-op和inter-op各2；实际只读验证为2/2。抽取阶段90分钟、评价阶段30分钟，外层检查涵盖暂停与阶段间I/O；评价计算另有SIGALRM。抽取、I/O及RSS采用安全边界检查，不是内核级预防限制或严格实时停止保证。失败后保留现有证据，由root决定后续，不自动重启。

## 本轮修复及验证

初版 wrapper 只核对拟合收据中的 observed_sequence 源码，未核对原提取收据的 linguistic/segmentation 依赖。profile/schema哈希不能代替算法源码哈希。最终版在开封marker之前、最终报告之前，逐项核验原提取 `module_hashes`，并绑定两个archive helper；两项纯合成篡改测试通过，实际旧依赖亦全部吻合。

初版解析阶段没有设置inter-op池。本审查用全新原创一句合成文本做本地Stanza→合成评估联调，观察到解析时inter-op为9、到评价才变2。最终入口在任何模型/解析之前显式设2/2，并新增合成设置测试；不修改冻结parser profile、权重或统计规则。另修正文档，将endpoint后算与page/speaker后置使用准确区分。

这些都是测试开封前的执行完整性修正；旧计划 `aee15c871803e1f8235338d8b48f17423897f650ca8905c36a96501ac7f9a9d2` 保留在audit中，最终版本见下。112项模块测试包括原79项已拟合模块契约，全部通过；本轮未增加自然数据效果试验。

## 最终绑定

- 测试计划：`427e39afabbdd21793459a7eb2e1368d480dc1af9a46ed73c7104a3d7dde8cb8`
- 新实现收据：`a7b32894f66249d4bef4c9386fad7444497a054210ab9d3fc5847ef2426ab38a`
- run_test.py：`7e9de68ed681e58fc2696b0f0b3aef3f153d918871c95942df129e8b4e9c6711`
- sealed_extract.py：`89476ad55f7f30e8ab08660815f9389cf24a49757244f2822eae883d2571331e`
- evaluation.py：`0c1d8eb95da7da31478ace776e18d1ff8705ce9853169e2d173923a26c301c6d`
- 精确命令文件：`2093c278ef4645bb659952d02bd7ceb280f304bb79701270cba44fbd11817672`
- 模型selection-freeze：`0633ef57ef1228d93ac989c366a39b239315531f64a5c2ed645572a6ec709c21`
- 原拟合结果：`a659b33493de4227dfed7aa92cd44837cd3d10f1a7fc1bfe716bdbc00192398b`

`final-binding-checks.public.json`记录元数据、线程及源码校验，`wrapper-order-checks.public.json`和`bootstrap-checks.public.json`记录独立合成复核；完整绑定见 `test-admission-review-receipt.public.json`。该公开包不含原文、逐记录标识/定位信息、测试目标、逐记录损失、speaker key或权重。后续10倍语料扩展属于另一实验，不得反向改写本次32条测试集或冻结模型。
