# BRACE-MSI Competition Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one official-SDK-compatible Competition Core that trains at least one real parent-compatible candidate every round, uses PyTRiO-trained Qwen for experiment and deployment reasoning, selects only comparable legal artifacts, and ships separate local-test and formal-upload images.

**Architecture:** Keep the verified `contest_harness` and `brace_formal` platform boundary. Split the current large formal transaction into task profiling, history, recipe execution, evaluation/selection and orchestration modules; Qwen makes two host calls per round while deterministic code owns metric facts and official hard constraints. Train and record the Advisor outside the formal image, then bind only a platform-validated Sampler through `rnd.model()`.

**Tech Stack:** Python 3.10+, NumPy, `contest_harness` 1.0.2, PyTRiO, SwanLab, pytest, Docker/Linux amd64.

**Spec:** `docs/superpowers/specs/2026-11-20-competition-core-design.md`

## Global Constraints

- Every formal round trains at least one real candidate from the current official parent checkpoint before deploy/retain/rollback.
- Unknown tasks are numeric tabular classification or non-negative regression with the official package/SDK shape; routing must not depend on Gas/Bearing/Engine names.
- Do not add participant-defined Token, candidate-count, epoch, improvement-percentage or fixed safety thresholds; obey host-provided resource and artifact limits.
- Qwen receives no raw private rows; formal model access is only `rnd.model()`/`rnd.transport()` and every used call ID is cited by `finish`.
- Parent, candidate and historical artifacts are comparable only after evaluation on the same current validation fingerprint.
- Formal artifacts stay `contest.cpu-mlp.v1`, load/save/predict compatible and no larger than the official 64 MiB limit.
- Local-test and formal-upload images use separate Dockerfiles and explicit allowlists from the first implementation task onward.
- Formal image excludes data, model weights, test/simulation/report code, PyTRiO/SwanLab clients, Tokenizers, Samplers, caches and credentials.
- Preserve all historical RCs, failed runs and negative results; never overwrite source data or use an official trial without separate authorization.

## Review Focus

- An unseen task contract with an unfamiliar `dataset_key` but valid classification/regression parent must route by contract and checkpoint, not name; Task 2 pins this.
- Valid historical rows with changed feature schema must be excluded without breaking current-round training; Task 3 pins this.
- A Qwen response that asks to deploy a numerically worse or incomparable artifact must not control the selected artifact; Task 6 pins this.
- A malformed first Qwen response must still lead to a real fallback candidate and a complete two-call round; Tasks 5 and 7 pin this.
- Formal image construction must not accidentally copy local simulator, tests, PyTRiO/SwanLab or credentials; Task 8 pins this.

---

### Task 1: Freeze the verified platform boundary and characterize the current transaction

**Files:**
- Create: `tests/competition_core/test_platform_boundary.py`
- Create: `tests/competition_core/test_current_round_characterization.py`
- Modify: `docs/TASKS.md`

**Interfaces:**
- Consumes: `contest_harness.Round`, `brace_formal.submission.train(rnd)`, `brace_formal.submission.predict(sample, model_dir)`.
- Produces: frozen tests for two model calls, one real candidate, parent continuation, state save, finish references and prediction schema.

- [ ] **Step 1: Write characterization tests** that assert one classification and one regression round each call the host twice, train a checkpoint whose epoch/step state changes, submit a legal candidate, save state, cite both call IDs and emit valid predictions.
- [ ] **Step 2: Add negative characterization tests** for empty model receipts, wrong parent digest and an unloadable candidate; assert official SDK errors or parent retention rather than silent success.
- [ ] **Step 3: Run the tests before refactoring.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_platform_boundary.py tests/competition_core/test_current_round_characterization.py -q`

  Expected: PASS against current verified interfaces; any failure is documented before implementation continues.

- [ ] **Step 4: Commit the frozen boundary tests.**

  ```powershell
  git add tests/competition_core docs/TASKS.md
  git commit -m "test: freeze competition platform boundary"
  ```

### Task 2: Add task-contract and checkpoint-driven profiling

**Files:**
- Create: `src/brace_formal/profile.py`
- Create: `tests/competition_core/test_task_profile.py`
- Modify: `src/brace_formal/metrics.py`

**Interfaces:**
- Consumes: `task_contract: Mapping[str, Any]`, `FormalModel`, current `DataBatch` objects.
- Produces: `TaskProfile`, `build_task_profile(task_contract, model, training, validation) -> TaskProfile`, and `TaskProfile.as_dict() -> dict[str, Any]`.

- [ ] **Step 1: Write failing tests** for unknown dataset names, classification/regression contracts, metric direction, class imbalance, target range, missing values, group/time hints and feature-count mismatch.
- [ ] **Step 2: Run the focused test and verify failures.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_task_profile.py -q`

  Expected: FAIL because `brace_formal.profile` does not exist.

