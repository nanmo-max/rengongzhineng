# Native Competitive RC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete platform-native competitive RC without modifying `0.6.0rc1`.

**Architecture:** Prove the native executor against the official trainer first, then migrate frozen schedules and a task-contract gate, add bounded PyTRiO/retain behavior, and finish with one frozen confirmation plus SwanLab and Docker release evidence.

**Tech Stack:** Python 3.11, NumPy, pytest, PyTRiO, SwanLab, Docker/PowerShell.

**Spec:** `docs/superpowers/specs/2026-11-15-native-competitive-rc-design.md`

## Global Constraints

- Do not modify historical RC tags, raw data, or historical results.
- No new HPO, SFT, paper reproduction, or official trial for basic debugging.
- Public validation is read once only after configuration freeze.
- Secrets and sample-level data never enter Git or public SwanLab.

## Review Focus

- Exact optimizer/state parity across classification and regression.
- Retain must not be counted as a trained/rejected candidate.
- Gate configuration must not use public validation feedback.
- PyTRiO fallback must be explicit and cannot masquerade as Agent evidence.
- Release image must contain no data, weights, or credentials.

---

### Task 1: Native parity and receipt counterfactual

**Files:** modify `tests/platform_runtime/test_platform_runtime.py`; create focused parity helper/test as needed; no production change until RED.

- [ ] Add parameterized A/B/C official-vs-Native one-epoch state tests and Native 1+1-vs-2 test.
- [ ] Run tests and observe expected parity failures or missing API.
- [ ] Make the minimum executor correction and rerun focused plus official trainer tests.
- [ ] Produce a read-only counterfactual summary from the existing 30 receipts.
- [ ] Commit with SSOT evidence updates.

### Task 2: Retain, frozen schedules, and task-contract Gate

**Files:** modify `src/brace_msi/platform_runtime.py`, CLI/config, and platform runtime tests.

- [ ] Add failing tests for zero-candidate retain, frozen schedule selection, C sub-5% positive gain, B bounded anchor risk, and no public-validation dependency.
- [ ] Implement minimal policy/Gate changes while preserving parent schema and atomic state.
- [ ] Run focused and full regression; commit with decision receipts.

### Task 3: Frozen local candidate and one confirmation

**Files:** add one registered config and result validator; outputs outside Git except aggregate report.

- [ ] Run train-internal ten-round A/B/C candidate and machine validation.
- [ ] Freeze configuration and hashes.
- [ ] Read public validation once; accept only if all tasks do not regress and at least two improve.
- [ ] Commit aggregate evidence without data or weights.

### Task 4: Native PyTRiO and SwanLab release record

**Files:** reuse existing adapters; add only Native-entry integration tests/recording gaps.

- [ ] Add failing tests proving fallback retains and Token-zero never counts as Agent evidence.
- [ ] Run at least three authorized Native PyTRiO calls, execute at least one valid suggestion, and preserve redacted receipts.
- [ ] Run final frozen A/B/C workflow with SwanLab aggregate logging and verify public field whitelist.
- [ ] Commit aggregate links and hashes; never commit credentials or full Sampler path.

### Task 5: Docker release candidate

**Files:** Docker/release metadata and current evidence documents only.

- [ ] Run complete regression and clean dependency checks.
- [ ] Build linux/amd64 image; test 4 CPU/8 GiB/read-only/network-none fallback, parent chain, independent prediction and recovery.
- [ ] Verify image <2 GiB, checkpoint <64 MiB, secret/data/weight scan, then `docker save` and `docker load`.
- [ ] Run fresh whole-branch review, fix Important/Critical findings, tag the new RC without moving historical tags.

