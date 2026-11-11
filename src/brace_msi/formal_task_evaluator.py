"""Real CPU evaluator that adapts task streams to the shared-policy search contract."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Mapping

from .budget import BudgetLimits
from .data.types import TaskStream
from .formal_development import (
    FormalRunConfig,
    create_local_checkpoint,
    run_formal_development_experiment,
)
from .official_metrics import higher_is_better
from .safety import GateConfig
from .unified_optimization import EvaluationMetrics
from .unified_policy import SharedPolicyConfig


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _phase_sha256(stream: TaskStream) -> str:
    return _canonical_sha256(
        {
            "initial": list(stream.initial.sample_ids),
            "development": [
                {"batch": batch.batch_id, "samples": list(batch.sample_ids)}
                for batch in stream.development
            ],
            "sealed_loaded": False,
        }
    )


class FormalTaskEvaluator:
    """Evaluate all policies on identical unsealed streams and local checkpoints."""

    def __init__(
        self,
        *,
        streams: Mapping[str, TaskStream],
        runtime_root: Path,
        seed: int,
        baseline_shared_config: SharedPolicyConfig,
        mlp_max_iter: int = 80,
    ) -> None:
        if not streams:
            raise ValueError("at least one task stream is required")
        if mlp_max_iter < 1:
            raise ValueError("mlp_max_iter must be positive")
        for key, stream in streams.items():
            if stream.sealed:
                raise ValueError(f"terminal data must not be loaded during development: {key}")
            if len(stream.development) != 10:
                raise ValueError("every development stream must contain ten rounds")
        self.streams = dict(streams)
        self.runtime_root = Path(runtime_root).resolve()
        self.seed = seed
        self.baseline_shared_config = baseline_shared_config
        self.mlp_max_iter = mlp_max_iter

    @staticmethod
    def _task_directory(task_key: str) -> str:
        return "task-" + hashlib.sha256(task_key.encode("utf-8")).hexdigest()[:12]

    def _run_config(
        self, stream: TaskStream, shared: SharedPolicyConfig
    ) -> FormalRunConfig:
        development_rows = sum(len(batch.y) for batch in stream.development)
        total_rows = len(stream.initial.y) + development_rows
        minimum_validation = max(
            4,
            min(16, min(max(1, len(batch.y) // 4) for batch in stream.development)),
        )
        return FormalRunConfig(
            seed=self.seed,
            budget=BudgetLimits(
                max_candidates=10,
                max_training_samples=max(10_000, total_rows * 10),
                max_wall_seconds=1200.0,
                max_cpu_seconds=1200.0,
            ),
            gate=GateConfig(
                min_validation_samples=minimum_validation,
                min_primary_improvement=0.0,
                max_anchor_degradation=1e12,
            ),
            minimum_candidate_events=0,
            replay_max_samples=max(1_000, min(50_000, total_rows * 2)),
            performance_drop_threshold=0.0,
            update_drop_threshold=0.0,
            refit_drop_threshold=1.0,
            drift_threshold=1.0,
            high_drift_threshold=1.0,
            mlp_max_iter=self.mlp_max_iter,
            validation_fraction=0.25,
            shared_policy_config=shared,
        )

    def _checkpoint(self, task_key: str, stream: TaskStream) -> Path:
        directory = self.runtime_root / self._task_directory(task_key)
        checkpoint = directory / "initial-checkpoint.pkl"
        if not checkpoint.exists():
            create_local_checkpoint(
                stream,
                checkpoint,
                self._run_config(stream, self.baseline_shared_config),
            )
        return checkpoint

    def evaluate(
        self,
        *,
        task_key: str,
        policy_name: str,
        candidate_id: str | None,
        shared_config: SharedPolicyConfig | None,
    ) -> EvaluationMetrics:
        try:
            stream = self.streams[task_key]
        except KeyError as exc:
            raise ValueError(f"unknown task key: {task_key}") from exc
        policy_map = {
            "static": "static",
            "fixed_low_cost": "fixed_low_cost",
            "performance_triggered": "normalized_performance_triggered",
            "brace": "unified_brace",
        }
        try:
            formal_policy = policy_map[policy_name]
        except KeyError as exc:
            raise ValueError(f"unsupported policy: {policy_name}") from exc
        selected_config = (
            shared_config if policy_name == "brace" else self.baseline_shared_config
        )
        if selected_config is None:
            raise ValueError("BRACE evaluation requires a shared config")
        checkpoint = self._checkpoint(task_key, stream)
        config_hash = _canonical_sha256(asdict(selected_config))[:12]
        candidate_component = (
            hashlib.sha256(str(candidate_id).encode("utf-8")).hexdigest()[:12]
            if candidate_id is not None
            else "baseline"
        )
        output_dir = (
            self.runtime_root
            / self._task_directory(task_key)
            / "evaluations"
            / f"{policy_name}-{candidate_component}-{config_hash}"
        )
        run_config = self._run_config(stream, selected_config)
        result = run_formal_development_experiment(
            stream,
            policy_name=formal_policy,
            checkpoint_path=checkpoint,
            output_dir=output_dir,
            config=run_config,
        )
        metric_name = result["primary_metric_name"]
        primary_key = "macro_f1" if metric_name == "macro_f1" else "rmse"
        resources = result["resources"]
        candidate_count = int(result["real_candidate_count"])
        resource_within_budget = (
            candidate_count <= run_config.budget.max_candidates
            and int(resources["candidate_training_samples"])
            <= run_config.budget.max_training_samples
            and float(resources["candidate_wall_seconds"])
            <= run_config.budget.max_wall_seconds
            and float(resources["candidate_cpu_seconds"])
            <= run_config.budget.max_cpu_seconds
        )
        return EvaluationMetrics(
            primary_metric=float(result["metrics"][primary_key]),
            higher_is_better=higher_is_better(metric_name),
            cpu_seconds=float(resources["candidate_cpu_seconds"]),
            wall_seconds=float(resources["candidate_wall_seconds"]),
            peak_rss_bytes=int(resources["peak_rss_bytes"]),
            training_samples=int(resources["candidate_training_samples"]),
            hard_constraints_passed=result.get("status") == "completed",
            resource_within_budget=resource_within_budget,
            initial_state_sha256=_sha256(checkpoint),
            phase_manifest_sha256=_phase_sha256(stream),
        )
