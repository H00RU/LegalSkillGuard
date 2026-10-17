"""Source-member skill contract for fresh online learning, not a run-specific probe.

Inference is the tested query/role/criterion interface. Teacher sources are printed
once with the same original markers; exact inverse checks preserve text/offsets.
No host legal verdict, admission, citation union, answer repair or extra LLM.
"""

from __future__ import annotations

import copy
import json
import re

from jsonschema import validate

from legal_skill_guard.task import marked_text

from .acquisition import GUIDANCE_SCHEMA, TEACHER
from .packing import expand, keyed, table
from .publication import skill_record_schema

EDIT_GUIDANCE = copy.deepcopy(GUIDANCE_SCHEMA)
EDIT_GUIDANCE["required"].append("evidence_criterion")
EDIT_GUIDANCE["properties"]["evidence_criterion"] = {
    "anyOf": [{"type": "string", "minLength": 1, "maxLength": 600}, {"type": "null"}],
}
STORED_GUIDANCE = {"anyOf": [copy.deepcopy(GUIDANCE_SCHEMA), EDIT_GUIDANCE]}
OLD_NOTICE = "No skill code, identity, scope-control map, query counts or teacher advice is supplied."
NEW_NOTICE = (
    "No skill identities, query counts or scope-control map are supplied. Optional "
    "evidence_selection_criteria are fallible learned inspection procedures for that "
    "hypothesis, never contract facts, label verdicts or mandatory citations. Literal "
    "access roles describe how a location was reached, not whether it is evidence."
)
MEMBER_COLUMNS = ["original_span_index", "original_member", "actually_cited", "ordinary_candidate",
    "literal_match", "explicit_neighbour", "possible_list_preamble"]
SPAN = re.compile(r"<SPAN (?P<index>\d+)>(?P<text>.*?)</SPAN (?P=index)>", re.DOTALL)


def writer_system():
    replacements = {
        "The lawyer receives source locations only, NEVER your legal guidance, examples or rationale.":
        "The lawyer receives source locations, factual access roles and published evidence_criterion, not examples or audit rationale.",
        "Runtime skill=id,hypothesis_ids,guidance.source_queries ONLY.":
        "Runtime skill=id,hypothesis_ids,guidance.source_queries with evidence_criterion. Every newly emitted CREATE/UPDATE/MERGE skill requires a concise string or deliberate null; untouched old records stay verbatim.",
        "No inspection text, examples, labels, case IDs, parties, dates, source indices, fingerprints or answer lookup tables.":
        "No case examples, label verdicts, case IDs, parties, dates, source indices, fingerprints or answer lookup tables.",
        "aim<=2200 master to leave correction room.":
        "aim<=3100 master to leave criterion and scope-projection room.",
    }
    result = TEACHER
    for before, after in replacements.items():
        assert result.count(before) == 1
        result = result.replace(before, after)
    return result + (
        " The observation window contains exactly the latest actual current-parent "
        "canonical own answer for EACH supplied seen TRAIN source, selected by version "
        "and chronology, never correctness. Older observations remain archived and "
        "have already taught earlier banks. All supplied sources, Gold and successes/"
        "failures remain. Complete original contracts are printed ONCE with original "
        "<SPAN i> markers; source IDs and offsets are exactly recoverable. In "
        "member_contrasts_by_hypothesis, zip member rows with member_columns and "
        "resolve their exact text in that case's full marked source. No member, "
        "original text, annotation or citation is dropped. original_member=false "
        "means unannotated, not an independent semantic negative; null means "
        "membership is undefined for original NM. Do not invent corrected Gold. "
        "Distil concise transferable member-selection criteria: directly responsive "
        "clauses, necessary governing language and unrelated nearby obligations. "
        "Apply them to ordinary and extra leads. Do not encode E/C/NM sufficient-"
        "condition verdicts, repeat generic task instructions, require whole read "
        "windows or force criteria/growth. Aim about30 words per criterion and "
        "<=3100 master tokens within4096 master/scope/criterion-projection limits. "
        "The actor receives literal-match/neighbour/preamble facts, not evidence "
        "labels; observations preserve what that actor actually saw. Your rationale "
        "is NOT served: any claimed learned criterion must appear in the actual "
        "evidence_criterion field. Explicit null intentionally publishes no criterion. "
        "No extra tools, critic, semantic admission, best-bank choice, citation "
        "union or answer repair. A valid NOOP or null criterion is normal online "
        "learning, not a reason to retry until content appears."
    )


