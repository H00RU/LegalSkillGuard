#!/usr/bin/env python3
"""Ask the frozen teacher to turn informative trajectory contrasts into Skill Contracts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from legal_skill_guard.evolution.advantage import AdvantageGroup, select_contrasts
from legal_skill_guard.evolution.diagnosis import parse_diagnosis
from legal_skill_guard.inference.openai_client import GenerationConfig
from legal_skill_guard.skills.loader import (
    find_lexical_near_duplicates,
    find_structural_duplicates,
    find_trigger_conflicts,
    load_skill_directory,
    validate_skill_static,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file

try:
    from scripts.collect_phase3_groups import DEFAULT_CONFIG
    from scripts.run_phase1_baseline import ROOT, LocalVLLMServer, atomic_json, load_yaml
except ModuleNotFoundError:
    from collect_phase3_groups import DEFAULT_CONFIG  # type: ignore[no-redef]
    from run_phase1_baseline import (  # type: ignore[no-redef]
        ROOT,
        LocalVLLMServer,
        atomic_json,
        load_yaml,
    )

PROMPT = ROOT / "configs/prompts/phase3_skill_teacher_zh.txt"


def trajectory_summary(trajectory: dict, reward: dict) -> dict:
    def compact_action(action: dict) -> dict:
        return {
            key: action.get(key)
            for key in (
                "action_type",
                "target_type",
                "target_id",
                "reason",
                "constraints",
            )
        }

    return {
        "trajectory_id": trajectory["trajectory_id"],
        "reward": reward,
        "status": trajectory["status"],
        "steps": [
            {
                "turn": step["turn"],
                "state_before": {
                    key: step["state_before"].get(key)
                    for key in (
                        "high_critical_unknown_count",
                        "unresolved_conflict_count",
                        "client_claimed_high_count",
                        "asked_targets",
                        "risk_flags",
                    )
                },
                "proposed_action": compact_action(step["proposed_action"]),
                "final_action": compact_action(step["action_decision"]["final"]),
                "activated_skills": step["action_decision"]["activated_skill_ids"],
                "question": (step.get("rendered_question") or "")[:240],
                "client_response": (step.get("client_response") or "")[:240],
                "failed_verifiers": [
                    item["validator_id"] for item in step["verifier_results"] if not item["passed"]
                ],
            }
            for step in trajectory["steps"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--group-limit", type=int)
    parser.add_argument("--no-start-server", action="store_true")
    args = parser.parse_args()
    config = load_yaml(args.config.resolve())
    run_root = ROOT / config["outputs"]["run_root"] / args.run_id
    advantage_data = json.loads(
        (run_root / "evolution/group_advantages.json").read_text(encoding="utf-8")
    )
    trajectories = {
        value["trajectory_id"]: value
        for path in sorted((run_root / "trajectories").glob("*/*.json"))
        for value in [json.loads(path.read_text(encoding="utf-8"))]
    }
    informative = [
        (group_id, value)
        for group_id, value in sorted(advantage_data["groups"].items())
        if value["informative"]
    ]
    if args.group_limit:
        informative = informative[: args.group_limit]
    template = PROMPT.read_text(encoding="utf-8")
    settings = config["generation"]["teacher"]
    existing_skills = load_skill_directory(ROOT / config["skill_library"]["path"])
    candidate_ids: list[str] = []
    rejected_candidates = 0
    diagnostics = 0
    with LocalVLLMServer(
        config, run_root / "vllm_teacher.log", auto_start=not args.no_start_server
    ) as client:
        for index, (group_id, raw_group) in enumerate(informative):
            output = run_root / "evolution/diagnoses" / f"{group_id}.json"
            if output.is_file():
                existing = json.loads(output.read_text(encoding="utf-8"))
                existing_skill = existing.get("diagnosis", {}).get("candidate_skill")
                if existing_skill:
                    candidate_ids.append(existing_skill["skill_id"])
                continue
            group = AdvantageGroup.model_validate(raw_group)
            selection = select_contrasts(group)
            selected_ids = list(
                dict.fromkeys(
                    item
                    for item in (
                        selection.highest_id,
                        selection.lowest_id,
                        selection.safety_failure_id,
                        selection.efficient_failure_id,
                    )
                    if item
                )
            )
            payload = {
                "group_id": group_id,
                "case_id": trajectories[selected_ids[0]]["case_id"],
                "persona": trajectories[selected_ids[0]]["persona"],
                "contrasts": [
                    trajectory_summary(
                        trajectories[trajectory_id],
                        advantage_data["trajectories"][trajectory_id],
                    )
                    for trajectory_id in selected_ids
                ],
            }
            prompt = template.replace("{contrast_payload}", json.dumps(payload, ensure_ascii=False))
            response = client.generate(
                [{"role": "user", "content": prompt}],
                GenerationConfig(
                    temperature=float(settings["temperature"]),
                    top_p=float(settings["top_p"]),
                    max_tokens=int(settings["max_tokens"]),
                    seed=int(config["seed"]) + 30_000 + index,
                    disable_thinking=config["generation"]["disable_thinking"],
                ),
            )
            diagnosis, parse_mode = parse_diagnosis(response.content, group_id)
            if diagnosis.candidate_skill is not None:
                skill = diagnosis.candidate_skill
                skill.status = "candidate"
                skill.provenance.source = "tf_grpo"
                executable_contract = skill.model_dump(
                    mode="json", exclude={"provenance", "evaluation"}
                )
                serialized = json.dumps(executable_contract, ensure_ascii=False)
                static_issues = validate_skill_static(skill)
                duplicates = find_structural_duplicates(skill, existing_skills)
                static_issues.extend(f"structural_duplicate:{item}" for item in duplicates)
                conflicts = find_trigger_conflicts(skill, existing_skills)
                static_issues.extend(f"trigger_conflict:{item}" for item in conflicts)
                near_duplicates = find_lexical_near_duplicates(skill, existing_skills)
                static_issues.extend(f"lexical_near_duplicate:{item}" for item in near_duplicates)
                existing_ids = {item.skill_id for item in existing_skills}
                if diagnosis.proposed_change == "CREATE" and skill.skill_id in existing_ids:
                    static_issues.append("create_reuses_existing_skill_id")
                if diagnosis.proposed_change in {"REFINE", "REPAIR", "DEPRECATE"} and (
                    skill.skill_id not in existing_ids
                ):
                    static_issues.append("update_targets_unknown_skill_id")
                case_specific = trajectories[selected_ids[0]]["case_id"] in serialized
                if case_specific or static_issues:
                    diagnosis.proposed_change = "NOOP"
                    diagnosis.candidate_skill = None
                    diagnosis.known_risks.extend(
                        [
                            "case_specific_trigger_rejected"
                            if case_specific
                            else "static_validation_rejected",
                            *static_issues,
                        ]
                    )
                    rejected_candidates += 1
                else:
                    skill.provenance.source_case_ids = [trajectories[selected_ids[0]]["case_id"]]
                    skill.provenance.source_trajectory_ids = selected_ids
                    skill.provenance.generator_model = config["model"]["id"]
                    skill.provenance.diagnosis_hash = canonical_json_sha256(payload)
                    candidate_path = run_root / "evolution/candidates" / f"{skill.skill_id}.yaml"
                    candidate_path.parent.mkdir(parents=True, exist_ok=True)
                    if not candidate_path.exists():
                        candidate_path.write_text(
                            yaml.safe_dump(
                                skill.model_dump(mode="json", exclude_none=True),
                                allow_unicode=True,
                                sort_keys=False,
                            ),
                            encoding="utf-8",
                        )
                    candidate_ids.append(skill.skill_id)
                    if skill.skill_id not in {item.skill_id for item in existing_skills}:
                        existing_skills.append(skill)
            atomic_json(
                output,
                {
                    "diagnosis": diagnosis.model_dump(mode="json"),
                    "parse_mode": parse_mode,
                    "raw_teacher_output": response.content,
                    "teacher_prompt_hash": canonical_json_sha256(prompt),
                    "contrast_payload_hash": canonical_json_sha256(payload),
                    "selected_trajectory_ids": selected_ids,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            diagnostics += 1
            print(
                f"diagnosed {group_id}: {diagnosis.proposed_change} "
                f"{diagnosis.candidate_skill.skill_id if diagnosis.candidate_skill else ''}",
                flush=True,
            )
    diagnosis_files = sorted((run_root / "evolution/diagnoses").glob("*.json"))
    persisted_diagnoses = [json.loads(path.read_text(encoding="utf-8")) for path in diagnosis_files]
    static_rejections_total = sum(
        "static_validation_rejected" in item["diagnosis"].get("known_risks", [])
        for item in persisted_diagnoses
    )
    summary = {
        "schema_version": 1,
        "run_id": args.run_id,
        "informative_groups_available": len(informative),
        "diagnostics_created_this_call": diagnostics,
        "diagnostics_total": len(diagnosis_files),
        "candidate_skill_ids": sorted(set(candidate_ids)),
        "static_rejections_this_call": rejected_candidates,
        "static_rejections_total": static_rejections_total,
        "teacher_prompt_sha256": sha256_file(PROMPT),
        "generator_script_sha256": sha256_file(Path(__file__)),
    }
    atomic_json(run_root / "evolution/candidate_summary.json", summary)
    manifest_path = run_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["prompt_sha256"] = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in sorted((ROOT / "configs/prompts").glob("*.txt"))
    }
    manifest["teacher_generation"] = summary
    manifest["status"] = "candidate_generation_complete"
    atomic_json(manifest_path, manifest)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
