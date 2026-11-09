"""Checked TRAIN compiler programs shared by all inference arms.

Templates demonstrate translation, never supply the current source's answer.
Python source programs may be partial: their original unknown source scopes
remain unknown on every compile. Storing material is not a completion proof.
Only original earlier TRAIN sources may enter a caller's library prefix.
"""
from copy import deepcopy

from .coverage import digest


def validate_template(item):
    from .model_horn import parse_model_horn
    if set(item)!={'language','source','code','origin','template_hash'}:
        raise ValueError('Compiler template has unknown or missing fields')
    value={k:item[k] for k in ('language','source','code','origin')}
    if digest(value)!=item['template_hash']:raise ValueError('Compiler template hash differs')
    source=item['source']
    if source['content_hash']!=digest(source['public']):raise ValueError('Compiler template public input differs')
    if set(source)&{'answer','targets','grade','score','reference_program','reference_arguments'}:
        raise ValueError('Compiler templates cannot contain grading information')
    origin=item['origin']
    if origin['role']!='teacher' or not origin['call_id'] or not origin['request_hash']:
        raise ValueError('Compiler material needs preserved teacher request provenance')
    if item['language']=='source_annotated_horn_v1':
        parsed=parse_model_horn(source,item['code'])
        if parsed.export()['missing_units']:raise ValueError('An incomplete program cannot teach whole-source compilation')
    elif item['language']=='source_annotated_python_v1':
        from .pal_frontend import lower_pal
        from .source_program import compile_source
        if source['dataset']=='ProofWriter_OWA_depth5':raise ValueError('Use the logic template language for ProofWriter')
        parsed=compile_source(source,lower_pal(source,item['code'])[0])
    else:raise ValueError('Unknown compiler template language')
    return parsed


def make_template(source,code,origin):
    language='source_annotated_horn_v1' if source['dataset']=='ProofWriter_OWA_depth5' else 'source_annotated_python_v1'
    item={'language':language,'source':deepcopy(source),'code':code,'origin':deepcopy(origin)}
    item['template_hash']=digest(item);validate_template(item);return item


def template_examples(source,library):
    from .source_structure import inspect_source
    result=[]
    for item in (library or {}).get('compiler_templates',[]):
        validate_template(item)
        previous=item['source']
        if previous['key']==source['key']:raise ValueError('Compiler template cannot provide the current program')
        if previous['dataset']!=source['dataset']:continue
        structure=inspect_source(previous)
        result.append({'template_hash':item['template_hash'],
            'units':[{'id':c.id,'role':structure.roles[c.id]['role'],
                      'text':structure.ledger.text[c.start:c.end]} for c in structure.ledger.clauses],
            'code':item['code']})
    return result
