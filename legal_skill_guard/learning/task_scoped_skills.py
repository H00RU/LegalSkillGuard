"""Task-local guidance in one bounded library; no semantic router or fallback.

The task is the original public EC/EV request, not a predicted category. Shared
text is stored once. Divergent task text costs its full serialized tokens. Only
EV owns numerical programs. Projection is deterministic, allowing independent
TRAIN commits without changing an unselected task's native request.
"""

from __future__ import annotations

import copy

from jsonschema import validate

from legal_skill_guard.learning.claim_execution import operator_catalog, operator_schema
from legal_skill_guard.learning.legal_namespace import SCOPES, allowable_namespaces
from legal_skill_guard.learning.publication import skill_record_schema

TASKS = ("EC", "EV")
TEXT_FIELDS = ("when", "procedure", "avoid_when")
SCOPED_GUIDANCE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["by_task", "operators", "jurisdiction"],
    "properties": {
        "by_task": {"type": "array", "minItems": 1, "maxItems": 2, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["tasks", *TEXT_FIELDS],
            "properties": {
                "tasks": {"type": "array", "minItems": 1, "maxItems": 2,
                          "items": {"type": "string", "enum": list(TASKS)}},
                **{key: {"type": "string", "minLength": 1} for key in TEXT_FIELDS},
            }}},
        "operators": {"type": "array", "items": operator_schema()},
        "jurisdiction": {"type": "string", "enum": list(SCOPES)},
    },
}


def validate_scoped_bank(bank):
    validate(bank, {"type": "array", "items": skill_record_schema(
        TASKS, guidance_schema=SCOPED_GUIDANCE_SCHEMA)})
    identities = set()
    for skill in bank:
        sid, scope = skill["id"], skill["hypothesis_ids"]
        if sid in identities or not sid.isascii() or len(scope) != len(set(scope)):
            raise ValueError("Distinct ASCII skill IDs and task scopes are required")
        identities.add(sid)
        covered = []
        for block in skill["guidance"]["by_task"]:
            covered.extend(block["tasks"])
        if len(covered) != len(set(covered)) or set(covered) != set(scope):
            raise ValueError("Exactly one explicit guidance block per declared task")
        if skill["guidance"]["operators"] and "EV" not in scope:
            raise ValueError("Only an EV-scoped skill may own numerical programs")
    operator_catalog(bank)


def import_blind_prior(bank):
    """Explicit one-time representation migration, never runtime compatibility."""
    result = []
    for skill in bank:
        guidance = skill["guidance"]
        if set(guidance) != {*TEXT_FIELDS, "operators", "jurisdiction"}:
            raise ValueError("Expected the declared legacy blind prior exactly once")
        result.append({"id": skill["id"],
            "hypothesis_ids": copy.deepcopy(skill["hypothesis_ids"]),
            "guidance": {
                "by_task": [{"tasks": copy.deepcopy(skill["hypothesis_ids"]),
                             **{key: guidance[key] for key in TEXT_FIELDS}}],
                "operators": copy.deepcopy(guidance["operators"]),
                "jurisdiction": guidance["jurisdiction"]}})
    validate_scoped_bank(result)
    return result


def task_view(bank, task):
    """Render the original actor record shape from only its known public task.

    Canonical IDs/order and task-local metadata cannot reveal edits belonging to
    another task. The actor never interprets the library's internal variants.
    """
    if task not in TASKS:
        raise ValueError("Unknown public task")
    validate_scoped_bank(bank)
    result = []
    for skill in sorted(bank, key=lambda value: value["id"]):
        if task not in skill["hypothesis_ids"]:
            continue
        guidance = skill["guidance"]
        block = next(b for b in guidance["by_task"] if task in b["tasks"])
        result.append({"id": skill["id"], "hypothesis_ids": [task],
            "guidance": {**{key: block[key] for key in TEXT_FIELDS},
                "operators": copy.deepcopy(guidance["operators"]) if task == "EV" else [],
                "jurisdiction": guidance["jurisdiction"]}})
    return result


def compose_task_edits(parent, proposed, accepted_tasks):
    """Commit only independently accepted TRAIN coordinates, not repaired answers.

    Supports CREATE/UPDATE/DELETE/MERGE through their already-applied proposal.
    A logical ID cannot simultaneously mean different legal jurisdictions. Such
    an incompatible composition is explicitly rejected, never normalized.
    """
    accepted_tasks = set(accepted_tasks)
    if not accepted_tasks or accepted_tasks - set(TASKS):
        raise ValueError("A nonempty subset of known tasks must pass TRAIN checks")
    views = {task: task_view(proposed if task in accepted_tasks else parent, task)
             for task in TASKS}
    return _join_task_views(views)


