from pathlib import Path

import pytest

from legal_skill_guard.skills.loader import load_skill_directory
from legal_skill_guard.skills.registry import SkillRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_immutable_version_activate_and_rollback(tmp_path: Path) -> None:
    skills = load_skill_directory(ROOT / "skills/seed")
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


def test_hash_tampering_is_detected(tmp_path: Path) -> None:
    skills = load_skill_directory(ROOT / "skills/seed")
    registry = SkillRegistry(tmp_path / "versions")
    target = registry.create_version("v1", skills, parent_version=None, evidence={})
    skill_file = next(target.glob("*.yaml"))
    skill_file.write_text(
        skill_file.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        registry.validate("v1")
