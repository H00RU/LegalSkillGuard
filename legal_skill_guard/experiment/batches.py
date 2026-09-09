"""Frozen sequential training-block contract and leakage-safe coverage checks."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from legal_skill_guard.environment.dlawbench_adapter import DLawBenchAdapter


class BatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrainingBatch(BatchModel):
    batch_id: str
    case_ids: list[str] = Field(min_length=1)
    persona_assignment: dict[str, str]


class SkillAccumulation(BatchModel):
    mode: Literal["source_grounded_direct_admission"]
    first_source_batch: str
    final_source_batch: str
    effect_assessment: Literal["prequential_library_level_shadow"]
    maintenance_interval_blocks: int = Field(ge=1)
    final_batch_generates_skills: bool


class CoverageRequirements(BatchModel):
    cumulative_training_domains: int = Field(ge=1)
    minimum_domains_per_batch: int = Field(ge=1)
    minimum_source_pages_per_batch: int = Field(ge=1)
    maximum_cases_from_one_source_page_per_batch: int = Field(ge=1)
    cases_must_appear_once: bool
    training_persona: str


class TrainingBatchPlan(BatchModel):
    schema_version: int = 3
    design: str
    status: str
    random_seed: int
    training_cases: int = Field(ge=1)
    training_batches: int = Field(ge=1)
    cases_per_batch: int = Field(ge=1)
    skill_accumulation: SkillAccumulation
    design_notes: list[str]
    batches: list[TrainingBatch]
    coverage_requirements: CoverageRequirements

    @model_validator(mode="after")
    def declared_sizes_are_consistent(self) -> TrainingBatchPlan:
        if len(self.batches) != self.training_batches:
            raise ValueError("training_batches does not match the batch list")
        if self.schema_version != 3:
            raise ValueError("only the 128-case schema-3 accumulation plan is supported")
        if any(len(item.case_ids) != self.cases_per_batch for item in self.batches):
            raise ValueError("a training batch has the wrong number of cases")
        batch_ids = [item.batch_id for item in self.batches]
        if len(batch_ids) != len(set(batch_ids)):
            raise ValueError("training batch IDs must be unique")
        if self.skill_accumulation.first_source_batch != batch_ids[0]:
            raise ValueError("first_source_batch must identify the first training block")
        if self.skill_accumulation.final_source_batch != batch_ids[-1]:
            raise ValueError("final_source_batch must identify the final training block")
        if not self.skill_accumulation.final_batch_generates_skills:
            raise ValueError("all 128 training cases must be allowed to contribute skills")
        for item in self.batches:
            if set(item.persona_assignment) != set(item.case_ids):
                raise ValueError(
                    f"training persona assignment does not match cases: {item.batch_id}"
                )
            if set(item.persona_assignment.values()) != {
                self.coverage_requirements.training_persona
            }:
                raise ValueError(
                    f"training persona assignment is not the controlled persona: {item.batch_id}"
                )
        flattened = [case_id for item in self.batches for case_id in item.case_ids]
        if len(flattened) != self.training_cases or len(flattened) != len(set(flattened)):
            raise ValueError("training cases must appear exactly once across batches")
        if not self.coverage_requirements.cases_must_appear_once:
            raise ValueError("the batch contract must require one acquisition block per case")
        return self

    def validate_against_adapter(self, adapter: DLawBenchAdapter) -> None:
        configured_personas = {
            persona
            for batch in self.batches
            for persona in batch.persona_assignment.values()
        }
        unknown_personas = sorted(configured_personas - set(adapter.persona_keys))
        if unknown_personas:
            raise ValueError(f"persona assignments contain unknown values: {unknown_personas}")
        training_persona = self.coverage_requirements.training_persona
        if training_persona not in set(adapter.persona_keys):
            raise ValueError("controlled training persona is not defined by DLawBench")
        for batch in self.batches:
            if set(batch.persona_assignment.values()) != {training_persona}:
                raise ValueError(f"controlled training persona drifted: {batch.batch_id}")
        training_ids = {case_id for item in self.batches for case_id in item.case_ids}
        declared_training = set(adapter.case_ids("train"))
        if training_ids != declared_training:
            raise ValueError("training batches do not exactly partition the train split")
        training_domains = {adapter.case_domain(case_id) for case_id in training_ids}
        if len(training_domains) != self.coverage_requirements.cumulative_training_domains:
            raise ValueError("cumulative training-domain coverage does not match the contract")
        for batch in self.batches:
            domains = {adapter.case_domain(case_id) for case_id in batch.case_ids}
            if len(domains) < self.coverage_requirements.minimum_domains_per_batch:
                raise ValueError(f"insufficient domain coverage: {batch.batch_id}")


def load_training_batch_plan(path: Path, adapter: DLawBenchAdapter) -> TrainingBatchPlan:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    plan = TrainingBatchPlan.model_validate(payload)
    plan.validate_against_adapter(adapter)
    return plan
