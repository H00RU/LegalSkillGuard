from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from pydantic import ValidationError

from legal_skill_guard.evolution.group_evidence import TrajectoryGroupEvidencePatch
from legal_skill_guard.evolution.teacher import (
    INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS,
    PLAYBOOK_SKILL_ID,
    PlaybookModeArtifact,
    PlaybookPatchDraft,
    PlaybookReduceArtifact,
    _playbook_mode_output_schema,
    _playbook_patch_output_schema,
    materialize_playbook_proposal,
    playbook_map_input_binding_sha256,
    playbook_map_request_payload,
    playbook_reduce_input_binding_sha256,
    playbook_reduce_request_payload,
)
from legal_skill_guard.experiment.executor import (
    COHORT_PARENT_EFFECT_DIRECTION,
    DIRECT_SKILL_ADMISSION_ROLE,
    DIRECT_SKILL_ADMISSION_STATUS,
    ExecutionError,
    MainExperimentExecutor,
    TrainingSummary,
    _role_assignment_status_check,
    _stage_unique_teacher_candidate,
    _structured_codex_request_sha256,
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


def test_current_executor_excludes_retired_per_candidate_lifecycle() -> None:
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


def test_direct_accumulation_has_no_result_driven_parent_restore_api() -> None:
    assert not hasattr(MainExperimentExecutor, "_restore_rejected_cohort_parent")


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
            "maximum_new_skills_per_block": 14,
            "teacher_call_budget_per_round": 2,
        },
        "personas": ["P_WD"],
        "trajectory_sampling": {
            "group_size": 1,
            "training_group_seeds": [42],
        },
        "learning_curve": {},
        "evaluation": {"primary_endpoint": "unique_disclosed_facts_per_question"},
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
    executor.main_adapter = SimpleNamespace(
        case_ids=lambda _split: ("case_test",),
        case_domain=lambda _case_id: "labor_employment",
    )
    executor.experiment["data"] = {"training_split": "train"}
    executor.registry = SimpleNamespace(current=lambda: None)
    executor.initial_skill_library = lambda: ([], {})
    executor.active_skills = lambda: []
    return executor


def _resume_card(group_id: str, case_id: str) -> dict[str, object]:
    target = {
        "target_id": f"{group_id}.target",
        "label": "待核实客户事实",
        "criticality": "medium",
        "target_kind": "client_fact",
    }
    summary = {
        "trajectory_id": f"{group_id}.trajectory",
        "visible_target_catalog": [target],
        "turn_outline": [
            {
                "visible_unresolved_targets_before_action": [
                    {"target_id": target["target_id"], "status": "unknown", "asked": False}
                ]
            }
        ],
    }
    return {
        "schema_version": 4,
        "group_id": group_id,
        "case_id": case_id,
        "domain": "labor_employment",
        "persona": "P_WD",
        "skill_library_version": skill_library_sha256([]),
        "opening_inquiry_agenda": [target],
        "group_relative_status": "process_tied",
        "trajectory_summaries": [dict(summary) for _ in range(4)],
        "undisclosed_hidden_facts_included": False,
    }


