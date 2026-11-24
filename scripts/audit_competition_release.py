"""Machine audit for a Competition Core release evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import tarfile
from typing import Any, Mapping, Sequence


_REQUIRED_SDK = {
    "src/contest_harness/protocol.py",
    "src/contest_harness/round.py",
    "src/brace_formal/submission.py",
    "submission/harness.py",
}
_FORBIDDEN_PARTS = {
    "tests", "docs", "data", "dataji", "weights", "reports", "artifacts",
    "pytrio", "swanlab", "tokenizer", "sampler", "__pycache__", ".git",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gate(ok: bool, evidence: Any) -> dict[str, Any]:
    return {"status": "PASS" if ok else "FAIL", "evidence": evidence}


def _blocked(reason: str) -> dict[str, Any]:
    return {"status": "BLOCKED_EXTERNAL", "evidence": reason}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"evidence is not an object: {path}")
    return value


def _docker_save_members(path: Path) -> tuple[bool, list[str]]:
    try:
        with tarfile.open(path, "r") as archive:
            names = archive.getnames()
            if "manifest.json" not in names:
                return False, names[:20]
            manifest_file = archive.extractfile("manifest.json")
            if manifest_file is None:
                return False, names[:20]
            manifest = json.loads(manifest_file.read().decode("utf-8"))
            valid = isinstance(manifest, list) and bool(manifest)
            return valid, names[:20]
    except (tarfile.TarError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False, []


def audit_competition_release(
    release_manifest_path: Path,
    acceptance_path: Path | Sequence[Path],
    blackbox_path: Path,
    archive_path: Path,
    *,
    expected_source_commit: str,
) -> dict[str, Any]:
    acceptance_paths = (
        (Path(acceptance_path),)
        if isinstance(acceptance_path, (str, Path))
        else tuple(Path(path) for path in acceptance_path)
    )
    paths = (
        Path(release_manifest_path),
        *acceptance_paths,
        Path(blackbox_path),
        Path(archive_path),
    )
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        gates = {"release_evidence": _blocked("missing: " + ", ".join(missing))}
        return {"format": "brace-msi.competition-release-audit.v1", "valid": False, "gates": gates}

    release = _load(paths[0])
    acceptances = [_load(path) for path in acceptance_paths]
    blackbox = _load(Path(blackbox_path))
    files = tuple(str(item) for item in release.get("content_manifest", {}).get("files", ()))
    normalized_parts = {
        part.lower()
        for file in files
        for part in Path(file.replace("/", "\\")).parts
    }
    forbidden = sorted(normalized_parts & _FORBIDDEN_PARTS)
    profiles: dict[str, Any] = {}
    duplicate_profiles: list[str] = []
    for acceptance in acceptances:
        current = acceptance.get("profiles", {})
        if not isinstance(current, dict):
            continue
        for name, profile in current.items():
            if name in profiles:
                duplicate_profiles.append(str(name))
            profiles[str(name)] = profile
    rounds = [row for profile in profiles.values() if isinstance(profile, dict) for row in profile.get("rounds", [])]
    calls_ok = bool(rounds) and all(len(row.get("model_call_ids", [])) >= 2 for row in rounds)
    candidates_ok = bool(rounds) and all(row.get("candidate_submitted") is True for row in rounds)
    proposals_ok = bool(rounds) and all(
        row.get("proposal_parse_error") in (None, "")
        and row.get("proposal_evidence_valid") is True
        for row in rounds
    )
    required_profiles = {"A", "B", "C"}
    profiles_ok = bool(profiles) and not duplicate_profiles and all(
        isinstance(profile, dict)
        and len(profile.get("rounds", [])) == 10
        and sum(len(row.get("model_call_ids", [])) for row in profile.get("rounds", [])) == 20
        and profile.get("prediction_smoke_rows") == 5
        for profile in profiles.values()
    ) and required_profiles.issubset(profiles)
    acceptance_valid = bool(acceptances) and all(item.get("valid") is True for item in acceptances)
    archive_ok, archive_members = _docker_save_members(Path(archive_path))

    gates = {
        "source_binding": _gate(release.get("source_commit") == expected_source_commit, release.get("source_commit")),
        "formal_forbidden_content": _gate(not forbidden, forbidden),
        "official_sdk_files": _gate(_REQUIRED_SDK.issubset(files), sorted(_REQUIRED_SDK - set(files))),
        "acceptance_reports": _gate(
            acceptance_valid and profiles_ok,
            {"profiles": sorted(profiles), "duplicates": sorted(duplicate_profiles)},
        ),
        "dual_model_calls": _gate(calls_ok, {"rounds": len(rounds)}),
        "every_round_candidate": _gate(candidates_ok, {"rounds": len(rounds)}),
        "training_proposals_executed": _gate(
            proposals_ok,
            {
                "rounds": len(rounds),
                "failed": sum(
                    1
                    for row in rounds
                    if row.get("proposal_parse_error") not in (None, "")
                    or row.get("proposal_evidence_valid") is not True
                ),
            },
        ),
        "wrong_deploy_rejected": _gate(blackbox.get("wrong_deploy_accepted") is False, blackbox.get("wrong_deploy_accepted")),
        "history_rollback": _gate(blackbox.get("history_rollback_valid") is True, blackbox.get("history_rollback_valid")),
        "model_reload": _gate(blackbox.get("model_reload_predictions_equal") is True, blackbox.get("model_reload_predictions_equal")),
        "docker_save_archive": _gate(archive_ok, {"sha256": _sha256(Path(archive_path)), "members": archive_members}),
    }
    return {
        "format": "brace-msi.competition-release-audit.v1",
        "valid": all(item["status"] == "PASS" for item in gates.values()),
        "gates": gates,
    }


def render_release_html(
    audit: Mapping[str, Any],
    release: Mapping[str, Any],
    acceptances: Sequence[Mapping[str, Any]],
    blackbox: Mapping[str, Any],
) -> str:
    profiles: dict[str, Mapping[str, Any]] = {}
    for acceptance in acceptances:
        current = acceptance.get("profiles")
        if isinstance(current, Mapping):
            profiles.update({str(key): value for key, value in current.items() if isinstance(value, Mapping)})
    gate_rows = "".join(
        "<tr><td>{}</td><td class='{}'>{}</td><td><code>{}</code></td></tr>".format(
            html.escape(str(name)),
            "pass" if gate.get("status") == "PASS" else "fail",
            html.escape(str(gate.get("status"))),
            html.escape(json.dumps(gate.get("evidence"), ensure_ascii=False, sort_keys=True)),
        )
        for name, gate in audit.get("gates", {}).items()
        if isinstance(gate, Mapping)
    )
    profile_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td><code>{}</code></td></tr>".format(
            html.escape(name),
            len(profile.get("rounds", [])),
            profile.get("model_call_count", 0),
            sum(1 for row in profile.get("rounds", []) if isinstance(row, Mapping) and row.get("candidate_submitted") is True),
            html.escape(str(profile.get("final_artifact_id", ""))),
        )
        for name, profile in sorted(profiles.items())
    )
    swanlab = release.get("swanlab", {})
    swanlab_url = swanlab.get("public_url", "") if isinstance(swanlab, Mapping) else ""
    archive = release.get("archive", {})
    archive_sha256 = archive.get("sha256", "") if isinstance(archive, Mapping) else ""
    agent_model = release.get("agent_model", {})
    agent_name = agent_model.get("name", "") if isinstance(agent_model, Mapping) else ""
    agent_selection = agent_model.get("selection", "") if isinstance(agent_model, Mapping) else ""
    return f"""<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'><title>BRACE-MSI 本地发布验收</title>
