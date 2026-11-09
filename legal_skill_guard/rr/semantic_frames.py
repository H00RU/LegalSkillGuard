"""Shared light source-role frontend for the first semantic-channel pilot.

Pointer membership is deterministic; relation truth remains a model claim.
All baselines receive exactly these fields and the same original source.
"""
from dataclasses import dataclass
from .coverage import digest


def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


TEXT_OR_UNKNOWN={'anyOf':[{'type':'string'},{'type':'null'}]}
BOOL_OR_UNKNOWN={'anyOf':[{'type':'boolean'},{'type':'null'}]}
FRAME_SCHEMA=obj({name:TEXT_OR_UNKNOWN for name in ('payer','payee','work_activity','payment_medium')} |
    {name:BOOL_OR_UNKNOWN for name in ('work_is_agricultural','payment_is_agricultural_product')})
READER_SCHEMA=obj({'agricultural_remuneration':BOOL_OR_UNKNOWN,'payment_in_agricultural_products':BOOL_OR_UNKNOWN,
    'evidence_work':TEXT_OR_UNKNOWN,'evidence_medium':TEXT_OR_UNKNOWN})


def occurrences(text, value):
    if value is None:return []
    if not isinstance(value,str) or not value.strip():raise ValueError('Use a real exact span or null, never an empty pointer')
    positions=[];start=0
    while True:
        start=text.find(value,start)
        if start<0:break
        positions.append([start,start+len(value)]);start+=1
    if not positions:raise ValueError('A predicted pointer is not in the original facts: '+value)
    return positions


def decode_frame(value,text):
    if set(value)!=set(FRAME_SCHEMA['properties']):raise ValueError('Shared frame fields differ')
    for name in ('work_is_agricultural','payment_is_agricultural_product'):
        if value[name] is not None and type(value[name]) is not bool:raise ValueError('Role classification must be Boolean or unknown')
    return {'values':value,'source_pointers':{name:occurrences(text,value[name]) for name in ('payer','payee','work_activity','payment_medium')},
            'source_text_sha256':digest(text),'role_truth_proved_by_pointer':False}


def decode_reader(value,text):
    if set(value)!=set(READER_SCHEMA['properties']):raise ValueError('Reader fields differ')
    for name in ('agricultural_remuneration','payment_in_agricultural_products'):
        if value[name] is not None and type(value[name]) is not bool:raise ValueError('Reader answer must be Boolean or unknown')
    return {'values':value,'source_pointers':{name:occurrences(text,value[name]) for name in ('evidence_work','evidence_medium')},
            'source_text_sha256':digest(text),'semantic_truth_proved':False}


def label(value):
    if value is None:return 2
    if type(value) is not bool:raise ValueError('Only Boolean/unknown labels are supported in this pilot')
    return int(value)


def frame_vector(frame):
    value=frame['values'];return [label(value['work_is_agricultural']),label(value['payment_is_agricultural_product'])]


def reader_vector(reader):
    value=reader['values'];return [label(value['agricultural_remuneration']),label(value['payment_in_agricultural_products'])]


def exact_edit(text,before,after):
    if text.count(before)!=1:raise ValueError('A controlled edit needs one unambiguous original span')
    start=text.index(before)
    changed=text[:start]+after+text[start+len(before):]
    return changed,{'start':start,'end':start+len(before),'before':before,'after':after,
        'outside_span_preserved':changed[:start]==text[:start] and changed[start+len(after):]==text[start+len(before):]}
