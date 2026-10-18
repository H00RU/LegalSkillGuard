"""Source-member skill contract for fresh online learning, not a run-specific probe.

Inference reads the complete original source and serves learned criteria once.
Sources are printed once with the same original markers; inverse checks preserve text/offsets.
No host legal verdict, admission, citation union, answer repair or extra LLM.
"""

from __future__ import annotations

import copy
import json
import re
from collections import Counter

from jsonschema import ValidationError, validate

from legal_skill_guard.task import marked_text

from .acquisition import NOTICE
from .packing import expand, indices, keyed, table
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
    " The complete original NDA remains present and unchanged. " + NEW_NOTICE +
    " Read the entire source, check actors, scope, quantifiers and exceptions, "
    "and cite ANY original index as needed. Decide each exact original hypothesis "
    "yourself. Return choice, spans and reason only."
)
MEMBER_COLUMNS = ["original_span_index", "original_member", "actually_cited"]
SPAN = re.compile(r"<SPAN (?P<index>\d+)>(?P<text>.*?)</SPAN (?P=index)>", re.DOTALL)


def member_replay_cases(proposals, annotations, labels):
    """Original seen-member feedback, never a native answer or legal judge."""
    result = {}
    for h in labels:
        annotation = annotations[h]
        gold, proposed = set(annotation["spans"]), set(proposals[h])
        result[h] = {
            "proposed_original_indices": proposals[h],
            "original_choice": annotation["choice"],
            "original_non_neutral_member_target": annotation["choice"] != "NotMentioned",
            "original_member_hits": sorted(proposed & gold),
            "original_member_misses": sorted(gold - proposed),
            "unannotated_read_proposals_not_false_legal_claims": sorted(proposed - gold),
        }
    return result


def draft_member_feedback(parent_replays, draft_replays, labels):
    """Reversible executed-draft differences, not candidate acceptance criteria.

    Every source and public hypothesis survives, including unchanged rows.
    The original parent replay and Gold are already in the same teacher body.
    Inclusive ordered runs avoid duplicating them or clipping dense proposals.
    """
    if [r["document_id"] for r in parent_replays] != [r["document_id"] for r in draft_replays]:
        raise ValueError("Draft feedback must cover the identical complete seen-source sequence")
    sources, totals = [], {"parent": {"tp": 0, "unannotated": 0, "misses": 0},
                           "draft": {"tp": 0, "unannotated": 0, "misses": 0}}
    for parent, draft in zip(parent_replays, draft_replays, strict=True):
        changes = {}
        for h in labels:
            a, b = parent["by_hypothesis"][h], draft["by_hypothesis"][h]
            ga = set(a["original_member_hits"]) | set(a["original_member_misses"])
            gb = set(b["original_member_hits"]) | set(b["original_member_misses"])
            if a["original_choice"] != b["original_choice"] or ga != gb:
                raise ValueError("Draft and parent must use the same unchanged original annotations")
            p, d = set(a["proposed_original_indices"]), set(b["proposed_original_indices"])
            added, removed = indices(sorted(d-p)), indices(sorted(p-d))
            restore = lambda runs: {i for start, end in runs for i in range(start, end+1)}
            if sorted((p-restore(removed)) | restore(added)) != b["proposed_original_indices"]:
                raise ValueError("Never omit or repair a draft's actual proposed members")
            changes[h] = {"added_original_index_runs": added, "removed_original_index_runs": removed}
            if a["original_non_neutral_member_target"]:
                for role, case in (("parent", a), ("draft", b)):
                    totals[role]["tp"] += len(case["original_member_hits"])
                    totals[role]["unannotated"] += len(case["unannotated_read_proposals_not_false_legal_claims"])
                    totals[role]["misses"] += len(case["original_member_misses"])
        sources.append({"document_id": parent["document_id"], "by_hypothesis": keyed(changes)})
    return {
        "encoding": "parent-relative-original-proposal-runs-v1",
        "instructions": "Every [a,b] is an inclusive original-index run. Reconstruct the complete draft "
                        "proposals as sorted((parent proposals minus removed runs) union added runs). "
                        "Parent proposals and unchanged original Gold are in the same teacher input. "
                        "All sources/hypotheses, including unchanged rows, are retained.",
        "all_seen_sources_and_hypotheses": table(sources),
        "Gold_non_neutral_read_proposal_counts_NOT_native_performance": totals,
        "not_a_score_threshold_or_publication_gate": True,
    }


