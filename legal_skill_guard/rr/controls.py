"""Six inference arms over one shared acquisition, plus common prediction budget."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field

from .coverage import digest


@dataclass(frozen=True)
class Arm:
    name: str
    compilation: str
    interface: str
    max_model_calls: int = 3
    tools: tuple[str, ...] = ("bounded_IR", "deterministic_primitives", "completion_backend")


ARMS = {
    "M00": Arm("M00", "full", "ordinary_IO_local_binding_repair"),
    "M10": Arm("M10", "answer_separating", "ordinary_IO_local_binding_repair"),
    "M01": Arm("M01", "full", "collision_refined"),
    "M11": Arm("M11", "answer_separating", "collision_refined"),
    "MA": Arm("MA", "generic_CEGAR_fixed_batch", "collision_refined"),
    "MB": Arm("MB", "answer_separating", "all_extracted_metadata_example_synthesis"),
}


@dataclass(frozen=True)
class SharedMaterial:
    source: str
    model_proposals: list[dict]
    original_training_labels: dict
    budgeted_oracle_views: list[dict]
    teacher_summary: dict
    learned_interface_patterns: list[dict]

    def __post_init__(self):
        if len(self.model_proposals) > 2 or len(self.budgeted_oracle_views) > 4:
            raise ValueError("Shared acquisition exceeds per-source budgets")


def project_material(material: SharedMaterial, arm: str) -> dict:
    profile = ARMS[arm]
    # Baselines receive the exact same raw proposals, labels and teacher records.
    # Whether a learned pattern is active is an inference intervention, not a
    # second paid learning run or a different set of labeled examples.
    shared = {"source": material.source, "model_proposals": deepcopy(material.model_proposals),
              "original_training_labels": deepcopy(material.original_training_labels),
              "budgeted_oracle_views": deepcopy(material.budgeted_oracle_views),
              "teacher_summary": deepcopy(material.teacher_summary)}
    return {"profile": asdict(profile), "shared_material": shared,
            "shared_material_hash": digest(shared),
            "active_learned_patterns": deepcopy(material.learned_interface_patterns)
            if profile.interface == "collision_refined" else [],
            "full_metadata_source": "same_model_proposals_only" if arm == "MB" else None,
            "extra_paid_preparation_calls": 0}


@dataclass
class PredictionBudget:
    """One shared 3-call limit, including parsing, schema repairs and fallback."""
    calls: list[str] = field(default_factory=list)
    limit: int = 3

    def reserve(self, purpose: str) -> None:
        if purpose not in {"parse", "repair", "fallback"}:
            raise ValueError("Unknown prediction call purpose")
        if len(self.calls) >= min(self.limit, 3):
            raise RuntimeError("Entire prediction model-call cap exhausted")
        if purpose == "parse" and self.calls.count("parse") >= 2:
            raise RuntimeError("At most two parsing calls")
        # Ordinary parsing cannot spend the reserved third fallback request.
        if purpose != "fallback" and len(self.calls) >= 2:
            raise RuntimeError("Third request is reserved for fixed fallback")
        self.calls.append(purpose)


def dry_run_matrix(protocol: dict) -> dict:
    if protocol["run_enabled"] or protocol["execution_request"]["frozen_test_enabled"]:
        raise ValueError("Current task must keep formal execution disabled")
    return {"executed": False, "model_calls": 0, "formal_execution_authorized": False,
            "shared_training_builds": 1, "profiles": [asdict(a) for a in ARMS.values()],
            "dev_outputs_per_arm": protocol["evaluation"]["dev_outputs_per_arm"],
            "test_outputs_per_arm": protocol["evaluation"]["test_outputs_per_arm"]}
