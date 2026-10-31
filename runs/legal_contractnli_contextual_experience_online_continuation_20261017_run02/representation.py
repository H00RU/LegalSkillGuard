"""Full past-source annotation demonstrations, before the current legal task."""

from __future__ import annotations

import copy
import hashlib
import json

from jsonschema import Draft202012Validator

from legal_skill_guard.task import marked_text

TEACHER_SYSTEM = (
    "You are the sole existing legal-skill writer. Update the exact supplied "
    "current_parent_library from ONLY the already-seen original TRAIN sources, "
    "their original annotations and actual own public observations. The first "
    "packet supplies all32 past cases. Later packets contain the entire current "
    "batch plus complete source cases of every parent-selected demonstration; "
    "unselected older history stays archived, not silently clipped into this "
    "explicit bounded replay packet. Retain unsupported-to-change parent "
    "boundaries rather than rewriting unobserved topics. Historical "
    "banks/tools/encodings differ explicitly; do not pretend all observed answers "
    "used this parent. No other-method answers, future cases/Gold, tools, outside "
    "law or private reasoning. Preserve original17 hypotheses/3 relations/full "
    "original-span evidence and frozen lawyer. This is online method-repair "
    "continuation, not a fresh independent learner. Diagnose visible-but-rejected "
    "evidence and incorrect relation selection as well as missing retrieval. "
    "A correct label with incomplete evidence needs evidence work, not a reversed "
    "verdict. Public reasons are fallible, not faithful internal explanations. "
    "Repair unsupported narrow vetoes: a phrase that was sufficient in a few "
    "positive examples is not thereby necessary. Use the meaning and quantifiers "
    "of the original hypothesis, not required vocabulary or a closed template. "
    "Express opposition to a universal requirement is Contradiction, not simply "
    "NotMentioned; genuinely unresolved propositions remain NotMentioned. "
    "Class definitions, incorporated clauses, equivalent form descriptions, "
    "exceptions and linked conditions can establish a relation indirectly. "
    "Do not exclude clauses by heading/genre or demand a particular surface word. "
    "Do not infer all material must be marked because one alternative must be. "
    "Distinguish original evidence membership from a fragment being sufficient "
    "alone for a relation: an annotated context member does not become a general "
    "positive legal rule. Preserve corpus evidence without inventing universal law. "
    "Write bounded operational reading procedures, not exhaustive legal vetoes, "
    "case lookups or a second final-answer judge. Keep required preambles, linked "
    "definitions and all independently responsive repeated evidence, not an "
    "automatic closure over every background legal premise. TRAIN_GOLD tags "
    "are training metadata, not contract text. Observation strings encoded as "
    "{$past_original_span_text:i} resolve to original SPAN i of that observation's "
    "document_id. {$table_columns:[keys],$table_rows:[[values],...]} encodes "
    "ordered rows with that named header; decoding restores the actual "
    "observation exactly. Native public answer content remains unchanged. "
    "Each guidance still has inspection and historical_example_refs. NOW every "
    "reference case_id:hypothesis_id expands to the FULL original past document "
    "and its selected original annotated answer, including genuine whole-document "
    "NM. These are original annotation demonstrations, NOT claimed successful "
    "native executions; never fabricate a reason or trajectory. Source text is "
    "shared once across all references to one case; answers are shared by public "
    "hypothesis. Full past source context is never clipped to selected fragments. "
    "Actual wrong past answers remain in training feedback, not in runtime "
    "demonstrations as trusted answers. No fixed number, types, mandatory NM "
    "quota, forced growth or requirement to retain all old example references. "
    "Original parent fragment references are valid IDs but now expand to full "
    "case context, which is a real representation change; budget accordingly. "
    "The complete expanded runtime master AND scoped-reference view must fit4096 "
    "existing8B tokens. Per-case full-context costs and per-answer costs are "
    "supplied; each source costs once even across skills. Aim below2800 total, "
    "leaving scope overhead. Select informative complete demonstrations and "
    "concise procedures jointly; more references are not inherently better. "
    "Do not clip, paraphrase, prune after publication, retry or replace a bank "
    "to fit. Current same-text examples are always excluded at inference to "
    "prevent current-answer leakage, including retention; procedures still apply. "
    "Inspection has no case IDs, source indices, parties, dates or case answers. "
    "Use atomic CREATE/UPDATE/DELETE/MERGE/NOOP against the actual parent; "
    "unmentioned records stay unchanged, UPDATE retains ID, no forward targets. "
    "Each resulting skill's example case IDs must appear in its operation's "
    "source_case_ids. Empty operations need a noop reason; edits have null noop. "
    "All structurally valid final edits are used unconditionally. No efficacy "
    "admission, best-bank rollback, new runtime role, fallback or answer repair."
)

