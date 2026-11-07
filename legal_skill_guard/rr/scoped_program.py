"""Source-linked local definitions and exact query dependency footprints.

Definitions are evaluated lazily. A mutable allowance may have only one owning
definition: all consumption of that bank must occur in one threaded graph.
This makes dependency projection valid without silently cloning entitlement.
"""
from __future__ import annotations

from copy import deepcopy
from collections import ChainMap
from dataclasses import dataclass
from fractions import Fraction

from .coverage import Unsupported, digest, evaluate
from .interfaces import AllowanceBank, Amount, Relation
from .ir_types import check_expression
from .interfaces import Connector
from .connector_completion import ConnectorQuery
from .pattern_execution import expand_graph


def expression_reads(node):
    if not isinstance(node, dict):
        return set()
    if set(node)=={'var'}:
        return {node['var']}
    return set().union(*(expression_reads(x) for x in node.get('args', [])))


def graph_reads(node):
    if 'slot' in node:
        return {node['slot']}
    return {v for k,v in node.get('params', {}).items() if k.endswith('_slot')} | \
        set().union(*(graph_reads(x) for x in node.get('inputs', [])))


def _walk_graph(graph):
    yield graph
    for child in graph.get('inputs', []):
        yield from _walk_graph(child)


def value_type(value):
    if type(value) is bool:return 'boolean'
    if type(value) in (int,Fraction):return 'number'
    if isinstance(value,str):return 'string'
    if isinstance(value,Amount):return 'amount'
    if isinstance(value,Relation):return 'relation'
    if isinstance(value,AllowanceBank):return 'bank'
    if isinstance(value,list):
        if value and all(isinstance(x,Amount) for x in value):return 'amounts'
        if value and all(type(x) is bool for x in value):return 'booleans'
        if value and all(isinstance(x,Relation) for x in value):return 'relations'
        if value and all(type(x) in (int,Fraction) for x in value):return 'numbers'
        return 'array'
    if isinstance(value,dict):return 'object'
    if isinstance(value,tuple):return 'resource_key'
    if value is None:return 'null'
    raise Unsupported('Unsupported scoped input type')


def infer_graph(graph, types):
    """Type-check the stored program, never execute a representative answer."""
    if 'slot' in graph:
        if graph['slot'] not in types:raise Unsupported('Unbound connector slot: '+graph['slot'])
        return set(types[graph['slot']])
    op,p=graph['op'],graph.get('params',{})
    children=[infer_graph(c,types) for c in graph['inputs']]
    def require(index,allowed):
        if not children[index]<=set(allowed):
            raise Unsupported('Connector '+op+' input '+str(index)+' expects '+str(allowed)+', got '+str(children[index]))
    def slot(key,allowed):
        name=p[key]
        if name not in types or not set(types[name])<=set(allowed):
            raise Unsupported('Connector '+op+' parameter '+key+' has incompatible slot '+name)
    if op=='bind_rename':require(0,{'relation'});return {'relation'}
    if op=='join_on':require(0,{'relation'});require(1,{'relation'});return {'relation'}
    if op=='project_exists':require(0,{'relation'});return {'boolean'}
    if op=='group_by':
        require(0,{'relation','amounts'})
        return {'relation_groups' if t=='relation' else 'amount_groups' for t in children[0]}
    if op=='map' and p['primitive']=='cap':
        require(0,{'amount','amounts'});slot('limit_slot',{'number'});return children[0]
    if op=='map' and p['primitive']=='sum_amounts':require(0,{'amount_groups'});return {'amounts'}
    if op=='map' and p['primitive']=='exists':require(0,{'relation_groups','relations'});return {'booleans'}
    if op=='fold_reduce' and p['primitive']=='sum_amounts':require(0,{'amounts'});return {'amount'}
    if op=='fold_reduce' and p['primitive'] in {'all','any'}:require(0,{'booleans'});return {'boolean'}
    if op=='thread_allowance':
        require(0,{'amounts'});slot('bank_slot',{'bank'});slot('key_slot',{'resource_key'});return {'amounts'}
    raise Unsupported('Unknown scoped connector operator')


def project_types(types, project):
    expected={'amount_value':({'amount'},{'number'}),'amount_values':({'amounts'},{'numbers'}),
              'entailment_label':({'boolean'},{'string'})}
    if project=='identity':return types
    if project not in expected or not types<=expected[project][0]:
        raise Unsupported('Incompatible connector projection '+project)
    return expected[project][1]


