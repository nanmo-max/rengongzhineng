"""High-fidelity local stream plans for the platform lifecycle.

This module never claims to reproduce unavailable hidden data.  It builds an
auditable local stream in which prediction is possible before feedback and in
which natural task groups, rather than JSONL row offsets, define rounds.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Iterable, Sequence

import numpy as np

from .official_metrics import nasa_asymmetric_score
from .platform_runtime import (
    ArrivalEvidence,
    PlatformAdvisor,
    PlatformRuntimeConfig,
    start_round,
    submit_predictions,
)
from .swanlab_adapter import SwanLabOfflineConfig, export_public_spool


_GAS_LABELS = {
    1: "Ethanol",
    2: "Ethylene",
    3: "Ammonia",
    4: "Acetaldehyde",
    5: "Acetone",
    6: "Toluene",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, raw in enumerate(stream, 1):
            if not raw.strip():
                continue
            value = json.loads(raw)
            if not isinstance(value, dict) or not isinstance(value.get("id"), str):
                raise ValueError(f"invalid JSONL row at line {line_number}")
            if "inputs" not in value or "answer" not in value or not isinstance(value.get("meta"), dict):
                raise ValueError(f"incomplete labeled row at line {line_number}")
            rows.append(value)
    if not rows:
        raise ValueError("labeled JSONL is empty")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("duplicate sample id")
    return rows


def _parse_gas_batch(path: Path, batch_number: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for source_index, raw in enumerate(stream, 1):
            tokens = raw.split()
            if not tokens:
                continue
            label_number = int(tokens[0])
            if label_number not in _GAS_LABELS:
                raise ValueError("unknown Gas class")
            features = [0.0] * 128
            seen: set[int] = set()
            for token in tokens[1:]:
                raw_index, raw_value = token.split(":", 1)
                feature_index = int(raw_index)
                value = float(raw_value)
                if not 1 <= feature_index <= 128 or feature_index in seen or not math.isfinite(value):
                    raise ValueError("invalid Gas feature")
                features[feature_index - 1] = value
                seen.add(feature_index)
            if len(seen) != 128:
                raise ValueError("Gas row does not contain 128 features")
            rows.append(
                {
                    "id": f"gas_b{batch_number:02d}_{source_index:06d}",
                    "inputs": {"features": features},
                    "answer": _GAS_LABELS[label_number],
                    "meta": {"source_batch": batch_number, "source_index": source_index},
                }
            )
    if not rows:
        raise ValueError(f"Gas batch {batch_number} is empty")
    return rows


def _row_feature_hash(row: dict[str, Any]) -> str:
    return _digest(row["inputs"])


def _sorted_rows(rows: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(sorted(rows, key=lambda row: str(row["id"])))


@dataclass(frozen=True)
class StreamRound:
    index: int
    rows: tuple[dict[str, Any], ...]
    update_ids: tuple[str, ...]
    gate_ids: tuple[str, ...]
    update_groups: tuple[str, ...]
    gate_groups: tuple[str, ...]
    source_groups: tuple[str, ...]

    def __post_init__(self) -> None:
        row_ids = {str(row["id"]) for row in self.rows}
        update = set(self.update_ids)
        gate = set(self.gate_ids)
        if not 1 <= self.index <= 10 or not update or not gate:
            raise ValueError("each stream round needs nonempty Update and Gate")
        if update & gate or update | gate != row_ids:
            raise ValueError("round Update/Gate partition is invalid")
        if set(self.update_groups) & set(self.gate_groups):
            raise ValueError("round Update/Gate groups overlap")


@dataclass(frozen=True)
class TaskStreamPlan:
    profile: str
    task: str
    rounds: tuple[StreamRound, ...]
    confirmation_rows: tuple[dict[str, Any], ...]
    parent_ids: tuple[str, ...]
    source_sha256: tuple[tuple[str, str], ...]
    audit: dict[str, int]
    assignment_digest: str

    def __post_init__(self) -> None:
        if len(self.rounds) != 10 or [row.index for row in self.rounds] != list(range(1, 11)):
            raise ValueError("stream plan must contain ordered rounds 1..10")
        if not self.confirmation_rows:
            raise ValueError("stream plan needs an independent confirmation set")


def _finalize_plan(
    *,
    profile: str,
    task: str,
    parent_rows: Sequence[dict[str, Any]],
    rounds: Sequence[StreamRound],
    confirmation_rows: Sequence[dict[str, Any]],
    sources: dict[str, str],
) -> TaskStreamPlan:
    parent_ids = {str(row["id"]) for row in parent_rows}
    stream_rows = [row for round_ in rounds for row in round_.rows]
    stream_ids = {str(row["id"]) for row in stream_rows}
    confirmation_ids = {str(row["id"]) for row in confirmation_rows}
    parent_features = {_row_feature_hash(row) for row in parent_rows}
    stream_features = {_row_feature_hash(row) for row in stream_rows}
    confirmation_features = {_row_feature_hash(row) for row in confirmation_rows}
    audit = {
        "parent_stream_id_overlap": len(parent_ids & stream_ids),
        "parent_confirmation_id_overlap": len(parent_ids & confirmation_ids),
        "stream_confirmation_id_overlap": len(stream_ids & confirmation_ids),
        "parent_stream_feature_overlap": len(parent_features & stream_features),
        "parent_confirmation_feature_overlap": len(parent_features & confirmation_features),
        "stream_confirmation_feature_overlap": len(stream_features & confirmation_features),
    }
    if audit["parent_stream_id_overlap"] or audit["parent_confirmation_id_overlap"]:
        raise ValueError("parent sample id overlaps stream or confirmation")
    if audit["stream_confirmation_id_overlap"]:
        raise ValueError("stream and confirmation sample ids overlap")
    if audit["parent_stream_feature_overlap"] or audit["parent_confirmation_feature_overlap"]:
        raise ValueError("parent feature overlaps stream or confirmation")
    if audit["stream_confirmation_feature_overlap"]:
        raise ValueError("stream and confirmation features overlap")
    assignment = {
        "profile": profile,
        "task": task,
        "rounds": [
            {
                "round": round_.index,
                "rows": sorted(str(row["id"]) for row in round_.rows),
                "update": sorted(round_.update_ids),
                "gate": sorted(round_.gate_ids),
                "update_groups": sorted(round_.update_groups),
                "gate_groups": sorted(round_.gate_groups),
            }
            for round_ in rounds
        ],
        "confirmation": sorted(confirmation_ids),
    }
    return TaskStreamPlan(
        profile=profile,
        task=task,
        rounds=tuple(rounds),
        confirmation_rows=_sorted_rows(confirmation_rows),
        parent_ids=tuple(sorted(parent_ids)),
        source_sha256=tuple(sorted(sources.items())),
        audit=audit,
        assignment_digest=_digest(assignment),
    )


def _stratified_time_partition(
    rows: Sequence[dict[str, Any]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["answer"])].append(row)
    update: list[str] = []
    gate: list[str] = []
    for label in sorted(grouped):
        values = sorted(
            grouped[label],
            key=lambda row: (int(row["meta"].get("source_index", 0)), str(row["id"])),
        )
        if len(values) < 2:
            raise ValueError("each class in a Gas round needs at least two samples")
        gate_count = max(1, round(len(values) * 0.2))
        gate_positions = {
            min(len(values) - 1, math.floor((offset + 0.5) * len(values) / gate_count))
            for offset in range(gate_count)
        }
        for position, row in enumerate(values):
            (gate if position in gate_positions else update).append(str(row["id"]))
    return tuple(sorted(update)), tuple(sorted(gate))


def _time_shards(rows: Sequence[dict[str, Any]], count: int) -> list[list[dict[str, Any]]]:
    shards: list[list[dict[str, Any]]] = [[] for _ in range(count)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["answer"])].append(row)
    for label in sorted(grouped):
        values = sorted(grouped[label], key=lambda row: int(row["meta"]["source_index"]))
        for shard_index in range(count):
            start = len(values) * shard_index // count
            stop = len(values) * (shard_index + 1) // count
            shards[shard_index].extend(values[start:stop])
    return shards


def build_gas_stream_plan(parent_train_path: Path, raw_root: Path) -> TaskStreamPlan:
    """Use parent-unseen Gas batches 2..9 for ten rounds and reserve batch 10."""

    parent_path = Path(parent_train_path).resolve()
    dataset_root = Path(raw_root).resolve()
    if (dataset_root / "Dataset").is_dir():
        dataset_root = dataset_root / "Dataset"
    parent_rows = _read_jsonl(parent_path)
    batches: dict[int, list[dict[str, Any]]] = {}
    sources = {"parent_train": _file_sha256(parent_path)}
    for batch_number in range(2, 11):
        source = dataset_root / f"batch{batch_number}.dat"
        if not source.is_file():
            raise FileNotFoundError(source)
        sources[f"gas_batch_{batch_number}"] = _file_sha256(source)
        batches[batch_number] = _parse_gas_batch(source, batch_number)
    split_batches = {
        batch
        for batch, _ in sorted(
            ((number, len(rows)) for number, rows in batches.items() if number != 10),
            key=lambda item: (-item[1], item[0]),
        )[:2]
    }
    rounds: list[StreamRound] = []
    for batch_number in range(2, 10):
        shard_count = 2 if batch_number in split_batches else 1
        for shard_index, shard in enumerate(_time_shards(batches[batch_number], shard_count), 1):
            update, gate = _stratified_time_partition(shard)
            group = f"gas_batch_{batch_number:02d}_time_{shard_index:02d}"
            rounds.append(
                StreamRound(
                    index=len(rounds) + 1,
                    rows=_sorted_rows(shard),
                    update_ids=update,
                    gate_ids=gate,
                    update_groups=(group,),
                    gate_groups=(),
                    source_groups=(group,),
                )
            )
    return _finalize_plan(
        profile="A",
        task="classification",
        parent_rows=parent_rows,
        rounds=rounds,
        confirmation_rows=batches[10],
        sources=sources,
    )


def _bearing_group(row: dict[str, Any]) -> str:
    return str(row["meta"]["bearing"])


def build_bearing_stream_plan(parent_train_path: Path, unseen_path: Path) -> TaskStreamPlan:
    parent_path = Path(parent_train_path).resolve()
    unseen = Path(unseen_path).resolve()
    parent_rows = _read_jsonl(parent_path)
    rows = _read_jsonl(unseen)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_bearing_group(row)].append(row)
    if len(grouped) < 3:
        raise ValueError("Bearing simulation needs at least three unseen bearings")
    by_size = sorted(grouped, key=lambda name: (len(grouped[name]), name))
    confirmation_group = by_size[len(by_size) // 2]
    stream_groups = sorted(name for name in grouped if name != confirmation_group)
    round_rows: list[list[dict[str, Any]]] = [[] for _ in range(10)]
    for name in stream_groups:
        values = sorted(grouped[name], key=lambda row: int(row["meta"]["snapshot"]))
        maximum = int(values[-1]["meta"]["snapshot"])
        minimum = int(values[0]["meta"]["snapshot"])
        span = max(1, maximum - minimum)
        for row in values:
            progress = (int(row["meta"]["snapshot"]) - minimum) / span
            round_rows[min(9, int(progress * 10))].append(row)
    rounds: list[StreamRound] = []
    for index, values in enumerate(round_rows, 1):
        present = sorted({_bearing_group(row) for row in values})
        if len(present) < 2:
            raise ValueError("each Bearing round needs at least two bearing groups")
        gate_group = present[(index - 1) % len(present)]
        update_groups = tuple(group for group in present if group != gate_group)
        update_ids = tuple(sorted(str(row["id"]) for row in values if _bearing_group(row) in update_groups))
        gate_ids = tuple(sorted(str(row["id"]) for row in values if _bearing_group(row) == gate_group))
        rounds.append(
            StreamRound(
                index=index,
                rows=_sorted_rows(values),
                update_ids=update_ids,
                gate_ids=gate_ids,
                update_groups=update_groups,
                gate_groups=(gate_group,),
                source_groups=tuple(present),
            )
        )
    return _finalize_plan(
        profile="B",
        task="regression",
        parent_rows=parent_rows,
        rounds=rounds,
        confirmation_rows=grouped[confirmation_group],
        sources={"parent_train": _file_sha256(parent_path), "unseen": _file_sha256(unseen)},
    )


def _engine_group(row: dict[str, Any]) -> str:
    return f"{row['meta']['source_subset']}:{int(row['meta']['unit'])}"


def build_engine_stream_plan(parent_train_path: Path, unseen_path: Path) -> TaskStreamPlan:
    parent_path = Path(parent_train_path).resolve()
    unseen = Path(unseen_path).resolve()
    parent_rows = _read_jsonl(parent_path)
    rows = _read_jsonl(unseen)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_engine_group(row)].append(row)
    if len(grouped) < 30:
        raise ValueError("Engine simulation needs at least thirty unseen units")
    ordered_groups = sorted(grouped, key=lambda group: (_digest({"group": group}), group))
    confirmation_count = max(1, round(len(ordered_groups) * 0.2))
    confirmation_groups = set(ordered_groups[:confirmation_count])
    stream_groups = ordered_groups[confirmation_count:]
    assigned: list[list[str]] = [[] for _ in range(10)]
    for position, group in enumerate(stream_groups):
        assigned[position % 10].append(group)
    rounds: list[StreamRound] = []
    for index, groups in enumerate(assigned, 1):
        groups = sorted(groups)
        if len(groups) < 2:
            raise ValueError("each Engine round needs at least two units")
        gate_count = max(1, round(len(groups) * 0.2))
        gate_groups = tuple(
            sorted(groups, key=lambda group: (_digest({"round": index, "group": group}), group))[:gate_count]
        )
        update_groups = tuple(group for group in groups if group not in set(gate_groups))
        values = [row for group in groups for row in grouped[group]]
        update_ids = tuple(sorted(str(row["id"]) for row in values if _engine_group(row) in update_groups))
        gate_ids = tuple(sorted(str(row["id"]) for row in values if _engine_group(row) in gate_groups))
        rounds.append(
            StreamRound(
                index=index,
                rows=_sorted_rows(values),
                update_ids=update_ids,
                gate_ids=gate_ids,
                update_groups=update_groups,
                gate_groups=gate_groups,
                source_groups=tuple(groups),
            )
        )
    confirmation_rows = [row for group in sorted(confirmation_groups) for row in grouped[group]]
    return _finalize_plan(
        profile="C",
        task="regression",
        parent_rows=parent_rows,
        rounds=rounds,
        confirmation_rows=confirmation_rows,
        sources={"parent_train": _file_sha256(parent_path), "unseen": _file_sha256(unseen)},
    )


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _write_rows(path: Path, rows: Sequence[dict[str, Any]], *, labeled: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        for row in rows:
            payload = dict(row)
            if not labeled:
                payload.pop("answer", None)
            stream.write(
                json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def materialize_stream_plan(plan: TaskStreamPlan, root: Path) -> dict[str, Any]:
    """Write only the predeclared round capabilities to an isolated directory."""

    root = Path(root).resolve()
    if root.exists() or root.is_symlink():
        raise FileExistsError("stream plan output must be a new directory")
    root.mkdir(parents=True)
    round_manifests: list[dict[str, Any]] = []
    for round_ in plan.rounds:
        round_root = root / "rounds" / f"round-{round_.index:02d}"
        row_by_id = {str(row["id"]): row for row in round_.rows}
        prediction = round_root / "prediction.jsonl"
        feedback = round_root / "feedback.jsonl"
        update = round_root / "update.jsonl"
        gate = round_root / "gate.jsonl"
        _write_rows(prediction, round_.rows, labeled=False)
        _write_rows(feedback, round_.rows, labeled=True)
        _write_rows(update, [row_by_id[identity] for identity in round_.update_ids], labeled=True)
        _write_rows(gate, [row_by_id[identity] for identity in round_.gate_ids], labeled=True)
        round_manifests.append(
            {
                "round_index": round_.index,
                "sample_count": len(round_.rows),
                "update_count": len(round_.update_ids),
                "gate_count": len(round_.gate_ids),
                "sample_ids_sha256": _digest(sorted(row_by_id)),
                "update_ids_sha256": _digest(sorted(round_.update_ids)),
                "gate_ids_sha256": _digest(sorted(round_.gate_ids)),
                "source_groups": list(round_.source_groups),
                "update_groups": list(round_.update_groups),
                "gate_groups": list(round_.gate_groups),
                "prediction_sha256": _file_sha256(prediction),
                "feedback_sha256": _file_sha256(feedback),
                "update_sha256": _file_sha256(update),
                "gate_sha256": _file_sha256(gate),
            }
        )
    confirmation_root = root / "confirmation"
    confirmation_prediction = confirmation_root / "prediction.jsonl"
    confirmation_feedback = confirmation_root / "feedback.jsonl"
    _write_rows(confirmation_prediction, plan.confirmation_rows, labeled=False)
    _write_rows(confirmation_feedback, plan.confirmation_rows, labeled=True)
    manifest = {
        "format": "brace-msi.stream-plan.v1",
        "profile": plan.profile,
        "task": plan.task,
        "round_count": len(plan.rounds),
        "assignment_digest": plan.assignment_digest,
        "source_sha256": dict(plan.source_sha256),
        "parent_ids_sha256": _digest(sorted(plan.parent_ids)),
        "audit": plan.audit,
        "rounds": round_manifests,
        "confirmation": {
            "sample_count": len(plan.confirmation_rows),
            "sample_ids_sha256": _digest(sorted(str(row["id"]) for row in plan.confirmation_rows)),
            "prediction_sha256": _file_sha256(confirmation_prediction),
            "feedback_sha256": _file_sha256(confirmation_feedback),
            "read_policy": "once_after_round_10_freeze",
        },
    }
    _atomic_json(root / "stream-plan.json", manifest)
    return manifest


class ScoreVault:
    """External scorer whose metrics are never passed to the runtime policy."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(round_index: int, confirmation: bool) -> str:
        if confirmation:
            return "confirmation"
        if not 1 <= round_index <= 10:
            raise ValueError("score round must be in 1..10")
        return f"round-{round_index:02d}"

    def _append_event(self, payload: dict[str, Any]) -> None:
        path = self.root / "events.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def seal_predictions(
        self, round_index: int, prediction_path: Path, *, confirmation: bool = False
    ) -> dict[str, Any]:
        key = self._key(round_index, confirmation)
        seal_path = self.root / "seals" / f"{key}.json"
        if seal_path.exists():
            raise ValueError("prediction is already sealed")
        prediction_path = Path(prediction_path).resolve()
        rows = _read_prediction_rows(prediction_path)
        try:
            relative = prediction_path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("prediction file must be inside ScoreVault") from exc
        receipt = {
            "format": "brace-msi.prediction-seal.v1",
            "key": key,
            "prediction_path": relative.as_posix(),
            "prediction_sha256": _file_sha256(prediction_path),
            "sample_count": len(rows),
            "sample_ids_sha256": _digest(sorted(row["id"] for row in rows)),
            "feedback_opened": False,
        }
        _atomic_json(seal_path, receipt)
        self._append_event({"event": "prediction_sealed", "key": key, "sha256": receipt["prediction_sha256"]})
        return receipt

    def score_feedback(
        self,
        round_index: int,
        feedback_path: Path,
        *,
        task: str,
        confirmation: bool,
        profile: str | None = None,
        visible_to_action_policy: bool = False,
    ) -> dict[str, Any]:
        key = self._key(round_index, confirmation)
        seal_path = self.root / "seals" / f"{key}.json"
        score_path = self.root / "scores" / f"{key}.json"
        if not seal_path.is_file():
            raise ValueError("sealed prediction is required before feedback")
        if score_path.exists():
            raise ValueError("feedback can be scored only once")
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        prediction_path = self.root / seal["prediction_path"]
        if _file_sha256(prediction_path) != seal["prediction_sha256"]:
            raise ValueError("sealed prediction changed before feedback")
        predictions = _read_prediction_rows(prediction_path)
        feedback = _read_jsonl(Path(feedback_path))
        prediction_by_id = {str(row["id"]): row for row in predictions}
        feedback_by_id = {str(row["id"]): row for row in feedback}
        if set(prediction_by_id) != set(feedback_by_id):
            raise ValueError("prediction and feedback sample IDs differ")
        metrics = _score_predictions(prediction_by_id, feedback_by_id, task=task, profile=profile)
        receipt = {
            "format": "brace-msi.external-score.v1",
            "key": key,
            "task": task,
            "profile": profile,
            "sample_count": len(feedback),
            "prediction_sha256": seal["prediction_sha256"],
            "feedback_sha256": _file_sha256(Path(feedback_path)),
            "metrics": metrics,
            "visible_to_action_policy": visible_to_action_policy,
            "prediction_sealed_before_feedback": True,
        }
        _atomic_json(score_path, receipt)
        event = "confirmation_scored" if confirmation else "feedback_scored"
        self._append_event({"event": event, "key": key, "sample_count": len(feedback)})
        return receipt

    @property
    def confirmation_read_count(self) -> int:
        return int((self.root / "scores" / "confirmation.json").is_file())


