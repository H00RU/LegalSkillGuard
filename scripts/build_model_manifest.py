#!/usr/bin/env python3
"""Build the per-file integrity manifest for a pinned local model snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--license", required=True)
    parser.add_argument("--download-source")
    parser.add_argument("--verify-huggingface", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    snapshot = (root / args.snapshot).resolve()
    if not snapshot.is_dir():
        raise SystemExit(f"Snapshot does not exist: {snapshot}")
    index_path = snapshot / "model.safetensors.index.json"
    if not index_path.is_file():
        raise SystemExit(f"Weight index does not exist: {index_path}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    required_shards = sorted(set(index.get("weight_map", {}).values()))
    missing_shards = [name for name in required_shards if not (snapshot / name).is_file()]
    if missing_shards:
        raise SystemExit(f"Snapshot is missing indexed weight shards: {missing_shards}")

    canonical_source = f"https://huggingface.co/{args.model_id}"
    upstream_sha256: dict[str, str] = {}
    if args.verify_huggingface:
        metadata_url = (
            f"https://huggingface.co/api/models/{args.model_id}/revision/{args.revision}?blobs=true"
        )
        with urlopen(metadata_url, timeout=60) as response:
            upstream = json.load(response)
        if upstream.get("sha") != args.revision:
            raise SystemExit("Hugging Face metadata returned a different revision")
        upstream_sha256 = {
            str(item["rfilename"]): str(item["lfs"]["sha256"])
            for item in upstream.get("siblings", [])
            if item.get("lfs", {}).get("sha256")
        }

    files: dict[str, dict[str, int | str]] = {}
    for path in sorted(snapshot.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        actual_sha256 = sha256_file(path)
        expected_sha256 = upstream_sha256.get(path.name)
        if expected_sha256 is not None and actual_sha256 != expected_sha256:
            raise SystemExit(
                f"Official Hugging Face SHA-256 mismatch for {path.name}: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        files[path.name] = {
            "bytes": path.stat().st_size,
            "sha256": actual_sha256,
            **({"upstream_sha256": expected_sha256} if expected_sha256 else {}),
        }

    relative_snapshot = snapshot.relative_to(root).as_posix()
    manifest = {
        "model_id": args.model_id,
        "revision": args.revision,
        "verified_at": datetime.now(UTC).isoformat(),
        "canonical_source": canonical_source,
        "download_source": args.download_source or canonical_source,
        "license": args.license,
        "snapshot": relative_snapshot,
        "upstream_hashes_verified": args.verify_huggingface,
        "files": files,
        "expected_hash_provenance": {
            "metadata": (
                f"https://huggingface.co/api/models/{args.model_id}/revision/"
                f"{args.revision}?blobs=true"
            ),
            "content": f"{canonical_source}/resolve/{args.revision}/<filename>",
        },
    }
    output = (root / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, delete=False
    ) as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)
    print(output)


if __name__ == "__main__":
    main()
