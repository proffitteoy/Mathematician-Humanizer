# 拓扑批处理故障账目草案 v0.3

这是旧 T1 六例运行器的独立后继草案，解决单个 encode/estimate 异常终止整批、其余选中记录无账目的缺陷。所有修改仅在此目录。旧六例协议、运行源码、聚合、独立复核及已发布结果保持原字节；它们属于历史 v0.1，不能让旧收据替新代码背书。

**本草案只完成代码与原创合成验证，没有新自然来源推理、下载、训练或经验参数拟合。** 将来用于扩容数据前，仍需冻结该批选样/许可用途、具体源视图、资源预算及预定分析，另行授权执行。当前 consumed observed-sequence 测试集不能借此进入新训练。

## 行为和账目

入口在调用任何模型前先保存包含全部选定记录的 ledger；严格固定顺序，无替换、无自动重试。每条记录保留以下状态：

| 状态 | 含义 |
|---|---|
| ok | 本记录编码及数值估计通过，有限正数PHD |
| unavailable | 编码完成，冻结估计器按原规则数值弃权，例如点数小于50 |
| failed | 本记录输入、编码、重复编码或估计失败；保留stage及封闭reason，不保存异常原文 |
| not_run | 全局停止后未执行的固定记录 |
| pending / in_progress | 仅在尚在运行或非正常进程中断时可出现；不算成功、失败或零分 |

缺少source路径、空路径、文件缺失/不可读、空文本/纯空白、无效UTF-8、输入字节上限等为可见的逐条输入失败。单条encode/estimate异常，以及无效/nonfinite输出，记账后继续下一条；失败和弃权都保留在selected覆盖分母。过短向量云直接交给原估计器产生原弃权理由，不减少最少点数、不制造零维度。

**来源摘要、模型、profile、核心代码、向量云摘要不符，网络尝试，资源超限、内存错误和重复云不一致均全局停止。** 即使后端吞掉网络异常，计数器也会在后续检查把整批停止。原始字节摘要先核验再判空；被清空而摘要不符的文件不会被降格为普通空记录。路径越界或symlink逃出source-root同样停止。

正常完成或受控停止会写出覆盖全部选中记录的终态ledger。此前成功记录保留；触发全局停止的当前记录不能被误算成已完成科学结果，剩余记录标not_run。`run_status=stopped`时，任何保留的数值仅为部分诊断，`partial_numeric_diagnostics_only=true`；不能声称完成固定整批。

采用每次唯一的同目录临时文件、文件与目录fsync及原子替换/排他创建。临时文件总在finally尝试清理；清理失败明确停止并将残留计入磁盘预算，不覆盖原始写入错误。预留终态账目空间，使正常磁盘预算停止仍可写失败与not_run。硬崩溃、OS kill、文件系统完全不可写不可能保证最后一次终态写入；已有ledger的pending/in_progress应视为未完成，不允许据缺失行推断成功。需检查`run-finished.private.json`及其摘要链。

## 与旧六例保持的接口

CLI只加载已固定的encoder.py、phd.py、encoder-profile.json，逐项核对SHA256后才执行代码；核心算法、模型资产、512-token截断、768维float32向量、排除特殊token、PHD参数和最少50点规则都不变。模型为调用者指定的已存在本地目录，加载前/整批后验证原profile的全部资产。没有Hub名称解析、下载回退或新依赖安装。

保持first selected重复策略：首条可编码时在同进程再编码一次并比对完整NPY字节。首条输入/编码不可用时，重复检查记为不可完成，**不以第二条替换**；重复编码异常为该条失败，实际重复字节不一致是全局停止。该检查仍只证明同一进程该次重复，不能替代跨设备或统计稳定性验证。

聚合分别报告selected、各状态、输入/编码失败理由、数值弃权理由、已知/未知截断覆盖、未截断token数范围、保留点数范围，以及仅在数值成功记录中的PHD min/max/median。零成功时全部数值为null。原始source view可能有元信息、代码或引文；截断后是来源开头窗口，不自动成为完整文章、纯正文或人类文风。rerun离散度仍是固定有限云的抽样变化，不是总体置信区间。

## 可移植本地入口

没有硬编码来源、输出或模型路径。传入`--topology-dir`指向已有仓库的research/topology目录；该目录中三个核心文件必须与本草案的固定摘要一致。运行器使用现有Python、NumPy、SciPy，实际编码才加载现有Torch/Transformers。RSS监控使用标准resource模块，支持Linux及macOS的单位差异；无法可靠获取RSS的平台明确停止，不静默跳过预算。文件写入要求本地文件系统支持原子replace及排他hard-link创建。

