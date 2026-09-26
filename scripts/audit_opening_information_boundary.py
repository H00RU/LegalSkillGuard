#!/usr/bin/env python3
"""Audit whether every hidden client belief adds information beyond the opening."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from legal_skill_guard.inference.openai_client import (
    ChatClient,
    GenerationConfig,
    ReplayCachedChatClient,
)
from legal_skill_guard.inference.structured_openai_client import StructuredOpenAIClient
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl"
OUTPUT = ROOT / "reports/artifacts/main_corpus_opening_information_boundary.json"
ADJUDICATIONS = ROOT / "configs/qualification/opening_information_boundary_adjudications.yaml"
LABELS = ("fully_present", "partially_new", "genuinely_new")
SYSTEM_PROMPT = """
你是法律咨询数据集的信息边界审计员。逐条比较公开开场与隐藏客户认知，不评价事实真伪或法律结论。

- fully_present：开场已经完整给出该隐藏认知中对咨询有实质意义的事实；律师无需追问即可知道。
- partially_new：二者有重叠，但隐藏认知仍新增至少一个会影响调查或分析的具体属性，例如主体、时间、
  数额、行为方式、文件内容、证据、因果或客户明确认知。只增加同义措辞不算新增。
- genuinely_new：开场没有给出该隐藏认知的实质内容。

