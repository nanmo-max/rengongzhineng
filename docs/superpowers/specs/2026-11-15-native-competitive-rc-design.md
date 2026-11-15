# Native Competitive RC Design

## Goal

在冻结`BRACE-MSI-0.6.0rc1`的前提下，形成一个当天可提交的平台原生竞争候选：执行器与官方训练器等价、十轮决策可选择retain或有界训练、性能策略来自既有冻结证据、PyTRiO和SwanLab有真实收据、镜像满足平台归档约束。

## Architecture

1. `NativeParity`在性能工作前逐状态比较官方训练器与`_NativeModel`。
2. `NativeDecisionPolicy`消费任务契约、当前/历史train证据和预算，输出`retain`、`incremental_update`或`replay_refit`及冻结参数；不按十轮固定菜单训练。
3. `NativeSafetyGate`使用任务契约提供的主指标、辅指标和train内部风险额度；不使用统一5%阈值或Anchor绝对零退化。
4. PyTRiO只能提出结构化白名单建议；Harness负责参数边界、训练、Gate和提交。服务失败记录收据并retain。
5. SwanLab只同步最终冻结运行的聚合训练、决策、资源和Token字段；逐样本数据、密钥和完整Sampler路径禁止公开。

## Data and evidence boundaries

- 原始训练包只读；当前Gate不训练，历史Replay遵守隔离期。
- 旧冻结日程只是候选参数来源，不把旧公开成绩归属于新Native实验。
- 公开validation只在配置冻结后打开一次；结果只能决定发布或保留`0.6.0rc1`。
- 新RC必须保留父checkpoint schema、Adam/预处理/epoch/step和64 MiB限制。

## Release gates

- A/B/C Native差分等价。
- 每轮一项真实决策，0或1候选；全程至少3个真实候选。
- 冻结确认三任务不低于`0.6.0rc1`，至少两项严格改善。
- Native PyTRiO至少3次非零Token、至少1项建议执行、后续上下文引用历史。
- SwanLab三任务运行完成且只含聚合字段。
- 完整回归、4核8GB、断网、父链、预测、体积和`docker save/load`通过。

## Stop rules

Native等价失败、必须重开validation调参、任何任务冻结确认退化或发布约束失败时，不替换`0.6.0rc1`。外部模型服务或SwanLab不可达时记录`BLOCKED_EXTERNAL`，不制造证据。
