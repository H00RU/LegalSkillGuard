"""Auditable Skill Contract schema with a finite operation language."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SkillLevel = Literal["strategic", "functional", "atomic"]
SkillStatus = Literal["candidate", "active", "rejected", "deprecated"]
ConditionOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains", "truthy"]
OperationType = Literal[
    "allow",
    "block",
    "replace_type",
    "replace_target",
    "replace_type_and_target",
    "add_constraint",
    "request_state",
    "force_abstain",
]


class SkillModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Condition(SkillModel):
    field: str | None = None
    op: ConditionOp | None = None
    value: Any = None
    all: list[Condition] = Field(default_factory=list)
    any: list[Condition] = Field(default_factory=list)

    @model_validator(mode="after")
    def exactly_one_form(self) -> Condition:
        forms = int(self.field is not None) + int(bool(self.all)) + int(bool(self.any))
        if forms != 1:
            raise ValueError("Condition requires exactly one of field, all, or any")
        if self.field is not None and self.op is None:
            raise ValueError("Leaf condition requires op")
        return self


class SkillOperation(SkillModel):
    type: OperationType
    new_action_type: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    target_selector: str | None = None
    constraint: str | None = None
    reason: str | None = None


class Guardrails(SkillModel):
    max_activations_per_session: int = Field(default=1, ge=1)
    disable_if: list[Condition] = Field(default_factory=list)


class Provenance(SkillModel):
    source: Literal["manual_seed", "tf_grpo", "repair", "merge"]
    source_case_ids: list[str] = Field(default_factory=list)
    source_trajectory_ids: list[str] = Field(default_factory=list)
    generator_model: str | None = None
    diagnosis_hash: str | None = None


class SkillEvaluation(SkillModel):
    paired_cases: int = 0
    triggered_pairs: int = 0
    mean_delta_reward: float | None = None
    median_delta_reward: float | None = None
    harmful_pair_rate: float | None = None
    severe_risk_count: int = 0
    accepted_at: str | None = None


class SkillContract(SkillModel):
    schema_version: int = 1
    skill_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    level: SkillLevel
    domain: str = "general"
    status: SkillStatus = "candidate"
    description: str
    preconditions: list[Condition]
    reads: list[str]
    operation: SkillOperation
    expected_effects: list[str]
    validators: list[str]
    failure_modes: list[str]
    guardrails: Guardrails
    provenance: Provenance
    evaluation: SkillEvaluation = Field(default_factory=SkillEvaluation)


Condition.model_rebuild()

