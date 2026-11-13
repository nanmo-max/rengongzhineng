# BRACE-MSI 技术架构

## 0. 当前正式增量：受控双闭环（D-052）

详细规格以 [`superpowers/specs/2026-11-13-controlled-dual-loop-design.md`](superpowers/specs/2026-11-13-controlled-dual-loop-design.md) 为准。十个批次是十次决策事务；执行层候选和策略层收益学习相互分离。每轮固定为稳定预测提交、合法反馈、证据分析、0至2候选、门控、原子历史提交，第二候选不能预先排队。

数据面采用四种互斥用途：Anchor只评估，Update供当前训练，Gate供当前候选门控且本轮永不训练，Replay只包含已完成一轮隔离的历史合法训练样本。预处理器必须拟合候选真实训练集合Update或Update+Replay。RuntimeAdapter是唯一外部数据入口，训练子进程只获得manifest列出的物化文件，不获得官方源根或未来批次。

控制面新增每任务`ActionValueTable`、性能—成本Pareto排序和一轮影子前任配对收益。Qwen只在证据触发时提出结构化动作或受限纯函数插件；预算、数据能力、SafetyGate、部署和回滚始终由确定性核心裁决。

## 1. 设计目标

系统处理的是“如何让Agent提出有价值的任务专属实验，并由确定性Harness判断该实验是否安全、值得执行和部署”。BRACE-MSI统一实验生命周期、工具边界、预算、安全、审计和回滚；Gas、Bearing、Engine允许独立模型、参数、动作和历史，不按数据集名称在共享代码中硬编码捷径 `[D-035]`。

## 2. 组件与边界

```text
OfficialRuntimeAdapter
  -> TaskBootstrap
  -> Official A/B/C Checkpoint + HistoryReader
  -> PyTrioAgentClient(Qwen3.5-4B) / DeterministicFallback
  -> StructuredProposalValidator
  -> ToolAllowlist / BudgetLedger
  -> SandboxedOfficialTrainer / ModelAdapter
  -> IndependentEvaluator
  -> SafetyGate
  -> ModelRegistry / RollbackManager
  -> SwanLabLogger + PrivateAuditLog
```

### PyTrioAgentClient与HistoryReader

- 只接收脱敏的任务元数据、聚合指标、资源、历史动作和失败摘要，不接收密钥或逐样本私有数据。
- 只输出版本化JSON提案；模型名、Sampler路径、Base URL和凭据由运行时注入 `[D-036]`。
- 记录请求/响应哈希、Token、延迟和错误；服务不可用、超时或输出非法时退回确定性策略。
- Agent不能直接训练、部署、调用shell或修改原始训练包。

### StructuredProposalValidator与ToolAllowlist

- 提案必须命中允许的动作、模型/训练参数schema、路径根和单轮资源上限。
- 代码级增强只允许预先登记、测试通过、固定哈希的插件；不得执行模型临时生成的源代码 `[D-011]`。
- 所有候选在隔离目录运行，成功加载并通过独立评估前不得替换稳定模型。

### 三任务适配

- 统一组件：历史格式、提案schema、预算账本、工具边界、SafetyGate、注册表和日志。
- 任务独立组件：模型/检查点、指标方向、超参数空间、训练动作、回放缓冲和历史经验。
- 正式平台字段只存在于`OfficialRuntimeAdapter`，不得渗入核心策略。

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

### GeneralistParentEnsemble

- `generalist-fit`只从任务类型、有限数值schema、合法训练数据和父`checkpoint.npz`构建候选；数据集名称不进入模型选择特征。
- 训练内部共享`linear / HistGradientBoosting / ExtraTrees`模型池与3折选择原则；分类和回归只切换估计器及指标方向。
- 最终单文件`checkpoint.npz`同时保存父checkpoint字节、父哈希、候选模型和固定混合元数据；`generalist-predict`独立加载并输出。
- D-056/D-057冻结A保留父模型、B/C采用固定50/50父模型集成。该A/B/C选择属于开发证据和SafetyGate结果，不写入未知任务的名称分支；隐藏任务必须由同一训练内部证据和运行时门控决定。
- 正式SDK的父路径、批次事件和提交字段只由`OfficialRuntimeAdapter`映射；当前本地格式通过不等于平台续训协议通过。

### EvidenceRouter与DiagnosisEngine

输入包括数据质量、协变量漂移、目标/类别分布变化、性能退化、历史遗忘、预算和动作历史。漂移不是训练的唯一触发器；性能证据可独立触发低成本候选 `[D-010]`。

### ActionPolicy与BudgetAllocator

白名单动作：`NOOP`、`RECALIBRATE`、`INCREMENTAL_UPDATE`、`REPLAY_REFIT`、`FAMILY_SWITCH`、`BOUNDED_HPO`、`REGISTERED_PLUGIN`、`ROLLBACK`。运行时禁止生成并执行任意代码 `[D-011]`。

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
- 在正式SDK公布前写死比赛端点、密钥、事件字段和调用顺序；Qwen3.5-4B仅作为当前默认配置而不是核心常量。
