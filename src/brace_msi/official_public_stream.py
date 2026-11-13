"""Freeze historically exposed official public validation as a local ten-batch stream."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable

import numpy as np
import psutil

from .official_package import PackageAudit


@dataclass(frozen=True)
class FrozenPublicBatch:
    batch_index: int
    batch_id: str
    path: Path
    sample_count: int
    sample_id_digest: str
    group_digest: str | None


@dataclass(frozen=True)
class FrozenPublicStream:
    profile: str
    task_kind: str
    source_sha256: str
    historically_exposed: bool
    batches: tuple[FrozenPublicBatch, ...]


@dataclass(frozen=True)
class PredictionReceipt:
    predictions: np.ndarray
    wall_seconds: float
    cpu_seconds: float
    peak_rss_bytes: int
    request_sha256: str


class OfficialCheckpointPredictor:
    """Run the official prediction adapter with inputs-only stdin in an isolated code root."""

    def __init__(self, package: PackageAudit, root: Path) -> None:
        self.package = package
        self.root = Path(root)
        self.worker_root = self.root / "worker"
        self.scratch_root = self.root / "scratch"
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.worker_root.exists():
            shutil.copytree(
                package.package_dir / "baselines",
                self.worker_root / "baselines",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        for name, expected in package.source_sha256.items():
            source = self.worker_root / "baselines" / name
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise ValueError(f"isolated prediction source mismatch: {name}")
        self.scratch_root.mkdir(exist_ok=True)

    @staticmethod
    def _environment() -> dict[str, str]:
        allowed = {
            key: value
            for key, value in os.environ.items()
            if key.upper()
            in {
                "PATH",
                "PATHEXT",
                "SYSTEMROOT",
                "WINDIR",
                "COMSPEC",
                "TEMP",
                "TMP",
            }
        }
        allowed.update(
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONIOENCODING="utf-8",
            BASELINE_CPU_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            OMP_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
        )
        return allowed

    def predict_rows(
        self,
        checkpoint: Path,
        rows: list[dict[str, Any]],
        *,
        stage_id: str,
        timeout_seconds: float = 120.0,
    ) -> PredictionReceipt:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", stage_id):
            raise ValueError("prediction stage ID is invalid")
        checkpoint = Path(checkpoint).resolve()
        if not checkpoint.is_file() or checkpoint.is_symlink():
            raise ValueError("prediction checkpoint must be a regular file")
        if checkpoint.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("prediction checkpoint exceeds 64 MiB")
        if not rows:
            raise ValueError("prediction batch is empty")
        requests: list[str] = []
        for row in rows:
            if not isinstance(row, dict) or "inputs" not in row:
                raise ValueError("prediction row has no inputs")
            requests.append(
                json.dumps(
                    {"task": self.package.task, "inputs": row["inputs"]},
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
            )
        request_bytes = ("\n".join(requests) + "\n").encode("utf-8")
        request_sha = hashlib.sha256(request_bytes).hexdigest()
        stdin_path = self.scratch_root / f"{stage_id}.stdin.jsonl"
        stdout_path = self.scratch_root / f"{stage_id}.stdout.jsonl"
        stderr_path = self.scratch_root / f"{stage_id}.stderr.txt"
        for path in (stdin_path, stdout_path, stderr_path):
            if path.exists():
                raise FileExistsError(f"prediction scratch conflict: {path}")
        stdin_path.write_bytes(request_bytes)
        started = time.monotonic()
        cpu_seconds = 0.0
        peak_rss = 0
        try:
            with stdin_path.open("rb") as stdin, stdout_path.open("wb") as stdout, stderr_path.open(
                "wb"
            ) as stderr:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "baselines.predict",
                        "--checkpoint",
                        str(checkpoint),
                    ],
                    cwd=self.worker_root,
                    env=self._environment(),
                    stdin=stdin,
                    stdout=stdout,
                    stderr=stderr,
                )
                observed = psutil.Process(process.pid)
                while process.poll() is None:
                    if time.monotonic() - started > timeout_seconds:
                        process.kill()
                        process.wait()
                        raise TimeoutError("official prediction worker timed out")
                    try:
                        family = [observed, *observed.children(recursive=True)]
                        cpu_seconds = max(
                            cpu_seconds,
                            sum(
                                member.cpu_times().user + member.cpu_times().system
                                for member in family
                            ),
                        )
                        peak_rss = max(
                            peak_rss,
                            sum(member.memory_info().rss for member in family),
                        )
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    time.sleep(0.005)
            if process.returncode != 0:
                error = stderr_path.read_text(encoding="utf-8", errors="replace")[-1000:]
                raise RuntimeError(f"official prediction worker failed: {error}")
            outputs = [
                json.loads(line)
                for line in stdout_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if len(outputs) != len(rows):
                raise ValueError("prediction output count mismatch")
            if self.package.task == "classification":
                predictions = np.asarray(
                    [
                        max(output["outputs"], key=lambda item: float(item["score"]))["label"]
                        for output in outputs
                    ],
                    dtype=str,
                )
            else:
                predictions = np.asarray(
                    [float(output["outputs"]["value"]) for output in outputs], dtype=np.float64
                )
            if predictions.shape != (len(rows),):
                raise ValueError("prediction output shape mismatch")
            if self.package.task == "regression" and not np.isfinite(predictions).all():
                raise ValueError("prediction output is nonfinite")
            return PredictionReceipt(
                predictions=predictions,
                wall_seconds=time.monotonic() - started,
                cpu_seconds=cpu_seconds,
                peak_rss_bytes=peak_rss,
                request_sha256=request_sha,
            )
        finally:
            for path in (stdin_path, stdout_path, stderr_path):
                if path.exists():
                    path.unlink()


def _read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict) or not isinstance(value.get("id"), str):
            raise ValueError(f"invalid public validation row {line_number}")
        rows.append(value)
    if not rows:
        raise ValueError("public validation is empty")
    return rows


def _ordered_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    meta_keys = set(rows[0].get("meta", {}))
    if {"source_subset", "unit", "cycle"} <= meta_keys:
        return sorted(
            rows,
            key=lambda row: (
                str(row["meta"]["source_subset"]),
                int(row["meta"]["unit"]),
                int(row["meta"]["cycle"]),
            ),
        )
    if {"bearing", "snapshot"} <= meta_keys:
        return sorted(
            rows,
            key=lambda row: (str(row["meta"]["bearing"]), int(row["meta"]["snapshot"])),
        )
    if "source_index" in meta_keys:
        return sorted(rows, key=lambda row: int(row["meta"]["source_index"]))
    return list(rows)


def _engine_group(row: dict[str, Any]) -> str | None:
    meta = row.get("meta", {})
    if isinstance(meta, dict) and {"source_subset", "unit"} <= set(meta):
        return f"{meta['source_subset']}:{meta['unit']}"
    return None


def _split_contiguous(rows: list[dict[str, Any]], rounds: int) -> list[list[dict[str, Any]]]:
    return [
        rows[(len(rows) * index) // rounds : (len(rows) * (index + 1)) // rounds]
        for index in range(rounds)
    ]


def _split_grouped(rows: list[dict[str, Any]], rounds: int) -> list[list[dict[str, Any]]]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for row in rows:
        group = _engine_group(row)
        if group is None:
            raise ValueError("grouped stream row has no unit identity")
        grouped.setdefault(group, []).append(row)
    if len(grouped) < rounds:
        raise ValueError("not enough independent groups for requested rounds")
    remaining = list(grouped.values())
    batches: list[list[dict[str, Any]]] = []
    for index in range(rounds):
        rounds_left = rounds - index
        rows_left = sum(len(group) for group in remaining)
        target = rows_left / rounds_left
        selected: list[dict[str, Any]] = []
        while remaining:
            groups_after = len(remaining) - 1
            if selected and len(selected) >= target and groups_after >= rounds_left - 1:
                break
            if groups_after < rounds_left - 1:
                break
            selected.extend(remaining.pop(0))
        if not selected:
            selected.extend(remaining.pop(0))
        batches.append(selected)
    if remaining:
        for group in remaining:
            batches[-1].extend(group)
    return batches


def _digest(values: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def freeze_public_validation_stream(
    package: PackageAudit, output_root: Path, *, rounds: int = 10
) -> FrozenPublicStream:
    """Create a one-time, auditable local stream without claiming hidden independence."""

    if rounds != 10:
        raise ValueError("controlled comparison requires ten rounds")
    output_root = Path(output_root)
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(f"frozen stream root already exists: {output_root}")
    output_root.mkdir(parents=True)
    rows = _ordered_rows(_read_rows(package.validation_path))
    grouped = _engine_group(rows[0]) is not None
    split = _split_grouped(rows, rounds) if grouped else _split_contiguous(rows, rounds)
    if any(not batch for batch in split):
        raise ValueError("frozen stream contains an empty batch")

    batches: list[FrozenPublicBatch] = []
    for index, batch_rows in enumerate(split, 1):
        path = output_root / f"batch-{index:02d}.jsonl"
        path.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
                for row in batch_rows
            ),
            encoding="utf-8",
            newline="\n",
        )
        ids = tuple(str(row["id"]) for row in batch_rows)
        groups = tuple(
            group for group in (_engine_group(row) for row in batch_rows) if group is not None
        )
        batches.append(
            FrozenPublicBatch(
                batch_index=index,
                batch_id=f"public-exposed-{index:02d}",
                path=path,
                sample_count=len(batch_rows),
                sample_id_digest=_digest(ids),
                group_digest=_digest(dict.fromkeys(groups)) if groups else None,
            )
        )

    stream = FrozenPublicStream(
        profile=package.profile,
        task_kind=package.task,
        source_sha256=package.validation_sha256,
        historically_exposed=True,
        batches=tuple(batches),
    )
    _atomic_json(
        output_root / "stream-manifest.json",
        {
            "format": "brace-msi.public-exposed-stream.v1",
            "profile": stream.profile,
            "task_kind": stream.task_kind,
            "source_sha256": stream.source_sha256,
            "historically_exposed": True,
            "rounds": rounds,
            "batches": [
                {
                    **asdict(batch),
                    "path": batch.path.name,
                }
                for batch in stream.batches
            ],
        },
    )
    return stream
