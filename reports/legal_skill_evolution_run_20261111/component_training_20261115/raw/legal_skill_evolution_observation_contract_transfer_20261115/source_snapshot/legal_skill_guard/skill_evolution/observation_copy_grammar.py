"""Compile existing literal-copy and shared-key obligations for decoding.

The model still chooses source meaning and attachment. This finite grammar
supplies source spellings and already enumerated nominal keys; no facts,
dates, relations or absent properties are created by the compiler.
"""
from copy import deepcopy

from .span_compiler import token_spans


def compile_wire(wire, contract, relation, facts, prior):
    result=deepcopy(wire)
    group=next(g for g in contract['relations']if g['name']==relation)
    complete=result['properties'][relation]['anyOf'][0]['properties']['records']
    item=complete['items']
    tokens=token_spans(facts)
    # Every accepted copy is a contiguous token sequence. Raw spelling gives
    # a canonical representative of each sequence; punctuation is preserved.
    spans=list(dict.fromkeys(facts[start:end]for i,(_,start,_)in enumerate(tokens)
        for _,_,end in tokens[i:]))
    fields=[]
    for field in group['fields']:
        name=field['name']
        if name==group['key']or not field.get('copy')or field.get('type','string')!='string':continue
        rule=item['properties'][name]
        if 'enum'in rule:continue
        values=spans+([None]if field.get('nullable')else[])
        if values:
            rule['enum']=values
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
    return result,{'literal_copy_fields':fields,'source_token_sequences':len(spans),
        'shared_key_transport':key_receipt,'semantic_facts_added':False,
        'prompt_schema_unchanged':True,'host_source_checks_unchanged':True}
