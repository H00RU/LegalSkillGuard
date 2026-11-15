"""Compile supported source-token and shared-key obligations for decoding.

The model still chooses source meaning and attachment. The compact vocabulary
mask excludes invented tokens; unchanged host checks enforce contiguous source
copying. Already enumerated nominal keys need no new semantic decision.
"""
from copy import deepcopy
import re

from .span_compiler import token_spans


def enumeration_schema(original,contract,relation,prior):
    """Remove a purely nominal key from the first enumeration's model task.

    The model still chooses how many distinct source occurrences to enumerate
    and all their attributes. The host only names those rows. Later relations
    use these exact keys through the existing shared-key decoder.
    """
    result=deepcopy(original)
    if relation!=contract['enumerator']or any(g['name']in prior for g in contract['relations']):
        return result,False
    group=next(g for g in contract['relations']if g['name']==relation)
    key=group['key'];field=next(f for f in group['fields']if f['name']==key)
    if field.get('copy'):raise ValueError('A source-copied identity is not a host nominal key')
    positions={g['name']:[f['name']for f in g['fields']].index(g['key'])for g in contract['relations']}
    for rule in contract['rules']:
        for atom in rule['body']:
            if atom['predicate']!=relation:continue
            variable=atom['arguments'][positions[relation]]
            if not isinstance(variable,dict)or set(variable)!={'var'}:
                raise ValueError('A source-key constant cannot be replaced by a nominal row identity')
            if any(arg==variable and i!=positions[other['predicate']]
                   for other in rule['body']for i,arg in enumerate(other['arguments'])):
                raise ValueError('A factual attribute cannot be replaced by a nominal row identity')
    item=result['properties'][relation]['anyOf'][0]['properties']['records']['items']
    item['properties'].pop(key);item['required'].remove(key)
    return result,True


def assign_enumerator_keys(value,group,component):
    result=deepcopy(value);observed=result[group['name']]
    if observed['status']=='complete':
        for index,row in enumerate(observed['records']):
            if group['key']in row:raise ValueError('A host-keyed enumeration cannot accept model-assigned keys')
            row[group['key']]=component+'_row_'+str(index)
    return result


def compile_wire(wire, contract, relation, facts, prior):
    result=deepcopy(wire)
    group=next(g for g in contract['relations']if g['name']==relation)
    complete=result['properties'][relation]['anyOf'][0]['properties']['records']
    item=complete['items']
    tokens=token_spans(facts)
    vocabulary=list(dict.fromkeys(t[0]for t in tokens))
    pattern=r'^(?:'+ '|'.join(re.escape(t)for t in sorted(vocabulary,key=lambda t:(-len(t),t)))+r'|\s)+$'
    fields=[]
    for field in group['fields']:
        name=field['name']
        if name==group['key']or not field.get('copy')or field.get('type','string')!='string':continue
        rule=item['properties'][name]
        if 'enum'in rule:continue
        if vocabulary:
            rule['pattern']=pattern
            fields.append(name)
    key_receipt={'used':False}
    enumerator=prior.get(contract['enumerator'])
    if relation!=contract['enumerator']and isinstance(enumerator,dict)and enumerator.get('status')=='complete':
        keys=[r[group['key']]for r in enumerator['records']]
        rows=[]
        for key in keys:
            row=deepcopy(item)
            row['properties'][group['key']]={'const':key}
            rows.append(row)
        complete.clear()
        complete.update(type='array',prefixItems=rows,items=False,minItems=len(rows),maxItems=len(rows))
        key_receipt={'used':True,'keys':keys,'same_observed_enumerator_not_a_new_scan':True}
    return result,{'literal_copy_fields':fields,'source_vocabulary_tokens':len(vocabulary),
        'shared_key_transport':key_receipt,'semantic_facts_added':False,
        'prompt_schema_unchanged':True,'host_source_checks_unchanged':True,
        'full_contiguous_source_copy_still_required_by_host':True}