私有manifest结构为：

```json
{
  "schema": "topology-fixed-inputs/0.2",
  "data_kind": "licensed_natural",
  "records": [
    {"record_id": "private-case-0001", "relative_path": "source-0001.md", "sha256": "逐字节UTF8文件的64位小写SHA256"}
  ]
}
```

record_id唯一且最长256字符；relative_path可缺失/空以保留不可用记录，其他已给路径必须在source-root内。缺失/非法记录ID或SHA256使整份manifest不能准入，不能在不知道选样身份时读取文件。最多10,000条只是输入结构上限，不代表预算足以处理该数量。CLI核验完整manifest原始字节摘要；Python注入接口由调用者承担同样的已验证manifest前提，仅用于受控集成/合成测试。

仅在另行得到该批本地运行授权后使用：

```bash
python runner.py \
  --authorized-local-run \
  --manifest /private/frozen-inputs.json \
  --manifest-sha256 ACTUAL_MANIFEST_SHA256 \
  --source-root /private/sources \
  --model-dir /existing/local/xlm-roberta-base \
  --topology-dir /existing/style-compiler/research/topology \
  --out /private/new-topology-output
```

授权标志只是记录调用者已有批准，不能自行授予自然数据访问。固定默认预算为30分钟、3GiB峰值RSS、50,000,000字节私有产物、每来源1MiB、CPU intra/inter-op各2；无GPU或新下载。代码在操作前后和持久化处检查墙钟/RSS/磁盘，**不是内核预防性内存限制，也不保证中断正在运行的任意扩展函数**。来源超过字节上限保留为失败，不能静默截取字节；token截断仍由原profile明确记录。

输出目录必须为空，且位于来源树/核心代码树之外。已存在目录内容会阻止重跑，不能改路径绕过已中断批次的审查。默认只保存私有数值/提取元数据，不保存向量云；明确加入`--save-clouds`才保存云，仍占同一磁盘预算。结束码0表示固定选择处理完成（可有逐条失败/弃权），2表示全局停止；不得只看退出码而忽略覆盖。

输出：

- ledger.private.json：全部固定记录身份与状态、截断元数据、私有结果摘要
- result-N.private.json：单记录提取/数值细节；可用时保留，即使后来数值步骤失败
- 可选cloud-N.npy：私有向量，永不自动发布
- aggregate.public.json：安全聚合，无原文、记录ID、路径、单来源摘要或异常原文
- run.started.private.json / run-finished.private.json：启动条件及最终摘要链

## 验证和历史完整性

`test_runner.py`全部使用新写的合成字符串、假编码器和故障注入。另以现有原PHD估计器验证合成短云弃权；没有加载自然文本或神经模型。覆盖encode/estimate异常后继续、missing/empty/UTF-8、太短、truncation、源码/来源/模型/profile完整性、禁止隐式下载、被吞的网络异常、repeat失败/不一致、时间/RSS/磁盘/内存/输出故障、全样本分母、隐私字段、重复执行拒绝及结果摘要。

```bash
TOPOLOGY_CORE_DIR=/existing/style-compiler/research/topology \
  PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  python -m unittest discover -s . -p 'test_*.py' -v
```

运行器与本目录文件的最终摘要见`DRAFT_RECEIPT.public.json`；旧自然T1冻结文件摘要见`HISTORICAL_FROZEN.sha256.json`。这只是下一次自然仪器实验可审查的运行草案，不对新语料上的通过率、PHD分布或有效性作经验声称。

## v0.3 持久化修订与复验

v0.2及其否决审查保持原字节。独立反例证明：v0.2一次ledger replace失败留下固定临时名，妨碍后续终态恢复。v0.3为每次提交生成唯一临时名并在finally清理，保存原错误，新增目录fsync，允许恢复后的文件系统保存failed/not_run终态。一次清理失败会显式停止；残留文件仍计磁盘预算。若磁盘持续不可写，函数抛错且没有完整finished收据，绝不声明终态账目已耐久写入。

本版运行47项不同合成测试：31项原测试、12项先于修复写出的独立故障用例、4项新增清理/持续磁盘/目录fsync用例，全部通过。另复跑38项冻结核心合成测试。该修复由发现问题的审查者实施，不能冒称又获得第二位独立代码审查。新自然执行仍未授权，历史六例和旧性能不替本版背书。
