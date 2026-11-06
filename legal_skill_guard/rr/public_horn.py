"""Auditable restricted-English grammar over public ProofWriter text only.

Unmatched text remains a source obligation. There is no import or access to
reference representations, gold labels or proofs in this prediction module.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from .coverage import FiniteTheory, Residual, SourceLedger, complete, plan_batch
from .horn import Atom, Rule, closure

VERBS = {v: v + "s" for v in ("eat", "like", "need", "visit", "see", "chase")}
VERBS.update({v: v for v in tuple(VERBS.values())})


def _term(text: str, variables: dict[str, str]) -> str:
    term = text.strip().casefold().removeprefix("the ")
    if term in variables:
        return variables[term]
    if not re.fullmatch(r"[a-z]+(?: [a-z]+)*", term):
        raise ValueError("Outside the finite entity grammar")
    return term


def parse_atom(text: str, variables: dict[str, str] | None = None, *,
               inherited_subject: str | None = None) -> Atom:
    variables = {} if variables is None else variables
    text = text.strip().removesuffix(".")
    unary = re.fullmatch(r"(.+?) (?:is|are) (not )?([a-z]+)", text, re.I)
    if unary:
        return Atom(unary[3].casefold(), (_term(unary[1], variables),), unary[2] is None)
    verb_pattern = "|".join(sorted(VERBS, key=len, reverse=True))
    binary = re.fullmatch(rf"(.+?) (does not |do not )?({verb_pattern}) (.+)", text, re.I)
    if binary:
        return Atom(VERBS[binary[3].casefold()],
                    (_term(binary[1], variables), _term(binary[4], variables)), binary[2] is None)
    if inherited_subject and re.fullmatch(r"(?:not )?[a-z]+", text, re.I):
        return parse_atom(f"{inherited_subject} is {text}", variables)
    raise ValueError("Unparsed public atom")


def parse_rule(text: str, source: str) -> Rule:
    text = text.strip().removesuffix(".")
    generic = re.fullmatch(r"(?:All )?(.+?) (?:people|things) are (not )?([a-z]+)", text, re.I)
    if generic:
        adjectives = re.split(r",\s*| and ", generic[1].casefold())
        if not all(re.fullmatch("[a-z]+", a) for a in adjectives):
            raise ValueError("Unparsed generic-rule guard")
        return Rule(tuple(Atom(a, ("?x",)) for a in adjectives),
                    Atom(generic[3].casefold(), ("?x",), generic[2] is None), source)
    conditional = re.fullmatch(r"If (.+) then (.+)", text, re.I)
    if not conditional:
        raise ValueError("Unparsed public rule")
    body, head = conditional[1], conditional[2]
    variables = {}
    if re.search(r"\bsomeone\b", body, re.I):
        variables.update({"someone": "?x", "they": "?x"})
    if re.search(r"\bsomething\b", body, re.I):
        key = "?y" if variables else "?x"
        variables.update({"something": key, "it": key})
    clauses = re.split(r" and ", body)
    first = parse_atom(clauses[0], variables)
    subject = re.split(r" (?:is|are|eats?|likes?|needs?|visits?|sees?|chases?|does not) ", clauses[0], 1)[0]
    atoms = [first] + [parse_atom(c, variables, inherited_subject=subject) for c in clauses[1:]]
    return Rule(tuple(atoms), parse_atom(head, variables), source)


@dataclass
class PublicHorn:
    ledger: SourceLedger
    facts: set[Atom]
    rules: list[Rule]
    query: Atom | None
    residuals: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    residual_contracts: dict[str, dict] = field(default_factory=dict)

    def execute(self) -> dict:
        if self.query is None:
            return {"answer": None, "status": "translation_unresolved", "trace": []}
        return closure(self.facts, self.rules, self.query)

    def completion_theory(self) -> FiniteTheory:
        result = self.execute()
        if result["status"] != "closure_complete":
            answer = "__CONFLICT__" if result["status"] == "conflict" else None
        else:
            answer = result["answer"]
        domains, residuals = {}, []
        query = answer
        for source in self.residuals:
            slot = f"effect_{source}"
            # Query-level TOP: every allowed task answer/conflict, or no effect.
            # This is a sound coarse overapproximation, not a candidate program
            # list. Unknown scope retains all outputs and cannot be discarded.
            contract = self.residual_contracts.get(source, {})
            domains[slot] = ("no_effect",) if contract.get("verified_query_irrelevant") else \
                ("no_effect", "True", "False", "Unknown", "__CONFLICT__")
            residuals.append(Residual(source, (slot,), "public_structure", False))
            query = {"op": "if", "args": [
                {"op": "eq", "args": [{"var": slot}, "no_effect"]}, query, {"var": slot}]}
        if self.query is None:
            # Even without residual rules, a missing query interpretation is a
            # genuine unresolved source obligation, not the task label Unknown.
            if not residuals:
                raise ValueError("Missing query has no registered obligation")
        return FiniteTheory(self.ledger, {}, domains, query, residuals,
                            containment_assumptions=("complete match of restricted public English grammar",))

    def assess(self, token_cost, budget: int) -> dict:
        theory = self.completion_theory()
        if not self.residuals and self.execute()["status"] != "closure_complete":
            return {"status": self.execute()["status"], "answer": None, "batch": []}
        result = complete(theory)
        if not self.residuals or result.status == "completion_stable":
            return {"status": result.status, "answer": result.answer, "batch": [],
                    "theory_hash": theory.version, "residual_contracts": self.residual_contracts}
        if any(not self.residual_contracts.get(s, {}).get("verified_query_irrelevant") for s in self.residuals):
            # Query-level TOP is adequate for conservative stability, but is
            # not a complete observation of a clause's extensional semantics.
            # Do not claim that observing one abstract answer-effect slot is a
            # separation-complete translation batch. Read all open source units.
            return {"status": result.status, "answer": None, "batch": list(self.residuals),
                    "planning_status": "conservative_full_source_no_separation_claim",
                    "theory_hash": theory.version, "residual_contracts": self.residual_contracts}
        plan = plan_batch(theory, token_cost, budget)
        selected = list(plan.selected)
        if plan.status in {"budget_exhausted", "conflict", "translation_unresolved"} and not selected:
            # Size/solver limits never discard source units. A conservative full
            # parse is an allowed action, without a minimum-cost certificate.
            selected = list(self.residuals)
        return {"status": result.status, "answer": None, "batch": selected,
                "planning_status": plan.status, "theory_hash": theory.version}


def parse_public(public: dict) -> PublicHorn:
    if public.get("answer_type") != "three_valued_owa":
        raise ValueError("This grammar applies only to public OWA inputs")
    units = [("fact", t) for t in public["facts"]] + [("rule", t) for t in public["rules"]] + [("query", public["query"])]
    if any("\n" in text or not text.strip() for _, text in units):
        raise ValueError("Each grammar unit must be one nonempty public sentence")
    ledger = SourceLedger.from_text("\n".join(t for _, t in units))
    result = PublicHorn(ledger, set(), [], None)
    for i, (kind, text) in enumerate(units):
        source = ledger.clauses[i].id
        try:
            if kind == "rule":
                result.rules.append(parse_rule(text, source))
            elif kind == "fact":
                atom = parse_atom(text)
                if any(a.startswith("?") for a in atom.arguments):
                    raise ValueError("Public fact is not ground")
                result.facts.add(atom)
            else:
                result.query = parse_atom(text)
        except ValueError as exc:
            result.residuals.append(source)
            result.errors[source] = str(exc)
        else:
            ledger.clauses[i] = replace(ledger.clauses[i], state="compiled")
    # Trusted *outer* Horn grammar can establish a write footprint while the
    # condition remains untranslated. No LLM scope proposal is trusted here.
    # Query dependencies include both polarities; no closed-world negation is
    # introduced by this relevance check.
    dependencies = {result.query.predicate} if result.query else set()
    effects = {}
    for source in result.residuals:
        c = next(c for c in ledger.clauses if c.id == source)
        text = ledger.text[c.start:c.end].removesuffix(".")
        match = re.fullmatch(r"If (.+) then (.+)", text, re.I)
        if not match or re.search(r"\b(if|then|unless|except|override)\b|[.;:]", match[1], re.I):
            continue
        try:
            head = parse_atom(match[2], {"someone": "?x", "something": "?x", "they": "?x", "it": "?x"})
        except ValueError:
            continue
        effects[source] = head.predicate
    # Unknown residual footprints can affect every predicate. They are never
    # removed; their own TOP still blocks any proposed stability certificate.
    changed = True
    while changed:
        before = set(dependencies)
        for rule in result.rules:
            if rule.head.predicate in dependencies:
                dependencies |= {a.predicate for a in rule.body}
        if set(result.residuals) - set(effects) or any(head in dependencies for head in effects.values()):
            # The unread body may read every predicate. Include residual-to-
            # residual dependency chains rather than proving irrelevance from
            # the already-compiled graph alone.
            dependencies |= {a.predicate for a in result.facts} | set(effects.values())
            dependencies |= {a.predicate for r in result.rules for a in r.body + (r.head,)}
        changed = before != dependencies
    for source, predicate in effects.items():
        result.residual_contracts[source] = {"evidence": "complete_outer_Horn_grammar",
            "writes": [predicate], "condition": "untranslated_TOP", "scope_verified": True,
            "verified_query_irrelevant": result.query is not None and predicate not in dependencies}
    return result
