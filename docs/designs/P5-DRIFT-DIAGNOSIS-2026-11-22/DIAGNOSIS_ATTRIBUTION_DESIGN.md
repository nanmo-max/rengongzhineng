# P5 诊断归因设计

## P5-R1 修订记录（2026-11-22）

- 将“引用正确fact_id”从充分条件降为必要条件。
- 为`RecipeRegistry`增加机器可校验的证据能力合同，并定义证据—Recipe匹配失败的降级行为。
- 补全“引用事实—选择Recipe—理由—预期—实际结果—采用/拒绝”的闭环收据。
- 增加诊断屏蔽、无关证据替换等反事实验证，避免把格式合规误写成Qwen真正利用诊断。
- 本修订只更新设计，不产生真实Qwen调用或效果证据。

## 1. 目标

诊断模块把`DriftReport`转换为可验证、可供实验设计使用的证据，而不是生成看似合理的故障故事。输出必须回答：

1. 哪些特征变化；
2. 变化类型和幅度；
3. 哪些特征贡献最大；
4. 是否同时观察到模型性能变化；
5. 哪些结论只是可能解释；
6. 下一轮值得验证哪类优化假设。

诊断模块不训练模型、不选择最终artifact、不直接触发部署或回滚。

## 2. 三层结论合同

### 2.1 `FACT`：统计事实

只有由当前合法数据和历史稳定摘要直接计算的内容可以进入事实层：

- 数据质量变化；
- 特征位置、尺度或分布形状变化；
- 类别/目标组成变化；
- 父模型误差或主指标变化；
- 变化持续时间、效应量、FDR结果和特征贡献。

每个事实拥有稳定`fact_id`、作用域哈希、计算方法、数值和置信度。

### 2.2 `HYPOTHESIS`：待验证归因

诊断器根据事实生成有限类别的可能解释：

| 诊断类型 | 必要证据 | 允许表达 | 禁止表达 |
| --- | --- | --- | --- |
| `data_quality_shift` | 缺失、非有限、常量化或范围异常 | 输入质量改变，可能影响模型 | 传感器已经损坏 |
| `location_shift` | 稳健位置统计持续改变 | 特征中心发生漂移 | 工况温度变化已被确认 |
| `scale_or_noise_shift` | IQR/MAD/方差及形状证据改变 | 波动或噪声水平可能改变 | 设备磨损已被确认 |
| `shape_shift` | Wasserstein/KS变化但位置/尺度不足以解释 | 分布形状改变 | 已知具体物理原因 |
| `label_composition_shift` | 合法标签组成变化 | 类别/目标构成变化 | 分类边界一定改变 |
| `covariate_shift_without_observed_impact` | `p(X)`变化、父模型性能未显著变化 | 当前变化尚未显示性能影响 | 模型无需更新且未来安全 |
| `performance_drift` | 同口径父模型误差或指标持续恶化 | 模型当前表现下降 | 输入漂移就是唯一原因 |
| `possible_conditional_drift` | 性能恶化，且仅输入边际变化不能解释或输入未明显变化 | `p(y|X)`可能改变，需实验验证 | 概念漂移已经被因果证明 |

### 2.3 `UNKNOWN`：无法判定

以下情况必须明确写成未知：

- 历史窗口不足；
- 评价作用域不可比；
- 标签尚未合法开放；
- 变化只出现一次；
- 多个解释均与数据一致；
- 分组/时间字段缺失，无法排除工况组成变化。

## 3. 特征变化定位

### 3.1 排名

按`contribution`排序输出前若干特征，同时保存全部聚合统计到本地收据。排名由超出稳定阈值的效应量决定，而不是由p值大小决定，避免样本量大的微小变化占据首位。

### 3.2 特征组

若任务合同或父checkpoint提供合法特征组，只按这些声明聚合；不得从数据集名称推测“传感器组”“工况设置”等语义。组贡献为组内特征超阈量之和，并同时保留组内最大单特征，防止大组天然占优。

### 3.3 共变模式

MVP不计算完整高维因果图。只报告：

- 多个特征是否在同一窗口共同超过门；
- 变化方向是否一致；
- 是否集中在同一已声明特征组；
- 是否与数据质量或性能证据同步出现。

这属于共现证据，不是因果归因。

## 4. 模型影响证据

### 4.1 可用标签时

