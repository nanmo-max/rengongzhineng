# Local Proxy Training Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在Gas与C-MAPSS代理数据上构建可审计、无未来泄漏的分类/回归本地自主训练闭环，并比较静态、性能触发式和BRACE策略。

**Architecture:** CORE-001继续只负责事件合法性；数据适配器产生带不可逆样本ID的初训、开发流和密封段。统一流运行器在每批执行预测、合法反馈、证据计算、训练前预算检查、候选训练、独立验证、SafetyGate及部署/拒绝，所有结果写入本地JSONL和汇总JSON。正式SDK与SwanLab云端适配保持隔离和阻塞。

**Tech Stack:** Python 3.12、NumPy、pandas、scikit-learn、SciPy、psutil、pytest；不新增下载依赖。

**Spec:** `docs/ARCHITECTURE.md`、`docs/EXPERIMENT_PROTOCOL.md`、`docs/DECISION_LOG.md`

## Global Constraints

- 所有运行标注为代理数据实验，不得表述为官方成绩。
- 原始数据只读；派生产物写入`artifacts/`，模型权重不提交Git。
- Gas按批次时间顺序；C-MAPSS按发动机ID分组，任何未来批次或密封段不得参与训练、阈值或动作选择。
- 同一被评分样本严格遵循预测→记录→反馈→候选训练。
- 默认随机种子`20261106`；正式SDK、官方评分、SwanLab云端同步继续阻塞。
- Smoke Test先于完整运行；资源记录至少包含墙钟、CPU时间、RSS、样本数和候选数。

## Review Focus

- 解析Gas稀疏格式时，缺失/重复/越界特征必须失败而不是静默错位；由Task 1测试覆盖。
- C-MAPSS必须按发动机分组切分，单个发动机不能跨初训、开发和密封段；由Task 1测试覆盖。
- 候选训练失败或超预算不能污染稳定模型；由Task 2测试覆盖。
- 性能触发和BRACE只能使用当前及历史合法反馈，不能读取未来批次指标；由Task 3测试覆盖。
- 结果文件必须明确`proxy_only=true`且不得包含原始特征或逐样本标签；由Task 3测试覆盖。

---

### Task 1: LOCAL-DATA-001 代理数据审计与冻结切分

**Files:**
- Create: `src/brace_msi/data/types.py`
- Create: `src/brace_msi/data/gas.py`
- Create: `src/brace_msi/data/cmapss.py`
- Create: `scripts/audit_proxy_data.py`
- Create: `tests/data/test_gas.py`
- Create: `tests/data/test_cmapss.py`
- Create: `docs/source_notes/PROXY_DATA_AUDIT.md`

**Interfaces:**
- Produces: `BatchData`, `TaskStream`, `load_gas_stream(root, smoke=False)`, `load_cmapss_fd001_stream(zip_path, smoke=False)`, `audit_proxy_data(...)`。

- [x] 编写失败测试：Gas解析维度/标签/批次顺序、非法稀疏索引；C-MAPSS 26列、RUL构造、发动机组互斥和时间顺序。
- [x] 运行定向测试，确认因数据模块缺失而失败。
- [x] 实现只读解析器、不可逆样本ID、Smoke和完整冻结切分；不加载密封标签到策略输入。
- [x] 运行数据测试和全套测试。
- [x] 执行审计脚本，仅输出结构、分布、哈希与切分摘要；更新任务证据并提交。

### Task 2: LOCAL-CORE-001 模型、预算、监测与SafetyGate

**Files:**
- Create: `src/brace_msi/modeling.py`
- Create: `src/brace_msi/monitoring.py`
- Create: `src/brace_msi/budget.py`
- Create: `src/brace_msi/safety.py`
- Create: `src/brace_msi/resources.py`
- Create: `tests/core/test_modeling.py`
- Create: `tests/core/test_budget_and_gate.py`

**Interfaces:**
- Consumes: `BatchData.task_kind`, training features/targets and stable anchor split。
- Produces: `SklearnModelAdapter.fit/partial_fit/predict/clone/refit`、`Evidence`、`BudgetDecision`、`GateDecision`、`ResourceUsage`。

- [x] 编写失败测试：分类/回归能力声明、增量与重拟合、性能/漂移证据、训练前预算拒绝、候选失败不替换稳定模型。
- [x] 运行定向测试确认预期红灯。
- [x] 最小实现SGD增量模型、同族重拟合、KS/性能证据、预算账本、三层门控和资源计量。
- [x] 运行定向及全套测试，更新任务证据并提交。

### Task 3: LOCAL-LOOP-001 策略与无人值守本地流运行器

**Files:**
- Create: `src/brace_msi/policies.py`
- Create: `src/brace_msi/runner.py`
- Create: `src/brace_msi/audit.py`
- Create: `tests/loop/test_policies.py`
- Create: `tests/loop/test_runner.py`

**Interfaces:**
- Consumes: Task 1流、Task 2模型/证据/预算/门控。
- Produces: `StaticPolicy`、`PerformanceTriggeredPolicy`、`BracePolicy`、`run_stream(...) -> RunSummary`及脱敏JSONL审计。

- [x] 编写失败测试：三策略动作、严格prequential顺序、至少两种真实训练动作、拒绝/部署、未来批次不可见、脱敏日志。
- [x] 运行定向测试确认预期红灯。
- [x] 实现静态、简单触发和BRACE白名单策略及统一运行器；BRACE按证据选择动作而非固定菜单。
- [x] 运行定向及全套测试，更新任务证据并提交。

### Task 4: LOCAL-SMOKE-001 低成本预注册与Smoke Test

**Files:**
- Create: `configs/local_smoke.json`
- Create: `scripts/run_local_experiment.py`
- Modify: `docs/EXPERIMENTS.md`
- Produce (ignored): `artifacts/experiments/LOCAL-SMOKE-001/`

**Interfaces:**
- Consumes: `run_stream`和两个`smoke=True`数据流。
- Produces: 六个策略×任务运行摘要、事件JSONL和资源汇总。

- [x] 预注册研究问题、切分、指标、种子、预算、停止条件和产物。
- [x] 写CLI失败测试并确认缺失入口红灯。
- [x] 实现配置驱动CLI；运行Smoke并保留成功或失败记录。
- [x] 核验无泄漏、至少一个增量与一个重拟合候选、日志脱敏和预算字段；未满足则按失败分析修复。
- [x] 更新实验记录、任务状态并提交代码与文档，不提交模型权重或实验大文件。

### Task 5: LOCAL-EXP-001 完整本地基线与三次真实迭代

**Files:**
- Create: `configs/local_full.json`
- Modify: `docs/EXPERIMENTS.md`
- Modify: `docs/RESEARCH_PROGRESS.md`
- Produce (ignored): `artifacts/experiments/LOCAL-EXP-001/`

**Interfaces:**
- Consumes: 冻结后的Task 1-4代码与配置。
- Produces: Gas与FD001的静态、性能触发、BRACE配对结果；阶段指标、候选事件、CPU/内存/耗时与失败分析。

- [ ] 预注册完整实验并冻结配置、数据指纹和代码提交。
- [ ] 先在开发流运行并冻结策略阈值，再对密封段只运行一次。
- [ ] 验证全局至少三次真实候选训练/评估，且包含增量更新和同族重拟合。
- [ ] 生成不含自创总分的分类Accuracy/Macro-F1、回归RMSE/MAE、最差阶段和资源对照表。
- [ ] 更新实验、风险、状态与交接；运行全套测试和结果一致性检查后提交。
