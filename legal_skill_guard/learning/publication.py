"""Atomic teacher updates; no efficacy gate, rollback or mandatory growth."""

from __future__ import annotations

import json

from jsonschema import validate

TEACHER_SYSTEM = (
    "Learn reusable legal document-inspection skills from the supplied already-seen "
    "original TRAIN observations only. The original benchmark labels and binary "
    "evidence are training feedback, not universal legal truth. No tools, outside law, "
    "future documents, current inference answers, hidden reasoning or invented actions. "
    "Publish one complete revised library, retaining, creating, correcting, deleting "
    "or consolidating skills as warranted by the seen sources; do not force growth. "
    "Each skill must list the public hypothesis IDs whose legal inspection it addresses. "
    "Each skill's hypothesis IDs must be distinct. In the joint 17-hypothesis "
    "solver, all published guidance is visible together; the tags constrain "
    "factual-query applicability, not guidance visibility or the legal conclusion. "
    "Do not assume that guidance for other hypotheses is hidden from the lawyer. "
    "Write concise operational inspection procedures: contractual actor/action/object, "
    "permission or duty, conditions/exceptions, and the document evidence needed to "
    "distinguish supported, opposed and unresolved statements. These are not mandatory "
    "skill types or fixed skill counts. Do not store case answer tables, document IDs, "
    "entities, original source span indices or output-format tricks in runtime text. "
    "Use the actual component feedback if public trajectories are supplied: a correct "
    "label with incomplete/excess evidence calls for evidence-inspection repair, not "
    "blind reversal of the relation; correct evidence with a wrong relation calls for "
    "checking the statement's actor, scope and polarity. Preserve already supported "
    "decision boundaries rather than turning one observed phrasing into universal law. "
    "When no trajectories are supplied, learn from the same source and labels without "
    "inventing a solver failure or attributing an error. Review all supplied seen cases "
    "and the complete parent; previous post-publication failures are genuine feedback, "
    "not successful examples. All-failed and all-correct observations remain available. "
    "Aim for a compact library, not a list of paraphrases; shared skills may name several "
    "public hypotheses only where the inspection really transfers. Return the exact "
    "requested JSON. No retries, score-based acceptance, model-weight updates or answers "
    "on behalf of the lawyer."
)


DELTA_TEACHER_SYSTEM = TEACHER_SYSTEM.replace(
    "Publish one complete revised library, retaining, creating, correcting, deleting "
    "or consolidating skills as warranted by the seen sources; do not force growth. ",
    "Publish explicit CREATE, UPDATE, DELETE or MERGE operations against the exact "
    "supplied parent, only where the seen sources warrant a change. Unmentioned "
    "parent skills remain verbatim; do not regenerate them for style or breadth. "
    "Preserve correct actor, object, polarity and evidence boundaries; success on "
    "one topic does not license a broader target on another. A correction can be "
    "warranted by an observed failure or a source-derived conflict, not only an "
    "incorrect label. Cite already-seen source case IDs and explain the actual "
    "boundary changed for each operation. Those audit IDs/rationales never enter "
    "runtime guidance. CREATE has no targets; UPDATE/DELETE have one parent target; "
    "MERGE has at least two. Non-delete operations contain one resulting skill; "
    "DELETE contains null. UPDATE retains its target's ID; MERGE may retain a "
    "consumed ID or use a new ID. Targets must be distinct original parent IDs, "
    "not forward references. If no change is warranted, return no operations and "
    "an explicit noop reason; otherwise noop_reason is null. Do not force growth. ",
)


def skill_record_schema(public_ids):
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "hypothesis_ids", "guidance"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "hypothesis_ids": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": list(public_ids)},
            },
            "guidance": {"type": "string", "minLength": 1},
        },
    }


def differential_schema(public_ids, parent, seen_ids):
    targets = {"type": "array", "items": {"type": "string"}}
    if parent:
        targets["items"]["enum"] = [s["id"] for s in parent]
    else:
        targets["maxItems"] = 0
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["operations", "noop_reason"],
        "properties": {
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "operation",
                        "target_ids",
                        "skill",
                        "source_case_ids",
                        "rationale",
                    ],
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["CREATE", "UPDATE", "DELETE", "MERGE"],
                        },
                        "target_ids": targets,
                        "skill": {"anyOf": [skill_record_schema(public_ids), {"type": "null"}]},
                        "source_case_ids": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "integer", "enum": list(seen_ids)},
                        },
                        "rationale": {"type": "string", "minLength": 1},
                    },
                },
            },
            "noop_reason": {"type": ["string", "null"]},
        },
    }


def apply_differential_publication(parent, value, public_ids, seen_ids):
    """Structural all-or-stop editing, never a legal judge or efficacy gate."""
    validate(value, differential_schema(public_ids, parent, seen_ids))
    operations, noop = value["operations"], value["noop_reason"]
    if (not operations and not (noop or "").strip()) or (operations and noop is not None):
        raise ValueError("Explicit NOOP is required exactly when there are no operations")
    old = {s["id"]: s for s in parent}
    if len(old) != len(parent):
        raise ValueError("Duplicate parent IDs")
    updated = json.loads(json.dumps(old, ensure_ascii=False))
    consumed, produced = set(), set()
    for op in operations:
        kind, targets, candidate = op["operation"], op["target_ids"], op["skill"]
        refs = op["source_case_ids"]
        if len(refs) != len(set(refs)):
            raise ValueError("Duplicate source references; no repair")
        if (
            len(targets) != len(set(targets))
            or not set(targets) <= old.keys()
            or consumed & set(targets)
        ):
            raise ValueError("Targets must be unique, unconsumed exact-parent IDs")
        if (
            (kind == "CREATE" and targets)
            or (kind in ("UPDATE", "DELETE") and len(targets) != 1)
            or (kind == "MERGE" and len(targets) < 2)
        ):
            raise ValueError("Operation target arity differs from publication contract")
        if (kind == "DELETE") != (candidate is None):
            raise ValueError("Only DELETE has a null resulting skill")
        if candidate is not None:
            sid, scope = candidate["id"], candidate["hypothesis_ids"]
            if len(scope) != len(set(scope)):
                raise ValueError("Duplicate public scope; no deduplication")
            if kind == "UPDATE" and sid != targets[0]:
                raise ValueError("UPDATE must preserve the parent ID")
            if sid in produced or (sid in old and sid not in targets):
                raise ValueError("Resulting ID collides with another original or new skill")
            produced.add(sid)
        consumed.update(targets)
        if kind == "UPDATE":
            updated[targets[0]] = candidate
        else:
            for sid in targets:
                del updated[sid]
            if candidate is not None:
                updated[candidate["id"]] = candidate
    return list(updated.values())


def paired(before: list[dict], after: list[dict]) -> dict:
    a, b = (
        {(r["document_id"], q["hypothesis_id"]): q for r in rr for q in r["queries"]}
        for rr in (before, after)
    )
    if set(a) != set(b):
        raise ValueError("Original tasks are not paired")
    fixes = [list(k) for k in a if not a[k]["label_correct"] and b[k]["label_correct"]]
    breaks = [list(k) for k in a if a[k]["label_correct"] and not b[k]["label_correct"]]
    return {
        "original_hypotheses": len(a),
        "label_corrected": fixes,
        "label_broken": breaks,
        "net_label_correct": len(fixes) - len(breaks),
        "joint_exact_corrected": [
            list(k) for k in a if not a[k]["joint_exact"] and b[k]["joint_exact"]
        ],
        "joint_exact_broken": [
            list(k) for k in a if a[k]["joint_exact"] and not b[k]["joint_exact"]
        ],
    }
