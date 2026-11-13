# BRACE-MSI Paper Fusion Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and evaluate a CPU-only paper-guided ensemble/distillation candidate for all three official tasks without changing RC3 or using official test submissions.

**Architecture:** A new isolated research runner loads official public training rows, creates leakage-safe task features and grouped folds, evaluates a bounded teacher pool with successive halving, combines out-of-fold predictions, optionally distills a compact student, freezes the winner, and opens the historically exposed public validation exactly once. The existing RC3 Harness remains the governance and fallback boundary.

**Tech Stack:** Python 3.10+, NumPy, scikit-learn, SciPy, pytest; no PyTorch/GPU/new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-11-13-paper-fusion-sprint-design.md`

## Global Constraints

- Original packages and RC3 history are immutable.
- New artifacts live under `D:/brace-msi-paper-fusion/PAPER-FUSION-SPRINT-001/`.
- Selection uses train-internal folds only; public validation opens once after freeze.
- At most 12 teacher configurations per task, at most four full-budget finalists.
- No official test submission, PyTRiO call, SwanLab sync, or API secret.
- CPU-only, peak RSS below 4GiB, no new heavy dependency.

## Review Focus

- Metadata features must be causal: tests reject total-life/future fields.
- Group identities must never cross train and holdout folds.
- Ensemble weights must come only from out-of-fold metrics and sum to one.
- Classification probabilities must align classes even when a fold lacks a class.
- Re-running an output directory after final validation must fail closed rather than overwrite evidence.

---

### Task 1: Leakage-safe paper-fusion primitives

**Files:**
- Create: `src/brace_msi/paper_fusion.py`
- Create: `tests/performance/test_paper_fusion.py`

**Interfaces:**
- Produces: `load_official_rows(path, profile)`, `build_causal_features(rows, profile)`, `grouped_folds(rows, profile, seed)`, `TeacherSpec`, `successive_halving(...)`, `fit_weighted_ensemble(...)`, `PaperFusionCandidate`.

- [ ] Write tests for deterministic loading, causal metadata allowlists, group disjointness, probability alignment, normalized weights, and fail-closed invalid inputs.
- [ ] Run `D:/anaconda3/python.exe -m pytest tests/performance/test_paper_fusion.py -q` and verify RED for the missing module.
- [ ] Implement the minimum primitives with NumPy/scikit-learn.
- [ ] Run the focused tests and then the full suite.
- [ ] Commit the implementation and evidence.

### Task 2: Bounded research runner and machine validation

**Files:**
- Create: `src/brace_msi/paper_fusion_runner.py`
- Create: `scripts/run_paper_fusion_sprint.py`
- Create: `configs/paper_fusion_sprint.json`
- Create: `tests/performance/test_paper_fusion_runner.py`

**Interfaces:**
- Consumes: Task 1 primitives.
- Produces: `run_paper_fusion_sprint(config_path, output_root)` and `validate_paper_fusion_output(output_root)`.

- [ ] Write tests for immutable manifests, resume behavior, single validation opening, resource receipts, negative-result retention, and A/B/C fixture execution.
- [ ] Run focused tests and verify RED.
- [ ] Implement the runner, atomic receipts, configuration hash, validation lock, and comparison table.
- [ ] Run focused tests and full suite.
- [ ] Commit.

### Task 3: Registered real A/B/C experiment

**Files:**
- Modify: `docs/EXPERIMENTS.md`
- Produce outside Git: `D:/brace-msi-paper-fusion/PAPER-FUSION-SPRINT-001/`

**Interfaces:**
- Consumes: Task 2 CLI/config and immutable official package paths.
- Produces: manifests, fold metrics, selected teachers, ensemble/student artifacts, resource receipts, final comparison JSON.

- [ ] Verify package hashes and freeze the experiment/config hashes before model fitting.
- [ ] Run a smoke subset and validate machine output.
- [ ] Run the bounded full matrix once; repair only technical failures without changing the frozen search space.
- [ ] Freeze winners, open public validation once, and validate output.
- [ ] Preserve every failed candidate and resource receipt.

### Task 4: BRACE integration, ablation report, and candidate release

**Files:**
- Modify: `src/brace_msi/action_sandbox.py`
- Modify: `src/brace_msi/cli.py`
- Create: `docs/results/PAPER-FUSION-SPRINT-001.md`
- Modify: `docs/STATUS.md`, `docs/TASKS.md`, `docs/RESEARCH_PROGRESS.md`, `docs/DECISION_LOG.md`, `docs/RISK_REGISTER.md`, `docs/SESSION_HANDOFF.md`

**Interfaces:**
- Consumes: frozen Task 3 candidate and receipts.
- Produces: allowlisted `paper_fusion_refit` action, result report, recovery state, and a release decision distinct from RC3.

- [ ] Write failing tests proving only frozen manifests and allowed paths can enter the sandbox.
- [ ] Implement the minimal integration and deterministic fallback.
- [ ] Generate static/continued-RC3/module/fusion ablations from actual receipts.
- [ ] Run focused tests, full regression, `pip check`, and output validator.
- [ ] Update SSOT with actual positive/negative results and commit; do not replace RC3 unless all release gates pass.
