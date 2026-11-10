"""Lower the actual static ordinary cache's literal programme without running it.

Only assignments of literals/earlier literals/the declared interface followed by
solve(program,facts['facts'],query) are accepted. Body-only rules acquire an empty
additional distinct-guard list. Bodies, source quotes and priorities are unchanged;
missing substantive programme fields are never filled.
"""
import ast
from copy import deepcopy
from .coverage import digest


def lower(code,interface):
    tree=ast.parse(code)
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef):raise ValueError('Expected the actual single cache function')
    fn=tree.body[0]
    if fn.name!='law_cache' or [a.arg for a in fn.args.args]!=['facts','query']:raise ValueError('Cache signature differs')
    if fn.decorator_list or fn.returns or fn.args.defaults or fn.args.kw_defaults or fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or fn.args.posonlyargs or any(a.annotation for a in fn.args.args):raise ValueError('Evaluated function metadata is not a literal cache')
    expected=ast.parse("solve(program, facts['facts'], query)",mode='eval').body
    if not fn.body or not isinstance(fn.body[-1],ast.Return) or ast.dump(fn.body[-1].value)!=ast.dump(expected):raise ValueError('Execution skeleton differs from the actual static cache')
    env={}
    def literal(node):
        if isinstance(node,ast.Constant):return node.value
        if isinstance(node,ast.Name) and node.id in env:return deepcopy(env[node.id])
        if isinstance(node,ast.List):return [literal(v) for v in node.elts]
        if isinstance(node,ast.Tuple):return tuple(literal(v) for v in node.elts)
        if isinstance(node,ast.Dict):return {literal(k):literal(v) for k,v in zip(node.keys,node.values)}
        if ast.dump(node)==ast.dump(ast.parse("facts['interface']",mode='eval').body):return deepcopy(interface)
        raise ValueError('Nonliteral computation cannot be lowered: '+type(node).__name__)
    for node in fn.body[:-1]:
        if not isinstance(node,ast.Assign) or len(node.targets)!=1 or not isinstance(node.targets[0],ast.Name):raise ValueError('Only the actual straight-line literal assignments are supported')
        name=node.targets[0].id
        if name in env:raise ValueError('Repeated assignment is not the actual static cache')
        env[name]=literal(node.value)
    programme=env['program'];before=deepcopy(programme);added=[]
    for rule in programme['rules']:
        if 'different' not in rule:rule['different']=[];added.append(rule['id'])
    def strip_added(p):
        p=deepcopy(p)
        for r in p['rules']:
            if r['id'] in added:assert r.pop('different')==[]
        return p
    assert strip_added(programme)==before
    return programme,{'raw_programme_sha256':digest(before),'adapted_programme_sha256':digest(programme),
        'rules_with_neutral_empty_additional_guard_field':added,'all_bodies_heads_quotes_priorities_and_unresolved_unchanged':True,
        'no_generated_code_or_native_answer_executed_to_extract_programme':True,
        'new_execution_adapter_not_original_strict_bridge_success':True}
