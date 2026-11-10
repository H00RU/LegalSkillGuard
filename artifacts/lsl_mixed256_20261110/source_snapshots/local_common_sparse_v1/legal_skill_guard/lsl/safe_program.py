"""Bounded standard-Python candidate execution, independent of native grading.

This replaces burdensome custom generation fields for scalar policy tasks.
The generated program cannot import, access files/network or use reflection.
TRAIN answers are compared outside the worker; no oracle is a prediction tool.
"""
import ast
from copy import deepcopy
import itertools
import json
import math
from pathlib import Path
import random
import re
import subprocess
import sys

BUILTINS=('abs','all','any','bool','dict','divmod','enumerate','float','int','len','list','max','min',
          'range','round','set','sorted','str','sum','tuple','zip')
ATTRIBUTES={'append','extend','get','items','keys','values','lower','upper','strip','lstrip','rstrip',
            'split','rsplit','splitlines','replace','find','index','count','startswith','endswith',
            'sort','group','groups','search','findall','fullmatch','match','sub','is_integer'}
FORBIDDEN=(ast.Import,ast.ImportFrom,ast.ClassDef,ast.Global,ast.Nonlocal,ast.AsyncFunctionDef,
           ast.Await,ast.Yield,ast.YieldFrom,ast.Delete,ast.With,ast.AsyncWith)


def validate(code):
    if not isinstance(code,str) or len(code)>30000:raise ValueError('Program length/type')
    tree=ast.parse(code)
    if sum(1 for _ in ast.walk(tree))>3000:raise ValueError('Program AST budget')
    functions={n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
    if 'solve' not in functions:raise ValueError('Candidate must define solve')
    assigned={n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
    arguments={n.arg for n in ast.walk(tree) if isinstance(n,ast.arg)}
    loaded={n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
    undefined=loaded-assigned-arguments-functions-set(BUILTINS)-{'ceil','floor','sqrt','ValueError','re','case'}
    if undefined:raise ValueError('Undefined names; document references are not runtime values: '+','.join(sorted(undefined)))
    for node in ast.walk(tree):
        if isinstance(node,FORBIDDEN):raise ValueError('Unsupported Python operation: '+type(node).__name__)
        if isinstance(node,ast.Name) and node.id.startswith('_'):raise ValueError('Private/reflection name')
        if isinstance(node,ast.Attribute) and node.attr not in ATTRIBUTES:raise ValueError('Unsupported attribute: '+node.attr)
        if isinstance(node,ast.Call):
            if isinstance(node.func,ast.Name) and node.func.id not in set(BUILTINS)|functions|{'ceil','floor','sqrt','ValueError'}:
                raise ValueError('Unsupported function: '+node.func.id)
            if not isinstance(node.func,(ast.Name,ast.Attribute)):raise ValueError('Indirect callable')
        if isinstance(node,ast.FunctionDef) and (node.decorator_list or node.args.vararg or node.args.kwarg):raise ValueError('Unsupported function interface')
    solves=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='solve']
    if len(solves)!=1 or len(solves[0].args.args)>1:raise ValueError('Expected solve() or solve(case)')
    return tree


def _worker():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU,(2,2));resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    payload=json.load(sys.stdin);tree=validate(payload['code'])
    import builtins
    env={'__builtins__':{n:getattr(builtins,n) for n in BUILTINS},'ceil':math.ceil,'floor':math.floor,
         'sqrt':math.sqrt,'ValueError':ValueError,'re':re,'case':payload.get('public',{})}
    exec(compile(tree,'<source-candidate>','exec'),env,env)
    solve=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='solve')
    value=env['solve'](payload.get('public',{})) if solve.args.args else env['solve']()
    if type(value) not in (bool,int,float,str) or isinstance(value,str) and len(value)>1000:raise ValueError('Unsupported native scalar result')
    print(json.dumps({'value':value},allow_nan=False))


def execute(code,public,dataset,timeout=3):
    try:
        validate(code)
        process=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--worker'],
            input=json.dumps({'code':code,'public':public}),text=True,capture_output=True,timeout=timeout)
        if process.returncode:return {'valid':False,'error':'candidate_runtime_error','detail':process.stderr[-1000:]}
        value=json.loads(process.stdout)['value'];adaptation=None
        if dataset=='SARA_v2_Binary':
            if type(value) is bool:value='Entailment' if value else 'Contradiction';adaptation='declared_boolean_binary_mapping'
            if value not in ('Entailment','Contradiction'):raise ValueError('Not a native SARA binary label')
        elif dataset=='RuleArena_Airline':
            if type(value) is float and math.isfinite(value) and value.is_integer():value=int(value);adaptation='exact_integral_float_to_integer'
            if type(value) is not int:raise ValueError('Not an exact integer fee')
        else:raise ValueError('Scalar Python adapter is not defined for this dataset')
        return {'valid':True,'answer':value,'adaptation':adaptation,'oracle_used':False}
    except subprocess.TimeoutExpired:return {'valid':False,'error':'candidate_execution_timeout'}
    except Exception as e:return {'valid':False,'error':type(e).__name__+': '+str(e)}


def assignments(tree):
    return [n for n in ast.walk(tree) if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)]


