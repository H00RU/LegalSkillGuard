"""Offline audit of hidden composition inside existing scalar assignments.

No proposals/labels/facts are added. It checks whether the current blanket
assignment closure hides actual argument-binding choices in generated TRAIN
programs. Every cell preserves literal constants, operators and named stores.
"""
from pathlib import Path
import ast
import itertools
import json
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legal_skill_guard.lsl.data import load_json,write_json
from legal_skill_guard.lsl.safe_program import validate,execute,_get,_set
from legal_skill_guard.lsl.native_scope import swaps as current_swaps


PURE={'min','max','sum','all','any','abs','int','float','bool','len','round'}


def locations(tree,exclude_name=None):
    assigned={n.id for n in ast.walk(tree)if isinstance(n,ast.Name)and isinstance(n.ctx,ast.Store)}
    found=[]
    def visit(node,path=(),parents=(),excluded=False):
        if isinstance(node,ast.Assign)and any(isinstance(t,ast.Name)and t.id==exclude_name for t in node.targets):excluded=True
        for field,value in ast.iter_fields(node):
            children=list(enumerate(value))if isinstance(value,list)else[(None,value)]
            for index,child in children:
                if not isinstance(child,ast.AST):continue
                p=path+((field,index),)
                blocked=excluded or field in ('targets','target','func')
                if isinstance(child,ast.Name)and isinstance(child.ctx,ast.Load)and child.id in assigned and child.id!='case'and not blocked:
                    if isinstance(node,(ast.BinOp,ast.BoolOp,ast.Compare))or(isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id in PURE):found.append(p)
                visit(child,p,parents+(path,),blocked)
    visit(tree);return found


def rewire(code,moves,bits):
    tree=validate(code)
    for active,(a,b)in zip(bits,moves):
        if active:
            from copy import deepcopy
            x,y=deepcopy(_get(tree,a)),deepcopy(_get(tree,b));_set(tree,a,y);_set(tree,b,x)
    return ast.unparse(ast.fix_missing_locations(tree))


def invariant(code):
    t=validate(code)
    return {'constants':[(type(n.value).__name__,repr(n.value))for n in ast.walk(t)if isinstance(n,ast.Constant)],
            'stores':[n.id for n in ast.walk(t)if isinstance(n,ast.Name)and isinstance(n.ctx,ast.Store)],
            'operators':[type(n).__name__ for n in ast.walk(t)if isinstance(n,(ast.operator,ast.boolop,ast.unaryop,ast.cmpop))],
            'public_case_reads':sum(isinstance(n,ast.Name)and n.id=='case'and isinstance(n.ctx,ast.Load)for n in ast.walk(t))}


def probe(code,public,dataset,identity,expected):
    tree=validate(code);refs=locations(tree);pairs=[]
    for a,b in itertools.combinations(refs,2):
        if _get(tree,a).id==_get(tree,b).id:continue
        # Exclude sibling exchanges inside the same commutative container.
        if a[:-1]==b[:-1]:
            p=_get(tree,a[:-1])
            if isinstance(p,ast.BoolOp)or(isinstance(p,ast.BinOp)and isinstance(p.op,(ast.Add,ast.Mult)))or(isinstance(p,ast.Call)and isinstance(p.func,ast.Name)and p.func.id in {'min','max','sum','all','any'}):continue
        pairs.append((a,b))
    random.Random(identity+':binding-audit').shuffle(pairs);baseline=invariant(code);tried=0
    for u,v in itertools.combinations(pairs,2):
        if set(u)&set(v):continue
        tried+=1
        if tried>16:break
        programs=[rewire(code,[u,v],bits)for bits in ((0,0),(0,1),(1,0),(1,1))]
        if len(set(programs))!=4:continue
        assert all(invariant(p)==baseline for p in programs)
        results=[execute(p,public,dataset)for p in programs]
        if not all(r['valid']for r in results):continue
        losses=[int(r['answer']!=expected)for r in results]
        delta=losses[3]-losses[2]-losses[1]+losses[0]
        if delta:return {'programs':programs,'predictions':[r['answer']for r in results],'errors':losses,'nonzero_error_interaction':delta,'literal_store_operator_case_read_invariant':True,'tried':tried}
    return {'nonzero_error_interaction':0,'tried':tried}


def main():
    out=ROOT/'artifacts/lsl_mixed256_20261110';rows={r['key']:r for r in load_json(out/'open_dataset.json')['records']if r['split']=='train'}
    bank=out/'candidates/common-canonical/train';primary={p['source']:p['result']for p in load_json(bank/'results.json')};tables=load_json(bank/'local/tables.json');selected=[];counts={d:0 for d in ('SARA_v2_Binary','RuleArena_Airline')}
    for t in tables:
        d=t['dataset']
        if d not in counts or not t['valid']or counts[d]>=2:continue
        program=primary[t['source']]['parsed']['program'];tree=validate(program)
        # Selection uses source order and code shape, not gold correctness.
        if not any(isinstance(n,ast.Assign)and len({x.id for x in ast.walk(n.value)if isinstance(x,ast.Name)and isinstance(x.ctx,ast.Load)})>=2 for n in ast.walk(tree)):continue
        counts[d]+=1;selected.append((t,program))
    results=[];started=time.monotonic()
    for t,code in selected:
        row=rows[t['source']];result=probe(code,row['public'],row['dataset'],row['key'],row['grade']['answer'])
        results.append({'source':row['key'],'dataset':row['dataset'],'old_rewiring_moves':len(current_swaps(code,row['key'])),**result})
        print(json.dumps({k:v for k,v in results[-1].items()if k!='programs'},ensure_ascii=False),flush=True)
    write_json(out/'scalar_binding_coverage_audit.json',{'selection':'first two already valid TRAIN programs per scalar task with multi-input assignments; code-shape only',
        'results':results,'physical_model_requests':0,'facts_queries_labels_not_changed':True,'seconds':time.monotonic()-started,
        'not_a_new_model_experiment_or_method_success':True})


if __name__=='__main__':main()
