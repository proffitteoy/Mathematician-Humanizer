# 观测序列真实拟合：独立有界GO

2026-10-01。**GO：可以在已核验train128／dev32缓存上启动固定15次真实拟合。test仍封存，不在本次授权范围。** 这是实现、泄漏和资源门通过，不要求先有经验效果，也不预判模型会获益。

## 1. 被审执行链

| 对象 | SHA-256 |
|---|---|
| fit.py | 9d839a463eac4331a8c1a3ee07769de94f968ea3ab5b1e00910f7dee74f1dd33 |
| run_fit.py | 595f57450426fcc8c7bf22741f7b980b69baec625ac49051d95fd819466b3bc5 |
| diagnostics.py | 7704c69091b8bdb93080373e266e8a257ea1ed7ccb961ea5ce7f43a1fdd1239e |
| learning-plan.json | e72d8ba86171e3ebe06440bd6a5921096b01fabbfa6bff73a3552af57321e750 |
| protocol.zh.md | 31474b57f93067622d6821fc487c3b2876cde815aa8faf97931142df741836ab |
| target-eof-amendment.json | 93dfa10d803428afebb5a5732eb41ae0d2fd8b31f306059e844728ec66e860b7 |

全部源码与测试摘要另由本目录收据绑定。test_fit.py最终为 `d1e3e092…`；此前报告的9deb…是旧字节，不能作为本次测试身份。

独立运行79项模块合成测试全部通过，含17项fit集成、53项契约／模型／生产者以及4项控制、5项EOF诊断测试。这些包含明确标注的合成优化机制检查，**不是自然数据拟合结果**。

## 2. 准入、旧缓存与新目标没有被偷换

wrapper固定核验缓存receipt `b36572cb…`。该缓存仍绑定提取时旧plan `32d08106…`；新训练plan `e72d8ba8…`显式指向旧提取plan和EOF修订 `93dfa10d…`。没有改旧缓存receipt来伪装它一开始就采用新措辞。

独立再次运行verify-only，实际读取精确128条train、32条dev及1,996／484单元。用拒绝调用桩证明该过程未进入train transform或model fit；test载入0。逐文件／源／profile摘要和跨区已知组检查均保留。先前独立缓存复核已确认755／223有效目标、117／31有效记录和4个失败屏障，不要求重复神经推理。

本轮目标明确为“固定来源视图定义的下一操作单位的观测POS组成”，包括EOF终止／可能残段；不是完整自然句或作者真实停止事件。修订发生在提取后、任何真实transform／fit前，明确承认旧文歧义，保留旧协议字节。主755／223共享ledger、计分及超参数不变。

terminal-source-unit诊断共74（train56/dev18），普通字符可扩展子集68（52/16）。另6个也不是interior或已证实完整自然句。标记不进入模型输入、loss权重或checkpoint选择，test类别数不开封。

## 3. 实现核验结论

- **独立入口。** root_approved默认false，test在transform之前被拒绝；旧learned的toy／personal门未修改。布尔flag记录调用方GO，不代替真实授权
- **共享目标与损失。** 所有七个比较器消费同一准备账本。14格整数计数归一，CE不再乘目标T；先记录内平均，再有效记录等权。12个零有效记录留覆盖，不计0损失
- **训练专属处理。** transform只拟合train，先验只用有目标的train记录。常量／全缺失通道冻结为0，保留支持、presence与机会已知标志。原1/3方差消减已用实际观测中心及稳定两阶段方差修复，无任意epsilon抹去小方差
- **真实前缀。** 模型只接收前缀张量和两个已见长度量，逐目标序号仅作分组／随机种子。DeepSets先非线性再池化；GRU不跨prefix保存隐状态；无序臂没有逐单位位置或历史特征旁路
- **打乱控制。** 同结构GRU训练时按预定种子每epoch重排；dev评估采用固定epoch=0的重排，避免checkpoint比较被额外随机噪声改写。测试时打乱仍是另一个未执行诊断
- **选择与EOF诊断分离。** 每个臂／种子用全共享dev目标的同一宏CE选最小epoch，完全相同时取最早；先落盘权重／transform／prior摘要与selection-freeze，再运行endpoint诊断。诊断不回流选择
- **没有test评价器。** 当前fit／diagnostics均仅接受train、development；未来test loader和一次最终评估需另外冻结与放行，本次不等它们实现

## 4. 本次GO的固定范围和停止方式

- 五个学习臂 × 三种子 × 40epochs；固定AdamW、学习率0.001、weight_decay0.0001、梯度裁剪1、batch16记录
- 最多4,800次optimizer更新，累计训练60分钟，CPU／interop各2线程，无GPU，3GiB运行期RSS上限
- 训练后诊断单独30分钟；产物仅写仓库外，250MB输出预算，不下载模型或公开原文、逐目标、权重
- 使用已给定的run／pause／stop控制文件；hook在epoch、batch、预测、评价及optimizer边界检查。pause是协作暂停，延迟还包括当前计算片段，不是0.1秒硬实时保证；暂停时间计入60分钟上限
- 现有stop不会被初始化覆盖，缺失／损坏控制文件停止。resource、源／实现摘要、split或profile异常停止，不用部分模型冒充完成实验

core的暂停／恢复／stop、总更新上限、墙钟退出与timer恢复均有通过的合成测试。进程RSS检查是运行期约束，不是OS保证任何瞬时分配永不越界。

wrapper在verify-only与执行模式间显式二选一；本次独立审核没有调用root-fit-go，也没有拟合真实transform、先验或模型。实际启动仍由root按上述字节及命令执行，不能泛化为任意数据／配置的常驻拟合许可。

## 5. 结果应怎样解释

完成后可以报告训练／开发的观测目标损失、覆盖、种子分布及已冻结后置诊断。dev已用于选epoch，其最好值不是无偏最终泛化结果。若实验在预算内未完成，应报告受限运行，不换样本、减epoch或只发布有利臂后继续叫原实验完成。

这里没有作者真值、自然人分类、潜在句法识别、跨体裁泛化或写作效用认证。即使GRU改善，也首先是这个固定来源窗口任务中的观测预测信息；不替代用户最终文章验收，不触发个人资料准入。

证据：`all-79-tests.log`、`verify-only-checks.public.json`及 `fit-admission-receipt.public.json`。本次复核无新自然解析、无真实fit、无test目标、无远端写入。