- [ ] **Step 3: Implement immutable `TaskProfile`** with fields `task`, `primary_metric`, `metric_direction`, `feature_count`, `class_count`, `sample_count`, `validation_count`, `label_summary`, `data_quality`, `group_hints`, `time_hints`, and `contract_fingerprint`.
- [ ] **Step 4: Implement `build_task_profile(...)`** so behavior derives only from task contract, parent metadata and aggregate data properties; treat `dataset_key` as an opaque identifier and reject contract/checkpoint task conflicts.
- [ ] **Step 5: Run focused and existing metric tests.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_task_profile.py tests/formal_runtime/test_metric_contract.py tests/formal_dev/test_official_metrics.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit.**

  ```powershell
  git add src/brace_formal/profile.py src/brace_formal/metrics.py tests/competition_core/test_task_profile.py
  git commit -m "feat: profile unknown competition tasks"
  ```

### Task 3: Persist legal historical data and artifacts through official state

**Files:**
- Create: `src/brace_formal/history.py`
- Create: `tests/competition_core/test_history_store.py`
- Modify: `src/brace_formal/data.py`
- Modify: `src/brace_formal/workspace.py`

**Interfaces:**
- Consumes: current `DataBatch`, restored `/state`, `rnd.history()` records, parent feature schema and official state byte limit.
- Produces: `HistoryStore.load(state_root, model) -> HistoryStore`, `HistoryStore.append(batch, round_index)`, `HistoryStore.training_batch(policy, current) -> DataBatch`, `HistoryStore.save(state_root)`, and `HistoryArtifactRef` records.

- [ ] **Step 1: Write failing tests** for exact state round-trip, legal replay, duplicate IDs, future-round rejection, changed feature schema, corrupt NPZ, symlink rejection and compressed state near the official 64 MiB boundary.
- [ ] **Step 2: Run the focused test and verify failures.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_history_store.py -q`

  Expected: FAIL because `HistoryStore` does not exist.

- [ ] **Step 3: Extend `DataBatch`** with a deterministic `select(indices) -> DataBatch` and `concat(batches) -> DataBatch` that preserve IDs, feature order, labels and source fingerprints.
- [ ] **Step 4: Implement `HistoryStore`** using compressed NumPy arrays plus JSON metadata, validating task, feature paths, round index and digests. Fill available official state capacity without a participant-defined sample-count cap; if exact rows cannot fit, preserve audit summaries and the newest complete legal rows that fit the host byte limit.
- [ ] **Step 5: Add history artifact references** without assuming raw data appears in `rnd.history()`; references are restorable only through official artifact APIs.
- [ ] **Step 6: Run focused, data and workspace tests.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_history_store.py tests/formal_runtime/test_agent_workspace.py tests/formal_runtime/test_model_core.py -q`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add src/brace_formal/history.py src/brace_formal/data.py src/brace_formal/workspace.py tests/competition_core/test_history_store.py
  git commit -m "feat: persist legal round history"
  ```

### Task 4: Replace the fixed portfolio with a parent-compatible recipe registry

**Files:**
- Create: `src/brace_formal/recipes.py`
- Create: `tests/competition_core/test_recipe_registry.py`
- Modify: `src/brace_formal/model.py`
- Modify: `src/brace_formal/portfolio.py`
- Modify: `tests/formal_runtime/test_model_core.py`
- Modify: `tests/formal_runtime/test_portfolio.py`

**Interfaces:**
- Consumes: `TaskProfile`, parent `FormalModel`, current/history `DataBatch`, a structured recipe configuration and host resource information.
- Produces: `TrainingRecipe`, `RecipeRegistry.available(profile)`, `RecipeRegistry.fallback(profile)`, `execute_recipe(parent, recipe, training_batch) -> CandidateResult`.

- [ ] **Step 1: Write failing registry tests** for classification weighting/balanced sampling, regression MSE/Huber/asymmetric loss, current-only/history replay, learning-rate/epoch overrides, parent-candidate averaging and task-incompatible recipes.
- [ ] **Step 2: Write failing model tests** for `FormalModel.fit(values, targets, epochs, *, sample_weights=None, loss="native", loss_parameters=None)` preserving current native behavior when optional arguments are absent.
- [ ] **Step 3: Run focused tests and verify failures.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_recipe_registry.py tests/formal_runtime/test_model_core.py -q`

  Expected: FAIL on missing registry and extended fit signature.

