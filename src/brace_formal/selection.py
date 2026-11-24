"""Deterministic selection of legally comparable competition artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .metrics import MetricContract, compare_metric_values


_ROLES = frozenset({"parent", "candidate", "history"})
_RESOURCE_ORDER = (
    "cpu_seconds",
    "wall_seconds",
    "peak_rss_bytes",
    "checkpoint_bytes",
    "parameter_count",
    "token_total",
)


def _immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class ArtifactEvaluation:
    """One artifact evaluated on an explicitly fingerprinted validation scope."""

    artifact_id: str
    role: str
    metrics: Mapping[str, float]
    validation_sha256: str
    resource_evidence: Mapping[str, float]
    hard_failures: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, str) or not self.artifact_id:
            raise ValueError("artifact_id is required")
        if self.role not in _ROLES:
            raise ValueError("artifact role must be parent, candidate or history")
        if not isinstance(self.validation_sha256, str) or not self.validation_sha256:
            raise ValueError("validation scope fingerprint is required")
        if not isinstance(self.metrics, Mapping):
            raise ValueError("metrics must be a mapping")
        if not isinstance(self.resource_evidence, Mapping):
            raise ValueError("resource evidence must be a mapping")
        if any(not isinstance(item, str) or not item for item in self.hard_failures):
            raise ValueError("hard failures must be non-empty strings")
        object.__setattr__(self, "metrics", _immutable_mapping(self.metrics))
        object.__setattr__(self, "resource_evidence", _immutable_mapping(self.resource_evidence))
        object.__setattr__(self, "hard_failures", tuple(self.hard_failures))


@dataclass(frozen=True)
class SelectionResult:
    """Requested and actually applied artifact choice plus its audit receipt."""

    requested_artifact_id: str | None
    applied_artifact_id: str
    applied_role: str
    relation_to_parent: str
    request_honored: bool
    reason: str
    validation_sha256: str
    comparable_artifact_ids: tuple[str, ...]
    excluded_artifacts: Mapping[str, str]
    ranked_artifact_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "comparable_artifact_ids", tuple(self.comparable_artifact_ids))
        object.__setattr__(self, "ranked_artifact_ids", tuple(self.ranked_artifact_ids))
        object.__setattr__(self, "excluded_artifacts", _immutable_mapping(self.excluded_artifacts))


def _finite_metric(evaluation: ArtifactEvaluation, name: str) -> float | None:
    value = evaluation.metrics.get(name)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite_resource(evaluation: ArtifactEvaluation, name: str) -> float | None:
    value = evaluation.resource_evidence.get(name)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0.0 else None


def _best_tied_by_metric(
    contract: MetricContract,
    tied: list[ArtifactEvaluation],
    metric_name: str,
) -> list[ArtifactEvaluation]:
    values = [_finite_metric(item, metric_name) for item in tied]
    if any(value is None for value in values):
        return tied
    assert values and all(value is not None for value in values)
    direction = contract.metric_directions[metric_name]
    best = values[0]
    for value in values[1:]:
        assert value is not None and best is not None
        if compare_metric_values(direction, value, best) > 0:
            best = value
    assert best is not None
    return [
        item
        for item, value in zip(tied, values, strict=True)
        if value is not None and compare_metric_values(direction, value, best) == 0
    ]


def _best_tied_by_resource(tied: list[ArtifactEvaluation], field: str) -> list[ArtifactEvaluation]:
    values = [_finite_resource(item, field) for item in tied]
    if any(value is None for value in values):
        return tied
    assert values and all(value is not None for value in values)
    best = min(value for value in values if value is not None)
    tolerance = 1e-12 * max(1.0, abs(best))
    return [
        item
        for item, value in zip(tied, values, strict=True)
        if value is not None and abs(value - best) <= tolerance
    ]


def _dominates(
    contract: MetricContract,
    left: ArtifactEvaluation,
    right: ArtifactEvaluation,
) -> bool:
    strictly_better = False
    compared = 0
    for name, direction in contract.metric_directions.items():
        left_value = _finite_metric(left, name)
        right_value = _finite_metric(right, name)
        if left_value is None or right_value is None:
            continue
        compared += 1
        relation = compare_metric_values(direction, left_value, right_value)
        if relation < 0:
            return False
        strictly_better = strictly_better or relation > 0
    return compared > 0 and strictly_better


def _same_metric_vector(
    contract: MetricContract,
    left: ArtifactEvaluation,
    right: ArtifactEvaluation,
) -> bool:
    for name, direction in contract.metric_directions.items():
        left_value = _finite_metric(left, name)
        right_value = _finite_metric(right, name)
        if left_value is None or right_value is None:
            if left_value is not None or right_value is not None:
                return False
            continue
        if compare_metric_values(direction, left_value, right_value) != 0:
            return False
    return True


def _resource_tied(tied: list[ArtifactEvaluation]) -> list[ArtifactEvaluation]:
    remaining = tied
    for field in _RESOURCE_ORDER:
        if len(remaining) <= 1:
            break
        remaining = _best_tied_by_resource(remaining, field)
    return remaining


def _rank(
    contract: MetricContract,
    comparable: list[ArtifactEvaluation],
    requested_artifact_id: str | None,
) -> tuple[ArtifactEvaluation, tuple[str, ...]]:
    by_id = {item.artifact_id: item for item in comparable}
    front = [
        item
        for item in comparable
        if not any(
            other.artifact_id != item.artifact_id and _dominates(contract, other, item)
            for other in comparable
        )
    ]
    requested = by_id.get(str(requested_artifact_id)) if requested_artifact_id is not None else None
    if requested is not None and requested in front:
        equivalent = [item for item in front if _same_metric_vector(contract, item, requested)]
        tied = _resource_tied(equivalent)
        if requested in tied:
            selected = requested
        else:
            parent = next((item for item in tied if item.role == "parent"), None)
            selected = parent if parent is not None else min(tied, key=lambda item: item.artifact_id)
    else:
        tied = _best_tied_by_metric(contract, front, contract.name)
        for name in contract.auxiliary_metrics:
            if len(tied) <= 1:
                break
            tied = _best_tied_by_metric(contract, tied, name)
        tied = _resource_tied(tied)
        parent = next((item for item in tied if item.role == "parent"), None)
        selected = parent if parent is not None else min(tied, key=lambda item: item.artifact_id)

    # The receipt is a deterministic best-first ordering, without pretending
    # that heterogeneous resource units form an invented official score.
    remainder = sorted(
        (item.artifact_id for item in comparable if item.artifact_id != selected.artifact_id)
    )
    return selected, (selected.artifact_id, *remainder)


def _relation_to_parent(
    contract: MetricContract,
    selected: ArtifactEvaluation,
    parent: ArtifactEvaluation,
) -> str:
    primary = compare_metric_values(
        contract.direction,
        float(selected.metrics[contract.name]),
        float(parent.metrics[contract.name]),
    )
    if primary > 0:
        return "improved"
    if primary < 0:
        return "regressed"
    for name in contract.auxiliary_metrics:
        selected_value = _finite_metric(selected, name)
        parent_value = _finite_metric(parent, name)
        if selected_value is None or parent_value is None:
            continue
        relation = compare_metric_values(contract.metric_directions[name], selected_value, parent_value)
        if relation > 0:
            return "improved_auxiliary"
        if relation < 0:
            return "regressed_auxiliary"
    return "unchanged"


def select_artifact(
    contract: MetricContract,
    evaluations: Sequence[ArtifactEvaluation],
    requested_artifact_id: str | None,
) -> SelectionResult:
    """Select the best legal artifact on the parent's current validation scope.

    Qwen's requested artifact is honored when it is Pareto-nondominated across
    the declared official metrics.  Hard failures, mismatched validation scope,
    dominated choices and equal-metric resource waste remain deterministic
    overrides.  No participant-defined percentage gate or combined score is
    introduced.
    """

    items = list(evaluations)
    if not items:
        raise ValueError("artifact evaluations are required")
    ids = [item.artifact_id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("artifact IDs must be unique")
    parents = [item for item in items if item.role == "parent"]
    if len(parents) != 1:
        raise ValueError("exactly one parent artifact is required")
    parent = parents[0]
    parent_primary = _finite_metric(parent, contract.name)
    if parent.hard_failures or parent_primary is None:
        raise ValueError("parent artifact is not a valid selection fallback")

    excluded: dict[str, str] = {}
    comparable: list[ArtifactEvaluation] = []
    for item in items:
        if item.hard_failures:
            excluded[item.artifact_id] = "hard_failure:" + ",".join(item.hard_failures)
        elif item.validation_sha256 != parent.validation_sha256:
            excluded[item.artifact_id] = "validation_scope_mismatch"
        elif _finite_metric(item, contract.name) is None:
            excluded[item.artifact_id] = "primary_metric_not_finite"
        else:
            comparable.append(item)

    selected, ranking = _rank(contract, comparable, requested_artifact_id)
    relation = _relation_to_parent(contract, selected, parent)
    honored = requested_artifact_id == selected.artifact_id
    if honored:
        reason = "requested artifact is a nondominated same-scope choice"
    elif requested_artifact_id in excluded:
        reason = f"requested artifact excluded: {excluded[str(requested_artifact_id)]}"
    elif requested_artifact_id not in ids:
        reason = "requested artifact is not a declared legal artifact"
    else:
        reason = "requested artifact was worse (Pareto-dominated) than the applied same-scope evidence"

    return SelectionResult(
        requested_artifact_id=requested_artifact_id,
        applied_artifact_id=selected.artifact_id,
        applied_role=selected.role,
        relation_to_parent=relation,
        request_honored=honored,
        reason=reason,
        validation_sha256=parent.validation_sha256,
        comparable_artifact_ids=tuple(item.artifact_id for item in comparable),
        excluded_artifacts=excluded,
        ranked_artifact_ids=ranking,
    )

