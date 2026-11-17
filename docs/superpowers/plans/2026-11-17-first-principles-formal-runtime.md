# BRACE-MSI Minimal Formal Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the failed formal adapter with a minimal workspace v2 runtime that makes one genuine host model call per round, continues the declared parent checkpoint, survives ten rounds, and ships as a clean Docker image.

**Architecture:** A small `brace_formal` package owns only checkpoint continuation, strict data parsing, bounded Agent proposal parsing, one-round orchestration, and prediction. The official SDK remains unmodified and owns framing, model receipts, artifact transfer, state and prediction IO.

**Tech Stack:** Python 3.12, NumPy 1.26.4, official `contest_harness` 1.0.2, pytest, Docker.

**Spec:** `docs/superpowers/specs/2026-11-17-first-principles-formal-runtime-design.md`

## Global Constraints

- Do not modify the official SDK sources.
- Do not include secrets, datasets, model weights, reports, PyTRiO private clients or SwanLab in the formal image.
- Write tests before production changes and observe RED before GREEN.
- Preserve all historical RCs and failed evidence.
- Do not consume an official trial during implementation.

## Review Focus

- `rnd.max_output_tokens < 256` must still issue one valid call.
- Host model aliases/Sampler paths must not be compared against a hard-coded model name.
- A valid response without `usage` must still produce an Agent decision.
- Retain and rollback-like safety outcomes must still cite a real call ID.
- A persisted `/workspace` across ten rounds must never collide on state or candidate directories.

### Task 1: Formal Agent boundary and per-round workspace

**Files:** create `src/brace_formal/agent.py`, `src/brace_formal/workspace.py`; create tests under `tests/formal_runtime/`.

**Produces:** `request_proposal(rnd, context) -> AgentDecision`; `create_round_paths(root, round_index, stage_id) -> RoundPaths`.

- [x] Write failing tests for all five Review Focus cases owned by this task.
- [x] Run the focused tests and confirm expected failures.
- [x] Implement direct `rnd.model()` call, strict bounded JSON parsing and unique round paths.
- [x] Run focused tests and the full suite.
- [x] Commit.

### Task 2: Minimal parent-compatible training and prediction core

**Files:** create `src/brace_formal/model.py`, `data.py`, `metrics.py`; create focused tests.

**Consumes:** official parent checkpoint path and current public JSONL.

**Produces:** strict load/predict/fit/save, deterministic train/validation parsing and task metrics.

- [x] Write differential tests against the existing verified native model for load, one epoch, save/reload and prediction.
- [x] Observe RED for the missing formal core.
- [x] Implement only the required NumPy continuation code.
- [x] Run focused tests and the full suite.
- [x] Commit.

### Task 3: One-round workspace v2 orchestration

**Files:** create `src/brace_formal/submission.py`; modify `submission/contest_submission.py`; create official SDK transcript tests.

**Consumes:** Task 1 decision and paths; Task 2 model/data APIs.

**Produces:** `TASKS`, `train(rnd)`, `predict(sample, model_dir)`.

- [ ] Write failing transcript tests for train, retain, candidate accept/reject, state save, history citation and predict.
- [ ] Observe RED.
- [ ] Implement one candidate maximum, parent retain fallback and platform measurement selection.
- [ ] Run focused tests, official SDK tests and the full suite.
- [ ] Commit.

### Task 4: Ten-round independent simulator and machine report

**Files:** create `tests/formal_runtime/test_ten_rounds.py`; create/update local-only simulator scripts outside the formal package.

**Produces:** A/B/C ten-round acceptance JSON and official-style HTML clearly marked local/non-scoring.

- [ ] Write a failing ten-round test that persists state and changes the parent artifact each round.
- [ ] Observe RED.
- [ ] Implement the smallest simulator changes needed.
- [ ] Run A/B/C ten-round protocol tests and verify 30 real model call receipts.
- [ ] Commit.

### Task 5: Clean formal Docker release

**Files:** create `Dockerfile.formal`; create release allowlist/audit tests and release script.

**Produces:** clean Linux image and `docker save` tar with SHA-256 evidence.

- [ ] Write a failing allowlist test proving the current full wheel is too broad.
- [ ] Observe RED.
- [ ] Build the allowlisted image with only SDK, entrypoints, NumPy and `brace_formal`.
- [ ] Verify 4-core/8-GB/offline ten-round run, independent prediction, artifact size, nonroot, save/load and禁入扫描.
- [ ] Run the full suite and commit evidence.

### Task 6: Performance integration after protocol gate

**Files:** only Task 2/3 policy surfaces plus pre-registered train-internal experiments.

- [ ] Use existing A/B/C evidence to define a bounded matrix without reusing exposed confirmation sets for selection.
- [ ] Compare retain, 1-epoch continuation and at most two mature parent-compatible recipes.
- [ ] Promote only methods with cross-round positive trend and acceptable CPU cost.
- [ ] Re-run the complete Task 4/5 acceptance once and freeze the new RC.

## Execution Ruling

The user explicitly requested autonomous inline execution after audit and forbade repeated approval pauses. Therefore this plan uses `executing-plans`; the written spec and plan remain reviewable, but implementation proceeds without another approval round.
