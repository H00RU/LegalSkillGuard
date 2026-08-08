"""Immutable skill-library versions with activation, integrity checks and rollback."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.skills.loader import load_skill_directory
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


class SkillRegistry:
    """Manage one directory whose children are immutable library versions."""

    def __init__(self, versions_root: Path) -> None:
        self.versions = versions_root
        self.pointer = versions_root / "current.json"

    def _manifest(
        self,
        version: str,
        parent_version: str | None,
        files: dict[str, str],
        skill_ids: list[str],
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        content = {
            "version": version,
            "parent_version": parent_version,
            "skills": skill_ids,
            "files": files,
            "evidence": evidence,
        }
        return {
            "schema_version": 1,
            **content,
            "created_at": datetime.now(UTC).isoformat(),
            "content_sha256": canonical_json_sha256(content),
        }

    def create_version(
        self,
        version: str,
        skills: list[SkillContract],
        *,
        parent_version: str | None,
        evidence: dict[str, Any],
    ) -> Path:
        destination = self.versions / version
        if destination.exists():
            raise FileExistsError(destination)
        if len({skill.skill_id for skill in skills}) != len(skills):
            raise ValueError("Cannot freeze duplicate skill IDs")
        destination.mkdir(parents=True)
        try:
            for skill in sorted(skills, key=lambda item: item.skill_id):
                path = destination / f"{skill.skill_id}.yaml"
                path.write_text(
                    yaml.safe_dump(
                        skill.model_dump(mode="json", exclude_none=True),
                        allow_unicode=True,
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )
            files = {
                path.name: sha256_file(path) for path in sorted(destination.glob("*.yaml"))
            }
            manifest = self._manifest(
                version,
                parent_version,
                files,
                [skill.skill_id for skill in sorted(skills, key=lambda item: item.skill_id)],
                evidence,
            )
            atomic_json(destination / "manifest.json", manifest)
        except BaseException:
            shutil.rmtree(destination)
            raise
        return destination

    def freeze(
        self,
        version: str,
        source: Path,
        *,
        parent_version: str | None,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        destination = self.create_version(
            version,
            load_skill_directory(source),
            parent_version=parent_version,
            evidence=evidence,
        )
        return json.loads((destination / "manifest.json").read_text(encoding="utf-8"))

    def validate(self, version: str) -> dict[str, Any]:
        destination = self.versions / version
        manifest_path = destination / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for filename, expected in manifest["files"].items():
            path = destination / filename
            actual = sha256_file(path) if path.is_file() else None
            if actual != expected:
                raise ValueError(
                    f"Skill library hash mismatch for {version}/{filename}: "
                    f"expected {expected}, got {actual}"
                )
        load_skill_directory(destination)
        return manifest

    def current(self) -> str | None:
        if not self.pointer.is_file():
            return None
        return str(json.loads(self.pointer.read_text(encoding="utf-8"))["version"])

    def activate(self, version: str) -> dict[str, Any]:
        self.validate(version)
        manifest_path = self.versions / version / "manifest.json"
        previous = self.current()
        pointer = {
            "version": version,
            "manifest_sha256": sha256_file(manifest_path),
            "previous_version": previous,
            "activated_at": datetime.now(UTC).isoformat(),
        }
        atomic_json(self.pointer, pointer)
        return pointer

    def rollback(self, target_version: str | None = None) -> dict[str, Any]:
        if not self.pointer.is_file():
            raise RuntimeError("No active skill library")
        current = json.loads(self.pointer.read_text(encoding="utf-8"))
        target = target_version or current.get("previous_version")
        if not target:
            raise RuntimeError("Active skill library has no rollback target")
        return self.activate(str(target))

