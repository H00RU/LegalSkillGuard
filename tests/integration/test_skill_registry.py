from pathlib import Path

import pytest

from legal_skill_guard.skills.registry import SkillRegistry
from tests.skill_fixtures import synthetic_skills

ROOT = Path(__file__).resolve().parents[2]


def test_immutable_version_activate_and_rollback(tmp_path: Path) -> None:
    skills = synthetic_skills()
    registry = SkillRegistry(tmp_path / "versions")
    registry.create_version("v0.1.0", skills, parent_version=None, evidence={"kind": "seed"})
    registry.activate("v0.1.0")
    assert registry.current() == "v0.1.0"
    registry.create_version(
        "v0.2.0", skills, parent_version="v0.1.0", evidence={"kind": "paired_audit"}
    )
    registry.activate("v0.2.0")
    assert registry.current() == "v0.2.0"
    registry.rollback("v0.1.0")
    assert registry.current() == "v0.1.0"
    with pytest.raises(FileExistsError):
        registry.create_version("v0.1.0", skills, parent_version=None, evidence={})


def test_activate_initial_empty_preserves_rejected_version_for_forensics(
    tmp_path: Path,
) -> None:
    registry = SkillRegistry(tmp_path / "versions")
    version_path = registry.create_version(
        "accumulated_v1",
        [synthetic_skills()[0]],
        parent_version="bootstrap_empty",
        evidence={"kind": "source_grounded_increment"},
    )
    registry.activate("accumulated_v1")

    pointer = registry.activate_initial_empty("bootstrap_empty")

    assert registry.current() is None
    assert pointer["version"] is None
    assert pointer["initial_library_id"] == "bootstrap_empty"
    assert pointer["previous_version"] == "accumulated_v1"
    assert version_path.is_dir()
    assert registry.validate("accumulated_v1")["parent_version"] == "bootstrap_empty"


def test_hash_tampering_is_detected(tmp_path: Path) -> None:
    skills = synthetic_skills()
    registry = SkillRegistry(tmp_path / "versions")
    target = registry.create_version("v1", skills, parent_version=None, evidence={})
    skill_file = next(target.glob("*.yaml"))
    skill_file.write_text(
        skill_file.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        registry.validate("v1")


def test_create_version_validates_before_atomic_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills = synthetic_skills()
    registry = SkillRegistry(tmp_path / "versions")
    destination = registry.versions / "v1"
    original_validate = registry._validate_directory
    validated_staging_directories: list[Path] = []

    def record_validation(
        staging: Path,
        version: str,
        *,
        require_current_static_schema: bool = False,
    ) -> dict[str, object]:
        assert staging.parent == registry.versions
        assert staging.name.startswith(".skill-version-")
        assert not destination.exists()
        validated_staging_directories.append(staging)
        return original_validate(
            staging,
            version,
            require_current_static_schema=require_current_static_schema,
        )

    monkeypatch.setattr(registry, "_validate_directory", record_validation)
    published = registry.create_version("v1", skills, parent_version=None, evidence={})

    assert published == destination
    assert published.is_dir()
    assert validated_staging_directories
    assert not validated_staging_directories[0].exists()
    assert list(registry.versions.glob(".skill-version-*")) == []
    assert original_validate(published, "v1")["version"] == "v1"


def test_create_version_failure_leaves_no_partial_version_or_staging_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = SkillRegistry(tmp_path / "versions")

    def fail_validation(
        _staging: Path,
        _version: str,
        *,
        require_current_static_schema: bool = False,
    ) -> dict[str, object]:
        del require_current_static_schema
        raise RuntimeError("injected validation failure")

    monkeypatch.setattr(registry, "_validate_directory", fail_validation)
    with pytest.raises(RuntimeError, match="injected validation failure"):
        registry.create_version(
            "v1", synthetic_skills(), parent_version=None, evidence={}
        )

    assert not (registry.versions / "v1").exists()
    assert list(registry.versions.glob(".skill-version-*")) == []


def test_create_version_conflict_preserves_existing_version(tmp_path: Path) -> None:
    registry = SkillRegistry(tmp_path / "versions")
    destination = registry.create_version(
        "v1", synthetic_skills(), parent_version=None, evidence={"source": "first"}
    )
    original_files = {
        path.name: path.read_bytes() for path in sorted(destination.iterdir())
    }

    with pytest.raises(FileExistsError):
        registry.create_version(
            "v1", synthetic_skills(), parent_version=None, evidence={"source": "second"}
        )

    assert {
        path.name: path.read_bytes() for path in sorted(destination.iterdir())
    } == original_files
    assert list(registry.versions.glob(".skill-version-*")) == []


def test_historical_integrity_is_distinct_from_current_static_activation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skills = synthetic_skills()
    registry = SkillRegistry(tmp_path / "versions")
    registry.create_version("legacy", [skills[0]], parent_version=None, evidence={})
    assert registry.validate("legacy")["version"] == "legacy"

    # Integrity validates the frozen historical bytes.  Activation additionally
    # applies today's static policy, which may become stricter after publication.
    monkeypatch.setattr(
        "legal_skill_guard.skills.loader.validate_skill_static",
        lambda _skill: ["new_current_policy_rule"],
    )
    with pytest.raises(ValueError, match="Static skill validation failed"):
        registry.activate("legacy")
