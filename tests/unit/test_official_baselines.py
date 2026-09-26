from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from pydantic import ValidationError

import legal_skill_guard.experiment.official_baselines as official_baselines
from legal_skill_guard.experiment.executor import ExecutionError
from legal_skill_guard.experiment.official_baselines import (
    BENCHMARK_EVIDENCE_ROLE,
    OFFICIAL_ARM_IDS,
    OURS_TRAINING_BINDING_MANIFEST,
    InsightOperation,
    OfficialBaselineController,
    _character_bigrams,
    _cosine,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.skills.memory import (
    EXPERIENCE_MEMORY_HEADER,
    extract_rendered_experience_memory,
    parse_rendered_experience_memory,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256


def test_character_bigram_retrieval_prefers_related_opening() -> None:
    query = _character_bigrams("公司违法解除劳动合同且拖欠工资")
    related = _character_bigrams("劳动合同解除后未支付工资")
    unrelated = _character_bigrams("房屋买卖合同未办理过户登记")

    assert _cosine(query, related) > _cosine(query, unrelated)


def test_expel_memory_round_trip_exposes_insights_and_examples() -> None:
    memory = (
        EXPERIENCE_MEMORY_HEADER
        + "\n"
        + json.dumps(
            {
                "insights": [
                    {
                        "insight_id": "expel.insight.ask_event_before_attribute",
                        "domain": "general",
                        "insight": "先确认事件是否发生，再询问事件属性。",
                    }
                ],
                "retrieved_training_successes": [
                    {
                        "memory_id": "expel.positive.0123456789abcdef",
                        "domain": "labor_employment",
                        "opening": "公司解除劳动关系。",
                        "dialogue": [],
                        "memo": "需继续核实解除经过。",
                    }
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    assert parse_rendered_experience_memory(memory) == [
        "expel.insight.ask_event_before_attribute",
        "expel.positive.0123456789abcdef",
    ]
    assert extract_rendered_experience_memory("共享策略提示\n" + memory) == memory


def test_expel_memory_rejects_unidentified_examples() -> None:
    memory = (
        EXPERIENCE_MEMORY_HEADER
        + "\n"
        + json.dumps(
            {"insights": [], "retrieved_training_successes": [{"opening": "缺少审计ID"}]},
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    with pytest.raises(ValueError, match="identifiers"):
        parse_rendered_experience_memory(memory)


def test_insight_operation_enforces_add_edit_vote_shapes() -> None:
    InsightOperation(
        operation="ADD",
        pair_index=1,
        existing_insight_id=None,
        new_insight_id="expel.insight.distinct_targets",
        domain="general",
        insight="客户表示不知道后，转向尚未覆盖的独立事实维度。",
        rationale="正轨迹取得更多新事实",
    )

    with pytest.raises(ValidationError, match="ADD requires"):
        InsightOperation(
            operation="ADD",
            pair_index=1,
            existing_insight_id=None,
            new_insight_id=None,
            domain="general",
            insight="缺少ID。",
            rationale="结构不完整",
        )

    vote = InsightOperation(
        operation="UPVOTE",
        pair_index=1,
        existing_insight_id="expel.insight.distinct_targets",
        new_insight_id=None,
        domain="general",
        insight="模型回显的旧正文不会被当作编辑应用。",
        rationale="同案对照再次支持已有经验",
    )
    assert vote.domain is None
    assert vote.insight is None


def test_insight_downvote_also_canonicalizes_nonoperative_echo_fields() -> None:
    vote = InsightOperation.model_validate(
        {
            "operation": "DOWNVOTE",
            "pair_index": 2,
            "existing_insight_id": "expel.insight.distinct_targets",
            "new_insight_id": None,
            "domain": "labor_employment",
            "insight": "回显内容",
            "rationale": "对照显示这条经验在该边界下会误导",
        }
    )

    assert vote.domain is None
    assert vote.insight is None


def test_official_protocol_covers_full_runtime_python_closure() -> None:
    root = Path(__file__).resolve().parents[2]
    controller = object.__new__(OfficialBaselineController)
    controller.root = root
    controller.config_path = root / "configs/experiments/official_baselines.yaml"
    controller.config = yaml.safe_load(controller.config_path.read_text(encoding="utf-8"))

    paths = set(controller._protocol_paths())

    assert set((root / "legal_skill_guard").rglob("*.py")) <= paths
    assert root / "scripts/run_official_baselines.py" in paths
    assert root / "pyproject.toml" in paths
    assert root / "uv.lock" in paths


def test_official_main_table_config_and_code_have_the_same_four_arms() -> None:
    root = Path(__file__).resolve().parents[2]
    controller = OfficialBaselineController(root, "static_four_arm_contract")
    config = yaml.safe_load(
        (root / "configs/experiments/official_baselines.yaml").read_text(encoding="utf-8")
    )

    controller._validate_contract_consistency()
    assert tuple(item["arm_id"] for item in config["arms"]) == OFFICIAL_ARM_IDS
    assert OFFICIAL_ARM_IDS == (
        "control_no_library",
        "luna_direct",
        "expel_adapted",
        "legal_skill_evolve",
    )


def test_reusable_luna_cache_requires_exact_request_and_response_binding(
    tmp_path: Path,
) -> None:
    value = {"documents": [{"skill_id": "luna_direct.general.consultation"}]}
    response_sha256 = canonical_json_sha256(value)
    path = tmp_path / "cache.json"
    payload = {
        "schema_version": 1,
        "purpose": "luna_direct_partition_01",
        "model": "gpt-5.6-luna",
        "request_sha256": "a" * 64,
        "response_sha256": response_sha256,
        "value": value,
        "invocation": {"attempt": 1},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert OfficialBaselineController._validated_reusable_codex_cache(
        path,
        purpose="luna_direct_partition_01",
        model="gpt-5.6-luna",
        request_sha256="a" * 64,
        response_sha256=response_sha256,
    ) == payload

    with pytest.raises(ExecutionError, match="cache contract mismatch"):
        OfficialBaselineController._validated_reusable_codex_cache(
            path,
            purpose="luna_direct_partition_01",
            model="gpt-5.6-luna",
            request_sha256="b" * 64,
            response_sha256=response_sha256,
        )


def _minimal_main_table_controller(tmp_path: Path) -> OfficialBaselineController:
    controller = object.__new__(OfficialBaselineController)
    controller.root = tmp_path
    controller.run_id = "paper_table"
    controller.store = RunStore(tmp_path / "runs", controller.run_id)
    controller.config = {
        "official_data": {
            "path": "official.jsonl",
            "expected_sha256": "declared",
            "expected_cases": 30,
            "personas": ["P_WD", "P_WS", "P_CS", "P_CD"],
            "dialogue_seed": 42,
        },
        "shared_runtime": {"rollout_workers": 1},
    }
    return controller


@pytest.mark.parametrize("arm_id", OFFICIAL_ARM_IDS)
def test_every_official_arm_requires_ours_binding_before_any_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    arm_id: str,
) -> None:
    controller = _minimal_main_table_controller(tmp_path)
    monkeypatch.setattr(
        controller,
        "_official_prerequisites",
        lambda: ({"content_sha256": "protocol"}, {}, {}),
    )
    access_attempted = False

    def unexpected_access(_: str) -> None:
        nonlocal access_attempted
        access_attempted = True

    monkeypatch.setattr(controller, "_record_official_access", unexpected_access)

    with pytest.raises(ExecutionError, match="require bind-ours-training"):
        controller.run_official_arm(arm_id)
    assert access_attempted is False


def test_bind_ours_training_is_forbidden_after_any_official_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _minimal_main_table_controller(tmp_path)
    monkeypatch.setattr(
        controller,
        "_official_prerequisites",
        lambda: ({"content_sha256": "protocol"}, {}, {}),
    )
    validated = False

    def unexpected_validation(_: str) -> tuple[object, list[object], dict[str, object]]:
        nonlocal validated
        validated = True
        return object(), [], {}

    monkeypatch.setattr(controller, "_validated_ours_training_source", unexpected_validation)
    prior = controller.store.root / "reports" / "official_control_no_library_aggregate.json"
    prior.parent.mkdir(parents=True, exist_ok=True)
    prior.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ExecutionError, match="before any official main-table access"):
        controller.bind_ours_training_source("training_run")
    assert validated is False


def test_validated_ours_source_uses_external_blind_shared_freeze_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _minimal_main_table_controller(tmp_path)
    training_root = tmp_path / "runs" / "training_run"
    run_manifest = training_root / "manifests" / "run.json"
    training_complete = training_root / "manifests" / "training_complete.json"
    library_manifest = training_root / "skills" / "versions" / "L7" / "manifest.json"
    for path in (run_manifest, training_complete, library_manifest):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    skill = SimpleNamespace(skill_id="skill.one")
    summary = SimpleNamespace(
        schema_version=6,
        case_limit=None,
        active_skill_library_version="L7",
        active_skill_library_sha256="library-sha",
        active_skill_ids=["skill.one"],
        final_training_holdout_arms_frozen_artifact={"path": "arms", "sha256": "a"},
        final_training_holdout_artifact={"path": "report", "sha256": "b"},
        final_training_holdout_disposition_artifact={
            "path": "disposition",
            "sha256": "c",
        },
        final_training_holdout_intervention_isolation_artifact={
            "path": "isolation",
            "sha256": "d",
        },
    )
    construction_flags: list[bool] = []

    class FakeExecutor:
        def __init__(
            self,
            root: Path,
            run_id: str,
            *,
            allow_external_data_access: bool,
        ) -> None:
            assert root == tmp_path
            assert run_id == "training_run"
            construction_flags.append(allow_external_data_access)
            self.store = SimpleNamespace(root=training_root)
            self.registry = SimpleNamespace(
                current=lambda: "L7",
                versions=training_root / "skills" / "versions",
            )

        def validated_external_ready_training_freeze(
            self,
        ) -> tuple[object, list[object], dict[str, object]]:
            return summary, [skill], {"passed": True, "mode": "locked"}

    monkeypatch.setattr(official_baselines, "MainExperimentExecutor", FakeExecutor)
    monkeypatch.setattr(official_baselines, "skill_library_sha256", lambda _: "library-sha")

    _, skills, binding = controller._validated_ours_training_source("training_run")

    assert construction_flags == [False]
    assert skills == [skill]
    assert binding["training_run_id"] == "training_run"
    assert binding["evidence_role"] == BENCHMARK_EVIDENCE_ROLE
    assert binding["active_skill_library_version"] == "L7"
    assert binding["active_skill_library_sha256"] == "library-sha"
    assert set(binding["final_training_holdout_artifacts"]) == {
        "arms_frozen",
        "report",
        "disposition",
        "isolation",
    }


@pytest.mark.parametrize(
    ("summary_updates", "has_skill", "current_version", "expected_error"),
    [
        ({"schema_version": 5}, True, "L7", "schema-6"),
        ({"case_limit": 1}, True, "L7", "complete 128-case"),
        ({}, False, None, "non-empty frozen skill library"),
        (
            {"active_skill_library_version": "other"},
            True,
            "L7",
            "version/hash drift",
        ),
        (
            {"active_skill_library_sha256": "other"},
            True,
            "L7",
            "version/hash drift",
        ),
    ],
)
def test_ours_binding_rejects_nonfinal_training_freezes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    summary_updates: dict[str, object],
    has_skill: bool,
    current_version: str | None,
    expected_error: str,
) -> None:
    controller = _minimal_main_table_controller(tmp_path)
    training_root = tmp_path / "runs" / "training_run"
    for path in (
        training_root / "manifests" / "run.json",
        training_root / "manifests" / "training_complete.json",
        training_root / "skills" / "versions" / "L7" / "manifest.json",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    values: dict[str, object] = {
        "schema_version": 6,
        "case_limit": None,
        "active_skill_library_version": "L7",
        "active_skill_library_sha256": "library-sha",
        "active_skill_ids": ["skill.one"],
        "final_training_holdout_arms_frozen_artifact": {},
        "final_training_holdout_artifact": {},
        "final_training_holdout_disposition_artifact": {},
        "final_training_holdout_intervention_isolation_artifact": {},
    }
    values.update(summary_updates)
    summary = SimpleNamespace(**values)
    skills = [SimpleNamespace(skill_id="skill.one")] if has_skill else []

    class FakeExecutor:
        def __init__(self, *_: object, **kwargs: object) -> None:
            assert kwargs["allow_external_data_access"] is False
            self.store = SimpleNamespace(root=training_root)
            self.registry = SimpleNamespace(
                current=lambda: current_version,
                versions=training_root / "skills" / "versions",
            )

        def validated_external_ready_training_freeze(
            self,
        ) -> tuple[object, list[object], dict[str, object]]:
            return summary, skills, {"passed": True}

    monkeypatch.setattr(official_baselines, "MainExperimentExecutor", FakeExecutor)
    monkeypatch.setattr(official_baselines, "skill_library_sha256", lambda _: "library-sha")

    with pytest.raises(ExecutionError, match=expected_error):
        controller._validated_ours_training_source("training_run")


def test_bind_ours_training_is_immutable_and_revalidated_for_all_arms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _minimal_main_table_controller(tmp_path)
    protocol = {"content_sha256": "protocol"}
    monkeypatch.setattr(
        controller,
        "_official_prerequisites",
        lambda: (protocol, {}, {}),
    )
    source = object()
    skill = SimpleNamespace(skill_id="skill.one")

    def validated(training_run_id: str) -> tuple[object, list[object], dict[str, object]]:
        return source, [skill], {
            "schema_version": 1,
            "training_run_id": training_run_id,
            "active_skill_library_sha256": "library-sha",
        }

    monkeypatch.setattr(controller, "_validated_ours_training_source", validated)

    first = controller.bind_ours_training_source("training_run")
    second = controller.bind_ours_training_source("training_run")
    assert first == second
    assert first["status"] == "ours_training_source_bound_before_all_official_main_table_arms"
    assert first["evidence_role"] == BENCHMARK_EVIDENCE_ROLE
    assert (
        controller.store.root
        / "manifests"
        / f"{OURS_TRAINING_BINDING_MANIFEST}.json"
    ).is_file()

    loaded_source, skills, source_binding, artifact = controller._bound_ours_training_source(
        protocol
    )
    assert loaded_source is source
    assert skills == [skill]
    assert source_binding["training_run_id"] == "training_run"
    assert artifact["path"].endswith(
        f"manifests/{OURS_TRAINING_BINDING_MANIFEST}.json"
    )

    with pytest.raises(ExecutionError, match="differs from the requested source"):
        controller.bind_ours_training_source("different_training_run")


def test_completed_official_arms_must_share_route_and_ours_binding(
    tmp_path: Path,
) -> None:
    controller = _minimal_main_table_controller(tmp_path)
    route = {"path": "route.json", "sha256": "route-sha"}
    binding = {"path": "binding.json", "sha256": "binding-sha"}
    report_path = (
        controller.store.root / "reports" / "official_control_no_library_aggregate.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "evidence_role": BENCHMARK_EVIDENCE_ROLE,
                "official_fixed_domain_routes_artifact": route,
                "ours_training_source_binding_artifact": binding,
            }
        ),
        encoding="utf-8",
    )

    controller._assert_completed_arm_shared_bindings(
        route_artifact=route,
        ours_binding_artifact=binding,
    )

    report_path.write_text(
        json.dumps(
            {
                "evidence_role": BENCHMARK_EVIDENCE_ROLE,
                "official_fixed_domain_routes_artifact": {
                    "path": "route.json",
                    "sha256": "changed",
                },
                "ours_training_source_binding_artifact": binding,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ExecutionError, match="do not share one fixed route"):
        controller._assert_completed_arm_shared_bindings(
            route_artifact=route,
            ours_binding_artifact=binding,
        )
