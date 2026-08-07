#!/usr/bin/env python3
"""Snapshot the public LeCoDe repository and record its gated-data boundary."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from scripts.prepare_dlawbench import (
    build_file_manifest,
    read_git_revision,
    set_read_only,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "third_party" / "LeCoDe"
DEFAULT_DESTINATION = ROOT / "data" / "raw" / "lecode"
DEFAULT_MANIFEST = ROOT / "data" / "manifests" / "lecode_source.json"
EXPECTED_REVISION = "36104863438bd61c6ea7072cc8c63dcacb074631"
REPOSITORY = "https://github.com/PiLab-ZJU/LeCoDe.git"
EXPECTED_DATA_FILES = ("LeCoDe_trainset.jsonl", "LeCoDe_testset.jsonl")
COPY_PATHS = (Path("README.md"), Path("requirement.txt"), Path("src"), Path("app_agreement"))


def prepare(
    source: Path = DEFAULT_SOURCE,
    destination_root: Path = DEFAULT_DESTINATION,
    expected_revision: str = EXPECTED_REVISION,
) -> tuple[Path, dict[str, object]]:
    source = source.resolve()
    revision = read_git_revision(source)
    if revision != expected_revision:
        raise RuntimeError(
            f"LeCoDe revision mismatch: expected {expected_revision}, observed {revision}"
        )

    snapshot = destination_root.resolve() / revision
    if not snapshot.exists():
        snapshot.mkdir(parents=True, exist_ok=False)
        for relative in COPY_PATHS:
            src = source / relative
            if not src.exists():
                raise FileNotFoundError(f"Required upstream path is missing: {src}")
            dst = snapshot / relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    observed_data_files = {
        name: any(path.name == name for path in source.rglob(name))
        for name in EXPECTED_DATA_FILES
    }
    files = build_file_manifest(snapshot)
    manifest: dict[str, object] = {
        "dataset": "LeCoDe gated release",
        "repository": REPOSITORY,
        "revision": revision,
        "snapshot": os.path.relpath(snapshot, ROOT),
        "prepared_at": datetime.now(UTC).isoformat(),
        "declared_license": "CC-BY-NC-ND-4.0",
        "access": {
            "status": "application_required",
            "dataset_files_present": all(observed_data_files.values()),
            "expected_files": observed_data_files,
            "application_requires_institutional_identity_and_signatures": True,
            "application_email": "yuanwk@zju.edu.cn",
            "redistribution_allowed": False,
        },
        "paper_statistics": {
            "dialogues": 3696,
            "turns": 110008,
            "train_dialogues": 2956,
            "test_dialogues": 740,
        },
        "file_count": len(files),
        "files": files,
    }
    set_read_only(snapshot)
    return snapshot, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination-root", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--expected-revision", default=EXPECTED_REVISION)
    args = parser.parse_args()

    snapshot, manifest = prepare(args.source, args.destination_root, args.expected_revision)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "snapshot": str(snapshot),
                "revision": manifest["revision"],
                "dataset_files_present": manifest["access"]["dataset_files_present"],
            }
        )
    )


if __name__ == "__main__":
    main()
