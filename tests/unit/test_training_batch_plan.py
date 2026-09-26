from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from legal_skill_guard.experiment.batches import TrainingBatchPlan

ROOT = Path(__file__).resolve().parents[2]


def _repository_plan() -> dict[str, object]:
    return yaml.safe_load(
        (ROOT / "configs/data/main_training_batches.yaml").read_text(encoding="utf-8")
    )


def test_repository_training_batch_plan_reserves_B8_for_final_observation() -> None:
    plan = TrainingBatchPlan.model_validate(_repository_plan())

    assert plan.skill_accumulation.final_source_batch == "training_batch_07"
    assert plan.skill_accumulation.final_batch_generates_skills is False
    assert plan.skill_accumulation.effect_assessment == (
        "descriptive_prequential_exact_parent_increment_or_library_identity"
    )


def test_training_batch_plan_rejects_an_unvalidated_B8_cohort() -> None:
    payload = _repository_plan()
    payload["skill_accumulation"] = {
        **payload["skill_accumulation"],
        "final_source_batch": "training_batch_08",
        "final_batch_generates_skills": True,
    }

    with pytest.raises(ValidationError, match="final_source_batch"):
        TrainingBatchPlan.model_validate(payload)
