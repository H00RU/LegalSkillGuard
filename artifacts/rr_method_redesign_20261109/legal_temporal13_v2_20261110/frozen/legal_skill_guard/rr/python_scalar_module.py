"""Ordinary pure scalar Python functions to the existing symbolic kernel.

No generated Python is executed. Straight-line assignments and conditional
returns are inlined exactly; unsupported code stays rejected.
"""
import ast
from copy import deepcopy

from .semantic_contracts import ContractError,expression,variables


def compile_function(code,signature):
    if code.strip().startswith('```'):
        lines=code.strip().splitlines()
        if lines[0] not in ('```','```python') or lines[-1]!='```':
            raise ContractError('Only one complete outer Python fence may be removed')
        code='\n'.join(lines[1:-1])
    try:tree=ast.parse(code)
    except SyntaxError as exc:raise ContractError(str(exc)) from exc
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef):
        raise ContractError('One ordinary function definition is required')
    function=tree.body[0];args=function.args
    if function.decorator_list or args.posonlyargs or args.kwonlyargs or args.defaults or args.vararg or args.kwarg:
        raise ContractError('Explicit named inputs without decorators or defaults required')
    if len({a.arg for a in args.args})!=len(args.args) or {a.arg for a in args.args}!=set(signature):
        raise ContractError('Function inputs differ from the shared source-learned contract')
    for a in args.args:
        if a.annotation is not None and (not isinstance(a.annotation,ast.Name) or
                a.annotation.id!=('int' if signature[a.arg]=='integer' else 'bool')):
            raise ContractError('Annotation differs from the supplied input type')
    if function.returns is not None and (not isinstance(function.returns,ast.Name) or function.returns.id not in ('int','bool')):
        raise ContractError('Only integer and Boolean return annotations are supported')
    visited=[0]
    class Inline(ast.NodeTransformer):
        def __init__(self,env):self.env=env
        def visit_Name(self,node):
            if node.id in self.env:return deepcopy(self.env[node.id])
            return node
    def substitute(value,env):return Inline(env).visit(deepcopy(value))
    def block(statements,env,depth=0):
        visited[0]+=1
        if visited[0]>4096 or depth>64:raise ContractError('Scalar control-flow resource bound exceeded')
        if not statements:raise ContractError('Every path must return an explicit value')
        current,*rest=statements
        if isinstance(current,ast.Expr) and isinstance(current.value,ast.Constant) and isinstance(current.value.value,str):
            return block(rest,env,depth+1)
        if isinstance(current,ast.Assign) and len(current.targets)==1 and isinstance(current.targets[0],ast.Name):
            changed=dict(env);changed[current.targets[0].id]=substitute(current.value,env)
            return block(rest,changed,depth+1)
        if isinstance(current,ast.AugAssign) and isinstance(current.target,ast.Name):
            if current.target.id not in env:raise ContractError('Update of an unbound local')
            changed=dict(env);changed[current.target.id]=ast.BinOp(deepcopy(env[current.target.id]),deepcopy(current.op),substitute(current.value,env))
            return block(rest,changed,depth+1)
        if isinstance(current,ast.Return) and current.value is not None:
            if rest:raise ContractError('Unreachable statements after return are not accepted')
            return substitute(current.value,env)
        if isinstance(current,ast.If):
            test=substitute(current.test,env)
            def branch(body):
                # A branch that already returns must not execute its continuation.
                if body and isinstance(body[-1],ast.Return):return block(body,dict(env),depth+1)
                return block(body+rest,dict(env),depth+1)
            return ast.IfExp(test,branch(current.body),branch(current.orelse))
        raise ContractError('Unsupported scalar statement '+type(current).__name__)
    body=block(function.body,{k:ast.Name(id=k,ctx=ast.Load()) for k in signature})
    body=ast.fix_missing_locations(body)
    result=ast.unparse(body)
    if len(result)>200000:raise ContractError('Expanded scalar expression exceeds the current resource bound')
    symbolic=expression(result,variables(signature))
    if function.returns is not None:
        import z3
        if (function.returns.id=='int')!=z3.is_int(symbolic):raise ContractError('Return annotation and function value differ')
    return {'function_name':function.name,'expression':result,'signature':dict(signature),
            'ordinary_Python_not_executed':True,'canonicalization':'pure_scalar_AST_control_flow_inlining'}
