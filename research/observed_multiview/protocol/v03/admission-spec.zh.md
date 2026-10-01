# 独立准入实现说明

这是待实现模块的验收规格，不是已通过的运行收据。旧 `research/observed_sequence`、模型/数据哈希及 toy gates 冻结不动；新增独立 `research/observed_multiview`。实现前先把本目录及来源修正版绑定进运行 manifest。

## G0 权利/版本与可读范围

`source_registry.py` 验证三对象 SHA256、真实展开字节上限、历史许可证据 oldid、官方 API 与包内正文相等的独立审计收据。继承 WikiConv 原有 source/metadata 许可区别。对每记录附带 rights evidence 与 unresolved exceptions。此模块不可联网、不可下载，不能把网页通知当任意 item 权利凭据。

输入只允许原来源白名单、旧排除 manifest、公开来源审计和当前实验私有输出根；禁止用户个人博客及其任何别名路径。第三方旧博客/PMC属于既有授权来源，但本方案研究阶段不重读原文；补指纹须按下述独立授权范围进行。存储 receipt 绑定：文件长度、SHA256、解码、Unicode 版本、所有间接依赖源文件哈希。外部 ROOT_GO 字段只授权阶段，不替代实际核验。

## G1 投影和角色

`project_wikitext.py` 原创离线状态机/AST 和 `projection_contract.py` 保留每个 emitted codepoint 的原文范围及操作种类；未知嵌套/未闭合构造 fail closed。不要调用从语料获得的 Lua、模板、脚本或外部 URL。

必须有合成测试：嵌套模板、内部/外部链接、分类与文件链接、XML实体、混合换行、引文、代码、列表、跨行注释、未闭合标记、链接标签带模板、零长度/多codepoint映射、纯标记块。删除块后不得跨屏障形成 prefix；源哈希改变必须拒绝旧 cache。

96条来自已有元数据已知组件的校准记录名单必须先于任何自然正文检查冻结；新图合并后任一来源少于32个最终组件则calibration_underfilled停止，不补抽。6000候选在排除当时已知旧/诊断/校准组件后、任何正文资格筛选前另行封存；后续排除损失不补。独立助手逐项核对 source→projection、角色与权利例外，不看训练目标。复核差异和 unresolved 全部入账。没有人工标注声明。通过后冻结角色规则、构造 allowlist 和 source_map code。

## G2 指纹/依赖、抽样与新测试封存

`build_lineages.py` 导入旧 all-page components、旧全部192和475暴露组件，接入新诊断/校准组件。新复制指纹同时覆盖原文与投影。旧sampler未持久化完整长块/5-shingle指纹是已核实的G2 blocker；仅组件/原文SHA不足以排除新跨来源近复制。依本次root单独授权，按明确的既有第三方来源文件白名单，流式生成旧暴露指纹包，绑定各原对象hash、指纹规范与工具hash，不输出原文、不解析POS、不碰用户资料。Root已单独授权这次排除指纹派生，授权不等于G2通过；执行覆盖和复现审计未完成前仍阻断。缺任一必要来源则不允许G2通过。倒排集合交集输出每条近复制边的阈值证据，按 protocol 的精确包含率复核；全部 edges/DSU private，public 仅 aggregate。

已知翻译/转载、共同页面/版本、事实事件及地区章节线索分类型；发现具体记录对而无法解决的线索须保守union或隔离；这种未决边不许跨split。所有成员键带canonical-origin/project/object命名空间；WikiConv/discussion/mediawiki按固定注册表归一为wikimedia+zhwiki+page:规范整数，跨wiki不同project保留，未知来源别名拒绝；旧组件先展开成员/祖先边，排除按污染成员传播，不按新旧ID字符串比较。一个共享大地域标签不自动 union 全世界，也不能假装地域相关性消失；直接章节/跨页连续作品边硬 union，广域类别作敏感性分组。

`sample_metadata.py` 是本目录提供的可执行原型：它仅从已核验的 metadata records 选择代表和配额，无文件读取、无模型依赖。所有角色、权利、依赖的核验必须由前置模块完成。其输入不能含正文或 parser 目标；未知字段拒绝，方便检查。合成通过不等于前置事实真实。

实际 gate 工具需独立重建 DSU、重复抽样，比较规范 manifest 字节及每个原 source/projection hash，不只相信 receipt 内 `pass=true`。以下值都必须为0：跨split硬边、旧排除连通分量交叉、重复组件入选、不可回指投影字符、规则外读取、后验替换。报告候选→投影→边界→组件→配额逐级计数。每个细角色/source strata 均报告 eligible 和 unknown，不能只报总1920。

## G3 解析/共同目标账本

`produce_views.py` 复用哈希固定 Stanza、Unicode、adapter、segmentation 的读取接口，不改旧代码。在原对象及投影视图上分别保存 offsets；每个合法 prefix 独立可重建，strict closure 与原单位前缀完全相同。局部解析 cache 不可来自全文双向模型再截断。

