# BRACE-MSI P3 自适应优化算法竞争力设计

> 状态：`DESIGN_ONLY`。本文件只定义公平对照、历史反馈和验收协议；没有运行新训练、调用PyTRiO、读取密封/隐藏数据或修改冻结RC。

## 1. 研究问题与边界

核心问题不是“Qwen能否返回合法JSON”，而是：在相同父checkpoint、数据可见性、候选训练数和训练资源下，带详细历史反馈的Qwen搜索是否比随机搜索和TPE更快找到更好的父模型兼容候选。

冻结边界：

- `COMPETITION-CORE-RC-001 / brace-msi:0.11.0rc1`及其归档保持不变。
- XJTU密封集永久关闭；官方隐藏数据和平台试运行均不使用。
- A/B/C `public/validation.jsonl`已有历史暴露，本研究不得读取它们进行选择或确认。
- 本研究代码、Optuna和PyTRiO只进入研究分支/研究环境，不进入正式镜像白名单。
- 所有性能结论先标记为本地开发证据；没有新独立数据时，不宣称隐藏泛化或官方优势。

## 2. 当前代码与证据审计

| 审计项 | 当前事实 | 设计影响 |
| --- | --- | --- |
| 统一候选执行 | `RecipeRegistry.resolve`、`execute_recipe`、`evaluate`和`select_artifact`已存在 | 四个优化臂必须复用同一执行器，不复制训练逻辑 |
| 历史输入 | `round_core._history_summary`只给轮数、保留轮次、官方历史条数和样本数 | 不能据此证明Qwen从上一轮结果学习 |
| 50轮记录 | 五个任务画像各10轮，50/50具备提案、参数、执行、父/候选指标、资源和选择字段 | 可复用收据schema，但不能把本地替身称为真实Qwen |
| 实际策略多样性 | 50轮仅出现`native_current`首轮和`native_replay`后九轮 | 50轮是协议验收，不是自适应竞争力证据 |
| 随机/TPE对照 | 仓库不存在随机搜索或TPE同预算实现和结果 | 必须新增共同优化器接口和公平预算账本 |
| TPE依赖 | Optuna 5.1.0为Python 3.10+、MIT许可，提供`TPESampler` | 仅作为研究可选依赖，固定版本且不进入正式镜像 |

实际50轮收据抽查结果：`missing_proposal=0`、`missing_params=0`、`missing_execution=0`、`missing_parent_metrics=0`、`missing_candidate_metrics=0`、`missing_resources=0`、`missing_selection=0`。这说明数据基础足够，但搜索策略证据不足。

## 3. 备选实现与选择

### 方案A：分别扩写现有脚本

为随机、TPE和Qwen各写一条实验路径。实现最快，但训练、预算和评价容易产生不一致，不能形成可信公平对照。拒绝。

### 方案B：共享TrialRunner与可插拔Optimizer（采用）

所有臂共享一套搜索空间、训练器、评价、选择器、数据划分和预算账本，仅替换`suggest/observe`策略。改动集中在研究模块，不触碰正式运行核，且可以直接做历史反馈消融。

### 方案C：完全交由Optuna编排

随机/TPE较省代码，但Qwen历史、平台父链和现有收据需要被强行映射到Optuna Study，且容易让Optuna存储成为新的事实源。只在方案B的TPE适配器内部使用Optuna，不让它接管实验生命周期。

## 4. 公平对照框架

### 4.1 主要实验臂

| 臂 | 提案方式 | 训练预算 |
| --- | --- | --- |
| A 静态 | 不训练，只在完全相同的评价作用域评估官方父模型 | 0候选；作为参考，不参与“搜索效率”比较 |
| B Random | NumPy `Generator`从共同条件搜索空间均匀采样 | 与C/D相同 |
| C TPE | Optuna `TPESampler`，经典单目标独立TPE | 与B/D相同 |
| D Qwen-History | Qwen读取完整脱敏试验历史后选择配置 | 与B/C相同 |

必要消融：`D0 Qwen-No-History`使用完全相同的任务画像、搜索空间和预算，但历史列表置空。它只用于回答“详细历史是否有效”，不替代四组主对照。

### 4.2 共同接口

```text
Optimizer.suggest(SearchContext) -> TrialSuggestion
TrialRunner.execute(TrialSuggestion) -> TrialObservation
Optimizer.observe(TrialObservation) -> None
```

`TrialRunner`唯一负责：解析recipe、计算计划成本、从同一父模型克隆候选、训练、同作用域评价、确定性选择、资源测量和写收据。优化器不能直接接触数据文件、checkpoint路径或部署API。

### 4.3 共同搜索空间

