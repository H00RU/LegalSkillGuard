"""Typed executable proposal wire contract; semantic checks stay in engine."""
from __future__ import annotations

from copy import deepcopy

from .interfaces import FIELDS

TARGETS = ("OpenExempt", "RuleArena_Airline", "SARA_v2_Binary")
EXPRESSION_DEPTH = 16  # JSON containers stay below the parser's64-level limit.
# The supplied Illinois statutes use canonical citations without a section sign.
# Preserve the JSON-string exclusions; a section sign is not a universal format.
CITATION_PATTERN = r'^(?:[^"\\\x00-\x1f]+§[^"\\\x00-\x1f]+|735 Ill\. Comp\. Stat\. [0-9]+/[0-9]+-[0-9]+(?:\([A-Za-z0-9]+\))*)$'


def obj(properties):
    return {"type": "object", "additionalProperties": False,
            "required": list(properties), "properties": properties}


def array(items):
    return {"type": "array", "items": items}


def ref(name):
    return {"$ref": "#/$defs/" + name}


def source_expression_operations(operators):
    """The actual expression checker's arities, also enforced during decoding."""
    from .ir_types import FIXED_ARITIES, NONEMPTY_OPERATORS
    groups={};special=[]
    for op in operators:
        if op=='if':
            args={'type':'array','prefixItems':[ref('bool_expr'),ref('expr'),ref('expr')],
                  'items':False,'minItems':3,'maxItems':3}
            special.append(obj({'op':{'enum':[op]},'args':args}))
        elif op=='number_field':
            special.append(obj({'op':{'enum':[op]},'args':{'type':'array',
                'prefixItems':[ref('expr'),ref('expr')],'items':False,'minItems':2,'maxItems':2}}))
        elif op in {'scale','divide_constant','ceil_divide_constant','number_at'}:
            literal={'type':'integer'}
            if op=='divide_constant':literal={'anyOf':[{'type':'integer','minimum':1},{'type':'integer','maximum':-1}]}
            elif op=='ceil_divide_constant':literal['minimum']=1
            elif op=='number_at':literal['minimum']=0
            items=[literal,ref('expr')] if op=='scale' else [ref('expr'),literal]
            special.append(obj({'op':{'enum':[op]},'args':{'type':'array','prefixItems':items,
                'items':False,'minItems':2,'maxItems':2}}))
        else:
            boolean=op in {'and','or','xor','not'}
            count=FIXED_ARITIES.get(op)
            minimum=count if count is not None else int(op in NONEMPTY_OPERATORS)
            groups.setdefault((minimum,count,boolean),[]).append(op)
    for (minimum,maximum,boolean),ops in groups.items():
        args={**array(ref('bool_expr' if boolean else 'expr')),'minItems':minimum}
        if maximum is not None:args['maxItems']=maximum
        special.append(obj({'op':{'enum':ops},'args':args}))
    return special


def type_enum_schemas(node):
    """Use the same explicit enum types in prompt and response-format schemas."""
    if isinstance(node,dict):
        if 'enum' in node and 'type' not in node:
            node['type']='integer' if all(type(v) is int for v in node['enum']) else 'string'
        for value in list(node.values()):type_enum_schemas(value)
    elif isinstance(node,list):
        for value in node:type_enum_schemas(value)


def bounded_expressions(definitions):
    """Bound expression/graph child edges; aliases consume no depth level."""
    names = set(definitions)
    def rewrite(node, depth, in_args=False):
        if isinstance(node, list):
            return [rewrite(v, depth, in_args) for v in node]
        if not isinstance(node, dict):
            return node
        if '$ref' in node and node['$ref'].split('/')[-1] in names:
            target = node['$ref'].split('/')[-1]
            remaining = depth - int(in_args)
            if remaining == 0 and target.endswith('operation'):
                return False
            return ref(f'{target}_{remaining}')
        result = {k: rewrite(v, depth, in_args or k in {'args', 'inputs'}) for k, v in node.items()}
        if result.get('type') == 'array' and result.get('items') is False and 'prefixItems' not in result:
            result['maxItems'] = 0
        return result
    result = {}
    for depth in range(EXPRESSION_DEPTH + 1):
        for name, definition in definitions.items():
            if depth == 0:
                if name.endswith('operation') or name == 'operation':
                    continue
                else:
                    atoms = [arm for arm in definition['anyOf'] if '$ref' not in arm and
                             'op' not in arm.get('properties', {})]
                    value = {'anyOf': atoms}
            else:
                value = rewrite(definition, depth)
            result[f'{name}_{depth}'] = value
    return result


