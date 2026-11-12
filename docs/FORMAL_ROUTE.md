# BRACE-MSI 当前正式技术路线

本文件说明当前执行方向，不替代状态、任务、证据、决策和实验五个单一事实来源。实时状态见[STATUS.md](STATUS.md)，任务依赖见[TASKS.md](TASKS.md)，外部证据见[SOURCE_REGISTRY.md](SOURCE_REGISTRY.md)，锁定决策见[DECISION_LOG.md](DECISION_LOG.md)，实验运行见[EXPERIMENTS.md](EXPERIMENTS.md)。

## 1. 路线结论

当前正式路线为：

> **Qwen3.5-4B PyTRiO Agent + BRACE确定性Harness + 官方A/B/C工业模型 + 经过验证的开源优化方法。**

项目统一的是十轮自主实验工作流、工具接口、预算、安全门、审计和回滚，不再强制Gas、Bearing和Engine共享同一组策略阈值、模型或优化动作。三个任务允许独立的模型配置、超参数、动作空间和历史经验，但都必须经过同一套确定性执行与验收边界。[D-035]

## 2. 已确认的平台能力

- 官方A/B/C训练包提供CPU训练代码、公开训练/验证集、真实初始`checkpoint.npz`和指标定义。[O-PLATFORM-005]
- PyTRiO官方Python客户端支持`ServiceClient`、Sampler推理、LoRA训练、权重保存与恢复、环境变量鉴权和OpenAI兼容接口。[O-PYTRIO-001]
- 平台提交校验已经接受Qwen3.5-4B基础模型；持久化Sampler微调权重也允许提交，先前失败是权重未正确持久化而不是4B基座受限。[B-PLATFORM-002]
- 每个任务进行十轮优化；至少保留三次完整“读历史—做实验—依据结果决策”记录；最终评分对象是续训后的工业模型。[O-PLATFORM-001][O-PLATFORM-003]

## 3. 已完成工程基础

- 事件协议、防泄漏状态机、候选隔离、资源账本、SafetyGate、原子检查点、部署回滚、恢复和私有审计均已有测试。
- 官方训练包原版NumPy训练器已完成真实续训、全状态继承与父检查点链验证。
- 三个官方包的静态基线和低成本续训已复算；结果仍属于公开开发证据，不是隐藏评测成绩。
- Docker上下文、依赖锁、SDK插件接口和SwanLab离线适配已存在；实际容器运行仍受本机无Docker/Podman阻塞。
- 统一策略搜索及其负结果完整保留。复杂共享策略在3/3任务级留出fold没有超过简单策略，因此不进入当前正式主线。[D-034]

## 4. 尚未验证的外部接口

- 正式评测镜像的入口命令、挂载目录、环境变量和十轮事件/输出协议；
- 比赛环境注入的PyTRiO Base URL、API Key、模型白名单与Token计量；
- 客观35分的完整数学公式和平台资源计量实现；
- SwanLab比赛项目、必填字段、公开范围及无公网环境后的同步责任；
- 正式镜像构建、4核8GB Linux运行和平台提交校验。

未知项必须留在适配器或配置中，禁止写死为事实。

## 5. 最终技术架构

```text
OfficialRuntimeAdapter
  -> OfficialTaskBootstrap / A-B-C Checkpoint
  -> HistoryReader
  -> PyTrioAgentClient(Qwen3.5-4B; optional persisted Sampler)
  -> StructuredExperimentProposal
  -> ProposalValidator / ToolAllowlist / BudgetLedger
  -> SandboxedOfficialTrainer
  -> IndependentEvaluator
  -> SafetyGate
  -> Deploy / Reject / Rollback
  -> ExperimentHistory + SwanLabAdapter + PrivateAudit
```

PyTRiO Agent只提出结构化实验建议。任何配置变更、有限代码补丁、命令调用、训练和部署都必须通过白名单、路径边界、预算和SafetyGate；模型服务异常时退回确定性策略。[D-035][D-036]

## 6. 三任务独立优化原则

- Gas：Macro-F1为主，关注类别不平衡、阶段混淆、校准、训练调度和分类损失。
- Bearing：RMSE/MAE为主，按整根轴承隔离，关注目标缩放、轨迹分布、稳健回归和CPU成本。
- Engine：RMSE为主并参考NASA非对称评分，按整台发动机隔离，关注寿命高估风险、稳健损失和训练调度。
- 任何任务不得使用未来阶段、设备ID、完整寿命或验证统计作为输入特征。
- 单任务优化不得破坏其他任务的硬性资格；正式候选必须三个任务均不低于各自平台基线。

## 7. 开源论文与代码进入规则

只检索并复现能够解决已测得失败点的方法。优先一区SCI、CCF-A及高质量开源研究；每个候选必须核验论文贡献、官方代码、许可证、与官方小型MLP/训练器的兼容性、4核8GB CPU成本和预期作用机制。

进入正式系统前必须依次通过：

1. 文献与许可证审计；
2. 独立实验ID和预注册假设；
3. 与官方静态、固定更新及BRACE无大模型对照；
4. 公开开发数据上的可复算增益与资源证据；
5. 必要消融和失败分析。

只引用未运行、无许可证、依赖GPU或不能解释真实性能问题的方法不得进入主线。[D-037]

## 8. 实验成功标准

- 每任务从官方检查点开始完成十轮无人干预流程；
- 每任务至少三次真实候选训练和完整决策记录；
- 三个任务最终主指标均不低于官方静态基线；
- 分别报告平均增益、最差阶段、恢复速度、CPU/RSS、Token/费用、候选接受与回滚；
- PyTRiO+BRACE必须与BRACE无大模型公平比较；没有增益时如实保留负结果；
- 公开验证集的反复使用必须记账，不得包装成独立测试；
- 最终结论具备提交、数据指纹、配置、日志、失败记录和干净环境复现。

## 9. 实施顺序

1. 官方训练器进入主Harness；
2. PyTRiO客户端、结构化提案、工具白名单和确定性降级；
3. Gas/Bearing/Engine独立性能诊断与低成本优化；
4. 高价值论文方法的有界复现；
5. 三任务十轮自主闭环与对照；
6. Docker、SwanLab、干净复现和竞赛材料；
7. 取得正式平台协议后只替换运行适配层，不绕过现有安全边界。
