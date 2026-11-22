# P5 Harness集成设计

## P5-R1 修订记录（2026-11-22）

- 将参考状态扩展为可恢复、可重建且双池隔离的持久状态机。
- 增加运行级alpha账本、经验校准分辨率和参考epoch血缘字段。
- 为RecipeRegistry和Qwen提案增加证据能力匹配，不再把有效fact_id等同于有效使用。
- 扩展轮收据为完整“证据—Recipe—预期—实测—选择”链，并增加反事实验收。
- 本修订不修改任何正式源码、RC或Docker镜像。

## 1. 现有正式链路

当前`0.11.0rc1`正式链为：

```text
OfficialRoundAdapter
  → load train/validation/parent/history
  → TaskProfiler
  → QwenExperimentAgent(call 1)
  → CandidateTrainer
  → LocalEvaluator
  → QwenExperimentAgent(call 2)
  → ArtifactSelector
  → RoundRecorder / state / finish
```

P5只在`TaskProfiler`与第一次Qwen调用之间增加证据层，不改SDK、checkpoint、模型训练、指标实现、选择、预测和回滚协议：

```text
TaskProfiler
  → DriftMonitor
  → DiagnosisAttributor
  → EvidenceProjection
  → QwenExperimentAgent(call 1)
```

## 2. 新增职责单元

### 2.1 `DriftMonitor`

建议文件：`src/brace_formal/drift.py`

输入：

- 当前`DataBatch`；
- 父checkpoint特征合同；
- 合法历史稳定摘要；
- 可选父模型当前误差摘要；
- `group_hints/time_hints`。

输出：不可变`DriftReport`。模块不得调用训练器、模型网关或artifact选择器。

### 2.2 `DiagnosisAttributor`

建议文件：`src/brace_formal/diagnosis.py`

输入：`TaskProfile`、`DriftReport`、当前合法父模型性能摘要和历史实验摘要。

输出：`DiagnosisReport`，明确facts、hypotheses、unknowns和experiment needs。

### 2.3 `DriftStateStore`

建议文件：`src/brace_formal/drift_state.py`，或在保持`history.py`单一职责的前提下建立独立状态类。

保存：

- 稳定参考窗口聚合摘要；
- 活动参考池与隔离候选参考池，以及各自不可逆摘要和窗口哈希；
- 经验阈值所需的不可逆分位数/同步重采样摘要、实际`B`和最小p值分辨率；
- `CALIBRATING/STABLE/WARNING/CONFIRMED/RECOVERY/REBASE_PENDING/STABLE_NEW_BASELINE`状态、持续计数和漂移episode；
- `alpha_run`、每轮`alpha_t`、累计已消耗alpha和监测序号；
- 当前/历史参考epoch、原子替换原因和血缘哈希；
- 历史性能漂移摘要；
- 每轮作用域哈希。

不保存逐样本特征到公开记录。若平台workspace允许保存合法历史原始数据，仍由现有`HistoryStore`管理；漂移模块只消费受控接口，不获得原始挂载根路径。

### 2.4 `EvidenceProjection`

建议在`agent.py`中新增纯函数，将完整报告裁剪成Qwen可用聚合上下文：

- 漂移状态和置信度；
- top贡献特征索引及事实ID；
- 变化类型、效应量和持续窗口；
- 模型影响状态；
- 可验证实验需要；
- 限制和未知项。

继续通过`_assert_aggregate_only`禁止逐样本、原始路径和敏感字段。

## 3. 轮次数据流

