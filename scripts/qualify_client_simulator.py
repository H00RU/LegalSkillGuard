#!/usr/bin/env python3
"""Qualify grounded client matching and disclosure on immutable run-bound cases."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

import yaml

from legal_skill_guard.environment.client_response import (
    ClientSimulator,
)
from legal_skill_guard.evaluation.qualification import (
    CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION,
    CLIENT_QUALIFICATION_REPORT_SCHEMA_VERSION,
    client_simulator_qualification_component_hashes,
    client_simulator_qualification_sha256,
)
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.openai_client import ChatClient, GenerationConfig
from legal_skill_guard.utils.hashing import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[1]
Disclosure = Literal["disclose", "withhold"]


class QualificationFixtureError(ValueError):
    """The fixture does not implement the current two-axis qualification schema."""


def _require_exact_keys(
    value: dict[str, Any],
    *,
    required: set[str],
    optional: set[str],
    location: str,
) -> None:
    missing = required - set(value)
    extra = set(value) - required - optional
    if missing or extra:
        raise QualificationFixtureError(
            f"{location} keys invalid: missing={sorted(missing)} extra={sorted(extra)}"
        )


def _validate_prior_exchanges(value: object, *, location: str) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise QualificationFixtureError(f"{location} must be a list")
    normalized: list[dict[str, str]] = []
    for index, exchange in enumerate(value):
        if not isinstance(exchange, dict):
            raise QualificationFixtureError(f"{location}[{index}] must be an object")
        _require_exact_keys(
            exchange,
            required={"question", "answer"},
            optional=set(),
            location=f"{location}[{index}]",
        )
        if not all(isinstance(exchange[key], str) and exchange[key].strip() for key in exchange):
            raise QualificationFixtureError(
                f"{location}[{index}] question and answer must be non-empty strings"
            )
        normalized.append({"question": exchange["question"], "answer": exchange["answer"]})
    return normalized


def _validate_fact_ids(value: object, *, location: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.startswith("F") for item in value
    ):
        raise QualificationFixtureError(f"{location} must contain only F identifiers")
    if len(value) != len(set(value)):
        raise QualificationFixtureError(f"{location} contains duplicate identifiers")
    return list(value)


def _validate_turn(
    value: object,
    *,
    location: str,
    persona_id: str,
    pre_disclosed_fact_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QualificationFixtureError(f"{location} must be an object")
    _require_exact_keys(
        value,
        required={
            "question",
            "expected_matched_fact_id",
            "expected_disclosure",
        },
        optional=set(),
        location=location,
    )
    question = value["question"]
    if not isinstance(question, str) or not question.strip():
        raise QualificationFixtureError(f"{location}.question must be a non-empty string")
    matched = value["expected_matched_fact_id"]
    if matched is not None and (not isinstance(matched, str) or not matched.startswith(("F", "O"))):
        raise QualificationFixtureError(
            f"{location}.expected_matched_fact_id must be an F/O identifier or null"
        )
    disclosure = value["expected_disclosure"]
    if disclosure not in {"disclose", "withhold"}:
        raise QualificationFixtureError(
            f"{location}.expected_disclosure must be disclose or withhold"
        )
    if disclosure == "withhold":
        if matched is None or not matched.startswith("F"):
            raise QualificationFixtureError(
                f"{location}: withhold requires one matched hidden F identifier"
            )
        if persona_id not in {"P_CS", "P_CD"}:
            raise QualificationFixtureError(
                f"{location}: only resistant P_CS/P_CD fixtures may expect withhold"
            )
        if matched in pre_disclosed_fact_ids:
            raise QualificationFixtureError(
                f"{location}: an already disclosed fact cannot be withheld"
            )
    if matched is None and disclosure != "disclose":
        raise QualificationFixtureError(
            f"{location}: an empty match must use disclose under the selector schema"
        )
    if isinstance(matched, str) and matched.startswith("O") and disclosure != "disclose":
        raise QualificationFixtureError(
            f"{location}: a public opening reference cannot be withheld"
        )
    return {
        "question": question,
        "expected_matched_fact_id": matched,
        "expected_disclosure": disclosure,
    }


def load_qualification_chains(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load only current observed-question fixtures; legacy formats fail closed."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualificationFixtureError(f"cannot load qualification fixture: {exc}") from exc
    if not isinstance(document, dict):
        raise QualificationFixtureError(
            "legacy flat qualification fixture is not accepted; schema_version=4 required"
        )
    _require_exact_keys(
        document,
        required={"schema_version", "cases", "chains"},
        optional=set(),
        location="fixture",
    )
    if document["schema_version"] != CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION:
        raise QualificationFixtureError(
            "fixture schema mismatch: "
            f"expected={CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION} "
            f"actual={document['schema_version']}"
        )
    cases = document["cases"]
    chains = document["chains"]
    if not isinstance(cases, list) or not isinstance(chains, list):
        raise QualificationFixtureError("fixture cases and chains must be lists")

    normalized: list[dict[str, Any]] = []
    turn_ordinal = 0
    for index, item in enumerate(cases):
        location = f"cases[{index}]"
        if not isinstance(item, dict):
            raise QualificationFixtureError(f"{location} must be an object")
        _require_exact_keys(
            item,
            required={
                "case_id",
                "question",
                "expected_matched_fact_id",
                "expected_disclosure",
            },
            optional={
                "persona_id",
                "pre_disclosed_fact_ids",
                "prior_exchanges",
            },
            location=location,
        )
        persona_id = str(item.get("persona_id") or "P_WD")
        pre_disclosed = _validate_fact_ids(
            item.get("pre_disclosed_fact_ids"),
            location=f"{location}.pre_disclosed_fact_ids",
        )
        prior_exchanges = _validate_prior_exchanges(
            item.get("prior_exchanges"), location=f"{location}.prior_exchanges"
        )
        turn = _validate_turn(
            {
                key: item[key]
                for key in (
                    "question",
                    "expected_matched_fact_id",
                    "expected_disclosure",
                )
                if key in item
            },
            location=location,
            persona_id=persona_id,
            pre_disclosed_fact_ids=set(pre_disclosed),
        )
        turn["turn_ordinal"] = turn_ordinal
        turn_ordinal += 1
        normalized.append(
            {
                "chain_id": f"single_{index:03d}",
                "case_id": str(item["case_id"]),
                "persona_id": persona_id,
                "pre_disclosed_fact_ids": pre_disclosed,
                "prior_exchanges": prior_exchanges,
                "turns": [turn],
            }
        )

    transition_personas: set[str] = set()
    chain_ids = {item["chain_id"] for item in normalized}
    for index, item in enumerate(chains):
        location = f"chains[{index}]"
        if not isinstance(item, dict):
            raise QualificationFixtureError(f"{location} must be an object")
        _require_exact_keys(
            item,
            required={"chain_id", "case_id", "persona_id", "turns"},
            optional={"pre_disclosed_fact_ids", "prior_exchanges"},
            location=location,
        )
        chain_id = item["chain_id"]
        if not isinstance(chain_id, str) or not chain_id.strip() or chain_id in chain_ids:
            raise QualificationFixtureError(f"{location}.chain_id must be non-empty and unique")
        chain_ids.add(chain_id)
        persona_id = str(item["persona_id"])
        pre_disclosed = _validate_fact_ids(
            item.get("pre_disclosed_fact_ids"),
            location=f"{location}.pre_disclosed_fact_ids",
        )
        prior_exchanges = _validate_prior_exchanges(
            item.get("prior_exchanges"), location=f"{location}.prior_exchanges"
        )
        raw_turns = item["turns"]
        if not isinstance(raw_turns, list) or len(raw_turns) < 2:
            raise QualificationFixtureError(
                f"{location}.turns must contain at least two linked turns"
            )
        normalized_turns: list[dict[str, Any]] = []
        for turn_index, raw_turn in enumerate(raw_turns):
            turn = _validate_turn(
                raw_turn,
                location=f"{location}.turns[{turn_index}]",
                persona_id=persona_id,
                pre_disclosed_fact_ids=set(pre_disclosed),
            )
            turn["turn_ordinal"] = turn_ordinal
            turn_ordinal += 1
            normalized_turns.append(turn)
        has_ordered_transition = any(
            first["expected_disclosure"] == "withhold"
            and any(
                later["expected_matched_fact_id"] == first["expected_matched_fact_id"]
                and later["expected_disclosure"] == "disclose"
                for later in normalized_turns[first_index + 1 :]
            )
            for first_index, first in enumerate(normalized_turns)
        )
        if not has_ordered_transition:
            raise QualificationFixtureError(
                f"{location} must test one matched fact withheld then disclosed later"
            )
        transition_personas.add(persona_id)
        normalized.append(
            {
                "chain_id": chain_id,
                "case_id": str(item["case_id"]),
                "persona_id": persona_id,
                "pre_disclosed_fact_ids": pre_disclosed,
                "prior_exchanges": prior_exchanges,
                "turns": normalized_turns,
            }
        )
    if not {"P_CS", "P_CD"}.issubset(transition_personas):
        raise QualificationFixtureError(
            "linked withhold-to-disclose coverage must include P_CS and P_CD"
        )
    return document, normalized


def validate_fixture_references(
    chains: list[dict[str, Any]],
    *,
    cases: dict[str, dict[str, Any]],
    personas: dict[str, dict[str, Any]],
) -> None:
    """Fail before model calls when a fixture label is absent from frozen inputs."""

    from legal_skill_guard.environment.client_response import opening_fact_candidates

    missing_cases = sorted({item["case_id"] for item in chains} - set(cases))
    missing_personas = sorted({item["persona_id"] for item in chains} - set(personas))
    invalid_labels: list[str] = []
    for chain in chains:
        case = cases.get(chain["case_id"])
        if case is None:
            continue
        hidden_ids = {str(fact.get("fact_id")) for fact in case.get("facts", [])}
        opening_ids = {
            str(fact["fact_id"]) for fact in opening_fact_candidates(str(case.get("opening") or ""))
        }
        for fact_id in chain["pre_disclosed_fact_ids"]:
            if fact_id not in hidden_ids:
                invalid_labels.append(f"{chain['chain_id']}:pre_disclosed:{fact_id}")
        for turn_index, turn in enumerate(chain["turns"]):
            fact_id = turn["expected_matched_fact_id"]
            if fact_id is not None and fact_id not in hidden_ids | opening_ids:
                invalid_labels.append(f"{chain['chain_id']}:{turn_index}:{fact_id}")
    if missing_cases or missing_personas or invalid_labels:
        raise QualificationFixtureError(
            "unknown fixture references: "
            f"cases={missing_cases} personas={missing_personas} labels={invalid_labels}"
        )


def _expected_response_kind(
    matched_fact_id: str | None,
    disclosure: Disclosure,
    disclosed_fact_ids: set[str],
) -> str:
    if matched_fact_id is None:
        return "unavailable"
    if matched_fact_id.startswith("O"):
        return "opening_repeat"
    if matched_fact_id in disclosed_fact_ids:
        return "repeated_hidden_fact"
    if disclosure == "withhold":
        return "withheld"
    return "new_hidden_fact"


def _advance_expected_disclosure_state(
    expected_disclosed_fact_ids: set[str],
    expected_matched_fact_id: str | None,
    expected_disclosure: Disclosure,
) -> None:
    """Advance oracle state independently from the model's observed state."""

    if (
        expected_matched_fact_id is not None
        and expected_matched_fact_id.startswith("F")
        and expected_disclosure == "disclose"
    ):
        expected_disclosed_fact_ids.add(expected_matched_fact_id)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the current two-axis client qualification and create one immutable "
            "report under runs/<run-id>/qualifications/client_simulator/."
        )
    )
    # argparse applies the path-component validator before main can construct a
    # model client or issue any request.  An unsafe destination therefore fails
    # closed without consuming qualification calls.
    parser.add_argument("--run-id", required=True, type=safe_component)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate schema and frozen references without model calls or a report",
    )
    parser.add_argument(
        "--base-url",
        help="diagnostic OpenAI-compatible endpoint override (for example a borrowed idle model)",
    )
    parser.add_argument("--model-id", help="diagnostic served-model-name override")
    parser.add_argument("--model-revision", help="diagnostic model revision label override")
    parser.add_argument(
        "--workers",
        type=int,
        help="bounded qualification concurrency override; use 1 on a shared service",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        help="limit a diagnostic qualification to selected fixture case IDs",
    )
    return parser.parse_args()


