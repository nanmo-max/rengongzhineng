# BRACE-MSI 技术架构

## 1. 设计目标

系统处理的是“如何自主决定一次训练是否值得执行”，而不是为三个公开数据集分别手工刷分。BRACE-MSI围绕训练前预算决策、训练后风险门控和后续批次收益反馈构建 `[D-001]`。

## 2. 组件与边界

```text
OfficialSDKAdapter
  -> TaskBootstrap
  -> StreamRunner
  -> EvidenceRouter / DiagnosisEngine
  -> ActionPolicy / BudgetAllocator
  -> ExperimentRunner / ModelAdapter
  -> StatisticalEvaluator
  -> SafetyGate
  -> ModelRegistry / RollbackManager
  -> SwanLabLogger + PrivateAuditLog
```

### OfficialSDKAdapter

- 将官方SDK事件转换为内部事件，不预设官方调用顺序。
- 首期支持 `predict_then_feedback` 与 `labeled_train_then_predict` 两种配置 `[D-006]`。
- 同一被评分样本不得先使用标签训练再预测。

内部事件最小集合：`TaskOpened`、`TrainDataAvailable`、`PredictionRequested`、`FeedbackAvailable`、`BatchCommitRequested`、`RunFinished`。

### TaskBootstrap

优先级：官方初始模型引用 > 合法初训数据 > SDK允许的弃权/默认路径。禁止把一个任务的模型用于特征或标签空间不兼容的新任务 `[D-007]`。

### ModelAdapter

每个模型声明：`task_kind`、`supports_partial_fit`、`supports_predict_proba`、`supports_warm_start`、`supports_calibration`、`supports_serialization`。Logistic Regression和Ridge不得被当成原生增量模型 `[D-008]`。

候选模型池在正式数据确认前只作为研究决策：SGD、Logistic/Ridge、HistGradientBoosting、ExtraTrees `[D-009]`。

### EvidenceRouter与DiagnosisEngine

输入包括数据质量、协变量漂移、目标/类别分布变化、性能退化、历史遗忘、预算和动作历史。漂移不是训练的唯一触发器；性能证据可独立触发低成本候选 `[D-010]`。

### ActionPolicy与BudgetAllocator

白名单动作：`NOOP`、`RECALIBRATE`、`INCREMENTAL_UPDATE`、`REPLAY_REFIT`、`FAMILY_SWITCH`、`BOUNDED_HPO`、`ROLLBACK`。运行时禁止生成并执行任意代码 `[D-011]`。

三段式“快速修复、稳定适应、定向搜索”是升级优先级，不是每次固定菜单。至少三次真实候选事件属于宣讲要求，最终计数语义待核实 `[B-ITER-001]` `[H-003]`。

### SafetyGate

分为三层：

1. 硬约束：合法数据、资源、输出、可加载、可回滚。
2. 统计比较：稳定模型、静态基线、历史阶段和不确定性。
3. 部署决策：收益、风险、预算和后续选择价值。

整个评测流是否达到官方静态基线由最终资格判断负责，不能假装在每个在线窗口已知隐藏测试结论 `[D-012]`。

### 日志

SwanLab记录被训工业模型的公开合规训练过程；本地审计记录批次状态、决策和故障。私有逐样本数据不得写入公开项目 `[D-013]`。

## 3. 失败与降级

- 模型服务不可用：退回确定性策略。
- 统计样本不足：保留当前稳定模型。
- 候选超时/OOM/损坏：拒绝候选并回滚。
- 连续两次候选失败：进入保守模式。
- 未知B包协议：停止训练，使用SDK允许的安全路径，记录阻塞，不猜测接口。

## 4. 非目标

- 运行时自由代码生成。
- 依赖公网搜索或外部API。
- 在镜像内打包大模型或Embedding权重。
- 在正式SDK公布前写死平台名、模型名和调用顺序。
