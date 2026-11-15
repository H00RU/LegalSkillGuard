"""Connect acquired observation contracts to guarded author-native execution.

Unread components remain explicit. Alternative views remain separate worlds;
no favorable world, missing fact or default answer is selected by this module.
"""
from copy import deepcopy
import json

import jsonschema

from .case_observation_contract import check_bindings
from .observation_component_library import component_value, observation_schema, plan, validate
from .observation_source_review import review
from .observation_scope_normalization import normalize
from .objects import digest
from .partial_native_proof import execute as execute_native
from .sara_statute_kernel import GIVENS
from .statute_input_dependencies import query_event_inputs


def evaluate(library, kernel, public, observation, source_id):
    validate(library, kernel)
    by_id = {c['id']:c for c in library['components']}
    schema = observation_schema(library,list(by_id))
    schema['required'] = []  # Missing component = unread; never an empty scan.
    jsonschema.validate(observation,schema)
    worlds = [{'facts':[],'negative_givens':[],'witnesses':[],'trusted_components':[],
        'complete_families':[],'unread_components':sorted(set(by_id)-set(observation)),
        'relation_scopes_used':False,'scope_contract':{'family_scans':[],'event_properties':[]}}]
    parts = {}
    for cid in sorted(observation):
        value=observation[cid]
        converted = []
        for view in value['views']:
            try:
                part = component_value(library,by_id[cid],kernel,public,view)
                trusted = part['complete'] and not part['reasons']
                if trusted:
                    check_bindings({'bindings':[{'inputs':{'facts':part['facts'],
                        'negative_givens':part['negative_givens'],'extraction_status':'unread'},
                        'witnesses':part['witnesses']}],'unresolved':[]},
                        json.loads(kernel['input_fields_json']),public)
                converted.append({'trusted_complete_observation':trusted,'converted':part})
            except (ValueError,KeyError,TypeError,jsonschema.ValidationError) as error:
                converted.append({'trusted_complete_observation':False,
                    'error':type(error).__name__+': '+str(error)})
        if not converted:
            converted=[{'trusted_complete_observation':False,'error':'No coherent observation view'}]
        parts[cid]=converted
        merged=[]
        for world in worlds:
            for row in converted:
                current=deepcopy(world)
                if row['trusted_complete_observation']:
                    current['trusted_components'].append(cid)
                    for key in ('facts','negative_givens','witnesses'):
                        for item in row['converted'][key]:
                            if item not in current[key]:current[key].append(deepcopy(item))
                    for family in by_id[cid]['complete_native_families']:
                        if family not in current['complete_families']:current['complete_families'].append(family)
                    if 'scope_contract' in row['converted']:
                        current['relation_scopes_used']=True
                        for key in ('family_scans','event_properties'):
                            for item in row['converted']['scope_contract'][key]:
                                if item not in current['scope_contract'][key]:current['scope_contract'][key].append(deepcopy(item))
                        if row['converted']['unread_relations']:
                            current['unread_components'].append(cid)
                else:
                    current['unread_components'].append(cid)
                merged.append(current)
        worlds=merged
    executed=[]
    for world in worlds:
        binding={'facts':world['facts'],'negative_givens':world['negative_givens'],
            # A static cover proves no global closure of relational facts.
            # Only the explicitly acquired family/event scopes may close a lookup.
            'extraction_status':'unread'}
        grounded={'bindings':[{'inputs':binding,'witnesses':world['witnesses']}],'unresolved':[]}
        scopes=world['scope_contract'] if world['relation_scopes_used'] else None
        source_review=review(source_id,grounded,complete_families=world['complete_families'],scope_contract=scopes)
        if source_review['failures']:
            execution={'handled':False,'answer':None,'reason':'Known source-semantic violation'}
        else:
            execution=execute_native(kernel,binding,world['complete_families'],public,scope_contract=scopes)
        executed.append({'inputs':binding,'witnesses':world['witnesses'],
            'complete_families':world['complete_families'],
            'scope_contract':scopes,
            'unread_components':world['unread_components'],'source_review':source_review,'execution':execution})
    answers={w['execution']['answer'] for w in executed if w['execution']['handled']}
    handled=bool(executed) and all(w['execution']['handled'] for w in executed) and len(answers)==1
    return {'handled':handled,'answer':next(iter(answers)) if handled else None,
        'binding_executions':executed,'component_conversions':parts,
        'unread_components':sorted({cid for w in worlds for cid in w['unread_components']}),
        'used_observation_families':sorted({f for w in executed
            for f in w['execution'].get('used_observation_families',[])}),
        'all_coherent_worlds_checked':True,'unknown_not_a_default_fact':True,
        'not_a_source_truth_or_method_novelty_certificate':True}