def _playbook_resume_executor(tmp_path: Path) -> MainExperimentExecutor:
    executor = _executor(tmp_path)
    executor.experiment["execution"]["teacher_call_budget_per_round"] = 3
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(
                batch_id="training_batch_01",
                case_ids=["case_a", "case_b"],
                persona_assignment={"case_a": "P_WD", "case_b": "P_WD"},
            ),
            SimpleNamespace(
                batch_id="training_batch_02",
                case_ids=["case_final"],
                persona_assignment={"case_final": "P_WD"},
            ),
        ]
    )
    executor.main_adapter = SimpleNamespace(
        case_ids=lambda _split: ("case_a", "case_b", "case_final"),
        case_domain=lambda _case_id: "labor_employment",
    )
    cache_root = executor.store.root / "cache/skill_teacher"
    ledger_path = tmp_path / "shared/luna_invocation_budget.json"
    executor.teacher_client = SimpleNamespace(
        model="gpt-test",
        reasoning_effort="low",
        cache_root=cache_root,
        invocation_budget_path=ledger_path,
        max_invocations=20,
    )
    executor.teacher = SimpleNamespace(
        mode_prompt="current playbook map prompt",
        prompt="current playbook reduce prompt",
    )
    scoreable = ["group_a", "group_b"]
    executor.store.atomic_json(
        executor.store.root / "health/pre_scoring_health_training_batch_01.json",
        {
            "quality_diagnostics": {
                "training_group_attribution_review": {
                    "scoring_eligible": True,
                    "scoreable_group_ids": scoreable,
                }
            }
        },
    )
    for index, (group_id, case_id) in enumerate(
        (("group_a", "case_a"), ("group_b", "case_b")), start=1
    ):
        card = _resume_card(group_id, case_id)
        patch = TrajectoryGroupEvidencePatch(
            round_index=1,
            partition="training_batch_01",
            group_id=group_id,
            case_id=case_id,
            domain="labor_employment",
            persona="P_WD",
            skill_library_version=skill_library_sha256([]),
            trajectory_ids=[f"{group_id}.trajectory_{item}" for item in range(4)],
            trajectory_sha256={
                f"{group_id}.trajectory_{item}": "a" * 64 for item in range(4)
            },
            evaluation_sha256={
                f"{group_id}.trajectory_{item}": "b" * 64 for item in range(4)
            },
            card=card,
        )
        executor.store.save_model(
            executor.store.root / f"evidence/group_cards/round_01_{index}.json",
            patch,
        )
    executor.store.atomic_json(
        executor._learning_curve_point_path(1),
        {
            "input_active_skill_ids": [],
            "input_skill_library_version": "bootstrap_empty",
            "input_skill_library_sha256": skill_library_sha256([]),
            "parent_skill_library_version": "bootstrap_empty",
            "identity_baseline": True,
            "new_skill_increment_ids": [],
            "curve": {
                "direction": COHORT_PARENT_EFFECT_DIRECTION,
                "identity_baseline": True,
                "metrics": {
                    "unique_disclosed_facts_per_question": {
                        "case_cluster_estimate": {
                            "mean_delta": 0.0,
                            "lower": 0.0,
                            "upper": 0.0,
                        }
                    }
                },
                "cases": [
                    {
                        "case_id": case_id,
                        "paired_delta_mean": {
                            "unique_disclosed_facts_per_question": 0.0
                        },
                    }
                    for case_id in ("case_a", "case_b")
                ],
                "pairs": [],
            },
        },
    )
    return executor


def _persist_teacher_cache(
    executor: MainExperimentExecutor,
    *,
    purpose: str,
    request_sha256: str,
    value: dict[str, object],
    reservations: list[dict[str, object]],
) -> str:
    response_sha256 = canonical_json_sha256(value)
    reservation = {
        "sequence": len(reservations) + 1,
        "reserved_at": f"2026-09-27T00:00:0{len(reservations)}+00:00",
        "purpose": purpose,
        "request_sha256": request_sha256,
        "attempt": 1,
    }
    reservations.append(reservation)
    executor.store.atomic_json(
        executor.teacher_client.cache_root / purpose / f"{request_sha256}.json",
        {
            "schema_version": 1,
            "request_sha256": request_sha256,
            "response_sha256": response_sha256,
            "model": "gpt-test",
            "purpose": purpose,
            "value": value,
            "invocation": {
                "returncode": 0,
                "tool_events_detected": False,
                "budget_reservation": reservation,
            },
        },
    )
    return response_sha256


