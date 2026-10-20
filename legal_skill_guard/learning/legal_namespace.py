"""Public-namespace contract for the next separately frozen training protocol.

These helpers read the explicitly supplied AE solved step, public statutory
headers, and optional literal asset mentions from a declared public lexicon.
They neither infer ownership nor decide legal eligibility or numerical amounts.
All arms must receive the same public label vocabulary. No answer repair.
The optional asset lexicon is a description-only projection of CC BY 4.0
servantez/OpenExempt ec6fa2547431096588ce2d3ef107b8adc33cd4fe; the source's
expert exemption, value and category-hint fields do not enter the encoding.
"""

from __future__ import annotations

import copy
import json
import re

from legal_skill_guard.learning.claim_execution import law_blocks

PREFIXES = {
    "FEDERAL": "11 U.S.C.",
    "ARIZONA": "Ariz. Rev. Stat.",
    "ILLINOIS": "735 Ill. Comp. Stat.",
    "OREGON": "Or. Rev. Stat.",
    "PENNSYLVANIA": "42 Pa. Cons. Stat.",
    "WISCONSIN": "Wis. Stat.",
}
SCOPES = ("ALL", *PREFIXES)
PRIOR = re.compile(
    r"The Debtors? may claim property exemptions under (.+) statutes\.", re.I
)


def allowable_namespaces(row: dict) -> frozenset[str]:
    """Use the given AE result, never domicile inference or hidden Case fields."""
    matches = [m for line in row["components"]["solved_steps"].splitlines()
               if (m := PRIOR.fullmatch(line.strip()))]
    if len(matches) != 1:
        raise ValueError("Exactly one explicit public AE solved step is required")
    names = matches[0][1].upper().split(" AND ")
    if not names or len(names) != len(set(names)) or set(names) - PREFIXES.keys():
        raise ValueError("Unknown or ambiguous public allowable-law namespace")
    return frozenset(names)


def citation_namespace(citation: str) -> str:
    matches = [name for name, prefix in PREFIXES.items()
               if citation.startswith(prefix + " ")]
    if len(matches) != 1:
        raise ValueError("Unknown public citation namespace: " + citation)
    return matches[0]


def statutory_catalog(statutes: str) -> dict[str, str]:
    """Readable ASCII citations, not a second opaque law-numbering task.

    Only the section sign changes spelling for the serving grammar. All legal
    names/numbers remain visible and decoding is a predeclared bijection, not
    post-answer normalization. No targets or private statute metadata are read.
    """
    citations = law_blocks(statutes)
    catalog = {citation.replace("§", "section"): citation for citation in citations}
    if len(catalog) != len(citations) or any(not key.isascii() for key in catalog):
        raise ValueError("Public citation references must be unique readable ASCII")
    return catalog


def public_catalog(row: dict) -> dict[str, str]:
    """Readable ASCII labels for all public headers in the given legal namespace.

    Spell references before filtering so they retain their meaning across cases.
    Do not filter by expert annotations, exemption truth or reference answers.
    """
    allowed = allowable_namespaces(row)
    catalog = {reference: citation
               for reference, citation in statutory_catalog(row["components"]["statutes"]).items()
               if citation_namespace(citation) in allowed}
    if not catalog:
        raise ValueError("No public statutory labels for the supplied AE result")
    return catalog


def asset_description_lexicon() -> tuple[str, ...]:
    """Description-only projection; expert labels/values are never consulted."""
    from legal_skill_guard.openexempt import UPSTREAM

    with (UPSTREAM / "data/assets/assets.jsonl").open() as source:
        names = [json.loads(line)["description"] for line in source if line.strip()]
    if not names or any(not isinstance(name, str) or not name for name in names):
        raise ValueError("A nonempty declared public asset-description lexicon is required")
    return tuple(sorted(set(names)))