1. `round_core.py`读取任务合同、父模型、当前train/validation和历史。
2. `build_task_profile`保持不变，输出任务类型、指标、特征数和分组/时间提示。
3. `DriftStateStore`从`rnd.state_workspace`恢复上一轮合法摘要。
4. `DriftMonitor`比较当前train与稳定参考；有合法标签和同口径父模型误差时生成独立性能漂移证据。
5. `DiagnosisAttributor`生成事实、假设和未知项。
6. `EvidenceProjection`把聚合证据加入第一次Qwen调用。
7. Qwen提案必须返回`evidence_refs`，Harness同时校验引用存在性和Recipe能力合同匹配。
8. 现有候选训练、LocalEvaluator和ArtifactSelector不变。
9. 第二次Qwen调用同时看到：本轮诊断事实、真实候选结果、资源和历史实验结果。
10. 选择完成后按状态机处理当前窗口：先进入隔离候选池，后续窗口确认稳定后才允许纳入活动参考；WARNING/CONFIRMED不得纳入。
11. RoundRecorder保存报告哈希、alpha账本、参考epoch、事实ID、能力匹配、预期效果、实际结果和最终选择；模型状态与漂移状态原子提交。

## 4. 历史参考更新原则

防止参考基准被漂移窗口逐步吞噬：

- `CALIBRATING`：只在隔离池积累合法稳定候选；校准量和经验p值分辨率达标后原子建立首个epoch。
- `STABLE`：当前窗口先进入隔离队列，必须由后续合法窗口确认稳定后才纳入活动参考，禁止同轮自证稳定。
- `WARNING`：冻结活动参考；当前窗口不得纳入任一稳定参考。
- `CONFIRMED`：冻结活动参考并开始独立漂移episode；旧参考完整保留。
- `RECOVERY`：用旧参考判断反向恢复，恢复窗口经连续确认后才回`STABLE`，期间不回填。
- `REBASE_PENDING`：持续新状态只进入隔离候选参考池；候选池内部稳定、数据质量合法、校准量充分后才能建立新epoch。
- `STABLE_NEW_BASELINE`：新epoch原子替换活动参考，旧epoch保留哈希、轮次和替换理由。
- 数据质量失败窗口：不得作为参考；确定性输入合同故障独立记录，不冒充统计漂移。
- 参考更新原因、来源窗口、轮次、哈希、alpha账本和原子替换链必须进入状态收据。

这是监测参考的生命周期，不恢复旧四缓冲区训练设计，也不改变现有历史训练数据使用方式。

## 5. Qwen接口修改

`request_experiment_proposal`上下文增加：

```json
{
  "drift_evidence": {
    "status": "confirmed",
    "confidence": "calibrated",
    "top_facts": [],
    "performance_impact": "observed",
    "unknowns": []
  },
  "diagnosis_evidence": {
    "hypotheses": [],
    "experiment_needs": []
  }
}
```

`ExperimentProposal`增加：

- `evidence_refs: tuple[str, ...]`；
- `expected_metric_effect: str`；
- `risk: str`。
- `expected_effect_channels: tuple[str, ...]`。

`RecipeRegistry`中的每个Recipe增加能力合同：

- `addresses_evidence_kinds`；
- `required_preconditions`；
- `incompatible_evidence`；
- `expected_effect_channels`；
- `resource_class`。

解析器必须先验证引用存在，再验证引用事实、前置条件和Recipe能力合同匹配。Qwen不需要复述全部统计量，但必须结构化说明“事实→Recipe→预期效果”。非法引用或能力不匹配均使用当前确定性父兼容fallback，并分别记录`invalid_reference`或`evidence_recipe_mismatch`；不能仅凭fact_id存在记录`diagnosis_used=true`。

## 6. RoundReceipt扩展

`brace-msi.round-receipt.v1`保持向后兼容，可增加可选字段：

```json
{
  "drift": {
    "report_sha256": "...",
    "status": "confirmed",
    "global_score": 0.0,
    "fact_ids": [],
    "calibration_method": "block_permutation_maxT",
    "minimum_empirical_p": 0.001,
    "alpha_window": 0.005,
    "alpha_spent_total": 0.005,
    "reference_epoch": 1,
    "reference_state": "warning"
  },
  "diagnosis": {
    "report_sha256": "...",
    "hypothesis_ids": [],
    "performance_impact": "unknown"
  },
  "agent_evidence": {
    "requested_refs": [],
    "validated_refs": [],
    "all_refs_valid": true,
    "evidence_recipe_match": "valid|weak|invalid|unverifiable",
    "recipe_id": "...",
    "recipe_contract_version": "...",
    "decision_rationale": "...",
    "expected_effect": {},
    "actual_result": {},
    "selection_outcome": "deploy|reject|rollback",
    "selection_reason": "..."
  }
}
```

