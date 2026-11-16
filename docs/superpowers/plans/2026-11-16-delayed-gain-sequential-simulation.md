# Delayed-Gain Sequential Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a ten-round simulation in which arrival performance drives the current decision and the next batch settles the previous deployment's delayed gain.

**Architecture:** Extend the existing natural-stream simulator with an explicit `ArrivalEvidence` input to the native runtime and a one-round predecessor shadow. Preserve ScoreVault sealing, explicit Update/Gate, parent-chain commits and one-time confirmation.

**Tech Stack:** Python 3.11+, NumPy, existing native checkpoint runtime, pytest, SwanLab offline export.

**Spec:** `docs/superpowers/specs/2026-11-16-delayed-gain-sequential-simulation-design.md`

## Global Constraints

- Do not modify raw data, frozen RC tags or previous experiment artifacts.
- Hidden test remains unavailable; all new results are local proxy evidence.
- No confirmation metric may enter ActionPolicy or select a round.
- Use TDD and retain negative evidence.

## Review Focus

- Classification and regression metric directions must both yield positive delayed gain for improvement.
- Round 1 and retain rounds must not fabricate delayed gain.
- Shadow inference must use exactly the same arrival sample IDs.
- Missing workspace replay must degrade safely.
- PyTRiO failure must retain the deterministic safety boundary.

---

### Task 1: Arrival evidence runtime contract

**Files:**
- Modify: `src/brace_msi/platform_runtime.py`
- Test: `tests/platform_runtime/test_platform_runtime.py`

**Interfaces:**
- Produces: `ArrivalEvidence`, `start_round(..., arrival_evidence=...)`, sequential decision receipts.

- [ ] Write failing tests for visible arrival evidence and evidence-triggered retain/train.
- [ ] Run targeted tests and confirm expected failure.
- [ ] Implement the minimal runtime contract and sequential policy.
- [ ] Run targeted tests and commit.

### Task 2: One-round delayed-gain settlement

**Files:**
- Modify: `src/brace_msi/official_flow_simulation.py`
- Test: `tests/platform_runtime/test_official_flow_streams.py`

**Interfaces:**
- Consumes: `ArrivalEvidence`.
- Produces: `arrival_metrics`, `delayed_gain`, predecessor shadow receipts and resource accounting in each round.

- [ ] Write failing tests for next-round paired settlement and retain behavior.
- [ ] Run targeted tests and confirm expected failure.
- [ ] Implement prediction, pairing and runtime evidence wiring.
- [ ] Run targeted tests and commit.

### Task 3: V2 report and complete experiment

**Files:**
- Modify: `scripts/run_official_flow_simulation.py`
- Modify: `scripts/render_official_flow_report.py`
- Test: `tests/system/test_official_flow_report.py`
- Update: project SSOT documents and `docs/results/DELAYED-GAIN-SIM-001.md`

**Interfaces:**
- Consumes: V2 task summaries.
- Produces: machine JSON, readable HTML and offline SwanLab directories.

- [ ] Write failing report-schema tests.
- [ ] Implement V2 fields and evidence labels.
- [ ] Run smoke, then full A/B/C ten-round experiment in a new output root.
- [ ] Validate artifacts, run the full suite, update SSOT and commit.