用父模型在本轮合法validation或当前反馈数据上计算：

- 分类：主指标、Accuracy、按类错误率、可用时的逐样本损失；
- 回归：主指标、MAE、平方误差、任务合同声明的NASA等辅助指标；
- 残差位置、尺度和尾部变化；
- 历史指标仅在任务合同、指标定义和评价作用域指纹可比时参与数值趋势。

若作用域不同，历史指标只作上下文，不计算“下降百分比”。当前父/候选比较继续由现有`LocalEvaluator/ArtifactSelector`负责。

### 4.2 无标签时

只能报告输入漂移和数据质量。`performance_impact.status`必须是`unknown`，不得根据输入距离推算准确率或RMSE损失。

### 4.3 证据组合

| 输入漂移 | 性能漂移 | 诊断输出 |
| --- | --- | --- |
| 否 | 否 | `stable_observed` |
| 是 | 否 | `covariate_shift_without_observed_impact` |
| 否 | 是 | `possible_conditional_or_unobserved_shift` |
| 是 | 是 | `drift_with_observed_model_impact`，仍不声称物理故障原因 |
| 任意 | 未知 | 保留输入事实，模型影响为`unknown` |

## 5. 结构化输出

建议新增`DiagnosisReport`：

```json
{
  "format": "brace-formal.diagnosis-report.v1",
  "diagnosis_id": "sha256:...",
  "drift_status": "confirmed",
  "facts": [
    {
      "fact_id": "drift.feature.17.scale",
      "kind": "scale_shift",
      "feature_index": 17,
      "effect": 1.42,
      "contribution": 0.31,
      "confidence": "calibrated"
    }
  ],
  "hypotheses": [
    {
      "hypothesis_id": "diagnosis.scale-noise.1",
      "kind": "scale_or_noise_shift",
      "supports": ["drift.feature.17.scale"],
      "contradicts": [],
      "claim_strength": "possible",
      "requires_validation": true
    }
  ],
  "performance_impact": {
    "status": "observed|not_observed|unknown",
    "scope_comparable": false,
    "metric_evidence": []
  },
  "experiment_needs": [
    {
      "need_id": "experiment.robust-current-data",
      "supported_by": ["diagnosis.scale-noise.1"],
      "objective": "test whether a robust parent-compatible update improves the current legal metric"
    }
  ],
  "unknowns": [],
  "prohibited_claims": ["physical_failure_not_established"]
}
```

## 6. 从诊断到优化决策

诊断器只生成`experiment_needs`，不指定最终recipe。映射原则如下：

| 诊断证据 | 可建议给Qwen验证的实验方向 | 不允许自动执行的结论 |
| --- | --- | --- |
| 数据质量变化 | 父状态兼容的清洗/缺失处理、输入契约检查 | 自动部署新模型 |
| 类别组成变化 | 类权重或平衡采样候选 | 一定存在类别概念漂移 |
| 尺度/噪声变化 | 稳健损失、当前数据续训、合法标准化实验 | 传感器损坏 |
| 持续协变量漂移但性能稳定 | 低成本候选或保守实验，记录而非强制更新 | 无需任何实验 |
| 性能漂移且输入变化弱 | 回放/稳健损失/有界参数搜索，验证可能的条件变化 | 已证明`p(y|X)`改变 |
| 历史实验连续失败 | 换用不同机制的注册Recipe | 任意代码修改 |

Qwen仍只能从`RecipeRegistry`选择父checkpoint兼容实验。Harness完成训练与评估；`ArtifactSelector`继续核对指标事实；诊断结果不能绕过现有准入或回滚逻辑。

## 7. 如何证明Qwen真正使用了诊断结果

仅把报告塞入prompt不构成使用证据。建议扩展实验提案schema，要求Qwen返回：

```json
{
  "recipe_id": "...",
  "parameters": {},
  "evidence_refs": ["drift.feature.17.scale", "diagnosis.scale-noise.1"],
  "hypothesis": "...",
  "expected_metric_effect": "...",
  "risk": "..."
}
```

Harness必须验证：

