"""Joint source compiler proposal contract, deterministic execution and fallback.

No grader or oracle is imported here. A model's scope assertion cannot erase an
uncompiled source unit; finite connector agreement does not certify Ω.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction

import jsonschema

from .coverage import FiniteTheory, SourceLedger, Unsupported, certificate, complete, evaluate
from .interfaces import AllowanceBank, Amount, Connector, ConnectorPool, InterfaceError, Relation
from .learning import parameterize_graph
from .public_horn import parse_public
from .scoring import LABELS
from .strict_contract import strict_proposal_schema as _strict_proposal_schema

PROPOSAL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["answer", "program", "compiled_units", "unsupported_units", "interfaces"],
    "properties": {
        "answer": {"anyOf": [{"type": "string"}, {"type": "integer"},
                               {"type": "object", "additionalProperties": True}, {"type": "null"}]},
        "program": {"type": "object", "additionalProperties": False, "required": ["kind", "body"],
                    "properties": {"kind": {"enum": ["expression", "connector", "unsupported"]},
                                   "body": {"type": "object", "additionalProperties": True}}},
        "compiled_units": {"type": "array", "items": {"type": "string"}},
        "unsupported_units": {"type": "array", "items": {"type": "string"}},
        "interfaces": {"type": "array", "maxItems": 8, "items": {
            "type": "object", "additionalProperties": True}},
    }}


def source_text(source: dict) -> str:
    public, dataset = source["public"], source["dataset"]
    if dataset == "ProofWriter_OWA_depth5":
        return "\n".join(public["facts"] + public["rules"] + [public["query"]])
    if dataset == "OpenExempt":
        return public["views"]["EC"] + "\n\n" + public["views"]["EV"]
    if dataset == "ContractNLI":
        return public["document"] + "\n\n" + public["query"]
    if dataset == "RuleArena_Airline":
        return public["rules"] + "\n\n" + public["prompt"]
    return public["rules"] + "\n\n" + public["facts"] + "\n\n" + public["query"]


def _native(value):
    if isinstance(value, Fraction):
        return value.numerator if value.denominator == 1 else float(value)
    if isinstance(value, list):
        return [_native(v) for v in value]
    if isinstance(value, dict):
        return {k: _native(v) for k, v in value.items()}
    if value is None or type(value) in (bool, str, int, float):
        return value
    raise Unsupported("Structured task output needs an explicit native projection")


def _exact_json_answer(value) -> bool:
    if isinstance(value, Fraction):
        return Fraction(str(_native(value))) == value
    if isinstance(value, dict):
        return all(_exact_json_answer(v) for v in value.values())
    if isinstance(value, list):
        return all(_exact_json_answer(v) for v in value)
    return True


def valid_answer(dataset: str, answer) -> bool:
    if dataset in LABELS:
        return isinstance(answer, str) and answer in LABELS[dataset]
    if dataset == "RuleArena_Airline":
        return type(answer) is int and answer >= 0
    if dataset == "OpenExempt":
        if not isinstance(answer, dict) or set(answer) != {"EC", "EV"}:
            return False
        from legal_skill_guard.openexempt import answer_schema
        try:
            for family in ("EC", "EV"):
                jsonschema.validate(answer[family], answer_schema(family))
        except jsonschema.ValidationError:
            return False
        return True
    return False


def decode_slots(body: dict, unit_ids: set[str], source_units: dict[str, str]) -> tuple[dict, set[str]]:
    slots, sources = {}, set()
    for binding in body.get("bindings", []):
        if set(binding) != {"name", "value", "type", "source"} or binding["source"] not in unit_ids:
            raise ValueError("Each binding requires current-source provenance")
        name, kind, value = binding["name"], binding["type"], binding["value"]
        if not isinstance(name, str) or name in slots:
            raise ValueError("Duplicate or invalid role slot")
        if kind == "rational":
            value = Fraction(str(value))
        elif kind == "integer":
            if type(value) is not int:
                raise ValueError("Integer slot type mismatch")
        elif kind == "scalar":
            if type(value) not in (str, bool, int):
                raise ValueError("Scalar slot type mismatch")
        elif kind == "relation":
            if set(value) != {"columns", "rows", "closed"} or type(value["closed"]) is not bool:
                raise ValueError("Relation needs explicit columns, rows and input closure")
            value = Relation(tuple(value["columns"]), tuple(tuple(r) for r in value["rows"]), value["closed"])
            for row in value.rows:
                for cell in row:
                    if not isinstance(cell, str) or not cell or not re.search(
                            r"(?<!\w)" + re.escape(cell) + r"(?!\w)",
                            source_units[binding["source"]], re.I):
                        raise ValueError("Entity witness is absent from the cited public input")
        elif kind == "amounts":
            value = [Amount(a["value"], a["unit"], a["owner"], a["period"],
                            frozenset(a["lineage"]), a["stage"]) for a in value]
        elif kind == "allowance_bank":
            bank = AllowanceBank()
            for entry in value:
                if set(entry) != {"key", "balance", "policy", "order_observable"}:
                    raise ValueError("Allowance needs an explicit key, balance, policy and order semantics")
                bank.create(tuple(entry["key"]), entry["balance"], policy=entry["policy"],
                            order_observable=entry["order_observable"])
            value = bank
        elif kind == "resource_key":
            if not isinstance(value, list) or len(value) != 3 or not all(isinstance(v, str) for v in value):
                raise ValueError("Resource key is (rule, owner, period)")
            value = tuple(value)
        elif kind == "slot_list":
            if not isinstance(value, list) or any(name not in slots for name in value):
                raise ValueError("Slot list cannot recover values that were not extracted")
            value = [slots[name] for name in value]
        else:
            raise ValueError("Unsupported typed role slot")
        slots[name] = value
        sources.add(binding["source"])
    return slots, sources


def _program(program: dict, unit_ids: set[str], source_units: dict[str, str]) -> dict:
    kind, body = program["kind"], program["body"]
    if kind == "unsupported":
        return {"status": "unsupported_no_certificate", "candidate_answer": None, "covered": set()}
    slots, binding_sources = decode_slots(body, unit_ids, source_units)
    links = body.get("source_links", {})
    if not isinstance(links, dict) or not set(links) <= unit_ids:
        raise ValueError("Program has dangling source links")
    if any(not isinstance(v, list) or not v for v in links.values()):
        raise ValueError("Each source link must identify one or more semantic nodes")
    known_nodes = {"query"} | {f"binding:{name}" for name in slots}
    if kind == "expression":
        if set(body) - {"bindings", "query", "source_links"}:
            raise ValueError("Unknown expression program fields")
        query = body["query"]
        if not isinstance(query, dict) or "op" not in query or not slots:
            raise ValueError("A copied answer literal is not a rule compilation")
        from .ir_types import check_expression
        check_expression(body, slots)
        value = evaluate(query, slots)
        status = "executed_expression"
    elif kind == "connector":
        if set(body) - {"bindings", "candidates", "source_links", "project"}:
            raise ValueError("Unknown connector program fields")
        pool = ConnectorPool([Connector(graph) for graph in body["candidates"]])
        known_nodes |= {f"connector:{i}" for i in range(len(pool.candidates))}
        mode = body.get("project", "identity")
        def project(v):
            if mode == "amount_value" and isinstance(v, Amount):
                return v.value
            if mode == "identity":
                return v
            raise InterfaceError("Unknown or inapplicable output projection")
        result = pool.predict(slots, project=project)
        value, status = result["answer"], result["status"]
    else:
        raise ValueError("Unsupported program kind")
    if any(not set(nodes) <= known_nodes for nodes in links.values()):
        raise ValueError("Source link names a missing program node")
    return {"status": status, "candidate_answer": _native(value),
            "covered": binding_sources | set(links), "slots": slots,
            "execution_states": result.get("execution_states", []) if kind == "connector" else []}


def _decode_proposal(content: str) -> dict:
    """Bound untrusted syntax before invoking recursive JSON/IR consumers."""
    if len(content) > 1_048_576:
        raise ValueError("Proposal exceeds bounded JSON size")
    depth, quoted, escaped = 0, False, False
    for char in content:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > 64:
                raise ValueError("Proposal exceeds bounded JSON nesting depth (64)")
        elif char in "]}":
            depth -= 1
    return json.loads(content)


def analyze(source: dict, content: str) -> dict:
    ledger = SourceLedger.from_text(source_text(source))
    unit_ids = {c.id for c in ledger.clauses}
    source_units = {c.id: ledger.text[c.start:c.end] for c in ledger.clauses}
    result = {"structural_pass": False, "answer": None, "program_status": "parse_failure",
              "certificate_status": "translation_unresolved", "source_ledger_hash": ledger.version,
              "residual_units": sorted(unit_ids), "interfaces": [], "diagnostics": []}
    try:
        proposal = _decode_proposal(content)
        jsonschema.validate(proposal, PROPOSAL_SCHEMA)
        declared = set(proposal["compiled_units"])
        unsupported = set(proposal["unsupported_units"])
        if not (declared | unsupported) <= unit_ids or declared & unsupported:
            raise ValueError("Unknown or contradictory source coverage declarations")
        result["structural_pass"] = valid_answer(source["dataset"], proposal["answer"])
        result["answer"] = proposal["answer"] if result["structural_pass"] else None
        result["interfaces"] = proposal["interfaces"]
        result["proposal"] = proposal
        for interface in result["interfaces"]:
            if set(interface) != {"fields", "graph", "bindings"}:
                raise ValueError("Interface proposal needs fixed fields, graph and source-linked bindings")
            from .interfaces import FIELDS
            if not isinstance(interface["fields"], list) or not set(interface["fields"]) <= set(FIELDS):
                raise ValueError("Forbidden or unknown interface field")
            parameterize_graph(interface["graph"])
            decode_slots(interface, unit_ids, source_units)
        try:
            program = _program(proposal["program"], unit_ids, source_units)
        except (ValueError, TypeError, KeyError, Unsupported, InterfaceError) as exc:
            result["program_status"] = "invalid_IR"
            result["diagnostics"].append(str(exc))
            program = {"covered": set(), "candidate_answer": None, "status": "invalid_IR"}
        result["program_status"] = program["status"]
        result["model_IR_pass"] = program["status"] != "invalid_IR"
        result["structural_pass"] = result["structural_pass"] and result["model_IR_pass"]
        result["candidate_answer"] = program["candidate_answer"]
        result["execution_states"] = program.get("execution_states", [])
        accepted = declared & program["covered"]
        for i, clause in enumerate(ledger.clauses):
            if clause.id in accepted:
                ledger.clauses[i] = replace(clause, state="compiled")
        residual = unit_ids - accepted
        result["residual_units"] = sorted(residual)
        result["source_ledger_hash"] = ledger.version
        result["source_ledger_snapshot"] = [asdict(c) for c in ledger.clauses]
        if source["dataset"] == "ProofWriter_OWA_depth5":
            trusted = parse_public(source["public"])
            assessment = trusted.assess(lambda ids: len(ids), 32768)
            result["public_grammar_assessment"] = assessment
            if assessment["status"] == "completion_stable":
                result["answer"] = assessment["answer"]
                result["certificate_status"] = "completion_stable"
                result["residual_units"] = list(trusted.residuals)
                result["source_ledger_hash"] = trusted.ledger.version
                result["source_ledger_snapshot"] = [asdict(c) for c in trusted.ledger.clauses]
                result["certificate_basis"] = "complete_restricted_public_grammar_not_connector_H"
                result["structural_pass"] = True
                return result
        if source["dataset"] == "ContractNLI" or unsupported or program["status"] == "unsupported_no_certificate":
            result["certificate_status"] = "unsupported_no_certificate"
        elif not residual and program["status"] == "executed_expression" and \
                valid_answer(source["dataset"], program["candidate_answer"]):
            # There are no remaining source choices only after accepted linked
            # translations close every source unit. This is conditional on NL
            # translation faithfulness, never inferred from H agreement.
            theory = FiniteTheory(ledger, program["slots"], {}, proposal["program"]["body"]["query"], [],
                                  containment_assumptions=("accepted source-linked translation is faithful",))
            checked = complete(theory)
            if checked.status == "completion_stable" and _exact_json_answer(checked.answer):
                result["certificate_status"] = checked.status
                result["answer"] = _native(checked.answer)
                result["certificate"] = certificate(theory, checked)
            elif checked.status == "completion_stable":
                result["certificate_status"] = "unsupported_no_certificate"
                result["diagnostics"].append("Exact rational would require rounding in the native JSON answer")
        result["fallback_used"] = result["certificate_status"] != "completion_stable"
        result["fallback_policy"] = "same_request_native_answer_no_extra_training_fallback_call"
    except (ValueError, TypeError, KeyError, RecursionError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        result["structural_pass"] = False
        result["diagnostics"].append(str(exc)[:2000])
    return result


def messages(source: dict, *, previous: dict | None = None) -> list[dict]:
    ledger = SourceLedger.from_text(source_text(source))
    numbered = "\n".join(f"[{c.id}] {ledger.text[c.start:c.end]}" for c in ledger.clauses)
    contract = {"OpenExempt": 'object with EC and EV; each is the asset mapping requested in its public view',
                "RuleArena_Airline": 'integer total cost', "SARA_v2_Binary": '"Entailment" or "Contradiction"',
                "ProofWriter_OWA_depth5": '"True", "False", or "Unknown"',
                "ContractNLI": '"Entailment", "Contradiction", or "NotMentioned"'}[source["dataset"]]
    instruction = (
        "Solve the supplied rule-constrained task. Return short JSON matching the response schema. "
        "Jointly propose an executable rule sketch and any entity/group/usage interface. "
        "Do not omit exceptions. A compiled unit needs a source link to a binding or query; "
        "unlisted units remain residual. Do not claim unsupported text is compiled. "
        "program.kind is expression, connector, or unsupported. For expression body use "
        "bindings [{name,value,type,source}], query {op,args}, source_links {unit:[node]}. "
        "Types: integer, rational (decimal string), scalar. Connectors also accept relation "
        "{columns,rows,closed}, amounts (value,unit,owner,period,lineage,stage), allowance_bank "
        "(entries key,balance,policy,order_observable), resource_key, slot_list. "
        "Do not invent entity witnesses or guess allocation policies. A variable is {var:name}. "
        "Operators: if,and,or,not,eq,ne,lt,le,add,sub,min,max,scale (literal constant first), "
        "divide_constant (literal denominator), array,pair,object,concat. No arbitrary code. "
        "Bind observed values and rule constants from public source units. Node names are "
        "query and binding:NAME. Use unsupported with empty body when faithful executable "
        "translation is unavailable. Always give your task answer in answer; this fixed "
        "fallback has no stability certificate. Interface proposals may describe a source-linked "
        "join/group/map/reduce graph, but never use source IDs or answers as routing features. "
        "Each interfaces entry has exactly fields (allowed semantic field names), graph (connector DSL), "
        "and bindings (same source-linked binding format); use [] when unavailable. "
        "Do not store case amounts or names as reusable skill constants. "
        "Answer contract: " + contract)
    user = "Public benchmark: " + source["dataset"] + "\n" + numbered
    if previous is not None:
        # Repair evidence comes only from this source's previous proposal and
        # mechanical diagnostics, never grader labels or reference programs.
        user += "\nOne remaining joint repair/translation call. Previous public-output diagnostics:\n" + \
            json.dumps({k: previous.get(k) for k in ["proposal", "program_status", "residual_units", "diagnostics"]}, ensure_ascii=False)
    return [{"role": "system", "content": instruction}, {"role": "user", "content": user}]


def reusable_inputs(source: dict, previous: dict | None) -> list[dict]:
    if previous is None or source['dataset'] not in ('OpenExempt', 'RuleArena_Airline', 'SARA_v2_Binary'):
        return []
    proposal = previous.get('proposal', {})
    if proposal.get('program', {}).get('kind') != 'expression':
        return []
    body = proposal['program']['body']
    bindings = body.get('bindings', [])
    if not bindings:
        return []
    from .grounding import source_grounding
    ledger = SourceLedger.from_text(source_text(source))
    units = {c.id: ledger.text[c.start:c.end] for c in ledger.clauses}
    try:
        decode_slots(body, set(units), units)
        checks = [c for c in source_grounding(ledger.text, source['dataset'], proposal)['checks'] if 'binding' in c]
        if len(checks) != len(bindings) or not all(c['pass'] for c in checks):
            return []
    except (ValueError, KeyError, TypeError, InterfaceError):
        return []
    return deepcopy(bindings)


def proposal_schema(dataset: str, *, source: dict | None = None, previous: dict | None = None) -> dict:
    """Source-bound strict contract for new calls; preserve legacy replay API.

    Source-free calls retain the historical contract needed to reproduce old
    sealed stages. Current strict repair and formal entry points pass source.
    """
    schema = deepcopy(PROPOSAL_SCHEMA)
    if dataset == "OpenExempt":
        from legal_skill_guard.openexempt import answer_schema
        schema["properties"]["answer"] = {"anyOf": [
            {"type": "object", "additionalProperties": False, "required": ["EC", "EV"],
             "properties": {family: answer_schema(family) for family in ("EC", "EV")}},
            {"type": "null"}]}
    if source is None:
        return schema
    ledger = SourceLedger.from_text(source_text(source))
    units = [c.id for c in ledger.clauses]
    schema = _strict_proposal_schema(dataset, schema, source_unit_ids=units)
    if 'expression_binding' in schema.get('$defs', {}):
        # Match the existing grounding check: inferred/assumed truth is not an input literal.
        branches = schema['$defs']['expression_binding']['anyOf']
        boolean_branch = next(b for b in branches if b['properties']['value'].get('type') == 'boolean')
        branches.remove(boolean_branch)
        available = False
        for value in (True, False):
            witnesses = [c.id for c in ledger.clauses if re.search(
                r'\b' + str(value).lower() + r'\b', ledger.text[c.start:c.end], re.I)]
            if witnesses:
                branch = deepcopy(boolean_branch)
                branch['properties']['value'] = {'enum': [value]}
                branch['properties']['source'] = {'enum': witnesses}
                branches.append(branch)
                available = True
        if not available:
            for name, definition in schema['$defs'].items():
                if name.startswith('boolean_expression_'):
                    definition['anyOf'] = [arm for arm in definition['anyOf'] if 'var' not in arm.get('properties', {})]
    bindings = reusable_inputs(source, previous)
    if bindings:
        from .strict_contract import close_expression_inputs
        schema = close_expression_inputs(schema, bindings)
    return schema


def wire_messages(source: dict, *, previous: dict | None = None) -> list[dict]:
    # These two adapters retain their existing public-Horn/native-fallback contract.
    # Numeric/label/EC-EV format examples apply only to the three strict adapters.
    from .strict_contract import TARGETS
    if source['dataset'] not in TARGETS:
        return messages(source, previous=previous)
    from .compiler_prompt import compiler_instructions
    prompt = messages(source)
    prompt[0]["content"] += compiler_instructions(source['dataset'])
    if previous is not None:
        prompt[1]["content"] += "\nPrevious mechanical diagnostics (compile from public text, not from the old answer):\n" + \
            json.dumps({k: previous.get(k) for k in ["program_status", "diagnostics"]}, ensure_ascii=False)
    bindings = reusable_inputs(source, previous)
    if bindings:
        prompt[1]['content'] += (
            '\nPreviously extracted input literals have verified public quotations. Preserve these bindings exactly. '
            'Construct the rule program again from public text. No previous answer or rule program is supplied. '
            'Use their declared variables; quote additional rule constants in the query with source links. '
            'These bindings do not establish completeness of the asset list or truth of the query. Bindings: '
            + json.dumps(bindings, ensure_ascii=False))
    if source['dataset'] == 'RuleArena_Airline':
        prompt[0]['content'] += (
            '\nThe original Airline task asks for the total travel cost, including the supplied flight ticket '
            'and all applicable checked baggage fees. The invented syntax example does not redefine this task.')
    elif source['dataset'] == 'SARA_v2_Binary':
        prompt[0]['content'] += (
            '\nThe SARA task is to evaluate the exact claim supplied as query under the supplied rules and facts. '
            'Entailment means that claim follows; Contradiction means that claim is false in this binary task. '
            'The query is the proposition to classify, not an additional fact. Do not substitute another legal question.')
        prompt[1]['content'] += '\nExact claim to classify (verbatim public query): ' + json.dumps(source['public']['query'], ensure_ascii=False)
    if source["dataset"] == "OpenExempt":
        prompt[0]["content"] += (
            "\nThe two public views describe fields inside answer.EC and answer.EV. "
            "Return both views in the outer proposal. EC maps each actual public asset description "
            "to citation strings. EV maps each actual public asset description to an array of "
            "{citation: string, claim_value: number}. Use [] for assets with no applicable claims. "
            "The native answer schema is: " + json.dumps(proposal_schema("OpenExempt")["properties"]["answer"]))
    return prompt
