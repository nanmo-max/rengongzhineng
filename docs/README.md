# BRACE-MSI 文档中心

本目录是项目的正式知识库。文档建立于 2026-11-06，依据本地官方赛题规则、三张宣讲截图、用户提供的宣讲记录、已确认团队决策以及本地文件审计结果。

## 单一事实来源

| 主题 | 权威文件 | 说明 |
|---|---|---|
| 当前状态与执行入口 | [STATUS.md](STATUS.md) | 只在这里维护“现在做到哪里” |
| 任务、依赖与完成标准 | [TASKS.md](TASKS.md) | 只在这里维护任务状态 |
| 外部事实与证据 | [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) | 区分官方、宣讲、本地事实、假设 |
| 研究决策 | [DECISION_LOG.md](DECISION_LOG.md) | 追加式记录，保留被替代决策 |
| 实验运行与结果 | [EXPERIMENTS.md](EXPERIMENTS.md) | 包含成功、失败与INVALID历史；代理结果不冒充官方成绩 |
| 风险状态 | [RISK_REGISTER.md](RISK_REGISTER.md) | 风险、触发器、缓解与负责人 |

## 正式文档

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)：从现在到企业赛的正式实施计划。
- [ARCHITECTURE.md](ARCHITECTURE.md)：BRACE-MSI V4.1 技术架构和接口边界。
- [WORKFLOW.md](WORKFLOW.md)：开发、评审、实验和交付工作流。
- [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md)：数据防泄漏、基线、资源、消融、SwanLab和验收规范。
- [REFERENCES.md](REFERENCES.md)：资料索引和文献研究队列。
- [RESEARCH_PROGRESS.md](RESEARCH_PROGRESS.md)：按时间追加的研究与工程进度。
- [SESSION_HANDOFF.md](SESSION_HANDOFF.md)：新会话恢复流程。
- [RELEASE_CANDIDATE.md](RELEASE_CANDIDATE.md)：RC交付物、审计结果和外部阻塞。
- [SWANLAB_INTEGRATION.md](SWANLAB_INTEGRATION.md)：SwanLab离线记录及显式同步边界。
- [SDK_INTEGRATION.md](SDK_INTEGRATION.md)：正式SDK插件契约与到货接入流程。
- [audits/INITIAL_FILE_AUDIT.md](audits/INITIAL_FILE_AUDIT.md)：建立文档前的文件审计。
- [source_notes/OFFICIAL_RULES_EXTRACT.md](source_notes/OFFICIAL_RULES_EXTRACT.md)：官方PDF逐页核验摘要。
- [source_notes/BRIEFING_NOTES_2026-11-06.md](source_notes/BRIEFING_NOTES_2026-11-06.md)：宣讲记录的证据化摘要。

## 证据标签

- `O-*`：官方已确认信息。
- `B-*`：宣讲、答疑或宣讲截图信息，低于正式规则。
- `L-*`：用户确认或本地文件直接核验的项目事实。
- `H-*`：待官方文档核实的假设或冲突项。
- `D-*`：团队研究或工程决策，不冒充官方要求。

所有关键结论必须引用以上标签。标签定义只允许登记在 `SOURCE_REGISTRY.md` 或 `DECISION_LOG.md`。

## 历史材料

`plans/_draft/` 中的文件是方案形成阶段的原始草稿，已包含被后续证据和决策替代的内容。它们保留用于追溯，但不具有当前规范效力。
