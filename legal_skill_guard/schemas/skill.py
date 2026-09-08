"""Schema for auditable, policy-facing legal consultation skill documents.

The learned object is a document shown to the frozen lawyer before it chooses an
action.  It is deliberately not an executable rule: no field refers to a
``candidate_action`` and no operation can rewrite a model output.  Causal source
evidence is stored separately by the evolution pipeline.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SkillStatus = Literal["candidate", "provisional", "active", "rejected", "deprecated"]
SkillObjective = Literal[
    "fact_elicitation",
    "evidence_gap_identification",
    "safe_stop",
]
SkillDocumentItem = Annotated[str, Field(min_length=1, max_length=240)]


class SkillModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Provenance(SkillModel):
    source: Literal["manual_seed", "tf_grpo", "repair", "merge"]
    source_evidence_cluster_id: str | None = None
    source_signal_family: SkillObjective | None = None
    source_case_ids: list[str] = Field(default_factory=list)
    source_trajectory_ids: list[str] = Field(default_factory=list)
    generator_model: str | None = None
    diagnosis_hash: str | None = None


class SkillEvaluation(SkillModel):
    paired_cases: int = 0
    exposed_pairs: int = 0
    exposed_cases: int = 0
    exposed_domains: int = 0
    mean_delta_reward: float | None = None
    median_delta_reward: float | None = None
    harmful_pair_rate: float | None = None
    severe_risk_count: int = 0
    accepted_at: str | None = None


class SkillDocumentFields(SkillModel):
    """The policy-facing portion shared by teacher drafts and stored skills."""

    schema_version: Literal[2] = 2
    skill_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=80)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    domain: str = "general"
    objective: SkillObjective
    description: str = Field(min_length=12, max_length=500)
    applicability_cues: list[SkillDocumentItem] = Field(min_length=1, max_length=5)
    procedure: list[SkillDocumentItem] = Field(min_length=1, max_length=5)
    question_guidance: list[SkillDocumentItem] = Field(min_length=1, max_length=4)
    expected_effects: list[SkillDocumentItem] = Field(min_length=1, max_length=5)
    contraindications: list[SkillDocumentItem] = Field(min_length=1, max_length=5)
    failure_modes: list[SkillDocumentItem] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def require_clean_document_lists(self) -> SkillDocumentFields:
        """Keep the prompt document compact, non-empty, and deterministic."""

        for field_name in (
            "applicability_cues",
            "procedure",
            "question_guidance",
            "expected_effects",
            "contraindications",
            "failure_modes",
        ):
            values = getattr(self, field_name)
            normalized = [item.strip() for item in values]
            if any(not item for item in normalized):
                raise ValueError(f"{field_name} cannot contain blank items")
            if len(normalized) != len(set(normalized)):
                raise ValueError(f"{field_name} cannot contain duplicate items")
            setattr(self, field_name, normalized)
        self.name = self.name.strip()
        self.description = self.description.strip()
        return self


class SkillDocumentDraft(SkillDocumentFields):
    """Teacher-owned fields; causal identity and outcome statistics are excluded."""

    status: Literal["candidate"] = "candidate"


class SkillContract(SkillDocumentFields):
    """One immutable prompt-memory skill learned from causal trajectory contrasts."""

    status: SkillStatus = "candidate"
    provenance: Provenance
    evaluation: SkillEvaluation = Field(default_factory=SkillEvaluation)
