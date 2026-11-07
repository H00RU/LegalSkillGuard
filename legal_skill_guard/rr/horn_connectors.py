"""Public controlled-grammar primitives and source-only connector execution.

Parsing/matching/closure are predefined components, not learned legal rules.
The B runtime executes actual immutable learned graphs for shared-witness joins.
This module never imports training grades, reference oracles or model clients.
"""
from __future__ import annotations

import time

from .coverage import Unsupported,digest
from .horn import Atom
from .interfaces import Connector,Relation
from .public_horn import parse_public
from .scoped_program import compile_query


def matches(pattern:Atom,facts:set[Atom])->Relation:
    columns=tuple(dict.fromkeys(a for a in pattern.arguments if a.startswith('?')))
    rows=[]
    for fact in sorted(facts):
        if (pattern.predicate,pattern.positive,len(pattern.arguments))!=(fact.predicate,fact.positive,len(fact.arguments)):continue
        binding={}
        for formal,actual in zip(pattern.arguments,fact.arguments):
            if formal.startswith('?'):
                if formal in binding and binding[formal]!=actual:break
                binding[formal]=actual
            elif formal!=actual:break
        else:rows.append(tuple(binding[c] for c in columns))
    return Relation(columns,tuple(rows))


def rule_graph(rule,*,erase_equalities:bool)->dict:
    graph={'slot':'atom0'}
    columns={x for x in rule.body[0].arguments if x.startswith('?')}
    for i,atom in enumerate(rule.body[1:],1):
        current={x for x in atom.arguments if x.startswith('?')}
        shared=sorted(columns&current);right={'slot':f'atom{i}'}
        if erase_equalities and shared:
            renamed=[f'rhs{i}_{x}' for x in shared]
            right={'op':'bind_rename','inputs':[right],'params':{'from':shared,'to':renamed}}
            current=(current-set(shared))|set(renamed);shared=[]
        graph={'op':'join_on','inputs':[graph,right],'params':{'keys':shared}};columns|=current
    return graph


def horn_sketches(public):
    parsed=parse_public(public)
    if parsed.residuals:return []
    n=len(parsed.rules)
    masks=[set(),set(range(n))]+[{i} for i in range(n)]+[set(range(n))-{i} for i in range(n)]
    result=[];seen=set()
    for mask in masks:
        graphs=[rule_graph(r,erase_equalities=i in mask) for i,r in enumerate(parsed.rules)]
        key=digest(graphs)
        if key not in seen:seen.add(key);result.append(graphs)
        if len(result)==32:break
    return result


def closure(parsed,execute,*,seconds=5):
    facts=set(parsed.facts);deadline=time.monotonic()+seconds
    for iteration in range(32):
        new=set()
        for index,rule in enumerate(parsed.rules):
            if time.monotonic()>=deadline:return {'status':'budget_exhausted','answer':None}
            relation=execute(index,rule,facts,iteration)
            for row in relation.rows:
                bound=dict(zip(relation.columns,row))
                if any(x.startswith('?') and x not in bound for x in rule.head.arguments):
                    return {'status':'missing_witness','answer':None}
                new.add(Atom(rule.head.predicate,tuple(bound.get(x,x) for x in rule.head.arguments),rule.head.positive))
        if new<=facts:
            if parsed.query in facts and parsed.query.negate() in facts:return {'status':'conflict','answer':None}
            return {'status':'closure_complete','answer':'True' if parsed.query in facts else 'False' if parsed.query.negate() in facts else 'Unknown',
                    'iterations':iteration+1,'derived_fact_count':len(facts)-len(parsed.facts)}
        facts|=new
    return {'status':'budget_exhausted','answer':None}


def predict_horn_sketch(public,graphs):
    parsed=parse_public(public)
    if parsed.residuals or len(graphs)!=len(parsed.rules):return None
    def execute(index,rule,facts,iteration):
        return Connector(graphs[index]).execute({f'atom{i}':matches(a,facts) for i,a in enumerate(rule.body)})
    return closure(parsed,execute)['answer']