- [ ] **Step 4: Implement the extended `FormalModel.fit`** with weighted cross-entropy, weighted MSE, Huber and asymmetric regression gradients while retaining Adam state, clipping, deterministic shuffling and exact checkpoint schema.
- [ ] **Step 5: Implement `RecipeRegistry` and `execute_recipe`** so recipes declare compatibility and executed parameters; remove `retain` as a training recipe and keep old portfolio functions only as historical-development adapters.
- [ ] **Step 6: Run all model/recipe tests and save-load-predict equality.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_recipe_registry.py tests/formal_runtime/test_model_core.py tests/formal_runtime/test_portfolio.py tests/formal_dev/test_official_model.py -q`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add src/brace_formal/model.py src/brace_formal/recipes.py src/brace_formal/portfolio.py tests/competition_core/test_recipe_registry.py tests/formal_runtime/test_model_core.py tests/formal_runtime/test_portfolio.py
  git commit -m "feat: add adaptive parent compatible recipes"
  ```

### Task 5: Make Qwen proposals task-aware, executable and fallback-safe

**Files:**
- Modify: `src/brace_formal/agent.py`
- Create: `tests/competition_core/test_experiment_agent.py`
- Modify: `tests/formal_runtime/test_agent_workspace.py`

**Interfaces:**
- Consumes: `TaskProfile.as_dict()`, registry capability descriptors, aggregate history, host resource fields and later evaluation evidence.
- Produces: `ExperimentProposal(recipe_id, parameters, history_policy, hypothesis, rationale, call_id, parse_error)` and existing `DeploymentDecision` with explicit artifact choice.

- [ ] **Step 1: Write failing tests** for unknown tasks, executable parameter maps, no participant `max_tokens`, malformed/ambiguous JSON, unsupported recipe, service exception and aggregate-only prompts.
- [ ] **Step 2: Add a failing test** proving invalid first-call output returns a real `RecipeRegistry.fallback(profile)` proposal rather than `retain` or no training.
- [ ] **Step 3: Run focused tests and verify failures.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_experiment_agent.py -q`

  Expected: FAIL on the new proposal interface.

- [ ] **Step 4: Implement the proposal schema and parser** using registry-provided recipe IDs and parameter domains; preserve raw call IDs and parse receipts without storing raw private rows.
- [ ] **Step 5: Update deployment prompts** to cite metric contract, same-scope artifact table, resource evidence and legal artifact IDs; return a requested artifact ID plus rationale.
- [ ] **Step 6: Run agent and official host tests.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_experiment_agent.py tests/formal_runtime/test_agent_workspace.py tests/formal_runtime/test_release_host.py -q`

  Expected: PASS.

- [ ] **Step 7: Commit.**

  ```powershell
  git add src/brace_formal/agent.py tests/competition_core/test_experiment_agent.py tests/formal_runtime/test_agent_workspace.py
  git commit -m "feat: make agent proposals executable"
  ```

### Task 6: Implement same-scope parent/candidate/history selection

**Files:**
- Create: `src/brace_formal/selection.py`
- Create: `tests/competition_core/test_artifact_selection.py`
- Modify: `src/brace_formal/metrics.py`

