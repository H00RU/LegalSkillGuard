"""Past-Gold evidence references expand before inference, never into its answer."""

from __future__ import annotations

import copy
import json

from jsonschema import Draft202012Validator

TEACHER_SYSTEM = (
    "You are the sole existing legal-skill writer. Re-express useful knowledge "
    "from the supplied18 already-seen original TRAIN sources, their original "
    "labels/full evidence sets, actual own public observations and latest "
    "abstract source-program library. This is a finite representation study, "
    "not a fresh independent training run. Historical observations identify "
    "their actual different libraries/tool states/serving formats; do not "
    "pretend they all executed the latest bank. No next-source text/Gold, "
    "other-method answers, outside law, hidden reasoning, tools or new models. "
    "The new runtime record has id,hypothesis_ids,guidance={inspection, "
    "historical_example_refs}. There is NO lexical-query DSL in this format. "
    "The same fallible ordinary candidate tool and full NDA remain visible. "
    "Write transferable source-dependent inspection/decision/evidence procedures "
    "that a weak lawyer can follow: specify the operative actor/action/object, "
    "scope and conditions/negation, how genuine opposing evidence differs from "
    "missing support, and how to keep independently operative and governing "
    "evidence without accepting unrelated candidates. Check boundaries against "
    "all supplied labels, including successes and failures; labels are benchmark "
    "supervision, not universal legal truth. Do not merely list topics or "
    "generic reminders, infer universal absence from unobserved classes, "
    "or force one skill per hypothesis, a fixed count, types or growth. "
    "A historical_example_ref selects one supplied past source/hypothesis. "
    "At serving, it expands to the ORIGINAL past relation plus ALL its Gold "
    "evidence texts, not a teacher-generated substitute or a selected subset. "
    "Select complementary concrete examples that make the instruction usable, "
    "including contrasting source conditions when available. They are excerpts "
    "from past documents, not complete trajectories/current facts or an "
    "automatic verdict rule. No NM references exist: an excerpt cannot prove "
    "whole-document absence. A record may have zero examples if justified. "
    "Every referenced public hypothesis must belong to the record's scope. "
    "The op.source_case_ids must include the original cases of its selected "
    "examples. Case refs remain in training provenance only; runtime receives "
    "the resolved quotes without case IDs or old span numbers. Keep new "
    "inspection text free of case names, parties, dates, original indices, "
    "case fingerprints/answer tables or output-format tricks. Verbatim example "
    "names are historical quotations, never transferable case facts. "
    "The COMPLETE expanded runtime master plus public scope references must "
    "fit4096 native tokens. Measured individual expanded example costs are "
    "supplied; count their full text, not cheap reference IDs. Target below2500 "
    "total: leave substantial space for instructions, record wrappers and "
    "public scope references. Prefer a few information-rich source patterns, "
    "not exhaustive repeated topics/boilerplate. Do not delete evidence from "
    "a selected example or invent a shorter paraphrase to fit. "
    "Return existing atomic CREATE/UPDATE/DELETE/MERGE/NOOP operations against "
    "the empty new-format parent; prior old-format bank is source knowledge, "
    "not an API-compatible parent. Therefore CREATE with empty targets or a "
    "genuine NOOP is valid. A non-delete has one resulting record. Each op "
    "cites supplied source_case_ids and a reusable rationale; metadata stays "
    "outside runtime. No extra critic, score admission, best-bank choice, "
    "fallback or answer repair. All valid output is used, even if it hurts. "
    "The lawyer alone chooses every current original label and evidence set."
)

CANDIDATE_NOTICE = (
    " Ordinary candidate original_span_index resolves to its exact quoted text "
    "in ordinary_candidate_original_text, shared once across questions; scores "
    "and membership are fallible. The entire original NDA and original SPAN "
    "indices remain present. Empty candidates never imply NotMentioned."
)
MEMORY_NOTICE = (
    " published_evidence_anchored_skills contains the complete named memory "
    "once; questions reference applicable IDs, with all content visible together. "
    "An inspection is a fallible reusable procedure. historical_evidence_examples "
    "are labeled excerpts from PREVIOUS TRAIN documents, not evidence about "
    "this NDA, complete past contracts or universal legal rules. Each example "
    "contains all original annotated evidence for that historical judgment, "
    "not necessarily every contextual sentence of its original document. "
    "Use source-pattern analogies only after checking the current full NDA. "
    "Do not transfer quoted names, facts, relations or citations into this "
    "contract. Empty procedures/examples or absent skills do not settle a "
    "relation; all3 original labels remain available. Judge each exact original "
    "hypothesis yourself and cite all necessary and independently operative "
    "current original SPANs, including opposing evidence where appropriate. "
    "Report only supplied IDs actually used; [] is always legal."
)


def example_catalogue(rows, labels, meter):
    catalogue = {}
    for row in rows:
        for h in labels:
            gold = row["annotation_sets"][0]["annotations"][h]
            if gold["choice"] == "NotMentioned":
                continue
            assert gold["spans"] and len(set(gold["spans"])) == len(gold["spans"])
            ref = f"{row['id']}:{h}"
            runtime = {"original_hypothesis_id": h, "historical_annotation": gold["choice"],
                "complete_annotated_evidence_texts": [row["text"][slice(*row["spans"][i])]
                    for i in sorted(gold["spans"])]}
            catalogue[ref] = {"source_case_id": row["id"], "hypothesis_id": h,
                "original_gold": copy.deepcopy(gold), "runtime_example": runtime,
                "expanded_example_native_tokens": meter.token_count(
                    text=json.dumps(runtime, ensure_ascii=False, separators=(",", ":")))}
    return catalogue


def guidance_schema(catalogue):
    return {"type": "object", "additionalProperties": False,
        "required": ["inspection", "historical_example_refs"], "properties": {
            "inspection": {"type": "string", "minLength": 1},
            "historical_example_refs": {"type": "array", "maxItems": 8,
                "items": {"type": "string", "enum": list(catalogue)}}}}


def expanded_library(bank, catalogue, arm):
    assert arm in ("empty", "procedures_only", "examples_only", "joint")
    if arm == "empty":
        return []
    runtime = []
    for skill in bank:
        guidance = skill["guidance"]
        refs = guidance["historical_example_refs"]
        assert len(refs) == len(set(refs))
        examples = []
        for ref in refs:
            record = catalogue[ref]
            assert record["hypothesis_id"] in skill["hypothesis_ids"]
            examples.append(copy.deepcopy(record["runtime_example"]))
        runtime.append({"id": skill["id"], "hypothesis_ids": copy.deepcopy(skill["hypothesis_ids"]),
            "guidance": {"inspection": guidance["inspection"] if arm != "examples_only" else "",
                "historical_evidence_examples": examples if arm != "procedures_only" else []}})
    return runtime


def scoped_output_schema(original, bank, labels):
    schema = copy.deepcopy(original)
    for h in labels:
        ids = [s["id"] for s in bank if h in s["hypothesis_ids"]]
        used = {"type": "array", "items": {"type": "string", "enum": ids}} if ids else {
            "type": "array", "items": {"type": "string"}, "maxItems": 0}
        for branch in schema["properties"][h]["anyOf"]:
            assert list(branch["properties"]) == branch["required"] == ["choice", "spans", "reason", "used_skill_ids"]
            branch["properties"]["used_skill_ids"] = copy.deepcopy(used)
    Draft202012Validator.check_schema(schema)
    return schema
