# Controlled Dual-Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the preregistered ten-candidate schedule with a prefix-safe ten-batch decision loop containing a lightweight adaptive decision layer and a deterministic, isolated execution layer.

**Architecture:** `RuntimeAdapter` materializes only the current legal prefix, `DecisionController` ranks actions using lightweight outcome statistics and optionally Qwen, and `CandidateExecutor` trains zero to two isolated candidates against four disjoint data uses. A transactional history records delayed shadow-model reward, resource use, deployment, and recovery.

**Tech Stack:** Python 3.12, NumPy, SciPy, scikit-learn, PyTRiO 0.2.9, pytest, Docker.

**Spec:** `docs/superpowers/specs/2026-11-13-controlled-dual-loop-design.md`

## Global Constraints

- Preserve all frozen RCs, historical evidence, original packages and public-validation exposure records.
- Never expose future batches, raw source roots, secrets, private rows or reversible features to candidates or public logs.
- Use TDD for production changes and commit each task with fresh verification.
- Do not consume official trial runs or retrain Qwen.
- Core v1 supports numeric tabular classification/regression; sequence support is interface-only.

## Review Focus

- Future files present beside current data must remain undiscoverable to round workers.
- Gate and Anchor samples must never enter same-round training or preprocessing.
- Crash recovery must not repeat a committed batch or double-charge resources.
- Shadow reward must compare active and predecessor predictions on identical samples.
- Restricted patches must fail closed on resource abuse and forbidden capabilities.

---

### Task 1: Evidence, decisions, and SSOT

**Files:** Modify the SSOT documents; add the approved spec and this plan.

**Interfaces:** Produces the locked dual-loop task graph and evidence IDs consumed by all later tasks.

- [ ] Register the 13 lecture screenshots with SHA-256 and evidence class.
- [ ] Append the dual-loop decision without rewriting D-001..D-050.
- [ ] Update status, task dependencies, architecture, workflow, protocol and handoff.
- [ ] Run documentation consistency searches and commit.

### Task 2: Four buffers and round data capability

**Files:** Create `src/brace_msi/online_data.py`; create `tests/dual_loop/test_online_data.py`.

**Interfaces:** Produces `BufferRole`, `BufferSlice`, `RoundDataManifest`, `DatasetHandle`, `partition_initial_data`, `partition_feedback`, `materialize_round_data`.

- [ ] Write failing tests for disjoint roles, one-round Gate embargo, Update+Replay preprocessing input and future-decoy exclusion.
- [ ] Run tests and confirm failures are caused by missing interfaces.
- [ ] Implement minimal immutable manifests, partitioning and isolated materialization.
- [ ] Run focused and full tests; commit.

### Task 3: Lightweight action values and Pareto planning

**Files:** Create `src/brace_msi/policy_learning.py`; create `tests/dual_loop/test_policy_learning.py`.

**Interfaces:** Produces `EvidenceState`, `ActionObservation`, `ActionStats`, `ActionValueTable`, `ParetoAction`, `rank_actions`.

- [ ] Write failing tests for per-task isolation, task rename invariance, weak priors, Pareto elimination and delayed-reward-only updates.
- [ ] Implement bounded statistics without a learned model or dataset identity.
- [ ] Verify focused and full tests; commit.

### Task 4: Shadow reward and transactional ten-batch state

**Files:** Create `src/brace_msi/dual_loop.py`; create `tests/dual_loop/test_dual_loop.py`.

**Interfaces:** Produces `DecisionContext`, `CandidateSpec`, `DecisionPlan`, `CandidateOutcome`, `PolicyState`, `RoundCommit`, `DualLoopController`.

- [ ] Write failing tests for one decision per batch, zero-to-two candidates, result-triggered escalation, paired shadow reward and atomic recovery.
- [ ] Implement the prefix-safe transaction state machine and low-confidence shadow fallback.
- [ ] Verify focused and full tests; commit.

### Task 5: Evidence-triggered PyTRiO advisor

**Files:** Modify `src/brace_msi/pytrio_agent.py`; create `tests/dual_loop/test_agent_advisor.py`.

**Interfaces:** Produces `AgentTrigger`, `RetryingProposalAdvisor`; consumes `DecisionContext` and returns a validated optional proposal plus receipt.

- [ ] Write failing tests for no-call stable rounds, trigger conditions, one retry, deterministic degradation and receipt accounting.
- [ ] Implement the adapter without retraining or requiring a Sampler path.
- [ ] Verify focused and full tests; commit.

### Task 6: Restricted plugin patch sandbox

**Files:** Create `src/brace_msi/plugin_sandbox.py`; create `tests/dual_loop/test_plugin_sandbox.py`.

**Interfaces:** Produces `PluginSlot`, `PatchRequest`, `PatchReceipt`, `validate_patch`, `run_patch_candidate`.

- [ ] Write failing tests covering forbidden imports, files, network, subprocess, reflection, dynamic execution, infinite loops, nonfinite values, wrong shape and nondeterminism.
- [ ] Implement AST validation, fixed signatures and resource-limited child execution.
- [ ] Verify focused and full tests; commit.

### Task 7: Model registration gate and candidate execution

**Files:** Create `src/brace_msi/model_registry.py`; modify the existing official trainer boundary; create `tests/dual_loop/test_model_registry.py`.

**Interfaces:** Produces `ModelRegistration`, `RegistrationReceipt`, `RegisteredModelPool`; consumes DatasetHandles and candidate specs.

- [ ] Write failing tests for capability declarations, save/load prediction identity, unsupported incremental actions and Tier 2 fail-closed registration.
- [ ] Register existing official/scikit-learn models first; keep CatBoost disabled until its compatibility receipt passes.
- [ ] Verify focused and full tests; commit.

### Task 8: Harness integration and formal simulation

**Files:** Modify `src/brace_msi/official_agent_harness.py` and CLI wiring; create `tests/dual_loop/test_official_integration.py`.

**Interfaces:** Consumes all prior task interfaces and produces ten committed round records plus an auditable run summary.

- [ ] Write failing end-to-end tests for two protocol modes, prefix-only access, three real experiment chains, rollback, crash recovery and identity-blind tasks.
- [ ] Replace frozen schedule overrides with the dual-loop controller while retaining the old path for historical reproduction only.
- [ ] Verify focused and full tests; commit.

### Task 9: Pre-registered A/B/C comparison and release gate

**Files:** Register a new experiment ID and add result/acceptance documents only after runs finish.

**Interfaces:** Produces static, fixed-update, deterministic dual-loop and PyTRiO dual-loop comparisons plus resource receipts.

- [ ] Freeze train-internal ordered/grouped ten-batch manifests and data fingerprints.
- [ ] Run low-cost smoke, then bounded A/B/C development comparisons without using official trials.
- [ ] Record positive and negative results, shadow attribution confidence and public exposure boundaries.
- [ ] Run full regression, clean-environment install and Docker 4-core/8GB/under-2GB acceptance.
- [ ] Freeze a new RC only if every spec gate passes; otherwise preserve the current RC and record blockers.