**Interfaces:**
- Consumes: `MetricContract`, `ArtifactEvaluation` objects for parent/candidates/restored history, requested Qwen artifact ID and official hard failures.
- Produces: `select_artifact(contract, evaluations, requested_artifact_id) -> SelectionResult` with requested/applied choice, relation, reason and comparable-set receipt.

- [ ] **Step 1: Write failing tests** for higher/lower metrics, equal primary with auxiliary/cost tie-break, changed validation fingerprint, NaN/Inf, unloadable artifact, wrong Qwen arithmetic and valid historical rollback.
- [ ] **Step 2: Add the frozen official counterexamples** from O-PLATFORM-019 and the 0.10.6 wrong-deploy black-box test; assert the worse artifact is never applied.
- [ ] **Step 3: Run focused tests and verify failures.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_artifact_selection.py -q`

  Expected: FAIL because `brace_formal.selection` does not exist.

- [ ] **Step 4: Implement immutable `ArtifactEvaluation` and `SelectionResult`** and deterministic same-scope selection. Do not add fixed percentage gates; use primary direction, contract-declared auxiliary metrics and measured resource evidence.
- [ ] **Step 5: Run selection and metric tests.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_artifact_selection.py tests/formal_runtime/test_metric_contract.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit.**

  ```powershell
  git add src/brace_formal/selection.py src/brace_formal/metrics.py tests/competition_core/test_artifact_selection.py
  git commit -m "feat: select comparable competition artifacts"
  ```

### Task 7: Rebuild the formal round orchestrator from the new components

**Files:**
- Create: `src/brace_formal/round_core.py`
- Modify: `src/brace_formal/submission.py`
- Create: `tests/competition_core/test_round_core.py`
- Modify: `tests/official_sdk_v2/test_contest_submission.py`
- Modify: `tests/formal_runtime/test_submission.py`
- Modify: `tests/formal_runtime/test_ten_rounds.py`

**Interfaces:**
- Consumes: Tasks 2-6 interfaces and official `rnd` object.
- Produces: `run_competition_round(rnd) -> RoundOutcome`; `submission.train(rnd)` becomes a thin adapter; `submission.predict` remains independently callable.

- [ ] **Step 1: Write failing end-to-end tests** for unknown classification/regression tasks, two Qwen calls, at least one real candidate, history replay, candidate/parent/history selection, state recovery and independent prediction.
- [ ] **Step 2: Write failure-path tests** for invalid first call, failed candidate, invalid second call, metric conflict and interrupted state save; every recoverable case must still produce truthful records and no corrupt artifact.
- [ ] **Step 3: Run focused tests and verify failures.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core/test_round_core.py -q`

  Expected: FAIL because `run_competition_round` does not exist.

- [ ] **Step 4: Move orchestration from `submission.py` into `round_core.py`** and wire profile, history, registry, agent, evaluator and selector. Keep `submission.py` limited to official entry and prediction.
- [ ] **Step 5: Persist complete round receipts** including exact executed recipe, both call IDs, validation fingerprint, parent/candidate/history evaluations, requested/applied choice, resource stages and state/artifact digests.
- [ ] **Step 6: Run focused, official SDK and ten-round tests.**

  Run: `D:\anaconda3\python.exe -m pytest tests/competition_core tests/official_sdk_v2 tests/formal_runtime/test_submission.py tests/formal_runtime/test_ten_rounds.py -q`

  Expected: PASS.

- [ ] **Step 7: Run the full regression suite.**

  Run: `D:\anaconda3\python.exe -m pytest -q --tb=short`

  Expected: all tests pass.

- [ ] **Step 8: Commit.**

  ```powershell
  git add src/brace_formal/round_core.py src/brace_formal/submission.py tests/competition_core tests/official_sdk_v2/test_contest_submission.py tests/formal_runtime
  git commit -m "feat: run competition core rounds"
  ```

### Task 8: Separate local-test and formal-upload image supply chains

**Files:**
- Create: `Dockerfile.local-test`
- Modify: `Dockerfile.formal`
- Create: `configs/formal_runtime_allowlist.json`
- Create: `tests/system/test_dual_image_boundaries.py`
- Modify: `scripts/build_formal_release.py`
- Create: `scripts/build_local_test_image.py`

