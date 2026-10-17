"""Source-member skill contract for fresh online learning, not a run-specific probe.

Inference is the tested query/role/criterion interface. Teacher sources are printed
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

from .acquisition import NOTICE, QUERY_SCHEMA
from .packing import expand, keyed, table
from .publication import DELTA_TEACHER_SYSTEM, skill_record_schema

_INSPECTION_GUIDANCE = {
    "type": "object", "additionalProperties": False,
    "required": ["source_queries", "evidence_criterion"],
    "properties": {
        "source_queries": {"type": "array", "minItems": 0, "maxItems": 8,
            "items": copy.deepcopy(QUERY_SCHEMA)},
        "evidence_criterion": {"type": "string", "minLength": 1},
    },
}
_QUERY_GUIDANCE = copy.deepcopy(_INSPECTION_GUIDANCE)
_QUERY_GUIDANCE["properties"]["source_queries"]["minItems"] = 1
_QUERY_GUIDANCE["properties"]["evidence_criterion"] = {"anyOf": [
    {"type": "string", "minLength": 1}, {"type": "null"}]}
EDIT_GUIDANCE = {"anyOf": [_INSPECTION_GUIDANCE, _QUERY_GUIDANCE]}
STORED_GUIDANCE = EDIT_GUIDANCE
NEW_NOTICE = (
    "No skill identities, query counts or scope-control map are supplied. Optional "
    "evidence_selection_criteria are fallible learned source-conditional legal "
    "inspection and evidence-selection procedures for that exact hypothesis, "
    "not current contract facts, automatic verdicts or mandatory citations. Literal "
    "access roles describe how a location was reached, not whether it is evidence."
)
MEMBER_NOTICE = (
    " The complete original NDA remains present and unchanged. Each hypothesis "
    "may have fallible_evidence_candidates or additional_source_read_indices; "
    "they resolve to exact original text in candidate_original_text. These are "
    "optional reading aids, never a verdict or mandatory evidence. Any membership "
    "score is a fallible candidate estimate, not legal confidence. " + NEW_NOTICE +
    " Empty aids never establish NotMentioned. Read the entire source, check "
    "actors, scope, quantifiers and exceptions, and cite ANY original index as "
    "needed, including outside every lead. Decide each exact original hypothesis "
    "yourself. Return choice, spans and reason only."
)
MEMBER_COLUMNS = ["original_span_index", "original_member", "actually_cited", "ordinary_candidate",
    "literal_match", "explicit_neighbour", "possible_list_preamble"]
SPAN = re.compile(r"<SPAN (?P<index>\d+)>(?P<text>.*?)</SPAN (?P=index)>", re.DOTALL)


def writer_system():
    return DELTA_TEACHER_SYSTEM + (
        " Optimize this frozen lawyer's reusable legal inspection and COMPLETE "
        "original-member selection, not only lexical acquisition coverage. "
        "Its actual own inputs have NO ordinary retriever candidates or scores. "
        "Do not depend on the separate control's model or observations. The "
        "runtime guidance has source_queries and evidence_criterion. Queries "
        "may be EMPTY: a source-conditional legal inspection or selection "
        "procedure can be useful without a lexical search recipe. The criterion "
        "may be null when at least one genuine source query is supplied. An "
        "entirely empty action belongs in NOOP, not an empty skill. No fixed "
        "types, number, one-record-per-hypothesis or compulsory expansion. "
        "Use the hypothesis_error_profiles together with the complete sources "
        "and member contrasts to find reusable, still-unaddressed failures "
        "across the original hypotheses; do not merely keep retuning one "
        "existing query family or fill a topic quota. Distinguish an acquisition "
        "miss, a visible-but-omitted member, an irrelevant citation, a wrong "
        "relation and a genuinely unresolved statement. A correct label with "
        "incomplete evidence needs selection work, not automatic label reversal. "
        "A record must express ONE reusable inspection/action or conditional "
        "boundary. That same check must apply to every hypothesis in its scope. "
        "Split genuinely different return, copying, definition or exclusion "
        "checks rather than attaching a catalogue of topic-specific rules to "
        "one broadly scoped record. A truly shared actor/quantifier check can "
        "remain shared, without appending unrelated family-specific conditions. "
        "These are not fixed skill categories, counts or one-per-topic quotas. "
        "Write short executable reading steps with source conditions, the "
        "operative actor/action/object, quantifier/polarity and exceptions "
        "needed for that boundary. A sufficient example is not a necessary "
        "template; a generic ban may have an operative exception elsewhere. "
        "Ground conditional distinctions in opposed as well as supported seen "
        "cases. Preserve original members without turning an annotated context "
        "fragment into a universal legal rule or independent relation verdict. "
        "The lawyer alone decides every relation and original citation. "
        "Optional queries use all_phrases,any_phrases,none_phrases,before,after,"
        "include_list_preamble. The supplied exact light suffix-token matcher "
        "requires every all phrase, one any phrase when nonempty, and no none "
        "phrase contiguously WITHIN an original SPAN. At least one all/any "
        "phrase per query is required. before/after(0..64) are original-span "
        "neighbours; preamble links are fallible literal list-introduction "
        "access, not semantic dependencies. All query locations in a record "
        "are delivered to every hypothesis in its declared scope; do not "
        "broadcast unrelated query families. No catch-all/fallback query, "
        "semantic classifier, host label rule, automatic citation union or "
        "new runtime model. Full original text is unchanged. "
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
        "Distil source-dependent procedures rather than repeating the base task, "
        "requiring entire read windows as evidence, case answer tables or "
        "unconditional E/C/NM orders. Keep procedures concise but retain the "
        "necessary distinction; aim<=3100 master tokens within4096 master, "
        "scope and actual one-copy-criteria hard limits. There is NO per-record "
        "character limit: finish each procedure in clear complete English, "
        "rather than cutting a thought to fit a field. The native lawyer sees "
        "each non-null criterion ONCE alongside its public hypothesis_ids, "
        "not repeated separately under each hypothesis. No skill IDs or query "
        "code accompany that criterion. Never clip or retry to fit. "
        "The actor receives literal-match/neighbour/preamble facts, not evidence "
        "labels; observations preserve what that actor actually saw. Your rationale "
        "is NOT served: any claimed learned criterion must appear in the actual "
        "evidence_criterion field. Explicit null intentionally publishes no criterion. "
        "No case IDs, source indices, parties, dates, historical case answers "
        "or audit rationales in runtime procedures. No extra tools, critic, "
        "semantic admission, best-bank choice, citation union or answer repair. "
        "A valid NOOP or null criterion with a query is normal online "
        "learning, not a reason to retry until content appears."
    )


WRITER = writer_system()


def criterion_projection(bank, labels):
    return {h: [s["guidance"]["evidence_criterion"] for s in bank
        if h in s["hypothesis_ids"] and s["guidance"].get("evidence_criterion") is not None] for h in labels}


def one_copy_criteria(bank):
    """One actual procedure per record, with public applicability but no opaque IDs."""
    return [{"hypothesis_ids": list(s["hypothesis_ids"]),
        "criterion": s["guidance"]["evidence_criterion"]} for s in bank
        if s["guidance"].get("evidence_criterion") is not None]


def access_roles(bank, executions, hypothesis):
    return {role: {i for s in bank if hypothesis in s["hypothesis_ids"]
        for event in executions[s["id"]] for i in event[role]}
        for role in ("matched", "neighbour", "preamble")}


def actor_messages(canonical_messages, bank, labels, trace, *, include_criterion=True):
    for s in bank:
        validate(s, skill_record_schema(labels, guidance_schema=STORED_GUIDANCE))
    messages = copy.deepcopy(canonical_messages)
    assert messages[0]["content"].count(NOTICE) == 1
    messages[0]["content"] = messages[0]["content"].replace(NOTICE, MEMBER_NOTICE)
    body = json.loads(messages[1]["content"])
    for h in labels:
        roles = access_roles(bank, trace["actual_source_executions"], h)
        for record in body["hypotheses"][h]["additional_source_read_indices"]:
            i = record["original_span_index"]
            record.update(literal_match=i in roles["matched"], explicit_neighbour=i in roles["neighbour"],
                possible_list_preamble=i in roles["preamble"])
    criteria = one_copy_criteria(bank)
    if include_criterion and criteria:
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


def member_contrasts(sources, labels, annotations, answers, bank, executions, visible_candidates):
    result = {h: [] for h in labels}
    for source in sources:
        d = source["id"]
        for h in labels:
            original, actual = annotations[str(d)][h], answers[d][h]
            gold, cited = set(original["spans"]), set(actual["spans"])
            ordinary = {r["original_span_index"] for r in visible_candidates[d][h]}
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
            visible = sum(any(m[k] for k in ("ordinary_candidate", "literal_match",
                "explicit_neighbour", "possible_list_preamble")) for m in missed)
            counts.update(gold_non_neutral_questions=1,
                original_Gold_members=sum(m["original_member"] for m in members),
                true_cited_members=tp, unannotated_citations=fp, omitted_members=len(missed),
                visible_omitted_members=visible, unlisted_omitted_members=len(missed) - visible,
                correct_relation_but_inexact_evidence=int(correct and bool(fp or missed)),
                joint_exact=int(correct and not fp and not missed))
        profiles[h] = {**counts, "original_to_actual_relation_counts": [
            {"original": g, "actual": p, "count": n} for (g, p), n in sorted(confusions.items())]}
    return profiles