def write_qualification_artifacts(
    *,
    root: Path,
    run_id: str,
    binding: dict[str, Any],
    report: dict[str, Any],
) -> tuple[Path, Path]:
    """Validate and immutably commit one qualification binding/report pair."""

    required_component_fields = {
        "selector_prompt_sha256",
        "disclosure_prompt_sha256",
        "selector_schema_sha256",
        "disclosure_signals_schema_sha256",
        "fixture_file_sha256",
    }
    required_endpoint_fields = {
        "selector_endpoint_contract",
        "disclosure_endpoint_contract",
    }
    if binding.get("run_id") != run_id or report.get("run_id") != run_id:
        raise ValueError("client qualification run binding mismatch")
    if binding.get("fixture_schema_version") != CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION:
        raise ValueError("client qualification binding uses a legacy fixture schema")
    if report.get("schema_version") != CLIENT_QUALIFICATION_REPORT_SCHEMA_VERSION:
        raise ValueError("client qualification report uses a legacy report schema")
    if not required_component_fields.issubset(binding) or not required_component_fields.issubset(
        report
    ):
        raise ValueError("client qualification is missing explicit prompt/schema/fixture hashes")
    if not required_endpoint_fields.issubset(binding) or not required_endpoint_fields.issubset(
        report
    ):
        raise ValueError("client qualification is missing live endpoint contracts")
    for key in (
        "qualification_protocol",
        "model",
        "model_revision",
        "disclosure_model",
        "disclosure_model_revision",
        "selector_endpoint_contract",
        "disclosure_endpoint_contract",
        "client_simulator_qualification_contract_sha256",
        *sorted(required_component_fields),
    ):
        if report.get(key) != binding.get(key):
            raise ValueError(f"client qualification binding field mismatch: {key}")
    binding_sha256 = canonical_json_sha256(binding)
    if report.get("qualification_binding_sha256") != binding_sha256:
        raise ValueError("client qualification report binding hash mismatch")

    store = RunStore(root / "runs", run_id)
    qualification_root = store.root / "qualifications" / "client_simulator"
    binding_path = qualification_root / "binding.json"
    report_path = qualification_root / "report.json"
    expected_binding_path = str(binding_path.relative_to(root))
    if report.get("qualification_binding_path") != expected_binding_path:
        raise ValueError("client qualification report binding path mismatch")
    RunStore.immutable_json(binding_path, binding)
    RunStore.immutable_json(report_path, report)
    return binding_path, report_path


