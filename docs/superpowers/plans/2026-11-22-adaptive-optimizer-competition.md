# BRACE-MSI P3 Adaptive Optimizer Competition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a research-only, equal-budget benchmark that compares static, random search, Optuna TPE and real-Qwen adaptive search without modifying the frozen formal RC.

**Architecture:** Add a shared research `TrialRunner` and interchangeable optimizer adapters. All arms reuse the existing parent-compatible recipe executor, evaluator and deterministic selector; only `suggest/observe` differs. Detailed aggregate history is produced once and consumed by Qwen, while random/TPE receive the same completed observations through typed interfaces.

**Tech Stack:** Python 3.10+, NumPy, existing `brace_formal`, pytest, psutil, research-only Optuna 5.1.0, existing PyTRiO 0.2.9 transport.

**Spec:** `docs/superpowers/specs/2026-11-22-adaptive-optimizer-competition-design.md`

## Global Constraints

- Do not modify, rebuild or retag `brace-msi:0.11.0rc1` or its `harness.tar`.
- Do not read A/B/C `public/validation.jsonl`, XJTU sealed data or official hidden data.
- Do not upload to the platform or consume official trial runs.
- Keep Optuna, PyTRiO and benchmark scripts outside the formal release whitelist.
- All optimizer arms share identical parent checkpoints, folds, search space, candidate counts, work-unit accounting and evaluation code.
- A result with local-model fallback, missing real service receipt or unequal budget is invalid, not a Qwen win/loss.

## Review Focus

- Conditional parameters from one recipe must never leak into another recipe's normalized configuration.
- TPE trial 4 must be observation-driven, not another unlabelled startup random trial.
- Row reordering must not change unit/bearing/class-group fold membership.
- A failed Qwen call must not silently execute a deterministic candidate under the Qwen arm.
- Confirmation paths and hashes must never enter optimizer context before all selection rules are frozen.

---

### Task 1: Create the isolated research branch and preregistration

**Files:**
- Create: `configs/adaptive_optimizer_pilot.json`
- Create: `requirements-hpo.lock`
- Modify: `docs/EXPERIMENTS.md`

**Interfaces:**
- Consumes: frozen commit `eae619b`, official package hashes already registered in `configs/competition_core_experiments.json`.
- Produces: immutable pilot manifest with `experiment_id=ADAPTIVE-OPT-COMPARE-001-A1`, task C, seed `20261122`, six trials and the frozen search space.

- [ ] **Step 1: Create branch `codex/p3-adaptive-optimizer-benchmark` from `eae619b` and verify the frozen RC hashes remain unchanged.**
- [ ] **Step 2: Add `requirements-hpo.lock` with `optuna==5.1.0` and its resolved research dependencies; do not alter `requirements.lock` or formal build files.**
- [ ] **Step 3: Register the A1 manifest and all success/stopping conditions in `docs/EXPERIMENTS.md`.**
- [ ] **Step 4: Run `git diff --check` and the manifest parser test added in Task 2.**
- [ ] **Step 5: Commit with `plan: preregister adaptive optimizer pilot`.**

### Task 2: Implement the common search-space and ledger contracts

**Files:**
- Create: `src/brace_msi/adaptive_benchmark/protocol.py`
- Create: `src/brace_msi/adaptive_benchmark/search_space.py`
- Create: `src/brace_msi/adaptive_benchmark/ledger.py`
- Create: `src/brace_msi/adaptive_benchmark/__init__.py`
- Create: `tests/research/adaptive_benchmark/test_protocol.py`
- Create: `tests/research/adaptive_benchmark/test_search_space.py`

**Interfaces:**
- Produces: `SearchContext`, `TrialSuggestion`, `TrialObservation`, `BudgetState`, `OptimizerProtocol`, `ConditionalSearchSpace.normalize()` and append-only `TrialLedger`.

