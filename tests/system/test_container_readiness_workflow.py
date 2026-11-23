from pathlib import Path


def test_container_readiness_workflow_enforces_release_limits() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/container-readiness.yml").read_text(
        encoding="utf-8"
    )

    assert "docker build --pull --tag brace-msi:candidate ." in workflow
    assert "--network=none" in workflow
    assert "--cpus=4" in workflow
    assert "--memory=4g" in workflow
    assert "test \"$size_bytes\" -lt 2000000000" in workflow
    assert "synthetic-smoke --output /outputs/smoke" in workflow
    assert "container-image-audit.json" in workflow
    assert "actions/upload-artifact@v4" in workflow

    verifier = (root / "scripts/verify_workspace_v2_image.py").read_text(encoding="utf-8")
    assert verifier.count('"--memory", "4g"') == 2
    assert '"--memory", "8g"' not in verifier
