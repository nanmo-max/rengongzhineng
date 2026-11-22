# P5 漂移监测设计

## P5-R1 修订记录（2026-11-22）

- 将“每个统计量直接参与BH”改为“特征内联合统计量校准、特征间相关性控制”的两层检验。
- 明确比较BH、BY和同步分组/时间块置换`maxT`；主方案不再假设特征或统计量独立。
- 增加经验p值分辨率、校准不足状态、运行级alpha-spending和累计误报定义。
- 将参考窗口更新改为双池状态机，补充短暂波动、恢复和持续新基准建立语义。
- 本修订只改变待实现设计，不代表正式RC已具备相应能力。

## 1. 目标与证据边界

本设计为`COMPETITION-CORE-RC-001 / brace-msi:0.11.0rc1`补充最小可验证漂移监测能力，但不修改冻结RC。核心对象是输入特征分布变化及其是否伴随模型性能变化。监测器只生成结构化证据，不训练模型、不决定部署、不读取隐藏测试标签。

必须区分：

- **观测事实**：数值分布、缺失率、标签组成或模型误差发生了可计算变化。
- **统计判断**：该变化超过历史稳定波动范围，并达到预先设置的误报控制标准。
- **工程推断**：变化可能影响模型，值得设计实验验证。
- **禁止结论**：仅凭分布变化断言设备故障、传感器损坏或工况原因。

