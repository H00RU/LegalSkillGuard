"""Select source evidence by identity; attach the literal source deterministically.

This removes error-prone text copying. It provides no legal values and does
not certify that a selected source unit entails a semantic judgment.
"""
import json

import jsonschema

from .native import record_schema
from .semantic_execution import focused_messages,strict_json
from .semantic_operations import ground_answers


def schema(operations,queries):
    ops={o['name']:o for o in operations}
    fields={}
    for q in queries:
        def branch(choices,minimum):
            return record_schema({'choice':{'type':'string','enum':choices},
                'support_ids':{'type':'array','minItems':minimum,
                    'items':{'type':'integer','enum':q['unit_ids']}}})
        fields[q['id']]={'anyOf':[
            branch([c['name'] for c in ops[q['operation']]['choices']],1),
            branch(['unknown'],0)]}
    return record_schema({'answers':record_schema(fields)})


def messages(operations,queries,units,*,scope):
    prompt=focused_messages(operations,queries,units,scope=scope)
    start=prompt[0]['content'].index('For every non-unknown choice, quote')
    end=prompt[0]['content'].index('No extra IDs or fields.',start)+len('No extra IDs or fields.')
    replacement=('For every non-unknown choice, select at least one supporting current unit ID '
        'inside this query\'s supplied unit IDs. Return support_ids instead of copying text; '
        'the host attaches the exact complete text of selected units. Negative alternatives '
        'also need actual source support; mere absence is insufficient unless the acquired '
        'operation explicitly asks whether something appears in the complete supplied window. '
        'Do not repeat support IDs. No extra IDs or fields.')
    prompt[0]['content']=prompt[0]['content'][:start]+replacement+prompt[0]['content'][end:]
    return prompt


def decode(operations,queries,units,content):
    value=strict_json(content);jsonschema.validate(value,schema(operations,queries))
    source={u['id']:u['text'] for u in units};answers=[]
    for q in queries:
        a=value['answers'][q['id']];ids=a['support_ids']
        if len(set(ids))!=len(ids):raise ValueError('Repeated source support identity')
        answers.append({'id':q['id'],'choice':a['choice'],
            'evidence':[{'unit_id':i,'quote':source[i]} for i in ids]})
    return value,ground_answers(operations,queries,units,{'answers':answers})
