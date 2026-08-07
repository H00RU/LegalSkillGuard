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
EXPECTED_FILES = {
    "LICENSE": (
        11343,
        "832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e",
    ),
    "README.md": (
        16857,
        "71add1cd091c309b1cb1a6b943f2476eb2b004124b3bd1d32dcd0b24cc1abc47",
    ),
    "config.json": (
        726,
        "8ba006f74fecfaaeb392872a60f4a480e7ec9860153d2e1b769ec81f9a147f8a",
    ),
    "generation_config.json": (
        239,
        "2325da0f15bb848e018c5ae071b7943332e9f871d6b60e2ed22ca97d4cb993d2",
    ),
    "merges.txt": (
        1671853,
        "8831e4f1a044471340f7c0a83d7bd71306a5b867e95fd870f74d0c5308a904d5",
    ),
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
    "model.safetensors.index.json": (
        32819,
        "6dc0981b8829fead746441f68f38f24c5ca4a3a66351f652c26c6df0efc43ab2",
    ),
    "tokenizer.json": (
        11422654,
        "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4",
    ),
    "tokenizer_config.json": (
        9732,
        "d5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101",
    ),
    "vocab.json": (
        2776833,
        "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910",
    ),
}
DEFAULT_OUTPUT = ROOT / "data/manifests/qwen3_4b_model.json"
DEFAULT_CONFIG = ROOT / "configs/experiments/phase1_pilot.yaml"


def resolve_snapshot(config_path: Path) -> tuple[Path, str]:
    """Prefer the configured immutable local mirror; fall back to the HF cache."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    configured = ROOT / config["model"]["local_path"]
    if configured.is_dir() and all((configured / name).is_file() for name in EXPECTED_FILES):
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
    for name in sorted(EXPECTED_FILES):
        path = snapshot / name
        files[name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    for name, (expected_bytes, expected_sha256) in EXPECTED_FILES.items():
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
        "snapshot": str(snapshot.relative_to(ROOT)),
        "files": files,
        "expected_hash_provenance": {
            "metadata": (
                f"https://huggingface.co/api/models/{MODEL_ID}/revision/"
                f"{REVISION}?blobs=true"
            ),
            "content": f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/<filename>",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.is_file():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        old_content = {key: value for key, value in previous.items() if key != "verified_at"}
        new_content = {key: value for key, value in manifest.items() if key != "verified_at"}
        if old_content == new_content:
            manifest["verified_at"] = previous["verified_at"]
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
