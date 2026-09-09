from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from pydantic import ValidationError

from legal_skill_guard.evolution.diagnosis import (
    BehaviorDifference,
    FailureState,
    SkillDiagnosis,
)
from legal_skill_guard.evolution.teacher import TeacherProposal
from legal_skill_guard.experiment.executor import (
    DIRECT_SKILL_ADMISSION_ROLE,
    DIRECT_SKILL_ADMISSION_STATUS,
    ExecutionError,
    MainExperimentExecutor,
    TrainingSummary,
    _role_assignment_status_check,
    _stage_unique_teacher_candidate,
    skill_contract_definition_sha256,
    skill_library_sha256,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.skills.loader import load_skill
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file
from tests.skill_fixtures import synthetic_skills


def test_role_assignment_status_is_an_explicit_preflight_contract() -> None:
    expected = "static_role_assignment_frozen_gpu_requalification_required"
    assert _role_assignment_status_check({"status": expected}) == {
        "value": expected,
        "passed": True,
    }
    assert _role_assignment_status_check({"status": "legacy_ready"}) == {
        "value": "legacy_ready",
        "passed": False,
    }


def test_current_executor_exposes_only_direct_accumulation_lifecycle() -> None:
    assert MainExperimentExecutor._direct_block_manifest_name("training_batch_01") == (
        "training_batch_01__complete"
    )
    retired_names = {
        "validate_provisional_candidate",
        "validate_preceding_block_candidates",
        "_write_provisionals_ready_checkpoint",
        "_validate_provisionals_ready_checkpoint",
        "_retired_prospective_train",
    }
    assert not retired_names.intersection(dir(MainExperimentExecutor))


def test_training_summary_rejects_legacy_acceptance_schema() -> None:
    with pytest.raises(ValidationError):
        TrainingSummary.model_validate(
            {
                "schema_version": 4,
                "run_id": "legacy",
                "run_manifest_sha256": "a" * 64,
                "trajectory_schema_version": 16,
                "evaluation_schema_version": 13,
                "rounds_completed": 8,
                "round_completion_manifests": {},
                "round_completion_set_sha256": canonical_json_sha256({}),
                "accepted_skill_ids": [],
                "prospective_validation_reports": {},
                "active_skill_ids": [],
                "active_skill_library_version": "bootstrap_empty",
                "active_skill_library_sha256": skill_library_sha256([]),
                "development_learning_curve_sha256": "b" * 64,
                "completed_at": "2026-09-09T00:00:00+00:00",
            }
        )


def _executor(tmp_path: Path, *, run_id: str = "direct_contract") -> MainExperimentExecutor:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = run_id
    executor.store = RunStore(tmp_path / "runs", run_id)
    executor.candidate_root = executor.store.root / "skills/candidates"
    executor.local_model = "model/test"
    executor.local_revision = "revision-1"
    executor.judge_qualification_contract_sha256 = "a" * 64
    executor.experiment = {
        "execution": {
            "evolution_rounds": 1,
            "maximum_new_skills_per_block": 3,
            "teacher_call_budget_per_round": 3,
        },
        "personas": ["P_WD"],
        "trajectory_sampling": {
            "group_size": 1,
            "training_group_seeds": [42],
        },
        "skill_admission": {"maintenance_interval_blocks": 2},
    }
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(
                batch_id="training_batch_01",
                case_ids=["case_test"],
                persona_assignment={"case_test": "P_WD"},
            )
        ]
    )
    executor.registry = SimpleNamespace(current=lambda: None)
    executor.initial_skill_library = lambda: ([], {})
    executor.active_skills = lambda: []
    return executor