**Interfaces:**
- Consumes: Competition Core runtime modules and repository tree.
- Produces: local image tagged `LOCAL_TEST_ONLY`; formal image generated only from `configs/formal_runtime_allowlist.json`; machine-readable content manifests.

- [ ] **Step 1: Write failing tests** that prove the formal allowlist includes the fixed harness/SDK/runtime modules and excludes tests, scripts, docs, data, weights, reports, PyTRiO, SwanLab, Tokenizers, Samplers, caches and secret-like files.
- [ ] **Step 2: Add a failing cross-image test** proving local simulator/report tooling exists only in the local image build context.
- [ ] **Step 3: Run focused tests and verify failures.**

  Run: `D:\anaconda3\python.exe -m pytest tests/system/test_dual_image_boundaries.py -q`

  Expected: FAIL because the separate allowlist/build path is absent.

- [ ] **Step 4: Implement both build paths** without copying the repository root and deleting files afterward; each path must construct its context from an explicit inclusion list.
- [ ] **Step 5: Run release-builder and boundary tests.**

  Run: `D:\anaconda3\python.exe -m pytest tests/system/test_dual_image_boundaries.py tests/system/test_release_builder.py tests/formal_runtime/test_formal_release.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit.**

  ```powershell
  git add Dockerfile.local-test Dockerfile.formal configs/formal_runtime_allowlist.json scripts/build_formal_release.py scripts/build_local_test_image.py tests/system/test_dual_image_boundaries.py
  git commit -m "build: separate local and formal images"
  ```

### Task 9: Build the official-style local simulator and report for known and unknown tasks

**Files:**
- Create: `src/brace_msi/competition_simulator.py`
- Create: `scripts/run_competition_simulation.py`
- Create: `scripts/render_competition_report.py`
- Create: `tests/system/test_competition_simulator.py`
- Create: `configs/competition_simulation.json`

**Interfaces:**
- Consumes: formal image/entry, official training packages and registered same-format surrogate task packages.
- Produces: ten-round host frames, model receipts, parent/history/state/candidate artifacts, predictions, `report.json` and official-style `report.html` marked local simulation.

- [ ] **Step 1: Write failing simulator tests** for classification/regression, opaque task names, ten rounds, two calls per round, every-round candidate training, host resource fields, history data, parent chain and final prediction.
- [ ] **Step 2: Write report tests** asserting all rounds show hypothesis, executed recipe, metrics, requested/applied artifact, CPU/RSS/Token and no claim of official hidden score.
- [ ] **Step 3: Run focused tests and verify failures.**

  Run: `D:\anaconda3\python.exe -m pytest tests/system/test_competition_simulator.py -q`

  Expected: FAIL because the simulator does not exist.

- [ ] **Step 4: Implement the simulator around official SDK frames** rather than a parallel custom protocol; do not feed final confirmation metrics back into policy.
- [ ] **Step 5: Implement the JSON/HTML report from the same receipts.**
- [ ] **Step 6: Run focused tests and one smoke simulation.**

  Run: `D:\anaconda3\python.exe -m pytest tests/system/test_competition_simulator.py -q`

  Run: `D:\anaconda3\python.exe scripts/run_competition_simulation.py --config configs/competition_simulation.json --output D:/brace-msi-competition/COMPETITION-CORE-SMOKE-001`

  Expected: tests PASS and smoke summary `valid=true`.

- [ ] **Step 7: Commit.**

  ```powershell
  git add src/brace_msi/competition_simulator.py scripts/run_competition_simulation.py scripts/render_competition_report.py tests/system/test_competition_simulator.py configs/competition_simulation.json
  git commit -m "feat: simulate official competition rounds"
  ```

### Task 10: Run the registered performance and generalization experiment matrix

**Files:**
- Create: `configs/competition_core_experiments.json`
- Create: `scripts/run_competition_core_experiments.py`
- Create: `tests/system/test_competition_experiment_manifest.py`
- Modify: `docs/EXPERIMENTS.md`
- Modify after completion: `docs/results/COMPETITION-CORE-EXP-001.md`

**Interfaces:**
- Consumes: official A/B/C packages, registered same-format surrogate classification/regression tasks, Competition Core simulator and recipe registry.
- Produces: resumable experiment manifest, per-round receipts, static/fixed-update/Competition-Core comparisons and frozen winning configuration without changing formal protocol.

- [ ] **Step 1: Register `COMPETITION-CORE-EXP-001`** in `docs/EXPERIMENTS.md` with source hashes, development/confirmation boundaries, baseline definitions, resource receipts and stop conditions; do not invent a minimum percentage improvement.
- [ ] **Step 2: Write manifest tests** asserting no task-name recipe routing, no final confirmation feedback, immutable source files, exact parent checkpoint lineage and resumable unique output roots.
- [ ] **Step 3: Run manifest tests and verify the runner is initially incomplete.**
- [ ] **Step 4: Implement the resumable runner** for static parent, simple fixed update and Competition Core; record primary/auxiliary metrics, worst stage, recovery, CPU, wall, RSS, Token and model size.
- [ ] **Step 5: Run Smoke first** on one classification and one regression round; validate outputs before full training.
- [ ] **Step 6: Run A/B/C and surrogate tasks** with no official trial or hidden data. Let Qwen/registry use host resource fields rather than participant hard limits.
- [ ] **Step 7: Freeze the configuration selected by development evidence** and open each registered confirmation partition once; retain all negative results.
- [ ] **Step 8: Write the evidence report and machine validator output.**
- [ ] **Step 9: Run related tests plus full regression.**

  Run: `D:\anaconda3\python.exe -m pytest tests/system/test_competition_experiment_manifest.py tests/competition_core -q`

  Run: `D:\anaconda3\python.exe -m pytest -q --tb=short`

  Expected: PASS; experiment validator reports `valid=true` independently of whether performance improves.

- [ ] **Step 10: Commit code, config and aggregate evidence only.**

  ```powershell
  git add configs/competition_core_experiments.json scripts/run_competition_core_experiments.py tests/system/test_competition_experiment_manifest.py docs/EXPERIMENTS.md docs/results/COMPETITION-CORE-EXP-001.md
  git commit -m "exp: validate competition core performance"
  ```

### Task 11: Train and validate the PyTRiO Competition Agent, then record SwanLab evidence

**Files:**
- Modify: `src/brace_msi/formal_advisor_sft.py`
- Modify: `scripts/run_formal_advisor_sft.py`
- Create: `configs/competition_agent_sft.json`
- Create: `tests/agent/test_competition_agent_sft.py`
- Modify: `scripts/build_final_swanlab_spool.py`
- Modify: `docs/EXPERIMENTS.md`
- Create after completion: `docs/results/COMPETITION-AGENT-SFT-001.md`

**Interfaces:**
- Consumes: sanitized experiment/deployment trajectories from Task 10 and registered numeric-error cases; PyTRiO credentials from environment only.
- Produces: frozen training/holdout manifests, persisted `trio://` Sampler receipt outside Git, base-vs-Sampler evaluation, sanitized SwanLab spool and public run link.

