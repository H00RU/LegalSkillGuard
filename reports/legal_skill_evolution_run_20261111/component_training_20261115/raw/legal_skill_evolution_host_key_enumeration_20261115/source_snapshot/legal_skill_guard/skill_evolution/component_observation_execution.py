"""Route public statute input demands to existing learned observation components.

The learned lowering functions, observations and truth checks are preserved.
Only selection moves out of the teacher's query-name table. Named native
symbols are routing hints, not a semantic or completeness certificate.
"""
import ast
from copy import deepcopy
from functools import lru_cache
from itertools import combinations
import json

from .case_observation_contract import validate_adapter
from .objects import digest
from .sara_statute_kernel import GIVENS
from .statute_input_dependencies import dependency_graph


def _component_branches(function):
    result = {}
    for node in ast.walk(function):
        test = node.test if isinstance(node, ast.If) else None
        if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and
                test.left.id == 'component' and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq) and
                isinstance(test.comparators[0], ast.Constant) and isinstance(test.comparators[0].value, str)):
            result[test.comparators[0].value] = node.body
    return result


def _reachable(functions, names):
    visited = set()
    while names:
        name = names.pop()
        if name in visited:
            continue
        visited.add(name)
        names.extend(n.func.id for n in ast.walk(functions[name])
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and
            n.func.id in functions and n.func.id not in visited)
    return visited


def native_capabilities(library, kernel):
    """Index symbols named in the real component branch and called helpers."""
    functions = {n.name:n for n in ast.parse(library['binding_program']).body if isinstance(n,ast.FunctionDef)}
    if 'lower' not in functions:
        raise ValueError('The current component interface needs its actual lower function')
    branches = _component_branches(functions['lower'])
    vocabulary = {**kernel['fact_arities'], **{p:len(args) for p,args in GIVENS.items()}}
    result = {}
    for component in library['components']:
        cid = component['id']
        if cid not in branches:
            raise ValueError('Declared component has no corresponding conversion branch: '+cid)
        nodes = list(branches[cid])
        called = {n.func.id for node in nodes for n in ast.walk(node)
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in functions}
        nodes += [functions[name] for name in _reachable(functions,list(called))]
        values = {n.value for node in nodes for n in ast.walk(node)
            if isinstance(n,ast.Constant) and isinstance(n.value,str)}
        # Dynamic event kinds in these actual libraries are native underscore
        # forms of schema enums (son -> son_, disability -> disability_).
        named = {value for value in values if value in vocabulary}
        named |= {value+'_' for value in values if value+'_' in vocabulary}
        result[cid] = {'named_native_predicates':dict(sorted((p,vocabulary[p]) for p in named)),
            'component_payload_sha256':digest(component),
            'not_a_semantic_or_output_completeness_certificate':True}
    return result


def naive_named_symbol_plan(library, kernel):
    """Diagnostic counter-control: symbol emission does not establish coverage.

    Retained to reproduce the real B3 specialization failure. Never used as an
    accepted runtime policy or a learned semantic completeness declaration.
    """
    demand = dependency_graph(kernel)
    capabilities = native_capabilities(library,kernel)
    # Shared binary roles (agent/start/amount) cannot identify the event type.
    # Unary event roots and explicit statutory input heads provide the anchors.
    anchors = {p for p,a in demand['input_predicates'].items() if a==1 or p in GIVENS}
    providers = {cid:set(c['named_native_predicates']) & anchors for cid,c in capabilities.items()}
    represented = set().union(*providers.values()) if providers else set()
    selected = []
    ids = sorted(cid for cid,values in providers.items() if values)
    for count in range(len(ids)+1):
        options = [combo for combo in combinations(ids,count)
            if set().union(*(providers[cid] for cid in combo)) >= represented]
        if options:
            by_id = {c['id']:c for c in library['components']}
            selected = list(min(options,key=lambda combo:(sum(len(by_id[c]['schema_json']) for c in combo),combo)))
            break
    return {'component_ids':selected,'public_demand':demand,
        'named_component_capabilities':capabilities,'required_native_anchors':sorted(anchors),
        'anchors_without_named_provider':sorted(anchors-represented),
        'selection_objective':['component_count','schema_characters','stable_ids'],
        'no_TRAIN_query_name_whitelist':True,'no_case_facts_or_answer_labels_used':True,
        'not_a_learned_method_or_semantic_coverage_certificate':True,'new_model_calls':0}


@lru_cache(maxsize=32)
def external_selection_program(program):
    """Reuse actual lowering; replace its one internal selection call only."""
    validate_adapter(program)
    tree = ast.parse(program)
    entry = next(f for f in tree.body if isinstance(f,ast.FunctionDef) and f.name=='apply')
    class Selection(ast.NodeTransformer):
        changed = 0
        def visit_Call(self,node):
            if isinstance(node.func,ast.Name) and node.func.id=='selected_components':
                if len(node.args)!=1 or not isinstance(node.args[0],ast.Name) or node.args[0].id!='kernel':
                    raise ValueError('Unsupported internal component selection call')
                self.changed += 1
                return ast.copy_location(ast.Subscript(value=ast.Name(id='inputs',ctx=ast.Load()),
                    slice=ast.Constant(value='component_ids'),ctx=ast.Load()),node)
            return self.generic_visit(node)
    change = Selection()
    change.visit(entry)
    if change.changed!=1:
        raise ValueError('Exactly one actual apply selection call is required')
    functions = {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    active = _reachable(functions,['apply'])
    tree.body = [n for n in tree.body if n.name in active]
    result = ast.unparse(ast.fix_missing_locations(tree))
    validate_adapter(result)
    return result


def convert(library, component_ids, kernel, public, observation, *, literal_context):
    declared = {c['id']:c for c in library['components']}
    if len(component_ids)!=len(set(component_ids)) or not set(component_ids)<=set(declared):
        raise ValueError('Explicit distinct declared components required')
    from .case_observation_contract import check_bindings
    from .span_compiler import execute_json
    value = execute_json(external_selection_program(library['binding_program']),
        {'kernel':kernel,'public_case':public,'literal_context':literal_context,
         'observation':deepcopy(observation),'component_ids':list(component_ids)}, {}, allow_helpers=True)
    return check_bindings(value,json.loads(kernel['input_fields_json']),public)
