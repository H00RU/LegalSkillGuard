"""Controlled-English Horn symbol serialization and exact alpha comparison.

Only the six verb inflections already defined by the public parser and entity
case normalization are reused. No sentence/rule parser is called, no missing
atom is supplied, and no reference answer participates in this codec.
"""
from copy import deepcopy
import itertools

from legal_skill_guard.rr.public_horn import VERBS


def atom(value):
    if not isinstance(value,list) or len(value)!=3 or not isinstance(value[0],str) or not isinstance(value[1],list) or not all(isinstance(t,str) for t in value[1]) or type(value[2])is not bool:raise ValueError('Invalid Horn atom tuple')
    predicate=value[0].casefold()
    return [VERBS.get(predicate,predicate),[x if x.startswith('?') else x.casefold() for x in value[1]],value[2]]


def normalize(program):
    if not isinstance(program,dict) or set(program)!={'facts','rules','query'}:raise ValueError('Horn root fields')
    rules=[]
    for rule in program['rules']:
        if set(rule)!={'body','head'}:raise ValueError('Horn rule fields')
        head=atom(rule['head']);body=[atom(a) for a in rule['body']];variables={}
        for a in [head]+body:
            for term in a[1]:
                if term.startswith('?') and term not in variables:
                    i=len(variables);variables[term]='?x' if i==0 else '?y' if i==1 else '?v'+str(i)
        def rename(a):return [a[0],[variables.get(t,t) for t in a[1]],a[2]]
        rules.append({'body':[rename(a) for a in body],'head':rename(head)})
    return {'facts':[atom(a) for a in program['facts']], 'rules':rules,'query':atom(program['query'])}


def rule_key(rule):
    variables=sorted({t for a in rule['body']+[rule['head']] for t in a[1] if t.startswith('?')})
    # Actual native open theories have at most two variables per rule. Unknown
    # very large cases are unverified constraints, not silently accepted.
    if len(variables)>6:raise ValueError('Alpha comparison outside bounded verified variable domain')
    keys=[]
    for permutation in itertools.permutations(range(len(variables))):
        mapping=dict(zip(variables,permutation))
        def key(a):return (a[0],tuple(('var',mapping[t]) if t in mapping else ('constant',t) for t in a[1]),a[2])
        keys.append((key(rule['head']),tuple(sorted(key(a) for a in rule['body']))))
    return min(keys)


def rules_key(rules):return tuple(sorted(rule_key(r) for r in rules))


def theory_key(program):
    p=normalize(program)
    def key(a):return a[0],tuple(a[1]),a[2]
    return tuple(sorted(key(a) for a in p['facts'])),rules_key(p['rules']),key(p['query'])
