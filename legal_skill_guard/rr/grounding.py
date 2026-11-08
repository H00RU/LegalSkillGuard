"""Public literal audit; no labels, references or inference of missing facts."""
import re
from fractions import Fraction
from .coverage import SourceLedger
from .scoring import LABELS

_SMALL=dict(zip(('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen '
                 'fifteen sixteen seventeen eighteen nineteen').split(),range(20)))
_TENS=dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10)))
_CARDINAL_WORDS=[*_SMALL,*_TENS,'hundred','thousand','million','billion','minus','negative']
_CARDINAL_PATTERN=re.compile(r'(?<![\w-])(?:'+'|'.join(_CARDINAL_WORDS)+r')'
    r'(?:[ \t-]+(?:'+'|'.join([*_CARDINAL_WORDS,'and'])+r'))*(?![\w-])',re.I)


def _cardinal_value(words):
    """Exact ordinary cardinals through thousands; reject incomplete phrases.

    These are lexical numbers, not inferred amounts or legal conclusions.
    Larger scales and signed/ambiguous constructions stay unsupported.
    """
    def below_hundred(tokens):
        if len(tokens)==1:return _SMALL.get(tokens[0],_TENS.get(tokens[0]))
        if len(tokens)==2 and tokens[0] in _TENS and 0<_SMALL.get(tokens[1],0)<10:
            return _TENS[tokens[0]]+_SMALL[tokens[1]]
        return None
    def below_thousand(tokens):
        if len(tokens)>=2 and 0<_SMALL.get(tokens[0],0)<10 and tokens[1]=='hundred':
            tail=tokens[2:]
            if not tail:return 100*_SMALL[tokens[0]]
            if tail[0]=='and':tail=tail[1:]
            remainder=below_hundred(tail)
            return 100*_SMALL[tokens[0]]+remainder if remainder is not None and remainder>0 else None
        return below_hundred(tokens)
    if words.count('thousand')==1:
        at=words.index('thousand');head=below_thousand(words[:at]);tail=words[at+1:]
        if head is None or head==0:return None
        if not tail:return 1000*head
        if tail[0]=='and':tail=tail[1:]
        remainder=below_thousand(tail)
        return 1000*head+remainder if remainder is not None and remainder>0 else None
    return below_thousand(words)


def _numbers(text):
    values = set()
    for match in re.finditer(r"(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\w|\.\d)", text):
        values.add(Fraction(match[0].replace(",", "")))
    # Fee schedules state positions as 1st/2nd/3rd/5th. These are explicit
    # numerical literals, not a computed bag count or an inferred allowance.
    for match in re.finditer(r'\b([0-9]+)(st|nd|rd|th)\b',text,re.I):
        number=int(match[1]);suffix='th' if 11<=number%100<=13 else {1:'st',2:'nd',3:'rd'}.get(number%10,'th')
        if match[2].lower()==suffix:values.add(Fraction(number))
    if re.search(r'\bone[- ]half\b',text,re.I):values.add(Fraction(1,2))
    # Do not extract "one" from the already-supported fraction. Horizontal
    # whitespace only prevents separate cited lines forming a new number.
    cardinal_text=re.sub(r'\bone[- ]half\b',' ',text,flags=re.I)
    for match in _CARDINAL_PATTERN.finditer(cardinal_text):
        number=_cardinal_value(re.split(r'[ \t-]+',match[0].lower()))
        if number is not None:values.add(Fraction(number))
    return values


def _walk(node):
    yield node
    if isinstance(node, dict):
        for child in node.values():
            yield from _walk(child)
    elif isinstance(node, list):
        for child in node:
            yield from _walk(child)


def expression_literal_audit(node,linked_text,dataset,*,structural_keys=False,allow_system_null=False,numeric_field_addresses=False):
    """Internal record labels may be syntax only after noninterference proof.

    Default behavior preserves the original native-output literal audit. The
    compact compiler may enable labels ONLY for a definition outside the full
    query dependency closure; values and all reachable output keys stay checked.
    """
    permitted={'EC','EV','citation','claim_value'}|set(LABELS.get(dataset,()))
    symbols=[];checks=[];indices=[];conversions=[]
    def visit(value,path,is_key=False,numeric_syntax=None):
        if isinstance(value,dict) and set(value)=={'var'}:return
        if isinstance(value,dict):
            for i,arg in enumerate(value.get('args',[])):
                context='index' if value.get('op')=='number_at' and i==1 else \
                    'denominator' if value.get('op')=='divide_constant' and i==1 else \
                    'field_address' if value.get('op')=='number_field' and i==1 else None
                visit(arg,path+'.args['+str(i)+']',value.get('op')=='pair' and i==0,context)
        elif isinstance(value,list):
            for i,arg in enumerate(value):visit(arg,path+'['+str(i)+']')
        elif type(value) is str and structural_keys and is_key:
            symbols.append({'path':path,'symbol':value})
        elif type(value) is str and numeric_field_addresses and numeric_syntax=='field_address':
            symbols.append({'path':path,'symbol':value,'role':'numeric_record_field_address_not_output_text'})
        elif value is None and allow_system_null:checks.append(True)
        elif type(value) is int:
            if numeric_syntax=='index' and value>=0:
                indices.append({'path':path,'index':value});checks.append(True)
            elif numeric_syntax=='denominator' and (
                    value==100 and re.search(r'\bpercent(?:age)?\b',linked_text,re.I) or
                    value==2 and re.search(r'\bone[- ]half\b',linked_text,re.I)):
                conversions.append({'path':path,'denominator':value});checks.append(True)
            else:checks.append(value in (0,1) or Fraction(value) in _numbers(linked_text))
        elif isinstance(value,str):checks.append(value in permitted or value.casefold() in linked_text.casefold())
        elif type(value) is bool:checks.append(True)
        else:checks.append(False)
    visit(node,'query')
    return {'check':'query_literals_are_public_or_fixed_task_or_logic_symbols',
            'pass':all(checks),**({'internal_noninterfering_record_symbols':symbols} if symbols else {}),
            **({'structural_numeric_vector_indices':indices} if indices else {}),
            **({'explicit_source_unit_conversions':conversions} if conversions else {})}


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

