"""Scope moves exclude superficial commutative/associative operand reorderings.

All named source assignments and case facts remain byte-semantically fixed.
Canonicalization only removes candidates from the search; it is never used to
accept an answer or to assert arbitrary Python programs globally equivalent.
"""
import ast
from copy import deepcopy
import itertools
import random

from .safe_program import (validate,_expression_locations,_get,_set,rewire,
                           replace_assignment,execute)


def scope_identity(code):
    def canonical(node):
        if isinstance(node,ast.BoolOp):
            op=type(node.op);terms=[]
            def collect(n):
                if isinstance(n,ast.BoolOp) and type(n.op)is op:
                    for v in n.values:collect(v)
                else:terms.append(canonical(n))
            collect(node)
            return (op.__name__,tuple(sorted(terms,key=repr)))
        if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Mult)):
            op=type(node.op);terms=[]
            def collect(n):
                if isinstance(n,ast.BinOp) and type(n.op)is op:collect(n.left);collect(n.right)
                else:terms.append(canonical(n))
            collect(node)
            return (op.__name__,tuple(sorted(terms,key=repr)))
        if isinstance(node,ast.AST):return (type(node).__name__,tuple((k,canonical(v)) for k,v in ast.iter_fields(node)))
        if isinstance(node,list):return tuple(canonical(n) for n in node)
        return node
    return repr(canonical(validate(code)))


def swaps(code,identity,maximum=3):
    tree=validate(code);locations=_expression_locations(tree);pairs=[];original=scope_identity(code)
    for (a,ta),(b,tb) in itertools.combinations(locations,2):
        if ta!=tb or ast.dump(_get(tree,a),include_attributes=False)==ast.dump(_get(tree,b),include_attributes=False):continue
        variant=rewire(code,[(a,b)],[1])
        if scope_identity(variant)==original:continue
        pairs.append((a,b))
    random.Random(identity+':same-node-rewiring').shuffle(pairs);selected=[];used=set()
    for pair in pairs:
        if set(pair)&used:continue
        selected.append(pair);used.update(pair)
        if len(selected)>=maximum:break
    return selected


def local_execution_table(proposal,block,public,dataset,expected,identity):
    moves=swaps(proposal['program'],identity,maximum=3)
    templates=[rewire(proposal['program'],moves,bits) for bits in itertools.product((0,1),repeat=len(moves))]
    rows=[];rejected=[];seen=set()
    for template in templates:
        key=scope_identity(template)
        if key in seen:continue
        seen.add(key);choices=[replace_assignment(template,block['name'],v) for v in block['choices']]
        results=[execute(c,public,dataset) for c in choices]
        if not all(e['valid'] for e in results):rejected.append({'programs':choices,'execution':results});continue
        rows.append({'programs':choices,'predictions':[e['answer'] for e in results],
                     'losses':[int(e['answer']!=expected) for e in results],'scope_identity':key})
    return {'block':block,'contexts':rows,'rejected_unscorable':rejected,
            'independently_fixed':False,'exhaustive':False,'finite_checked_completions_only':True,
            'loss_table':[r['losses'] for r in rows],'no_oracle_called_by_candidate':True,
            'commutative_reorderings_excluded':True}


def inference_square(code,public,dataset,identity):
    available=swaps(code,identity,maximum=3)
    for moves in itertools.combinations(available,2):
        programs=[rewire(code,moves,bits) for bits in ((0,0),(0,1),(1,0),(1,1))]
        if len({scope_identity(c) for c in programs})!=4:continue
        execution=[execute(c,public,dataset) for c in programs]
        if not all(e['valid'] for e in execution):continue
        return {'programs':programs,'cells':[{'program':c} for c in programs],
                'predictions':[e['answer'] for e in execution],
                'same_nodes_and_facts':True,'commutative_reorderings_excluded':True}
    return None


def native_square(proposal,public,dataset,expected,identity):
    result=inference_square(proposal['program'],public,dataset,identity)
    if result is not None:
        result['mean_errors']=[int(p!=expected) for p in result['predictions']]
        result['native_gold_used_only_in_training_error_table']=True
    return result
