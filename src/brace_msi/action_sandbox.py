"""Versioned, fail-closed execution plans for Agent proposals."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from collections.abc import Iterable

from .official_package import PackageAudit
from .official_trainer import CandidateConfig
from .policies import Action
from .pytrio_agent import ExperimentProposal, validate_experiment_proposal


class ActionSandboxError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class BudgetSnapshot:
    candidate_slots_remaining: int
    cpu_seconds_remaining: float
    wall_seconds_remaining: float


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    version: str
    action: Action
    supported_tasks: tuple[str, ...]
    allowed_parameters: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionPlan:
    tool_id: str
    tool_version: str
    tool_registry_sha256: str
    candidate_config: CandidateConfig | None
    estimated_training_sample_visits: int
    estimated_cpu_seconds: float


class ToolRegistry:
    def __init__(self, specs: Iterable[ToolSpec]) -> None:
        indexed: dict[str, ToolSpec] = {}
        for spec in specs:
            if not spec.tool_id or not spec.version or spec.tool_id in indexed:
                raise ValueError("tool IDs and versions must be unique and nonempty")
            indexed[spec.tool_id] = spec
        if not indexed:
            raise ValueError("tool registry must not be empty")
        self._specs = indexed
        encoded = json.dumps(
            [
                {
                    **asdict(spec),
                    "action": spec.action.value,
                }
                for spec in sorted(indexed.values(), key=lambda item: item.tool_id)
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.sha256 = hashlib.sha256(encoded).hexdigest()

    def build_plan(
        self,
        proposal: ExperimentProposal,
        package: PackageAudit,
        budget: BudgetSnapshot,
        *,
        allowed_epochs: tuple[int, ...],
        allowed_learning_rate_multipliers: tuple[float, ...],
    ) -> ExecutionPlan:
        validate_experiment_proposal(proposal)
        spec = self._specs.get(proposal.tool)
        if spec is None or spec.action is not proposal.action:
            raise ActionSandboxError("action_not_executable")
        if package.task not in spec.supported_tasks:
            raise ActionSandboxError("task_not_supported")
        unknown = set(proposal.parameters) - set(spec.allowed_parameters)
        if unknown:
            raise ActionSandboxError("tool_parameter_not_allowed")
        if proposal.action is Action.NOOP:
            return ExecutionPlan(
                spec.tool_id, spec.version, self.sha256, None, 0, 0.0
            )
        if budget.candidate_slots_remaining < 1:
            raise ActionSandboxError("candidate_budget_exhausted")

        epochs = proposal.parameters.get("epochs", 1)
        learning_rate = proposal.parameters.get(
            "learning_rate", package.base_learning_rate
        )
        batch_size = proposal.parameters.get("batch_size", package.base_batch_size)
        if isinstance(epochs, bool) or not isinstance(epochs, int):
            raise ActionSandboxError("epochs_not_allowed")
        if epochs not in allowed_epochs:
            raise ActionSandboxError("epochs_not_allowed")
        if proposal.action is Action.INCREMENTAL_UPDATE and epochs != 1:
            raise ActionSandboxError("incremental_epochs_not_allowed")
        if proposal.action is Action.REPLAY_REFIT:
            replay_fraction = proposal.parameters.get("replay_fraction", 1.0)
            if (
                isinstance(replay_fraction, bool)
                or not isinstance(replay_fraction, (int, float))
                or not math.isclose(float(replay_fraction), 1.0)
            ):
                # The delivered trainer reads the complete public training file.
                # Pretending a fractional replay was executed would be false evidence.
                raise ActionSandboxError("replay_fraction_not_executable")
        if isinstance(learning_rate, bool) or not isinstance(
            learning_rate, (int, float)
        ):
            raise ActionSandboxError("learning_rate_not_allowed")
        allowed_rates = tuple(
            package.base_learning_rate * multiplier
            for multiplier in allowed_learning_rate_multipliers
        )
        if not any(
            math.isclose(float(learning_rate), value, rel_tol=1e-12)
            for value in allowed_rates
        ):
            raise ActionSandboxError("learning_rate_not_allowed")
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size != package.base_batch_size
        ):
            raise ActionSandboxError("batch_size_not_allowed")

        estimated_cpu = (
            max(0.0, package.training_seconds)
            / max(1, package.base_epochs)
            * epochs
        )
        if estimated_cpu > budget.cpu_seconds_remaining:
            raise ActionSandboxError("estimated_cpu_budget_exceeded")
        if proposal.max_cpu_seconds > budget.cpu_seconds_remaining:
            raise ActionSandboxError("proposal_cpu_budget_exceeds_remaining")
        if proposal.max_candidates > budget.candidate_slots_remaining:
            raise ActionSandboxError("proposal_candidate_budget_exceeds_remaining")
        if budget.wall_seconds_remaining <= 0:
            raise ActionSandboxError("wall_budget_exhausted")
        return ExecutionPlan(
            tool_id=spec.tool_id,
            tool_version=spec.version,
            tool_registry_sha256=self.sha256,
            candidate_config=CandidateConfig(
                epochs=epochs,
                learning_rate=float(learning_rate),
                batch_size=batch_size,
            ),
            estimated_training_sample_visits=package.train_rows * epochs,
            estimated_cpu_seconds=estimated_cpu,
        )


def default_official_tool_registry() -> ToolRegistry:
    tasks = ("classification", "regression")
    return ToolRegistry(
        (
            ToolSpec("noop", "1", Action.NOOP, tasks, ()),
            ToolSpec(
                "train_incremental",
                "1",
                Action.INCREMENTAL_UPDATE,
                tasks,
                ("epochs", "learning_rate", "batch_size"),
            ),
            ToolSpec(
                "train_replay_refit",
                "1",
                Action.REPLAY_REFIT,
                tasks,
                ("epochs", "learning_rate", "batch_size", "replay_fraction"),
            ),
        )
    )


def assert_isolated_output_path(
    package_dir: Path, runtime_root: Path, output_path: Path
) -> None:
    package = Path(package_dir).resolve()
    runtime = Path(runtime_root).resolve()
    output = Path(output_path).resolve()
    if runtime == package or runtime.is_relative_to(package) or package.is_relative_to(runtime):
        raise ActionSandboxError("runtime_overlaps_package")
    if output == runtime or not output.is_relative_to(runtime):
        raise ActionSandboxError("output_outside_runtime")
    if output == package or output.is_relative_to(package):
        raise ActionSandboxError("output_overlaps_package")


@dataclass(frozen=True)
class PluginSpec:
    plugin_id: str
    version: str
    entry_path: Path
    sha256: str
    license_id: str
    supported_tasks: tuple[str, ...]


class PluginRegistry:
    """Audit registry only; registration does not grant execution permission."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self._plugins: dict[str, PluginSpec] = {}

    def register(self, spec: PluginSpec) -> None:
        if spec.plugin_id in self._plugins or not spec.plugin_id or not spec.version:
            raise ActionSandboxError("plugin_identity_invalid")
        if not spec.license_id.strip():
            raise ActionSandboxError("plugin_license_missing")
        path = Path(spec.entry_path).resolve()
        if not path.is_file() or not path.is_relative_to(self.root):
            raise ActionSandboxError("plugin_outside_registry_root")
        if _sha256(path) != spec.sha256.lower():
            raise ActionSandboxError("plugin_hash_mismatch")
        if not spec.supported_tasks:
            raise ActionSandboxError("plugin_tasks_missing")
        self._plugins[spec.plugin_id] = spec

    def resolve(self, plugin_id: str, *, task: str) -> PluginSpec:
        try:
            spec = self._plugins[plugin_id]
        except KeyError as exc:
            raise ActionSandboxError("plugin_not_registered") from exc
        if task not in spec.supported_tasks:
            raise ActionSandboxError("plugin_task_not_supported")
        if _sha256(Path(spec.entry_path).resolve()) != spec.sha256.lower():
            raise ActionSandboxError("plugin_hash_mismatch")
        return spec


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
