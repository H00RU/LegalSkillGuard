"""Projection of a complete one-condition definition in an explicit finite scope.

This implements ordinary finite existential evaluation. It is NOT completion of
an arbitrary Horn program, nor a rule that missing atoms are false. The caller
must justify that the supplied rule defines the target condition completely and
that each declared free-variable domain exhausts the task scope. Without finite
scope only explicit positive witnesses can settle an existential projection.
"""
from itertools import product
from .legal_predicate_skills import var


def project_definition(rule,facts,query,free_domains=None):
    if len(rule['body'])!=1:raise ValueError('One-condition complete definitions only')
    head=rule['head'];body=rule['body'][0]
    if not head['positive'] or not body['positive'] or not query['positive']:
        raise ValueError('Positive definition and query required')
    if query['predicate']!=head['predicate'] or len(query['arguments'])!=len(head['arguments']):
        raise ValueError('Target definition/query mismatch')
    env={};free=set()
    for t,v in zip(head['arguments'],query['arguments']):
        if var(t):
            if v is None:free.add(t)
            elif t in env and env[t]!=v:raise ValueError('Inconsistent repeated head role')
            else:env[t]=v
        elif v is not None and t!=v:raise ValueError('Query conflicts with definition constant')
    free-=set(env)
    used={t for t in body['arguments'] if var(t)}|{t for d in rule['different'] for t in d.values() if var(t)}
    if used-set(env)-free:raise ValueError('Unbound definition variable')
    lookup={}
    for row in facts:
        atom=row['atom']
        lookup.setdefault((atom['predicate'],tuple(atom['arguments'])),set()).add(atom['positive'])
    def instantiate(terms,e):return tuple(e[t] if var(t) else t for t in terms)
    def eligible(e):
        return all(instantiate([d['left']],e)!=instantiate([d['right']],e) for d in rule['different'])
    # Positive witnesses remain valid without claiming a complete domain.
    if free_domains is None and not free:
        candidates=[env] if eligible(env) else []
        complete=True
    elif free_domains is None:
        candidates=[]
        for pred,args in lookup:
            if pred!=body['predicate'] or len(args)!=len(body['arguments']):continue
            e=dict(env)
            for term,val in zip(body['arguments'],args):
                if var(term):
                    if term in e and e[term]!=val:break
                    e[term]=val
                elif term!=val:break
            else:
                if free<=set(e) and eligible(e):candidates.append(e)
        complete=not free
    else:
        if set(free_domains)!=free:raise ValueError('Finite domains must cover exactly the projected variables')
        for values in free_domains.values():
            if not isinstance(values,list) or any(not isinstance(v,str) or not v for v in values) or len(values)!=len(set(values)):
                raise ValueError('Explicit unique nonempty-string domain values required')
        variables=sorted(free)
        candidates=[env|dict(zip(variables,values)) for values in product(*(free_domains[v] for v in variables))]
        candidates=[e for e in candidates if eligible(e)];complete=True
    proofs=[]
    for e in candidates:
        args=instantiate(body['arguments'],e);polarities=lookup.get((body['predicate'],args),set())
        truth=True if polarities=={True} else False if polarities=={False} else None
        proofs.append({'bindings':e,'condition_predicate':body['predicate'],'condition_arguments':list(args),
            'condition_truth':truth,'explicit_polarities':sorted(polarities)})
    if any(p['condition_truth'] is True for p in proofs):answer=True
    elif complete and all(p['condition_truth'] is False for p in proofs):answer=False
    else:answer=None
    return {'value':answer,'domain_complete_for_this_projection':complete,'witnesses':proofs,
        'missing_condition_values_defaulted_false':False,'definition_rule_id':rule['id'],
        'definition_completeness_is_caller_source_obligation':True}