- [ ] **Step 1: Register `COMPETITION-AGENT-SFT-001`** with trajectory split by task/scenario family, source hashes, budget accounting and no hidden/raw-row content.
- [ ] **Step 2: Write failing tests** for trajectory redaction, train/holdout separation, assistant-only loss, structure, executable recipes, metric arithmetic, history use and reload evaluation.
- [ ] **Step 3: Run tests and verify failures for the new trajectory schema.**
- [ ] **Step 4: Extend the SFT builder** without changing the formal image; save no API key, raw private row, full prompt or Sampler path to Git/SwanLab.
- [ ] **Step 5: Evaluate the platform base Qwen** on the frozen holdout and save aggregate receipts.
- [ ] **Step 6: Run the authorized PyTRiO LoRA/SFT job** only after the frozen hash check passes; persist the returned Sampler outside Git.
- [ ] **Step 7: Recreate a sampling client from the persisted path** and evaluate the same untouched holdout; report both positive and negative cases.
- [ ] **Step 8: Build and scan the SwanLab spool**, then explicitly sync the same run ID; record the public link and aggregate fields.
- [ ] **Step 9: Commit code/config/tests and sanitized aggregate report.**

  ```powershell
  git add src/brace_msi/formal_advisor_sft.py scripts/run_formal_advisor_sft.py scripts/build_final_swanlab_spool.py configs/competition_agent_sft.json tests/agent/test_competition_agent_sft.py docs/EXPERIMENTS.md docs/results/COMPETITION-AGENT-SFT-001.md
  git commit -m "exp: train competition decision agent"
  ```