def _join_task_views(views):
    joined = {}
    for task in TASKS:
        for skill in views[task]:
            sid, guidance = skill["id"], skill["guidance"]
            text = {key: guidance[key] for key in TEXT_FIELDS}
            if sid not in joined:
                joined[sid] = {"id": sid, "hypothesis_ids": [], "guidance": {
                    "by_task": [], "operators": [],
                    "jurisdiction": guidance["jurisdiction"]}}
            entry = joined[sid]
            if entry["guidance"]["jurisdiction"] != guidance["jurisdiction"]:
                raise ValueError("Cross-task composition has conflicting legal jurisdictions")
            entry["hypothesis_ids"].append(task)
            blocks = entry["guidance"]["by_task"]
            same = next((b for b in blocks if all(b[key] == text[key]
                                                for key in TEXT_FIELDS)), None)
            if same is None:
                blocks.append({"tasks": [task], **text})
            else:
                same["tasks"].append(task)
            if task == "EV":
                entry["guidance"]["operators"] = copy.deepcopy(guidance["operators"])
    result = [joined[sid] for sid in sorted(joined)]
    validate_scoped_bank(result)
    for task in TASKS:
        if task_view(result, task) != views[task]:
            raise ValueError("Composition changed an evaluated task projection")
    return result


def legal_edit_coordinates(parent, proposed, rows):
    """TRAIN edit components from public law co-visibility, never answer labels.

    Co-visible jurisdictions, moved identities and changed ALL guidance must be
    evaluated together. Unchanged ALL records do not couple disjoint laws. The
    number of components is data/edit-dependent, not a fixed set of skill types.
    No inference routing changes: the original public AE filter stays in charge.
    """
    result = []
    for task in TASKS:
        before = {s["id"]: s for s in task_view(parent, task)}
        after = {s["id"]: s for s in task_view(proposed, task)}
        current = [r for r in rows if r["family"] == task]
        graph = {}

        def connect(names):
            names = set(names)
            for name in names:
                graph.setdefault(name, set()).update(names - {name})

        for row in current:
            connect(allowable_namespaces(row))
        for skill in [*before.values(), *after.values()]:
            namespace = skill["guidance"]["jurisdiction"]
            if namespace != "ALL":
                connect([namespace])
        for sid in before.keys() & after.keys():
            connect({before[sid]["guidance"]["jurisdiction"],
                     after[sid]["guidance"]["jurisdiction"]} - {"ALL"})
        shared_before = [s for s in before.values() if s["guidance"]["jurisdiction"] == "ALL"]
        shared_after = [s for s in after.values() if s["guidance"]["jurisdiction"] == "ALL"]
        if shared_before != shared_after:
            connect({"ALL", *graph})
        remaining = set(graph)
        while remaining:
            component, pending = set(), [min(remaining)]
            while pending:
                name = pending.pop()
                if name not in component:
                    component.add(name)
                    pending.extend(graph[name] - component)
            remaining -= component
            sources = sorted({r["case_id"] for r in current
                              if allowable_namespaces(r) & component})
            result.append({"id": task + ":" + "+".join(sorted(component)),
                           "task": task, "jurisdictions": sorted(component),
                           "source_case_ids": sources})
    return sorted(result, key=lambda value: value["id"])


def compose_legal_edits(parent, proposed, coordinates, accepted_coordinates):
    """One mixed library, not a per-case choice of answers or inference fallback."""
    accepted = set(accepted_coordinates)
    if not accepted or accepted - {c["id"] for c in coordinates}:
        raise ValueError("A nonempty set of evaluated legal coordinates is required")
    ownership = {}
    for coordinate in coordinates:
        for namespace in coordinate["jurisdictions"]:
            key = coordinate["task"], namespace
            if key in ownership:
                raise ValueError("Legal edit components overlap")
            ownership[key] = coordinate["id"]
    views = {}
    for task in TASKS:
        before = {s["id"]: s for s in task_view(parent, task)}
        after = {s["id"]: s for s in task_view(proposed, task)}
        selected = []
        for sid in sorted(before.keys() | after.keys()):
            variants = [source[sid] for source in (before, after) if sid in source]
            owners = {ownership.get((task, s["guidance"]["jurisdiction"])) for s in variants}
            if len(owners) != 1:
                raise ValueError("A moved skill identity crossed independent edit components")
            owner = owners.pop()
            if owner is None and (before.get(sid) != after.get(sid)
                                  or variants[0]["guidance"]["jurisdiction"] != "ALL"):
                raise ValueError("A changed public scope lacks an evaluated coordinate")
            source = after if owner in accepted else before
            if sid in source:
                selected.append(source[sid])
        views[task] = selected
    return _join_task_views(views)
