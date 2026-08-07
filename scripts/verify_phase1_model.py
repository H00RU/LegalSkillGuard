#!/usr/bin/env python3
"""Verify the pinned Qwen3-4B snapshot and write a reproducible model manifest."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import yaml
from huggingface_hub import snapshot_download

from legal_skill_guard.utils.hashing import sha256_file

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "Qwen/Qwen3-4B"
REVISION = "1cfa9a7208912126459214e8b04321603b3df60c"
EXPECTED_LFS = {
    "model-00001-of-00003.safetensors": (
        3957900840,
        "328a91d3122359d5547f9d79521205bc0a46e1f79a792dfe650e99fc2d651223",
    ),
    "model-00002-of-00003.safetensors": (
        3987450520,
        "6cd087b316306a68c562436b5492edbcf6e16c6dba3a1308279caa5a58e21ca5",
    ),
    "model-00003-of-00003.safetensors": (
        99630640,
        "e4bf436957184f4eeb86a80e9db394503f1f56446b2e6b7edeac5b81470f4ca1",
    ),
    "tokenizer.json": (
        11422654,
        "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4",
    ),
}
DEFAULT_OUTPUT = ROOT / "data/manifests/qwen3_4b_model.json"
DEFAULT_CONFIG = ROOT / "configs/experiments/phase1_pilot.yaml"


def resolve_snapshot(config_path: Path) -> tuple[Path, str]:
    """Prefer the configured immutable local mirror; fall back to the HF cache."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    configured = ROOT / config["model"]["local_path"]
    if configured.is_dir() and all((configured / name).is_file() for name in EXPECTED_LFS):
        return configured, config["model"].get("download_mirror", "local")

    cache = ROOT / "data/cache/huggingface"
    os.environ["HF_HOME"] = str(cache)
    snapshot = Path(
        snapshot_download(
            MODEL_ID,
            revision=REVISION,
            cache_dir=cache / "hub",
            local_files_only=True,
        )
    )
    return snapshot, f"https://huggingface.co/{MODEL_ID}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    snapshot, download_source = resolve_snapshot(args.config.resolve())
    files = {}
    for path in sorted(item for item in snapshot.iterdir() if item.is_file()):
        files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    for name, (expected_bytes, expected_sha256) in EXPECTED_LFS.items():
        observed = files.get(name)
        if observed != {"bytes": expected_bytes, "sha256": expected_sha256}:
            raise RuntimeError(f"Pinned model file verification failed for {name}: {observed}")

    license_text = (snapshot / "LICENSE").read_text(encoding="utf-8")
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        raise RuntimeError("Pinned model LICENSE is not recognizable as Apache-2.0")
    manifest = {
        "model_id": MODEL_ID,
        "revision": REVISION,
        "verified_at": datetime.now(UTC).isoformat(),
        "canonical_source": f"https://huggingface.co/{MODEL_ID}",
        "download_source": download_source,
        "license": "Apache-2.0",
        "snapshot": str(snapshot),
        "files": files,
        "expected_lfs_provenance": (
            f"https://huggingface.co/api/models/{MODEL_ID}/revision/{REVISION}?blobs=true"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "model_id": MODEL_ID,
                "revision": REVISION,
                "files": len(files),
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
