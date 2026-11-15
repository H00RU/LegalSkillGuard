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


def retained_family_context(library):
    """Factor the unchanged residence/birth channels out of the acquired unit.

    A new kinship representation must not silently remove these real task
    inputs. The source-to-fact loops and field meanings are copied exactly.
    """
    original=next(c for c in library['components']if c['id']=='family_relationship_residence')
    view=deepcopy(json.loads(original['schema_json'])['properties']['views']['items'])
    nodes=[view]
    for clause in view.get('allOf',[]):
        nodes.extend(clause[k]for k in ('if','then','else')if k in clause)
    for node in nodes:
        node.get('properties',{}).pop('relationships',None)
        if 'required'in node:node['required']=[k for k in node['required']if k!='relationships']
    tree=ast.parse(original['conversion_program']);entry=next(n for n in tree.body if n.name=='apply')
    assignments=[]
    for n in entry.body:
        if isinstance(n,ast.If):break
        if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='witnesses'for t in n.targets):
            n=ast.parse("witnesses=list(view.get('witnesses',[]))").body[0]
        assignments.append(n)
    guard=ast.parse("""if type(view) is not dict or view.get('extraction_status')!='complete':
    return part([],[],[],False,['retained_context_unread'])
residences=view.get('residences')
births=view.get('births')
if type(residences)is not list or type(births)is not list or type(view.get('witnesses'))is not list:
    return part([],[],[],False,['retained_context_channels_unread'])
""").body
    loops=[n for n in entry.body if isinstance(n,ast.For)and isinstance(n.iter,ast.Call)
           and any(isinstance(a,ast.Name)and a.id in ('residences','births')for a in n.iter.args)]
    assert len(loops)==2,'Use the actual acquired residence and birth loops only'
    entry.body=assignments+guard+loops+entry.body[-2:]
    result={'id':'retained_family_context','meaning':'Previously acquired residence and birth observations, separate from revised kinship.',
        'prompt':original['prompt']+'\nRead only the residences and births channels in the supplied schema. Read current facts only; do not fill other channels.',
        'schema_json':json.dumps(record_schema({'views':{'type':'array','minItems':1,'items':view}})),
        'conversion_program':ast.unparse(ast.fix_missing_locations(tree)),
        'complete_native_families':['residence_','birth_'],'facts_only':True,
        'update':{'unchanged_parent_component_sha256':digest(original),'retained_channels':['residences','births'],
                  'learned_source_to_fact_loops_unchanged':True,'existing_source_witnesses_retained':True}}
    validate_adapter(library['shared_helpers']+'\n\n'+result['conversion_program'])
    return result


def validate(library,kernel):
    ids = [c['id'] for c in library['components']]
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate observation components')
    vocabulary = {p for p,a in kernel['fact_arities'].items() if a==1}|set(GIVENS)
    for c in library['components']:
        if type(c.get('facts_only',False)) is not bool:
            raise ValueError('Observation factual-input scope must be an explicit boolean')
        if not c['id'].isidentifier():
            raise ValueError('Invalid component identity')
        ports = c['complete_native_families']
        if len(ports)!=len(set(ports)) or not set(ports)<=vocabulary:
            raise ValueError('Coverage names an undeclared native family')
        jsonschema.Draft202012Validator.check_schema(json.loads(c['schema_json']))
        if 'relation_contract' in c:
            from .relational_observation_contract import validate as validate_contract
            validate_contract(c['relation_contract'],kernel)
            if ports:
                raise ValueError('Relation reads close their explicit scopes, not whole event families')
        else:
            validate_adapter(library['shared_helpers']+'\n\n'+c['conversion_program'])
        if c.get('observation_program') is not None:
            validate_adapter(c['observation_program'])
    return library


def plan(library,kernel):
    validate(library,kernel)
    dependency = dependency_graph(kernel)
    anchors = {p for p,a in dependency['input_predicates'].items() if a==1 or p in GIVENS}
    providers = {c['id']:set(c['relation_contract']['covered_families'] if 'relation_contract' in c
                           else c['complete_native_families']) & anchors for c in library['components']}
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
    if 'relation_contract' in component:
        from .relational_observation_contract import forward
        value=forward(component['relation_contract'],view,public,kernel)
        if set(component['relation_contract']['covered_families']) & {'service_', 'payment_'}:
            from .source_event_binding import bind
            value,receipt=bind(kernel,value)
            names={r['source_event']:r['native_event'] for r in receipt['bindings']}
            for scope in value['scope_contract']['event_properties']:
                scope['event']=names.get(scope['event'],scope['event'])
            value['source_event_binding']=receipt
        return value
    source_service=component.get('facts_only',False) and set(component['complete_native_families'])=={'service_'}
    conversion_kernel=deepcopy(kernel)if source_service else kernel
    if source_service:
        # Source encoding is independent of query identity. The shared typed
        # linker below resolves identities after the original encoder validates.
        conversion_kernel.update(native_query=[],query_clause='')
    value = execute_json(_program(library['shared_helpers'],component['conversion_program']),
        {'component_id':component['id'],'view':view,'kernel':conversion_kernel,
            'public_case':{'facts':public['facts']}if source_service else public}, {},allow_helpers=True)
    if set(value)!={'facts','negative_givens','witnesses','complete','reasons'} or type(value['complete']) is not bool:
        raise ValueError('A converted observation has exact facts, witnesses, completeness and residual reasons')
    if source_service:
        from .source_event_binding import bind
        value,_=bind(kernel,value)
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