- [ ] **Step 1: Write failing tests for conditional normalization, identical arm search spaces, budget accounting and atomic ledger resume.**
- [ ] **Step 2: Run `pytest tests/research/adaptive_benchmark/test_protocol.py tests/research/adaptive_benchmark/test_search_space.py -q` and verify failure.**
- [ ] **Step 3: Implement the typed contracts and exact search space from the spec.**
- [ ] **Step 4: Re-run the two test files and verify all pass.**
- [ ] **Step 5: Commit with `feat: add adaptive benchmark contracts`.**

### Task 3: Add random and TPE optimizer adapters

**Files:**
- Create: `src/brace_msi/adaptive_benchmark/optimizers.py`
- Create: `tests/research/adaptive_benchmark/test_optimizers.py`

**Interfaces:**
- Consumes: `OptimizerProtocol`, `ConditionalSearchSpace`, `TrialObservation`.
- Produces: `RandomOptimizer(seed)` and `TPEOptimizer(seed, n_startup_trials=3, n_ei_candidates=24)`.

- [ ] **Step 1: Write failing tests proving random reproducibility, identical conditional support, ask/tell persistence and a TPE trial after startup.**
- [ ] **Step 2: Run the optimizer tests and verify failure because adapters do not exist.**
- [ ] **Step 3: Implement NumPy random search and an Optuna ask/tell wrapper with `multivariate=False`; store whether each suggestion is `startup` or `tpe`.**
- [ ] **Step 4: Run optimizer tests in a clean research venv containing `requirements-hpo.lock`.**
- [ ] **Step 5: Commit with `feat: add random and tpe benchmark optimizers`.**

### Task 4: Add detailed aggregate history and the real-Qwen optimizer

**Files:**
- Create: `src/brace_msi/adaptive_benchmark/history_view.py`
- Create: `src/brace_msi/adaptive_benchmark/qwen_optimizer.py`
- Create: `tests/research/adaptive_benchmark/test_history_view.py`
- Create: `tests/research/adaptive_benchmark/test_qwen_optimizer.py`

**Interfaces:**
- Consumes: completed `TrialObservation` records and existing `PyTrioSamplingTransport`.
- Produces: `build_optimizer_history(observations)`, `QwenOptimizer(include_history: bool)` and `QwenCallReceipt` with provider IDs separated from local correlation IDs.

- [ ] **Step 1: Write failing tests that the second prompt contains the first trial's recipe, resolved parameters, metrics, selection, failure and resource fields, while raw IDs/features/labels/paths are rejected.**
- [ ] **Step 2: Write failing tests that no-history removes only trial history, missing provider receipt invalidates the Qwen arm, and deterministic fallback cannot be reported as Qwen.**
- [ ] **Step 3: Implement the compact JSON schema, strict response parser and PyTRiO 0.2.9 adapter. Record `sampling_run_cuid`; record per-call provider request ID only when actually exposed.**
- [ ] **Step 4: Run the history/Qwen tests with a fake transport; do not make a paid call.**
- [ ] **Step 5: Commit with `feat: add history-aware qwen optimizer`.**

### Task 5: Implement the shared fold runner and leak guards

**Files:**
- Create: `src/brace_msi/adaptive_benchmark/runner.py`
- Create: `src/brace_msi/adaptive_benchmark/splits.py`
- Create: `tests/research/adaptive_benchmark/test_runner.py`
- Create: `tests/research/adaptive_benchmark/test_splits.py`

**Interfaces:**
- Consumes: official parent checkpoint, train JSONL, optimizer and frozen manifest.
- Produces: per-trial fold receipts, final selected checkpoint, one-time confirmation receipt and budget validation.

- [ ] **Step 1: Write failing tests for unit/bearing/class grouping, row-order invariance, zero path overlap and denial of `public/validation`, XJTU and hidden paths.**
- [ ] **Step 2: Write failing tests that static/random/TPE/Qwen use the same parent, folds, evaluator, selector and budget schema.**
- [ ] **Step 3: Implement grouped splits, fixed-parent three-fold candidate evaluation, work-unit accounting and deterministic artifact selection using existing `brace_formal` components.**
- [ ] **Step 4: Verify confirmation is unreadable until every optimizer is frozen, then readable exactly once per arm.**
- [ ] **Step 5: Run all adaptive benchmark tests and commit with `feat: add fair adaptive benchmark runner`.**

