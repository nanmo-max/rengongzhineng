import json
import io
from pathlib import Path
import sys

from brace_msi.cli import main
from brace_msi.recording import LocalPublicSpool
from brace_msi.swanlab_adapter import (
    SwanLabOfflineConfig,
    build_sync_command,
    export_public_spool,
)


class _FakeRun:
    def __init__(self) -> None:
        self.records: list[tuple[dict[str, float | int], int]] = []

    def log(self, payload: dict[str, float | int], *, step: int) -> None:
        self.records.append((payload, step))


class _FakeSwanLab:
    def __init__(self) -> None:
        self.init_kwargs: dict[str, object] | None = None
        self.run = _FakeRun()
        self.finished = False

    def init(self, **kwargs: object) -> _FakeRun:
        self.init_kwargs = kwargs
        return self.run

    def finish(self) -> None:
        self.finished = True


def test_offline_export_logs_only_aggregate_numeric_fields(tmp_path: Path) -> None:
    spool_path = tmp_path / "public.jsonl"
    spool = LocalPublicSpool(spool_path)
    spool.record(
        "candidate_evaluated",
        {
            "task_id": "gas",
            "batch_id": "batch-1",
            "primary_metric": 0.81,
            "cpu_seconds": 0.25,
            "accepted": True,
            "raw_features": [[1.0, 2.0]],
            "targets": [1],
            "api_key": "secret",
        },
    )
    fake = _FakeSwanLab()
    config = SwanLabOfflineConfig(
        project="brace-msi",
        experiment_name="release-test",
        logdir=tmp_path / "swanlog",
    )

    result = export_public_spool(spool_path, config, swanlab_module=fake)

    assert result.record_count == 1
    assert fake.init_kwargs is not None
    assert fake.init_kwargs["mode"] == "offline"
    assert fake.init_kwargs["public"] is False
    assert "api_key" not in fake.init_kwargs
    assert fake.finished is True
    payload, step = fake.run.records[0]
    assert step == 0
    assert payload["brace/primary_metric"] == 0.81
    assert payload["brace/cpu_seconds"] == 0.25
    assert payload["brace/accepted"] == 1
    serialized = json.dumps(payload)
    assert "raw_features" not in serialized
    assert "targets" not in serialized
    assert "api_key" not in serialized


def test_sync_command_is_explicit_and_never_embeds_api_key(tmp_path: Path) -> None:
    command = build_sync_command(
        tmp_path / "swanlog" / "run-abc",
        workspace="team",
        project="brace-msi",
    )

    assert command == (
        "swanlab",
        "sync",
        str(tmp_path / "swanlog" / "run-abc"),
        "--workspace",
        "team",
        "--project",
        "brace-msi",
    )
    assert not any("key" in part.lower() or "secret" in part.lower() for part in command)


def test_cli_exports_offline_log_without_syncing(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    spool_path = tmp_path / "public.jsonl"
    LocalPublicSpool(spool_path).record("run_finished", {"candidate_count": 3})
    fake = _FakeSwanLab()
    monkeypatch.setitem(sys.modules, "swanlab", fake)

    exit_code = main(
        [
            "swanlab-offline-export",
            "--spool",
            str(spool_path),
            "--logdir",
            str(tmp_path / "swanlog"),
            "--project",
            "brace-msi",
            "--experiment-name",
            "release-test",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "offline_export_completed"
    assert output["record_count"] == 1
    assert fake.init_kwargs is not None
    assert fake.init_kwargs["mode"] == "offline"


def test_export_reconfigures_non_utf8_text_streams_before_swanlab_init(
    tmp_path: Path, monkeypatch
) -> None:
    class _ReconfigurableStream(io.StringIO):
        encoding = "gbk"

        def __init__(self) -> None:
            super().__init__()
            self.reconfigured_to: str | None = None

        def reconfigure(self, *, encoding: str) -> None:
            self.reconfigured_to = encoding

    stdout = _ReconfigurableStream()
    stderr = _ReconfigurableStream()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    spool_path = tmp_path / "public.jsonl"
    LocalPublicSpool(spool_path).record("run_finished", {"candidate_count": 3})

    export_public_spool(
        spool_path,
        SwanLabOfflineConfig("brace-msi", "encoding-test", tmp_path / "swanlog"),
        swanlab_module=_FakeSwanLab(),
    )

    assert stdout.reconfigured_to == "utf-8"
    assert stderr.reconfigured_to == "utf-8"