def public_asset_catalog(row: dict) -> dict[str, str]:
    """Case-local IDs for maximal literal public mentions, not owned/eligible assets.

    This closed-vocabulary input encoding adds mention boundaries to ALL arms.
    It does not promise to recognize out-of-vocabulary entities. Repeated literal
    names share one map key, like the benchmark's description-keyed answer.
    """
    facts = row["components"]["facts"]
    spans = {(match.start(), match.end(), match.group())
             for name in asset_description_lexicon()
             for match in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", facts, re.I)}
    maximal = sorted((start, end, text) for start, end, text in spans
        if not any(a <= start and end <= b and (a, b) != (start, end) for a, b, _ in spans))
    mentions = {}
    for _, _, text in maximal:
        mentions.setdefault(text.casefold(), text)
    if not mentions:
        raise ValueError("No literal public asset mention; no guess, target lookup or fallback")
    return {f"A{index:03d}": text for index, text in enumerate(mentions.values(), 1)}


def decode_asset_references(answer: dict, catalog: dict[str, str]) -> dict:
    """Invert the predeclared public encoding; never fill, normalize or judge values."""
    if not isinstance(answer, dict) or set(answer) != set(catalog):
        raise ValueError("Submit exactly the declared public asset-reference keys")
    return {catalog[key]: copy.deepcopy(values) for key, values in answer.items()}


def validate_scopes(bank: list[dict], statutes: str) -> None:
    """Validate only reference types, not whether an exemption legally applies."""
    public = law_blocks(statutes)
    for skill in bank:
        guidance = skill["guidance"]
        scope = guidance["jurisdiction"]  # Explicit for every newly authored skill.
        if scope not in SCOPES:
            raise ValueError("Unknown declared skill jurisdiction")
        for operator in guidance["operators"]:
            citation = operator["citation"]
            if citation not in public or citation_namespace(citation) != scope:
                raise ValueError("Operator and declared legal namespace disagree")


def compile_seed_scopes(bank: list[dict], statutes: str, *,
                        shared_skill_ids: set[str]) -> list[dict]:
    """One-time explicit migration of the existing law-only seed, not fallback.

    The caller declares genuinely shared seed guidance. Every other seed record
    must have a unique public namespace witnessed by its existing operators.
    Future teacher-authored records must declare jurisdiction directly instead.
    """
    result = copy.deepcopy(bank)
    if shared_skill_ids - {s["id"] for s in result}:
        raise ValueError("A declared shared seed skill is absent")
    for skill in result:
        guidance = skill["guidance"]
        if "jurisdiction" in guidance:
            raise ValueError("Seed scope migration must not be applied twice")
        operators = guidance["operators"]
        if skill["id"] in shared_skill_ids:
            if operators:
                raise ValueError("Shared seed policy must not own state-law operators")
            scope = "ALL"
        else:
            namespaces = {citation_namespace(op["citation"]) for op in operators}
            if len(namespaces) != 1:
                raise ValueError("Seed needs an explicit, unique public scope")
            scope = namespaces.pop()
        guidance["jurisdiction"] = scope
    validate_scopes(result, statutes)
    return result


def active_bank(row: dict, bank: list[dict]) -> list[dict]:
    """Exact public precondition matching; no semantic router or rescue path."""
    allowed = allowable_namespaces(row) | {"ALL"}
    for skill in bank:
        if skill["guidance"]["jurisdiction"] not in SCOPES:
            raise ValueError("Unknown declared skill jurisdiction")
    return copy.deepcopy([s for s in bank
                          if s["guidance"]["jurisdiction"] in allowed])


def decode_reference(reference: str, catalog: dict[str, str]) -> str:
    """Ordinary predeclared class-label decoding, never citation normalization."""
    if not isinstance(reference, str) or reference not in catalog:
        raise ValueError("Unknown submitted public-law label")
    return catalog[reference]


def decode_classification(answer: dict, catalog: dict[str, str]) -> dict:
    return {asset: [decode_reference(ref, catalog) for ref in refs]
            for asset, refs in answer.items()}


def decode_claim_plan(plan: dict, catalog: dict[str, str]) -> dict:
    result = copy.deepcopy(plan)
    for asset in result["assets"]:
        for claim in asset["claims"]:
            if "citation" in claim:
                raise ValueError("Submit one public label, not two competing citation fields")
            claim["citation"] = decode_reference(claim.pop("citation_ref"), catalog)
    return result