### Task 6: Add CLI, validation and machine report

**Files:**
- Create: `scripts/run_adaptive_optimizer_benchmark.py`
- Create: `src/brace_msi/adaptive_benchmark/report.py`
- Create: `tests/research/adaptive_benchmark/test_cli.py`
- Create: `tests/research/adaptive_benchmark/test_report.py`

**Interfaces:**
- Produces: `manifest.json`, per-arm ledgers, `summary.json`, `report.html` and `validation.json`.

- [ ] **Step 1: Write failing smoke tests using synthetic classification/regression tasks and fake Qwen receipts.**
- [ ] **Step 2: Implement `--config`, `--output`, `--smoke`, `--resume` and `--validate-only`; refuse nonempty mismatched output roots.**
- [ ] **Step 3: Report best-so-far AUC, fixed-budget final metrics, ineffective ratio, repetition, failures, CPU/wall/RSS/work units and model-service costs without creating a composite official score.**
- [ ] **Step 4: Run smoke twice to prove deterministic resume and report hash stability.**
- [ ] **Step 5: Commit with `feat: add adaptive benchmark cli and report`.**

### Task 7: Execute the C feasibility pilot

**Files:**
- Modify: `docs/EXPERIMENTS.md`
- Create: `docs/results/ADAPTIVE-OPT-COMPARE-001-A1.md`
- Modify: `docs/RESEARCH_PROGRESS.md`

**Interfaces:**
- Consumes: frozen A1 manifest and real PyTRiO login outside the repository.
- Produces: static/Random/TPE/Qwen-History/Qwen-No-History six-trial machine evidence.

- [ ] **Step 1: Run `--smoke` with fake Qwen and validate all protocol gates before spending any remote budget.**
- [ ] **Step 2: Run the real C pilot once; save real PyTRiO sampler/service identifiers, prompt/response hashes, Tokens and latency without saving credentials.**
- [ ] **Step 3: Run `--validate-only`; stop immediately if budgets, folds, receipts or access guards differ.**
- [ ] **Step 4: Write the result report, including negative and invalid outcomes; do not read public validation.**
- [ ] **Step 5: Commit machine summaries and documentation only; keep checkpoints and raw remote artifacts outside Git.**

### Task 8: Gate the three-task, three-seed experiment

**Files:**
- Create only after A1 passes: `configs/adaptive_optimizer_full.json`
- Modify only after A1 passes: `docs/EXPERIMENTS.md`

**Interfaces:**
- Consumes: A1 valid budget receipts and the deterministic formulas in the spec.
- Produces: a preregistered A2 manifest; it does not itself authorize execution.

- [ ] **Step 1: Verify A1 has six completed candidates per optimizer, TPE post-startup trials and valid real-Qwen receipts.**
- [ ] **Step 2: Generate A2 budgets solely from the frozen formulas; do not hand-tune them from performance.**
- [ ] **Step 3: Register the three tasks, three paired seeds, primary/secondary outcomes and stop conditions.**
- [ ] **Step 4: Request explicit approval before launching the large A2 matrix.**
- [ ] **Step 5: Commit with `plan: preregister full adaptive optimizer comparison`.**

## Plan self-review

- Spec coverage: all seven requested deliverables are covered by the spec and Tasks 1–8.
- Isolation: formal runtime files and frozen RC are not modified; research dependencies use a separate lock.
- Fairness: one runner, one search space, paired folds/seeds and three simultaneous budget measures prevent algorithm-specific advantages.
- Evidence: real-Qwen and local fallback are structurally distinguishable; missing service evidence invalidates the arm.
- Staging: only the C feasibility pilot is executable after implementation approval; the large matrix has an explicit second approval gate.