def close_expression_inputs(schema, bindings):
    """Keep observed input values verbatim; query may refer only to these slots."""
    schema = deepcopy(schema)
    names = {b['name'] for b in bindings}
    numbers = {b['name'] for b in bindings if b['type'] in {'integer', 'rational'} or
               b['type'] == 'scalar' and type(b['value']) is int}
    strings = {b['name'] for b in bindings if b['type'] == 'scalar' and isinstance(b['value'], str)}
    booleans = {b['name'] for b in bindings if b['type'] == 'scalar' and type(b['value']) is bool}
    def constrain(node):
        if isinstance(node, list):
            return [constrain(n) for n in node]
        if not isinstance(node, dict):
            return node
        if set(node.get('properties', {})) == {'var'}:
            pattern = node['properties']['var'].get('pattern', '')
            available = numbers if pattern.startswith('^n_') else strings if pattern.startswith('^s_') else \
                booleans if pattern.startswith('^b_') else names
            return obj({'var': {'enum': sorted(available)}}) if available else None
        result = {k: constrain(v) for k, v in node.items()}
        if 'anyOf' in result:
            result['anyOf'] = [v for v in result['anyOf'] if v is not None]
        return result
    schema['$defs'] = constrain(schema['$defs'])
    literal_bindings = [obj({key: {'enum': [b[key]]} for key in ['name', 'type', 'value', 'source']}) for b in bindings]
    program = schema['properties']['program']['anyOf'][0]
    program['properties']['body']['properties']['bindings'] = {'type': 'array', 'prefixItems': literal_bindings,
        'items': False, 'minItems': len(bindings), 'maxItems': len(bindings)}
    return schema


def interface_definitions(source_unit_ids=None, *, literal_text=None):
    """One wire/runtime contract for source bindings and the seven connectors."""
    string = {"type": "string"}
    strings = array(string)
    scalar = {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "boolean"}]}
    amount = obj({"value": {"type": "integer", "minimum": 0}, "unit": string, "owner": string,
                  "period": string, "lineage": {**strings, "minItems": 1},
                  "stage": {"enum": ["element", "closed_group"]}})
    key = {**strings, "minItems": 3, "maxItems": 3}
    bank = obj({"key": key, "balance": {"type": "integer", "minimum": 0},
                "policy": {"enum": ["input_order", "reverse_order"]}, "order_observable": {"type": "boolean"}})
    types = {"integer": {"type": "integer"}, "rational": {"type": "string"}, "scalar": scalar,
             "relation": obj({"columns": strings, "rows": array(strings), "closed": {"type": "boolean"}}),
             "amount": amount, "amounts": array(amount), "allowance_bank": array(bank), "resource_key": key, "slot_list": strings}
    if literal_text is not None:
        # Mirror necessary lexical conditions of binding_literal_audit. This
        # never infers factual truth, an amount, or a missing legal rule.
        import re
        from .grounding import _numbers
        numbers = _numbers(literal_text)
        booleans = [value for value in (False, True)
                    if re.search(r'\b' + str(value).lower() + r'\b', literal_text, re.I)]
        scalar['anyOf'] = [string] + ([{'type': 'integer'}] if numbers else []) + \
            ([{'type': 'boolean', 'enum': booleans}] if booleans else [])
        if not numbers:
            for kind in ('integer', 'rational', 'amount'):
                del types[kind]
            for kind in ('amounts', 'allowance_bank'):
                types[kind]['maxItems'] = 0
    source_ref = {"enum": list(source_unit_ids)} if source_unit_ids is not None else string
    binding = {"anyOf": [obj({"name": {"type": "string", "pattern": "^[A-Za-z_][A-Za-z0-9_]*$"}, "value": value, "type": {"enum": [kind]}, "source": source_ref})
                         for kind, value in types.items()]}
    def connector(op, arity, params):
        result = obj({"op": {"enum": [op]}, "inputs": {"type": "array", "items": ref("connector"),
                    "minItems": arity, "maxItems": arity}, "params": obj(params)})
        if not params:
            result["required"].remove("params")
        return result
    graphs = {"anyOf": [obj({"slot": string}),
        obj({'pattern': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'},
             'variant': {'type': 'integer', 'minimum': 0},
             'slots': {'type': 'object', 'additionalProperties': string},
             'columns': {'type': 'object', 'additionalProperties': string}}),
        connector("bind_rename", 1, {"from": strings, "to": strings}),
        connector("join_on", 2, {"keys": strings}), connector("project_exists", 1, {}),
        connector("group_by", 1, {"keys": strings}),
        connector("map", 1, {"primitive": {"enum": ["cap"]}, "limit_slot": string,
                             "scope": {"enum": ["element", "closed_group"]}}),
        connector("map", 1, {"primitive": {"enum": ["exists", "sum_amounts"]}}),
        connector("fold_reduce", 1, {"primitive": {"enum": ["sum_amounts", "all", "any"]}}),
        connector("thread_allowance", 1, {"bank_slot": string, "key_slot": string})]}
    return {"binding": binding, "connector": graphs}