### Task 12: Build, verify and freeze the final local and formal release candidates

**Files:**
- Modify: `scripts/verify_workspace_v2_image.py`
- Modify: `scripts/verify_formal_image.py`
- Create: `scripts/audit_competition_release.py`
- Create: `tests/system/test_competition_release_audit.py`
- Modify: `docs/RELEASE_CANDIDATE.md`
- Create after completion: `docs/results/COMPETITION-CORE-RC-001.md`
- Modify: `docs/STATUS.md`, `docs/TASKS.md`, `docs/RESEARCH_PROGRESS.md`, `docs/RISK_REGISTER.md`, `docs/SESSION_HANDOFF.md`

**Interfaces:**
- Consumes: frozen runtime commit, frozen recipe configuration, platform-validated model selection, formal allowlist and local test image.
- Produces: local-test image, clean formal image, reloadable `docker save` archive, SHA-256/content manifest, 4CPU/8GiB acceptance, HTML/JSON report and release decision.

- [ ] **Step 1: Write failing release-audit tests** for source/image mismatch, forbidden files, missing SDK files, absent dual calls, zero-candidate rounds, wrong-deploy acceptance, unknown task failure, model reload mismatch and archive not produced by `docker save`.
- [ ] **Step 2: Implement `audit_competition_release(...)`** returning per-gate `PASS/FAIL/BLOCKED_EXTERNAL` with evidence paths and exact hashes.
- [ ] **Step 3: Build and test the local image** with the complete simulator, tests and reports; mark it `LOCAL_TEST_ONLY`.
- [ ] **Step 4: Build the formal image from the allowlist** and scan its filesystem for data, weights, reports, simulators, tests, PyTRiO/SwanLab, Tokenizers, Samplers, caches and credentials.
- [ ] **Step 5: Run official SDK tests inside the exact formal image** under Linux amd64, nonroot, read-only root, `--network=none`, `--cpus=4`, `--memory=8g`.
- [ ] **Step 6: Run A/B/C plus opaque same-format classification/regression ten-round simulations** against the exact formal image; assert every round has real training and both call IDs, and final predictions are valid.
- [ ] **Step 7: Run wrong-deploy and history-rollback black-box tests** against the exact image.
- [ ] **Step 8: Execute full clean-environment regression and `pip check`.**
- [ ] **Step 9: Export with `docker save`, reload, verify identical image ID, compute archive SHA-256 and bind source commit, model selection and SwanLab link in the release manifest.**
- [ ] **Step 10: Generate the final official-style HTML/JSON report and release audit.** Do not upload or consume an official trial in this task.
- [ ] **Step 11: Update SSOT documents and commit the frozen RC evidence.**

  ```powershell
  git add scripts/verify_workspace_v2_image.py scripts/verify_formal_image.py scripts/audit_competition_release.py tests/system/test_competition_release_audit.py docs/RELEASE_CANDIDATE.md docs/results/COMPETITION-CORE-RC-001.md docs/STATUS.md docs/TASKS.md docs/RESEARCH_PROGRESS.md docs/RISK_REGISTER.md docs/SESSION_HANDOFF.md
  git commit -m "release: freeze competition core candidate"
  ```

## Execution Order and Stop Conditions

Execute Tasks 1-9 sequentially because each publishes interfaces consumed by the next. Task 10 may run only after the exact ten-round orchestrator and local simulator pass. Task 11 may run only after Task 10 freezes sanitized trajectories. Task 12 may run only after the chosen runtime and Advisor configuration are frozen.

At any task boundary, stop that task and preserve evidence if the official parent schema, SDK contract, source data immutability or formal image allowlist is violated. Ordinary test, implementation and local training failures are fixed within the same task; they do not authorize official uploads or hidden-data use.
