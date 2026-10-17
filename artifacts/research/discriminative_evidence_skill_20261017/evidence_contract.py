"""Candidate member-level skill contract, without changing the native final task.

Research implementation only. Not imported by the completed production runs.
No inference judge, source filter, citation repair or additional model call.
"""

from __future__ import annotations

import copy
import json

from jsonschema import validate

from legal_skill_guard.learning.acquisition import GUIDANCE_SCHEMA, TEACHER
from legal_skill_guard.learning.packing import table
from legal_skill_guard.learning.publication import skill_record_schema

_with_criterion = copy.deepcopy(GUIDANCE_SCHEMA)
_with_criterion["required"].append("evidence_criterion")
_with_criterion["properties"]["evidence_criterion"] = {
    "type": "string", "minLength": 1, "maxLength": 600,
}
EVIDENCE_GUIDANCE_SCHEMA = {"anyOf": [copy.deepcopy(GUIDANCE_SCHEMA), _with_criterion]}

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
        "Runtime skill=id,hypothesis_ids,guidance.source_queries with an optional evidence_criterion. Original query-only records remain valid.",
        "No inspection text, examples, labels, case IDs, parties, dates, source indices, fingerprints or answer lookup tables.":
        "No case examples, label verdicts, case IDs, parties, dates, source indices, fingerprints or answer lookup tables.",
    }
    for before, after in replacements.items():
        assert result.count(before) == 1, "Update the explicit writer contract, never silently skip a clause"
        result = result.replace(before, after)
    return result + (
        " The current learning window is ALL32 actual same-parent canonical answers, "
        "selected by version, not correctness. Earlier observations already taught "
        "the parent and remain archived; do not pretend they are included as raw "
        "current-version responses. member_contrasts_by_hypothesis provides exact "
        "original text and original membership versus actual citation, with the full "
        "source still supplied. A false original_member means not annotated, not an "
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
        "best-bank choice, citation union, answer repair or required growth."
    )


WRITER_SYSTEM = _writer_system()


def criterion_projection(bank, labels):
    return {h: [s["guidance"]["evidence_criterion"] for s in bank
        if h in s["hypothesis_ids"] and "evidence_criterion" in s["guidance"]] for h in labels}


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
    return {h: table(v) for h, v in result.items()}
