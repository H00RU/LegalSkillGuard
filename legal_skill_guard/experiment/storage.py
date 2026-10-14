"""Atomic and immutable JSON artifacts only; no consultation trajectory layer."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from legal_skill_guard.utils.hashing import canonical_json_sha256


class ImmutableArtifactConflictError(FileExistsError):
    """An immutable artifact path already contains different JSON content."""


def safe_component(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_.-")
    if not normalized or normalized != value:
        raise ValueError(f"Unsafe artifact path component: {value!r}")
    return normalized


class RunStore:
    @staticmethod
    def atomic_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(path)

    @staticmethod
    def immutable_json(path: Path, value: Any) -> Path:
        """Create a JSON artifact once, allowing only content-identical retries.

        Equality is based on canonical JSON rather than whitespace or dictionary
        insertion order.  Creation uses an exclusive hard-link commit so two
        concurrent writers cannot silently replace one another.
        """

        expected_sha256 = canonical_json_sha256(value)
        path.parent.mkdir(parents=True, exist_ok=True)

        def validate_existing() -> Path:
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ImmutableArtifactConflictError(
                    f"immutable JSON artifact is unreadable: {path}: {exc}"
                ) from exc
            actual_sha256 = canonical_json_sha256(existing)
            if actual_sha256 != expected_sha256:
                raise ImmutableArtifactConflictError(
                    "immutable JSON artifact conflict: "
                    f"{path} existing_sha256={actual_sha256} "
                    f"requested_sha256={expected_sha256}"
                )
            return path

        if path.exists():
            return validate_existing()

        serialized = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(serialized)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                return validate_existing()
            return path
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
