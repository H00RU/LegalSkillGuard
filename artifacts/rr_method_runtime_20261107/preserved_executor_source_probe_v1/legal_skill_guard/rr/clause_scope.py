"""Lower explicit source scopes and legal clauses into executable guarded DAGs.

Local calculations do not discharge source obligations. The engine derives
scope inheritance from the registered public-source context, not a model's
proposed scope set. Translation faithfulness remains an explicit assumption.
"""
from __future__ import annotations

from copy import deepcopy
import re

from .coverage import Unsupported
from .scoped_program import expression_reads,graph_reads
from .source_structure import CITATION


def structural_heading(text):
    line=text.strip()
    markdown=re.match(r'^#{1,6}\s+(.+)$',line)
    if markdown:
        title=markdown[1]
        return not re.search(r'\b(?:first|second|third|fourth|over|under|between|within|except|unless|if|only)\b|\d',title,re.I)
    return bool(CITATION.fullmatch(line) or re.fullmatch(r'§\d+\. [^\n]+',line) or
                re.fullmatch(r'\([A-Za-z0-9]+\)(?:\s+[A-Z][A-Za-z -]{0,80})?',line))


def required_scope_sources(structure):
    """Recognize explicit conditional context syntax, without guessing truth."""
    ancestors={key for c in structure.ledger.clauses for key in c.context}
    result=[]
    for clause in structure.ledger.clauses:
        if clause.id not in ancestors or structure.roles[clause.id]['role']!='rule':continue
        text=structure.ledger.text[clause.start:clause.end].strip()
        if re.search(r'\bif\s*[-:]\s*$|\bunless\b|\bprovided that\b',text,re.I) or \
                re.match(r'For purposes of .*\brefer\b',text,re.I):
            result.append(clause.id)
    return tuple(result)


def lower_clauses(structure,program):
    units={c.id:c for c in structure.ledger.clauses}
    local=deepcopy(program['nodes']);definitions=list(local)
    names=[n['name'] for n in local]+[s['name'] for s in program['scopes']]+[c['name'] for c in program['clauses']]
    if len(names)!=len(set(names)):raise Unsupported('Local, scope and clause names must be unique')
    scope_by_source={};scope_names=set();scope_declarations={}
    for scope in program['scopes']:
        source=scope['source'];name=scope['name'];condition=scope['condition']
        if source in scope_by_source or structure.roles[source]['role']!='rule':
            raise Unsupported('Each scope owns one distinct actual rule source')
        text=structure.ledger.text[units[source].start:units[source].end]
        if type(condition) is bool and not (condition is True and structural_heading(text)):
            raise Unsupported('Only a structural title can have a literal unconditional scope')
        scope_by_source[source]=name;scope_names.add(name);scope_declarations[name]=scope
        definitions.append({'name':name,'kind':'expression','body':condition})
    covered=set();used_scopes=set();clauses=[]
    required=set(required_scope_sources(structure))
    for clause in program['clauses']:
        sources=set(clause['sources'])
        if len(sources)!=len(clause['sources']) or any(structure.roles[s]['role']!='rule' for s in sources):
            raise Unsupported('Clause ownership requires distinct rule units, not facts or query labels')
        context=structure.ledger.closure(sources)
        applicable=sorted(scope_by_source[s] for s in context if s in scope_by_source)
        condition={'op':'and','args':[{'var':name} for name in applicable]}
        definitions.append({'name':clause['name'],'kind':'expression','body':{'op':'if',
            'args':[condition,deepcopy(clause['value']),deepcopy(clause['otherwise'])]}})
        covered.update(sources);used_scopes.update(applicable)
        clauses.append({'name':clause['name'],'sources':sorted(sources),
                        'context':sorted(context),'enforced_scopes':applicable})
    covered.update(scope_declarations[name]['source'] for name in used_scopes)
    # Citing an explicit conditional preface as an ordinary value cannot stand
    # in for a Boolean scope attached to the affected child clauses.
    missing=required-set(scope_by_source)
    covered-=missing
    clause_names={c['name'] for c in program['clauses']}
    query_reads=expression_reads(program['query'])
    if not query_reads&clause_names or query_reads&(set(names)-clause_names):
        raise Unsupported('Native answer query must use guarded clause outputs, not bypass them through local/scope nodes')
    remaining={n['name']:n for n in definitions};ordered=[]
    # Only dependencies on definitions take part; public inputs and unresolved
    # observations are checked by the existing all-branch type checker.
    while remaining:
        ready=[]
        for name,node in remaining.items():
            reads=expression_reads(node['body']) if node['kind']=='expression' else graph_reads(node['body']['graph'])
            if not reads&set(remaining):ready.append(name)
        if not ready:raise Unsupported('Cyclic local/scope/clause definitions')
        for name in ready:ordered.append(remaining.pop(name))
    return {'nodes':ordered,'covered':covered,'scope_names':scope_names,
            'scope_bindings':clauses,'missing_scope_sources':sorted(missing),
            'unused_scope_sources':sorted(s['source'] for s in program['scopes'] if s['name'] not in used_scopes)}
