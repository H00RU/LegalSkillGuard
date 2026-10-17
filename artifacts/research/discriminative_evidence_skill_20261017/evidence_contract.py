"""Candidate member-level skill contract, without changing the native final task.

Research implementation only. Not imported by the completed production runs.
No inference judge, source filter, citation repair or additional model call.
"""

from __future__ import annotations

import copy
import json

from jsonschema import validate

from legal_skill_guard.learning.acquisition import GUIDANCE_SCHEMA, TEACHER
from legal_skill_guard.learning.packing import expand, table
from legal_skill_guard.learning.publication import skill_record_schema

UPDATED_GUIDANCE_SCHEMA = copy.deepcopy(GUIDANCE_SCHEMA)
UPDATED_GUIDANCE_SCHEMA["required"].append("evidence_criterion")
UPDATED_GUIDANCE_SCHEMA["properties"]["evidence_criterion"] = {
    "anyOf": [{"type": "string", "minLength": 1, "maxLength": 600}, {"type": "null"}],
}
# Old stored records remain verbatim. Newly emitted edits have a single explicit
# contract, rather than letting the decoder silently choose the old object shape.
EVIDENCE_GUIDANCE_SCHEMA = {"anyOf": [copy.deepcopy(GUIDANCE_SCHEMA), UPDATED_GUIDANCE_SCHEMA]}

OLD_NOTICE_SENTENCE = (
    "No skill code, identity, scope-control map, query counts or teacher advice is supplied."
)
NEW_NOTICE_SENTENCE = (
    "No skill identities, query counts or scope-control map are supplied. Optional "
    "evidence_selection_criteria are fallible learned inspection procedures for that "
    "hypothesis, never contract facts, label verdicts or mandatory citations. Literal "
    "access roles describe how a location was reached, not whether it is evidence."
)


def _writer_system():
    result = TEACHER
    replacements = {
        "The lawyer receives source locations only, NEVER your legal guidance, examples or rationale.":
        "The lawyer receives source locations, their factual access roles and any published evidence_criterion; no examples or audit rationale.",
        "Runtime skill=id,hypothesis_ids,guidance.source_queries ONLY.":
        "Runtime skill=id,hypothesis_ids,guidance.source_queries with a fallible evidence_criterion. Every newly emitted CREATE/UPDATE/MERGE skill must include evidence_criterion: a concise string, or explicit null when unwarranted. Original untouched query-only records remain valid verbatim.",
        "No inspection text, examples, labels, case IDs, parties, dates, source indices, fingerprints or answer lookup tables.":
        "No case examples, label verdicts, case IDs, parties, dates, source indices, fingerprints or answer lookup tables.",
        "aim<=2200 master to leave correction room.":
        "aim<=3100 master to leave criterion and scope-projection room.",
    }
    for before, after in replacements.items():
        assert result.count(before) == 1, "Update the explicit writer contract, never silently skip a clause"
        result = result.replace(before, after)
    return result + (
        " The current learning window is ALL32 actual same-parent canonical answers, "
        "selected by version, not correctness. Earlier observations already taught "
        "the parent and remain archived; do not pretend they are included as raw "
        "current-version responses. member_contrasts_by_hypothesis provides exact "
        "original membership versus actual citation. Its shared original_text_by_source "
        "catalogue resolves EVERY member by enclosing source_case_id and original_span_index; "
        "member_columns names every member row field. Recursively expand the ordinary "
        "record tables. These are lossless references, not omitted text or selected cases; "
        "the complete sources are supplied too. A false original_member means not annotated, not an "
        "independent semantic negative; null means evidence is undefined for the "
        "original NM relation. Do not invent corrected Gold or erase plausible "
        "support solely because it is unannotated. Distil concise transferable "
        "member-selection criteria: what makes a span directly responsive or "
        "necessary for a selected clause to be self-contained, and what separates "
        "nearby unrelated obligations from that function. Apply these criteria to "
        "ordinary as well as extra leads. Do not encode an E/C/NM sufficient-condition "
        "rule, repeat generic task instructions, demand all read-window spans, or "
        "force a new criterion where none is warranted. Aim at about30 words per "
        "criterion and<=3100 total master tokens, within the actual4096 bank/scope/"
        "criterion-projection bound. The next actor will see factual literal-match/"
        "neighbour/preamble booleans; earlier parent answers did not see those fields. "
        "Portability observations are actual earlier party-specific literals, not "
        "a reason to add another named-party exception. Correct them generally if "
        "the seen sources warrant it. No extra tools, critic, semantic admission, "
        "best-bank choice, citation union, answer repair or required growth. "
        "Your audit rationale is NOT served to the lawyer. If an edit rationale "
        "claims a learned selection criterion, publish that criterion in the actual "
        "evidence_criterion field; do not leave it only in your rationale. Explicit "
        "null means this edit intentionally offers no member-selection criterion."
    )


WRITER_SYSTEM = _writer_system()