def next_component(library,kernel,observation,failed_components,execution,static_plan,policy):
    """Compare residual routing with a strong direct-input/static control."""
    if policy not in ('native_residual','direct_inputs_first'):
        raise ValueError('Unknown fixed read policy')
    roots=query_event_inputs(kernel)
    requested={r['family'] for r in roots}
    if policy=='native_residual':
        requested=set()
        declarations={(q['predicate'],r['argument'],r['family']) for r in roots
            for q in kernel['native_query'] if q['predicate']==r['predicate']}
        for world in execution['binding_executions']:
            for access in world['execution'].get('unread_factual_scopes',[]):
                predicate=access['predicate']
                if kernel['fact_arities'].get(predicate)==1 or predicate in GIVENS:
                    requested.add(predicate)
                for pred,index,family in declarations:
                    for q in kernel['native_query']:
                        if q['predicate']==pred and q['arguments'][index]==access['event']:
                            requested.add(family)
    requested.update(family for world in execution['binding_executions']
        for check in world.get('source_review',{}).get('checks',[]) if not check['passed']
        for family in check.get('native_families',[]))
    candidates=[c for c in library['components'] if c['id']not in observation
        and c['id']not in failed_components and (c['id']in static_plan['component_ids']
            or set(c['complete_native_families'])&requested)]
    if not candidates:return None
    def priority(c):
        return (c.get('observation_program') is None,
            not bool(set(c['complete_native_families'])&requested),len(c['schema_json']),c['id'])
    return min(candidates,key=priority)['id']


def run(library,kernel,public,source_id,read,*,policy='native_residual'):
    """Read each selected component at most once; stop on a guarded verdict."""
    static=plan(library,kernel)
    observation,failed,reads,history={},{},[],[]
    by_id={c['id']:c for c in library['components']}
    while True:
        observed,receipts=normalize(library,kernel,public,deepcopy(observation))
        execution=evaluate(library,kernel,public,observed,source_id)
        history.append({'observed_components':sorted(observation),
            'handled':execution['handled'],'answer':execution['answer'],
            'unread_scopes':[scope for w in execution['binding_executions']
                for scope in w['execution'].get('unread_factual_scopes',[])],
            'scope_normalization_receipts':receipts})
        if execution['handled']:break
        if any(w['source_review']['failures'] for w in execution['binding_executions']):
            # Reading unrelated providers cannot undo an already supplied
            # source-invalid component. Keep it for explicit repair feedback.
            break
        if any(w['execution'].get('error') or w['execution'].get('execution_error')
                for w in execution['binding_executions']):break
        cid=next_component(library,kernel,observation,failed,execution,static,policy)
        if cid is None:break
        try:
            value,receipt=read(by_id[cid])
            observation.update(value)
            reads.append({'component_id':cid,**receipt})
        except (ValueError,KeyError,TypeError,jsonschema.ValidationError) as error:
            failed[cid]=type(error).__name__+': '+str(error)
    grounded={'bindings':[{'inputs':w['inputs'],'witnesses':w['witnesses']}
        for w in execution['binding_executions']],
        'unresolved':execution['unread_components']}
    return {'plan':static,'observation':observed,'raw_observation':observation,
        'reads':reads,'component_read_order':[r['component_id']for r in reads],
        'grounded':grounded,'execution':execution,'native_scope_history':history,
        'failed_observation_components':failed,'read_policy':policy,
        'not_learned_observation_success':not bool(execution['used_observation_families'])}