def _write_trusted_noop_teacher_proposal(
    executor: MainExperimentExecutor,
    *,
    fingerprint_character: str,
) -> None:
    fingerprint = fingerprint_character * 16
    group_id = f"training_batch_01.semantic_advantage.{fingerprint[:12]}"
    diagnosis = SkillDiagnosis(
        group_id=group_id,
        failure_state=FailureState(turn=1),
        behavior_difference=BehaviorDifference(
            positive_action="来源不足，不能形成可迁移方法",
            negative_action="来源不足，不能形成可迁移方法",
        ),
        causal_hypothesis="当前证据不足，安全地不生成候选技能。",
        proposed_change="NOOP",
        skill_scope="general",
        candidate_skill=None,
    )
    response_value = diagnosis.model_dump(mode="json")
    request_sha256 = fingerprint_character * 64
    response_sha256 = canonical_json_sha256(response_value)
    proposal = TeacherProposal(
        group_id=group_id,
        request_sha256=request_sha256,
        response_sha256=response_sha256,
        teacher_model="gpt-test",
        parse_status="noop",
        diagnosis=diagnosis,
    )
    proposal_path = (
        executor.store.root
        / "teacher/round_01"
        / f"proposal_{fingerprint}.json"
    )
    executor.store.save_model(proposal_path, proposal)
    executor.store.atomic_json(
        executor.teacher_client.cache_root
        / "skill_teacher_batch"
        / f"{request_sha256}.json",
        {
            "schema_version": 1,
            "request_sha256": request_sha256,
            "response_sha256": response_sha256,
            "model": "gpt-test",
            "purpose": "skill_teacher_batch",
            "value": response_value,
            "invocation": {"budget_reservation": {"sequence": int(fingerprint_character, 16)}},
        },
    )


def test_teacher_budget_allows_exhausted_resume_with_three_trusted_proposals(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path)
    executor.teacher_client = SimpleNamespace(
        model="gpt-test",
        cache_root=executor.store.root / "cache/skill_teacher",
    )
    for character in ("1", "2", "3"):
        _write_trusted_noop_teacher_proposal(
            executor,
            fingerprint_character=character,
        )

    contract = executor._teacher_invocation_budget_contract(
        {"available": 0, "reserved": 225, "hard_limit": 225}
    )

    assert contract["passed"] is True
    assert contract["maximum_formal_new_calls"] == 0
    assert contract["remaining_new_calls_by_round"] == {"1": 0}
    assert contract["trusted_persisted_proposals_by_round"]["1"]["trusted_count"] == 3


def test_teacher_budget_requires_only_missing_calls_and_ignores_untrusted_cache(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path)
    executor.teacher_client = SimpleNamespace(
        model="gpt-test",
        cache_root=executor.store.root / "cache/skill_teacher",
    )
    for character in ("1", "2"):
        _write_trusted_noop_teacher_proposal(
            executor,
            fingerprint_character=character,
        )
    # A copied proposal without its exact response cache is not budget credit.
    fingerprint = "3" * 16
    copied = executor.store.load_model(
        executor.store.root / "teacher/round_01" / f"proposal_{'2' * 16}.json",
        TeacherProposal,
    ).model_copy(
        update={
            "group_id": f"training_batch_01.semantic_advantage.{fingerprint[:12]}",
            "request_sha256": "3" * 64,
        }
    )
    executor.store.save_model(
        executor.store.root / "teacher/round_01" / f"proposal_{fingerprint}.json",
        copied,
    )

    exhausted = executor._teacher_invocation_budget_contract(
        {"available": 0, "reserved": 225, "hard_limit": 225}
    )
    sufficient = executor._teacher_invocation_budget_contract(
        {"available": 1, "reserved": 224, "hard_limit": 225}
    )

    assert exhausted["passed"] is False
    assert sufficient["passed"] is True
    assert sufficient["maximum_formal_new_calls"] == 1
    round_contract = sufficient["trusted_persisted_proposals_by_round"]["1"]
    assert round_contract["trusted_count"] == 2
    assert list(round_contract["ignored_files"].values()) == [
        "missing_or_invalid_response_cache:FileNotFoundError"
    ]


