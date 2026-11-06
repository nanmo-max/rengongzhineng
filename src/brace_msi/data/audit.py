"""Aggregate-only audit records for local proxy datasets."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from .types import BatchData, TaskStream


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _partition_samples(stream: TaskStream) -> dict[str, int]:
    return {
        "initial": len(stream.initial.y),
        "development": sum(len(batch.y) for batch in stream.development),
        "sealed": sum(len(batch.y) for batch in stream.sealed),
    }


def _partition_groups(stream: TaskStream) -> dict[str, int]:
    return {
        "initial": len(set(stream.initial.group_ids)),
        "development": len(
            {group for batch in stream.development for group in batch.group_ids}
        ),
        "sealed": len({group for batch in stream.sealed for group in batch.group_ids}),
    }


def _batch_samples(batches: tuple[BatchData, ...]) -> dict[str, int]:
    return {batch.batch_id: len(batch.y) for batch in batches}


def _dataset_summary(stream: TaskStream) -> dict[str, Any]:
    all_batches = (stream.initial, *stream.development, *stream.sealed)
    summary: dict[str, Any] = {
        "task_id": stream.task_id,
        "task_kind": stream.task_kind,
        "feature_count": int(stream.initial.X.shape[1]),
        "split_rule": stream.metadata["split_rule"],
        "partition_samples": _partition_samples(stream),
        "batch_samples": _batch_samples(all_batches),
        "sample_ids_disjoint": stream.all_sample_ids_are_disjoint(),
    }
    if stream.task_kind == "classification":
        counts = Counter(int(target) for batch in all_batches for target in batch.y)
        summary["class_counts"] = {
            str(label): counts[label] for label in sorted(counts)
        }
    else:
        summary["partition_groups"] = _partition_groups(stream)
        summary["target_range"] = {
            "minimum": float(min(target for batch in all_batches for target in batch.y)),
            "maximum": float(max(target for batch in all_batches for target in batch.y)),
        }
    return summary


def build_proxy_audit(
    gas: TaskStream,
    cmapss: TaskStream,
    *,
    gas_archive: Path,
    cmapss_archive: Path,
) -> dict[str, Any]:
    gas_summary = _dataset_summary(gas)
    cmapss_summary = _dataset_summary(cmapss)
    return {
        "schema_version": 1,
        "proxy_only": True,
        "archives": {
            "gas_sha256": file_sha256(gas_archive),
            "cmapss_sha256": file_sha256(cmapss_archive),
        },
        "datasets": {"gas": gas_summary, "cmapss": cmapss_summary},
        "checks": {
            "sample_ids_disjoint": bool(
                gas_summary["sample_ids_disjoint"]
                and cmapss_summary["sample_ids_disjoint"]
            ),
            "raw_data_modified": False,
            "sealed_data_used_for_selection": False,
        },
    }