def local_choices(proposal,source):
    tree=validate(proposal['program']);all_assignments=assignments(tree);out=[]
    for block in proposal.get('blocks',[]):
        quote=block.get('quote');name=block.get('name');alternative=block.get('alternative')
        start=block.get('source_start')
        if not isinstance(quote,str) or not quote or type(start) is not int or source[start:start+len(quote)]!=quote:continue
        candidates=[n for n in all_assignments if n.targets[0].id==name]
        if len(candidates)!=1:continue
        try:
            other=ast.parse(alternative)
            if len(other.body)!=1 or not isinstance(other.body[0],ast.Assign):continue
            target=other.body[0]
            if len(target.targets)!=1 or not isinstance(target.targets[0],ast.Name) or target.targets[0].id!=name:continue
            old_inputs={n.id for n in ast.walk(candidates[0].value) if isinstance(n,ast.Name)}
            new_inputs={n.id for n in ast.walk(target.value) if isinstance(n,ast.Name)}
            if old_inputs!=new_inputs:continue
            if ast.dump(candidates[0],include_attributes=False)==ast.dump(target,include_attributes=False):continue
            out.append({'name':name,'quote':quote,'source_start':start,
                        'choices':[ast.unparse(candidates[0]),ast.unparse(target)]})
        except (ValueError,SyntaxError,TypeError):continue
    return sorted(out,key=lambda b:b['source_start'])[:4]


def replace_assignment(code,name,statement):
    tree=validate(code);replacement=ast.parse(statement).body[0];count=0
    class Change(ast.NodeTransformer):
        def visit_Assign(self,node):
            nonlocal count
            if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id==name:
                count+=1;return deepcopy(replacement)
            return self.generic_visit(node)
    result=Change().visit(tree)
    if count!=1:raise ValueError('Ambiguous optional source slot')
    result=ast.fix_missing_locations(result);code=ast.unparse(result);validate(code);return code


def _expression_locations(tree,exclude_name=None):
    locations=[]
    def visit(node,path=(),excluded=False):
        # Every named source-local decision/fact stays a closed record. Only
        # references composing those records outside assignments may move.
        # This prevents a purported scope variant from changing case facts or
        # another local rule's internal threshold/negation.
        excluded=excluded or isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign))
        for field,value in ast.iter_fields(node):
            children=list(enumerate(value)) if isinstance(value,list) else [(None,value)]
            for index,child in children:
                if not isinstance(child,ast.AST):continue
                cp=path+((field,index),)
                if isinstance(child,ast.Name) and isinstance(child.ctx,ast.Load) and not excluded:
                    category='named_record_reference'
                    if field!='func':locations.append((cp,category))
                visit(child,cp,excluded)
    visit(tree);return locations


def _get(tree,path):
    node=tree
    for field,index in path:
        value=getattr(node,field);node=value if index is None else value[index]
    return node


def _set(tree,path,value):
    parent=_get(tree,path[:-1]);field,index=path[-1]
    if index is None:setattr(parent,field,value)
    else:getattr(parent,field)[index]=value


def scope_swaps(code,identity,exclude_name=None,maximum=3):
    tree=validate(code);locations=_expression_locations(tree,exclude_name);pairs=[]
    for (a,ta),(b,tb) in itertools.combinations(locations,2):
        if ta!=tb or ast.dump(_get(tree,a),include_attributes=False)==ast.dump(_get(tree,b),include_attributes=False):continue
        pairs.append((a,b))
    random.Random(identity+':same-node-rewiring').shuffle(pairs);selected=[];used=set()
    for pair in pairs:
        if set(pair)&used:continue
        selected.append(pair);used.update(pair)
        if len(selected)>=maximum:break
    return selected


def rewire(code,swaps,bits):
    tree=validate(code)
    for active,(left,right) in zip(bits,swaps):
        if active:
            a,b=deepcopy(_get(tree,left)),deepcopy(_get(tree,right));_set(tree,left,b);_set(tree,right,a)
    result=ast.unparse(ast.fix_missing_locations(tree));validate(result);return result


def local_execution_table(proposal,block,public,dataset,expected,identity):
    swaps=scope_swaps(proposal['program'],identity,block['name'],maximum=3)
    templates=[rewire(proposal['program'],swaps,bits) for bits in itertools.product((0,1),repeat=len(swaps))]
    rows=[];rejected=[];seen=set()
    for template in templates[:8]:
        choices=[replace_assignment(template,block['name'],v) for v in block['choices']]
        if tuple(choices) in seen:continue
        seen.add(tuple(choices));execution=[execute(code,public,dataset) for code in choices]
        if not all(e['valid'] for e in execution):rejected.append({'programs':choices,'execution':execution});continue
        rows.append({'programs':choices,'predictions':[e['answer'] for e in execution],
                     'losses':[int(e['answer']!=expected) for e in execution]})
    return {'block':block,'contexts':rows,'rejected_unscorable':rejected,
            'independently_fixed':False,'exhaustive':False,'finite_checked_completions_only':True,
            'loss_table':[r['losses'] for r in rows], 'no_oracle_called_by_candidate':True}


def native_square(proposal,public,dataset,expected,identity):
    swaps=scope_swaps(proposal['program'],identity,maximum=2)
    if len(swaps)!=2:return None
    programs=[rewire(proposal['program'],swaps,bits) for bits in ((0,0),(0,1),(1,0),(1,1))]
    execution=[execute(code,public,dataset) for code in programs]
    if not all(e['valid'] for e in execution):return None
    return {'programs':programs,'predictions':[e['answer'] for e in execution],
            'mean_errors':[int(e['answer']!=expected) for e in execution],
            'same_nodes_and_facts':True,'native_gold_used_only_in_training_error_table':True}


if __name__=='__main__' and '--worker' in sys.argv:_worker()
