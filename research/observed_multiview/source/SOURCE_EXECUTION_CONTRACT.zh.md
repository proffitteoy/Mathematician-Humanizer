# Source-only 实施与后续执行契约

当前授权只覆盖实施、合成测试与元数据冻结；此实现没有执行新的自然96校准、6000候选正文、POS/目标/模型或新下载。下面的命令是未来审核后的操作契约，不是已执行收据。不能以源码中字段或命令行字符串代替 root 的实际阶段批准。

## 已封存的元数据结果

- 三源现有元数据框：讨论117,266记录，新闻14,876页，旅行4,691页；原始字符数200..20000。讨论只取明确非标题top-level；后两者只取主空间非重定向
- 旧192+475组件按成员污染传播，所有174,410旧wiki页面祖先分量导入；旧已暴露wiki页面5,780个
- 导入旧排除指纹包的全部不同成员、3个已诊断博客成员、wiki已有长块组、542条明确旅行父页/子页关系。广域类别保留为敏感性元数据，未当作全球硬合并规则
- 在上述已知图排除后可用组件：讨论66,298、新闻14,729、旅行4,342。每源按已冻结v03哈希顺序选32个已知组件的全局哈希最小记录，共96；未做体裁/Han/投影/单位/闭合点筛选
- 96冻结文件SHA256：5eb673703d71a6f26d8f2828c99e3e4d857355714b541d38ba15fdc424a142cf
- 图/记录SQLite：144,678,912字节；自然正文不在该库。所有成员、定位、标题和抽样记录仅在private
- 同作者元数据复算重新检查192,693个规范组件哈希、全部旧成员和冻结96，零校准/旧排除交叉。这不是独立审核

初次元数据生成时的registry源码按原哈希另存。后来只增加未来候选冻结时的独立图验证；现有96及元数据库从未替换。加注记录见metadata-freeze-code-addendum.json。

## 阶段隔离和GO

runner只识别calibration、candidates两个source-only阶段。每次执行同时需要：

1. 独立提供的contract SHA256，不能从待验证contract内部取值
2. 独立review文件及其SHA256，decision必须为APPROVE_CALIBRATION_EXECUTION或APPROVE_CANDIDATE_SOURCE_EXECUTION，绑定同一contract及合成测试通过情况
3. root批准文件，actor=root；action分别为CALIBRATION_GO或CANDIDATE_SOURCE_GO；绑定contract/review SHA256，no_other_stages=true
4. 精确code/source/metadata/解释器/Unicode/分段规则/标准库与加载共享库哈希；代码集合增加或任意变化都拒绝旧契约
5. private/control.json只允许一个state，取run/pause/stop。缺失、未知字段、未知状态均拒绝

SOURCE_IMPLEMENTATION_GO不能启动任何正文处理。当前没有生成GO、review approval、自然执行marker或自然执行receipt。

## 命令（尚不允许启动自然阶段）

在全部代码冻结且相关旧排除处理完成后，先提出契约：

    python public/runner.py prepare-contract --stage calibration

该命令只在固定private根生成calibration.contract.proposal.json；它不产生批准。需要独立审核者实际重算所有绑定，而不是相信receipt的pass字段。

获明确实际批准后，未来执行命令形状为：

    python public/runner.py execute --stage calibration --contract private/calibration.contract.proposal.json --contract-sha256 <independently_supplied_sha256> --review <review_file> --review-sha256 <independently_supplied_review_sha256> --go <root_stage_GO_file>

candidates使用相同参数形状和stage=candidates。不得改根/换目录、删marker或复制marker规避一次性执行。中断、暂停到资源超限、失败和partial均不会隐式重试；新版本/恢复需要root判断。

## 暴露、读取和资源

