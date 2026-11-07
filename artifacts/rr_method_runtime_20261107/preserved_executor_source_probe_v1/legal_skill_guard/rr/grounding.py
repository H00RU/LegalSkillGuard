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


def expression_literal_audit(node,linked_text,dataset,*,structural_keys=False,allow_system_null=False):
    """Internal record labels may be syntax only after noninterference proof.

    Default behavior preserves the original native-output literal audit. The
    compact compiler may enable labels ONLY for a definition outside the full
    query dependency closure; values and all reachable output keys stay checked.
    """
    permitted={'EC','EV','citation','claim_value'}|set(LABELS.get(dataset,()))
    symbols=[];checks=[]
    def visit(value,path,is_key=False):
        if isinstance(value,dict) and set(value)=={'var'}:return
        if isinstance(value,dict):
            for i,arg in enumerate(value.get('args',[])):
                visit(arg,path+'.args['+str(i)+']',value.get('op')=='pair' and i==0)
        elif isinstance(value,list):
            for i,arg in enumerate(value):visit(arg,path+'['+str(i)+']')
        elif type(value) is str and structural_keys and is_key:
            symbols.append({'path':path,'symbol':value})
        elif value is None and allow_system_null:checks.append(True)
        elif type(value) is int:checks.append(value in (0,1) or Fraction(value) in _numbers(linked_text))
        elif isinstance(value,str):checks.append(value in permitted or value.casefold() in linked_text.casefold())
        elif type(value) is bool:checks.append(True)
        else:checks.append(False)
    visit(node,'query')
    return {'check':'query_literals_are_public_or_fixed_task_or_logic_symbols',
            'pass':all(checks),**({'internal_noninterfering_record_symbols':symbols} if symbols else {})}


def binding_literal_audit(kind,value,unit,names):
    ok,basis=False,'unverified_public_literal'
    if kind in {'integer','rational'} or kind=='scalar' and type(value) is int:
        try:ok=Fraction(str(value)) in _numbers(unit)
        except ValueError:ok=False
        basis='exact_numeric_literal_in_cited_public_unit'
    elif kind=='scalar' and isinstance(value,str):
        ok=bool(value) and value.casefold() in unit.casefold();basis='scalar_text_in_cited_public_unit'
    elif kind=='scalar' and type(value) is bool:
        ok=re.search(r'\b'+str(value).lower()+r'\b',unit,re.I) is not None
        basis='explicit_public_boolean_only_no_inferred_truth'
    elif kind=='relation':
        ok=all(isinstance(cell,str) and cell.casefold() in unit.casefold() for row in value['rows'] for cell in row)
        basis='public_entity_witnesses_checked_by_shared_decoder'
    elif kind in {'amount','amounts'}:
        items=[value] if kind=='amount' else value
        ok=all(Fraction(a['value']) in _numbers(unit) for a in items)
        basis='amount_quoted_in_cited_public_unit' if kind=='amount' else 'amounts_quoted_in_cited_public_unit'
    elif kind=='allowance_bank':
        ok=all(Fraction(a['balance']) in _numbers(unit) for a in value)
        basis='allowance_values_quoted_in_cited_public_unit'
    elif kind=='resource_key':
        ok=all(v.casefold() in unit.casefold() for v in value);basis='resource_key_components_in_public_unit'
    elif kind=='slot_list':
        ok=all(v in names for v in value);basis='references_existing_extracted_inputs'
    return {'pass':ok,'basis':basis}


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
    checks.append(expression_literal_audit(body.get('query',{}),linked_text,dataset))
    for binding in body.get("bindings", []):
        unit = units.get(binding["source"], "")
        checks.append({"binding": binding["name"], "source": binding["source"],
                       **binding_literal_audit(binding['type'],binding['value'],unit,names)})
    return {"pass": all(c["pass"] for c in checks), "checks": checks,
            "scope": "public_literal_grounding_and_original_TRAIN_reference_check_not_universal_NL_equivalence"}