<style>body{{font-family:system-ui,sans-serif;margin:32px;color:#222}}h1{{margin-bottom:4px}}.notice{{background:#fff3cd;padding:12px;border-radius:8px}}table{{border-collapse:collapse;width:100%;margin:16px 0}}th,td{{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}}th{{background:#f4f5f7}}.pass{{color:#137333;font-weight:700}}.fail{{color:#b3261e;font-weight:700}}code{{font-size:12px;word-break:break-all}}</style></head><body>
<h1>BRACE-MSI 训练与评测报告</h1>
<p class='notice'><strong>LOCAL RELEASE ACCEPTANCE — NOT AN OFFICIAL SCORE</strong><br>本报告验证正式镜像的协议、训练、选择、回滚、资源边界与可复现性；不代表官方隐藏测试成绩。</p>
<h2>发布信息</h2><table>
<tr><th>镜像</th><td><code>{html.escape(str(release.get('tag', '')))}</code></td></tr>
<tr><th>镜像ID</th><td><code>{html.escape(str(release.get('image_id', '')))}</code></td></tr>
<tr><th>源码提交</th><td><code>{html.escape(str(release.get('source_commit', '')))}</code></td></tr>
<tr><th>归档SHA-256</th><td><code>{html.escape(str(archive_sha256))}</code></td></tr>
<tr><th>Agent模型</th><td>{html.escape(str(agent_name))}（{html.escape(str(agent_selection))}）</td></tr>
<tr><th>SwanLab</th><td><a href='{html.escape(str(swanlab_url))}'>{html.escape(str(swanlab_url))}</a></td></tr></table>
<h2>十轮协议复演</h2><table><tr><th>任务画像</th><th>轮数</th><th>模型调用</th><th>真实候选</th><th>最终产物</th></tr>{profile_rows}</table>
<h2>发布门</h2><table><tr><th>检查项</th><th>状态</th><th>证据</th></tr>{gate_rows}</table>
<h2>黑盒安全行为</h2><pre>{html.escape(json.dumps(dict(blackbox), ensure_ascii=False, indent=2, sort_keys=True))}</pre>
<h2>边界</h2><p>公开开发投影在协议复演中重复用于同范围门控，因此其中数值仅用于接入与选择逻辑验证，不作为独立泛化证据。真实平台生命周期、隐藏数据与官方评分仍只能由平台试运行确认。</p>
</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, action="append", required=True)
    parser.add_argument("--blackbox", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--html-output", type=Path)
    args = parser.parse_args()
    result = audit_competition_release(
        args.release_manifest, args.acceptance, args.blackbox, args.archive,
        expected_source_commit=args.source_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.html_output is not None:
        release = _load(args.release_manifest)
        acceptances = [_load(path) for path in args.acceptance]
        blackbox = _load(args.blackbox)
        args.html_output.parent.mkdir(parents=True, exist_ok=True)
        args.html_output.write_text(
            render_release_html(result, release, acceptances, blackbox), encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
