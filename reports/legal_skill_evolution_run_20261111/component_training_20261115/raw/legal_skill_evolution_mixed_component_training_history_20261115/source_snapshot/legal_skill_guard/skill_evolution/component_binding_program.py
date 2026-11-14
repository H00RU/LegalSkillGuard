"""Compile acquired component programs into the existing traced adapter ABI.

Only function names and the deterministic product/merge collector are supplied
by this compiler. Acquired schemas, conversion branches, witnesses and residual
reasons are unchanged. Execution parity must precede residual-read dispatch.
"""
import ast
from copy import deepcopy

from .case_observation_contract import validate_adapter


class _Rename(ast.NodeTransformer):
    def __init__(self, names):
        self.names = names

    def visit_FunctionDef(self, node):
        node.name = self.names[node.name]
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in self.names:
            node.id = self.names[node.id]
        return node


def binding_program(library, ids):
    by_id = {c['id']: c for c in library['components']}
    body = list(ast.parse(library['shared_helpers']).body)
    calls = []
    for index, cid in enumerate(ids):
        tree = ast.parse(by_id[cid]['conversion_program'])
        names = {n.name: 'component_' + str(index) + '_' + n.name
            for n in tree.body if isinstance(n, ast.FunctionDef)}
        body.extend(_Rename(names).visit(tree).body)
        calls.append("        " + ('if' if index == 0 else 'elif') + " cid == " + repr(cid) + ":\n"
            + "            part = " + names['apply'] + "({'component_id': cid, 'view': view, "
            + "'public_case': inputs['public_case'], 'kernel': inputs['kernel']}, {})\n")
    dispatch = ''.join(calls) or "        part = {}\n"
    entry = '''def apply(inputs, premises):
    alternatives = [{'facts': [], 'negative_givens': [], 'witnesses': [], 'complete': True, 'reasons': []}]
    for cid in COMPONENT_IDS:
        views = inputs['observation'][cid].get('views')
        if not isinstance(views, list) or not views:
            return {'bindings': [], 'unresolved': ['No observation alternative for ' + cid]}
        parts = []
        for view in views:
DISPATCH
            parts.append(part)
        combined = []
        for left in alternatives:
            for right in parts:
                value = {'complete': left['complete'] and right['complete']}
                for key in ['facts', 'negative_givens', 'witnesses', 'reasons']:
                    values = list(left[key])
                    for row in right[key]:
                        if row not in values:
                            values.append(row)
                    value[key] = values
                combined.append(value)
        alternatives = combined
    bindings = []
    reasons = []
    for value in alternatives:
        bindings.append({'inputs': {'facts': value['facts'], 'negative_givens': value['negative_givens'], 'extraction_status': 'complete' if value['complete'] else 'unread'}, 'witnesses': value['witnesses']})
        for reason in value['reasons']:
            if reason not in reasons:
                reasons.append(reason)
    return {'bindings': bindings, 'unresolved': sorted(reasons)}
'''.replace('COMPONENT_IDS', repr(list(ids))).replace('DISPATCH\n',
        ''.join('    ' + line + '\n' for line in dispatch.splitlines()))
    body.extend(ast.parse(entry).body)
    program = ast.unparse(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])))
    return validate_adapter(program)