def compare_reads(library,kernel,public,source_id,observation,read,*,policies=('residual_guided','ordinary_reread')):
    """One fair follow-up opportunity per policy under the same contracts."""
    initial=deepcopy(observation)
    before=evaluate(library,kernel,public,initial,source_id)
    result={'common_before':before,'eligible':not before['handled'],
        'eligibility_uses_native_answers':False,'library_sha256':digest(library),
        'initial_observation_sha256':digest(initial),'policies':{}}
    if not result['eligible']:return result
    static=plan(library,kernel);by_id={c['id']:c for c in library['components']}
    unread=set(before['unread_components'])
    bad_families={family for world in before['binding_executions']
        for check in world['source_review']['checks'] if not check['passed']
        for family in check.get('native_families',[])}
    unread.update(c['id'] for c in library['components'] if set(c['complete_native_families'])&bad_families)
    # Revisit only an unresolved observation, or a genuinely missing component.
    choice_observation={k:v for k,v in initial.items()if k not in unread}
    modes={'residual_guided':'native_residual','ordinary_reread':'direct_inputs_first'}
    for label in policies:
        policy=modes[label]
        existing_unread=set(initial)&unread
        # A strong ordinary rereader can use the actual failed component ID;
        # it need not guess an unrelated shorter schema from the static cover.
        blocked=set(by_id)-existing_unread if policy=='direct_inputs_first' and existing_unread else set()
        cid=next_component(library,kernel,choice_observation,blocked,before,static,policy)
        selection_basis='existing_unresolved_component'if blocked else 'fixed_policy'
        if cid is None and blocked:
            cid=next_component(library,kernel,choice_observation,[],before,static,policy)
            selection_basis='fixed_policy_no_existing_provider'
        if cid is None:
            result['policies'][label]={'read_requested':False,'execution':before,'reason':'No undealt-with observation provider'}
            continue
        component=by_id[cid]
        prompt=component['prompt']+'\nRe-read this same factual component. Preserve unread channels and do not copy the target as a fact.'
        failed_checks=[check['check']for w in before['binding_executions']
            for check in w['source_review']['checks']if not check['passed']]
        if failed_checks:prompt+='\nKnown source-semantic failures: '+json.dumps(failed_checks,ensure_ascii=False)
        if policy=='native_residual':
            scopes=[s for w in before['binding_executions']for s in w['execution'].get('unread_factual_scopes',[])]
            if component.get('facts_only',False):
                scopes=[{k:v for k,v in s.items()if k!='event'}for s in scopes]
            prompt+='\nActual unread native factual scopes: '+json.dumps(scopes,ensure_ascii=False)
        action={'schema':observation_schema(library,[cid]),'prompt':prompt,'component_ids':[cid],
            'facts_only':component.get('facts_only',False),'selection_basis':selection_basis}
        try:
            value,receipt=read(label,action)
            jsonschema.validate(value,action['schema'])
            updated=deepcopy(initial);updated.update(value)
            updated,normalizations=normalize(library,kernel,public,updated)
            result['policies'][label]={'read_requested':True,'action':action,'read_receipt':receipt,
                'observation_after':updated,'scope_normalization_receipts':normalizations,
                'execution':evaluate(library,kernel,public,updated,source_id)}
        except (ValueError,KeyError,TypeError,jsonschema.ValidationError)as error:
            result['policies'][label]={'read_requested':True,'execution':{'handled':False,'answer':None},
                'error':type(error).__name__+': '+str(error),'action':action}
    assert observation==initial
    result['same_initial_and_contracts_both_policies']=True
    result['comparison_success_is_not_an_innovation_certificate']=True
    return result
