"""Typed public primitives with explicit multi-unit evidence, without aliases."""
from .coverage import Unsupported
from .engine import decode_slots
from .grounding import binding_literal_audit


def decode_source_bindings(bindings,units):
    decoded=[];contexts={};covered=set();checks=[]
    names={b['name'] for b in bindings}
    for i,binding in enumerate(bindings):
        if set(binding)!={'name','type','value','sources'}:
            raise Unsupported('A source primitive needs name/type/value/sources')
        sources=binding['sources']
        if not sources or len(sources)!=len(set(sources)) or not set(sources)<=set(units):
            raise Unsupported('Primitive evidence requires distinct actual source units')
        text='\n'.join(units[s] for s in sources)
        context='primitive_evidence_'+str(i);contexts[context]=text;covered.update(sources)
        decoded.append({k:binding[k] for k in ('name','type','value')}|{'source':context})
        checks.append({'binding':binding['name'],'sources':list(sources),
            **binding_literal_audit(binding['type'],binding['value'],text,names)})
    if not all(c['pass'] for c in checks):
        raise Unsupported('Public literal grounding failed: '+str([c for c in checks if not c['pass']]))
    slots,_=decode_slots({'bindings':decoded},set(contexts),contexts)
    return slots,covered,checks