def main() -> None:
    args = _parse_args()
    roles = yaml.safe_load((ROOT / "configs/models/roles.yaml").read_text(encoding="utf-8"))[
        "roles"
    ]
    selector_role = dict(roles["client_fact_selector"])
    disclosure_role = dict(roles["client_disclosure_classifier"])
    if args.base_url:
        selector_role["base_url"] = args.base_url
    if args.model_id:
        selector_role["model_id"] = args.model_id
    if args.model_revision:
        selector_role["revision"] = args.model_revision
    if args.workers is not None:
        if args.workers < 1:
            raise SystemExit("--workers must be positive")
        selector_role["qualification_workers"] = args.workers
    fixture_path = ROOT / "configs/qualification/client_simulator_cases.json"
    fixture_document, chains = load_qualification_chains(fixture_path)
    if args.case_ids:
        requested = set(args.case_ids)
        known = {item["case_id"] for item in chains}
        unknown = sorted(requested - known)
        if unknown:
            raise SystemExit(f"unknown qualification case IDs: {unknown}")
        chains = [item for item in chains if item["case_id"] in requested]
    raw_personas = json.loads(
        (ROOT / "third_party/DLawBench/config/personas.json").read_text(encoding="utf-8")
    )
    cases = {
        item["id"]: item
        for item in (
            json.loads(line)
            for line in (ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        )
    }
    validate_fixture_references(chains, cases=cases, personas=raw_personas)

    if args.validate_only:
        print(
            json.dumps(
                {
                    "fixture_valid": True,
                    "qualification_executed": False,
                    "run_id": str(args.run_id),
                    "fixture_schema_version": fixture_document["schema_version"],
                    "case_count": len({item["case_id"] for item in chains}),
                    "chain_count": len(chains),
                    "transition_chain_count": sum(len(item["turns"]) > 1 for item in chains),
                    "contrast_count": sum(len(item["turns"]) for item in chains),
                    "client_simulator_qualification_contract_sha256": (
                        client_simulator_qualification_sha256(ROOT, selector_role, disclosure_role)
                    ),
                    **client_simulator_qualification_component_hashes(ROOT),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    model = ChatClient(
        str(selector_role["base_url"]),
        str(selector_role["model_id"]),
        retries=0,
        expected_model_root=ROOT / str(selector_role["local_snapshot"]),
        expected_max_model_len=int(
            roles["semantic_judge"]["runtime_limits"]["max_model_len"]
        ),
    )
    disclosure_model = ChatClient(
        str(disclosure_role["base_url"]),
        str(disclosure_role["model_id"]),
        retries=0,
        expected_model_root=ROOT / str(disclosure_role["local_snapshot"]),
        expected_max_model_len=int(
            roles["lawyer_policy"]["runtime_limits"]["max_model_len"]
        ),
    )
    selector_endpoint_contract = model.readiness()
    disclosure_endpoint_contract = disclosure_model.readiness()
    if not selector_endpoint_contract["ready"] or not disclosure_endpoint_contract["ready"]:
        raise SystemExit(
            "client router or disclosure-classifier service contract does not match: "
            + json.dumps(
                {
                    "selector": selector_endpoint_contract,
                    "disclosure": disclosure_endpoint_contract,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    def qualify_chain(chain: dict[str, Any]) -> list[dict[str, Any]]:
        case = cases[chain["case_id"]]
        persona_id = chain["persona_id"]
        persona = json.loads(json.dumps(raw_personas[persona_id], ensure_ascii=False))
        persona["persona_id"] = persona_id
        simulator = ClientSimulator.from_template_file(
            case_view=case,
            persona=persona,
            model=model,
            disclosure_model=disclosure_model,
            template_path=ROOT / "configs/prompts/client_fact_selector_zh.txt",
            disclosure_template_path=ROOT / "configs/prompts/client_fact_disclosure_zh.txt",
            generation=GenerationConfig(
                temperature=float(selector_role["temperature"]),
                top_p=1.0,
                max_tokens=int(selector_role["max_tokens"]),
                seed=10_000,
                reasoning_effort=selector_role.get("reasoning_effort"),
            ),
            max_selection_attempts=2,
        )
        simulator.disclosed_fact_ids.update(chain["pre_disclosed_fact_ids"])
        expected_disclosed_fact_ids = set(chain["pre_disclosed_fact_ids"])
        simulator.history.extend(
            (item["question"], item["answer"]) for item in chain["prior_exchanges"]
        )
        results: list[dict[str, Any]] = []
        for turn_index, turn in enumerate(chain["turns"]):
            seed = 10_000 + int(turn["turn_ordinal"])
            response, request_sha256 = simulator.respond(
                turn["question"],
                seed,
            )
            observed_matches = list(simulator.last_matched_fact_ids)
            observed_match = observed_matches[0] if len(observed_matches) == 1 else None
            observed_disclosure: str | None = simulator.last_disclosure_decision
            if not observed_matches and simulator.last_response_kind == "unavailable":
                # The current structured schema permits an empty match only with
                # disclose.  Contract fallback is a distinct response kind and is
                # never inferred as a valid disclosure decision.
                observed_disclosure = "disclose"
            expected_match = turn["expected_matched_fact_id"]
            expected_disclosure = turn["expected_disclosure"]
            expected_kind = _expected_response_kind(
                expected_match,
                expected_disclosure,
                expected_disclosed_fact_ids,
            )
            match_passed = observed_match == expected_match and len(observed_matches) <= 1
            disclosure_passed = observed_disclosure == expected_disclosure
            response_kind_passed = simulator.last_response_kind == expected_kind
            results.append(
                {
                    "chain_id": chain["chain_id"],
                    "turn_index": turn_index,
                    "case_id": chain["case_id"],
                    "persona_id": persona_id,
                    "question": turn["question"],
                    "expected_matched_fact_id": expected_match,
                    "observed_matched_fact_id": observed_match,
                    "expected_disclosure": expected_disclosure,
                    "observed_disclosure": observed_disclosure,
                    "expected_response_kind": expected_kind,
                    "observed_response_kind": simulator.last_response_kind,
                    "match_passed": match_passed,
                    "disclosure_passed": disclosure_passed,
                    "response_kind_passed": response_kind_passed,
                    "passed": match_passed and disclosure_passed and response_kind_passed,
                    "opening_reference_ids": list(simulator.last_opening_reference_ids),
                    "route_candidate_fact_id": simulator.last_route_candidate_fact_id,
                    "route_guard_violations": list(
                        simulator.last_route_guard_violations
                    ),
                    "selection_attempts": list(simulator.last_selection_attempts),
                    "disclosure_attempts": list(simulator.last_disclosure_attempts),
                    "rendered_response": response.content,
                    "request_sha256": request_sha256,
                }
            )
            _advance_expected_disclosure_state(
                expected_disclosed_fact_ids,
                expected_match,
                expected_disclosure,
            )
        return results

    with ThreadPoolExecutor(max_workers=int(selector_role["qualification_workers"])) as pool:
        nested_results = list(pool.map(qualify_chain, chains))
    results = [result for chain_results in nested_results for result in chain_results]

    component_hashes = client_simulator_qualification_component_hashes(ROOT)
    contract_sha256 = client_simulator_qualification_sha256(ROOT, selector_role, disclosure_role)
    store = RunStore(ROOT / "runs", str(args.run_id))
    qualification_root = store.root / "qualifications" / "client_simulator"
    binding = {
        "schema_version": 1,
        "run_id": str(args.run_id),
        "qualification_protocol": int(selector_role["qualification_protocol"]),
        "fixture_schema_version": CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION,
        "report_schema_version": CLIENT_QUALIFICATION_REPORT_SCHEMA_VERSION,
        "model": model.model,
        "model_revision": str(selector_role["revision"]),
        "disclosure_model": disclosure_model.model,
        "disclosure_model_revision": str(disclosure_role["revision"]),
        "selector_endpoint_contract": selector_endpoint_contract,
        "disclosure_endpoint_contract": disclosure_endpoint_contract,
        "client_simulator_qualification_contract_sha256": contract_sha256,
        **component_hashes,
    }
    binding_path = qualification_root / "binding.json"
    binding_sha256 = canonical_json_sha256(binding)

    matched = [item for item in results if item["expected_matched_fact_id"] is not None]
    unmatched = [item for item in results if item["expected_matched_fact_id"] is None]
    disclose = [item for item in results if item["expected_disclosure"] == "disclose"]
    withhold = [item for item in results if item["expected_disclosure"] == "withhold"]
    transitions = [item for item in chains if len(item["turns"]) > 1]
    transition_results = [
        item
        for item in results
        if any(item["chain_id"] == chain["chain_id"] for chain in transitions)
    ]
    metrics = {
        "match_accuracy": sum(item["match_passed"] for item in results) / len(results),
        "matched_accuracy": sum(item["match_passed"] for item in matched) / len(matched),
        "unmatched_accuracy": sum(item["match_passed"] for item in unmatched) / len(unmatched),
        "disclosure_accuracy": sum(item["disclosure_passed"] for item in results) / len(results),
        "response_kind_accuracy": sum(item["response_kind_passed"] for item in results)
        / len(results),
        "transition_accuracy": sum(item["passed"] for item in transition_results)
        / len(transition_results),
        "contract_fallback_rate": sum(
            item["observed_response_kind"] == "contract_fallback" for item in results
        )
        / len(results),
    }
    thresholds = {
        key: float(selector_role[key])
        for key in (
            "qualification_min_match_accuracy",
            "qualification_min_matched_accuracy",
            "qualification_min_unmatched_accuracy",
            "qualification_min_disclosure_accuracy",
            "qualification_min_response_kind_accuracy",
            "qualification_min_transition_accuracy",
            "qualification_max_contract_fallback_rate",
        )
    }
    minimum_threshold_names = {
        "match_accuracy": "qualification_min_match_accuracy",
        "matched_accuracy": "qualification_min_matched_accuracy",
        "unmatched_accuracy": "qualification_min_unmatched_accuracy",
        "disclosure_accuracy": "qualification_min_disclosure_accuracy",
        "response_kind_accuracy": "qualification_min_response_kind_accuracy",
        "transition_accuracy": "qualification_min_transition_accuracy",
    }
    threshold_failures = [
        metric
        for metric, threshold_name in minimum_threshold_names.items()
        if metrics[metric] < thresholds[threshold_name]
    ]
    if (
        metrics["contract_fallback_rate"]
        > thresholds["qualification_max_contract_fallback_rate"]
    ):
        threshold_failures.append("contract_fallback_rate")
    report = {
        "schema_version": CLIENT_QUALIFICATION_REPORT_SCHEMA_VERSION,
        "run_id": str(args.run_id),
        "qualification_protocol": int(selector_role["qualification_protocol"]),
        "fixture_schema_version": fixture_document["schema_version"],
        "qualification_binding_path": str(binding_path.relative_to(ROOT)),
        "qualification_binding_sha256": binding_sha256,
        "model": model.model,
        "model_revision": str(selector_role["revision"]),
        "disclosure_model": disclosure_model.model,
        "disclosure_model_revision": str(disclosure_role["revision"]),
        "selector_endpoint_contract": selector_endpoint_contract,
        "disclosure_endpoint_contract": disclosure_endpoint_contract,
        "client_simulator_qualification_contract_sha256": contract_sha256,
        **component_hashes,
        "fixture_canonical_sha256": canonical_json_sha256(fixture_document),
        "case_count": len({item["case_id"] for item in results}),
        "chain_count": len(chains),
        "transition_chain_count": len(transitions),
        "contrast_count": len(results),
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "disclose_count": len(disclose),
        "withhold_count": len(withhold),
        **metrics,
        "thresholds": thresholds,
        "threshold_failures": threshold_failures,
        "passed": not threshold_failures,
        "results": results,
    }
    _, output = write_qualification_artifacts(
        root=ROOT,
        run_id=str(args.run_id),
        binding=binding,
        report=report,
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "passed",
                    "case_count",
                    "chain_count",
                    "contrast_count",
                    "match_accuracy",
                    "matched_accuracy",
                    "unmatched_accuracy",
                    "disclosure_accuracy",
                    "response_kind_accuracy",
                    "transition_accuracy",
                    "contract_fallback_rate",
                    "threshold_failures",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"immutable_report={output.relative_to(ROOT)}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
