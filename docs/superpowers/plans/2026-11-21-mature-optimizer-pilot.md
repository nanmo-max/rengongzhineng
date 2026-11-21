# Mature Optimizer Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以可审计、父 checkpoint 兼容的开发探针比较 L2-SP、SAM-Adam 与 AdamW，只将有跨任务证据的机制送入后续十轮集成任务。

**Architecture:** 在 `FormalModel.fit` 中增加不改 checkpoint schema 的可选优化机制，用研究专用 registry 和运行器隔离正式 RecipeRegistry。运行器复用已锁定的官方源哈希与 train 内部序贯分组，生成不含 confirmation 的机器摘要。

**Tech Stack:** Python 3.11, NumPy, pytest, psutil, `contest.cpu-mlp.v1`.

**Spec:** `docs/superpowers/specs/2026-11-21-mature-optimizer-pilot-design.md`

## Global Constraints

- 冻结 `0.11.0rc1` 归档和 D-095；不修改、不替换正式镜像。
- 原始官方包只读；不读取公开 confirmation、密封集或隐藏数据。
- 首轮只运行三阶段小测；不运行完整十轮、PyTRiO、SwanLab、Docker 或官方试运行。
- 新方法必须保持原 checkpoint 字段、Adam 状态、参数量和独立预测契约。
- 先独立比较后组合；负结果同样保留。

## Review Focus

- SAM 扰动后必须恢复原参数，且只用第二梯度更新 Adam 状态。
- L2-SP 必须相对进入当次 `fit` 的父参数约束，不能锨定到零。
- AdamW 不对偏置、标准化统计和 Adam 矩衰减。
- 优化器参数为非有限、负数或未知字段时失败关闭。
- 小测输出中不得出现 confirmation 读取或修改源哈希。

---

### Task 1: 优化机制与研究配方

**Files:**
- Modify: `src/brace_formal/model.py`
- Create: `src/brace_msi/mature_optimizer_pilot.py`
- Test: `tests/research/test_mature_optimizer_pilot.py`

**Interfaces:**
- Consumes: `FormalModel.fit(values, targets, epochs, ...)` 和 `DataBatch` 现有契约。
- Produces: `MaturePilotRecipe` 以及 `fit_mature_recipe(parent, recipe, batch) -> CandidateResult`。

- [ ] **Step 1:** 先写 L2-SP、SAM、AdamW 行为和失败关闭测试。
- [ ] **Step 2:** 运行专项测试，确认因缺少新契约而失败。
- [ ] **Step 3:** 最小实现三种机制及参数校验。
- [ ] **Step 4:** 运行专项与原生模型/配方回归测试。
- [ ] **Step 5:** 提交机制实现。

### Task 2: 三阶段可恢复小测运行器

**Files:**
- Create: `configs/mature_optimizer_pilot.json`
- Create: `scripts/run_mature_optimizer_pilot.py`
- Test: `tests/system/test_mature_optimizer_pilot_runner.py`

**Interfaces:**
- Consumes: Task 1 `fit_mature_recipe` 和 `scripts.run_competition_core_experiments` 的只读源校验/分组边界。
- Produces: `summary.json` with `valid`, source hashes, per-task/per-arm/per-stage metrics and resource receipts.

- [ ] **Step 1:** 先写 manifest、confirmation 禁读、恢复和机器摘要测试。
- [ ] **Step 2:** 运行测试，确认因运行器缺失而失败。
- [ ] **Step 3:** 最小实现三阶段、可恢复运行与 Pareto 摘要。
- [ ] **Step 4:** 运行 Smoke 及专项测试。
- [ ] **Step 5:** 提交运行器与冻结 manifest。

### Task 3: 执行小测与证据归档

**Files:**
- Create: `docs/results/MATURE-OPTIMIZER-PILOT-001.md`
- Modify: `docs/EXPERIMENTS.md`
- Modify: `docs/RESEARCH_PROGRESS.md`
- Modify: `docs/RISK_REGISTER.md`
- Modify: `docs/TASKS.md`
- Modify: `docs/STATUS.md`

**Interfaces:**
- Consumes: Task 2 冻结 manifest 与运行器。
- Produces: `D:/brace-msi-competition/MATURE-OPTIMIZER-PILOT-001-A1/summary.json` 和脱敏结果摘要。

- [ ] **Step 1:** 预检源哈希并运行两个代理任务 Smoke。
- [ ] **Step 2:** 运行 A/B/C 前三阶段矩阵，保留全部正负结果。
- [ ] **Step 3:** 验证摘要、源哈希、父链、资源与 confirmation 零读取。
- [ ] **Step 4:** 运行全量回归和独立审查。
- [ ] **Step 5:** 更新 SSOT；只在存在晋级候选时创建新的完整十轮 READY 任务。

