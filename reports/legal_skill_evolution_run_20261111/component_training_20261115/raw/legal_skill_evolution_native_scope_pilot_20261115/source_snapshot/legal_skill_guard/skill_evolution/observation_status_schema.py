"""Exact disjunctions for the observed complete/unread schema conditions.

The author/teacher schema stays unchanged. This compiler handles its finite,
required status discriminator and the actual type/cardinality refinements used
by the acquired observation views. Unsupported conditions remain with the
existing strict host validator; they are never weakened in accepted outputs.
No existing model output is adapted, completed or rescored by this module.
"""
from copy import deepcopy


class _UnsupportedCondition(Exception):
    pass


def _refine(original, constraint):
    if not isinstance(original, dict) or not isinstance(constraint, dict):
        raise _UnsupportedCondition
    if not set(constraint) <= {'type', 'minItems', 'maxItems', 'minLength', 'maxLength'}:
        raise _UnsupportedCondition
    if set(original) & {'anyOf', 'oneOf', 'allOf', 'not', 'if', 'then', 'else'}:
        raise _UnsupportedCondition
    result = deepcopy(original)
    for key, value in constraint.items():
        if key == 'type':
            proposed = [value] if isinstance(value, str) else value
            old = result.get('type', proposed)
            old = [old] if isinstance(old, str) else old
            intersection = []
            for kind in old:
                common = kind if kind in proposed or kind == 'integer' and 'number' in proposed else (
                    'integer' if kind == 'number' and 'integer' in proposed else None)
                if common is not None and common not in intersection:
                    intersection.append(common)
            if not intersection:
                return False
            result['type'] = intersection[0] if len(intersection) == 1 else intersection
        elif key.startswith('min'):
            result[key] = max(result.get(key, value), value)
        else:
            result[key] = min(result.get(key, value), value)
    return result


def _status_disjunction(node):
    clauses = node.get('allOf')
    if not clauses or node.get('type') != 'object' or not isinstance(node.get('properties'), dict):
        raise _UnsupportedCondition
    status = None
    parsed = []
    for clause in clauses:
        if not isinstance(clause, dict) or 'if' not in clause or not set(clause) <= {'if', 'then', 'else'}:
            raise _UnsupportedCondition
        condition = clause['if']
        if set(condition) - {'properties', 'required'} or len(condition.get('properties', {})) != 1:
            raise _UnsupportedCondition
        key, rule = next(iter(condition['properties'].items()))
        if key not in node.get('required', []) or set(rule) != {'const'}:
            raise _UnsupportedCondition
        if set(condition.get('required', [])) - {key} or status not in (None, key):
            raise _UnsupportedCondition
        status = key
        parsed.append((rule['const'], clause.get('then', {}), clause.get('else', {})))
    domain = node['properties'][status].get('enum')
    if (not isinstance(domain, list) or not domain or any(not isinstance(v, str) for v in domain)
            or set(node['properties'][status]) - {'type', 'enum', 'title', 'description'}):
        raise _UnsupportedCondition
    branches = []
    for value in domain:
        branch = deepcopy(node)
        branch.pop('allOf')
        branch['properties'][status]['enum'] = [value]
        possible = True
        for expected, yes, no in parsed:
            refinement = yes if value == expected else no
            if not isinstance(refinement, dict) or set(refinement) - {'properties'}:
                raise _UnsupportedCondition
            for name, constraint in refinement.get('properties', {}).items():
                if name not in branch['properties'] or name not in branch.get('required', []):
                    raise _UnsupportedCondition
                narrowed = _refine(branch['properties'][name], constraint)
                if narrowed is False:
                    possible = False
                    break
                branch['properties'][name] = narrowed
        if possible:
            branches.append(branch)
    return {'anyOf': branches} if branches else False


def compile_status_conditions(schema):
    receipts = []

    def visit(node, path):
        if not isinstance(node, dict):
            return node
        node = deepcopy(node)
        if 'allOf' in node:
            try:
                replacement = _status_disjunction(node)
            except _UnsupportedCondition:
                pass
            else:
                receipts.append({'path': path, 'operation': 'exact_required_status_disjunction',
                    'conditions': len(node['allOf']), 'branches': len(replacement.get('anyOf', []))
                    if isinstance(replacement, dict) else 0})
                node = replacement
        if not isinstance(node, dict):
            return node
        for key in ('properties', '$defs', 'definitions'):
            if key in node:
                node[key] = {name: visit(child, path + '/' + key + '/' + name)
                    for name, child in node[key].items()}
        for key in ('items', 'additionalProperties', 'not', 'if', 'then', 'else'):
            if key in node:
                node[key] = visit(node[key], path + '/' + key)
        for key in ('anyOf', 'oneOf', 'allOf', 'prefixItems'):
            if key in node:
                node[key] = [visit(child, path + '/' + key + '/' + str(i))
                    for i, child in enumerate(node[key])]
        return node

    return visit(schema, ''), receipts