概念漂移文献区分`p(X)`变化与`p(y|X)`变化；只有输入变化不足以证明预测关系已经改变。[Gama等人的综述](https://doi.org/10.1145/2523813)支持这一边界。

## 2. 当前任务画像

依据`docs/source_notes/OFFICIAL_TRAINING_PACKAGE_AUDIT_2026-11-11.md`，正式设计必须覆盖以下数值表格任务：

| 任务 | 类型 | 特征数 | 分组/时间结构 | 监测重点 |
| --- | --- | ---: | --- | --- |
| Gas | 六分类 | 128 | 自然气体传感器批次 | 高维传感器整体偏移、类别组成、少数类及跨批次域变化 |
| Bearing | RUL回归 | 34 | 轴承设备与严格退化时间 | 设备间工况异质性、轨迹阶段、尺度与噪声变化 |
| Engine | RUL回归 | 24 | 发动机unit与cycle | 工况设置、传感器组合、时间相关退化和误差漂移 |

正式逻辑只读取任务合同、父checkpoint、数值特征、分组/时间提示和合法标签，不按Gas/Bearing/Engine名称路由。三任务仅用于验证覆盖面。

## 3. 候选方法比较

| 方法 | 优点 | 主要问题 | 结论 |
| --- | --- | --- | --- |
| 单特征KS + 固定p值 | 非参数、实现简单、能发现形状变化 | 128维多重比较易误报；p值受样本量影响；不能直接表达效应大小 | 只作为辅助统计量，不单独触发 |
| 固定PSI阈值 | 工业界常见、易解释 | 常用0.1/0.2阈值缺少任务内校准；分箱敏感 | 不作为MVP主算法 |
| 每特征ADWIN | 在线、窗口自适应，并有误报/漏报理论界限 | 逐特征部署复杂；主要检测均值变化；高维下仍需多重控制 | 只用于全局误差或聚合漂移分数的可选序贯层 |
| MMD/深度表征检测 | 可检测多变量联合变化 | 二次计算或近似复杂；CPU、解释和阈值成本高 | MVP不采用 |
| **稳健双窗口多统计量 + 经验校准** | NumPy可实现；同时覆盖位置、尺度、形状、质量；特征级可解释；适合24/34/128维 | 需要历史稳定窗口；早期轮次置信度较低 | **推荐MVP** |

[ADWIN原论文](https://doi.org/10.1137/1.9781611972771.42)说明自适应窗口适合变化流，并提供误报与漏报界限；本设计不直接复制完整ADWIN作为高维主检测器，而把它保留为聚合分数或模型误差流的后续增强。

## 4. 推荐算法：Calibrated Robust Window Monitor

### 4.1 窗口定义

实现采用滑动窗口与历史参考窗口比较；“滑动”服从合法批次、设备组和时间顺序，不在缺少时间语义时凭JSONL行号伪造序列。

- `ReferenceWindow`：此前合法开放且被标记为稳定的历史窗口摘要，优先按设备组或连续时间块建立。
- `CurrentWindow`：本轮当前合法训练数据；若任务合同提供时间字段，可再划分为连续子窗口观察渐进变化。
- 只有历史稳定窗口参与阈值校准。已确认漂移窗口不得污染稳定基准。
- 没有时间提示时，不伪造样本顺序；只进行批次级比较。
- 参考窗口不足时返回`confidence=insufficient_history`，允许输出描述统计，但不得给出“确认漂移”。

### 4.2 每特征统计量

对特征`j`计算：

1. `missing_delta`：缺失/非有限比例差。
2. `location_shift`：中位数差除以参考稳健尺度。
3. `scale_shift`：当前IQR与参考IQR的对数比绝对值。
4. `wasserstein_shift`：一维Wasserstein距离除以参考稳健尺度。
5. `ks_distance`：两经验分布函数最大距离，仅作形状辅助证据。

稳健尺度取`max(IQR/1.349, 1.4826×MAD, numeric_floor)`。`numeric_floor`根据父checkpoint保存的特征尺度和机器精度计算，不使用跨任务固定量纲阈值。[SciPy官方说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wasserstein_distance.html)给出一维Wasserstein距离定义；正式实现可用排序后的经验CDF以NumPy实现，不新增SciPy运行依赖。[NIST说明](https://www.itl.nist.gov/div898/handbook/prc/section2/prc212.htm)指出KS基于经验CDF，有限样本临界值需要谨慎处理，因此KS不单独承担触发职责。

### 4.3 特征内多统计量合并

同一特征的位置、尺度、Wasserstein、KS和缺失率统计高度相关，禁止把它们当成五次独立检验。对特征`j`执行：

1. 使用稳定历史伪比较分布，把每个统计量转换为方向一致的标准化超阈量`Z_{j,k}`。
2. 定义特征级联合统计量`T_j=max_k(Z_{j,k})`；同时保留是哪一类统计量达到最大值，供诊断解释。
3. 以同一次同步分组/时间块置换重算全部统计量和`T_j`。置换必须移动完整样本行并保留任务合同声明的组或连续块，不得逐列独立打乱。
4. 使用加一校正的经验尾概率：`p_j=(1 + count(T_j^null >= T_j^obs))/(B+1)`，经验p值不得为0。

`max`联合统计量用于发现“任一统计维度明显变化”，效应量门仍用于过滤统计显著但工程意义很小的变化。若任务结构不满足可交换性，不能把置换p值表述为已校准证据，必须进入后述保守降级。

### 4.4 特征间多重检验：BH、BY与联合置换

三种方法的适用边界如下：

| 方法 | 统计依据 | 相关性条件 | 本项目定位 |
| --- | --- | --- | --- |
| BH | 控制FDR | 独立或满足特定正相关结构 | 只有依赖结构有数据或结构依据时使用，不作默认 |
| BY | 控制FDR | 任意依赖，代价是更保守 | 无法构造合法置换时的保守fallback |
| 同步块置换`maxT` | 以联合零分布控制窗口内FWER并给出调整后特征p值 | 需要合法的可交换性/块交换性；应尽量保持跨特征相关性 | 满足条件时的主方案 |

BH原始方法见[Benjamini与Hochberg 1995](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)；BY对任意依赖的保守修正见[Benjamini与Yekutieli 2001](https://doi.org/10.1214/aos/1013699998)。同步置换借鉴Westfall–Young类联合校准；其有效性依赖交换性等条件，不能无条件宣称适用于任意时序数据，可参见[Meinshausen、Maathuis与Bühlmann 2011](https://doi.org/10.1214/11-AOS946)。

决策顺序固定为：

1. 有合法分组/时间块置换时，以同步`maxT`联合零分布作为主校准。
2. 无法证明交换性时使用BY；记录`calibration_method=by_fallback`和保守性限制。
3. 只有预注册的依赖诊断或任务结构支持BH条件时才能使用BH，并记录依据。
4. 无论使用哪种校准，特征必须同时满足调整后显著性门和预注册效应量门。

### 4.5 有限校准样本与经验p值分辨率

经验p值最小分辨率为`1/(B+1)`。置换次数或稳定伪比较数不足时，“未显著”不能解释为“无漂移”。设计要求：

- 目标经验分辨率不高于本窗口正式alpha的十分之一；因此`B >= ceil(10/alpha_window)-1`。
- CPU允许时优先使用不少于999次同步置换；如果窗口alpha很小，必须按上述公式增加次数或降级为`insufficient_calibration`。
- 历史稳定窗口不足以生成所需独立/块级伪比较时，输出描述性效应量和`confidence=insufficient_calibration`，禁止输出`CONFIRMED`统计结论。
- 校准预算、实际`B`、最小可达p值、置换单位和交换性假设必须写入报告。

### 4.6 跨窗口累计误报控制

必须区分三个概念：

- `single_window_fpr`：一次合法监测窗口被错误标为统计异常的概率。
- `confirmation_fpr`：连续性规则把短暂异常错误升级为`CONFIRMED`的概率。
- `run_level_false_alarm`：整个监测周期至少一次错误确认的概率。

连续两次确认只能降低工程误报，不能替代运行级统计保证。正式确认使用预注册alpha-spending：

- 已知最多`T`次正式监测时，可用等额`alpha_t=alpha_run/T`或预注册权重`w_t`，并满足`sum(w_t)<=1`。
- 监测上限未知时使用可求和权重，例如`w_t=1/[t(t+1)]`，`alpha_t=alpha_run*w_t`。
- 在每次检验有效的前提下，Bonferroni/并集界给出`P(运行期至少一次错误确认)<=sum(alpha_t)<=alpha_run`，不要求不同窗口相互独立。
- `WARNING`可使用单独的探索阈值，但不能作为正式漂移确认或消耗后续训练预算的唯一依据；只有达到本轮正式alpha且满足持续性规则才进入`CONFIRMED`。

alpha-spending思想参考[Lan与DeMets 1983](https://doi.org/10.1093/biomet/70.3.659)。本项目仍需用完整无漂移流实测运行级误报，而不能只报告单窗口p值。

### 4.7 历史参考窗口状态机与恢复

采用“不可变活动参考池 + 隔离候选参考池”的双池设计，防止被缓慢漂移污染：

| 状态 | 活动参考池 | 当前窗口处理 | 转移条件 |
| --- | --- | --- | --- |
| `CALIBRATING` | 尚未形成 | 只积累隔离校准窗口、输出描述统计 | 样本量、块数和经验p分辨率达标后原子建立首个参考epoch |
| `STABLE` | 只读用于比较 | 当前窗口先进入隔离队列；至少经后续合法窗口确认稳定后才可纳入 | 异常证据进入`WARNING` |
| `WARNING` | 冻结 | 不纳入活动参考；保留为事件证据 | 证据消失进入`RECOVERY`；满足正式alpha与持续性进入`CONFIRMED` |
| `CONFIRMED` | 冻结 | 不纳入旧参考；开始独立漂移episode | 回到旧分布进入`RECOVERY`；持续形成新状态进入`REBASE_PENDING` |
| `RECOVERY` | 继续使用旧参考 | 恢复窗口只进隔离队列 | 连续合法恢复窗口后回`STABLE`；再次异常则回`WARNING/CONFIRMED` |
| `REBASE_PENDING` | 旧参考仍保留 | 仅在候选参考池收集新稳定状态，绝不混入旧池 | 候选内部稳定、校准量充足且数据质量合法后建立新epoch |
| `STABLE_NEW_BASELINE` | 新epoch原子替换为活动参考；旧epoch保留哈希和审计 | 按`STABLE`规则继续延迟纳入 | 后续异常重新进入`WARNING` |

恢复与重建语义：

- 单次短暂波动：`WARNING → RECOVERY → STABLE`，活动参考不变。
- 连续多次短暂波动：每次均不得回填活动参考；累计频率作为独立风险证据，但不自动宣称新基准。
- 缓慢漂移后反向恢复：旧参考始终冻结保留，恢复窗口经连续确认后重新使用旧epoch。
- 持续漂移：只有新候选池内部稳定、数据质量正常、校准分辨率充分，且可用时模型性能也稳定，才原子建立新基准。

严禁把`WARNING`、`CONFIRMED`、未完成恢复确认或数据质量失败窗口回填到活动参考。每个参考epoch保存来源窗口哈希、建立原因、校准配置和替换链；不允许事后回填。

严重输入契约破坏属于确定性数据质量故障，不计作统计漂移确认，也不消耗统计alpha，但必须单独失败关闭。

若标签合法可用，额外监测父模型逐样本损失或误差流。该性能流可使用ADWIN或相同的序贯校准，独立输出`performance_drift`证据；输入漂移和性能漂移不得混为同一p值。

### 4.8 聚合与特征贡献

每个特征的贡献由通过门后的标准化超阈量计算：

```text
excess_j = max(0, calibrated_score_j - calibrated_threshold_j)
contribution_j = excess_j / sum(excess)
```

全局漂移分数同时保存`max_score`和`top_k_mean`。不能只用所有特征平均值，因为Gas的少数关键传感器变化可能被128维平均稀释。`top_k`由特征数的平方根上限生成，并在输出中记录实际值，不按任务名称设置。

## 5. 结构化输出

建议新增不可变`DriftReport`：

```json
{
  "format": "brace-formal.drift-report.v1",
  "status": "stable|warning|confirmed|insufficient_history",
  "reference_scope_sha256": "...",
  "current_scope_sha256": "...",
  "sample_count": 0,
  "history_window_count": 0,
  "global_score": 0.0,
  "calibration_method": "block_permutation_maxT|by_fallback|bh_conditional",
  "permutation_count": 0,
  "minimum_empirical_p": 1.0,
  "alpha_run": 0.05,
  "alpha_spent": 0.0,
  "alpha_window": 0.0,
  "reference_epoch": 0,
  "reference_state": "calibrating|stable|warning|confirmed|recovery|rebase_pending|stable_new_baseline",
  "performance_drift": {
    "available": false,
    "status": "unknown",
    "score": null
  },
  "features": [
    {
      "feature_index": 0,
      "fact_id": "drift.feature.0.location",
      "location_shift": 0.0,
      "scale_shift": 0.0,
      "wasserstein_shift": 0.0,
      "ks_distance": 0.0,
      "missing_delta": 0.0,
      "empirical_p": 1.0,
      "adjusted_p": 1.0,
      "selected": false,
      "contribution": 0.0
    }
  ],
  "limitations": []
}
```

禁止包含逐样本特征、标签、原始路径或可逆数据。完整报告写入本地轮收据，给Qwen的版本仅保留聚合值、前若干贡献特征和事实ID。

## 6. 任务适配原则

- **分类**：输入特征监测始终可用；标签开放后可监测类别比例和父模型0/1错误或对数损失。类别比例变化只标记`label_composition_shift`，不能自动等价为概念漂移。
- **回归**：输入特征监测始终可用；标签开放后监测目标分布、绝对误差和平方误差。Bearing/Engine按设备组与连续块校准，不能随机打散时间轨迹建立“稳定”基准。
- **未知任务**：依赖父checkpoint的特征路径、任务类型、主指标方向、`group_hints`和`time_hints`；信息不足则降低置信度，不按数据集名称回退。

## 7. 计算成本估计

设参考样本`n_r`、当前样本`n_c`、特征数`d≤128`。主要成本为每特征排序，约`O(d(n_r log n_r+n_c log n_c))`；描述统计内存约`O(d+n_r+n_c)`，不构造`d×d`协方差矩阵。

加入同步置换后，朴素成本近似乘以`B`，不能继续承诺所有场景都在1秒内完成。实现应复用排序、批量计算置换统计并允许在不改变预注册alpha分辨率的前提下缓存稳定零分布。规划目标为4核CPU单窗口数秒到数十秒、峰值附加内存低于1GiB；该数值是工程估计，不是已验证结果，MVP必须记录真实CPU、墙钟、RSS、实际`B`和p值分辨率后才能进入正式镜像。

## 8. 明确不做

- 不引入深度漂移检测器、自动编码器或大模型来计算漂移。
- 不使用固定PSI阈值冒充跨任务通用门。
- 不用单次显著性检验直接触发模型更新。
- 不用输入漂移断言设备故障。
- 不读取公开validation、XJTU密封或隐藏数据进行阈值选择。
- 不改变现有checkpoint、训练、选择、回滚或预测协议。
