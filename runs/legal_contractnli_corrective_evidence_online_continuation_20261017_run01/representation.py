"""Past-Gold evidence references expand before inference, never into its answer."""

from __future__ import annotations

import copy
import json

from jsonschema import Draft202012Validator

TEACHER_SYSTEM = (
    "You are the sole existing legal-skill writer. Update current_parent_library "
    "from ONLY the supplied24 already-seen original TRAIN sources/Gold and actual "
    "own public observations. The newest6 observations executed this actual "
    "parent; older observations explicitly used different banks/tools/formats. "
    "No other-method answers, future source/Gold, outside law, private reasoning "
    "or tools. Preserve the legal NLI task and original complete evidence target. "
    "This is an explicit one-step online representation repair, not an independent "
    "fresh training repeat. Use actual component feedback: label-correct omissions "
    "need evidence repair, not a reversed verdict; unrelated citations need "
    "rejection, not a generic positive pattern. Identify unsupported exclusions "
    "and generalizations that conflict with supplied annotated evidence. "
    "TRAIN_GOLD tags are annotation metadata, never contract text. They preserve "
    "all source bytes and original indices and directly identify annotated members. "
    "The benchmark requires concise interpretable responsive fragments and all "
    "independently repeated evidence, not an unconditional closure over every "
    "background legal premise. Follow actual examples of evidence granularity. "
    "Do not delete an observed class of Gold evidence merely because an ideal "
    "legal taxonomy would exclude it. Labels/membership are corpus supervision, "
    "not universal law; write reusable bounded procedures rather than case lookup. "
    "Each guidance has inspection and historical_example_refs. A reference now "
    "expands to the ACTUAL past selected evidence versus ORIGINAL annotated "
    "evidence, with each union fragment quoted once and named observed_evidence/"
    "annotated_evidence booleans. Non-NM examples show the actual past relation "
    "and its original corrected relation. A past NM false-positive example shows "
    "local evidence rejection only: both relation fields are null, because a "
    "fragment cannot prove whole-document absence. Do not derive current NM from "
    "a negative example, missing skill, empty query, or absent positive pattern. "
    "Historical examples are not complete past documents/private reasoning, "
    "automatic legal rules or evidence about the next contract. Preserve all "
    "Gold fragments and actual selected fragments of each chosen reference; "
    "no shortened fabricated paraphrases. Select informative missing-evidence, "
    "overcitation and wrong-relation contrasts, including successes as useful; "
    "do not fill the budget with only cheap canonical positives. No fixed count, "
    "topic classes, coverage quotas or forced growth. Scope each procedure "
    "precisely and reject unrelated source without treating lexical overlap as "
    "support. Inspection must contain no case IDs, source indices, parties, dates "
    "or case-answer tables. Historical quoted names stay verbatim, not current "
    "facts. References/case IDs and member feedback stay in training provenance. "
    "The complete expanded runtime master AND one-copy scoped view must fit4096 "
    "native tokens. Current actual counts and per-example costs are supplied; "
    "count real quotes, NOT cheap reference IDs. Aim below2800 total, leaving "
    "space for scope references. Use justified UPDATE/DELETE/MERGE/CREATE or "
    "NOOP against the exact parent. Unmentioned records remain unchanged, UPDATE "
    "keeps ID; no forward references. Each non-delete resulting record's selected "
    "example cases must be included in op.source_case_ids. No performance gate, "
    "best-bank choice, retries, new critic, fallback or current-answer repair. "
    "All structurally valid final edits are used unconditionally; lawyer alone "
    "chooses every future original label and full original-span evidence set."
)

CANDIDATE_NOTICE = (
    " Ordinary candidate original_span_index resolves to its exact quoted text "
    "in ordinary_candidate_original_text, shared once across questions; scores "
    "and membership are fallible. The entire original NDA and original SPAN "
    "indices remain present. Empty candidates never imply NotMentioned."
)
MEMORY_NOTICE = (
    " published_evidence_anchored_skills is the full named memory once, with "
    "public-hypothesis ID references; all content is visible together. "
    "An inspection is fallible. historical_evidence_examples are PREVIOUS TRAIN "
    "correction examples, not this NDA's facts, proof, citations or final labels. "
    "In evidence_comparison each quoted fragment has observed_evidence (the "
    "past lawyer selected it) and annotated_evidence (original annotation "
    "selected it). Learn both missed annotated fragments and unannotated "
    "overcitations; observed is not a trusted answer. Non-null historical_annotation "
    "is the past document's original corrected relation, alongside the actual "
    "observed_original_relation. Null relations mean only local evidence "
    "rejection is illustrated, NOT proof of whole-document NotMentioned. "
    "Do not transfer names, facts, relations or citations from old examples "
    "into this NDA. Check the complete CURRENT NDA yourself for every exact "
    "original hypothesis, including opposing evidence. Missing skills or "
    "missing positive patterns never settle a relation. Cite concise readable "
    "current fragments, preserving needed subjects/list introductions and all "
    "independently responsive repeated evidence; do not mechanically add all "
    "background legal premises. All3 original labels remain available. "
    "Report only supplied IDs actually used; [] is always legal."
)


