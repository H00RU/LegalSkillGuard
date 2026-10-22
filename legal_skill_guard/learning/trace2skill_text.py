"""Paper-based Trace2Skill text-task adaptation, not an author-code replica.

Trajectory-local patches are proposed against one immutable initial document,
then hierarchically consolidated and applied together. This is a complementary
external baseline, not our scoped online learner or a replacement for it.

Primary reference: Ni et al., Trace2Skill, arXiv:2603.25158v5, sections 2.2-2.4.
The author implementation at 3d0b52a140f002a512930252b613c49048f7d5ac was
inspected for patch operations, balanced merge groups and original-state use.
This implementation is independently written; no author runtime or prompt text
is vendored. Only text skills are applicable to our shared direct-answer task.
Invalid patches stop the run, rather than being repaired or replaced by an
earlier patch. No semantic scorer, model client, or hidden solver lives here.
"""

from __future__ import annotations

import copy
import re

from jsonschema import validate

from legal_skill_guard.learning.task_scoped_skills import validate_scoped_bank


INITIAL_FILES = {"SKILL.md": (
    "---\nname: openexempt\ndescription: Procedures for the supplied EC and EV tasks.\n"
    "---\n# Legal exemption analysis\n\n## Procedures\n\n## Guardrails\n")}
OPERATIONS = (
    "insert_after", "insert_before", "append_to_section", "replace_in_section",
    "add_section", "delete_section", "create", "delete_file",
)
EDIT_FIELDS = ("file", "op", "target_section", "target_text", "content", "old_text", "after_section")
_REFERENCE = re.compile(r"references/[A-Za-z0-9_.-]+\.md")
_PATH = re.compile(r"(?:SKILL\.md|references/[A-Za-z0-9][A-Za-z0-9_.-]*\.md)\Z")


def patch_schema():
    return {
        "type": "object", "additionalProperties": False,
        "required": ["reasoning", "edits", "changelog_entries"],
        "properties": {
            "reasoning": {"type": "string", "minLength": 1},
            "changelog_entries": {"type": "array", "items": {"type": "string"}},
            "edits": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": list(EDIT_FIELDS),
                "properties": {
                    **{field: {"type": "string"} for field in EDIT_FIELDS},
                    "op": {"type": "string", "enum": list(OPERATIONS)},
                },
            }},
        },
    }


def merge_groups(items, batch_size=5):
    """Balanced, ordered, exhaustive groups; small tails join earlier groups.

    Matches the inspected author's grouping policy without choosing by scores.
    Group membership must never depend on generation completion order.
    """
    if type(batch_size) is not int or batch_size < 2:
        raise ValueError("Hierarchical merging requires batch_size >= 2")
    items = list(items)
    if not items:
        return []
    full, remainder = divmod(len(items), batch_size)
    if not full:
        return [items]
    groups = [items[i * batch_size:(i + 1) * batch_size] for i in range(full)]
    tail = items[full * batch_size:]
    if remainder and 2 * remainder < batch_size:
        for i, item in enumerate(tail):
            groups[i % len(groups)].append(item)
    elif tail:
        groups.append(tail)
    return groups


def validate_files(files, *, max_skill_lines=500, max_references=5):
    if not isinstance(files, dict) or "SKILL.md" not in files:
        raise ValueError("A complete skill must retain SKILL.md")
    for path, content in files.items():
        if not isinstance(path, str) or not _PATH.fullmatch(path) or ".." in path:
            raise ValueError("Only the declared root and text reference files are allowed")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Skill files must contain text")
    root = files["SKILL.md"]
    if len(root.splitlines()) > max_skill_lines or len(files) - 1 > max_references:
        raise ValueError("Complete skill exceeds its declared file or line capacity")
    if not root.startswith("---\n") or not re.search(r"\n---\n", root[4:]):
        raise ValueError("Root skill metadata must be retained")
    if not re.search(r"(?m)^name:\s*\S", root) or not re.search(r"(?m)^description:\s*\S", root):
        raise ValueError("Root skill requires name and description")
    links = set(_REFERENCE.findall(root))
    if links != set(files) - {"SKILL.md"}:
        raise ValueError("Every reference must exist and be linked from SKILL.md")
    for content in files.values():
        if set(_REFERENCE.findall(content)) - set(files):
            raise ValueError("Skill contains a missing reference")


