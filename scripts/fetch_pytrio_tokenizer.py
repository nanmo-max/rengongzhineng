"""Fetch and verify the Qwen3.5-4B tokenizer without model weights.

This build-only helper makes the formal image independent of runtime access to
ModelScope/Hugging Face.  The PyTRiO service still hosts all model weights and
inference; only deterministic text tokenization assets enter the image.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from modelscope.hub.snapshot_download import snapshot_download


MODEL_ID = "Qwen/Qwen3.5-4B"
EXPECTED_SHA256 = {
    "chat_template.jinja": "a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715",
    "config.json": "ddc63e1c717afa86c865bb5e01313d89d72bb53b97ad4a8a03ba8510c0621670",
    "configuration.json": "f888421726665e8a84b738eed42a64875aed79de8be7daade851ac8bf4c0cef9",
    "merges.txt": "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d",
    "tokenizer_config.json": "316230d6a809701f4db5ea8f8fc862bc3a6f3229c937c174e674ff3ca0a64ac8",
    "tokenizer.json": "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42",
    "vocab.json": "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003",
}
FORBIDDEN_SUFFIXES = {".safetensors", ".bin", ".pt", ".pth", ".onnx"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    cache_root = Path(
        os.environ.get("MODELSCOPE_CACHE", "/opt/brace-tokenizer-cache")
    ).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    snapshot = Path(
        snapshot_download(
            MODEL_ID,
            cache_dir=cache_root,
            allow_file_pattern=sorted(EXPECTED_SHA256),
        )
    ).resolve()
    observed: dict[str, str] = {}
    for name, expected in EXPECTED_SHA256.items():
        path = snapshot / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"tokenizer asset missing or invalid: {name}")
        actual = _sha256(path)
        if actual != expected:
            raise RuntimeError(f"tokenizer asset digest mismatch: {name}")
        observed[name] = actual
    forbidden = [
        path.relative_to(cache_root).as_posix()
        for path in cache_root.rglob("*")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES
    ]
    if forbidden:
        raise RuntimeError(f"model weight files entered tokenizer cache: {forbidden}")
    manifest = {
        "format": "brace-msi.pytrio-tokenizer-bundle.v1",
        "model_id": MODEL_ID,
        "files": observed,
        "model_weights_included": False,
    }
    (cache_root / "BRACE_TOKENIZER_MANIFEST.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
