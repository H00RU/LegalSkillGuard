#!/usr/bin/env python3
"""Create a verified, immutable DLawBench raw-data snapshot."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "third_party" / "DLawBench"
DEFAULT_DESTINATION = ROOT / "data" / "raw" / "dlawbench"
DEFAULT_MANIFEST = ROOT / "data" / "manifests" / "dlawbench_source.json"
EXPECTED_REVISION = "9f6325f29f07b296fac110a6e1880bdd5d9ca538"

COPY_PATHS = (
    Path("data"),
    Path("metadata"),
    Path("schema"),
    Path("config/personas.json"),
    Path("LICENSE"),
    Path("README.md"),
    Path("README_zh.md"),
)


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_git_revision(source: Path) -> str:
    git_dir = source / ".git"
    head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head
    ref = head.removeprefix("ref: ")
    loose_ref = git_dir / ref
    if loose_ref.is_file():
        return loose_ref.read_text(encoding="utf-8").strip()
    packed_refs = git_dir / "packed-refs"
    if packed_refs.is_file():
        for line in packed_refs.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith(("#", "^")):
                continue
            revision, candidate_ref = line.split(" ", 1)
            if candidate_ref == ref:
                return revision
    raise RuntimeError(f"Cannot resolve Git revision {ref!r} in {git_dir}")


def set_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_symlink():
            raise RuntimeError(f"Raw snapshots must not contain symlinks: {path}")
        if path.is_file():
            path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        elif path.is_dir():
            path.chmod(
                stat.S_IRUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IXGRP
                | stat.S_IROTH
                | stat.S_IXOTH
            )
    root.chmod(
        stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
    )


def build_file_manifest(snapshot: Path) -> dict[str, dict[str, int | str]]:
    files: dict[str, dict[str, int | str]] = {}
    for path in sorted(p for p in snapshot.rglob("*") if p.is_file()):
        relative = path.relative_to(snapshot).as_posix()
        files[relative] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    return files


def copy_snapshot(source: Path, snapshot: Path) -> None:
    snapshot.mkdir(parents=True, exist_ok=False)
    for relative in COPY_PATHS:
        src = source / relative
        dst = snapshot / relative
        if not src.exists():
            raise FileNotFoundError(f"Required upstream path is missing: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def preserve_prepared_at(manifest_path: Path, manifest: dict[str, object]) -> None:
    """Keep source manifests byte-stable when the verified snapshot is unchanged."""
    if not manifest_path.is_file():
        return
    previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    previous_content = {key: value for key, value in previous.items() if key != "prepared_at"}
    current_content = {key: value for key, value in manifest.items() if key != "prepared_at"}
    if previous_content == current_content:
        manifest["prepared_at"] = previous["prepared_at"]


def prepare(
    source: Path,
    destination_root: Path,
    repository: str = "https://github.com/SKYLENAGE-AI/DLawBench.git",
    expected_revision: str = EXPECTED_REVISION,
) -> tuple[Path, dict[str, object]]:
    """Prepare and return a verified snapshot plus its source manifest."""

    source = source.resolve()
    revision = read_git_revision(source)
    if revision != expected_revision:
        raise RuntimeError(
            f"DLawBench revision mismatch: expected {expected_revision}, observed {revision}"
        )

    snapshot = destination_root.resolve() / revision
    if not snapshot.exists():
        copy_snapshot(source, snapshot)

    files = build_file_manifest(snapshot)
    manifest = {
        "dataset": "DLawBench public release",
        "repository": repository,
        "revision": revision,
        "snapshot": os.path.relpath(snapshot, ROOT),
        "prepared_at": datetime.now(UTC).isoformat(),
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

    snapshot, manifest = prepare(
        args.source,
        args.destination_root,
        expected_revision=args.expected_revision,
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    preserve_prepared_at(args.manifest, manifest)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "snapshot": str(snapshot),
                "revision": manifest["revision"],
                "files": manifest["file_count"],
            }
        )
    )


if __name__ == "__main__":
    main()
