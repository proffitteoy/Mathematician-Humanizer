# 缺少text字段：下一版本最小修补建议

当前绑定evaluate.py：`add6c269342e31404981dea09917a4df1e1126cac41033120c2e154960c4388b`。

本文件是修补建议，不是已应用的修补。当前固定64条均有text，结果不受影响。不得就地替换旧预注册／私有冻结选择，或沿用旧源码审查摘要。

## 精确失败链

1. `read_records()`允许没有 `text` 元数据的块进入记录列表
2. `select_records()`只根据sent_id抽样，不要求text
3. `evaluate()`已加selected计数及整数行数，但在建立可保存的unit／进入reference错误捕获前，执行 `segment(record['meta']['text'])`
4. 该处抛KeyError，整批无返回结果；`reference()`里的missing_text检查没有机会执行
5. 冻结辅助程序另有直接 `x['meta']['text']` 访问，也不能生成含该记录的选择清单

## A. evaluate最小变更

把记录级 `unit` 初始化移到 `rowcount`计数之后、任何text读取／分段之前。用 `record['meta'].get('text')`，在None时做下面的记账并continue：

```python
unit = {
    'record_index': record['record_index'],
    'stratum': stratum,
    'boundary_exact': None,
    'reference_integer_rows': rowcount,
}
text = record['meta'].get('text')
if text is None:
    coverage['source_text_unavailable_records'] += 1
    coverage['boundary_not_evaluable_records'] += 1
    coverage['reference_failed_records'] += 1
    coverage['production_not_attempted_missing_text_records'] += 1
    coverage['control_not_attempted_missing_text_records'] += 1
    coverage['excluded_reference_integer_rows'] += rowcount
    reference_fail['missing_text'] += 1
    unit['source_text_failure'] = 'missing_text'
    unit['reference_failure'] = 'missing_text'
    private.append(unit)
    continue
spans = segment(text)[1]
# 原有边界、参考、生产和控制处理继续
```

这些新计数字段在初始化时显式置零。没有文本时不能说边界错误，也不能说解析失败：操作未开始，边界无法判断。`boundaries`只记实际分段过的记录；用 `boundary_not_evaluable_records`保证总账闭合。保留所选stratum、整数行计数和原始私有定位，不能替换入选记录。

## B. freeze辅助程序的最小配套

若下一版仍承诺缺text记录保留，则冻结清单允许该记录的 `text_sha256` 为None，并增加显式状态，例如 `source_text_status='missing'`；已存在text时正常计算摘要。源码及清单schema／预注册版本均升级。缺失text不影响根据sent_id确定的选样顺序，不删记录、不补样。

若选择让text缺失成为整份语料不接纳的前置错误，也可实现显式 `ValueError('missing_text_container')`，但必须把方法承诺改为“容器前提不满足则拒绝整批”，不能再宣称该情况进入记录级覆盖。该替代方案不能算兑现原有缺字段保留承诺。

## C. 必加回归测试

使用原创合成64条（news/wiki各32），每条1个整数token；仅1条缺text，sent_id与token行完整，另外63条均可对齐并由Fake parser/control成功返回。断言：

- selected_records=64，selected_reference_integer_rows=64，private记录数=64
- common_gate_records=63，common_gate_reference_tokens=63，excluded_reference_integer_rows=1
- reference_failed_records=1，reference_failures的missing_text=1
- boundary_exact_records=63，boundary_mismatch_records=0，boundary_not_evaluable_records=1
- production_source_units=63，production_failed_source_units=0，production_not_attempted_missing_text_records=1
- control_success_records=63，control_not_attempted_missing_text_records=1
- 缺text的unit保存reference_failure=missing_text，boundary_exact为None，且没有reference／production／control分析
- Fake parser只被调用63次；不能用拼接token FORM重建缺失文本
- 成功子集分数和通道仍可生成，不发生整批异常

另给 `freeze_bytes` 一个允许测试固定SHA的合成入口／mock：同一seed仍选中全部64个ID，缺text项摘要为None且标记缺失；两次生成字节一致；exclusive-create仍拒绝覆盖。不要为了测试放松真实CLI的固定SOURCE_SHA校验。

## D. 发布处理

现版README补充已知限制即可如实发布固定结果。下一版代码修正后，应重新运行本反例、现有75项相关测试和60项核心回归，重新生成实现收据；若要宣称自然数据结果属于新实现，再按原选择与权重复跑并核对数值。无需在现版冻结文件中伪装成没有发生过偏差。