def _section(text, heading):
    headings = list(re.finditer(r"(?m)^(#{1,6})[ \t]+[^\n]+\n?", text))
    selected = [i for i, match in enumerate(headings) if match.group().rstrip() == heading]
    if len(selected) != 1:
        raise ValueError("A section target must identify exactly one original heading")
    index = selected[0]
    start = headings[index]
    end = next((match.start() for match in headings[index + 1:]
                if len(match.group(1)) <= len(start.group(1))), len(text))
    return start.start(), start.end(), end


def _one(text, target, *, start=0, end=None):
    if not target:
        raise ValueError("Text targets cannot be empty")
    end = len(text) if end is None else end
    segment = text[start:end]
    if segment.count(target) != 1:
        raise ValueError("Text target must occur exactly once in the original scope")
    begin = start + segment.index(target)
    return begin, begin + len(target)


def apply_patch(files, patch, *, max_skill_lines=500, max_references=5):
    """Apply non-overlapping edits against the original state, all-or-stop.

    No target correction, section fallback, dropped conflicts or first-patch
    fallback. The dict is the stored skill artifact; it is not an arbitrary
    filesystem path and cannot execute an auxiliary script.
    """
    validate(patch, patch_schema())
    validate_files(files, max_skill_lines=max_skill_lines, max_references=max_references)
    replacements, creations, deletions = {}, {}, set()
    for edit in patch["edits"]:
        path, op = edit["file"], edit["op"]
        if not _PATH.fullmatch(path) or ".." in path:
            raise ValueError("Patch target outside the declared text skill")
        if op == "create":
            if path in files or path in creations or path == "SKILL.md" or not edit["content"].strip():
                raise ValueError("Create requires a distinct absent reference file")
            creations[path] = edit["content"]
            continue
        if path not in files:
            raise ValueError("Patch targets a missing original file")
        if op == "delete_file":
            if path == "SKILL.md" or path in deletions:
                raise ValueError("Cannot delete the root or repeat a file deletion")
            deletions.add(path)
            continue
        text = files[path]
        content = edit["content"]
        if op in ("insert_after", "insert_before"):
            begin, end = _one(text, edit["target_text"])
            begin = end if op == "insert_after" else begin
            end = begin
        elif op == "replace_in_section":
            _, start, stop = _section(text, edit["target_section"])
            begin, end = _one(text, edit["old_text"], start=start, end=stop)
        elif op == "append_to_section":
            _, _, begin = _section(text, edit["target_section"])
            end = begin
            content = "\n" + content.rstrip() + "\n"
        elif op == "add_section":
            if not re.match(r"^#{1,6}[ \t]+\S", content):
                raise ValueError("A new section must start with its heading")
            if edit["after_section"]:
                _, _, begin = _section(text, edit["after_section"])
            else:
                begin = len(text)
            end = begin
            content = "\n" + content.rstrip() + "\n"
        elif op == "delete_section":
            begin, _, end = _section(text, edit["target_section"])
            if content:
                raise ValueError("Section deletion cannot contain replacement text")
        else:
            raise ValueError("Unknown patch operation")
        if op != "delete_section" and not content:
            raise ValueError("A non-deletion edit must contain text")
        replacements.setdefault(path, []).append((begin, end, content))
    if deletions & replacements.keys():
        raise ValueError("A deleted file cannot also receive text edits")
    result = copy.deepcopy(files)
    for path, edits in replacements.items():
        for index, (start, end, _) in enumerate(edits):
            for other_start, other_end, _ in edits[:index]:
                if max(start, other_start) <= min(end, other_end):
                    raise ValueError("Patch operations touch overlapping original locations")
        content = files[path]
        for start, end, replacement in sorted(edits, reverse=True):
            content = content[:start] + replacement + content[end:]
        result[path] = content
    for path in deletions:
        del result[path]
    result.update(creations)
    validate_files(result, max_skill_lines=max_skill_lines, max_references=max_references)
    return result