所有搜索臂看到完全相同的离散条件空间：

- 共同：`epochs ∈ {1,2,3}`；`learning_rate_multiplier ∈ {0.3,1.0,3.0}`。
- 分类recipe：`native_current`、`native_replay`、`class_weighted_ce`、`class_balanced_sample`、`averaged_native`。
- 回归recipe：`native_current`、`native_replay`、`regression_mse`、`regression_huber`、`regression_asymmetric`、`averaged_native`。
- `averaged_native`：`parent_average_alpha ∈ {0.10,0.25,0.50}`。
- `regression_huber`：`delta ∈ {0.5,1.0,2.0}`。
- `regression_asymmetric`：`overprediction_weight=1.0`，`underprediction_weight ∈ {1.0,2.0,4.0}`。

这些值只属于P3研究预算，不成为正式Harness或官方协议硬限制。非法组合必须在训练前拒绝，不能静默修正后仍归因给原优化器。

### 4.4 TPE配置

研究依赖固定为`optuna==5.1.0`，只写入独立研究锁文件。`TPESampler(seed=paired_seed, n_startup_trials=3, n_ei_candidates=24, multivariate=False)`；前三次为记录清楚的随机启动，第4次起才计为TPE建议。目标仅使用有向主指标，不把CPU、Token等拼成自创官方总分；资源作为共同预算和次要结果报告。

## 5. 两阶段实验设计

### 5.1 阶段一：单任务可行性探针

优先选择C Engine，因为官方train具有大量完整`unit`分组，能按unit构造比A/B更稳定的训练内部隔离。该选择不是因为C更容易获得正结果，而是因为它最适合检验优化器本身。

- 数据：只读C `public/train.jsonl`及官方初始checkpoint；`public/validation.jsonl`读取0次。
- 分组：按完整unit用固定哈希分配；20% unit为一次性外层确认，80%为搜索池；同一unit不得跨边界。
- 内层：搜索池构造3个固定group folds；一个“候选配置”在3折上分别训练并汇总，物理训练数必须记录。
- 配对种子：`20261122`。
- B/C/D/D0各6个完成候选配置；每臂最多18次物理训练。
- TPE必须至少包含3个startup和3个真正的TPE建议。
- 所有臂使用4核、8GB环境；共同预算同时核对候选数、物理训练数和标准化训练工作量。

标准化训练工作量：

```text
work_units = epochs × actual_training_samples / current_update_samples
```

历史Replay和类平衡导致的实际样本扩张因此会真实消耗更多预算。阶段一每个优化臂的工作量上限为12；静态臂为0。若Qwen没有有效真实调用收据、提案非法或回退到本地替身，则D臂判为`INVALID_AGENT_EVIDENCE`，不进入性能排名。

阶段一只回答链路与辨别能力，不形成三任务竞争力结论。

### 5.2 阶段二：正式本地对照

只有阶段一全部协议门通过才执行：

- A/B/C分别运行，配对种子为`20261122/20261123/20261124`。
- B/C/D每个“任务×种子”最多10个完成候选配置。
- 完整预算由阶段一机器收据确定，公式为：

```text
full_work_budget = ceil((10 / 6) × max(valid_pilot_arm_consumed_work_units))
full_cpu_budget_seconds = ceil(1.25 × max(valid_pilot_arm_cpu_seconds))
```

- 每个任务的所有优化臂获得同一个由公式生成的预算；不能根据某臂中途成绩追加预算。
- 外层确认只在该任务全部优化臂及其选模规则冻结后各读取一次，不反馈下一次提案。
- A按类别分层的固定哈希组、B按完整bearing/轨迹组、C按完整unit分组；禁止JSONL行随机切分。

由于官方父checkpoint已经使用过公开train，阶段二只能估计“同数据源上的优化器相对效率”，不能当作全新任务泛化证明。真正外部泛化仍需未来新增合法数据或官方评测。

## 6. Qwen详细历史反馈

### 6.1 输入历史schema

每条历史只含聚合、不可逆字段：

```json
{
  "trial_index": 2,
  "recipe_id": "regression_huber",
  "requested_parameters": {},
  "resolved_parameters": {},
  "execution_status": "completed",
  "parent_metrics": {},
  "candidate_metrics": {},
  "signed_primary_gain": 0.0,
  "worst_fold_gain": 0.0,
  "selection": "candidate|parent",
  "rejection_reason": null,
  "failure_category": null,
  "cpu_seconds": 0.0,
  "wall_seconds": 0.0,
  "peak_rss_bytes": 0,
  "work_units": 0.0,
  "delayed_gain": null,
  "scope_sha256": "..."
}
```

