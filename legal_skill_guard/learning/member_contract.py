"""Source-member skill contract for fresh online learning, not a run-specific probe.

Inference shares the ordinary retriever and serves learned criteria once. Sources are printed
once with the same original markers; exact inverse checks preserve text/offsets.
No host legal verdict, admission, citation union, answer repair or extra LLM.
"""

from __future__ import annotations

import copy
import json
import re
from collections import Counter

from jsonschema import validate

from legal_skill_guard.task import marked_text

from .acquisition import NOTICE
from .packing import expand, keyed, table
from .publication import DELTA_TEACHER_SYSTEM, skill_record_schema

EDIT_GUIDANCE = {
    "type": "object", "additionalProperties": False,
    "required": ["evidence_criterion"],
    "properties": {
        "evidence_criterion": {"type": "string", "minLength": 1},
    },
}
STORED_GUIDANCE = EDIT_GUIDANCE
NEW_NOTICE = (
    "No skill identities or scope-control map are supplied. Optional "
    "evidence_selection_criteria are fallible learned source-conditional legal "
    "inspection and evidence-selection procedures for that exact hypothesis, "
    "not current contract facts, automatic verdicts or mandatory citations."
)
MEMBER_NOTICE = (
    " The complete original NDA remains present and unchanged. Each hypothesis "
    "may have fallible_evidence_candidates from the same fixed ordinary retriever; "
    "they resolve to exact original text in candidate_original_text. These are "
    "optional reading aids, never a verdict or mandatory evidence. Any membership "
    "score is a fallible candidate estimate, not legal confidence. " + NEW_NOTICE +
    " Empty aids never establish NotMentioned. Read the entire source, check "
    "actors, scope, quantifiers and exceptions, and cite ANY original index as "
    "needed, including outside every lead. Decide each exact original hypothesis "
    "yourself. Return choice, spans and reason only."
)
MEMBER_COLUMNS = ["original_span_index", "original_member", "actually_cited", "ordinary_candidate"]
SPAN = re.compile(r"<SPAN (?P<index>\d+)>(?P<text>.*?)</SPAN (?P=index)>", re.DOTALL)


def writer_system():
    base = DELTA_TEACHER_SYSTEM.replace(
        "the tags constrain factual-query applicability, not guidance visibility or the legal conclusion.",
        "the tags declare procedural applicability, not guidance visibility or the legal conclusion.")
    return base + (
        " Learn reusable legal judgment and COMPLETE original-member selection "
        "for the actual frozen lawyer. Own and ordinary-control inputs share "
        "the exact SAME fixed ordinary evidence candidates and scores. The "
        "retriever is fallible, does not choose relations, is not refit by you, "
        "and does not exclude unlisted original source spans. Your only runtime "
        "guidance field is evidence_criterion: a complete source-conditional "
        "reading/decision procedure. There are NO learned literal queries, "
        "query windows, programs, candidate filtering or host citation unions. "
        "Use actual own observations only, never other-arm answers. All supplied "
        "sources and original Gold are already-seen TRAIN, not universal legal truth. "
        "Inspect each hypothesis_error_profile, relation confusion and member "
        "contrast across supported, opposed and unresolved seen sources. Do not "
        "increase correct NM by turning opposed or supported clauses into NM. "
        "Separate a wrong relation, visible-but-omitted evidence, unlisted missed "
        "evidence and an unannotated citation. For a correct relation with partial "
        "evidence, repair the completeness procedure, not the label by default. "
        "A statement may require both operative language and referenced definitions "
        "or qualifications, and several independently annotated provisions may matter. "
        "Do not equate a concise sufficient witness with the complete original "
        "target, or require an entire section simply because it contains context. "
        "Do not turn one observed lexical phrasing into a mandatory legal template. "
        "Distil reusable actor/action/object, polarity, quantifier and exception "
        "checks grounded in contrasting cases. Each record expresses one coherent "
        "procedure applicable to every declared public hypothesis; no fixed skill "
        "types/count, one-per-hypothesis rule or forced growth. The lawyer sees "
        "each criterion ONCE with its public hypothesis_ids, never opaque skill IDs. "
        "The actual evidence candidates and public answers are supplied by source; "
        "candidate text resolves exactly in the complete original marked sources. "
        "Member rows zip with member_columns. original_member=false is unannotated, "
        "not a semantic negative; null is undefined for original NM. The window "
        "contains the latest actual CURRENT-PARENT own answer per seen source, "
        "selected by version and chronology, not correctness. Older answers remain "
        "archived and taught earlier banks. No source character, Gold member, "
        "actual citation, actual candidate or public reason is omitted. "
        "Runtime procedures must not contain source IDs, original span integers, "
        "parties, dates, case-answer tables or audit rationales. Your rationale "
        "is not served: put the learned procedure in evidence_criterion. Finish "
        "complete English; no per-record character cap. Aim<=3100 master tokens "
        "within4096 actual master, scope and one-copy-criteria limits. No clipping, "
        "retry, score admission, best-bank rollback, new model or answer repair. "
        "Valid NOOP is normal; every valid edit is published without efficacy gating."
    )