WRITER = writer_system()


def criterion_projection(bank, labels):
    return {h: [s["guidance"]["evidence_criterion"] for s in bank
        if h in s["hypothesis_ids"] and s["guidance"].get("evidence_criterion") is not None] for h in labels}


def access_roles(bank, executions, hypothesis):
    return {role: {i for s in bank if hypothesis in s["hypothesis_ids"]
        for event in executions[s["id"]] for i in event[role]}
        for role in ("matched", "neighbour", "preamble")}


def actor_messages(canonical_messages, bank, labels, trace, *, include_criterion=True):
    for s in bank:
        validate(s, skill_record_schema(labels, guidance_schema=STORED_GUIDANCE))
    messages = copy.deepcopy(canonical_messages)
    assert messages[0]["content"].count(OLD_NOTICE) == 1
    messages[0]["content"] = messages[0]["content"].replace(OLD_NOTICE, NEW_NOTICE)
    body = json.loads(messages[1]["content"])
    projection = criterion_projection(bank, labels)
    for h in labels:
        roles = access_roles(bank, trace["actual_source_executions"], h)
        for record in body["hypotheses"][h]["additional_source_read_indices"]:
            i = record["original_span_index"]
            record.update(literal_match=i in roles["matched"], explicit_neighbour=i in roles["neighbour"],
                possible_list_preamble=i in roles["preamble"])
        if include_criterion and projection[h]:
            body["hypotheses"][h]["evidence_selection_criteria"] = projection[h]
    messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return messages


def decode_teacher_source(encoded):
    marked, parts, spans, last, length = encoded["full_original_contract_with_original_span_markers"], [], [], 0, 0
    for match in SPAN.finditer(marked):
        assert int(match["index"]) == len(spans)
        gap, text = marked[last:match.start()], match["text"]
        parts.extend((gap, text))
        length += len(gap)
        spans.append([length, length + len(text)])
        length += len(text)
        last = match.end()
    parts.append(marked[last:])
    return {"id": encoded["id"], "text": "".join(parts), "spans": spans}


def teacher_sources(sources, annotations):
    rows = []
    for source in sources:
        assert "<SPAN " not in source["text"] and "</SPAN " not in source["text"]
        row = {"id": source["id"], "full_original_contract_with_original_span_markers": marked_text(source),
            "original_annotations": keyed(annotations[str(source["id"])])}
        assert decode_teacher_source(row) == source, "Never drop a source character or shift original offsets"
        rows.append(row)
    return table(rows)


def member_contrasts(sources, labels, annotations, answers, bank, executions, proposals):
    result = {h: [] for h in labels}
    for source in sources:
        d = source["id"]
        for h in labels:
            original, actual = annotations[str(d)][h], answers[d][h]
            gold, cited = set(original["spans"]), set(actual["spans"])
            ordinary = {r["original_span_index"] for r in proposals[d]["by_hypothesis"][h]["candidates"]}
            roles = access_roles(bank, executions[d], h)
            members = [[i, i in gold if original["choice"] != "NotMentioned" else None,
                i in cited, i in ordinary, i in roles["matched"], i in roles["neighbour"], i in roles["preamble"]]
                for i in sorted(gold | cited)]
            result[h].append({"source_case_id": d, "original_choice": original["choice"],
                "actual_choice": actual["choice"], "members": members})
    return {"encoding": "source-indexed-original-members-v2", "member_columns": MEMBER_COLUMNS,
        "legend": "Member rows zip with member_columns. Exact original text resolves from the enclosing "
            "source_case_id and original_span_index in the complete marked source, printed once. "
            "Every case, original Gold/cited member, choice and access role is retained.",
        "by_hypothesis": {h: table(v) for h, v in result.items()}}


def expand_member_contrasts(value, encoded_sources):
    """Audit-only inverse of the one declared teacher encoding, not a fallback."""
    value = expand(value)
    assert value["encoding"] == "source-indexed-original-members-v2"
    sources = {r["id"]: decode_teacher_source(r) for r in expand(encoded_sources)}
    result = {}
    for h, cases in value["by_hypothesis"].items():
        result[h] = []
        for case in cases:
            source, members = sources[case["source_case_id"]], []
            for row in case["members"]:
                member = dict(zip(value["member_columns"], row, strict=True))
                i = member["original_span_index"]
                member["original_text"] = source["text"][slice(*source["spans"][i])]
                members.append(member)
            result[h].append({**case, "members": members})
    return result