def _persist_playbook_stages(
    executor: MainExperimentExecutor,
    *,
    stages: int,
    persist_ledger: bool = True,
) -> None:
    map_packages, current_playbook, feedback = executor._playbook_teacher_round_resume_inputs(1)
    reservations: list[dict[str, object]] = []
    artifacts: list[PlaybookModeArtifact] = []
    teacher_root = executor.store.root / "teacher/round_01"
    for index, cards in enumerate(map_packages, start=1):
        if index > stages:
            break
        package_id = f"training_batch_01.playbook_map_{index:02d}"
        value: dict[str, object] = {
            "package_id": package_id,
            "modes": [],
            "no_new_mode_group_ids": [str(card["group_id"]) for card in cards],
        }
        payload = playbook_map_request_payload(
            package_id=package_id,
            evidence_cards=cards,
            current_playbook=current_playbook,
        )
        request_sha256 = _structured_codex_request_sha256(
            client=executor.teacher_client,
            purpose="playbook_mode_extraction",
            system_prompt=executor.teacher.mode_prompt,
            user_payload=payload,
            output_schema=_playbook_mode_output_schema(package_id=package_id),
        )
        response_sha256 = _persist_teacher_cache(
            executor,
            purpose="playbook_mode_extraction",
            request_sha256=request_sha256,
            value=value,
            reservations=reservations,
        )
        artifact = PlaybookModeArtifact(
            package_id=package_id,
            input_binding_sha256=playbook_map_input_binding_sha256(
                package_id=package_id,
                evidence_cards=cards,
                current_playbook=current_playbook,
            ),
            request_sha256=request_sha256,
            response_sha256=response_sha256,
            teacher_model="gpt-test",
            source_group_ids=sorted(str(card["group_id"]) for card in cards),
            modes=[],
            no_new_mode_group_ids=sorted(str(card["group_id"]) for card in cards),
        )
        artifacts.append(artifact)
        executor.store.save_model(
            teacher_root / f"training_batch_01.playbook_map_{index:02d}.json",
            artifact,
        )
    if stages >= 3:
        package_id = "training_batch_01.playbook_reduce"
        patch = PlaybookPatchDraft(
            package_id=package_id,
            synthesis_summary="两份来源包没有提供足以支持修改当前全局手册的新机制。",
            operations=[],
            noop_reason="现有证据只重复已知限制，不支持有来源的局部编辑。",
        )
        payload = playbook_reduce_request_payload(
            package_id=package_id,
            mode_artifacts=artifacts,
            current_playbook=current_playbook,
            library_feedback=feedback,
            maximum_operations=INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS,
        )
        request_sha256 = _structured_codex_request_sha256(
            client=executor.teacher_client,
            purpose="playbook_patch_curation",
            system_prompt=executor.teacher.prompt,
            user_payload=payload,
            output_schema=_playbook_patch_output_schema(
                package_id=package_id,
                maximum_operations=INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS,
            ),
        )
        response_sha256 = _persist_teacher_cache(
            executor,
            purpose="playbook_patch_curation",
            request_sha256=request_sha256,
            value=patch.model_dump(mode="json"),
            reservations=reservations,
        )
        proposal = materialize_playbook_proposal(
            package_id=package_id,
            evidence_cards=[card for cards in map_packages for card in cards],
            mode_artifacts=artifacts,
            current_playbook=current_playbook,
            patch=patch,
            teacher_model="gpt-test",
            request_sha256=request_sha256,
            response_sha256=response_sha256,
        )
        executor.store.save_model(
            teacher_root / "training_batch_01.playbook_reduce.json",
            PlaybookReduceArtifact(
                package_id=package_id,
                input_binding_sha256=playbook_reduce_input_binding_sha256(
                    package_id=package_id,
                    mode_artifacts=artifacts,
                    current_playbook=current_playbook,
                    library_feedback=feedback,
                    maximum_operations=INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS,
                ),
                proposal=proposal,
                patch=patch,
            ),
        )
    if persist_ledger:
        executor.store.atomic_json(
            executor.teacher_client.invocation_budget_path,
            {
                "schema_version": 1,
                "model": "gpt-test",
                "max_invocations": 20,
                "reservations": reservations,
            },
        )


def test_teacher_budget_credits_only_current_playbook_map_reduce_stages(tmp_path: Path) -> None:
    executor = _playbook_resume_executor(tmp_path)
    _persist_playbook_stages(executor, stages=3)

    contract = executor._teacher_invocation_budget_contract(
        {"available": 17, "reserved": 3, "hard_limit": 20}
    )

    assert contract["passed"] is True
    assert contract["maximum_formal_new_calls"] == 0
    assert contract["remaining_new_calls_by_round"] == {"1": 0, "2": 0}
    trusted = contract["trusted_persisted_teacher_calls_by_round"]["1"]
    assert trusted["trusted_count"] == 3
    assert trusted["trusted_stages"] == ["map_01", "map_02", "reduce"]
    assert trusted["ignored_files"] == {}