def _write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_teacher_skill_id_collisions_are_rejected_without_overwriting_or_raising(
    tmp_path: Path,
) -> None:
    candidate_root = tmp_path / "candidates"
    first = synthetic_skills()[0].model_copy(deep=True)
    first.status = "candidate"
    conflicting = first.model_copy(deep=True)
    conflicting.description = first.description + " 不同的方法内容。"
    round_documents: dict[str, str] = {}
    round_owners: dict[str, str] = {}

    first_path, _, first_disposition, _, first_issues = _stage_unique_teacher_candidate(
        first,
        candidate_root=candidate_root,
        round_candidate_documents=round_documents,
        round_document_owners=round_owners,
    )
    assert first_path is not None
    original_bytes = first_path.read_bytes()
    conflict_path, _, disposition, duplicate_of, issues = _stage_unique_teacher_candidate(
        conflicting,
        candidate_root=candidate_root,
        round_candidate_documents=round_documents,
        round_document_owners=round_owners,
    )

    assert first_disposition == "staged_unique_candidate"
    assert first_issues == []
    assert conflict_path is None
    assert disposition == "rejected_same_round_skill_id_conflict"
    assert duplicate_of == first.skill_id
    assert issues == ["same_round_skill_id_reused_for_different_document"]
    assert first_path.read_bytes() == original_bytes

    # The same collision against a path from an earlier block is also a local
    # proposal rejection, while an exact definition remains resumable.
    earlier = first.model_copy(update={"status": "active"})
    _write_yaml(first_path, earlier.model_dump(mode="json"))
    prior_bytes = first_path.read_bytes()
    cross_path, _, disposition, duplicate_of, issues = _stage_unique_teacher_candidate(
        conflicting,
        candidate_root=candidate_root,
        round_candidate_documents={},
        round_document_owners={},
    )
    assert cross_path is None
    assert disposition == "rejected_existing_skill_id_conflict"
    assert duplicate_of == first.skill_id
    assert issues == ["existing_skill_id_reused_for_different_contract"]
    assert first_path.read_bytes() == prior_bytes

    resumed_path, resumed, disposition, _, issues = _stage_unique_teacher_candidate(
        first,
        candidate_root=candidate_root,
        round_candidate_documents={},
        round_document_owners={},
    )
    assert resumed_path == first_path
    assert resumed is not None and resumed.status == "candidate"
    assert disposition == "staged_unique_candidate"
    assert issues == []


def _write_empty_admission_report(executor: MainExperimentExecutor) -> dict[str, object]:
    empty_hash = skill_library_sha256([])
    value: dict[str, object] = {
        "schema_version": 5,
        "run_id": executor.run_id,
        "round": 1,
        "status": DIRECT_SKILL_ADMISSION_STATUS,
        "admission_role": DIRECT_SKILL_ADMISSION_ROLE,
        "per_candidate_outcome_gate": False,
        "baseline_active_skill_ids": [],
        "baseline_skill_library_sha256": empty_hash,
        "records": [],
        "admitted_skill_files": [],
        "admitted_skill_ids": [],
        "output_active_skill_ids": [],
        "output_skill_library_sha256": empty_hash,
        "output_skill_library_version": "bootstrap_empty",
    }
    executor.store.atomic_json(
        executor._skill_admission_report_path(1),
        value,
    )
    return value


def test_direct_admission_loader_has_no_hidden_candidate_outcome_gate(tmp_path: Path) -> None:
    executor = _executor(tmp_path)
    report = _write_empty_admission_report(executor)
    loaded, paths = executor._load_direct_admission_report(
        round_index=1,
        expected_baseline_ids=[],
        expected_baseline_hash=skill_library_sha256([]),
    )
    assert loaded == report
    assert paths == []

    report["per_candidate_outcome_gate"] = True
    executor.store.atomic_json(
        executor._skill_admission_report_path(1),
        report,
    )
    with pytest.raises(ExecutionError, match="binding drift"):
        executor._load_direct_admission_report(
            round_index=1,
            expected_baseline_ids=[],
            expected_baseline_hash=skill_library_sha256([]),
        )