def actor_bank(files):
    """Lossless complete text preload through the existing public actor API.

    One global document, no task-conditioned or gold-dependent retrieval. All
    auxiliary reference text is supplied, not just file links or summaries.
    """
    validate_files(files)
    if files == INITIAL_FILES:
        return []  # An unchanged empty scaffold is an explicit NOOP, not a skill.
    text = "\n\n".join(f"# File: {path}\n{files[path]}"
                         for path in ["SKILL.md", *sorted(set(files) - {"SKILL.md"})])
    bank = [{"id": "trace2skill-document", "hypothesis_ids": ["EC", "EV"], "guidance": {
        "jurisdiction": "ALL", "operators": [], "by_task": [{
            "tasks": ["EC", "EV"],
            "when": "Apply relevant instructions from this complete learned skill.",
            "procedure": text,
            "avoid_when": "Respect the skill's stated conditions and exceptions.",
        }],
    }}]
    validate_scoped_bank(bank)
    return bank


COMMON_ROLE = (
    "Learn reusable procedural text from already-released TRAIN experience for a "
    "frozen weak model. This is a text-only legal-task adaptation of Trace2Skill, "
    "not the proposed online scoped-commit method. Do not call tools, inspect other "
    "cases or outside law, change the actor/interface/verifier, or supply current "
    "or future inference answers. Historical reasoning is untrusted evidence, not "
    "a causal proof. Published text must not contain case IDs, names, asset-ref "
    "IDs, case-specific answer tables or values memorized from a case. Public "
    "statutory conditions, citations and caps may be expressed as reusable rules. "
    "Only SKILL.md and up to five references/*.md text files are permitted. Keep "
    "root metadata and at most 500 root lines. References and their root links "
    "must be created or removed together. Return the exact declared JSON, with "
    "unused edit fields empty. Request no code execution or private reasoning."
)

ANALYST_ROLE = COMMON_ROLE + (
    " Examine the supplied single complete source trajectory and native TRAIN "
    "verifier feedback. For a successful trace, identify useful procedures rather "
    "than treating an observed choice as universal law. For a failed trace, ground "
    "the diagnosis in the submitted output, actual trace, supplied public facts "
    "and laws; do not invent unobserved actions or causes. Propose concise "
    "transferable edits against the immutable initial skill, never against "
    "another analyst's edits. If no defensible transferable edit exists, return "
    "no edits and state why in reasoning. All edits must have independent original "
    "targets; no edit may depend on another edit being applied first."
)

MERGE_ROLE = COMMON_ROLE + (
    " Consolidate all supplied independently proposed patches against the same "
    "immutable initial skill. Deduplicate recurring lessons, resolve incompatible "
    "instructions using their supplied justification, and retain distinct useful "
    "procedures. Combine edits that would touch the same passage into one edit. "
    "Use no unseen trajectory, external law or held-out result. Return one coherent "
    "patch with independent original targets, not a ranking or a selected first "
    "patch. Explicitly record omitted or reconciled conflicts in reasoning and "
    "changelog_entries. Empty edits are allowed when nothing defensible remains."
)

TRANSLATOR_ROLE = COMMON_ROLE + (
    " Translate the one consolidated patch into exact edits of the supplied "
    "immutable initial files. Preserve its substantive lessons. Resolve the "
    "proposed locations to unique original headings or exact text and ensure "
    "independent edit locations and atomic reference/link pairs. Do not add "
    "new legal lessons, inspect a new case, or evaluate performance. This is "
    "the single planned patch-translation stage, not a failed-output retry."
)