def interface_schema():
    return {"type": "array", "maxItems": 8,
        "items": obj({"fields": array({"enum": list(FIELDS)}),
                      "graph": ref("connector"), "bindings": array(ref("binding"))})}


def strict_proposal_schema(dataset, base_schema, *, source_unit_ids=None):
    schema = deepcopy(base_schema)
    if dataset not in (*TARGETS, 'ProofWriter_OWA_depth5', 'ContractNLI'):
        schema["$defs"] = interface_definitions(source_unit_ids)
        schema["properties"]["interfaces"] = interface_schema()
        return schema
    string = {"type": "string"}
    strings = array(string)
    scalar = {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "boolean"}]}
    variable = obj({"var": string})
    def typed_variable(prefix):
        return obj({"var": {"type": "string", "pattern": '^' + prefix + '_[A-Za-z0-9_]+$'}})
    atom = {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "boolean"},
                      {"type": "null"}, variable, ref("operation")]}

    def operation(op, items, arity=None, minimum=0):
        args = {**array(items), "minItems": minimum}
        if arity is not None:
            args.update(minItems=arity, maxItems=arity)
        return obj({"op": {"enum": [op]}, "args": args})

    def positional(op, items):
        return obj({"op": {"enum": [op]}, "args": {"type": "array", "prefixItems": items,
                    "items": False, "minItems": len(items), "maxItems": len(items)}})

    number_ops = {"anyOf": [operation(op, ref("number_expression"), arity, minimum)
        for op, arity, minimum in [("add", None, 0), ("sub", 2, 0), ("min", None, 1), ("max", None, 1)]] + [
        positional("scale", [{"type": "integer"}, ref("number_expression")]),
        positional("divide_constant", [ref("number_expression"), {"type": "integer", "not": {"const": 0}}])]}
    boolean_ops = {"anyOf": [operation(op, ref("boolean_expression"), arity) for op, arity in
        [("and", None), ("or", None), ("not", 1), ("xor", 2)]] + [
        operation(op, ref("expression"), 2) for op in ("eq", "ne")] + [
        operation(op, ref("number_expression"), 2) for op in ("lt", "le")]}
    pair_op = positional("pair", [ref("string_expression"), ref("expression")])
    def conditional(kind):
        return positional("if", [ref("boolean_expression"), ref(kind), ref(kind)])
    operation_schema = {"anyOf": [ref("number_operation"), ref("boolean_operation"),
        conditional("expression"), operation("array", ref("expression")), pair_op,
        operation("object", ref("pair_operation")), operation("concat", ref("array_expression"))]}
    definitions = interface_definitions(source_unit_ids)
    source_ref = {"enum": list(source_unit_ids)} if source_unit_ids is not None else string
    bindings = array(ref("binding"))
    expression_binding = {'anyOf': [obj({'name': {'type': 'string', 'pattern': '^' + prefix + '_[A-Za-z0-9_]+$'},
        'type': {'enum': [kind]}, 'value': value, 'source': source_ref})
        for prefix, kind, value in [('n', 'integer', {'type': 'integer'}), ('n', 'rational', {'type': 'string'}),
                                   ('n', 'scalar', {'type': 'integer'}), ('s', 'scalar', {'type': 'string'}),
                                   ('b', 'scalar', {'type': 'boolean'})]]}
    node_names = array({"type": "string", "pattern": "^(query|binding:[A-Za-z_][A-Za-z0-9_]*|connector:[0-9]+)$"})
    links = {"type": "object", "additionalProperties": {**node_names, "minItems": 1}}
    if source_unit_ids is not None:
        links = {"type": "object", "additionalProperties": False, "required": [],
                 "properties": {key: {**node_names, "minItems": 1} for key in source_unit_ids}}
        for key in ("compiled_units", "unsupported_units"):
            schema["properties"][key]["items"] = source_ref
    depth = EXPRESSION_DEPTH
    if dataset == 'RuleArena_Airline':
        query = {'anyOf': [ref(f'number_operation_{depth}'), positional('if', [
            ref(f'boolean_expression_{depth-1}'), ref(f'number_expression_{depth-1}'), ref(f'number_expression_{depth-1}')])]}
    elif dataset in {'SARA_v2_Binary', 'ProofWriter_OWA_depth5', 'ContractNLI'}:
        query = positional('if', [ref(f'boolean_expression_{depth-1}'),
                                ref(f'string_expression_{depth-1}'), ref(f'string_expression_{depth-1}')])
    else:
        citation = {'type': 'string', 'pattern': CITATION_PATTERN}
        claim = positional('object', [positional('pair', [{'enum': ['citation']}, citation]),
            positional('pair', [{'enum': ['claim_value']}, ref('number_expression_6')])])
        def native_array(item):
            base = operation('array', item)
            # Finite conditional lists permit exclusions without inventing a value.
            result = base
            for _ in range(3):
                result = {'anyOf': [base, positional('if', [ref('boolean_expression_4'), result, result]),
                                    operation('concat', result)]}
            return result
        query = positional('object', [positional('pair', [{'enum': [family]}, operation('object',
            positional('pair', [ref('string_expression_4'), native_array(item)]))])
            for family, item in [('EC', citation), ('EV', claim)]])
    expression_body = obj({"bindings": {**array(ref('expression_binding')), 'minItems': 1},
                           "query": query, "source_links": links})
    connector_body = obj({"bindings": bindings, "candidates": {"type": "array", "items": ref("connector"),
                         "minItems": 1, "maxItems": 32}, "selected": {"type": "integer", "minimum": 0, "maximum": 31}, "source_links": links,
                          "project": {"enum": ["identity", "amount_value", "amount_values", "entailment_label"]},
                          "query": query})
    connector_body['required'].remove('query')
    expressions = {"expression": atom, "operation": operation_schema,
        "number_operation": number_ops, "boolean_operation": boolean_ops, "pair_operation": pair_op,
        "number_expression": {"anyOf": [{"type": "integer"}, typed_variable('n'), ref("number_operation"), conditional("number_expression")]},
        "boolean_expression": {"anyOf": [{"type": "boolean"}, typed_variable('b'), ref("boolean_operation"), conditional("boolean_expression")]},
        "string_expression": {"anyOf": [{"type": "string"}, typed_variable('s'), conditional("string_expression")]},
        "array_expression": {"anyOf": [variable, operation("array", ref("expression")), pair_op,
            operation("concat", ref("array_expression")), conditional("array_expression")]}}
    schema['$defs'] = {**bounded_expressions(expressions), 'expression_binding': expression_binding,
                       **definitions}
    schema["properties"]["program"] = {"anyOf": [
        obj({"kind": {"enum": ["expression"]}, "body": expression_body}),
        obj({"kind": {"enum": ["connector"]}, "body": connector_body}),
        obj({"kind": {"enum": ["unsupported"]}, "body": obj({})})]}
    schema["properties"]["interfaces"] = interface_schema()
    schema['properties'] = {k: schema['properties'][k] for k in
                            ['program', 'answer', 'compiled_units', 'unsupported_units', 'interfaces']}
    return schema
