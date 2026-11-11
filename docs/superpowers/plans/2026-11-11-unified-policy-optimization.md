# Unified Policy Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate one identity-blind BRACE policy with shared normalized evidence, shared parameters and three-task leave-one-task-out evidence before any official test submission.

**Architecture:** Add a separate optimization path around the existing task adapters and model interfaces. It converts task metrics into dimensionless evidence, searches a bounded shared policy configuration using only bootstrap/development phases, validates transfer with task-level leave-one-out, and opens terminal phases only after a frozen execution manifest.

**Tech Stack:** Python 3.12, NumPy, SciPy, scikit-learn, existing BRACE-MSI adapters/audit/resource modules, pytest.

**Spec:** `docs/superpowers/specs/2026-11-11-unified-policy-optimization-design.md`

## Global Constraints

- Do not modify raw data, frozen experiment directories, the RC tag or `main`.
- Do not call platform SDK, SwanLab, external APIs or use any official test opportunity.
- The policy input schema must not contain task IDs, dataset/profile names, paths or batch names.
- Gas and FD001 terminal evidence is historically exposed; only unopened XJTU terminal bearings may be labelled virgin.
- Every experiment is preregistered with an ID, source commit, config hash, split manifest and exposure class.
- A terminal phase is prediction-only and can be opened once after the shared configuration is frozen.

## Review Focus

- Metric direction/scale errors: tests must show equivalent relative degradation yields the same action for Macro-F1 and RMSE.
- Identity leakage: tests must fail configs or policy inputs containing task/profile/dataset keys and prove renaming does not change actions.
- Split leakage: tests must reject overlapping sample/group IDs and any terminal access before freeze.
- Selection leakage: tests must prove held-out fold results are not inputs to that fold's parameter selector.
- Resume/tamper safety: tests must reject changed config/split hashes and resume without repeating completed candidates.

---

### Task 1: Normalized identity-blind policy core

**Files:**
- Create: `src/brace_msi/unified_policy.py`
- Create: `tests/unified_policy/test_policy_core.py`
- Modify: `src/brace_msi/decision.py`

**Interfaces:**
- Consumes: existing `Action`, `ModelCapabilities`, `BudgetLedger` concepts.
- Produces: `MetricDescriptor`, `NormalizedEvidence`, `SharedPolicyConfig`, `UnifiedActionPolicy.select()` and `normalized_metric_delta()`.

- [ ] **Step 1: Write failing tests for scale/direction invariance, identity-blind schema, action escalation and invalid evidence.**
- [ ] **Step 2: Run `pytest tests/unified_policy/test_policy_core.py -q` and verify RED.**
- [ ] **Step 3: Implement the immutable dataclasses, normalized metric conversion and deterministic shared action ladder.**
- [ ] **Step 4: Run focused tests and the full suite; record results.**
- [ ] **Step 5: Commit the policy core.**

### Task 2: Three-phase manifests and terminal lock

**Files:**
- Create: `src/brace_msi/policy_phases.py`
- Create: `tests/unified_policy/test_policy_phases.py`
- Create: `configs/unified_policy_optimization.json`

**Interfaces:**
- Consumes: `TaskStream`, existing Gas/C-MAPSS/XJTU adapters and immutable source hashes.
- Produces: `PhaseManifest`, `ExposureClass`, `validate_phase_manifest()` and `TerminalLock`.

- [ ] **Step 1: Write failing tests for sample/group overlap, source mutation, early terminal access, one-time opening and historical exposure labels.**
- [ ] **Step 2: Run the focused test and verify RED.**
- [ ] **Step 3: Implement phase manifests and an atomic terminal lock whose freeze record includes source commit, config hash and split hash.**
- [ ] **Step 4: Add task-adapter mappings without exposing task identity to the policy core.**
- [ ] **Step 5: Run focused/full tests and commit.**

### Task 3: Cross-task selector and robust objective

**Files:**
- Create: `src/brace_msi/cross_task_validation.py`
- Create: `tests/unified_policy/test_cross_task_validation.py`

**Interfaces:**
- Consumes: `SharedPolicyConfig`, per-task development results and resource ledgers.
- Produces: `TaskOutcome`, `FoldResult`, `CandidateRanking`, `leave_one_task_out()` and `rank_shared_candidates()`.

- [ ] **Step 1: Write failing tests for three rotating folds, fold-local selection, lexicographic worst-task ranking, simple-baseline domination and deterministic tie breaks.**
- [ ] **Step 2: Run the focused test and verify RED.**
- [ ] **Step 3: Implement selection/ranking without any task-name feature in candidate scoring.**
- [ ] **Step 4: Add machine-readable reasons for candidate elimination and stopping.**
- [ ] **Step 5: Run focused/full tests and commit.**

### Task 4: Resumable unified optimization runner

**Files:**
- Create: `src/brace_msi/unified_optimization.py`
- Create: `scripts/run_unified_policy_optimization.py`
- Create: `tests/unified_policy/test_unified_optimization.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: phase manifests, shared candidate configs, existing adapters/models/resources/audit primitives.
- Produces: preregistration, resumable fold/candidate state, immutable receipts, summaries and a validate-only command.

- [ ] **Step 1: Write failing tests for smoke execution, resume after receipt persistence, terminal refusal before freeze, tampered artifacts and no-op/fixed/performance-triggered/BRACE fairness.**
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Implement the runner and CLI with atomic state and bounded worker/resource settings.**
- [ ] **Step 4: Generate Markdown/HTML plus JSON machine validation without reading terminal data during development.**
- [ ] **Step 5: Run focused/full tests and commit.**

### Task 5: Smoke and bounded shared-parameter search

**Files:**
- Modify: `docs/EXPERIMENTS.md`
- Modify: `docs/RESEARCH_PROGRESS.md`
- Create after execution: `docs/results/UNIFIED-POLICY-OPT-001.md`

**Interfaces:**
- Consumes: committed runner/config and three public task adapters.
- Produces: smoke evidence, three leave-one-task-out folds, frozen shared candidate and resource comparison.

- [ ] **Step 1: Register `UNIFIED-POLICY-OPT-001-SMOKE` with hashes and development-only scope.**
- [ ] **Step 2: Run a low-cost smoke without terminal access and machine-validate it.**
- [ ] **Step 3: Register the bounded search matrix before execution.**
- [ ] **Step 4: Run/resume all shared candidates, preserve failures and compare four policies.**
- [ ] **Step 5: Apply stopping rules, freeze exactly one shared config and commit the development report.**

### Task 6: Single terminal evaluation and final candidate audit

**Files:**
- Modify: `docs/EXPERIMENTS.md`
- Modify: `docs/RESEARCH_PROGRESS.md`
- Modify: `docs/RISK_REGISTER.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/TASKS.md`
- Modify: `docs/SESSION_HANDOFF.md`
- Modify: `docs/results/UNIFIED-POLICY-OPT-001.md`

**Interfaces:**
- Consumes: frozen shared config, clean Git commit and terminal lock.
- Produces: one terminal result per task, exposure-aware conclusions, final machine validation and candidate handoff.

- [ ] **Step 1: Verify the frozen manifest and confirm zero official test submissions.**
- [ ] **Step 2: Open each terminal phase once; run static, fixed, triggered and BRACE from fair initial states without further selection.**
- [ ] **Step 3: Validate metrics, resources, exposure labels, hashes and no-training terminal behavior.**
- [ ] **Step 4: Report Gas/FD001 as historically exposed and XJTU as virgin only if its sealed data remained unopened until this step.**
- [ ] **Step 5: Run the full regression suite, update all SSOT documents and commit without moving the RC tag or merging `main`.**

