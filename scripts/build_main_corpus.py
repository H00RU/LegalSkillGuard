"""Validate the formally authored annotations and materialize the main corpus.

The authoring YAML files are deliberately human-readable.  This builder attaches
source metadata, verifies every evidence quote, computes stable hashes, and refuses
to publish a partially reviewed corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/source_pool/spc_typical_cases.jsonl"
SUPPLEMENTAL_SOURCES = (
    ROOT / "data/source_pool/spc_reference_cases.jsonl",
    ROOT / "data/source_pool/spc_labor_consumer_cases.jsonl",
    ROOT / "data/source_pool/spc_procedure_insurance_cases.jsonl",
    ROOT / "data/source_pool/spc_expansion_128_cases.jsonl",
)
AUTHORING = ROOT / "data/annotations/main_corpus"
CORE = ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl"
PROVENANCE = ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl"
MANIFEST = ROOT / "data/manifests/main_corpus_selection.json"
REPORT = ROOT / "reports/artifacts/main_corpus_quality.json"

FINAL_OUTCOME_TERMS = (
    "法院判决",
    "法院认定",
    "法院最终",
    "最终判决",
    "判处有期徒刑",
    "判处死刑",
    "驳回诉讼请求",
    "支持了我的诉求",
)
BELIEF_META_TERMS = ("来源案件", "裁判时点", "核验现行法", "请律师", "需要律师")
GENERIC_MEMO_TERMS = ("来源案件", "来源所载", "裁判时点", "核验现行法")
COURT_RECORD_META_TERMS = (
    "与客户",
    "与公司掌握情况",
    "与来源一致",
    "来源记载",
    "来源确认",
    "来源认定",
    "来源认为",
    "来源所载",
    "上述",
    "该判断",
    "该证据缺口",
    "三类问题",
)
COURT_RECORD_META_ENDING = re.compile(r"(?:明确|一致)。?$")
SOURCE_HEADING_OVERRIDES = {
    # The 2021 personality-rights page repeats a shortened mobile heading later
    # in the HTML.  Keep the complete numbered heading in published provenance.
    "8bbb6b58b0e25e2f8029bf4190fe7bfcc7cf9094bf8b183af242e7efef18d667": (
        "金融机构长期怠于核查更正债务人信用记录可构成名誉侵权"
        "——债务人诉金融机构名誉侵权案"
    ),
}
VISIBLE_NUMERIC_ANCHOR = re.compile(
    r"\d+(?:\.\d+)?(?:号|%|％|万元|元|年|个月|月|日|小时|次|份|名|家|人|公里|亩|吨)?"
)


def canonical_hash(value: dict[str, Any]) -> str:
    payload = dict(value)
    payload.pop("sha256", None)
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_source() -> list[dict[str, Any]]:
    paths = [SOURCE]
    paths.extend(path for path in SUPPLEMENTAL_SOURCES if path.is_file())
    return [
        json.loads(line)
        for path in paths
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def load_annotations() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(AUTHORING.glob("batch_*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("annotations"), list):
            raise SystemExit(f"{path}: expected an annotations list")
        for item in payload["annotations"]:
            item["_authoring_file"] = str(path.relative_to(ROOT))
            records.append(item)
    return records


def normalized_gap(left: str, right: str) -> bool:
    """Only catch identical/almost-identical pairs mislabeled as disputed.

    Full semantic gap validation remains an explicit editorial checklist.
    """

    def clean(text: str) -> str:
        return re.sub(r"[，。；：、！？\s‘’“”\"']", "", text)

    a, b = clean(left), clean(right)
    return a == b or (min(len(a), len(b)) >= 12 and (a in b or b in a))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    sources = load_source()
    annotations = load_annotations()
    errors: list[str] = []
    warnings: list[str] = []
    cores: list[dict[str, Any]] = []
    provenances: list[dict[str, Any]] = []
    selection: list[dict[str, Any]] = []

    for source_index, origin in enumerate(sources, 1):
        stored_case_hash = origin.get("source_case_sha256")
        case_payload = dict(origin)
        case_payload.pop("source_case_sha256", None)
        recomputed_case_hash = hashlib.sha256(
            json.dumps(case_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if stored_case_hash != recomputed_case_hash:
            errors.append(f"source line {source_index}: source case hash mismatch")
        raw_page = ROOT / "data/source_pool/raw_pages" / f"{origin.get('source_id')}.html"
        if not raw_page.is_file():
            errors.append(f"source line {source_index}: frozen raw page is missing")
        elif hashlib.sha256(raw_page.read_bytes()).hexdigest() != origin.get(
            "source_page_sha256"
        ):
            errors.append(f"source line {source_index}: frozen page hash mismatch")

    ids = [item.get("id") for item in annotations]
    if len(ids) != len(set(ids)):
        errors.append("duplicate annotation ids")
    source_lines = [item.get("source_line") for item in annotations]
    if len(source_lines) != len(set(source_lines)):
        errors.append("a source case was annotated more than once")

    selected_pages: set[str] = set()
    for item in annotations:
        source_line = item.get("source_line")
        if isinstance(source_line, int) and 1 <= source_line <= len(sources):
            page_sha = str(sources[source_line - 1]["source_page_sha256"])
            selected_pages.add(page_sha)

    required_checks = {
        "source_read_in_full",
        "single_client_role",
        "pre_outcome_timeline",
        "opening_has_no_outcome",
        "opening_information_boundary_checked",
        "beliefs_are_natural",
        "gap_labels_semantically_checked",
        "inquiries_are_answerable",
        "memo_points_are_substantive",
    }

    for item in annotations:
        case_id = item.get("id", "<missing-id>")
        source_line = item.get("source_line")
        if not isinstance(source_line, int) or not 1 <= source_line <= len(sources):
            errors.append(f"{case_id}: invalid source_line {source_line!r}")
            continue
        origin = sources[source_line - 1]
        if item.get("source_case_sha256") != origin["source_case_sha256"]:
            errors.append(f"{case_id}: source hash mismatch")
        if item.get("split") != "train":
            errors.append(f"{case_id}: the 128-case corpus permits only the train split")
        if not item.get("client_role") or not item.get("consultation_stage"):
            errors.append(f"{case_id}: missing role or consultation stage")
        opening = item.get("opening", "")
        if not 24 <= len(opening) <= 180:
            errors.append(f"{case_id}: opening length {len(opening)} outside 24..180")
        for term in FINAL_OUTCOME_TERMS:
            if term in opening:
                errors.append(f"{case_id}: opening leaks final outcome term {term!r}")

        facts = item.get("facts", [])
        if not 6 <= len(facts) <= 10:
            errors.append(f"{case_id}: expected 6..10 facts, got {len(facts)}")
        gaps = Counter(fact.get("gap_type") for fact in facts)
        if gaps["disputed"] < 2 or gaps["undisputed"] < 2:
            errors.append(f"{case_id}: insufficient gap diversity {dict(gaps)}")

        core_facts: list[dict[str, str]] = []
        support: list[dict[str, Any]] = []
        for index, fact in enumerate(facts, 1):
            fact_id = f"F{index}"
            belief = fact.get("client_belief", "")
            record = fact.get("court_record", "")
            gap = fact.get("gap_type")
            if gap not in {"disputed", "undisputed"}:
                errors.append(f"{case_id}/{fact_id}: invalid gap_type")
            if not belief or not record:
                errors.append(f"{case_id}/{fact_id}: empty belief or record")
            if belief.endswith(("？", "?")):
                errors.append(f"{case_id}/{fact_id}: client belief is a question")
            for term in BELIEF_META_TERMS:
                if term in belief:
                    errors.append(f"{case_id}/{fact_id}: belief contains meta term {term!r}")
            for term in COURT_RECORD_META_TERMS:
                if term in record:
                    errors.append(
                        f"{case_id}/{fact_id}: court record contains non-self-contained "
                        f"annotation term {term!r}"
                    )
            if COURT_RECORD_META_ENDING.search(record):
                errors.append(
                    f"{case_id}/{fact_id}: court record ends in an empty "
                    "'clear/consistent' shorthand"
                )
            if gap == "disputed" and normalized_gap(belief, record):
                errors.append(f"{case_id}/{fact_id}: disputed pair is textually aligned")
            evidence = fact.get("evidence", [])
            if not evidence:
                errors.append(f"{case_id}/{fact_id}: missing evidence")
            for quote in evidence:
                section = quote.get("section")
                text = quote.get("quote", "")
                if section not in {"basic_facts", "adjudication"}:
                    errors.append(f"{case_id}/{fact_id}: invalid evidence section")
                elif text not in origin[section]:
                    errors.append(f"{case_id}/{fact_id}: non-verbatim evidence quote {text!r}")
            core_facts.append(
                {
                    "fact_id": fact_id,
                    "client_belief": belief,
                    "court_record": record,
                    "gap_type": gap,
                }
            )
            support.append({"fact_id": fact_id, "quotes": evidence})

        inquiries = item.get("expected_inquiries", [])
        memos = item.get("memo_expectations", [])
        if not 5 <= len(inquiries) <= 8:
            errors.append(f"{case_id}: expected 5..8 inquiries, got {len(inquiries)}")
        if not 5 <= len(memos) <= 7:
            errors.append(f"{case_id}: expected 5..7 memo points, got {len(memos)}")
        if any(not question.endswith(("。", "？", "?")) for question in inquiries):
            warnings.append(f"{case_id}: inquiry punctuation is inconsistent")
        for memo in memos:
            for term in GENERIC_MEMO_TERMS:
                if term in memo:
                    errors.append(f"{case_id}: memo contains generic boilerplate {term!r}")
        lawyer_visible_text = (
            opening + "\n" + "\n".join(str(fact.get("client_belief", "")) for fact in facts)
        )
        for criterion_type, criteria in (
            ("inquiry", inquiries),
            ("memo", memos),
        ):
            for criterion in criteria:
                hidden_anchors = sorted(
                    {
                        anchor
                        for anchor in VISIBLE_NUMERIC_ANCHOR.findall(criterion)
                        if anchor not in lawyer_visible_text
                    }
                )
                if hidden_anchors:
                    errors.append(
                        f"{case_id}: {criterion_type} exposes numeric detail absent from "
                        f"lawyer-visible case view: {hidden_anchors}"
                    )

        review = item.get("editorial_review", {})
        missing = sorted(required_checks - {key for key, value in review.items() if value is True})
        if missing:
            errors.append(f"{case_id}: editorial review incomplete: {missing}")
        note = item.get("editorial_note", "")
        if len(note) < 20:
            errors.append(f"{case_id}: editorial note is too short")

        core = {
            "id": case_id,
            "jurisdiction": "CN",
            "language": "zh",
            "opening": opening,
            "facts": core_facts,
            "evaluation_criteria": {
                "expected_inquiries": inquiries,
                "memo_expectations": memos,
            },
        }
        core["sha256"] = canonical_hash(core)
        cores.append(core)
        provenances.append(
            {
                "id": case_id,
                "split": item["split"],
                "source": {
                    "publisher": origin["publisher"],
                    "url": origin["source_url"],
                    "page_title": origin["source_page_title"],
                    "published_at": origin["source_published_at"],
                    "retrieved_at": origin["retrieved_at"],
                    "page_sha256": origin["source_page_sha256"],
                    "source_id": origin["source_id"],
                    "case_index": origin["source_case_index"],
                    "case_heading": SOURCE_HEADING_OVERRIDES.get(
                        origin["source_case_sha256"], origin["source_case_heading"]
                    ),
                    "case_sha256": origin["source_case_sha256"],
                    "structure": origin["source_structure"],
                },
                "annotation": {
                    "legal_domain": item["legal_domain"],
                    "client_role": item["client_role"],
                    "consultation_stage": item["consultation_stage"],
                    "fact_support": support,
                    "editorial_note": note,
                    "editorial_review": review,
                },
                "annotation_pipeline": {
                    "authoring_model": "gpt-5.6-sol",
                    "reasoning_effort": "high",
                    "runtime": "current_interactive_codex_session",
                    "identity_basis": "user_selected_ui_model",
                    "prior_rejected_draft_used_as_annotation_input": False,
                    "prior_rejected_draft_authoring_model": "gpt-5.4-mini",
                    "source_level_reconstruction": True,
                },
                "label_status": "source_grounded_ai_authored_and_casewise_semantic_reviewed",
                "expert_validated": False,
                "core_sha256": core["sha256"],
                "authoring_file": item["_authoring_file"],
            }
        )
        selection.append(
            {
                "id": case_id,
                "source_line": source_line,
                "source_case_sha256": origin["source_case_sha256"],
                "source_id": origin["source_id"],
                "domain": item["legal_domain"],
                "split": item["split"],
                "admission_reason": item.get("admission_reason", ""),
            }
        )

    if not args.allow_partial and len(annotations) != 128:
        errors.append(f"formal build requires exactly 128 cases, found {len(annotations)}")
    if errors:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "cases_seen": len(annotations),
                    "errors": errors,
                    "warnings": warnings,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        raise SystemExit("main corpus validation failed:\n" + "\n".join(errors[:40]))

    cores.sort(key=lambda row: row["id"])
    provenances.sort(key=lambda row: row["id"])
    selection.sort(key=lambda row: row["id"])
    CORE.parent.mkdir(parents=True, exist_ok=True)
    CORE.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in cores),
        encoding="utf-8",
    )
    PROVENANCE.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in provenances),
        encoding="utf-8",
    )
    MANIFEST.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "corpus_id": "legal_skill_guard_dlawbench_style_cn",
                "selection_policy": (
                    "casewise_admission_under_docs/data/main_corpus_build_protocol.md"
                ),
                "records": selection,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    stats = {
        "status": "passed",
        "cases": len(cores),
        "source_pool_cases": len(sources),
        "selected_source_pages": len(selected_pages),
        "splits": dict(sorted(Counter(row["split"] for row in provenances).items())),
        "domains": dict(
            sorted(Counter(row["annotation"]["legal_domain"] for row in provenances).items())
        ),
        "facts": sum(len(row["facts"]) for row in cores),
        "disputed": sum(fact["gap_type"] == "disputed" for row in cores for fact in row["facts"]),
        "undisputed": sum(
            fact["gap_type"] == "undisputed" for row in cores for fact in row["facts"]
        ),
        "inquiries": sum(len(row["evaluation_criteria"]["expected_inquiries"]) for row in cores),
        "memo_expectations": sum(
            len(row["evaluation_criteria"]["memo_expectations"]) for row in cores
        ),
        "warnings": warnings,
        "core_sha256": hashlib.sha256(CORE.read_bytes()).hexdigest(),
        "provenance_sha256": hashlib.sha256(PROVENANCE.read_bytes()).hexdigest(),
    }
    REPORT.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