- 正文流打开前，全部96校准记录的exposure事件逐条append并fsync，声明其最终完整组件永久污染；读取失败也不撤销
- calibration与candidates另有source-stream-open和逐条selected-source-view-pre-read账本，绑定原对象/原文SHA。只允许精确冻结source-view
- ZIP只读冻结utterances成员；SAX只保留被选page/revision正文，DTD/实体声明拒绝。流过未选字节不做资格/角色/投影/指纹/目标处理
- Linux内核seccomp阻断网络、子进程创建/执行与io_uring；导入Stanza/Torch等模型/解析库拒绝。无GPU；线程环境上限2。仅字符/标记结构处理
- 单记录检查run/pause/stop；暂停消耗墙钟。90min累计包括已有metadata、3诊断博客增量、旧投影排除，以及之前source阶段receipt。RSS≤3GiB；RLIMIT_AS同为3GiB，约束更保守
- 全部新private文件加旧指纹目录实际大小，且旧包最低计566,539,146字节，总量≤1GiB。写前预留预算和紧急receipt余量。旧压缩源不复制；输出按记录gzip确定性压缩
- 校准记录保留私有raw source＋projection＋source_map供两个独立助手逐条复核。候选只自动处理和保存私有结果；人/助手若要直接查看其自然正文，必须先补独立exposure并排除最终组件
- 运行只输出聚合状态。自然source失败内容不打印；partial、实际CPU/墙钟/RSS/字节、读取与输出哈希可审计

## 校准后候选冻结

registry.freeze_candidates需要外部独立review哈希、已完成96校准与两助手复核、未决权利/角色/映射均0、冻结role规则哈希以及最终成员图哈希。它独立重算组件规范哈希，拒绝已知祖先分量被拆开、旧污染丢失或旧成员缺失。

新图令任一来源32校准记录少于32最终组件、跨源碰撞或连到旧排除时，calibration_underfilled停止；不追加、不替换。通过后排除旧/诊断/全部校准组件，并在任何候选正文资格检查前按v03冻结最多讨论3000、新闻1500、旅行1500。候选失败/图合并/资格损失均不补抽。

## 尚未完成的后续门

runner阶段终态最多为source_projection_complete_pending_independent_review_and_lineage，永不声明G2准入。最终全校准/全候选/旧曝光的兼容跨视图复制匹配、全新硬边传染、未决具体来源线索和独立复算必须另外完成；负匹配不证明无复制，也不证明旧clean-prose投影覆盖。build_lineages的配额输出仍只是需独立G2核验的提案。

权利角色默认per-record pending，speaker/latest editor不是原作者，两个助手不是人类金标。本阶段没有feature/targets/fit/test授权。

## 可重复验证

    cd public
    PYTHONDONTWRITEBYTECODE=1 python -m unittest test_runner -v
    PYTHONDONTWRITEBYTECODE=1 python -c 'import check_metadata_freeze as c; print(c.check())'

测试只用生成的合成文本/ZIP/XML；包括真实SAX/ZIP adapter接口、96先曝光后读取、第三raw_text参数、单次marker、pause/run/stop、全局字节和旧资源计数、独立哈希不符及内核socket拒绝。自然适配器尚未针对本轮96或候选执行。

## v02校准运行修订

原runner/test/测试收据已保留，旧投影排除实际运行绑定的六个源码字节保持在独立冻结子目录。v02只用于未来校准契约：

- source adapter记录selected-source-view-attempt及实际已读取源视图事件；即使后续投影/输出失败，实际读取计数不丢失。XML同一缓冲块内先读取的多个选中页也逐项入账
- terminal receipt区分source-attempt、actual-read、projection-attempt与completed；失败中的记录键/成员/原SHA只进入私有receipt，public仍只有聚合计数
- source_risk_gate在投影前标记fenced-code和超长HTML标签角色未决，保留source_risks sidecar和原metadata；不修改旧投影profile及其已审计输出
- 校准全阶段新增私有输出上限80MiB，另外始终受总旧＋新1GiB约束；GO前再次检查实际剩余空间，元数据字符总量/最大值入契约preflight
- candidates执行和候选execution-contract准备均明确阻断，直到流式原文/投影/source-span指纹写入及资源/谱系集成完成。当前不能把仅投影的6000候选运行称为可完整执行的来源准入流水线