def _read_prediction_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for raw in stream:
            if not raw.strip():
                continue
            value = json.loads(raw)
            if not isinstance(value, dict) or not isinstance(value.get("id"), str) or "outputs" not in value:
                raise ValueError("invalid prediction row")
            rows.append(value)
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("prediction rows are empty or duplicated")
    return rows


def _score_predictions(
    predictions: dict[str, dict[str, Any]],
    feedback: dict[str, dict[str, Any]],
    *,
    task: str,
    profile: str | None,
) -> dict[str, float]:
    identities = sorted(feedback)
    if task == "classification":
        all_labels: set[str] = set()
        predicted: list[str] = []
        targets: list[str] = []
        for identity in identities:
            outputs = predictions[identity]["outputs"]
            if not isinstance(outputs, list) or not outputs:
                raise ValueError("classification prediction outputs must be a nonempty list")
            for item in outputs:
                if not isinstance(item, dict) or not isinstance(item.get("label"), str):
                    raise ValueError("invalid classification output")
                all_labels.add(item["label"])
            predicted.append(max(outputs, key=lambda item: float(item["score"]))["label"])
            targets.append(str(feedback[identity]["answer"]))
        correct = sum(left == right for left, right in zip(predicted, targets, strict=True))
        f1: list[float] = []
        for label in sorted(all_labels | set(targets)):
            true_positive = sum(p == label and t == label for p, t in zip(predicted, targets, strict=True))
            denominator = sum(p == label for p in predicted) + sum(t == label for t in targets)
            f1.append(2.0 * true_positive / denominator if denominator else 0.0)
        return {"accuracy": correct / len(identities), "macro_f1": sum(f1) / len(f1)}
    if task != "regression":
        raise ValueError("unsupported score task")
    predicted_values = np.asarray(
        [float(predictions[identity]["outputs"]["value"]) for identity in identities], dtype=np.float64
    )
    targets = np.asarray([float(feedback[identity]["answer"]) for identity in identities], dtype=np.float64)
    if not np.isfinite(predicted_values).all() or not np.isfinite(targets).all():
        raise ValueError("nonfinite regression score input")
    errors = predicted_values - targets
    metrics = {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors**2))),
    }
    if profile == "C":
        metrics["nasa_score"] = float(nasa_asymmetric_score(targets, predicted_values))
        metrics["nasa_score_mean"] = metrics["nasa_score"] / len(targets)
    return metrics