def writer_system():
    base = DELTA_TEACHER_SYSTEM.replace(
        "the tags constrain factual-query applicability, not guidance visibility or the legal conclusion.",
        "the tags declare procedural applicability, not guidance visibility or the legal conclusion.")
    return base + (
        " Learn reusable legal judgment and COMPLETE original-member selection "
        "for the actual frozen lawyer. Both own and empty-control inputs contain "
        "the SAME complete original source and original hypotheses, without any "
        "retriever, candidate list, membership scores or extra source windows. "
        "Your only runtime "
        "guidance field is evidence_criterion: a complete source-conditional "
        "reading/decision procedure. There are NO learned literal queries, "
        "query windows, programs, candidate filtering or host citation unions. "
        "Use actual own observations only, never other-arm answers. All supplied "
        "sources and original Gold are already-seen TRAIN, not universal legal truth. "
        "Inspect each hypothesis_error_profile, relation confusion and member "
        "contrast across supported, opposed and unresolved seen sources. Do not "
        "increase correct NM by turning opposed or supported clauses into NM. "
        "Separate a wrong relation, omitted evidence and an unannotated citation. "
        "For a correct relation with partial "
        "evidence, repair the completeness procedure, not the label by default. "
        "A statement may require both operative language and referenced definitions "
        "or qualifications, and several independently annotated provisions may matter. "
        "Do not equate a concise sufficient witness with the complete original "
        "target, or require an entire section simply because it contains context. "
        "Learn selection precision as well as completeness from the supplied "
        "member contrasts. Distinguish text useful to READ from text that belongs "
        "in the final cited set: a cross-reference, surrounding paragraph or "
        "logical premise is not automatically a citation. Conversely, retain "
        "a governing introduction or terminal qualification when it changes the "
        "responsive unit. State observable source conditions and inclusion/exclusion "
        "actions, not 'include the annotated/Gold spans': future Gold is unavailable. "
        "Do not turn one observed lexical phrasing into a mandatory legal template. "
        "Distil reusable actor/action/object, polarity, quantifier and exception "
        "checks grounded in contrasting cases. Each record expresses one coherent "
        "procedure applicable to every declared public hypothesis; no fixed skill "
        "types/count, one-per-hypothesis rule or forced growth. The lawyer sees "
        "each criterion ONCE with its public hypothesis_ids, never opaque skill IDs. "
        "The actual public answers are supplied by source and their citations "
        "resolve exactly in the complete original marked sources. "
        "Member rows zip with member_columns. original_member=false is unannotated, "
        "not a semantic negative; null is undefined for original NM. The window "
        "contains the latest actual CURRENT-PARENT own answer per seen source, "
        "selected by version and chronology, not correctness. Older answers remain "
        "archived and taught earlier banks. No source character, Gold member, "
        "actual citation or public reason is omitted. "
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


def execution_blocks(bank, labels):
    """Public applicability partitions, never a current-case semantic router.

    Hypotheses sharing the EXACT applicable skill set form one execution unit.
    Empty controls use this same partition, not a cheaper/different task. The
    number of blocks is learned-bank dependent, not fixed to three or seventeen.
    """
    for skill in bank:
        validate(skill, skill_record_schema(labels, guidance_schema=STORED_GUIDANCE))
    if len({s["id"] for s in bank}) != len(bank):
        raise ValueError("Duplicate skill identities")
    groups = {}
    for h in labels:
        signature = tuple(s["id"] for s in bank if h in s["hypothesis_ids"])
        groups.setdefault(signature, []).append(h)
    blocks = list(groups.values())
    assert sum(map(len, blocks)) == len(labels)
    return blocks


def project_criteria(bank, hypothesis_ids):
    """Lossless applicable procedures, with public scope intersected explicitly."""
    selected = set(hypothesis_ids)
    projected = []
    for skill in bank:
        scope = [h for h in skill["hypothesis_ids"] if h in selected]
        if scope:
            item = copy.deepcopy(skill)
            item["hypothesis_ids"] = scope
            projected.append(item)
    return projected


def combine_block_responses(fragments, labels):
    """Join disjoint native answers, without selecting or repairing a decision.

    Any incomplete/invalid fragment makes the whole logical contract answer
    invalid for the SAME full original denominator. Never fill absent keys or
    retain only easy questions. This is explicitly not a native server response.
    """
    answers, errors, physical_ids = {}, [], []
    prompt_tokens = completion_tokens = 0
    expected = []
    for index, fragment in enumerate(fragments):
        response = fragment["response"]
        keys = fragment["hypothesis_ids"]
        if set(expected) & set(keys):
            raise ValueError("Overlapping execution blocks; no answer selection")
        expected.extend(keys)
        physical_ids.append(response["raw_id"])
        prompt_tokens += response["prompt_tokens"]
        completion_tokens += response["completion_tokens"]
        try:
            if response["finish_reason"] != "stop":
                raise ValueError("Incomplete native fragment")
            value = json.loads(response["content"])
            validate(value, fragment["schema"])
            if set(value) != set(keys):
                raise ValueError("Fragment keys differ from its public block")
            answers.update(value)
        except (ValueError, ValidationError) as exc:
            errors.append({"block": index, "error": str(exc)})
    if set(expected) != set(labels) or len(expected) != len(labels):
        raise ValueError("Blocks do not partition the complete original task")
    if len(set(physical_ids)) != len(physical_ids) or any(not i for i in physical_ids):
        raise ValueError("Every block requires a distinct real native response")
    cutoff = any(f["response"]["finish_reason"] == "length" for f in fragments)
    return {"content": json.dumps(answers, ensure_ascii=False, separators=(",", ":")),
        "finish_reason": ("length" if cutoff else None) if errors else "stop", "raw_id": None,
        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
        "composite_logical_answer_not_a_native_server_response": True,
        "actual_native_raw_ids": physical_ids, "component_errors": errors,
        "no_answer_rewrite_repair_or_missing_key_substitution": True}


def actor_messages(canonical_messages, bank, labels):
    for s in bank:
        validate(s, skill_record_schema(labels, guidance_schema=STORED_GUIDANCE))
    messages = copy.deepcopy(canonical_messages)
    assert messages[0]["content"].count(NOTICE) == 1
    messages[0]["content"] = messages[0]["content"].replace(NOTICE, MEMBER_NOTICE)
    body = json.loads(messages[1]["content"])
    # Reuse the original source/schema serializer, not its obsolete empty aid ABI.
    # Never silently discard an actual retrieval result or change source content.
    assert not body.pop("candidate_original_text")
    for h in labels:
        assert not body["hypotheses"][h].pop("fallible_evidence_candidates")
        assert not body["hypotheses"][h].pop("additional_source_read_indices")
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


def annotated_sources(sources, labels, annotations):
    """One-copy full original text with colocated original membership tags.

    Exact gaps, original coordinates, annotation order/values and all source
    characters survive. Gold tags repeat original membership next to its text,
    not the text itself. No interesting-case selection, constructed negatives or
    NM semantic claims. This teacher-only encoding never reaches the lawyer.
    """
    result = []
    for source in sources:
        ann = annotations[str(source["id"])]
        assert set(ann) == set(labels)
        segments, recovered, coordinates, cursor, size = [], [], [], 0, 0
        for i,(a,b) in enumerate(source["spans"]):
            gap, text = source["text"][cursor:a], source["text"][a:b]
            assert cursor <= a < b <= len(source["text"])
            recovered.extend((gap,text)); size += len(gap)
            coordinates.append([size,size+len(text)]); size += len(text); cursor=b
            segments.append({"original_span_index":i,"gap_before":gap,
                "literal_original_text":text,
                "original_member_for": [h for h in labels if i in ann[h]["spans"]]})
        tail = source["text"][cursor:]; recovered.append(tail)
        assert "".join(recovered)==source["text"] and coordinates==source["spans"]
        original = keyed(ann); assert expand(original)==ann
        result.append({"id":source["id"], "source_segments_with_original_membership":table(segments),
            "trailing_original_text":tail, "original_annotations":original})
    return table(result)


def original_witness_replay(source, labels, annotation, proposed, cited):
    """All original labels and factual accessed/cited excerpts, NOT a full source.

    Used only for past-source teacher replay, never as a replacement lawyer
    contract or an NM absence proof. Complete past sources remain the actual
    inputs to program execution and retention. No case or Gold member is chosen
    by its score; all original members and all validated proposals/citations
    resolve to verbatim original excerpts once per source.
    """
    assert set(annotation) == set(labels)
    indices = set(proposed) | set(cited) | {i for h in labels for i in annotation[h]["spans"]}
    if any(type(i) is not int or i<0 or i>=len(source["spans"]) for i in indices):
        raise ValueError("Past witness references must be actual original indices")
    excerpts = [{"original_span_index":i,
        "literal_original_text":source["text"][slice(*source["spans"][i])],
        "original_member_for":[h for h in labels if i in annotation[h]["spans"]]}
        for i in sorted(indices)]
    original=keyed(annotation);assert expand(original)==annotation
    return {"id":source["id"],"original_annotations":original,
        "all_original_members_and_actual_accessed_cited_excerpts":table(excerpts),
        "complete_original_contract_not_repeated_in_teacher_context":True,
        "excerpts_do_not_prove_contract_wide_absence_or_NM":True}


def member_contrasts(sources, labels, annotations, answers):
    result = {h: [] for h in labels}
    for source in sources:
        d = source["id"]
        for h in labels:
            original, actual = annotations[str(d)][h], answers[d][h]
            gold, cited = set(original["spans"]), set(actual["spans"])
            members = [[i, i in gold if original["choice"] != "NotMentioned" else None,
                i in cited]
                for i in sorted(gold | cited)]
            result[h].append({"source_case_id": d, "original_choice": original["choice"],
                "actual_choice": actual["choice"], "members": members})
    return {"encoding": "source-indexed-original-members-v3", "member_columns": MEMBER_COLUMNS,
        "legend": "Member rows zip with member_columns. Exact original text resolves from the enclosing "
            "source_case_id and original_span_index in the complete marked source, printed once. "
            "Every case, original Gold/cited member and choice is retained.",
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
            counts.update(gold_non_neutral_questions=1,
                original_Gold_members=sum(m["original_member"] for m in members),
                true_cited_members=tp, unannotated_citations=fp, omitted_members=len(missed),
                omitted_members_with_correct_relation=len(missed) if correct else 0,
                omitted_members_with_wrong_relation=0 if correct else len(missed),
                unannotated_citations_with_correct_relation=fp if correct else 0,
                unannotated_citations_with_wrong_relation=0 if correct else fp,
                correct_relation_but_inexact_evidence=int(correct and bool(fp or missed)),
                joint_exact=int(correct and not fp and not missed))
        profiles[h] = {**counts, "original_to_actual_relation_counts": [
            {"original": g, "actual": p, "count": n} for (g, p), n in sorted(confusions.items())]}
    return profiles