def test_fresh_eight_block_run_reserves_three_calls_for_b1_to_b7_and_zero_for_b8(
    tmp_path: Path,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(batch_id=f"training_batch_{index:02d}")
            for index in range(1, 9)
        ]
    )
    executor.teacher_client.max_invocations = 40

    contract = executor._teacher_invocation_budget_contract(
        {"available": 40, "reserved": 0, "hard_limit": 40}
    )

    assert contract["passed"] is True
    assert contract["maximum_formal_new_calls"] == 21
    assert contract["remaining_new_calls_by_round"] == {
        **{str(index): 3 for index in range(1, 8)},
        "8": 0,
    }


def test_teacher_budget_accepts_historical_transport_retry_as_real_consumption(
    tmp_path: Path,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    reservations = [
        {
            "sequence": 1,
            "reserved_at": "2026-08-16T03:54:12+00:00",
            "purpose": "legacy_skill_teacher",
            "request_sha256": "a" * 64,
            "attempt": 1,
        },
        {
            "sequence": 2,
            "reserved_at": "2026-08-16T03:57:13+00:00",
            "purpose": "legacy_skill_teacher",
            "request_sha256": "a" * 64,
            "attempt": 2,
        },
    ]
    executor.store.atomic_json(
        executor.teacher_client.invocation_budget_path,
        {
            "schema_version": 1,
            "model": "gpt-test",
            "max_invocations": 20,
            "reservations": reservations,
        },
    )

    # The client status API counts all reservations, including retries.
    contract = executor._teacher_invocation_budget_contract(
        {"available": 18, "reserved": 2, "hard_limit": 20}
    )

    assert contract["passed"] is True
    assert contract["hard_ledger_contract_issue"] is None
    assert contract["budget_status_contract_issue"] is None
    assert contract["reserved"] == 2
    assert contract["available"] == 18


@pytest.mark.parametrize("invalid_attempt", [0, -1, True, "2"])
def test_teacher_budget_rejects_invalid_historical_attempt_values(
    tmp_path: Path,
    invalid_attempt: object,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    executor.store.atomic_json(
        executor.teacher_client.invocation_budget_path,
        {
            "schema_version": 1,
            "model": "gpt-test",
            "max_invocations": 20,
            "reservations": [
                {
                    "sequence": 1,
                    "reserved_at": "2026-08-16T03:54:12+00:00",
                    "purpose": "legacy_skill_teacher",
                    "request_sha256": "a" * 64,
                    "attempt": invalid_attempt,
                }
            ],
        },
    )

    reservations, issue = executor._teacher_budget_ledger_reservations()

    assert reservations == []
    assert issue == "teacher_budget_ledger_reservations_invalid"


def test_historical_retry_compatibility_does_not_credit_current_resume_stage(
    tmp_path: Path,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    _persist_playbook_stages(executor, stages=1)
    ledger_path = executor.teacher_client.invocation_budget_path
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["reservations"][0]["attempt"] = 2
    executor.store.atomic_json(ledger_path, ledger)

    artifact_path = (
        executor.store.root
        / "teacher/round_01/training_batch_01.playbook_map_01.json"
    )
    artifact = executor.store.load_model(artifact_path, PlaybookModeArtifact)
    cache_path = (
        executor.teacher_client.cache_root
        / "playbook_mode_extraction"
        / f"{artifact.request_sha256}.json"
    )
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    cached["invocation"]["budget_reservation"]["attempt"] = 2
    executor.store.atomic_json(cache_path, cached)

    contract = executor._teacher_invocation_budget_contract(
        {"available": 19, "reserved": 1, "hard_limit": 20}
    )

    assert contract["hard_ledger_contract_issue"] is None
    assert contract["budget_status_contract_issue"] is None
    assert contract["passed"] is False
    ignored = contract["trusted_persisted_teacher_calls_by_round"]["1"]["ignored_files"]
    assert list(ignored.values()) == ["response_cache_budget_reservation_mismatch"]


def test_luna_preflight_probe_uses_current_playbook_map_contract(tmp_path: Path) -> None:
    executor = _executor(tmp_path)
    executor.teacher_client = SimpleNamespace(model="gpt-test")

    def extract_playbook_modes(**kwargs: object) -> SimpleNamespace:
        assert kwargs["package_id"] == "preflight.playbook_map"
        assert kwargs["purpose"] == "preflight_playbook_mode_extraction"
        assert kwargs["current_playbook"] is None
        cards = kwargs["evidence_cards"]
        assert isinstance(cards, list) and len(cards) == 1
        card = cards[0]
        assert isinstance(card, dict)
        assert card["undisclosed_hidden_facts_included"] is False
        return SimpleNamespace(
            package_id=kwargs["package_id"],
            input_binding_sha256=playbook_map_input_binding_sha256(
                package_id=str(kwargs["package_id"]),
                evidence_cards=cards,
                current_playbook=None,
            ),
            source_group_ids=[str(card["group_id"])],
            teacher_model="gpt-test",
            request_sha256="a" * 64,
            response_sha256="b" * 64,
        )

    executor.teacher = SimpleNamespace(extract_playbook_modes=extract_playbook_modes)

    report = executor._playbook_teacher_structured_probe()

    assert report["passed"] is True
    assert report["schema"] == "PlaybookModeBatchDraft"
    assert report["purpose"] == "preflight_playbook_mode_extraction"


def test_teacher_budget_credits_one_trusted_map_and_reserves_two_new_calls(
    tmp_path: Path,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    _persist_playbook_stages(executor, stages=1)

    contract = executor._teacher_invocation_budget_contract(
        {"available": 19, "reserved": 1, "hard_limit": 20}
    )

    assert contract["passed"] is True
    assert contract["maximum_formal_new_calls"] == 2
    assert contract["remaining_new_calls_by_round"] == {"1": 2, "2": 0}


def test_copied_playbook_cache_without_exact_hard_ledger_entry_gets_no_credit(
    tmp_path: Path,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    _persist_playbook_stages(executor, stages=1, persist_ledger=False)

    contract = executor._teacher_invocation_budget_contract(
        {"available": 20, "reserved": 0, "hard_limit": 20}
    )

    assert contract["passed"] is False
    assert contract["maximum_formal_new_calls"] == 3
    ignored = contract["trusted_persisted_teacher_calls_by_round"]["1"]["ignored_files"]
    assert list(ignored.values()) == ["response_cache_budget_reservation_mismatch"]
    assert contract["untrusted_persisted_stages_by_round"]["1"] == ignored


def test_teacher_manifest_alone_does_not_waive_unfinished_block_calls(
    tmp_path: Path,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    executor.store.atomic_json(
        executor.store.root / "manifests/teacher_round_01.json",
        {"status": "copied_or_interrupted_teacher_manifest"},
    )

    contract = executor._teacher_invocation_budget_contract(
        {"available": 20, "reserved": 0, "hard_limit": 20}
    )

    assert contract["unfinished_teacher_rounds"] == [1, 2]
    assert contract["maximum_formal_new_calls"] == 3
    assert contract["remaining_new_calls_by_round"] == {"1": 3, "2": 0}


def test_teacher_budget_denies_resume_credit_when_exact_inputs_cannot_be_rebuilt(
    tmp_path: Path,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    _persist_playbook_stages(executor, stages=1)
    (executor.store.root / "health/pre_scoring_health_training_batch_01.json").unlink()

    contract = executor._teacher_invocation_budget_contract(
        {"available": 19, "reserved": 1, "hard_limit": 20}
    )

    assert contract["maximum_formal_new_calls"] == 3
    round_contract = contract["trusted_persisted_teacher_calls_by_round"]["1"]
    assert round_contract["trusted_count"] == 0
    assert round_contract["resume_input_binding_status"] == (
        "unavailable_conservative_no_credit"
    )
    assert round_contract["uncredited_stage_reasons"]["map_01"] == (
        "playbook_resume_input_contract_invalid:FileNotFoundError"
    )
    assert contract["passed"] is False


def test_tampered_system_materialized_reduce_proposal_gets_no_resume_credit(
    tmp_path: Path,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    _persist_playbook_stages(executor, stages=3)
    reduce_path = (
        executor.store.root
        / "teacher/round_01/training_batch_01.playbook_reduce.json"
    )
    artifact = executor.store.load_model(reduce_path, PlaybookReduceArtifact)
    tampered_diagnosis = artifact.proposal.diagnosis.model_copy(
        update={"causal_hypothesis": "这段系统物化的诊断已被事后篡改。"}
    )
    tampered_proposal = artifact.proposal.model_copy(
        update={"diagnosis": tampered_diagnosis}
    )
    executor.store.save_model(
        reduce_path,
        artifact.model_copy(update={"proposal": tampered_proposal}),
        overwrite=True,
    )

    contract = executor._teacher_invocation_budget_contract(
        {"available": 17, "reserved": 3, "hard_limit": 20}
    )

    assert contract["passed"] is False
    assert contract["maximum_formal_new_calls"] == 1
    ignored = contract["trusted_persisted_teacher_calls_by_round"]["1"]["ignored_files"]
    assert list(ignored.values()) == [
        "playbook_reduce_proposal_materialization_mismatch"
    ]


def test_parent_playbook_drift_invalidates_all_persisted_teacher_stages(
    tmp_path: Path,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    packages, _, feedback = executor._playbook_teacher_round_resume_inputs(1)
    _persist_playbook_stages(executor, stages=3)
    parent = synthetic_skills()[0].model_copy(
        update={
            "skill_id": PLAYBOOK_SKILL_ID,
            "version": "1.0.0",
            "domain": "general",
            "objective": "fact_elicitation",
            "status": "active",
        }
    )
    executor._playbook_teacher_round_resume_inputs = lambda _round: (  # type: ignore[method-assign]
        packages,
        parent,
        feedback,
    )

    contract = executor._teacher_invocation_budget_contract(
        {"available": 17, "reserved": 3, "hard_limit": 20}
    )

    assert contract["passed"] is False
    assert contract["maximum_formal_new_calls"] == 3
    ignored = contract["trusted_persisted_teacher_calls_by_round"]["1"]["ignored_files"]
    assert list(ignored.values()) == [
        "playbook_map_artifact_binding_mismatch",
        "playbook_map_artifact_binding_mismatch",
        "playbook_reduce_requires_two_trusted_maps",
    ]


def test_parent_feedback_drift_invalidates_only_persisted_reduce_stage(
    tmp_path: Path,
) -> None:
    executor = _playbook_resume_executor(tmp_path)
    packages, parent, feedback = executor._playbook_teacher_round_resume_inputs(1)
    _persist_playbook_stages(executor, stages=3)
    executor._playbook_teacher_round_resume_inputs = lambda _round: (  # type: ignore[method-assign]
        packages,
        parent,
        {**feedback, "drifted_after_artifact": True},
    )

    contract = executor._teacher_invocation_budget_contract(
        {"available": 17, "reserved": 3, "hard_limit": 20}
    )

    assert contract["passed"] is False
    assert contract["maximum_formal_new_calls"] == 1
    round_contract = contract["trusted_persisted_teacher_calls_by_round"]["1"]
    assert round_contract["trusted_stages"] == ["map_01", "map_02"]
    assert list(round_contract["ignored_files"].values()) == [
        "playbook_reduce_artifact_binding_mismatch"
    ]


def test_retired_proposal_file_never_counts_as_resumable_teacher_call(tmp_path: Path) -> None:
    executor = _playbook_resume_executor(tmp_path)
    legacy_path = executor.store.root / "teacher/round_01/proposal_deadbeefdeadbeef.json"
    executor.store.atomic_json(legacy_path, {"schema_version": 3})

    contract = executor._teacher_invocation_budget_contract(
        {"available": 3, "reserved": 17, "hard_limit": 20}
    )

    round_contract = contract["trusted_persisted_teacher_calls_by_round"]["1"]
    assert round_contract["trusted_count"] == 0
    assert round_contract["legacy_proposal_files_ignored"] == [
        str(legacy_path.relative_to(executor.root))
    ]
    assert contract["maximum_formal_new_calls"] == 3


def _write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_candidate_deduplication_is_callable_from_executor_instance(tmp_path: Path) -> None:
    executor = _executor(tmp_path)
    candidate = synthetic_skills()[0].model_copy(update={"status": "candidate"})
    candidate_path = (
        executor.candidate_root / "round_01" / f"{candidate.skill_id}.yaml"
    )
    _write_yaml(candidate_path, candidate.model_dump(mode="json"))

    unique, duplicates = executor._deduplicate_candidate_paths([candidate_path])

    assert unique == [candidate_path]
    assert duplicates == []


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
        "schema_version": 6,
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
                    "direction": "current_library_minus_parent_library",
                "identity_baseline": True,
                "metrics": {
                    "fact_efficiency": {
                        "current_library_mean": 0.0,
                        "empty_library_mean": 0.0,
                        "case_cluster_estimate": {
                            "mean_delta": 0.0,
                            "lower": 0.0,
                            "upper": 0.0,
                        },
                    }
                },
                "cases": [
                    {
                        "case_id": "case_test",
                        "paired_delta_mean": {"fact_efficiency": 0.0},
                    }
                ],
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
    candidate_path = (
        executor.candidate_root / "round_01" / f"{candidate.skill_id}.yaml"
    )
    _write_yaml(candidate_path, candidate.model_dump(mode="json"))
    relative = str(candidate_path.relative_to(tmp_path))
    empty_hash = skill_library_sha256([])
    report = {
        "schema_version": 6,
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


def test_resume_after_activation_uses_pre_admission_library_for_block_rollout(
    tmp_path: Path,
) -> None:
    """A normal continue disposition must not be mistaken for cohort rejection."""

    executor = _executor(tmp_path, run_id="resume_after_activation")
    admitted = synthetic_skills()[0]
    empty_hash = skill_library_sha256([])
    admitted_hash = skill_library_sha256([admitted])
    executor.store.atomic_json(
        executor._skill_admission_report_path(1),
        {
            "baseline_active_skill_ids": [],
            "baseline_skill_library_sha256": empty_hash,
            "output_active_skill_ids": [admitted.skill_id],
            "output_skill_library_sha256": admitted_hash,
        },
    )
    executor.store.atomic_json(
        executor._library_effect_disposition_path(1),
        {"decision": "continue_training"},
    )
    # This fixture models a one-block run, so the final-arm ordering guard also
    # applies.  Only existence is consulted before the deliberately interrupted
    # rollout below; the artifact is never consumed in this classification test.
    executor.store.atomic_json(executor._final_training_holdout_arms_path(), {})
    executor.active_skills = lambda: [admitted]
    executor._verified_run_manifest_sha256 = lambda: "b" * 64

    requested_versions: list[str] = []

    def load_version(version: str) -> list[object]:
        requested_versions.append(version)
        return []

    observed_rollout_inputs: list[list[object]] = []

    def stop_after_classification(
        _round_index: int,
        *,
        case_limit: int | None,
        input_skills: list[object],
    ) -> list[ResearchTrajectory]:
        assert case_limit is None
        observed_rollout_inputs.append(input_skills)
        raise RuntimeError("stop_after_resume_classification")

    executor._skills_for_library_version = load_version
    executor.generate_training_round = stop_after_classification

    with pytest.raises(RuntimeError, match="stop_after_resume_classification"):
        executor.train(case_limit=None)

    assert requested_versions == ["bootstrap_empty"]
    assert observed_rollout_inputs == [[]]


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
        {
            "schema_version": 3,
            "status": "skipped_final_block_zero_candidate_budget",
            "round": 1,
            "evidence_unit": "none_final_observation_block",
            "all_scoreable_cases_represented": True,
            "represented_case_ids": [],
            "group_evidence_cards": [],
            "group_relative_status_counts": {},
            "teacher_update_unit": "none_final_block",
            "current_block_enters_cumulative_teacher_evidence": False,
            "round_trajectory_contrast_patches": 0,
            "teacher_packages": [],
            "teacher_call_budget": 2,
            "teacher_calls": 0,
            "resumed_teacher_packages": 0,
            "teacher_budget_status_before_round": None,
            "candidate_outcome_feedback_used": False,
            "input_library_prequential_feedback": None,
            "candidate_budget": 0,
            "teacher_proposal_records": [],
            "candidate_files": [],
            "candidate_count": 0,
            "final_block_generates_skills": False,
        },
    )
    curve_path = executor.store.root / "reports/development_curve_point_01.json"
    curve_point = {
        "schema_version": 3,
        "run_id": executor.run_id,
        "run_manifest_sha256": "b" * 64,
        "round": 1,
        "batch_id": "training_batch_01",
        "input_active_skill_ids": [],
        "input_skill_library_version": "bootstrap_empty",
        "input_skill_library_sha256": empty_hash,
        "parent_active_skill_ids": [],
        "parent_skill_library_version": "bootstrap_empty",
        "parent_skill_library_sha256": empty_hash,
        "new_skill_increment_ids": [],
        "identity_baseline": True,
        "curve": {
            "direction": "current_library_minus_parent_library",
            "identity_baseline": True,
            "no_pending_cohort": True,
            "pair_count": 1,
            "case_cluster_count": 1,
            "bootstrap": {
                "unit": "case_id",
                "samples": 100,
                "confidence_level": 0.95,
                "seed": 17,
            },
            "metrics": {
                "unique_disclosed_facts_per_question": {
                    "case_cluster_estimate": {
                        "pairs": 1,
                        "mean_delta": 0.0,
                        "median_delta": 0.0,
                        "lower": 0.0,
                        "upper": 0.0,
                        "confidence_level": 0.95,
                        "bootstrap_samples": 100,
                        "seed": 17,
                    }
                }
            },
        },
    }
    executor.store.atomic_json(curve_path, curve_point)
    executor._validate_learning_curve_point_artifact = lambda **_: curve_point
    executor.write_library_effect_disposition(
        round_index=1,
        run_manifest_sha256="b" * 64,
        input_version="bootstrap_empty",
        input_skills=[],
        curve_point=curve_point,
    )
    admission = _write_empty_admission_report(executor)
    learning: dict[str, object] = {
        "schema_version": 5,
        "measured_input_active_skill_ids": [],
        "measured_input_skill_library_sha256": empty_hash,
        "admitted_from_current_block": [],
        "active_skill_ids": [],
        "active_skill_library_sha256": empty_hash,
        "teacher_evidence_created": False,
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


@pytest.mark.parametrize("disposition_state", ["missing", "input_binding_drift"])
def test_completed_block_resume_requires_exact_library_effect_disposition(
    tmp_path: Path,
    disposition_state: str,
) -> None:
    executor = _executor(tmp_path)
    _write_complete_empty_block(executor)
    path = executor._library_effect_disposition_path(1)
    if disposition_state == "missing":
        path.unlink()
        expected = "artifact is missing"
    else:
        value = json.loads(path.read_text(encoding="utf-8"))
        value["input_skill_library_version"] = "library_other"
        executor.store.atomic_json(path, value)
        expected = "differs from resumed state"

    with pytest.raises(ExecutionError, match=expected):
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
            "schema_version": 6,
            "run_id": "copied_run",
            "run_manifest_sha256": "a" * 64,
            "trajectory_schema_version": 27,
            "evaluation_schema_version": 14,
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
            "final_training_holdout_arms_frozen_artifact": {
                "path": "arms",
                "sha256": "c" * 64,
            },
            "final_training_holdout_artifact": {
                "path": "report",
                "sha256": "d" * 64,
            },
            "final_training_holdout_disposition_artifact": {
                "path": "disposition",
                "sha256": "e" * 64,
            },
            "final_training_holdout_intervention_isolation_artifact": {
                "path": "isolation",
                "sha256": "f" * 64,
            },
            "completed_at": "2026-09-09T00:00:00+00:00",
        },
    )

    with pytest.raises(ExecutionError, match="binding drift"):
        executor._load_validated_training_summary(run_manifest_sha256="a" * 64)