CANDIDATE_NOTICE = (
    " Ordinary candidate original_span_index resolves to its exact quoted text "
    "in ordinary_candidate_original_text, shared once across questions. Scores "
    "and membership are fallible; empty candidates never imply NotMentioned. "
    "The complete CURRENT original contract and all original SPAN indices remain."
)
MEMORY_NOTICE = (
    " The historical skills and full past-document demonstrations precede the "
    "CURRENT task. They are fallible reading assistance, not current facts or "
    "automatic verdicts. PAST Hn SPAN i markers and original_annotated_answers "
    "belong only to that complete PAST document; its annotations are original "
    "training supervision, not claimed successful native trajectories. A past "
    "NM is interpretable only together with that full past source. Never transfer "
    "old parties, facts, labels or indices into the CURRENT contract. Read its "
    "entire source, follow definitions and conditions, and choose each original "
    "relation/evidence yourself. Missing a skill or familiar phrase is not proof "
    "of absence. Examples and sufficient clues are not exclusive necessary "
    "templates. All3 labels remain available; [] for used_skill_ids is legal."
)


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def text_identity(text):
    return hashlib.sha256(text.encode()).hexdigest()


def gold_annotated_view(row, labels):
    source = marked_text(row)
    assert "<TRAIN_GOLD>" not in row["text"]
    inserted = []
    gold = row["annotation_sets"][0]["annotations"]
    for i in range(len(row["spans"])):
        members = {h: gold[h]["choice"] for h in labels if i in gold[h]["spans"]}
        if members:
            tag = "<TRAIN_GOLD>" + compact(members) + "</TRAIN_GOLD>"
            source = source.replace(f"<SPAN {i}>", f"<SPAN {i}>" + tag, 1)
            inserted.append(tag)
    recovered = source
    for tag in inserted:
        recovered = recovered.replace(tag, "", 1)
    assert recovered == marked_text(row)
    return source


def pack_observation(observation, row):
    """Only repeated literal full-SPAN strings become reversible source pointers."""
    fragments = [row["text"][slice(*span)] for span in row["spans"]]
    index = {s: i for i, s in reversed(list(enumerate(fragments)))}

    def encode(value):
        if isinstance(value, str) and value in index:
            return {"$past_original_span_text": index[value]}
        if isinstance(value, dict):
            assert set(value) != {"$past_original_span_text"}
            assert set(value) != {"$table_columns", "$table_rows"}
            return {k: encode(v) for k, v in value.items()}
        if isinstance(value, list):
            if len(value) > 1 and all(isinstance(v, dict) for v in value):
                columns = list(value[0])
                if columns and all(list(v) == columns for v in value):
                    return {"$table_columns": columns,
                        "$table_rows": [[encode(v[k]) for k in columns] for v in value]}
            return [encode(v) for v in value]
        return value

    def decode(value):
        if isinstance(value, dict):
            if set(value) == {"$past_original_span_text"}:
                return fragments[value["$past_original_span_text"]]
            if set(value) == {"$table_columns", "$table_rows"}:
                return [{k: decode(v) for k, v in zip(value["$table_columns"], row, strict=True)}
                    for row in value["$table_rows"]]
            return {k: decode(v) for k, v in value.items()}
        if isinstance(value, list):
            return [decode(v) for v in value]
        return value

    packed = encode(observation)
    assert compact(decode(packed)) == compact(observation)
    return packed


