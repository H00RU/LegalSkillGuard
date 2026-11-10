"""Bounded runtime for learned source compilers and ordinary program learners.

Both arms receive the same Python, regex and graph execution capabilities. No
model call or task label is available inside a learned program.
"""
import ast
import builtins
import json
import multiprocessing
import re
import resource
import jsonschema

from .contract_scope_learning import GRAPH, execute, validate

SAFE_BUILTINS={n:getattr(builtins,n) for n in
 ('set','frozenset','list','dict','tuple','str','int','float','bool','len','sorted','enumerate','zip','any','all','min','max','sum','isinstance','range','abs','next','reversed')}
METHODS={'get','items','keys','values','add','discard','append','extend','update','setdefault','copy',
 'union','intersection','difference','replace','startswith','endswith','pop','remove','clear','count','index',
 'issubset','issuperset','isdisjoint','lower','upper','casefold','strip','lstrip','rstrip','split','rsplit','splitlines','partition','rpartition','removeprefix','removesuffix','join','isdigit','sort','reverse','find','rfind',
 'compile','search','match','fullmatch','findall','finditer','sub','escape','group','groups','groupdict','start','end','span',
 'IGNORECASE','DOTALL','MULTILINE','I','S','M'}

def check(code):
    tree=ast.parse(code)
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    if 'infer' not in functions or [a.arg for a in functions['infer'].args.args]!=['document','query']:
        raise ValueError('Expected infer(document, query)')
    if any(not isinstance(n,(ast.FunctionDef,ast.Assign,ast.AnnAssign)) for n in tree.body):
        raise ValueError('Only functions and literal module constants are allowed')
    for n in tree.body:
        if isinstance(n,(ast.Assign,ast.AnnAssign)):
            ast.literal_eval(n.value)
    blocked=(ast.Import,ast.ImportFrom,ast.ClassDef,ast.AsyncFunctionDef,ast.Lambda,ast.Global,
      ast.Nonlocal,ast.With,ast.AsyncWith,ast.Try,ast.Raise,ast.Delete,ast.Await,ast.Yield,ast.YieldFrom)
    for n in ast.walk(tree):
        if isinstance(n,blocked):raise ValueError('Unsupported statement '+type(n).__name__)
        if isinstance(n,ast.FunctionDef) and (n.decorator_list or n.returns or n.args.defaults or n.args.kw_defaults or n.args.vararg or n.args.kwarg or any(a.annotation for a in n.args.args)):
            raise ValueError('No evaluated annotations/defaults/decorators or variadic arguments')
        if isinstance(n,ast.Name) and n.id.startswith('__'):raise ValueError('Private environment access')
        if isinstance(n,ast.Attribute) and n.attr not in METHODS:raise ValueError('Unsupported method '+n.attr)
        if isinstance(n,ast.Call):
            if not isinstance(n.func,(ast.Name,ast.Attribute)):raise ValueError('Dynamic call')
            if isinstance(n.func,ast.Name) and n.func.id not in {*SAFE_BUILTINS,*functions,'scope_answer'}:
                raise ValueError('Unsupported function '+n.func.id)
    return tree

def scope_answer(graph,document,query_id):
    jsonschema.validate(graph,GRAPH)
    return execute(graph,document,query_id)

def _worker(pipe,code,document,queries):
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(3,3));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
        ns={'__builtins__':SAFE_BUILTINS,'re':re,'scope_answer':scope_answer}
        exec(compile(check(code),'<learned-contract-compiler>','exec'),ns)
        values=[]
        for query in queries:
            try:values.append({'value':ns['infer'](document,query)})
            except Exception as e:values.append({'error_type':type(e).__name__,'error':str(e)})
        pipe.send_bytes(json.dumps({'entries':values},ensure_ascii=False).encode())
    except BaseException as e:pipe.send_bytes(json.dumps({'error_type':type(e).__name__,'error':str(e)}).encode())
    finally:pipe.close()

def run(code,document,queries):
    check(code);parent,child=multiprocessing.get_context('fork').Pipe(duplex=False)
    p=multiprocessing.get_context('fork').Process(target=_worker,args=(child,code,document,queries));p.start();child.close()
    try:
        if not parent.poll(8):raise ValueError('Learned compiler exceeded execution time')
        result=json.loads(parent.recv_bytes())
    finally:
        if p.is_alive():p.terminate()
        p.join();parent.close()
    if 'error' in result:raise ValueError(result['error_type']+': '+result['error'])
    return result['entries']

def baseline_answer(value,document):
    if not isinstance(value,dict) or 'answer' not in value or value['answer'] not in ['Entailment','Contradiction','NotMentioned',None]:
        raise ValueError('Expected explicit native answer or null')
    quotes=value.get('evidence')
    if not isinstance(quotes,list) or any(not isinstance(q,str) or not q or q not in document for q in quotes):
        raise ValueError('Evidence is not an exact source substring')
    if value['answer'] in ['Entailment','Contradiction'] and not quotes:raise ValueError('Non-null support needs source evidence')
    return {**value,'fallback':False}

def predict(arm,code,document,queries):
    if arm=='scope_compiler':
        entry=run(code,document,[None])[0]
        if 'error' in entry:raise ValueError(entry['error_type']+': '+entry['error'])
        graph=entry['value'];jsonschema.validate(graph,GRAPH);validate(graph,document)
        return [execute(graph,document,q['id']) for q in queries],graph
    values=[]
    for entry in run(code,document,queries):
        try:
            if 'error' in entry:raise ValueError(entry['error_type']+': '+entry['error'])
            values.append(baseline_answer(entry['value'],document))
        except Exception as e:values.append({'answer':None,'evidence':[],'executed':False,'fallback':False,'execution_error':type(e).__name__+': '+str(e)})
    return values,None

def offline():
    text='The Receiver may disclose to its advisers.'
    code="def infer(document, query):\n    match=re.search(r'advisers',document,re.I)\n    return {'answer':'Entailment' if match else 'NotMentioned','evidence':[match.group()] if match else []}\n"
    assert baseline_answer(run(code,text,[{'id':'software'}])[0]['value'],text)['answer']=='Entailment'
    assert run("def infer(document, query):\n    return {'answer':None,'evidence':[]}\n",text,[None])[0]['value']['answer'] is None
    for bad in ["import os\ndef infer(document, query):\n    return None", "def infer(document, query):\n    return document.__class__"]:
        try:check(bad)
        except ValueError:pass
        else:raise AssertionError('Unsupported access accepted')
    return {'regex_and_program_execution':True,'unresolved_retained':True,'unsupported_access_rejected':True,'no_native_success_claim':True}