def criterion_projection(bank, labels):
    return {h: [s["guidance"]["evidence_criterion"] for s in bank
        if h in s["hypothesis_ids"] and s["guidance"].get("evidence_criterion") is not None] for h in labels}


def access_roles(bank, executions, hypothesis):
    return {role: {i for s in bank if hypothesis in s["hypothesis_ids"]
        for event in executions[s["id"]] for i in event[role]}
        for role in ("matched", "neighbour", "preamble")}


def render_discriminative(canonical_messages, bank, labels, trace, *, include_criterion):
    """Preserve all source facts/scores and old choice/spans/reason grammar."""
    for s in bank:
        validate(s, skill_record_schema(labels, guidance_schema=EVIDENCE_GUIDANCE_SCHEMA))
    messages = copy.deepcopy(canonical_messages)
    assert messages[0]["content"].count(OLD_NOTICE_SENTENCE) == 1
    # Shared notice MUST change for every new arm: old ordinary wires are NOT
    # same-interface controls and may only be reported as historical references.
    messages[0]["content"] = messages[0]["content"].replace(OLD_NOTICE_SENTENCE, NEW_NOTICE_SENTENCE)
    body = json.loads(messages[1]["content"])
    projection = criterion_projection(bank, labels)
    for h in labels:
        roles = access_roles(bank, trace["actual_source_executions"], h)
        for item in body["hypotheses"][h]["additional_source_read_indices"]:
            i = item["original_span_index"]
            item.update(literal_match=i in roles["matched"],
                explicit_neighbour=i in roles["neighbour"],
                possible_list_preamble=i in roles["preamble"])
        if include_criterion and projection[h]:
            body["hypotheses"][h]["evidence_selection_criteria"] = projection[h]
    messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return messages


def member_contrasts(sources, labels, annotations, public_answers, bank, executions, proposals):
    """All same-hypothesis Gold/cited members; no selected failures or new labels."""
    result = {h: [] for h in labels}
    for source in sources:
        d = source["id"]
        for h in labels:
            original, actual = annotations[str(d)][h], public_answers[d][h]
            gold, cited = set(original["spans"]), set(actual["spans"])
            ordinary = {r["original_span_index"] for r in proposals[d]["by_hypothesis"][h]["candidates"]}
            roles = access_roles(bank, executions[d], h)
            members = [{"original_span_index": i,
                "original_text": source["text"][slice(*source["spans"][i])],
                "original_member": i in gold if original["choice"] != "NotMentioned" else None,
                "actually_cited": i in cited, "ordinary_candidate": i in ordinary,
                "literal_match": i in roles["matched"], "explicit_neighbour": i in roles["neighbour"],
                "possible_list_preamble": i in roles["preamble"]} for i in sorted(gold | cited)]
            result[h].append({"source_case_id": d, "original_choice": original["choice"],
                "actual_choice": actual["choice"], "members": table(members)})
    packed = compact_member_contrasts(result)
    assert expand_member_contrasts(packed) == expand(result), "Never omit or rewrite teaching members"
    return packed


def compact_member_contrasts(logical):
    """Share identical source text and table headers, never select evidence."""
    logical = expand(logical)
    columns = ["original_span_index", "original_member", "actually_cited", "ordinary_candidate",
        "literal_match", "explicit_neighbour", "possible_list_preamble"]
    texts, by_hypothesis = {}, {}
    for h, cases in logical.items():
        rows = []
        for case in cases:
            d, members = str(case["source_case_id"]), []
            for member in case["members"]:
                i = member["original_span_index"]
                text = member["original_text"]
                assert i not in texts.setdefault(d, {}) or texts[d][i] == text
                texts[d][i] = text
                members.append([member[k] for k in columns])
            rows.append({**case, "members": members})
        by_hypothesis[h] = table(rows)
    return {"encoding": "shared-original-member-texts-v1",
        "legend": "Every case and member is retained. Member rows zip with member_columns. "
            "Resolve original_text in original_text_by_source using the enclosing source_case_id "
            "and member original_span_index. A shared text is printed once, not removed from any observation.",
        "member_columns": columns,
        "original_text_by_source": {d: table([{"original_span_index": i, "original_text": t}
            for i, t in sorted(members.items())]) for d, members in texts.items()},
        "by_hypothesis": by_hypothesis}


def expand_member_contrasts(value):
    """Source-only inverse for audits; never used in lawyer inference."""
    value = expand(value)
    assert value["encoding"] == "shared-original-member-texts-v1"
    catalogue = {d: {m["original_span_index"]: m["original_text"] for m in members}
        for d, members in value["original_text_by_source"].items()}
    logical = {}
    for h, cases in value["by_hypothesis"].items():
        logical[h] = []
        for case in cases:
            members = []
            for row in case["members"]:
                member = dict(zip(value["member_columns"], row, strict=True))
                member["original_text"] = catalogue[str(case["source_case_id"])][member["original_span_index"]]
                members.append(member)
            logical[h].append({**case, "members": members})
    return logical