`targets.py` 固定 14/28/2/1 四头；依赖只取同一单位中合法 lexical-to-lexical 非root弧，未知合法关系入 OTHER，非法 head/循环按 profile 报错。内容词形精确NFKC匹配仅用 prefix，以 token 次数作分子分母，target分母不能进入输入。

首12 TRAIN 记录（每来源4）审查 cached vs uncached tokens/form/spans/UPOS/head/relation、68传感器、目标和关系图；预测点逐项比较，不能只报平均差。供独立者重算，不依赖作者断言。失败即 stop，无后续整批提取。原分割保留所有 parse failures/屏障；四个头的 opportunity-specific missing reason 不能混成0。

## G4 多视图、变换与训练

`views.py` 返回 time-cutoff/record/source-profile/role/graph/measurement identity。global 是前缀单元每通道7个排列不变摘要组成的476维向量；graph 只由该前缀的 unit-form 观测边构造。无原文词形 embedding、source record/page/speaker ID、t/T 或全篇统计。

`transforms.py` 使用旧稳定两阶段中心化的记录等权思想，按三个来源各1/3拟合；保存 train support、exact-constant flag、中心和方差。1/3常量、所有缺失、常量log机会、近常量非零方差等回归测试必须过。只有训练生成器有 transform.fit 权限，dev/test reader 不提供 fit 方法。

`models.py` 冻结六组、所有 tensor shapes/激活、共享/不共享参数、graph message 函数、各组参数数和完全同前缀输入。GELU、hidden16、两轮均值 unit→form→unit graph 消息；不得用节点排序/节点ID偷带原序。global476→16及融合37/53→48→四头固定；静态/动态配对容量差≤较大组10%是实现冻结门，不是事后模型选择。

全部 prefix 视图测试未来替换不变；DeepSets/global/graph 测试单位排列不变；D/DG 允许顺序敏感；graph 随机 relabel 不变；同词形 ID 只影响相等关系，不许记忆词汇；shuffle 必须覆盖全部同一输入单位。测试中的目标词形、未来段号、EOF标记、后文专名都是刻意泄漏诱饵。

`fit.py` 用 source-equal conditional record macro，六臂同 ledger；固定18 fits/21600 updates，dev精确tie earliest；无额外搜索。先 verify-only，独立者核对真实训练 ledger/代码但不跑test。根明确FIT_GO后才 fit。

## G5 布局支线

`layout_pairs.py` 只消费经映射证实的自然段边界，不把任意物理换行作段落。先删除所有空白得到layout-neutral字符序列，再用与原布局无关的固定标点规则重新unitize。不能复用A的切分/features/graph缓存，只能复用冻结权重。丢弃原paragraph_index/source_offset等字段；映射仅作标签sidecar。候选位置只从neutral内容生成。合成测试要求相同非空白序列不同原段落的完整unit spans/features/graph/context逐项一致；否则B保持泄漏诊断状态并禁止fit。去空白引起的拉丁词边界测量变化须报告。

候选集机械检查非空白字符逐个相同、保护串计数相同及明确风险跨度不被切开，但返回 semantic_status=uncertain；不能自动升为pass。双盲化助手审查不调用模型分数，保留冲突/不可比。没有人类读者审查时，不发布人类偏好或可靠保义结论。

本支线 fit 需另行 ROOT_GO、独立账本/3seeds≤3000updates；它不因 A 完成自动获准，也不能看到外层test再调布局规则。如果未准备完成，A的测试可以独立结束，此后相同test对布局只能称已暴露诊断，新的布局效果主张须另留新test。

## G6 一次性测试与报告

`run.py` 阶段 allowlist 和外部 control.json(run/pause/stop)，每记录/每optimizer batch 检查；从启动阻断网络并固定torch两类线程为2。one-time marker 不覆盖、不新路径重跑；中断保存partial，恢复要由root判定。

独立审查前后都重验全部源码/间接依赖、数据和训练 artifact hashes。test metadata与读取次数进入ledger；只有一次明确TEST_GO可打开本轮320条新test，旧32条不重用。所有预测文件先冻结，再计算 endpoint/source-role/cluster summaries。

报告原始四头与等权复合、各source与role、每seed、pairedΔ和2000+2000固定bootstrap、实际CPU/RSS/字节、失败/弃权、coverage-only记录。无数据删失掩盖，无classifier/human/author gate 升级。通过该门只代表本估计对象的软件与有界实验可审核，不代表完整风格模型已验证。

## 暴露与阶段授权补充

任何助手/人直接阅读的自然正文、或用于投影调试的失败实例，在阅读/使用前进入exposure账本，最终完整组件排除全部模型分割。权利/角色审查不能绕过该规则。6000候选由已冻结代码自动处理，不提供逐条正文给开发者。SOURCE/ADMISSION_GO不包含Stanza、POS、features、targets、模型执行，G3仍需独立审核与批准。字符/标记分段仅为结构程序。记录首12复现的actual unit-parser calls，不因其小于30000 cap就假称已运行满额。
