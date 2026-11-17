"""Compose existing certified finite pairs into a source-bound consumer.

Programs contain data-only boolean expressions, never arbitrary executable
source. A generated local predicate cannot directly be a native answer field.
Composition preserves each local consumer and its declared identity binding;
the certificate does not claim correctness of English reading or legal scope.
"""
from copy import deepcopy

from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


def evaluate(expression,local):
    if 'constant' in expression:return expression['constant']
    if 'local' in expression:
        unit,key=expression['local'];return local.get(unit,{}).get(key)
    if 'all' in expression or 'any' in expression:
        kind='all' if 'all' in expression else 'any'
        values=[evaluate(e,local) for e in expression[kind]]
        if any(type(v) not in (bool,type(None)) for v in values):
            raise ValueError('Boolean composition requires explicit boolean/unknown local outputs')
        if kind=='all':return False if False in values else None if None in values else True
        return True if True in values else None if None in values else False
    if 'if' in expression:
        value=evaluate(expression['if'],local)
        if value is None:return None
        if type(value) is not bool:raise ValueError('A conditional guard must be boolean')
        return evaluate(expression['then'] if value else expression['else'],local)
    raise ValueError('Unsupported closed consumer expression')


def schema(program):
    return record_schema({name:residual.reader_schema(unit['asset']) for name,unit in program['units'].items()})


def verify(program):
    expected=digest({k:v for k,v in program.items() if k!='program_sha256'})
    if program.get('program_sha256')!=expected:raise ValueError('Relational consumer program changed')
    for unit in program['units'].values():
        asset=unit['asset']
        if digest(asset)!=unit['asset_sha256'] or asset['module_binding']!=unit['module_binding']:
            raise ValueError('A local certified pair changed')
        if not asset['certificate']['all_outputs_preserved']:
            raise ValueError('Local equivalence is required for program composition')
    return True


def decode(program,raw,public_source):
    verify(program)
    if set(raw)!=set(program['units']):raise ValueError('A source-local unit was lost or duplicated')
    local={};receipts={}
    for name,unit in program['units'].items():
        asset=unit['asset'];reading=raw[name]
        receipt=residual.validate_read(asset,reading,public_source)
        anchor=(reading.get('observation') or {}).get('source_anchor') if asset['layout']=='anchored' else reading.get('source_anchor')
        if receipt['supported'] and anchor!=name:raise ValueError('Source unit identity was exchanged')
        outcome=(residual.decode(asset,receipt['values'],unit.get('context',{}),module_binding=unit['module_binding'])
            if receipt['supported'] else {'valid':False,'unresolved':'unread source unit'})
        local[name]=outcome.get('outputs',{}) if outcome['valid'] else {}
        receipts[name]={'source_read':receipt,'consumer':outcome}
    outputs={task:evaluate(expression,local) for task,expression in program['outputs'].items()}
    diagnostics={key:evaluate(expression,local) for key,expression in program.get('diagnostics',{}).items()}
    return {'outputs':outputs,'diagnostics':diagnostics,'local_receipts':receipts,
        'source_semantics_verified_by_inference_oracle':False,
        'method_one_relational_pair_executed':True,'local_unknown_preserved':True}


def prompt(program):
    lines=['Read the public source using each identified local unit below. Return the combined supplied JSON schema.',
        'Use the exact unit key as its source_anchor. Preserve entity and claim attachment; never exchange unit readings.',
        'Read local attributes/relations only, without returning a jurisdiction or native task classification.']
    # A template appears once even when instantiated for several entity pairs.
    seen={}
    for name,unit in program['units'].items():
        key=unit['template_key']
        if key not in seen:
            seen[key]=True;lines.append('Template '+key+':\n'+residual.reader_prompt(unit['asset']))
        lines.append('Unit '+name+' uses '+key+'. Entity context: '+residual.canonical(unit['entity_context']))
    return '\n'.join(lines)


def sealed(program):
    value=deepcopy(program);value['program_sha256']=digest(value);verify(value);return value