@dataclass(frozen=True)
class ScopedQuery:
    nodes: tuple
    query: dict
    input_names: tuple

    def __rr_state__(self):
        return {'kind':'source_scoped_DAG','nodes':self.nodes,'query':self.query,'inputs':self.input_names}

    def node_reads(self,node):
        if node['kind']=='expression':
            return expression_reads(node['body'])
        return graph_reads(node['body']['graph']) | \
            (expression_reads(node['body'].get('query',{})) - {node.get('result_slot')})

    def completion_dependencies(self):
        by_name={node['name']:node for node in self.nodes}
        pending=list(expression_reads(self.query));result=set()
        while pending:
            name=pending.pop()
            if name in result:continue
            result.add(name)
            if name in by_name:pending.extend(self.node_reads(by_name[name]))
        return result & set(self.input_names)

    def execute(self,inputs,*,return_environment=False):
        by_name={n['name']:n for n in self.nodes};uses=[];active=set();executed=[]
        # Expression branches resolve definitions only when actually read. A
        # pattern in an inactive branch must not be reported as real reuse.
        class LazyInputs(dict):
            def __contains__(self,key):
                if not dict.__contains__(self,key) and key in by_name:
                    ensure(key)
                return dict.__contains__(self,key)
            def __getitem__(self,key):
                if not dict.__contains__(self,key) and key in by_name:
                    ensure(key)
                return dict.__getitem__(self,key)
        env=LazyInputs(deepcopy(inputs))
        def ensure(name):
            if dict.__contains__(env,name):return
            if name not in by_name:raise Unsupported('Unbound scoped variable '+name)
            if name in active:raise Unsupported('Cyclic local definition')
            active.add(name);node=by_name[name]
            if node['kind']=='expression':env[name]=evaluate(node['body'],env)
            else:
                body=node['body']
                for parent in graph_reads(body['graph']):ensure(parent)
                execution=ConnectorQuery(body['graph'],{'project':body['project']}).execute(dict(env))
                env[name]=evaluate(body['query'],ChainMap({node['result_slot']:execution['answer']},env)) \
                    if 'query' in body else execution['answer']
                uses.extend({**u,'node':name,'status':'executed_main_program'} for u in node.get('pattern_uses',[]))
            active.remove(name);executed.append(name)
        answer=evaluate(self.query,env)
        return {'answer':answer,'pattern_uses':uses,'executed_nodes':executed,
                **({'environment':dict(env)} if return_environment else {})}

    def evaluate(self,inputs):
        return self.execute(inputs)['answer']


def compile_query(nodes,query,inputs,*,domains=None,library=None,boolean_nodes=()):
    domains=domains or {};types={name:{value_type(v)} for name,v in inputs.items()}
    if set(domains)&set(inputs):raise Unsupported('Unresolved domains cannot overwrite source inputs')
    for name,values in domains.items():
        if not values:raise Unsupported('Cannot compile an untyped empty observation domain')
        types[name]={value_type(v) for v in values}
    initial=tuple(sorted(types));compiled=[];bank_owners={}
    for node in nodes:
        if set(node)!={'name','kind','body'} or not isinstance(node['name'],str) or not node['name'] or node['name'] in types:
            raise Unsupported('Scoped nodes need unique names and explicit kind/body')
        node=deepcopy(node);body=node['body']
        if node['kind']=='expression':
            check=check_expression({'query':body},{},slot_types=types);result_types=set(check['result_types'])
        elif node['kind']=='connector':
            if set(body)-{'graph','project','query'} or not {'graph','project'}<=set(body):
                raise Unsupported('Scoped connector needs a concrete graph and projection')
            body['graph'],node['pattern_uses']=expand_graph(body['graph'],library,set(types))
            Connector(body['graph']).validate()
            result_types=project_types(infer_graph(body['graph'],types),body['project'])
            if 'query' in body:
                if len(result_types)!=1 or not result_types<={'number','boolean','string'}:
                    raise Unsupported('Scoped connector wrapper requires one scalar result')
                prefix={'number':'n','boolean':'b','string':'s'}[next(iter(result_types))]
                key=prefix+'_result'
                if key in types:raise Unsupported('Connector output shadows a source variable')
                node['result_slot']=key
                result_types=set(check_expression({'query':body['query']},{},slot_types={**types,key:result_types})['result_types'])
            for part in _walk_graph(body['graph']):
                if part.get('op')=='thread_allowance':
                    bank=part['params']['bank_slot']
                    if bank in bank_owners and bank_owners[bank]!=node['name']:
                        raise Unsupported('One allowance bank must be threaded in one owning local graph')
                    bank_owners[bank]=node['name']
        else:raise Unsupported('Unsupported scoped node kind')
        if 'bank' in result_types:raise Unsupported('A mutable bank cannot be aliased as a derived value')
        if node['name'] in boolean_nodes and result_types!={'boolean'}:
            raise Unsupported('Executable source scope must be Boolean, got '+str(sorted(result_types)))
        types[node['name']]=result_types;compiled.append(node)
    check_expression({'query':query},{},slot_types=types)
    return ScopedQuery(tuple(compiled),deepcopy(query),initial)