opening 允许概括争议触发和求助目标，因此主题相同不等于 fully_present。
必须为每个 F 编号输出一个标签。
""".strip()


def load_cases() -> list[dict[str, Any]]:
    return [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line]


def schema_for(case: dict[str, Any]) -> dict[str, Any]:
    fact_ids = [str(item["fact_id"]) for item in case["facts"]]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["facts"],
        "properties": {
            "facts": {
                "type": "object",
                "additionalProperties": False,
                "required": fact_ids,
                "properties": {
                    fact_id: {"type": "string", "enum": list(LABELS)}
                    for fact_id in fact_ids
                },
            }
        },
    }


def user_prompt(case: dict[str, Any]) -> str:
    beliefs = "\n".join(
        f"{item['fact_id']}: {item['client_belief']}" for item in case["facts"]
    )
    return f"案件：{case['id']}\n公开开场：{case['opening']}\n隐藏客户认知：\n{beliefs}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be positive")

    roles = yaml.safe_load(
        (ROOT / "configs/models/roles.yaml").read_text(encoding="utf-8")
    )["roles"]
    # This audit deliberately uses two different model families.  The client
    # router may share the judge service, so derive Qwen from the frozen lawyer
    # role rather than accidentally turning a nominal dual-model screen into two
    # calls to the same model.
    qwen = roles["lawyer_policy"]
    judge = roles["semantic_judge"]
    model_specs = {
        "qwen3_8b": {
            "base_url": qwen["base_url"],
            "model": qwen["model_id"],
            "revision": qwen["revision"],
            "reasoning_effort": "low",
            "max_completion_tokens": 256,
            "backend": "chat_no_thinking",
        },
        "gpt_oss_20b": {
            "base_url": judge["base_url"],
            "model": judge["model_id"],
            "revision": judge["revision"],
            "reasoning_effort": judge["reasoning_effort"],
            "max_completion_tokens": 2048,
            "backend": "structured_reasoning",
        },
    }
    cases = load_cases()
    clients: dict[str, Any] = {
        "qwen3_8b": ReplayCachedChatClient(
            ChatClient(
                str(model_specs["qwen3_8b"]["base_url"]),
                str(model_specs["qwen3_8b"]["model"]),
                retries=1,
            ),
            ROOT
            / "runs/qualification_cache/opening_information_boundary/protocol_2/qwen3_8b",
        ),
        "gpt_oss_20b": StructuredOpenAIClient(
            base_url=str(model_specs["gpt_oss_20b"]["base_url"]),
            model=str(model_specs["gpt_oss_20b"]["model"]),
            model_revision=str(model_specs["gpt_oss_20b"]["revision"]),
            cache_root=ROOT
            / "runs/qualification_cache/opening_information_boundary/protocol_2/gpt_oss_20b",
            reasoning_effort=str(model_specs["gpt_oss_20b"]["reasoning_effort"]),
            max_completion_tokens=int(
                model_specs["gpt_oss_20b"]["max_completion_tokens"]
            ),
            retries=1,
        ),
    }
    readiness = {
        name: (
            client.preflight()
            if isinstance(client, StructuredOpenAIClient)
            else {"ready": client.is_ready(), "model": client.model}
        )
        for name, client in clients.items()
    }
    if not all(bool(item["ready"]) for item in readiness.values()):
        raise SystemExit(f"model service not ready: {readiness}")

    def audit_one(task: tuple[str, dict[str, Any]]) -> dict[str, Any]:
        model_name, case = task
        schema = schema_for(case)
        if model_name == "qwen3_8b":
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt(case)},
            ]
            generation = GenerationConfig(
                temperature=0.0,
                top_p=1.0,
                max_tokens=int(model_specs[model_name]["max_completion_tokens"]),
                seed=0,
                disable_thinking=True,
                response_schema=schema,
                response_schema_name="opening_information_boundary",
            )
            response = clients[model_name].generate(messages, generation)
            value = json.loads(response.content)
            Draft202012Validator(schema).validate(value)
            request_sha256 = canonical_json_sha256(
                {
                    "model": model_specs[model_name]["model"],
                    "messages": messages,
                    "generation": generation.__dict__,
                }
            )
            response_sha256 = canonical_json_sha256(value)
            cache_hit = False
            invocation = {
                "finish_reason": response.finish_reason,
                "usage": {
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                },
                "response_id": response.raw_id,
            }
        else:
            response = clients[model_name].generate_json(
                purpose="opening_information_boundary",
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt(case),
                output_schema=schema,
            )
            value = response.value
            request_sha256 = response.request_sha256
            response_sha256 = response.response_sha256
            cache_hit = response.cache_hit
            invocation = response.invocation
        return {
            "case_id": case["id"],
            "model": model_name,
            "labels": value["facts"],
            "request_sha256": request_sha256,
            "response_sha256": response_sha256,
            "cache_hit": cache_hit,
            "invocation": invocation,
        }

    tasks = [(model_name, case) for model_name in model_specs for case in cases]
    with ThreadPoolExecutor(max_workers=min(args.workers, len(tasks))) as pool:
        rows = list(pool.map(audit_one, tasks))

    counts: dict[str, Counter[str]] = defaultdict(Counter)
    labels_by_case: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        counts[row["model"]].update(row["labels"].values())
        labels_by_case[row["case_id"]][row["model"]] = row["labels"]
    flagged = []
    for case in cases:
        case_id = str(case["id"])
        for fact in case["facts"]:
            fact_id = str(fact["fact_id"])
            model_labels = {
                name: labels_by_case[case_id][name][fact_id] for name in model_specs
            }
            if "fully_present" in model_labels.values():
                flagged.append(
                    {
                        "case_id": case_id,
                        "fact_id": fact_id,
                        "opening": case["opening"],
                        "client_belief": fact["client_belief"],
                        "model_labels": model_labels,
                        "consensus_fully_present": all(
                            label == "fully_present" for label in model_labels.values()
                        ),
                    }
                )
    adjudication_payload = yaml.safe_load(ADJUDICATIONS.read_text(encoding="utf-8"))
    adjudications = adjudication_payload.get("adjudications", {})
    current_data_sha256 = sha256_file(DATA)
    adjudication_corpus_matches = (
        adjudication_payload.get("corpus_core_sha256") == current_data_sha256
    )
    # The two frozen models are high-recall screeners, not adjudicators.  Model
    # agreement must never silently decide whether an opening leaked a hidden
    # belief: every flag is bound to a casewise human/researcher adjudication on
    # the current corpus revision.
    for item in flagged:
        key = f"{item['case_id']}/{item['fact_id']}"
        item["manual_adjudication"] = adjudications.get(key)
    current_flag_keys = {
        f"{item['case_id']}/{item['fact_id']}" for item in flagged
    }
    stale_adjudications = sorted(set(adjudications) - current_flag_keys)
    unreviewed_flags = [
        item
        for item in flagged
        if not isinstance(item.get("manual_adjudication"), dict)
        or item["manual_adjudication"].get("decision")
        not in {"incremental", "leakage"}
        or len(str(item["manual_adjudication"].get("reason") or "")) < 20
    ]
    adjudicated_leakage = [
        item
        for item in flagged
        if isinstance(item.get("manual_adjudication"), dict)
        and item["manual_adjudication"].get("decision") == "leakage"
    ]
    passed = (
        adjudication_corpus_matches
        and not unreviewed_flags
        and not adjudicated_leakage
        and not stale_adjudications
    )
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "passed" if passed else "review_required",
        "pass_rule": (
            "the frozen models only screen candidate boundary violations; every flag, "
            "including model consensus, has a casewise researcher adjudication bound "
            "to the current corpus; no adjudication finds leakage and none is stale"
        ),
        "case_count": len(cases),
        "fact_count": sum(len(case["facts"]) for case in cases),
        "data_sha256": current_data_sha256,
        "script_sha256": sha256_file(Path(__file__)),
        "adjudications_sha256": sha256_file(ADJUDICATIONS),
        "system_prompt_sha256": canonical_json_sha256({"prompt": SYSTEM_PROMPT}),
        "models": model_specs,
        "readiness": readiness,
        "counts": {name: dict(sorted(value.items())) for name, value in counts.items()},
        "flagged_count": len(flagged),
        "consensus_fully_present_count": sum(
            item["consensus_fully_present"] for item in flagged
        ),
        "unreviewed_flag_count": len(unreviewed_flags),
        "adjudicated_leakage_count": len(adjudicated_leakage),
        "stale_adjudications": stale_adjudications,
        "adjudication_corpus_matches": adjudication_corpus_matches,
        "flagged": flagged,
        "rows": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    summary_keys = (
        "status",
        "case_count",
        "fact_count",
        "counts",
        "flagged_count",
        "consensus_fully_present_count",
        "unreviewed_flag_count",
        "adjudicated_leakage_count",
        "stale_adjudications",
        "adjudication_corpus_matches",
    )
    print(
        json.dumps(
            {key: report[key] for key in summary_keys},
            ensure_ascii=False,
            indent=2,
        )
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