def test_library_maintenance_report_is_idempotent_after_interrupted_block_commit(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path)
    executor.experiment["evaluation"] = {"primary_endpoint": "fact_efficiency"}
    curve_path = executor._learning_curve_point_path(1)
    executor.store.atomic_json(
        curve_path,
        {
            "curve": {
                "metrics": {
                    "fact_efficiency": {
                        "current_library_mean": 0.0,
                        "empty_library_mean": 0.0,
                    }
                }
            }
        },
    )

    first = executor.write_library_maintenance_report(round_index=1, input_skills=[])
    assert first is not None
    original_bytes = first.read_bytes()

    # Models the crash window after maintenance was committed but before the
    # block-complete manifest.  Resume must validate and reuse the exact bytes.
    resumed = executor.write_library_maintenance_report(round_index=1, input_skills=[])
    assert resumed == first
    assert resumed.read_bytes() == original_bytes


def test_direct_admission_loader_binds_candidate_bytes_and_active_status(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path)
    candidate = synthetic_skills()[0].model_copy(deep=True)
    candidate.status = "active"
    candidate_path = executor.candidate_root / f"{candidate.skill_id}.yaml"
    _write_yaml(candidate_path, candidate.model_dump(mode="json"))
    relative = str(candidate_path.relative_to(tmp_path))
    empty_hash = skill_library_sha256([])
    report = {
        "schema_version": 5,
        "run_id": executor.run_id,
        "round": 1,
        "status": DIRECT_SKILL_ADMISSION_STATUS,
        "admission_role": DIRECT_SKILL_ADMISSION_ROLE,
        "per_candidate_outcome_gate": False,
        "baseline_active_skill_ids": [],
        "baseline_skill_library_sha256": empty_hash,
        "records": [
            {
                "skill_id": candidate.skill_id,
                "candidate_file": relative,
                "candidate_sha256": sha256_file(candidate_path),
                "candidate_contract_sha256": skill_contract_definition_sha256(candidate),
                "valid": True,
            }
        ],
        "admitted_skill_files": [relative],
        "admitted_skill_ids": [candidate.skill_id],
        "output_active_skill_ids": [candidate.skill_id],
        "output_skill_library_sha256": skill_library_sha256([candidate]),
        "output_skill_library_version": "library_test",
    }
    executor.store.atomic_json(
        executor._skill_admission_report_path(1),
        report,
    )

    _, admitted = executor._load_direct_admission_report(
        round_index=1,
        expected_baseline_ids=[],
        expected_baseline_hash=empty_hash,
    )
    assert [load_skill(path).skill_id for path in admitted] == [candidate.skill_id]

    candidate.status = "rejected"
    _write_yaml(candidate_path, candidate.model_dump(mode="json"))
    with pytest.raises(ExecutionError, match="artifact drift|lifecycle drift"):
        executor._load_direct_admission_report(
            round_index=1,
            expected_baseline_ids=[],
            expected_baseline_hash=empty_hash,
        )