1. `evidence_refs`全部来自本轮合法`DriftReport/DiagnosisReport`；
2. 引用事实的`kind`、置信度和前置条件与选择Recipe的能力合同匹配；
3. 下一轮历史摘要包含“引用事实—Recipe—参数—决策理由—预期效果—真实结果—采用/拒绝原因”；
4. Qwen若忽略全部高置信证据或引用不存在ID，提案标记为不可解释并使用确定性兼容备用实验；
5. 记录`requested_evidence_refs`和`validated_evidence_refs`，不能用自然语言声称已利用证据。

### 7.1 Recipe能力合同

每个注册Recipe必须提供机器可读能力合同：

```json
{
  "recipe_id": "robust-current-update.v1",
  "addresses_evidence_kinds": ["scale_shift", "shape_shift"],
  "required_preconditions": ["labels_available", "parent_compatible"],
  "incompatible_evidence": ["input_contract_failure"],
  "expected_effect_channels": ["reduce_tail_error", "improve_worst_group"],
  "resource_class": "low"
}
```

Harness计算`evidence_recipe_match`：

- `valid`：至少一个高置信引用事实属于Recipe支持范围，全部硬前置条件满足，且不存在禁止证据。
- `weak`：引用事实相关但置信度或前置条件不足；允许作为低优先级探索，但必须明确风险。
- `invalid`：引用事实与Recipe能力无关、前置条件不满足或存在禁止证据；不得执行，转为父兼容fallback。
- `unverifiable`：能力合同或诊断证据缺失；不能声称“诊断驱动”。

正确fact_id只证明引用可追溯，不能证明选择与证据相关。若Qwen引用“缺失率上升”却选择只处理类别不平衡的Recipe，仍应判为`invalid`。

### 7.2 完整证据—实验—结果账本

每轮至少记录：

1. `cited_facts`：引用事实、效应量、校准状态和作用域哈希；
2. `selected_recipe`：Recipe ID、精确参数和能力合同版本；
3. `decision_rationale`：结构化说明为何该Recipe对应这些事实；
4. `expected_effect`：预期改善的指标、误差切片或资源维度，以及失败风险；
5. `actual_training_result`：父/候选指标、分组指标、CPU、墙钟、RSS、模型大小和失败信息；
6. `selection_outcome`：部署、拒绝或回滚及其数值依据；
7. `relevance_status`：`valid|weak|invalid|unverifiable`，由Harness而非Qwen自行声明。

### 7.3 使用有效性验证

证明Qwen真正使用诊断至少需要三层证据：

1. **结构合规**：引用存在且能力合同匹配。
2. **行为敏感性**：在相同历史、预算和候选集合下，比较`Qwen-With-Diagnosis`、屏蔽诊断和替换为无关诊断；策略或参数应对相关事实作出可解释变化，而不是始终返回同一Recipe。
3. **结果关联**：匹配的Recipe产生预期方向结果，或失败后历史明确改变下一轮选择；负结果也必须保留。

后续验证应比较`Qwen-With-Diagnosis`与`Qwen-Without-Diagnosis`，并增加`Irrelevant-Diagnosis`反事实，在相同预算下观察策略变化率、重复率、无效训练率和最终指标。单次正确引用、一次正向训练或自然语言解释均不能单独证明诊断带来收益；未完成对照前只能声称“接口已接入并完成匹配校验”。

## 8. 失败与降级

- 漂移报告不可用：诊断输出`insufficient_evidence`，不编造归因。
- 标签不可用：模型影响为`unknown`。
- 多个假设同样可解释：全部保留并降低置信度，由实验区分。
- Qwen输出非法引用：记录失败，使用已有确定性训练fallback。
- Qwen引用合法但Recipe能力不匹配：记录`evidence_recipe_match=invalid`，不得执行该提案，使用父兼容fallback。
- 诊断与指标事实冲突：指标事实优先；诊断只作解释与实验假设。
- 任何诊断失败都不能污染父checkpoint、历史稳定模型或现有回滚链。

## 9. 最小验收

1. 所有结论可追溯到事实ID和作用域哈希。
2. 受控合成数据上能区分位置、尺度、质量和形状变化。
3. 无标签时不输出性能已受影响。
4. 不输出设备故障等物理因果结论。
5. Qwen提案必须引用有效事实ID并通过Recipe能力合同校验，且完整证据—结果链可在轮收据复算。
6. 诊断模块不直接调用训练、部署或回滚接口。
7. 诊断屏蔽与无关证据反事实能够区分“格式引用”与“行为确实受诊断影响”。
