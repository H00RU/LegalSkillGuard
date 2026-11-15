"""Compile supported source-token and shared-key obligations for decoding.

The model still chooses source meaning and attachment. The compact vocabulary
mask excludes invented tokens; unchanged host checks enforce contiguous source
copying. Already enumerated nominal keys need no new semantic decision.
"""
from copy import deepcopy
import re

from .span_compiler import token_spans


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