def _learned_join(library,left,right,keys):
    choices=[]
    for item in library.get('patterns',[]):
        if 'entity_equality' not in item['pattern']['fields']:continue
        for variant,graph in enumerate(item['pattern']['graphs']):
            if graph.get('op')!='join_on' or len(graph.get('inputs',[]))!=2 or \
                    any(set(x)!={'slot'} for x in graph['inputs']):continue
            columns=graph.get('params',{}).get('keys',[])
            if len(columns)!=len(keys) or not all(c.startswith('column') for c in columns):continue
            choices.append((item['pattern_hash'],variant,{'pattern':item['pattern_hash'],'variant':variant,
                'slots':{graph['inputs'][0]['slot']:left,graph['inputs'][1]['slot']:right},
                'columns':dict(zip(columns,keys))}))
    if not choices:raise Unsupported('No learned graph supports this shared-witness interface')
    return min(choices,key=lambda x:x[:2])[2]


def predict_with_library(public,library):
    parsed=parse_public(public)
    if parsed.residuals:return {'status':'unsupported_public_grammar','answer':None,'pattern_uses':[],
                               'fallback_used':False,'residuals':parsed.residuals}
    return execute_parsed_with_library(parsed,library)


def execute_parsed_with_library(parsed,library,*,seconds=5):
    """Execute the selected stored graphs on one actual source-completion world."""
    relevant={(parsed.query.predicate,parsed.query.positive),(parsed.query.predicate,not parsed.query.positive)}
    while True:
        expanded=relevant|{(a.predicate,a.positive) for r in parsed.rules
            if (r.head.predicate,r.head.positive) in relevant for a in r.body}
        if expanded==relevant:break
        relevant=expanded
    uses=[];plans={};calls=[]
    def execute(index,rule,facts,iteration):
        slots={f'atom{i}':matches(a,facts) for i,a in enumerate(rule.body)}
        if index not in plans:
            nodes=[];left='atom0';columns=set(slots[left].columns)
            for i in range(1,len(rule.body)):
                right=f'atom{i}';keys=sorted(columns&set(slots[right].columns))
                graph=_learned_join(library,left,right,keys) if keys else \
                    {'op':'join_on','inputs':[{'slot':left},{'slot':right}],'params':{'keys':[]}}
                name=f'joined_{i}';nodes.append({'name':name,'kind':'connector','body':{'graph':graph,'project':'identity'}})
                columns|=set(slots[right].columns);left=name
            plans[index]=compile_query(nodes,{'var':left},slots,library=library)
        result=plans[index].execute(slots,return_environment=True)
        for use in result['pattern_uses']:
            uses.append({**use,'rule_index':index,'iteration':iteration,
                'query_relevant':(rule.head.predicate,rule.head.positive) in relevant,
                'input_witnesses':{name:{'columns':list(result['environment'][name].columns),
                    'rows':[list(row) for row in result['environment'][name].rows]}
                    for name in use['role_bindings'].values()},
                'output_rows':len(result['environment'][use['node']].rows)})
        calls.append({'rule_index':index,'iteration':iteration,'pattern_calls':len(result['pattern_uses'])})
        return result['answer']
    try:result=closure(parsed,execute,seconds=seconds)
    except Unsupported as exc:result={'status':'pattern_unavailable','answer':None,'reason':str(exc)}
    except (ValueError,TypeError,KeyError) as exc:
        result={'status':'invalid_graph_or_library','answer':None,'reason':str(exc),'error_type':type(exc).__name__}
    return {**result,'pattern_uses':uses,'rule_calls':calls,'fallback_used':False,
        'predefined_components':['public controlled-grammar parser','factual witness matching','fixed-point scheduler'],
        'learned_component':'collision-supported entity_equality interface and executed stored graph variants',
        'A_certificate_issued':False}