完整报告保存在state workspace；公开/SwanLab只同步聚合指标、报告哈希和事实类别。

## 7. 正式文件修改范围

最小可验证版本预计修改：

| 文件 | 修改目的 |
| --- | --- |
| `src/brace_formal/drift.py` | 新增稳健双窗口统计、经验校准、状态和输出schema |
| `src/brace_formal/diagnosis.py` | 新增事实—假设—未知分层归因 |
| `src/brace_formal/drift_state.py` | 新增参考窗口与持续性状态原子序列化 |
| `src/brace_formal/agent.py` | 传入聚合诊断、要求并验证`evidence_refs` |
| `src/brace_formal/round_core.py` | 在TaskProfile后编排P5链并扩展收据 |
| `src/brace_formal/profile.py` | 仅在需要时补充不可逆聚合描述；不混入漂移算法 |
| `configs/formal_runtime_allowlist.json` | 仅在实现和验收通过后加入三个新正式文件 |
| `tests/competition_core/test_drift.py` | 统计量、校准、持续性和边界测试 |
| `tests/competition_core/test_diagnosis.py` | 事实/假设/未知和禁止结论测试 |
| `tests/competition_core/test_drift_integration.py` | Qwen引用、收据、恢复和失败降级测试 |

冻结`0.11.0rc1`不原地修改；实施应从新分支和新版本产生候选。

## 8. 不应修改的模块

- `contest_harness`官方SDK封装；
- checkpoint schema和`FormalModel`父链；
- `metrics.py`现有指标方向事实；
- `selection.py`ArtifactSelector；
- 预测入口和逐行输出；
- Docker正式入口；
- PyTRiO/SwanLab镜像外边界。

## 9. 失败关闭与恢复

- 状态文件损坏：保留父模型，漂移置信度降为`unavailable`，仍按现有真实训练fallback完成轮次；不得读取未来或猜测历史。
- 当前样本太少：只输出描述统计和`insufficient_sample`。
- 全常量/全缺失特征：记录数据质量事实，不进行无意义分布检验。
- Qwen忽略证据：记录无效引用并fallback；不得让文本绕过RecipeRegistry。
- Qwen引用合法但Recipe能力不匹配：记录`evidence_recipe_mismatch`并fallback，不执行该提案。
- 经验p值分辨率不足或交换性条件不满足：输出`insufficient_calibration`或BY降级，不得把未显著解释为稳定。
- alpha账本损坏或累计值不一致：漂移确认失败关闭，保留父模型并记录状态错误。
- 漂移模块异常：错误进入轮收据，不改变父、候选和历史artifact的合法集合。
- 恢复后相同state/data必须生成相同报告hash，防止重复运行改变决策。

## 10. 集成验收

1. 正式运行仍每轮产生真实父兼容候选和双阶段模型调用。
2. 无P5状态的旧workspace可以迁移为冷启动状态，不破坏既有轮次。
3. P5报告不含逐样本、原始路径、密钥或隐藏信息。
4. 未来轮数据无法进入当前窗口、校准或诊断。
5. Qwen提案引用事实ID和Recipe能力匹配可复算，非法引用或不匹配均失败关闭。
6. 关闭P5时，现有训练、评估、选择和回滚结果保持兼容。
7. P5失败不改变父checkpoint或artifact血缘。
8. 本地测试镜像先验证；正式上传镜像只有在专项、全量和容器验收通过后才加入新文件。
9. 完整无漂移流的累计alpha不超预算，运行级误报可以从状态与收据复算。
10. WARNING/CONFIRMED窗口永不进入活动参考；恢复和新基准建立均产生可追溯epoch切换证据。
11. 相同历史和预算下，诊断存在、诊断屏蔽和无关诊断替换三种输入可用于离线反事实验收；未完成该对照不得声称Qwen真正利用诊断。
