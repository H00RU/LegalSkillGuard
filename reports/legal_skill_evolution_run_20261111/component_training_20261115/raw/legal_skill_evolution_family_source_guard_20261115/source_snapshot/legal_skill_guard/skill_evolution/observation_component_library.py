"""Observation schemas and their conversions are revised as one learned unit.

The public statute determines input demands. A component may replace a family
only through its declared complete-family contract, not because its converter
sometimes emits that predicate. These learned contracts remain empirical
claims; source checks and actual execution are required separately.
"""
import ast
from copy import deepcopy
from functools import lru_cache
from itertools import combinations
import json

import jsonschema

from .case_observation_contract import check_bindings, validate_adapter
from .component_observation_execution import _component_branches, _reachable
from .native import record_schema
from .objects import digest
from .sara_statute_kernel import GIVENS
from .span_compiler import execute_json
from .statute_input_dependencies import dependency_graph


def import_saved_library(saved):
    """One-time, exact code extraction from the already paid B8 library.

    This imports reusable code, not coverage assertions. The teacher must
    acquire or revise the complete-family contracts from the actual errors.
    """
    tree = ast.parse(saved['binding_program'])
    functions = {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    lower = functions['lower']
    branches = _component_branches(lower)
    index = next(i for i,n in enumerate(lower.body) if isinstance(n,ast.If) and
        isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='component')
    helper_names = _reachable(functions,['lower'])-{'lower'}
    shared = '\n\n'.join(ast.unparse(n) for n in tree.body if n.name in helper_names)
    components = []
    for original in saved['components']:
        cid = original['id']
        specialized = deepcopy(lower)
        specialized.body = deepcopy(lower.body[:index]+branches[cid]+lower.body[index+1:])
        entry = ast.parse('''def apply(inputs,premises):
    return lower(inputs['component_id'],inputs['view'],inputs['public_case'],inputs['kernel'])
''').body[0]
        program = ast.unparse(ast.fix_missing_locations(ast.Module(body=[specialized,entry],type_ignores=[])))
        component = {k:deepcopy(original[k]) for k in ('id','meaning','prompt','schema_json')}
        component.update(conversion_program=program,complete_native_families=[],
            coverage_explanation='Unacquired: named outputs alone do not establish complete-family coverage.',
            parent_component_hash=digest(original),error_feedback_ids=[])
        validate_adapter(shared+'\n\n'+program)
        components.append(component)
    return {'shared_helpers':shared,'components':components,
        'origin_saved_library_sha256':digest(saved),'coverage_unacquired_not_assumed':True}


def validate(library,kernel):
    ids = [c['id'] for c in library['components']]
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate observation components')
    vocabulary = {p for p,a in kernel['fact_arities'].items() if a==1}|set(GIVENS)
    for c in library['components']:
        if not c['id'].isidentifier():
            raise ValueError('Invalid component identity')
        ports = c['complete_native_families']
        if len(ports)!=len(set(ports)) or not set(ports)<=vocabulary:
            raise ValueError('Coverage names an undeclared native family')
        jsonschema.Draft202012Validator.check_schema(json.loads(c['schema_json']))
        validate_adapter(library['shared_helpers']+'\n\n'+c['conversion_program'])
    return library


def plan(library,kernel):
    validate(library,kernel)
    dependency = dependency_graph(kernel)
    anchors = {p for p,a in dependency['input_predicates'].items() if a==1 or p in GIVENS}
    providers = {c['id']:set(c['complete_native_families']) & anchors for c in library['components']}
    represented = set().union(*providers.values()) if providers else set()
    by_id = {c['id']:c for c in library['components']}
    ids = sorted(cid for cid,ports in providers.items() if ports)
    chosen = ()
    for count in range(len(ids)+1):
        covers = [v for v in combinations(ids,count)
            if set().union(*(providers[c] for c in v)) >= represented]
        if covers:
            chosen = min(covers,key=lambda v:(sum(len(by_id[c]['schema_json']) for c in v),v))
            break
    return {'component_ids':list(chosen),'required_native_families':sorted(anchors),
        'unrepresented_native_families':sorted(anchors-represented),'public_dependency':dependency,
        'complete_family_claims_are_learned_not_certified_by_types':True,
        'selection_uses_case_labels':False,'new_model_calls':0}


def observation_schema(library,ids):
    by_id = {c['id']:c for c in library['components']}
    return record_schema({cid:json.loads(by_id[cid]['schema_json']) for cid in ids})


@lru_cache(maxsize=128)
def _program(shared,component):
    value = shared+'\n\n'+component
    return validate_adapter(value)


def component_value(library,component,kernel,public,view):
    value = execute_json(_program(library['shared_helpers'],component['conversion_program']),
        {'component_id':component['id'],'view':view,'kernel':kernel,'public_case':public}, {},allow_helpers=True)
    if set(value)!={'facts','negative_givens','witnesses','complete','reasons'} or type(value['complete']) is not bool:
        raise ValueError('A converted observation has exact facts, witnesses, completeness and residual reasons')
    return value


def convert(library,ids,kernel,public,observation):
    jsonschema.validate(observation,observation_schema(library,ids))
    by_id = {c['id']:c for c in library['components']}
    alternatives = [{'facts':[],'negative_givens':[],'witnesses':[],'complete':True,'reasons':[]}]
    for cid in ids:
        views = observation[cid].get('views')
        if not isinstance(views,list) or not views:
            return {'bindings':[],'unresolved':['No observation alternative for '+cid]}
        parts = [component_value(library,by_id[cid],kernel,public,view) for view in views]
        combined = []
        for left in alternatives:
            for right in parts:
                value = {'complete':left['complete'] and right['complete']}
                for key in ('facts','negative_givens','witnesses','reasons'):
                    value[key] = deepcopy(left[key])
                    for row in right[key]:
                        if row not in value[key]:value[key].append(deepcopy(row))
                combined.append(value)
        alternatives = combined
    value = {'bindings':[{'inputs':{'facts':v['facts'],'negative_givens':v['negative_givens'],
        'extraction_status':'complete' if v['complete'] else 'unread'},'witnesses':v['witnesses']} for v in alternatives],
        'unresolved':sorted({reason for v in alternatives for reason in v['reasons']})}
    return check_bindings(value,json.loads(kernel['input_fields_json']),public)


def replace_components(base,edits):
    """A schema and its lowering are an indivisible version during selection."""
    current = {c['id']:deepcopy(c) for c in base['components']}
    seen = set()
    for component in edits:
        cid = component['id']
        if cid in seen:
            raise ValueError('Conflicting component edits')
        seen.add(cid)
        current[cid] = deepcopy(component)
    return {**deepcopy(base),'components':[current[cid] for cid in sorted(current)]}
