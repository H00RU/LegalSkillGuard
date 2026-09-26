"""Leakage-separated construction and official evaluation of the paper main table.

The controller has two deliberately different modes:

* construction never instantiates the official DLawBench adapter;
* official execution is enabled only after the shared protocol, Luna-Direct
  library, and independent ExpeL experience bank have immutable manifests;
* the LegalSkillEvolve arm additionally requires an explicitly named, fully
  validated training run and imports only its hash-bound frozen skill library.

The public CN30 benchmark has prior method-level aggregate exposure, so every
new result is a benchmark-aware locked reevaluation rather than a pristine
confirmatory test.  All four arms use one method-independent frozen domain route.
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from legal_skill_guard.environment.dlawbench_adapter import DLawBenchAdapter
from legal_skill_guard.evaluation.semantic import TrajectoryEvaluation
from legal_skill_guard.evaluation.statistics import (
    clustered_mean_deltas,
    paired_bootstrap_interval,
    paired_sign_flip_p_value,
)
from legal_skill_guard.experiment.executor import (
    JUDGE_DIAGNOSTIC_METRICS,
    OFFICIAL_METRICS,
    OPERATIONAL_METRICS,
    PAIRED_BEHAVIOR_METRICS,
    SAFETY_METRICS,
    ExecutionError,
    MainExperimentExecutor,
    parallel_map_ordered,
    skill_library_sha256,
    trajectory_behavior_summary,
    trajectory_behavior_values,
)
from legal_skill_guard.experiment.storage import RunStore, trajectory_identity
from legal_skill_guard.inference.codex_cli_client import CodexCLIClient, strict_output_schema
from legal_skill_guard.inference.openai_client import GenerationConfig, ReplayCachedChatClient
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.schemas.skill import Provenance, SkillContract, SkillDocumentDraft
from legal_skill_guard.skills.loader import ALLOWED_SKILL_DOMAINS, validate_skill_static
from legal_skill_guard.skills.memory import (
    EXPERIENCE_MEMORY_HEADER,
    skill_memory_capacity_issues,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file

BASELINE_CONFIG = "configs/experiments/official_baselines.yaml"
PROTOCOL_MANIFEST = "official_baseline_protocol"
LUNA_MANIFEST = "luna_direct_library"
EXPEL_MANIFEST = "expel_experience_bank"
OURS_TRAINING_BINDING_MANIFEST = "official_main_table_ours_training_source"
ACCESS_LOG = "official_access_log.json"
BENCHMARK_EVIDENCE_ROLE = (
    "benchmark_aware_locked_public_benchmark_reevaluation_not_pristine_confirmatory"
)
OFFICIAL_ARM_IDS = (
    "control_no_library",
    "luna_direct",
    "expel_adapted",
    "legal_skill_evolve",
)


class BaselineModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DirectLibraryBatch(BaselineModel):
    documents: list[SkillDocumentDraft] = Field(min_length=1, max_length=5)


class InsightOperation(BaselineModel):
    operation: Literal["ADD", "EDIT", "UPVOTE", "DOWNVOTE"]
    pair_index: int = Field(ge=1, le=4)
    existing_insight_id: str | None
    new_insight_id: str | None
    domain: str | None
    insight: str | None
    rationale: str = Field(min_length=4, max_length=300)

    @model_validator(mode="before")
    @classmethod
    def normalize_vote_echo_fields(cls, value: Any) -> Any:
        """Discard non-operative text fields echoed on vote-only operations.

        ExpeL votes reference an immutable insight identifier; they never edit
        its domain or text.  Some structured decoders nevertheless echo those
        nullable fields from the referenced bank entry.  Preserve the raw model
        response in the invocation cache, but canonicalize the executable
        operation so this harmless echo cannot invalidate an otherwise valid
        evidence-backed vote.
        """

        if isinstance(value, dict) and value.get("operation") in {
            "UPVOTE",
            "DOWNVOTE",
        }:
            return {**value, "domain": None, "insight": None}
        return value

    @model_validator(mode="after")
    def validate_operation_shape(self) -> InsightOperation:
        if self.operation == "ADD":
            if not self.new_insight_id or not self.domain or not self.insight:
                raise ValueError("ADD requires new_insight_id, domain and insight")
            if self.existing_insight_id is not None:
                raise ValueError("ADD cannot reference an existing insight")
        else:
            if not self.existing_insight_id:
                raise ValueError(f"{self.operation} requires existing_insight_id")
            if self.new_insight_id is not None:
                raise ValueError(f"{self.operation} cannot create an identifier")
            if self.operation == "EDIT" and (not self.domain or not self.insight):
                raise ValueError("EDIT requires replacement domain and insight")
            if self.operation in {"UPVOTE", "DOWNVOTE"} and any(
                value is not None for value in (self.domain, self.insight)
            ):
                raise ValueError(f"{self.operation} canonicalization failed")
        return self


class InsightUpdate(BaselineModel):
    operations: list[InsightOperation] = Field(max_length=8)


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected YAML object: {path}")
    return value


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _relative(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def _artifact_record(root: Path, path: Path) -> dict[str, str]:
    return {"path": _relative(root, path), "sha256": sha256_file(path)}


def _dialogue(trajectory: ResearchTrajectory) -> list[dict[str, Any]]:
    return [
        {
            "turn": step.turn,
            "lawyer": step.rendered_question,
            "client": step.client_response,
            "response_kind": step.client_response_kind,
        }
        for step in trajectory.steps
        if step.rendered_question is not None
    ]


def _character_bigrams(text: str) -> Counter[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    if len(normalized) < 2:
        return Counter({normalized: 1}) if normalized else Counter()
    return Counter(normalized[index : index + 2] for index in range(len(normalized) - 1))


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    numerator = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _insight_text_issues(value: str) -> list[str]:
    issues: list[str] = []
    if len(value) > 360:
        issues.append("insight_character_budget_exceeded")
    if re.search(r"\blsg_cn_\d+\b|\btraj_[0-9a-f]+\b|\b[FO]\d+\b", value, re.I):
        issues.append("source_identifier_in_insight")
    if any(
        marker in value for marker in ("隐藏事实", "标准答案", "裁判得分", "保证胜诉", "必然胜诉")
    ):
        issues.append("hidden_outcome_or_guaranteed_result_language")
    return issues


class OfficialBaselineController:
    """Build, freeze, run and summarize the independent paper comparators."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self.store = RunStore(root / "runs", run_id)
        self.config_path = root / BASELINE_CONFIG
        self.config = _load_yaml(self.config_path)
        self.main_config = _load_yaml(
            root / self.config["shared_runtime"]["main_experiment_config"]
        )
        self.roles = _load_yaml(root / self.config["shared_runtime"]["model_roles"])

    def _protocol_paths(self) -> list[Path]:
        shared = self.config["shared_runtime"]
        configured = [
            self.config_path,
            self.root / "pyproject.toml",
            self.root / "uv.lock",
            self.root / shared["main_experiment_config"],
            self.root / shared["model_roles"],
            self.root / shared["policy_prompt"],
            self.root / shared["opening_agenda_prompt"],
            self.root / shared["client_selector_prompt"],
            self.root / shared["client_disclosure_prompt"],
            self.root / shared["memo_prompt"],
            self.root / shared["semantic_judge_prompt"],
            self.root / shared["domain_router_prompt"],
            self.root / self.config["luna_direct"]["prompt"],
            self.root / self.config["expel_adapted"]["insight_prompt"],
            self.root / "configs/compliance/china_research_boundary.yaml",
        ]
        # A protocol freeze must cover the full executable package, not a manually
        # curated handful of apparent entry points.  Stateful policy validation,
        # client routing and state transitions are transitive runtime dependencies;
        # omitting any one of them lets behavior change without manifest drift.
        # Bind all package Python sources plus the sole official-baseline entrypoint
        # and dependency lock.  Tests and paper-writing files remain outside the
        # execution closure so ordinary reporting edits do not invalidate a run.
        implementation = sorted((self.root / "legal_skill_guard").rglob("*.py")) + [
            self.root / "scripts/run_official_baselines.py"
        ]
        paths = configured + implementation
        if len(paths) != len(set(paths)):
            raise ValueError("baseline protocol path list contains duplicates")
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"baseline protocol files missing: {missing}")
        return paths

    def _expected_protocol_payload(self) -> dict[str, Any]:
        self._validate_contract_consistency()
        official = self.config["official_data"]
        return {
            "schema_version": 3,
            "run_id": self.run_id,
            "status": "benchmark_aware_locked_main_table_protocol",
            "evidence_role": BENCHMARK_EVIDENCE_ROLE,
            "historical_method_level_cn30_aggregates_observed": True,
            "freeze_command_does_not_parse_official_payload": True,
            "implementation_contract": "all_package_python_official_entrypoint_and_lockfile",
            "official_payload_expected_sha256": official["expected_sha256"],
            "official_case_count": int(official["expected_cases"]),
            "persona_order": list(official["personas"]),
            "dialogue_seed": int(official["dialogue_seed"]),
            "sessions_per_arm": int(official["sessions_per_arm"]),
            "independent_unit": official["independent_unit"],
            "arm_order": [str(item["arm_id"]) for item in self.config["arms"]],
            "contract_files": {
                _relative(self.root, path): sha256_file(path) for path in self._protocol_paths()
            },
            "model_roles_sha256": canonical_json_sha256(self.roles["roles"]),
            "domain_taxonomy_sha256": canonical_json_sha256(
                self.config["domain_router"]["domains"]
            ),
            "metric_contract_sha256": canonical_json_sha256(self.config["reporting"]),
        }

    def _validate_contract_consistency(self) -> None:
        """Bind repeated baseline declarations to the actual shared runtime."""

        shared = self.config["shared_runtime"]
        official = self.config["official_data"]
        lawyer = self.roles["roles"]["lawyer_policy"]
        configured_arm_ids = tuple(str(item["arm_id"]) for item in self.config["arms"])
        if configured_arm_ids != OFFICIAL_ARM_IDS:
            raise ValueError(
                "official main-table config/code arm order differs: "
                f"expected={OFFICIAL_ARM_IDS}; actual={configured_arm_ids}"
            )
        if float(shared["paired_policy_temperature"]) != float(
            lawyer["paired_evaluation_temperature"]
        ):
            raise ValueError("baseline paired policy temperature differs from lawyer role")
        if int(shared["emergency_turn_ceiling"]) != int(self.main_config["emergency_turn_ceiling"]):
            raise ValueError("baseline emergency ceiling differs from shared runtime")
        for field in ("rollout_workers", "judge_workers"):
            if int(shared[field]) != int(self.main_config["execution"][field]):
                raise ValueError(f"baseline {field} differs from shared runtime")
        if list(official["personas"]) != list(self.main_config["personas"]):
            raise ValueError("baseline official persona order differs from main contract")
        if [int(official["dialogue_seed"])] != [
            int(item)
            for item in self.main_config["trajectory_sampling"]["external_evaluation_seeds"]
        ]:
            raise ValueError("baseline official dialogue seed differs from main contract")
        if str(official["path"]) != str(self.main_config["data"]["external_evaluation"]):
            raise ValueError("baseline official payload path differs from main contract")
        if set(self.config["domain_router"]["domains"]) != set(ALLOWED_SKILL_DOMAINS):
            raise ValueError("baseline fixed taxonomy differs from the skill domain interface")
        router = self.roles["roles"][self.config["domain_router"]["model_role"]]
        for field in ("model_id", "revision", "local_snapshot", "base_url"):
            if router.get(field) != lawyer.get(field):
                raise ValueError(f"official fixed router does not share lawyer {field}")
        for baseline_role_name in (
            self.config["luna_direct"]["generator_role"],
            self.config["expel_adapted"]["insight_teacher_role"],
        ):
            role = self.roles["roles"][baseline_role_name]
            reference = self.roles["roles"]["skill_teacher"]
            for field in ("model_id", "runtime", "executable", "reasoning_effort"):
                if role.get(field) != reference.get(field):
                    raise ValueError(f"baseline teacher {baseline_role_name} differs on {field}")

    def freeze_protocol(self) -> dict[str, Any]:
        manifest_path = self.store.root / "manifests" / f"{PROTOCOL_MANIFEST}.json"
        expected = self._expected_protocol_payload()
        if manifest_path.is_file():
            current = self.store.read_manifest(PROTOCOL_MANIFEST)
            comparable = {
                key: value
                for key, value in current.items()
                if key not in {"content_sha256", "frozen_at"}
            }
            if comparable != expected:
                raise ExecutionError("frozen official baseline protocol differs from current files")
            return current
        payload = {**expected, "frozen_at": _now()}
        self.store.write_manifest(PROTOCOL_MANIFEST, payload)
        return self.store.read_manifest(PROTOCOL_MANIFEST)

    def verified_protocol(self) -> dict[str, Any]:
        current = self.store.read_manifest(PROTOCOL_MANIFEST)
        expected = self._expected_protocol_payload()
        comparable = {
            key: value
            for key, value in current.items()
            if key not in {"content_sha256", "frozen_at"}
        }
        if comparable != expected:
            raise ExecutionError("official baseline protocol hash drift")
        return current

    def _teacher_client(self, role_name: str, cache_name: str) -> CodexCLIClient:
        role = self.roles["roles"][role_name]
        execution = self.main_config["execution"]
        return CodexCLIClient(
            model=str(role["model_id"]),
            cache_root=self.store.root / "cache" / cache_name,
            reasoning_effort=str(role["reasoning_effort"]),
            timeout_seconds=int(execution["codex_timeout_seconds"]),
            retries=int(execution["codex_retries"]),
            executable=str(role["executable"]),
            invocation_budget_path=(
                self.root / "runs/main_experiment_shared/luna_invocation_budget.json"
            ),
            max_invocations=int(execution["teacher_total_invocation_budget"]),
        )

    @staticmethod
    def _validated_reusable_codex_cache(
        path: Path,
        *,
        purpose: str,
        model: str,
        request_sha256: str,
        response_sha256: str,
    ) -> dict[str, Any]:
        """Load one exact Luna response cache without permitting regeneration."""

        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError(f"reusable Luna-Direct cache is unreadable: {path}") from exc
        value = cached.get("value") if isinstance(cached, dict) else None
        valid = (
            isinstance(cached, dict)
            and cached.get("schema_version") == 1
            and cached.get("purpose") == purpose
            and cached.get("model") == model
            and cached.get("request_sha256") == request_sha256
            and cached.get("response_sha256") == response_sha256
            and isinstance(value, dict)
            and isinstance(cached.get("invocation"), dict)
            and canonical_json_sha256(value) == response_sha256
        )
        if not valid:
            raise ExecutionError(f"reusable Luna-Direct cache contract mismatch: {path}")
        return cached

    def build_luna_direct(
        self,
        *,
        reuse_from_run_id: str | None = None,
    ) -> dict[str, Any]:
        protocol = self.verified_protocol()
        manifest_path = self.store.root / "manifests" / f"{LUNA_MANIFEST}.json"
        if manifest_path.is_file():
            manifest = self._verify_luna_manifest()
            source = manifest.get("reuse_source")
            actual_source = source.get("source_run_id") if isinstance(source, dict) else None
            if reuse_from_run_id is not None and actual_source != reuse_from_run_id:
                raise ExecutionError(
                    "existing Luna-Direct library was not rebound from the requested source"
                )
            return manifest
        config = self.config["luna_direct"]
        prompt_path = self.root / config["prompt"]
        system_prompt = prompt_path.read_text(encoding="utf-8")
        policy_contract = (
            self.root / self.config["shared_runtime"]["policy_prompt"]
        ).read_text(encoding="utf-8")
        interface = {
            "allowed_domains": sorted(ALLOWED_SKILL_DOMAINS),
            "objectives": ["fact_elicitation", "evidence_gap_identification", "safe_stop"],
            "maximum_document_characters": int(config["maximum_document_characters"]),
            "maximum_session_memory_characters": int(config["maximum_session_memory_characters"]),
        }
        teacher = self._teacher_client(str(config["generator_role"]), "luna_direct")
        source_manifest: dict[str, Any] | None = None
        source_manifest_path: Path | None = None
        source_responses: dict[int, dict[str, Any]] = {}
        if reuse_from_run_id is not None:
            source_store = RunStore(self.root / "runs", reuse_from_run_id)
            source_manifest_path = (
                source_store.root / "manifests" / f"{LUNA_MANIFEST}.json"
            )
            try:
                source_manifest = source_store.read_manifest(LUNA_MANIFEST)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise ExecutionError(
                    "requested Luna-Direct reuse source has no valid immutable manifest"
                ) from exc
            if (
                source_manifest.get("run_id") != reuse_from_run_id
                or source_manifest.get("model") != teacher.model
                or source_manifest.get("selection") != config["selection"]
                or int(source_manifest.get("document_count", -1))
                != sum(len(item) for item in config["generation_partitions"])
            ):
                raise ExecutionError("requested Luna-Direct reuse source is incompatible")
            raw_responses = source_manifest.get("responses")
            if not isinstance(raw_responses, list):
                raise ExecutionError("Luna-Direct reuse source has no response provenance")
            for item in raw_responses:
                if not isinstance(item, dict) or not isinstance(item.get("partition"), int):
                    raise ExecutionError("Luna-Direct reuse response provenance is invalid")
                source_responses[int(item["partition"])] = item
            if len(source_responses) != len(config["generation_partitions"]):
                raise ExecutionError("Luna-Direct reuse source partition count differs")
        all_skills: list[SkillContract] = []
        response_records: list[dict[str, Any]] = []
        documents_dir = self.store.root / "baselines" / "luna_direct" / "skills"
        for index, domains in enumerate(config["generation_partitions"], start=1):
            user_prompt = (
                "指定法域：\n"
                + json.dumps(domains, ensure_ascii=False)
                + "\n\n固定领域定义：\n"
                + json.dumps(
                    {domain: self.config["domain_router"]["domains"][domain] for domain in domains},
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n\n技能接口：\n"
                + json.dumps(interface, ensure_ascii=False, sort_keys=True)
                + "\n\n冻结基础咨询能力合同：\n"
                + policy_contract
            )
            purpose = f"luna_direct_partition_{index:02d}"
            if source_manifest is not None:
                request_sha256 = canonical_json_sha256(
                    {
                        "adapter_schema_version": 1,
                        "purpose": purpose,
                        "model": teacher.model,
                        "reasoning_effort": teacher.reasoning_effort,
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                        "output_schema": strict_output_schema(
                            DirectLibraryBatch.model_json_schema()
                        ),
                    }
                )
                source_record = source_responses[index]
                if (
                    source_record.get("domains") != list(domains)
                    or source_record.get("request_sha256") != request_sha256
                    or source_record.get("model") != teacher.model
                    or not isinstance(source_record.get("response_sha256"), str)
                ):
                    raise ExecutionError(
                        "Luna-Direct reuse request is not byte-compatible with current prompts, "
                        f"interface and model: partition={index}"
                    )
                source_cache_path = (
                    self.root
                    / "runs"
                    / reuse_from_run_id
                    / "cache"
                    / "luna_direct"
                    / purpose
                    / f"{request_sha256}.json"
                )
                cached = self._validated_reusable_codex_cache(
                    source_cache_path,
                    purpose=purpose,
                    model=teacher.model,
                    request_sha256=request_sha256,
                    response_sha256=str(source_record["response_sha256"]),
                )
                target_cache_path = (
                    teacher.cache_root / purpose / f"{request_sha256}.json"
                )
                if target_cache_path.is_file():
                    existing = self._validated_reusable_codex_cache(
                        target_cache_path,
                        purpose=purpose,
                        model=teacher.model,
                        request_sha256=request_sha256,
                        response_sha256=str(source_record["response_sha256"]),
                    )
                    if existing != cached:
                        raise ExecutionError(
                            f"target Luna-Direct cache differs from reuse source: {purpose}"
                        )
                else:
                    teacher._atomic_json(target_cache_path, cached)
            response = teacher.generate_json(
                purpose=purpose,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=strict_output_schema(DirectLibraryBatch.model_json_schema()),
            )
            if source_manifest is not None and not response.cache_hit:
                raise ExecutionError(
                    "Luna-Direct reuse unexpectedly attempted model regeneration"
                )
            batch = DirectLibraryBatch.model_validate(response.value)
            if [item.domain for item in batch.documents] != list(domains):
                raise ExecutionError(
                    f"Luna-Direct partition {index} did not preserve declared domain order"
                )
            for draft in batch.documents:
                expected_id = f"luna_direct.{draft.domain}.consultation"
                if draft.skill_id != expected_id or draft.version != "1.0.0":
                    raise ExecutionError(f"invalid frozen Luna-Direct identity: {draft.skill_id}")
                skill = SkillContract(
                    **draft.model_dump(mode="json", exclude={"status"}),
                    status="active",
                    provenance=Provenance(
                        source="luna_direct",
                        generator_model=response.model,
                    ),
                )
                issues = validate_skill_static(skill)
                if issues:
                    raise ExecutionError(
                        f"Luna-Direct static contract failed for {skill.skill_id}: {issues}"
                    )
                all_skills.append(skill)
                path = documents_dir / f"{skill.skill_id}.yaml"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    yaml.safe_dump(
                        skill.model_dump(mode="json", exclude_none=True),
                        allow_unicode=True,
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )
            response_records.append(
                {
                    "partition": index,
                    "domains": list(domains),
                    "request_sha256": response.request_sha256,
                    "response_sha256": response.response_sha256,
                    "model": response.model,
                    "cache_hit": response.cache_hit,
                    "invocation": response.invocation,
                }
            )
        if len(all_skills) > int(config["maximum_documents"]):
            raise ExecutionError("Luna-Direct library exceeds frozen document count")
        capacity_issues = skill_memory_capacity_issues(all_skills)
        if capacity_issues:
            raise ExecutionError(f"Luna-Direct library capacity failed: {capacity_issues}")
        library_sha256 = canonical_json_sha256(
            [
                skill.model_dump(mode="json")
                for skill in sorted(all_skills, key=lambda item: item.skill_id)
            ]
        )
        if (
            source_manifest is not None
            and source_manifest.get("library_sha256") != library_sha256
        ):
            raise ExecutionError(
                "rebound Luna-Direct documents differ from the frozen source library"
            )
        documents = sorted(documents_dir.glob("*.yaml"))
        payload = {
            "schema_version": 2,
            "run_id": self.run_id,
            "protocol_manifest_sha256": protocol["content_sha256"],
            "status": "frozen_before_official_outcomes",
            "construction_mode": (
                "exact_static_response_cache_reuse_rebound_to_current_protocol"
                if source_manifest is not None
                else "fresh_luna_generation"
            ),
            "model": teacher.model,
            "selection": config["selection"],
            "skill_ids": sorted(skill.skill_id for skill in all_skills),
            "document_count": len(all_skills),
            "library_sha256": library_sha256,
            "documents": [_artifact_record(self.root, path) for path in documents],
            "responses": response_records,
            "reuse_source": (
                {
                    "source_run_id": reuse_from_run_id,
                    "source_manifest_artifact": _artifact_record(
                        self.root, source_manifest_path
                    ),
                    "source_protocol_manifest_sha256": source_manifest.get(
                        "protocol_manifest_sha256"
                    ),
                    "source_library_sha256": source_manifest.get("library_sha256"),
                    "source_result_was_previously_observed": True,
                    "selection_or_content_tuning_during_rebind": False,
                }
                if source_manifest is not None and source_manifest_path is not None
                else None
            ),
            "frozen_at": _now(),
        }
        self.store.write_manifest(LUNA_MANIFEST, payload)
        return self._verify_luna_manifest()

    def _verify_luna_manifest(self) -> dict[str, Any]:
        protocol = self.verified_protocol()
        manifest = self.store.read_manifest(LUNA_MANIFEST)
        if manifest.get("protocol_manifest_sha256") != protocol["content_sha256"]:
            raise ExecutionError("Luna-Direct library is bound to another protocol")
        skills = self.load_luna_skills()
        expected_hash = canonical_json_sha256(
            [
                skill.model_dump(mode="json")
                for skill in sorted(skills, key=lambda item: item.skill_id)
            ]
        )
        if manifest.get("library_sha256") != expected_hash:
            raise ExecutionError("Luna-Direct library hash drift")
        reuse_source = manifest.get("reuse_source")
        if reuse_source is not None:
            if not isinstance(reuse_source, dict):
                raise ExecutionError("Luna-Direct reuse binding is invalid")
            source_artifact = reuse_source.get("source_manifest_artifact")
            if not isinstance(source_artifact, dict):
                raise ExecutionError("Luna-Direct reuse source artifact is missing")
            source_path = self.root / str(source_artifact.get("path", ""))
            if (
                not source_path.is_file()
                or sha256_file(source_path) != source_artifact.get("sha256")
                or reuse_source.get("source_library_sha256") != expected_hash
                or reuse_source.get("selection_or_content_tuning_during_rebind") is not False
            ):
                raise ExecutionError("Luna-Direct reuse source binding drift")
        if any(validate_skill_static(skill) for skill in skills) or skill_memory_capacity_issues(
            skills
        ):
            raise ExecutionError("Luna-Direct library no longer passes its static contract")
        return manifest

    def load_luna_skills(self) -> list[SkillContract]:
        root = self.store.root / "baselines" / "luna_direct" / "skills"
        return [
            SkillContract.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            for path in sorted(root.glob("*.yaml"))
        ]

    def _apply_insight_update(
        self,
        bank: dict[str, dict[str, Any]],
        update: InsightUpdate,
        *,
        block_index: int,
        pair_ids: list[str],
    ) -> list[dict[str, Any]]:
        audit: list[dict[str, Any]] = []
        allowed_domains = set(self.config["domain_router"]["domains"])
        for operation in update.operations:
            record = operation.model_dump(mode="json")
            if operation.pair_index > len(pair_ids):
                record.update(
                    {
                        "source_case_id": None,
                        "applied": False,
                        "reason": "pair_index_outside_current_chunk",
                    }
                )
                audit.append(record)
                continue
            source_case = pair_ids[operation.pair_index - 1]
            record["source_case_id"] = source_case
            record["applied"] = False
            record["reason"] = None
            if operation.operation == "ADD":
                insight_id = str(operation.new_insight_id)
                if not re.fullmatch(r"expel\.insight\.[a-z][a-z0-9_.-]+", insight_id):
                    record["reason"] = "invalid_new_insight_id"
                elif insight_id in bank:
                    record["reason"] = "duplicate_new_insight_id"
                elif operation.domain not in allowed_domains:
                    record["reason"] = "unsupported_domain"
                elif issues := _insight_text_issues(str(operation.insight)):
                    record["reason"] = ",".join(issues)
                else:
                    bank[insight_id] = {
                        "insight_id": insight_id,
                        "domain": operation.domain,
                        "insight": operation.insight,
                        "votes": 1,
                        "support_count": 1,
                        "source_case_ids": [source_case],
                        "created_block": block_index,
                        "updated_block": block_index,
                    }
                    record["applied"] = True
            else:
                insight_id = str(operation.existing_insight_id)
                target = bank.get(insight_id)
                if target is None:
                    record["reason"] = "unknown_existing_insight_id"
                elif operation.operation == "EDIT":
                    if operation.domain not in allowed_domains:
                        record["reason"] = "unsupported_domain"
                    elif issues := _insight_text_issues(str(operation.insight)):
                        record["reason"] = ",".join(issues)
                    else:
                        target["domain"] = operation.domain
                        target["insight"] = operation.insight
                        target["support_count"] += 1
                        target["source_case_ids"] = sorted(
                            set(target["source_case_ids"] + [source_case])
                        )
                        target["updated_block"] = block_index
                        record["applied"] = True
                elif operation.operation == "UPVOTE":
                    target["votes"] += 1
                    target["support_count"] += 1
                    target["source_case_ids"] = sorted(
                        set(target["source_case_ids"] + [source_case])
                    )
                    target["updated_block"] = block_index
                    record["applied"] = True
                else:
                    target["votes"] -= 1
                    target["updated_block"] = block_index
                    record["applied"] = True
            audit.append(record)
        maximum = int(self.config["expel_adapted"]["maximum_insights"])
        if len(bank) > maximum:
            retained = sorted(
                bank.values(),
                key=lambda item: (
                    -int(item["votes"]),
                    -int(item["support_count"]),
                    str(item["insight_id"]),
                ),
            )[:maximum]
            retained_ids = {str(item["insight_id"]) for item in retained}
            for insight_id in list(bank):
                if insight_id not in retained_ids:
                    del bank[insight_id]
        return audit

    def train_expel(self) -> dict[str, Any]:
        protocol = self.verified_protocol()
        self._verify_luna_manifest()
        manifest_path = self.store.root / "manifests" / f"{EXPEL_MANIFEST}.json"
        if manifest_path.is_file():
            return self._verify_expel_manifest()
        config = self.config["expel_adapted"]
        training_path = self.root / config["training_cases"]
        if sha256_file(training_path) != config["training_cases_expected_sha256"]:
            raise ExecutionError("ExpeL training corpus hash drift")
        executor = MainExperimentExecutor(
            self.root,
            self.run_id,
            allow_external_data_access=False,
        )
        runner = executor._runner(paired=False, cache_namespace="expel_training")
        teacher = self._teacher_client(str(config["insight_teacher_role"]), "expel_insight_updates")
        insight_prompt = (self.root / config["insight_prompt"]).read_text(encoding="utf-8")
        bank: dict[str, dict[str, Any]] = {}
        bank_audit: list[dict[str, Any]] = []
        positive_pool: list[dict[str, Any]] = []
        empty_hash = canonical_json_sha256([])
        seed = int(config["training_dialogue_seed"])
        group_size = int(config["trajectories_per_case"])
        all_trajectory_records: dict[str, dict[str, str]] = {}
        block_checkpoints: list[dict[str, Any]] = []
        for block_index, batch in enumerate(executor.training_plan.batches, start=1):
            partition = f"expel_training_batch_{block_index:02d}"
            requests: list[tuple[str, dict[str, Any], int, str, str]] = []
            for case_id in batch.case_ids:
                persona = executor.main_adapter.persona(str(config["training_persona"]))
                group_id = f"{partition}.{case_id}.P_WD.seed_{seed}"
                for sample_index in range(group_size):
                    identity = trajectory_identity(
                        run_id=self.run_id,
                        partition=partition,
                        method="training_policy_sample",
                        case_id=case_id,
                        persona=str(config["training_persona"]),
                        seed=seed,
                        sample_index=sample_index,
                        skill_library_version=empty_hash,
                    )
                    requests.append((case_id, persona, sample_index, group_id, identity))

            def run_one(
                request: tuple[str, dict[str, Any], int, str, str],
                current_partition: str = partition,
            ) -> ResearchTrajectory:
                case_id, persona, sample_index, group_id, identity = request
                return executor._load_or_run(
                    runner=runner,
                    adapter=executor.main_adapter,
                    case_id=case_id,
                    persona=persona,
                    skills=[],
                    trajectory_id=identity,
                    method="training_policy_sample",
                    partition=current_partition,
                    seed=seed,
                    sample_index=sample_index,
                    group_id=group_id,
                    skill_hash=empty_hash,
                )

            trajectories = parallel_map_ordered(
                requests,
                run_one,
                max_workers=int(self.config["shared_runtime"]["rollout_workers"]),
                label=partition,
                fail_fast=True,
            )
            failed = [item.trajectory_id for item in trajectories if item.status == "error"]
            if failed:
                raise ExecutionError(f"ExpeL training rollout failures: {failed[:5]}")
            evaluations = executor.score_trajectories(trajectories, executor.main_adapter)
            by_case: dict[str, list[ResearchTrajectory]] = {}
            for trajectory in trajectories:
                by_case.setdefault(trajectory.case_id, []).append(trajectory)
                all_trajectory_records[trajectory.trajectory_id] = {
                    "trajectory_sha256": sha256_file(
                        executor.store.trajectory_path(partition, trajectory.trajectory_id)
                    ),
                    "evaluation_sha256": sha256_file(
                        executor.store.evaluation_path(trajectory.trajectory_id)
                    ),
                }
            pairs: list[dict[str, Any]] = []
            for case_id in batch.case_ids:
                members = sorted(
                    by_case[case_id],
                    key=lambda item: (
                        evaluations[item.trajectory_id].reward.final_reward,
                        item.trajectory_id,
                    ),
                )
                low, high = members[0], members[-1]
                low_eval = evaluations[low.trajectory_id]
                high_eval = evaluations[high.trajectory_id]
                gap = high_eval.reward.final_reward - low_eval.reward.final_reward
                positive_pool.append(
                    {
                        "case_id": case_id,
                        "domain": executor.main_adapter.case_domain(case_id),
                        "opening": high.opening,
                        "trajectory_id": high.trajectory_id,
                        "reward": high_eval.reward.final_reward,
                        "dialogue": _dialogue(high),
                        "memo": high.memo,
                    }
                )
                if gap < float(config["reward_gap_minimum"]):
                    continue
                pairs.append(
                    {
                        "case_id": case_id,
                        "domain": executor.main_adapter.case_domain(case_id),
                        "opening": high.opening,
                        "reward_gap": round(gap, 6),
                        "positive": {
                            "reward": high_eval.reward.final_reward,
                            "behavior": trajectory_behavior_values(high, set()),
                            "dialogue": _dialogue(high),
                            "memo": high.memo,
                        },
                        "negative": {
                            "reward": low_eval.reward.final_reward,
                            "behavior": trajectory_behavior_values(low, set()),
                            "dialogue": _dialogue(low),
                            "memo": low.memo,
                        },
                    }
                )
            chunk_size = int(config["cases_per_teacher_call"])
            for chunk_index in range(0, len(pairs), chunk_size):
                chunk = pairs[chunk_index : chunk_index + chunk_size]
                if not chunk:
                    continue
                teacher_pairs = []
                pair_ids = []
                for pair_index, pair in enumerate(chunk, start=1):
                    pair_ids.append(str(pair["case_id"]))
                    teacher_pair = dict(pair)
                    teacher_pair.pop("case_id")
                    teacher_pair["pair_index"] = pair_index
                    teacher_pairs.append(teacher_pair)
                user_prompt = (
                    "当前insight bank：\n"
                    + json.dumps(
                        [
                            {
                                "insight_id": item["insight_id"],
                                "domain": item["domain"],
                                "insight": item["insight"],
                                "votes": item["votes"],
                            }
                            for item in sorted(
                                bank.values(), key=lambda item: str(item["insight_id"])
                            )
                        ],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n\n同案成功/失败对照：\n"
                    + json.dumps(teacher_pairs, ensure_ascii=False, sort_keys=True)
                )
                response = teacher.generate_json(
                    purpose=(
                        f"expel_insight_block_{block_index:02d}_"
                        f"chunk_{chunk_index // chunk_size + 1:02d}"
                    ),
                    system_prompt=insight_prompt,
                    user_prompt=user_prompt,
                    output_schema=strict_output_schema(InsightUpdate.model_json_schema()),
                )
                update = InsightUpdate.model_validate(response.value)
                operations = self._apply_insight_update(
                    bank,
                    update,
                    block_index=block_index,
                    pair_ids=pair_ids,
                )
                bank_audit.append(
                    {
                        "block": block_index,
                        "chunk": chunk_index // chunk_size + 1,
                        "source_case_count": len(chunk),
                        "request_sha256": response.request_sha256,
                        "response_sha256": response.response_sha256,
                        "model": response.model,
                        "operations": operations,
                    }
                )
            checkpoint = {
                "schema_version": 1,
                "block": block_index,
                "training_cases": len(batch.case_ids),
                "training_trajectories": len(trajectories),
                "eligible_comparison_pairs": len(pairs),
                "insight_count": len(bank),
                "bank_sha256": canonical_json_sha256(
                    sorted(bank.values(), key=lambda item: str(item["insight_id"]))
                ),
            }
            checkpoint_path = (
                self.store.root
                / "baselines"
                / "expel"
                / "checkpoints"
                / f"block_{block_index:02d}.json"
            )
            self.store.immutable_json(checkpoint_path, checkpoint)
            block_checkpoints.append(_artifact_record(self.root, checkpoint_path))

        bank_values = sorted(
            bank.values(),
            key=lambda item: (
                -int(item["votes"]),
                -int(item["support_count"]),
                str(item["insight_id"]),
            ),
        )
        bank_path = self.store.root / "baselines" / "expel" / "insight_bank.json"
        pool_path = self.store.root / "baselines" / "expel" / "positive_pool.json"
        audit_path = self.store.root / "baselines" / "expel" / "insight_update_audit.json"
        self.store.immutable_json(bank_path, bank_values)
        self.store.immutable_json(pool_path, positive_pool)
        self.store.immutable_json(audit_path, bank_audit)
        payload = {
            "schema_version": 1,
            "run_id": self.run_id,
            "protocol_manifest_sha256": protocol["content_sha256"],
            "status": "frozen_before_official_outcomes",
            "training_case_count": len(positive_pool),
            "training_trajectory_count": len(all_trajectory_records),
            "trajectory_artifact_set_sha256": canonical_json_sha256(all_trajectory_records),
            "insight_count": len(bank_values),
            "insight_bank": _artifact_record(self.root, bank_path),
            "positive_pool": _artifact_record(self.root, pool_path),
            "insight_update_audit": _artifact_record(self.root, audit_path),
            "block_checkpoints": block_checkpoints,
            "retriever": config["retriever"],
            "retrieved_positive_trajectories": int(config["retrieved_positive_trajectories"]),
            "frozen_at": _now(),
        }
        self.store.write_manifest(EXPEL_MANIFEST, payload)
        return self._verify_expel_manifest()

    def _verify_expel_manifest(self) -> dict[str, Any]:
        protocol = self.verified_protocol()
        manifest = self.store.read_manifest(EXPEL_MANIFEST)
        if manifest.get("protocol_manifest_sha256") != protocol["content_sha256"]:
            raise ExecutionError("ExpeL bank is bound to another protocol")
        for field in ("insight_bank", "positive_pool", "insight_update_audit"):
            record = manifest.get(field) or {}
            path = self.root / str(record.get("path") or "")
            if not path.is_file() or sha256_file(path) != record.get("sha256"):
                raise ExecutionError(f"ExpeL frozen artifact drift: {field}")
        if int(manifest.get("training_case_count", -1)) != 128:
            raise ExecutionError("ExpeL positive pool does not cover 128 training cases")
        if int(manifest.get("training_trajectory_count", -1)) != 512:
            raise ExecutionError("ExpeL training matrix is not 128 x K4")
        return manifest

    def _expel_memory(self, opening: str, domain: str) -> tuple[str, list[str]]:
        self._verify_expel_manifest()
        bank = json.loads(
            (self.store.root / "baselines" / "expel" / "insight_bank.json").read_text(
                encoding="utf-8"
            )
        )
        pool = json.loads(
            (self.store.root / "baselines" / "expel" / "positive_pool.json").read_text(
                encoding="utf-8"
            )
        )
        applicable_insights = [
            item
            for item in bank
            if item["domain"] in {"general", domain} and int(item["votes"]) > 0
        ]
        query = _character_bigrams(opening)
        ranked = sorted(
            pool,
            key=lambda item: (
                -_cosine(query, _character_bigrams(str(item["opening"]))),
                str(item["case_id"]),
            ),
        )[: int(self.config["expel_adapted"]["retrieved_positive_trajectories"])]
        candidate_examples = [
            {
                "memory_id": "expel.positive." + canonical_json_sha256(item["trajectory_id"])[:16],
                "domain": item["domain"],
                "opening": item["opening"],
                "dialogue": item["dialogue"],
                "memo": item["memo"],
            }
            for item in ranked
        ]
        limit = int(self.config["expel_adapted"]["maximum_session_memory_characters"])
        selected_insights: list[dict[str, Any]] = []
        examples: list[dict[str, Any]] = []

        def render() -> str:
            return (
                EXPERIENCE_MEMORY_HEADER
                + "\n"
                + json.dumps(
                    {
                        "insights": selected_insights,
                        "retrieved_training_successes": examples,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )

        # Frozen bank rank and opening-similarity rank determine capacity; no
        # official outcome can enter this projection.
        for item in applicable_insights:
            selected_insights.append(
                {
                    "insight_id": item["insight_id"],
                    "domain": item["domain"],
                    "insight": item["insight"],
                }
            )
            if len(render()) > limit:
                selected_insights.pop()
        for item in candidate_examples:
            examples.append(item)
            if len(render()) > limit:
                examples.pop()
        rendered = render()
        memory_ids = sorted(
            [str(item["insight_id"]) for item in selected_insights]
            + [str(item["memory_id"]) for item in examples]
        )
        if not memory_ids:
            raise ExecutionError("ExpeL memory has no deliverable insight or positive example")
        return rendered, memory_ids

    def _record_official_access(self, purpose: str) -> None:
        path = self.store.root / "manifests" / ACCESS_LOG
        rows: list[dict[str, Any]] = []
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, list):
                raise ExecutionError("official access log is invalid")
            rows = value
        rows.append({"purpose": purpose, "accessed_at": _now()})
        self.store.atomic_json(path, rows)

    def _official_routes(
        self,
        executor: MainExperimentExecutor,
        adapter: DLawBenchAdapter,
        protocol_sha256: str,
    ) -> dict[str, str]:
        route_path = self.store.root / "reports" / "official_fixed_domain_routes.json"
        domain_catalog = self.config["domain_router"]["domains"]
        allowed = list(domain_catalog)
        expected = {
            "schema_version": 1,
            "run_id": self.run_id,
            "protocol_manifest_sha256": protocol_sha256,
            "input_boundary": "public_opening_and_fixed_method_independent_taxonomy_only",
            "shared_across_all_arms_personas_and_seeds": True,
            "domain_catalog_sha256": canonical_json_sha256(domain_catalog),
            "router_model": self.roles["roles"][self.config["domain_router"]["model_role"]][
                "model_id"
            ],
            "router_revision": self.roles["roles"][self.config["domain_router"]["model_role"]][
                "revision"
            ],
            "case_ids": list(adapter.case_ids()),
        }

        def validate(value: dict[str, Any]) -> dict[str, str]:
            if any(value.get(key) != expected_value for key, expected_value in expected.items()):
                raise ExecutionError("official method-independent route contract drift")
            rows = value.get("routes")
            if not isinstance(rows, list) or len(rows) != len(adapter.case_ids()):
                raise ExecutionError("official route matrix incomplete")
            routes = {str(item["case_id"]): str(item["domain"]) for item in rows}
            if set(routes) != set(adapter.case_ids()) or not set(routes.values()) <= set(allowed):
                raise ExecutionError("official route values invalid")
            return routes

        if route_path.is_file():
            return validate(json.loads(route_path.read_text(encoding="utf-8")))
        template = (self.root / self.config["shared_runtime"]["domain_router_prompt"]).read_text(
            encoding="utf-8"
        )
        prompt = template.replace(
            "{domain_catalog}", json.dumps(domain_catalog, ensure_ascii=False, sort_keys=True)
        )
        role = self.roles["roles"][self.config["domain_router"]["model_role"]]
        router = ReplayCachedChatClient(
            executor.local_client,
            self.store.root / "cache" / "official_fixed_domain_router",
        )
        schema = {
            "type": "object",
            "properties": {"domain": {"type": "string", "enum": allowed}},
            "required": ["domain"],
            "additionalProperties": False,
        }

        def route_one(case_id: str) -> dict[str, Any]:
            opening = str(adapter.lawyer_case(case_id)["opening"])
            response = router.generate(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "客户公开开场：\n" + opening},
                ],
                GenerationConfig(
                    temperature=float(role["temperature"]),
                    top_p=float(role["top_p"]),
                    max_tokens=int(role["max_tokens"]),
                    seed=int(self.config["reporting"]["statistical_seed"]),
                    disable_thinking=True,
                    response_schema=schema,
                    response_schema_name="official_fixed_domain_route",
                ),
            )
            value = json.loads(response.content)
            return {
                "case_id": case_id,
                "public_opening_sha256": canonical_json_sha256(opening),
                "domain": str(value["domain"]),
                "response_sha256": canonical_json_sha256(response.content),
            }

        rows = parallel_map_ordered(
            list(adapter.case_ids()),
            route_one,
            max_workers=int(role["max_workers"]),
            label="official_fixed_domain_router",
            fail_fast=True,
        )
        report = {
            **expected,
            "routes": rows,
            "domain_counts": dict(sorted(Counter(str(item["domain"]) for item in rows).items())),
            "completed_at": _now(),
        }
        self.store.immutable_json(route_path, report)
        return validate(report)

    def _official_prerequisites(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        protocol = self.verified_protocol()
        luna = self._verify_luna_manifest()
        expel = self._verify_expel_manifest()
        return protocol, luna, expel

    def _validated_ours_training_source(
        self,
        training_run_id: str,
    ) -> tuple[MainExperimentExecutor, list[SkillContract], dict[str, Any]]:
        """Validate a frozen Ours library without constructing a CN30 adapter.

        The immutable run envelope, current non-benchmark protocol hashes,
        schema-6 training summary, all eight block transactions and the four B8
        safeguard artifacts are checked before the official payload is parsed,
        routed or supplied to a model.  The shared boundary may verify the
        already-declared payload checksum as part of the immutable run binding.
        """

        if not training_run_id.strip():
            raise ValueError("legal_skill_evolve requires a non-empty training_run_id")
        source = MainExperimentExecutor(
            self.root,
            training_run_id,
            allow_external_data_access=False,
        )
        run_manifest_path = source.store.root / "manifests" / "run.json"
        training_complete_path = source.store.root / "manifests" / "training_complete.json"
        summary, active, integrity = source.validated_external_ready_training_freeze()
        active_version = source.registry.current()
        active_sha256 = skill_library_sha256(active)
        # The shared executor boundary already verifies each condition below.
        # Keep the explicit assertions here because these fields become the
        # immutable cross-run binding consumed by all four paper-table arms.
        if summary.schema_version != 6:
            raise ExecutionError("Ours main-table arm requires schema-6 training_complete")
        if summary.case_limit is not None:
            raise ExecutionError("Ours main-table arm requires the complete 128-case training run")
        if integrity.get("passed") is not True:
            raise ExecutionError("Ours source run does not satisfy locked external protocol")
        if not active or active_version is None:
            raise ExecutionError("Ours main-table arm requires a non-empty frozen skill library")
        if (
            summary.active_skill_library_version != active_version
            or summary.active_skill_library_sha256 != active_sha256
            or summary.active_skill_ids != sorted(skill.skill_id for skill in active)
        ):
            raise ExecutionError("Ours source frozen skill library version/hash drift")
        library_manifest_path = source.registry.versions / active_version / "manifest.json"
        if not library_manifest_path.is_file():
            raise ExecutionError("Ours source frozen skill library manifest is missing")

        binding = {
            "schema_version": 1,
            "evidence_role": BENCHMARK_EVIDENCE_ROLE,
            "training_run_id": training_run_id,
            "locked_external_protocol_integrity": integrity,
            "run_manifest_artifact": _artifact_record(self.root, run_manifest_path),
            "training_complete_artifact": _artifact_record(
                self.root, training_complete_path
            ),
            "active_skill_library_version": active_version,
            "active_skill_library_sha256": active_sha256,
            "active_skill_ids": sorted(skill.skill_id for skill in active),
            "active_skill_library_manifest_artifact": _artifact_record(
                self.root, library_manifest_path
            ),
            "final_training_holdout_artifacts": {
                "arms_frozen": summary.final_training_holdout_arms_frozen_artifact,
                "report": summary.final_training_holdout_artifact,
                "disposition": summary.final_training_holdout_disposition_artifact,
                "isolation": summary.final_training_holdout_intervention_isolation_artifact,
            },
        }
        return source, active, binding

    def bind_ours_training_source(self, training_run_id: str) -> dict[str, Any]:
        """Freeze the Ours source before any main-table arm may access CN30."""

        protocol, _, _ = self._official_prerequisites()
        forbidden_existing = [
            self.store.root / "manifests" / ACCESS_LOG,
            self.store.root / "reports" / "official_fixed_domain_routes.json",
            *sorted((self.store.root / "reports").glob("official_*_aggregate.json")),
            *sorted((self.store.root / "manifests").glob("official_*_artifacts.json")),
            *sorted((self.store.root / "trajectories").glob("official_*/*.json")),
        ]
        existing = sorted(
            str(path.relative_to(self.store.root))
            for path in forbidden_existing
            if path.exists() or path.is_symlink()
        )
        if existing:
            raise ExecutionError(
                "Ours training source must be bound before any official main-table access "
                f"or arm artifact; found={existing}"
            )
        _, _, source_binding = self._validated_ours_training_source(training_run_id)
        manifest_path = (
            self.store.root / "manifests" / f"{OURS_TRAINING_BINDING_MANIFEST}.json"
        )
        expected = {
            "schema_version": 1,
            "run_id": self.run_id,
            "status": "ours_training_source_bound_before_all_official_main_table_arms",
            "evidence_role": BENCHMARK_EVIDENCE_ROLE,
            "official_protocol_manifest_sha256": protocol["content_sha256"],
            "source_training_binding": source_binding,
        }
        if manifest_path.is_file():
            current = self.store.read_manifest(OURS_TRAINING_BINDING_MANIFEST)
            comparable = {
                key: value
                for key, value in current.items()
                if key not in {"bound_at", "content_sha256"}
            }
            if comparable != expected:
                raise ExecutionError(
                    "immutable Ours training source binding differs from the requested source"
                )
            return current
        self.store.write_manifest(
            OURS_TRAINING_BINDING_MANIFEST,
            {**expected, "bound_at": _now()},
        )
        return self.store.read_manifest(OURS_TRAINING_BINDING_MANIFEST)

    def _bound_ours_training_source(
        self,
        protocol: dict[str, Any],
    ) -> tuple[MainExperimentExecutor, list[SkillContract], dict[str, Any], dict[str, str]]:
        """Revalidate the immutable source binding before every official arm."""

        manifest_path = (
            self.store.root / "manifests" / f"{OURS_TRAINING_BINDING_MANIFEST}.json"
        )
        if not manifest_path.is_file():
            raise ExecutionError(
                "all official main-table arms require bind-ours-training before the "
                "CN30 adapter, route, or arm execution"
            )
        try:
            current = self.store.read_manifest(OURS_TRAINING_BINDING_MANIFEST)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ExecutionError("Ours training source binding manifest is invalid") from exc
        source_binding = current.get("source_training_binding")
        if not isinstance(source_binding, dict):
            raise ExecutionError("Ours training source binding payload is missing")
        training_run_id = str(source_binding.get("training_run_id") or "")
        source, skills, revalidated = self._validated_ours_training_source(training_run_id)
        expected = {
            "schema_version": 1,
            "run_id": self.run_id,
            "status": "ours_training_source_bound_before_all_official_main_table_arms",
            "evidence_role": BENCHMARK_EVIDENCE_ROLE,
            "official_protocol_manifest_sha256": protocol["content_sha256"],
            "source_training_binding": revalidated,
        }
        comparable = {
            key: value
            for key, value in current.items()
            if key not in {"bound_at", "content_sha256"}
        }
        if comparable != expected:
            raise ExecutionError("Ours training source binding no longer validates")
        return source, skills, revalidated, _artifact_record(self.root, manifest_path)

    def _assert_completed_arm_shared_bindings(
        self,
        *,
        route_artifact: dict[str, str],
        ours_binding_artifact: dict[str, str],
    ) -> None:
        """Prevent any main-table row from surviving a shared-artifact change."""

        for prior_arm_id in OFFICIAL_ARM_IDS:
            report_path = (
                self.store.root / "reports" / f"official_{prior_arm_id}_aggregate.json"
            )
            if not report_path.is_file():
                continue
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ExecutionError(
                    f"completed official arm report is unreadable: {prior_arm_id}"
                ) from exc
            if (
                report.get("evidence_role") != BENCHMARK_EVIDENCE_ROLE
                or report.get("official_fixed_domain_routes_artifact") != route_artifact
                or report.get("ours_training_source_binding_artifact")
                != ours_binding_artifact
            ):
                raise ExecutionError(
                    "official main-table arms do not share one fixed route and Ours source "
                    f"binding: {prior_arm_id}"
                )

    def run_official_arm(
        self,
        arm_id: str,
    ) -> dict[str, Any]:
        if arm_id not in OFFICIAL_ARM_IDS:
            raise ValueError(f"unsupported official main-table arm: {arm_id}")
        protocol, luna_manifest, expel_manifest = self._official_prerequisites()
        _, ours_skills, ours_binding, ours_binding_artifact = (
            self._bound_ours_training_source(protocol)
        )
        report_path = self.store.root / "reports" / f"official_{arm_id}_aggregate.json"
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if (
                report.get("source_training_binding") != ours_binding
                or report.get("ours_training_source_binding_artifact")
                != ours_binding_artifact
            ):
                raise ExecutionError("completed official arm has a different Ours source binding")
            return report
        official = self.config["official_data"]
        official_path = self.root / official["path"]
        # Everything above this line avoids a CN30 adapter and online role: the
        # Ours source is fully validated before the public payload is parsed or routed.
        self._record_official_access(f"execute_arm:{arm_id}")
        if sha256_file(official_path) != official["expected_sha256"]:
            raise ExecutionError("official DLawBench payload hash drift")
        executor = MainExperimentExecutor(self.root, self.run_id, allow_external_data_access=True)
        adapter = executor.external_adapter
        if adapter is None or len(adapter.case_ids()) != int(official["expected_cases"]):
            raise ExecutionError("official DLawBench case matrix mismatch")
        routes = self._official_routes(executor, adapter, protocol["content_sha256"])
        route_path = self.store.root / "reports" / "official_fixed_domain_routes.json"
        route_artifact = _artifact_record(self.root, route_path)
        self._assert_completed_arm_shared_bindings(
            route_artifact=route_artifact,
            ours_binding_artifact=ours_binding_artifact,
        )
        runner = executor._runner(paired=True, cache_namespace=f"official_{arm_id}")
        arm_skills = (
            self.load_luna_skills()
            if arm_id == "luna_direct"
            else ours_skills
            if arm_id == "legal_skill_evolve"
            else []
        )
        intervention_root = (
            luna_manifest["library_sha256"]
            if arm_id == "luna_direct"
            else expel_manifest["content_sha256"]
            if arm_id == "expel_adapted"
            else str(ours_binding["active_skill_library_sha256"])
            if arm_id == "legal_skill_evolve" and ours_binding is not None
            else canonical_json_sha256([])
        )
        requests: list[dict[str, Any]] = []
        for case_id in adapter.case_ids():
            opening = str(adapter.lawyer_case(case_id)["opening"])
            domain = routes[case_id]
            memory = None
            memory_ids = None
            cell_hash = intervention_root
            if arm_id == "expel_adapted":
                memory, memory_ids = self._expel_memory(opening, domain)
                cell_hash = canonical_json_sha256(
                    {"intervention": intervention_root, "memory": memory}
                )
            for persona_id in official["personas"]:
                identity = trajectory_identity(
                    run_id=self.run_id,
                    partition=f"official_{arm_id}",
                    method=arm_id,
                    case_id=case_id,
                    persona=persona_id,
                    seed=int(official["dialogue_seed"]),
                    sample_index=0,
                    skill_library_version=cell_hash,
                )
                requests.append(
                    {
                        "case_id": case_id,
                        "persona": adapter.persona(persona_id),
                        "persona_id": persona_id,
                        "domain": domain,
                        "identity": identity,
                        "memory": memory,
                        "memory_ids": memory_ids,
                        "cell_hash": cell_hash,
                    }
                )

        def run_one(request: dict[str, Any]) -> ResearchTrajectory:
            return executor._load_or_run(
                runner=runner,
                adapter=adapter,
                case_id=request["case_id"],
                persona=request["persona"],
                skills=arm_skills,
                trajectory_id=request["identity"],
                method=arm_id,
                partition=f"official_{arm_id}",
                seed=int(official["dialogue_seed"]),
                sample_index=0,
                group_id=(
                    f"official.{request['case_id']}.{request['persona_id']}."
                    f"seed_{official['dialogue_seed']}"
                ),
                skill_hash=request["cell_hash"],
                domain_override=request["domain"],
                policy_memory_override=request["memory"],
                exposed_memory_ids=request["memory_ids"],
            )

        trajectories = parallel_map_ordered(
            requests,
            run_one,
            max_workers=int(self.config["shared_runtime"]["rollout_workers"]),
            label=f"official_{arm_id}",
            fail_fast=True,
        )
        failed = [item.trajectory_id for item in trajectories if item.status == "error"]
        if failed:
            raise ExecutionError(f"official {arm_id} rollout failures: {failed[:5]}")
        expected_libraries = None
        if arm_id in {"control_no_library", "luna_direct", "legal_skill_evolve"}:
            expected_libraries = {request["cell_hash"]: arm_skills for request in requests}
        evaluations = executor.score_trajectories(
            trajectories,
            adapter,
            expected_skill_libraries=expected_libraries,
            score_observed_terminal_failures=True,
        )
        aggregate = self._aggregate_arm(arm_id, trajectories, evaluations)
        artifacts = {
            item.trajectory_id: {
                "trajectory_sha256": sha256_file(
                    executor.store.trajectory_path(item.partition, item.trajectory_id)
                ),
                "evaluation_sha256": sha256_file(
                    executor.store.evaluation_path(item.trajectory_id)
                ),
            }
            for item in trajectories
        }
        sealed_path = self.store.root / "manifests" / f"official_{arm_id}_artifacts.json"
        self.store.immutable_json(
            sealed_path,
            {
                "schema_version": 2,
                "run_id": self.run_id,
                "arm_id": arm_id,
                "evidence_role": BENCHMARK_EVIDENCE_ROLE,
                "protocol_manifest_sha256": protocol["content_sha256"],
                "official_fixed_domain_routes_artifact": route_artifact,
                "source_training_binding": ours_binding,
                "ours_training_source_binding_artifact": ours_binding_artifact,
                "sessions": len(trajectories),
                "case_clusters": len(set(item.case_id for item in trajectories)),
                "artifact_set_sha256": canonical_json_sha256(artifacts),
                "artifacts": artifacts,
                "sealed_at": _now(),
            },
        )
        report = {
            "schema_version": 2,
            "run_id": self.run_id,
            "arm_id": arm_id,
            "status": "complete_benchmark_aware_locked_method_level_aggregate",
            "evidence_role": BENCHMARK_EVIDENCE_ROLE,
            "protocol_manifest_sha256": protocol["content_sha256"],
            "official_fixed_domain_routes_artifact": route_artifact,
            "source_training_binding": ours_binding,
            "ours_training_source_binding_artifact": ours_binding_artifact,
            "sessions": len(trajectories),
            "case_clusters": len(set(item.case_id for item in trajectories)),
            "independent_unit": "case_id",
            "aggregate": aggregate,
            "sealed_artifact_manifest": _artifact_record(self.root, sealed_path),
            "completed_at": _now(),
        }
        self.store.immutable_json(report_path, report)
        return report

    def _aggregate_arm(
        self,
        arm_id: str,
        trajectories: list[ResearchTrajectory],
        evaluations: dict[str, TrajectoryEvaluation],
    ) -> dict[str, Any]:
        official = {
            name: round(
                statistics.fmean(
                    float(getattr(evaluations[item.trajectory_id].official_metrics, name))
                    for item in trajectories
                ),
                6,
            )
            for name in OFFICIAL_METRICS
        }
        safety = {
            name: round(
                statistics.fmean(
                    float(getattr(evaluations[item.trajectory_id].safety_metrics, name))
                    for item in trajectories
                ),
                6,
            )
            for name in SAFETY_METRICS
        }
        operational = {
            name: round(
                statistics.fmean(
                    float(getattr(evaluations[item.trajectory_id].operational_metrics, name))
                    for item in trajectories
                ),
                6,
            )
            for name in OPERATIONAL_METRICS
        }
        judge_extractors = {
            "rubric_repair_rate": lambda value: float(value.rubric_repair_used),
            "fact_repair_rate": lambda value: float(value.fact_repair_used),
            "grounding_repair_rate": lambda value: float(value.grounding_repair_used),
            "rubric_normalization_rate": lambda value: float(bool(value.rubric_normalizations)),
            "fact_normalization_rate": lambda value: float(bool(value.fact_normalizations)),
            "grounding_normalization_rate": lambda value: float(
                bool(value.grounding_normalizations)
            ),
        }
        judge = {
            name: round(
                statistics.fmean(
                    judge_extractors[name](evaluations[item.trajectory_id]) for item in trajectories
                ),
                6,
            )
            for name in JUDGE_DIAGNOSTIC_METRICS
        }
        exposed = {memory_id for item in trajectories for memory_id in item.exposed_skill_ids}
        behavior = trajectory_behavior_summary(trajectories, exposed)
        behavior["method_memory_exposure_rate"] = round(
            sum(bool(item.exposed_skill_ids) for item in trajectories) / len(trajectories), 6
        )
        return {
            "official_metrics": official,
            "behavior_metrics": {
                name: round(
                    statistics.fmean(
                        trajectory_behavior_values(item, exposed)[name] for item in trajectories
                    ),
                    6,
                )
                for name in PAIRED_BEHAVIOR_METRICS
            },
            "behavior_summary": behavior,
            "safety_metrics": safety,
            "operational_metrics": operational,
            "judge_diagnostics": judge,
        }

    def reveal_completed_baselines(self) -> dict[str, Any]:
        completed: dict[str, Any] = {}
        for arm_id in OFFICIAL_ARM_IDS:
            path = self.store.root / "reports" / f"official_{arm_id}_aggregate.json"
            if path.is_file():
                report = json.loads(path.read_text(encoding="utf-8"))
                completed[arm_id] = report["aggregate"]
        return {
            "schema_version": 2,
            "run_id": self.run_id,
            "view": "method_level_aggregate_only",
            "evidence_role": BENCHMARK_EVIDENCE_ROLE,
            "completed_arms": list(completed),
            "arms": completed,
            "paired_vs_base": self._completed_paired_comparisons(set(completed)),
            "legal_skill_evolve": completed.get("legal_skill_evolve", "[PENDING RESULT]"),
        }

    def _completed_paired_comparisons(self, completed_arms: set[str]) -> dict[str, Any]:
        """Return only aggregate case-clustered estimates, never individual rows."""

        if "control_no_library" not in completed_arms:
            return {}

        def load_arm(
            arm_id: str,
        ) -> tuple[list[ResearchTrajectory], dict[str, TrajectoryEvaluation]]:
            trajectories = [
                self.store.load_model(path, ResearchTrajectory)
                for path in sorted(
                    (self.store.root / "trajectories" / f"official_{arm_id}").glob("*.json")
                )
            ]
            trajectories.sort(key=lambda item: (item.case_id, item.persona, item.seed))
            evaluations = {
                item.trajectory_id: self.store.load_model(
                    self.store.evaluation_path(item.trajectory_id), TrajectoryEvaluation
                )
                for item in trajectories
            }
            return trajectories, evaluations

        control, control_evaluations = load_arm("control_no_library")
        config = self.config["reporting"]
        comparisons: dict[str, Any] = {}
        for arm_id in OFFICIAL_ARM_IDS[1:]:
            if arm_id not in completed_arms:
                continue
            treatment, treatment_evaluations = load_arm(arm_id)
            if [(item.case_id, item.persona, item.seed) for item in control] != [
                (item.case_id, item.persona, item.seed) for item in treatment
            ]:
                raise ExecutionError(f"official paired matrix drift for {arm_id}")
            metrics: dict[str, Any] = {}
            for name in (*OFFICIAL_METRICS, *SAFETY_METRICS, *OPERATIONAL_METRICS):
                section = (
                    "official_metrics"
                    if name in OFFICIAL_METRICS
                    else "safety_metrics"
                    if name in SAFETY_METRICS
                    else "operational_metrics"
                )
                before = [
                    float(getattr(getattr(control_evaluations[item.trajectory_id], section), name))
                    for item in control
                ]
                after = [
                    float(
                        getattr(
                            getattr(treatment_evaluations[item.trajectory_id], section),
                            name,
                        )
                    )
                    for item in treatment
                ]
                deltas = clustered_mean_deltas([item.case_id for item in control], before, after)
                estimate = paired_bootstrap_interval(
                    deltas,
                    samples=int(config["bootstrap_samples"]),
                    confidence_level=float(config["confidence_level"]),
                    seed=int(config["statistical_seed"]),
                ).model_dump(mode="json")
                estimate["paired_p_value"] = paired_sign_flip_p_value(
                    deltas,
                    samples=int(config["randomization_samples"]),
                    seed=int(config["statistical_seed"]),
                )
                metrics[name] = estimate
            control_ids: set[str] = set()
            treatment_ids = {
                memory_id for item in treatment for memory_id in item.exposed_skill_ids
            }
            for name in PAIRED_BEHAVIOR_METRICS:
                before = [trajectory_behavior_values(item, control_ids)[name] for item in control]
                after = [
                    trajectory_behavior_values(item, treatment_ids)[name] for item in treatment
                ]
                deltas = clustered_mean_deltas([item.case_id for item in control], before, after)
                estimate = paired_bootstrap_interval(
                    deltas,
                    samples=int(config["bootstrap_samples"]),
                    confidence_level=float(config["confidence_level"]),
                    seed=int(config["statistical_seed"]),
                ).model_dump(mode="json")
                estimate["paired_p_value"] = paired_sign_flip_p_value(
                    deltas,
                    samples=int(config["randomization_samples"]),
                    seed=int(config["statistical_seed"]),
                )
                metrics[name] = estimate
            comparisons[f"{arm_id}_minus_control_no_library"] = {
                "cluster_unit": "case_id",
                "case_clusters": len(set(item.case_id for item in control)),
                "session_pairs": len(control),
                "metrics": metrics,
            }
        return comparisons

    def status(self) -> dict[str, Any]:
        def exists(name: str) -> bool:
            return (self.store.root / "manifests" / f"{name}.json").is_file()

        expel_trajectories = len(
            list((self.store.root / "trajectories").glob("expel_training_batch_*/*.json"))
        )
        expel_evaluations = 0
        for trajectory_path in (self.store.root / "trajectories").glob(
            "expel_training_batch_*/*.json"
        ):
            try:
                trajectory = ResearchTrajectory.model_validate_json(
                    trajectory_path.read_text(encoding="utf-8")
                )
            except ValueError:
                continue
            if self.store.evaluation_path(trajectory.trajectory_id).is_file():
                expel_evaluations += 1
        return {
            "run_id": self.run_id,
            "protocol_frozen": exists(PROTOCOL_MANIFEST),
            "luna_direct_frozen": exists(LUNA_MANIFEST),
            "expel_frozen": exists(EXPEL_MANIFEST),
            "ours_training_source_bound": exists(OURS_TRAINING_BINDING_MANIFEST),
            "expel_training_trajectories": expel_trajectories,
            "expel_training_evaluations": expel_evaluations,
            "official_arms_complete": [
                arm_id
                for arm_id in OFFICIAL_ARM_IDS
                if (self.store.root / "reports" / f"official_{arm_id}_aggregate.json").is_file()
            ],
            "official_access_started": (self.store.root / "manifests" / ACCESS_LOG).is_file(),
            "visible_results": self.reveal_completed_baselines(),
        }