WRITER = writer_system()


def one_copy_criteria(bank):
    """One actual procedure per record, with public applicability but no opaque IDs."""
    return [{"hypothesis_ids": list(s["hypothesis_ids"]),
        "criterion": s["guidance"]["evidence_criterion"]} for s in bank
        if s["guidance"].get("evidence_criterion") is not None]


def actor_messages(canonical_messages, bank, labels):
    for s in bank:
        validate(s, skill_record_schema(labels, guidance_schema=STORED_GUIDANCE))
    messages = copy.deepcopy(canonical_messages)
    assert messages[0]["content"].count(NOTICE) == 1
    messages[0]["content"] = messages[0]["content"].replace(NOTICE, MEMBER_NOTICE)
    body = json.loads(messages[1]["content"])
    assert all(not body["hypotheses"][h]["additional_source_read_indices"] for h in labels)
    criteria = one_copy_criteria(bank)
    if criteria:
        body["evidence_selection_criteria"] = criteria
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


def member_contrasts(sources, labels, annotations, answers, visible_candidates):
    result = {h: [] for h in labels}
    for source in sources:
        d = source["id"]
        for h in labels:
            original, actual = annotations[str(d)][h], answers[d][h]
            gold, cited = set(original["spans"]), set(actual["spans"])
            ordinary = {r["original_span_index"] for r in visible_candidates[d][h]}
            members = [[i, i in gold if original["choice"] != "NotMentioned" else None,
                i in cited, i in ordinary]
                for i in sorted(gold | cited)]
            result[h].append({"source_case_id": d, "original_choice": original["choice"],
                "actual_choice": actual["choice"], "members": members})
    return {"encoding": "source-indexed-original-members-v3", "member_columns": MEMBER_COLUMNS,
        "legend": "Member rows zip with member_columns. Exact original text resolves from the enclosing "
            "source_case_id and original_span_index in the complete marked source, printed once. "
            "Every case, original Gold/cited member, choice and actual candidate membership is retained.",
        "by_hypothesis": {h: table(v) for h, v in result.items()}}


def expand_member_contrasts(value, encoded_sources):
    """Audit-only inverse of the one declared teacher encoding, not a fallback."""
    value = expand(value)
    assert value["encoding"] == "source-indexed-original-members-v3"
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


def hypothesis_error_profiles(contrasts):
    """Deterministic summaries of the SAME own/Gold member rows, not a judge."""
    profiles = {}
    for h, cases in contrasts.items():
        counts, confusions = Counter(), Counter()
        for case in cases:
            original, actual = case["original_choice"], case["actual_choice"]
            correct = original == actual
            members = case["members"]
            counts.update(questions=1, label_correct=int(correct))
            confusions[(original, actual)] += 1
            if original == "NotMentioned":
                counts["joint_exact"] += int(correct and not any(m["actually_cited"] for m in members))
                continue
            tp = sum(m["original_member"] and m["actually_cited"] for m in members)
            fp = sum(not m["original_member"] and m["actually_cited"] for m in members)
            missed = [m for m in members if m["original_member"] and not m["actually_cited"]]
            visible = sum(m["ordinary_candidate"] for m in missed)
            counts.update(gold_non_neutral_questions=1,
                original_Gold_members=sum(m["original_member"] for m in members),
                true_cited_members=tp, unannotated_citations=fp, omitted_members=len(missed),
                visible_omitted_members=visible, unlisted_omitted_members=len(missed) - visible,
                correct_relation_but_inexact_evidence=int(correct and bool(fp or missed)),
                joint_exact=int(correct and not fp and not missed))
        profiles[h] = {**counts, "original_to_actual_relation_counts": [
            {"original": g, "actual": p, "count": n} for (g, p), n in sorted(confusions.items())]}
    return profiles
