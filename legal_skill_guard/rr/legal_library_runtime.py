"""Execute the acquired legal library with its source-condition call interfaces.

No raw query repair, invented callees, or implicit closure of named people.
The relation/amount solver and this shared call runtime are open to controls.
"""
from copy import deepcopy
from .legal_predicate_skills import evaluate_guard,run,var


def execute_library(library,case):
    program=library['program'];predicates={p['name']:p for p in program['predicates']}
    query=case['query'];native=run(program,case)
    if predicates[query['predicate']]['functional']:
        return {'answer':native['answer'],'mechanism':'scoped_terminal_effects',
                'source_calls':[],'proof':native,'unbounded_roles_not_closed':True}
    rules=[r for r in program['rules'] if r['head']['predicate']==query['predicate'] and r['head']['positive']==query['positive']]
    if len(rules)!=1:
        raise ValueError('The acquired pilot call needs one explicit source antecedent')
    rule=rules[0]
    condition=evaluate_guard(program,case,rule['id'])
    body=rule['body'][0];calls=[];seen=set()
    for predicate,arguments,positive in native.get('known_atoms',[]):
        if predicate!=body['predicate']:continue
        env={};matches=True
        for term,value in zip(body['arguments'],arguments):
            if var(term):
                if term in env and env[term]!=value:matches=False;break
                env[term]=value
            elif term!=value:matches=False;break
        if not matches:continue
        bound=[]
        for term in rule['head']['arguments']:
            if var(term) and term not in env:
                raise ValueError('Callee observation does not bind this source call')
            bound.append(env.get(term,term))
        if not all(q is None or q==value for q,value in zip(query['arguments'],bound)):continue
        identity=tuple(bound)
        if identity in seen:continue
        seen.add(identity)
        point={**case,'query':{**query,'arguments':bound}}
        result=evaluate_guard(program,point,rule['id'])
        calls.append({'arguments':bound,'observed_callee_polarity':positive,
                      'condition':result,'callee_recompiled':False})
    # Evaluating a clause antecedent is distinct from negating every possible
    # head derivation. These pilot applicability interfaces have one acquired
    # source condition; native inference remains checked by the shared solver.
    if condition['condition_value'] is True:
        if native.get('query_supported') is not True or native.get('query_refuted') is True:
            raise ValueError('Source call and native applicability evidence disagree')
        answer='Entailment'
    elif condition['condition_value'] is False and None not in query['arguments']:
        answer='Contradiction'
    else:answer=None
    return {'answer':answer,'mechanism':'source_condition_call','source_rule':rule['id'],
            'source_condition':condition,'source_calls':calls,'proof':native,
            'unbounded_roles_not_closed':True,
            'source_module_dependencies_unresolved':list(program['unresolved'])}