不得包含逐样本特征、标签、ID、原始路径、密钥或可逆数据摘要。当前最多10个trial，全部历史均传入，不做会改变证据的摘要截断。

### 6.2 Qwen输出schema

Qwen每轮必须返回：

1. `previous_result_analysis`：分析最近一次结果；首轮必须显式为无历史。
2. `recipe_id`和`parameters`：命中共同搜索空间。
3. `strategy_change_reason`：本轮相对上一轮改变或保持的依据。
4. `expected_gain`和`risks`：预期收益方向及主要风险。
5. `budget_request`：计划work units及其依据。

同时保留`hypothesis`与`rationale`。Harness以解析后的结构化值执行，不能从自然语言重新猜参数。

### 6.3 真实调用证据

- 官方宿主调用保存真实`call_id`。
- 本地PyTRiO SDK 0.2.9至少保存真实`SamplingClient.sampling_run_cuid`、本地请求关联ID、请求/响应SHA-256、输入/输出Token和延迟。
- 若SDK成功响应不公开单次服务端request ID，字段必须为`null`并明确`not_exposed_by_sdk`；禁止生成字符串冒充真实服务ID。
- D臂不得使用`native_replay`或任何确定性替身填补失败后再声称Qwen实验成功。

## 7. 结果指标与分析

主结果：

- 固定候选预算下，冻结选中模型在外层确认上的官方主指标。
- `best-so-far`有向主指标曲线的面积（AUC），反映搜索效率。

次要结果：

- 达到随机/TPE最终性能所需候选数、work units和CPU时间；
- 每轮父/候选有向增益；
- 无效训练比例：候选未优于同作用域父模型或被拒绝；
- 策略重复率：完全相同的规范化配置重复次数/有效建议数；
- 提案非法、训练失败、部署拒绝和回滚率；
- CPU、墙钟、RSS、checkpoint大小、Qwen Token和费用；
- 三个配对种子的中位数、范围和逐种子配对差。

不把三个种子伪装成足够统计功效。报告效应量、配对差和不确定性；任何显著性结论必须有按设备/unit/批次进行的组级重采样支持。

## 8. 验收和停止条件

### 8.1 协议验收

- 所有优化臂父checkpoint、搜索空间、数据哈希、fold、种子、候选数和预算一致。
- TPE至少产生一次基于既有观察的非startup建议。
- Qwen每轮具有真实远程收据，且第2轮起提示确实包含上一轮参数、指标、选择、成本和失败信息。
- `Qwen-No-History`除history字段外与D臂完全一致。
- 任何路径访问`public/validation`、XJTU密封或隐藏数据，整项实验立即无效。

### 8.2 自适应能力判据

只有同时满足以下条件，才可写成“详细历史带来收益”：

- D相对D0的best-so-far AUC配对差中位数为正；
- 至少2/3配对种子中D优于D0；
- 外层确认主指标不因启用历史而系统性退化；
- 不能由更高候选数、work units、CPU或不同搜索空间解释。

只有Qwen在固定预算最终主指标或best-so-far AUC上对Random和TPE均形成可复核优势，才能声称搜索竞争力。否则如实结论为“未优于传统HPO”或“历史反馈无额外价值”。

### 8.3 工程停止条件

- 冻结RC、原始数据或历史证据哈希发生变化；
- 任一臂数据划分、训练器、评价器或预算口径不同；
- Qwen真实调用ID/服务标识与Token收据缺失；
- TPE依赖进入正式镜像白名单；
- 阶段一协议失败仍继续扩大到三任务；
- 为获得正结果而查看外层确认后修改搜索空间、提示、预算或选模规则。

## 9. 研究风险

1. 公开train已被官方父模型使用，外层确认只是优化器隔离，不是模型真正未见数据。
2. 十次试验对TPE仍偏少，结果可能主要受startup影响；因此明确设置3次startup并报告每次建议来源。
3. Qwen额外Token和墙钟可能抵消性能收益，必须进入同一资源报告。
4. Qwen对自然语言历史的优势可能来自更丰富上下文而非“学习”；D0消融只回答历史条件效应，不宣称参数更新式学习。
5. 多次开发可能过拟合当前任务；没有新独立数据时不晋级正式RC。

## 10. 参考依据

- 当前实现：`src/brace_formal/{round_core,agent,recipes,history}.py`。
- 当前机器证据：`docs/results/COMPETITION-CORE-RC-001.md`及仓库外50轮收据。
- Optuna官方`TPESampler`文档与MIT许可证：<https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.TPESampler.html>、<https://github.com/optuna/optuna/blob/master/LICENSE>。
- Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. arXiv:2609.00065. <https://doi.org/10.48550/arXiv.2609.00065>。