def _paired_delayed_gain(
    *, task: str, current: dict[str, float], predecessor: dict[str, float]
) -> float:
    if task == "classification":
        return float(current["macro_f1"] - predecessor["macro_f1"])
    if task == "regression":
        return float(predecessor["rmse"] - current["rmse"])
    raise ValueError("unsupported delayed-gain task")


def run_official_flow_simulation(
    plan: TaskStreamPlan,
    parent_checkpoint: Path,
    run_root: Path,
    *,
    config: PlatformRuntimeConfig = PlatformRuntimeConfig(),
    advisor: PlatformAdvisor | None = None,
    export_swanlab: bool = True,
    policy_feedback: bool = False,
) -> dict[str, Any]:
    """Execute the prediction-seal-feedback-gate lifecycle for a frozen plan."""

    root = Path(run_root).resolve()
    if root.exists() or root.is_symlink():
        raise FileExistsError("official-flow output must be a new directory")
    root.mkdir(parents=True)
    materialized = {
        "format": "brace-msi.stream-plan.v1",
        "profile": plan.profile,
        "task": plan.task,
        "round_count": len(plan.rounds),
        "assignment_digest": plan.assignment_digest,
        "source_sha256": dict(plan.source_sha256),
        "parent_ids_sha256": _digest(sorted(plan.parent_ids)),
        "audit": plan.audit,
        "rounds": [
            {
                "round_index": round_.index,
                "sample_count": len(round_.rows),
                "update_count": len(round_.update_ids),
                "gate_count": len(round_.gate_ids),
                "sample_ids_sha256": _digest(sorted(str(row["id"]) for row in round_.rows)),
                "update_ids_sha256": _digest(sorted(round_.update_ids)),
                "gate_ids_sha256": _digest(sorted(round_.gate_ids)),
                "source_groups": list(round_.source_groups),
                "update_groups": list(round_.update_groups),
                "gate_groups": list(round_.gate_groups),
            }
            for round_ in plan.rounds
        ],
        "confirmation": {
            "sample_count": len(plan.confirmation_rows),
            "sample_ids_sha256": _digest(sorted(str(row["id"]) for row in plan.confirmation_rows)),
            "read_policy": "once_after_round_10_freeze",
        },
        "future_batches_materialized_up_front": False,
    }
    _atomic_json(root / "stream-plan.json", materialized)
    vault = ScoreVault(root / "score-vault")
    workspace = root / "runtime-workspace"
    runtime_inputs = root / "runtime-inputs"
    current_parent = Path(parent_checkpoint).resolve()
    rounds: list[dict[str, Any]] = []
    previous_arrival_metrics: dict[str, float] | None = None
    pending_shadow_parent: Path | None = None
    pending_shadow_round: int | None = None
    total_shadow_cpu_seconds = 0.0
    for round_ in plan.rounds:
        round_root = runtime_inputs / f"round-{round_.index:02d}"
        round_root.mkdir(parents=True)
        row_by_id = {str(row["id"]): row for row in round_.rows}
        _write_rows(round_root / "prediction.jsonl", round_.rows, labeled=False)
        prediction_path = vault.root / "predictions" / f"round-{round_.index:02d}.jsonl"
        submit_predictions(current_parent, round_root / "prediction.jsonl", prediction_path)
        seal = vault.seal_predictions(round_.index, prediction_path)
        _write_rows(round_root / "feedback.jsonl", round_.rows, labeled=True)
        _write_rows(
            round_root / "update.jsonl",
            [row_by_id[identity] for identity in round_.update_ids],
            labeled=True,
        )
        _write_rows(
            round_root / "gate.jsonl",
            [row_by_id[identity] for identity in round_.gate_ids],
            labeled=True,
        )
        external_score = vault.score_feedback(
            round_.index,
            round_root / "feedback.jsonl",
            task=plan.task,
            confirmation=False,
            profile=plan.profile,
            visible_to_action_policy=policy_feedback,
        )
        delayed_gain: dict[str, Any] | None = None
        if policy_feedback and pending_shadow_parent is not None:
            shadow_started_cpu = time.process_time()
            shadow_prediction_path = vault.root / "shadow-predictions" / f"round-{round_.index:02d}.jsonl"
            submit_predictions(
                pending_shadow_parent,
                round_root / "prediction.jsonl",
                shadow_prediction_path,
            )
            shadow_cpu_seconds = time.process_time() - shadow_started_cpu
            total_shadow_cpu_seconds += shadow_cpu_seconds
            current_predictions = {
                str(row["id"]): row for row in _read_prediction_rows(prediction_path)
            }
            shadow_predictions = {
                str(row["id"]): row for row in _read_prediction_rows(shadow_prediction_path)
            }
            feedback_by_id = {
                str(row["id"]): row for row in _read_jsonl(round_root / "feedback.jsonl")
            }
            paired_sample_ids = set(current_predictions) == set(shadow_predictions) == set(feedback_by_id)
            if not paired_sample_ids:
                raise ValueError("delayed-gain predictions must use identical arrival sample IDs")
            predecessor_metrics = _score_predictions(
                shadow_predictions,
                feedback_by_id,
                task=plan.task,
                profile=plan.profile,
            )
            delayed_gain = {
                "settles_round_index": pending_shadow_round,
                "observed_round_index": round_.index,
                "sample_count": len(feedback_by_id),
                "paired_sample_ids": True,
                "current_metrics": external_score["metrics"],
                "predecessor_metrics": predecessor_metrics,
                "gain": _paired_delayed_gain(
                    task=plan.task,
                    current=external_score["metrics"],
                    predecessor=predecessor_metrics,
                ),
                "shadow_prediction_sha256": _file_sha256(shadow_prediction_path),
                "shadow_cpu_seconds": shadow_cpu_seconds,
            }
        arrival_evidence = (
            ArrivalEvidence(
                metrics=dict(external_score["metrics"]),
                previous_metrics=(
                    dict(previous_arrival_metrics)
                    if previous_arrival_metrics is not None
                    else None
                ),
                sample_count=len(round_.rows),
                delayed_gain=(delayed_gain["gain"] if delayed_gain is not None else None),
            )
            if policy_feedback
            else None
        )
        output = root / "runtime-rounds" / f"round-{round_.index:02d}"
        output.parent.mkdir(parents=True, exist_ok=True)
        runtime_receipt = start_round(
            round_root / "update.jsonl",
            current_parent,
            workspace,
            output,
            config,
            advisor=advisor,
            gate_data_path=round_root / "gate.jsonl",
            arrival_evidence=arrival_evidence,
        )
        rounds.append(
            {
                "round_index": round_.index,
                "prediction_seal": seal,
                "prediction_sealed_before_feedback": True,
                "prequential_metrics": external_score["metrics"],
                "arrival_metrics": external_score["metrics"],
                "external_score_visible_to_action_policy": external_score[
                    "visible_to_action_policy"
                ],
                "delayed_gain": delayed_gain,
                "candidate_gate_metrics": {
                    "stable": runtime_receipt["metrics_before"],
                    "candidate": runtime_receipt["metrics_candidate"],
                },
                "runtime_receipt": runtime_receipt,
            }
        )
        parent_before_round = current_parent
        current_parent = output / "checkpoint.npz"
        if policy_feedback and runtime_receipt["deployed"]:
            pending_shadow_parent = parent_before_round
            pending_shadow_round = round_.index
        else:
            pending_shadow_parent = None
            pending_shadow_round = None
        previous_arrival_metrics = dict(external_score["metrics"])
    confirmation_root = runtime_inputs / "confirmation"
    confirmation_root.mkdir(parents=True)
    _write_rows(
        confirmation_root / "prediction.jsonl", plan.confirmation_rows, labeled=False
    )
    confirmation_prediction = vault.root / "predictions" / "confirmation.jsonl"
    submit_predictions(
        current_parent,
        confirmation_root / "prediction.jsonl",
        confirmation_prediction,
    )
    vault.seal_predictions(10, confirmation_prediction, confirmation=True)
    _write_rows(
        confirmation_root / "feedback.jsonl", plan.confirmation_rows, labeled=True
    )
    confirmation = vault.score_feedback(
        10,
        confirmation_root / "feedback.jsonl",
        task=plan.task,
        confirmation=True,
        profile=plan.profile,
    )
    parent_chain_valid = all(
        row["runtime_receipt"]["parent_checkpoint_sha256"]
        == (
            _file_sha256(Path(parent_checkpoint))
            if index == 0
            else rounds[index - 1]["runtime_receipt"]["checkpoint_sha256"]
        )
        for index, row in enumerate(rounds)
    )
    swanlab_logdir: str | None = None
    if export_swanlab:
        export = export_public_spool(
            workspace / "public-spool.jsonl",
            SwanLabOfflineConfig(
                project="brace-msi-official-flow-sim",
                experiment_name=f"official-flow-{plan.profile}",
                logdir=root / "swanlab",
                public=False,
            ),
        )
        swanlab_logdir = str(export.logdir)
    summary = {
        "format": (
            "brace-msi.sequential-adaptation-simulation.v1"
            if policy_feedback
            else "brace-msi.official-flow-simulation.v1"
        ),
        "status": "completed",
        "evidence_scope": "local_protocol_and_task_stream_simulation_not_official_hidden_score",
        "profile": plan.profile,
        "task": plan.task,
        "stream_plan": materialized,
        "round_count": len(rounds),
        "parent_chain_valid": parent_chain_valid,
        "prequential_metrics_visible_to_policy": policy_feedback,
        "delayed_gain_semantics": (
            "next_batch_direct_predecessor_pairing" if policy_feedback else "disabled"
        ),
        "shadow_cpu_seconds": total_shadow_cpu_seconds,
        "confirmation_read_count": vault.confirmation_read_count,
        "local_final_confirmation": confirmation,
        "final_checkpoint_sha256": rounds[-1]["runtime_receipt"]["checkpoint_sha256"],
        "input_tokens": sum(int(row["runtime_receipt"]["input_tokens"]) for row in rounds),
        "output_tokens": sum(int(row["runtime_receipt"]["output_tokens"]) for row in rounds),
        "swanlab_logdir": swanlab_logdir,
        "rounds": rounds,
    }
    _atomic_json(root / "summary.json", summary)
    return summary


def run_sequential_adaptation_simulation(
    plan: TaskStreamPlan,
    parent_checkpoint: Path,
    run_root: Path,
    *,
    config: PlatformRuntimeConfig,
    advisor: PlatformAdvisor | None = None,
    export_swanlab: bool = True,
) -> dict[str, Any]:
    if config.policy_mode != "sequential":
        raise ValueError("sequential simulation requires sequential policy mode")
    return run_official_flow_simulation(
        plan,
        parent_checkpoint,
        run_root,
        config=config,
        advisor=advisor,
        export_swanlab=export_swanlab,
        policy_feedback=True,
    )


__all__ = [
    "ScoreVault",
    "StreamRound",
    "TaskStreamPlan",
    "build_bearing_stream_plan",
    "build_engine_stream_plan",
    "build_gas_stream_plan",
    "materialize_stream_plan",
    "run_official_flow_simulation",
    "run_sequential_adaptation_simulation",
]