def make_catalogue(rows, labels, observations, meter):
    parsed = {o["document_id"]: json.loads(o["actual_native_response"]["content"]) for o in observations}
    assert set(parsed) == {r["id"] for r in rows} and len(parsed) == len(observations)
    documents, references = {}, {}
    for row in rows:
        source = {k: copy.deepcopy(row[k]) for k in ("id", "text", "spans")}
        gold = row["annotation_sets"][0]["annotations"]
        documents[str(row["id"])] = {
            "source": source, "original_annotations": copy.deepcopy(gold),
            "text_sha256": text_identity(row["text"]),
            "whole_marked_source_native_tokens": meter.token_count(text=marked_text(source))}
        for h in labels:
            g, p = gold[h], parsed[row["id"]][h]
            gs, ps = set(g["spans"]), set(p["spans"])
            references[f"{row['id']}:{h}"] = {
                "source_case_id": row["id"], "hypothesis_id": h,
                "original_relation": g["choice"], "actual_label_correct": g["choice"] == p["choice"],
                "missing_original_Gold_members": sorted(gs - ps),
                "extra_selected_members": sorted(ps - gs),
                "original_annotated_answer_native_tokens": meter.token_count(text=compact(g))}
    return {"documents": documents, "references": references}


def guidance_schema(catalogue):
    return {"type": "object", "additionalProperties": False,
        "required": ["inspection", "historical_example_refs"], "properties": {
            "inspection": {"type": "string", "minLength": 1},
            "historical_example_refs": {"type": "array", "maxItems": 8,
                "items": {"type": "string", "enum": list(catalogue["references"])}}}}


def expanded_memory(bank, catalogue, current_text, arm):
    assert arm in ("empty", "joint")
    if arm == "empty":
        return {"published_contextual_skills": [], "past_context_complete_demonstrations": {}}, []
    current_hash = text_identity(current_text) if current_text is not None else None
    active, excluded = {}, []
    for skill in bank:
        refs = skill["guidance"]["historical_example_refs"]
        assert len(refs) == len(set(refs))
        for ref in refs:
            item = catalogue["references"][ref]
            assert item["hypothesis_id"] in skill["hypothesis_ids"]
            doc = str(item["source_case_id"])
            if catalogue["documents"][doc]["text_sha256"] == current_hash:
                excluded.append(ref)
            else:
                active.setdefault(doc, set()).add(item["hypothesis_id"])
    names = {doc: f"H{i + 1}" for i, doc in enumerate(sorted(active, key=int))}
    demonstrations = {}
    for doc, name in names.items():
        past = catalogue["documents"][doc]
        source = marked_text(past["source"])
        count = len(past["source"]["spans"])
        for i in range(count):
            source = source.replace(f"<SPAN {i}>", f"<PAST {name} SPAN {i}>")
            source = source.replace(f"</SPAN {i}>", f"</PAST {name} SPAN {i}>")
        recovered = source.replace(f"<PAST {name} SPAN ", "<SPAN ").replace(f"</PAST {name} SPAN ", "</SPAN ")
        assert recovered == marked_text(past["source"])
        demonstrations[name] = {"full_original_past_contract_with_local_span_markers": source,
            "original_annotated_answers": {h: copy.deepcopy(past["original_annotations"][h])
                for h in sorted(active[doc])}, "annotations_not_claimed_successful_native_executions": True}
    cards = []
    for skill in bank:
        refs = []
        for ref in skill["guidance"]["historical_example_refs"]:
            item = catalogue["references"][ref]
            doc = str(item["source_case_id"])
            if doc in names:
                refs.append({"past_case": names[doc], "hypothesis_id": item["hypothesis_id"]})
        cards.append({"id": skill["id"], "hypothesis_ids": copy.deepcopy(skill["hypothesis_ids"]),
            "guidance": {"inspection": skill["guidance"]["inspection"], "past_demonstration_refs": refs}})
    return {"published_contextual_skills": cards, "past_context_complete_demonstrations": demonstrations}, excluded


def scoped_output_schema(original, cards, labels):
    schema = copy.deepcopy(original)
    for h in labels:
        ids = [s["id"] for s in cards if h in s["hypothesis_ids"]]
        used = {"type": "array", "items": {"type": "string", "enum": ids}} if ids else {
            "type": "array", "items": {"type": "string"}, "maxItems": 0}
        for branch in schema["properties"][h]["anyOf"]:
            assert list(branch["properties"]) == branch["required"] == ["choice", "spans", "reason", "used_skill_ids"]
            branch["properties"]["used_skill_ids"] = copy.deepcopy(used)
    Draft202012Validator.check_schema(schema)
    return schema
