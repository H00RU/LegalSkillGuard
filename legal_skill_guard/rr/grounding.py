"""Public literal audit; no labels, references or inference of missing facts."""
import re
from fractions import Fraction
from .coverage import SourceLedger
from .scoring import LABELS

def _numbers(text):
    values = set()
    for match in re.finditer(r"(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\w|\.\d)", text):
        values.add(Fraction(match[0].replace(",", "")))
    return values


def _walk(node):
    yield node
    if isinstance(node, dict):
        for child in node.values():
            yield from _walk(child)
    elif isinstance(node, list):
        for child in node:
            yield from _walk(child)


def source_grounding(text, dataset, proposal):
    ledger = SourceLedger.from_text(text)
    units = {c.id: ledger.text[c.start:c.end] for c in ledger.clauses}
    body = proposal["program"]["body"]
    checks = []
    names = {b["name"] for b in body.get("bindings", [])}
    program_tree = body.get("query", body.get("candidates", []))
    referenced = {n.get("var", n.get("slot")) for n in _walk(program_tree)
                  if isinstance(n, dict) and ("var" in n or "slot" in n)}
    checks.append({"check": "uses_extracted_input_not_answer_literal", "pass": bool(names & referenced)})
    linked_units = {b["source"] for b in body.get("bindings", [])} | set(body.get("source_links", {}))
    linked_text = "\n".join(units.get(k, "") for k in linked_units)
    permitted_strings = {"EC", "EV", "citation", "claim_value"} | set(LABELS.get(dataset, ()))
    def query_literals(node):
        if isinstance(node, dict) and set(node) == {"var"}:
            return []
        if isinstance(node, dict):
            return [v for arg in node.get("args", []) for v in query_literals(arg)]
        if isinstance(node, list):
            return [v for arg in node for v in query_literals(arg)]
        return [node]
    literal_checks = []
    for value in query_literals(body.get("query", {})):
        if type(value) is int:
            literal_checks.append(value in (0, 1) or Fraction(value) in _numbers(linked_text))
        elif isinstance(value, str):
            literal_checks.append(value in permitted_strings or value.casefold() in linked_text.casefold())
        elif type(value) is bool:
            literal_checks.append(True)
        else:
            literal_checks.append(False)
    checks.append({"check": "query_literals_are_public_or_fixed_task_or_logic_symbols", "pass": all(literal_checks)})
    for binding in body.get("bindings", []):
        unit = units.get(binding["source"], "")
        kind, value = binding["type"], binding["value"]
        ok, basis = False, "unverified_public_literal"
        if kind in {"integer", "rational"} or kind == "scalar" and type(value) is int:
            try:
                ok = Fraction(str(value)) in _numbers(unit)
            except ValueError:
                ok = False
            basis = "exact_numeric_literal_in_cited_public_unit"
        elif kind == "scalar" and isinstance(value, str):
            ok = bool(value) and value.casefold() in unit.casefold()
            basis = "scalar_text_in_cited_public_unit"
        elif kind == "scalar" and type(value) is bool:
            ok = re.search(r"\b" + str(value).lower() + r"\b", unit, re.I) is not None
            basis = "explicit_public_boolean_only_no_inferred_truth"
        elif kind == "relation":
            ok = all(isinstance(cell, str) and cell.casefold() in unit.casefold()
                     for row in value["rows"] for cell in row)
            basis = "public_entity_witnesses_checked_by_shared_decoder"
        elif kind == "amounts":
            ok = all(Fraction(a["value"]) in _numbers(unit) for a in value)
            basis = "amounts_quoted_in_cited_public_unit"
        elif kind == "allowance_bank":
            ok = all(Fraction(a["balance"]) in _numbers(unit) for a in value)
            basis = "allowance_values_quoted_in_cited_public_unit"
        elif kind == "resource_key":
            ok = all(v.casefold() in unit.casefold() for v in value)
            basis = "resource_key_components_in_public_unit"
        elif kind == "slot_list":
            ok = all(v in names for v in value)
            basis = "references_existing_extracted_inputs"
        checks.append({"binding": binding["name"], "source": binding["source"],
                       "pass": ok, "basis": basis})
    return {"pass": all(c["pass"] for c in checks), "checks": checks,
            "scope": "public_literal_grounding_and_original_TRAIN_reference_check_not_universal_NL_equivalence"}

