"""Atomic run artifacts, deterministic identities, and resume safety."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from legal_skill_guard.utils.hashing import canonical_json_sha256

ModelT = TypeVar("ModelT", bound=BaseModel)


class ImmutableArtifactConflictError(FileExistsError):
    """An immutable artifact path already contains different JSON content."""


def safe_component(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_.-")
    if not normalized or normalized != value:
        raise ValueError(f"Unsafe artifact path component: {value!r}")
    return normalized


def trajectory_identity(
    *,
    run_id: str,
    partition: str,
    method: str,
    case_id: str,
    persona: str,
    seed: int,
    sample_index: int,
    skill_library_version: str,
) -> str:
    value = {
        "run_id": run_id,
        "partition": partition,
        "method": method,
        "case_id": case_id,
        "persona": persona,
        "seed": seed,
        "sample_index": sample_index,
        "skill_library_version": skill_library_version,
    }
    return f"traj_{canonical_json_sha256(value)[:24]}"


class RunStore:
    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root / safe_component(run_id)
        self.run_id = run_id

    def trajectory_path(self, partition: str, trajectory_id: str) -> Path:
        return (
            self.root
            / "trajectories"
            / safe_component(partition)
            / f"{safe_component(trajectory_id)}.json"
        )

    def evaluation_path(self, trajectory_id: str) -> Path:
        return self.root / "evaluations" / f"{safe_component(trajectory_id)}.json"

    def save_model(self, path: Path, value: BaseModel, *, overwrite: bool = False) -> None:
        if path.exists() and not overwrite:
            raise FileExistsError(path)
        self.atomic_json(path, value.model_dump(mode="json", exclude_computed_fields=True))

    def load_model(self, path: Path, model: type[ModelT]) -> ModelT:
        return model.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def write_manifest(self, name: str, value: dict[str, Any], *, overwrite: bool = False) -> Path:
        path = self.root / "manifests" / f"{safe_component(name)}.json"
        payload = dict(value)
        payload["content_sha256"] = canonical_json_sha256(value)
        if overwrite:
            self.atomic_json(path, payload)
        else:
            self.immutable_json(path, payload)
        return path

    def read_manifest(self, name: str) -> dict[str, Any]:
        path = self.root / "manifests" / f"{safe_component(name)}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "content_sha256" not in payload:
            raise ValueError(f"invalid manifest envelope: {path}")
        content_hash = payload.pop("content_sha256")
        if canonical_json_sha256(payload) != content_hash:
            raise ValueError(f"manifest hash mismatch: {path}")
        payload["content_sha256"] = content_hash
        return payload

    def read_run_bound_json(
        self,
        path: Path,
        *,
        run_manifest_sha256: str,
    ) -> dict[str, Any]:
        """Read a diagnostic artifact only when its immutable run binding matches."""

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid run-bound JSON artifact: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"run-bound JSON artifact must be an object: {path}")
        if payload.get("run_id") != self.run_id:
            raise ValueError(
                f"run-bound JSON run_id mismatch: {path}: "
                f"expected={self.run_id!r} actual={payload.get('run_id')!r}"
            )
        actual_binding = payload.get("run_manifest_sha256")
        if actual_binding != run_manifest_sha256:
            raise ValueError(
                f"run-bound JSON manifest mismatch: {path}: "
                f"expected={run_manifest_sha256} actual={actual_binding}"
            )
        return payload

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
