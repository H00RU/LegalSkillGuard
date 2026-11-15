"""Materialize an acquired external compiler update, with no legal defaults."""
import ast
from copy import deepcopy

from .native import record_schema
from .scoped_grammar import CONSTRUCTOR, SEED, induce
from .source_schema import LABELS
from .span_compiler import validate_procedure


PROPOSAL = record_schema({
    'architecture': {'type':'string','enum':['compiler','program']},
    'rationale': {'type':'string'},
    'new_constructors': {'type':'array','items':CONSTRUCTOR},
    'source_functions': {'type':'array','items':{'type':'string'}},
    'decision_functions': {'type':'array','items':{'type':'string'}},
    'source_examples': {'type':'array','items':SEED},
    'direct_program': {'type':['string','null']}})


def function_update(old, changes):
    """Replace or add actual pure functions; do not change supplied semantics."""
    tree=ast.parse(old)
    parts={n.name:ast.get_source_segment(old,n) for n in tree.body if isinstance(n,ast.FunctionDef)}
    if len(parts)!=len(tree.body):raise ValueError('Only pure function definitions may be updated')
    changed=set()
    for code in changes:
        nodes=ast.parse(code).body
        if len(nodes)!=1 or not isinstance(nodes[0],ast.FunctionDef):
            raise ValueError('One complete function per update')
        name=nodes[0].name
        if name in changed:raise ValueError('Duplicate function update')
        changed.add(name);parts[name]=code
    result='\n\n'.join(parts.values())+'\n'
    validate_procedure(result,allow_helpers=True)
    return result


def materialize(base, proposal, materials):
    if proposal['architecture']=='program':
        if any(proposal[k] for k in ('new_constructors','source_functions','decision_functions','source_examples')):
            raise ValueError('A direct program must not pretend to supply unused compiler updates')
        if proposal['direct_program'] is None:raise ValueError('Missing independent program')
        validate_procedure(proposal['direct_program'],allow_helpers=True)
        return {'architecture':'program','program':proposal['direct_program']},None
    if proposal['direct_program'] is not None:raise ValueError('Compiler and direct program are separate acquired artifacts')
    spec=deepcopy(base['grammar'])
    spec['constructors'].extend(deepcopy(proposal['new_constructors']))
    spec['seeds'].extend(deepcopy(proposal['source_examples']))
    spec['decision_program']=function_update(spec['decision_program'],proposal['decision_functions'])
    source=function_update(base['source_program'],proposal['source_functions'])
    if any(isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value in LABELS
           for n in ast.walk(ast.parse(source))):
        raise ValueError('A source compiler cannot encode native answer labels')
    grammar=induce(spec,materials)
    return {'architecture':'compiler','grammar':spec,'source_program':source},grammar
