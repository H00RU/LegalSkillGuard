"""Bind observed service/payment identities to the public native-call ABI.

No source fact, role, date, event or legal rule is generated here. Ground role
arguments filter source events; queries without such arguments require a unique
literal kind match. Unknown or ambiguous identity remains unresolved.
"""
from copy import deepcopy

from .statute_input_dependencies import query_event_inputs


def bind(kernel,part):
    value=deepcopy(part)
    receipt={'source_facts_changed':False,'bindings':[],'binding_demands':[],
             'no_source_or_answer_lookup':True}
    if not value['complete']or value['reasons']:return value,receipt
    facts=value['facts'];events=[f['arguments'][0]for f in facts if f['predicate']in ('service_','payment_')]
    mapping={}
    def values(predicate,event):return [f['arguments'][1]for f in facts
        if f['predicate']==predicate and f['arguments'][0]==event]
    def closed(predicate,event):
        # Legacy complete encoders cover their whole event. Relational readers
        # close only the properties explicitly read, never the whole event.
        if 'scope_contract'not in value:return True
        return {'event':event,'predicate':predicate}in value['scope_contract']['event_properties']
    declarations=query_event_inputs(kernel)
    for call in kernel['native_query']:
        for declaration in (d for d in declarations if d['predicate']==call['predicate']):
            target=call['arguments'][declaration['argument']]
            if not isinstance(target,str):continue
            family_events=[f['arguments'][0]for f in facts if f['predicate']==declaration['family']]
            constraints={p:call['arguments'][i]for p,i in declaration['role_arguments'].items()
                if isinstance(call['arguments'][i],str)}
            if not family_events:continue  # Empty scans never invent a referent.
            candidates=[];unknown=[]
            for event in family_events:
                if constraints:
                    missing=[p for p,v in constraints.items()if v not in values(p,event)]
                    if any(closed(p,event)for p in missing):continue
                else:
                    if event==target or target in values('purpose_',event)or target in values('type_',event):
                        missing=[]
                    else:
                        missing=[p for p in ('purpose_','type_')if not closed(p,event)]
                        if not missing:continue
                if missing:unknown.extend({'source_event':event,'predicate':p,
                    'family':declaration['family']}for p in missing)
                else:candidates.append(event)
            if unknown:
                # Even a known match is not unique while another source event
                # could still match. Request source roles, never desired values.
                receipt['binding_demands'].extend(d for d in unknown if d not in receipt['binding_demands'])
                value['complete']=False;value['reasons'].append('source_event_identity_needs_unread_properties')
                return value,receipt
            if len(candidates)!=1 or candidates[0]in mapping and mapping[candidates[0]]!=target:
                value['complete']=False;value['reasons'].append('source_service_identity_unknown_or_ambiguous')
                return value,receipt
            event=candidates[0];mapping[event]=target
            receipt['bindings'].append({'source_event':event,'native_event':target,
                'basis':'observed_roles'if constraints else 'literal_observed_kind',
                'public_query':call['predicate']})
    if len({mapping.get(e,e)for e in events})!=len(events):
        value['complete']=False;value['reasons'].append('native_service_identity_collision')
        return value,receipt
    # Current converters generate fresh nominal event IDs. Do not rename a
    # literal person if an invalid source encoding reused that ID as an entity.
    if any(f['predicate']in ('agent_','patient_')and f['arguments'][1]in mapping for f in facts):
        value['complete']=False;value['reasons'].append('source_event_entity_identity_collision')
        return value,receipt
    for f in value['facts']:
        f['arguments']=[mapping.get(a,a)if isinstance(a,str)else a for a in f['arguments']]
    receipt['only_nominal_event_ids_renamed']=True
    receipt['source_facts_changed']=False
    return value,receipt