def gold_annotated_view(row, labels, original_marked):
    assert "<TRAIN_GOLD>" not in row["text"]
    view = original_marked
    inserted = []
    gold = row["annotation_sets"][0]["annotations"]
    for i in range(len(row["spans"])):
        members = {h: gold[h]["choice"] for h in labels if i in gold[h]["spans"]}
        if members:
            marker = f"<SPAN {i}>"
            assert view.count(marker) == 1
            tag = "<TRAIN_GOLD>" + json.dumps(members, ensure_ascii=False, separators=(",", ":")) + "</TRAIN_GOLD>"
            view = view.replace(marker, marker + tag, 1)
            inserted.append(tag)
    restored = view
    for tag in inserted:
        restored = restored.replace(tag, "", 1)
    assert restored == original_marked
    return view


def example_catalogue(rows, labels, meter, observations):
    parsed = {o["document_id"]: json.loads(o["actual_native_response"]["content"]) for o in observations}
    assert len(parsed) == len(observations) == len(rows)
    catalogue = {}
    for row in rows:
        for h in labels:
            gold = row["annotation_sets"][0]["annotations"][h]
            observed = parsed[row["id"]][h]
            gs, ps = set(gold["spans"]), set(observed["spans"])
            nn = gold["choice"] != "NotMentioned"
            assert bool(gs) == nn
            if not nn and not ps:
                continue
            indices = sorted(gs | ps)
            runtime = {
                "original_hypothesis_id": h,
                "observed_original_relation": observed["choice"] if nn else None,
                "historical_annotation": gold["choice"] if nn else None,
                "evidence_comparison": [
                    {"text": row["text"][slice(*row["spans"][i])],
                        "observed_evidence": i in ps, "annotated_evidence": i in gs}
                    for i in indices],
            }
            assert [v["text"] for v in runtime["evidence_comparison"] if v["annotated_evidence"]] == [
                row["text"][slice(*row["spans"][i])] for i in sorted(gs)]
            catalogue[f"{row['id']}:{h}"] = {
                "source_case_id": row["id"], "hypothesis_id": h,
                "original_gold": copy.deepcopy(gold),
                "actual_observed_public_answer": copy.deepcopy(observed),
                "component_feedback": {
                    "label_correct": gold["choice"] == observed["choice"],
                    "missing_original_Gold_members": sorted(gs - ps),
                    "extra_unannotated_selected_members": sorted(ps - gs),
                    "selected_union_original_indices": indices,
                    "local_negative_only_without_whole_document_relation": not nn},
                "runtime_example": runtime,
                "expanded_example_native_tokens": meter.token_count(
                    text=json.dumps(runtime, ensure_ascii=False, separators=(",", ":"))),
            }
    return catalogue


def guidance_schema(catalogue):
    return {"type": "object", "additionalProperties": False,
        "required": ["inspection", "historical_example_refs"], "properties": {
            "inspection": {"type": "string", "minLength": 1},
            "historical_example_refs": {"type": "array", "maxItems": 8,
                "items": {"type": "string", "enum": list(catalogue)}}}}


def expanded_library(bank, catalogue, arm):
    assert arm in ("empty", "joint")
    if arm == "empty":
        return []
    runtime = []
    for skill in bank:
        refs = skill["guidance"]["historical_example_refs"]
        assert len(refs) == len(set(refs))
        examples = []
        for ref in refs:
            item = catalogue[ref]
            assert item["hypothesis_id"] in skill["hypothesis_ids"]
            examples.append(copy.deepcopy(item["runtime_example"]))
        runtime.append({
            "id": skill["id"], "hypothesis_ids": copy.deepcopy(skill["hypothesis_ids"]),
            "guidance": {"inspection": skill["guidance"]["inspection"],
                "historical_evidence_examples": examples}})
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