def _write_complete_empty_block(
    executor: MainExperimentExecutor,
) -> tuple[dict[str, object], ResearchTrajectory]:
    empty_hash = skill_library_sha256([])
    expected = executor._training_round_expected_matrix(
        1,
        case_limit=None,
        input_skill_library_sha256=empty_hash,
        input_skills=[],
    )[0]
    trajectory = ResearchTrajectory.model_validate(
        {
            **expected,
            "domain": "civil",
            "jurisdiction": "CN",
            "status": "memo_submitted",
            "opening": "测试开场。",
            "max_turns": 6,
            "steps": [],
            "memo": "测试备忘录。",
            "elapsed_seconds": 1.0,
            "created_at": "2026-09-09T00:00:00+00:00",
        }
    )
    executor.store.save_model(
        executor.store.trajectory_path("training_batch_01", trajectory.trajectory_id),
        trajectory,
    )
    executor.store.atomic_json(
        executor.store.evaluation_path(trajectory.trajectory_id),
        {"schema_version": 13, "trajectory_id": trajectory.trajectory_id},
    )
    executor.store.atomic_json(
        executor.store.root / "health/pre_scoring_health_training_batch_01.json",
        {"healthy": True},
    )
    executor.store.write_manifest(
        "teacher_round_01",
        {"schema_version": 1, "run_id": executor.run_id, "round": 1},
    )
    curve_path = executor.store.root / "reports/development_curve_point_01.json"
    executor.store.atomic_json(curve_path, {"schema_version": 1, "identity_baseline": True})
    admission = _write_empty_admission_report(executor)
    learning: dict[str, object] = {
        "schema_version": 3,
        "measured_input_active_skill_ids": [],
        "measured_input_skill_library_sha256": empty_hash,
        "admitted_from_current_block": [],
        "active_skill_ids": [],
        "active_skill_library_sha256": empty_hash,
        "development_curve_artifact": executor._relative_artifact_record(curve_path),
    }
    executor.store.atomic_json(
        executor.store.root / "reports/learning_checkpoint_01.json",
        learning,
    )
    maintenance_path = executor.store.root / "reports/library_maintenance_01.json"
    executor.store.atomic_json(maintenance_path, {"schema_version": 1, "round": 1})
    complete = executor._write_direct_block_complete(
        round_index=1,
        case_limit=None,
        run_manifest_sha256="b" * 64,
        input_version="bootstrap_empty",
        input_skills=[],
        trajectories=[trajectory],
        admission_report=admission,
        learning_report=learning,
        maintenance_path=maintenance_path,
    )
    return complete, trajectory


@pytest.mark.parametrize("artifact", ["trajectory", "evaluation"])
def test_direct_block_checkpoint_rejects_bound_artifact_hash_drift(
    tmp_path: Path,
    artifact: str,
) -> None:
    executor = _executor(tmp_path)
    _, trajectory = _write_complete_empty_block(executor)
    path = (
        executor.store.trajectory_path("training_batch_01", trajectory.trajectory_id)
        if artifact == "trajectory"
        else executor.store.evaluation_path(trajectory.trajectory_id)
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    value["post_checkpoint_edit"] = True
    executor.store.atomic_json(path, value)

    with pytest.raises(ExecutionError, match="artifact is missing or changed"):
        executor._validate_direct_block_complete(
            round_index=1,
            case_limit=None,
            run_manifest_sha256="b" * 64,
            expected_input_ids=[],
            expected_input_hash=skill_library_sha256([]),
            expected_input_version="bootstrap_empty",
        )


def test_training_complete_rejects_wrong_summary_run_id(tmp_path: Path) -> None:
    executor = _executor(tmp_path, run_id="current_run")
    executor.store.write_manifest(
        "training_complete",
        {
            "schema_version": 5,
            "run_id": "copied_run",
            "run_manifest_sha256": "a" * 64,
            "trajectory_schema_version": 16,
            "evaluation_schema_version": 13,
            "rounds_completed": 1,
            "round_completion_manifests": {},
            "round_completion_set_sha256": canonical_json_sha256({}),
            "admitted_skill_ids": [],
            "rejected_skill_ids": [],
            "skill_admission_reports": {},
            "library_maintenance_reports": {},
            "active_skill_ids": [],
            "active_skill_library_version": "bootstrap_empty",
            "active_skill_library_sha256": skill_library_sha256([]),
            "development_learning_curve_sha256": "b" * 64,
            "completed_at": "2026-09-09T00:00:00+00:00",
        },
    )

    with pytest.raises(ExecutionError, match="binding drift"):
        executor._load_validated_training_summary(run_manifest_sha256="a" * 64)
