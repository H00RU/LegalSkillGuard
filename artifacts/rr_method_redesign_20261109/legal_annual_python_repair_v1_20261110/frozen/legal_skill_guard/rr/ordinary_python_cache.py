"""Bounded execution of ordinary policy-cache Python with declared helpers.

Supports the real complete lambda/helper output that the historical one-def
wrapper could not run. No source rewrite, source-semantic repair or relaxed
output truth check is performed here.
"""
import ast
import builtins
import json
import multiprocessing
import resource

BUILTINS={k:getattr(builtins,k) for k in ('set','frozenset','list','dict','tuple','str','int','bool','len','sorted','enumerate','zip','any','all','min','max','sum','isinstance')}
METHODS={'get','items','keys','values','add','discard','append','extend','update','setdefault','copy','union','intersection','difference','pop','remove','clear','count','index','sort','reverse'}


def validate(code):
    tree=ast.parse(code);functions=[];entry_lambda=None
    for top in tree.body:
        if isinstance(top,ast.FunctionDef):functions.append(top)
        elif (isinstance(top,ast.Assign) and len(top.targets)==1 and isinstance(top.targets[0],ast.Name)
              and top.targets[0].id=='law_cache' and isinstance(top.value,ast.Lambda) and entry_lambda is None):
            entry_lambda=top.value
        else:raise ValueError('Only ordinary function declarations or one entry lambda assignment are supported')
    names=[f.name for f in functions]+(['law_cache'] if entry_lambda else [])
    if len(names)!=len(set(names)) or names.count('law_cache')!=1:raise ValueError('Exactly one law_cache entry required')
    entry=entry_lambda or next(f for f in functions if f.name=='law_cache')
    if [a.arg for a in entry.args.args]!=['facts','query']:raise ValueError('The existing cache input contract is facts,query')
    for fn in [*functions,*([entry_lambda] if entry_lambda else [])]:
        a=fn.args
        if (a.defaults or a.kw_defaults or a.vararg or a.kwarg or a.posonlyargs or a.kwonlyargs
            or any(x.annotation for x in a.args) or getattr(fn,'returns',None) or getattr(fn,'decorator_list',None)):
            raise ValueError('No evaluated defaults, annotations or decorators')
    blocked=(ast.Import,ast.ImportFrom,ast.ClassDef,ast.AsyncFunctionDef,ast.Global,ast.Nonlocal,ast.With,ast.AsyncWith,ast.Try,ast.Raise,ast.Delete,ast.Await,ast.Yield,ast.YieldFrom)
    for node in ast.walk(tree):
        if isinstance(node,blocked):raise ValueError('Unsupported code statement '+type(node).__name__)
        if isinstance(node,ast.FunctionDef) and node not in functions:raise ValueError('Nested declarations not needed by this cache contract')
        if isinstance(node,ast.Lambda) and node is not entry_lambda:raise ValueError('Only the declared entry lambda is supported')
        if isinstance(node,ast.Name) and node.id.startswith('__'):raise ValueError('Private environment access')
        if isinstance(node,ast.Attribute) and node.attr not in METHODS:raise ValueError('Unsupported collection attribute')
        if isinstance(node,ast.Call):
            if isinstance(node.func,ast.Name) and node.func.id not in set(BUILTINS)|set(names):raise ValueError('Unsupported call '+node.func.id)
            if not isinstance(node.func,(ast.Name,ast.Attribute)):raise ValueError('Dynamic call target')
    return tree


def _worker(pipe,code,facts,query):
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(3,3));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
        namespace={'__builtins__':BUILTINS}
        exec(compile(validate(code),'<ordinary-source-cache>','exec'),namespace)
        pipe.send_bytes(json.dumps({'value':namespace['law_cache'](facts,query)},ensure_ascii=False).encode())
    except BaseException as exc:pipe.send_bytes(json.dumps({'error_type':type(exc).__name__,'error':str(exc)}).encode())
    finally:pipe.close()


def execute(code,facts,query):
    validate(code);context=multiprocessing.get_context('fork');parent,child=context.Pipe(duplex=False)
    process=context.Process(target=_worker,args=(child,code,facts,query));process.start();child.close()
    try:
        if not parent.poll(8):raise ValueError('Ordinary cache exceeded bounded execution time')
        out=json.loads(parent.recv_bytes())
    finally:
        if process.is_alive():process.terminate()
        process.join();parent.close()
    if 'error' in out:raise ValueError(out['error_type']+': '+out['error'])
    return out['value']
