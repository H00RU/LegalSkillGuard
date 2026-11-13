"""Bounded pure Python for the current acquired reader/update programs.

Local helpers and recursive traversal are ordinary Python. They execute in the
existing restricted subprocess with the same resource and four-second wall
limits. Scientific schemas, source evidence and native grading are unchanged.
"""
import ast
import json
from pathlib import Path
import subprocess
import sys

import jsonschema

from .span_compiler import CALLS,METHODS
from .semantic_operations import PLAN
from .semantic_execution import DEMAND


def validate(code):
    tree=ast.parse(code);top=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
    if len(top)!=len(tree.body) or sum(n.name=='apply' for n in top)!=1:
        raise ValueError('Pure function definitions and one apply entry required')
    if len({n.name for n in top})!=len(top):raise ValueError('Duplicate top-level function')
    entry=next(n for n in top if n.name=='apply')
    if (entry.args.vararg or entry.args.kwarg or entry.args.kwonlyargs or entry.args.defaults or
            [a.arg for a in entry.args.args]!=['inputs','premises']):
        raise ValueError('Explicit JSON input bindings required')
    functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)]
    names={n.name for n in functions}
    forbidden=(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.ClassDef,ast.Lambda,ast.With,ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if isinstance(node,forbidden):raise ValueError('Effectful/reflection code forbidden')
        if isinstance(node,ast.FunctionDef) and node.decorator_list:raise ValueError('No decorators')
        if isinstance(node,ast.Name) and node.id.startswith('__'):raise ValueError('No introspection')
        if isinstance(node,ast.Attribute) and node.attr not in METHODS|{'setdefault'}:
            raise ValueError('Unsupported attribute: '+node.attr)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id not in CALLS|names:
            raise ValueError('Unsupported/unlinked call: '+node.func.id)
    return code


def merge_functions(old,changes):
    tree=ast.parse(old)
    if any(not isinstance(n,ast.FunctionDef) for n in tree.body):raise ValueError('Pure definitions required')
    parts={n.name:ast.get_source_segment(old,n) for n in tree.body};seen=set()
    for code in changes:
        body=ast.parse(code).body
        if len(body)!=1 or not isinstance(body[0],ast.FunctionDef):raise ValueError('One complete top-level function per update')
        name=body[0].name
        if name in seen:raise ValueError('Duplicate update')
        seen.add(name);parts[name]=code
    result='\n\n'.join(parts.values())+'\n';validate(result);return result


def execute(code,inputs,premises=None):
    validate(code)
    worker=Path(__file__).with_name('span_compiler_worker.py')
    result=subprocess.run([sys.executable,'-I','-S',str(worker)],
        input=json.dumps({'procedure':code,'inputs':inputs,'premises':premises or {},'trace':False},ensure_ascii=False),
        capture_output=True,text=True,timeout=4,cwd='/tmp',env={'LANG':'C.UTF-8'},close_fds=True)
    if result.returncode:raise ValueError('Acquired source execution failed: '+result.stderr[-1000:])
    return json.loads(result.stdout)


def plan(program,operations,text,units):
    raw=execute(program,{'phase':'plan','source_text':text,'source_spans':units,'semantic_answers':[]})
    jsonschema.validate(raw,PLAN);queries=raw['queries'];ids=[q['id'] for q in queries]
    if len(set(ids))!=len(ids):raise ValueError('Repeated query identity')
    known={o['name'] for o in operations};current={u['id'] for u in units}
    for q in queries:
        if q['operation'] not in known:raise ValueError('Undeclared acquired operation')
        if len(set(q['unit_ids']))!=len(q['unit_ids']) or not set(q['unit_ids'])<=current:
            raise ValueError('Invalid current query window')
    return queries


def finish(program,text,units,answers):
    return execute(program,{'phase':'finish','source_text':text,'source_spans':units,'semantic_answers':answers})


def probe_program(program,lookup):
    tree=ast.parse(program);functions={n.name:n for n in tree.body}
    if lookup not in functions:raise ValueError('Declared lookup absent')
    fn=functions[lookup]
    if len(fn.args.args) not in (4,5) or fn.args.vararg or fn.args.kwarg:
        raise ValueError('Declared observation lookup contract differs')
    for caller in functions.values():
        if caller.name==lookup:continue
        parents={child:n for n in ast.walk(caller) for child in ast.iter_child_nodes(n)}
        calls=[n for n in ast.walk(caller) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==lookup]
        containers=set()
        for call in calls:
            if not call.args or not isinstance(call.args[0],ast.Name):raise ValueError('Explicit answer container required')
            containers.add(call.args[0].id)
        for n in ast.walk(caller):
            if not (isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id in containers):continue
            use=parents[n]
            if not (isinstance(use,ast.Call) and isinstance(use.func,ast.Name) and use.func.id==lookup and use.args[0] is n):
                raise ValueError('Observation container used outside the declared lookup')
    answer,qid,_,errors=[a.arg for a in fn.args.args[:4]]
    original=ast.dump(fn,include_attributes=False)
    marker=ast.parse('if '+qid+' is not None and '+qid+' not in '+answer+':\n    '+errors+'.append('+repr(DEMAND)+'+'+qid+')').body[0]
    fn.body.insert(0,marker)
    assert ast.dump(ast.FunctionDef(name=fn.name,args=fn.args,body=fn.body[1:],decorator_list=fn.decorator_list,
        returns=fn.returns,type_comment=fn.type_comment),include_attributes=False)==original
    result=ast.unparse(ast.fix_missing_locations(tree));validate(result);return result
