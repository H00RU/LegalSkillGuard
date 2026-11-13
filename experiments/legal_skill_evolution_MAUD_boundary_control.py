"""One public punctuation repair, frozen before the fixed future pair is read.

Preserves all original programs. It adds no legal rule or source category and
does not dispatch any model. Both acquired architectures receive the same
rewrite; only the actual Free parser contains the affected sentence operations.
"""
import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.maud_source_feedback import evaluate_view,view_units
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure
from experiments.legal_skill_evolution_MAUD_rule_acquisition import setup,FOLDER,read,name_for,GRADING

HERE=FOLDER/'source_boundary_control'
HELPERS='''def source_sentence_dot(text,start=0):
    pos=text.find('.',start)
    while pos>=0:
        numeric=pos>0 and pos+1<len(text) and text[pos-1].isdigit() and text[pos+1].isdigit()
        if not numeric:
            return pos
        pos=text.find('.',pos+1)
    return -1

def source_previous_sentence_dot(text,start,end):
    previous=-1
    pos=source_sentence_dot(text,start)
    while pos>=0 and pos<end:
        previous=pos
        pos=source_sentence_dot(text,pos+1)
    return previous
'''


def repair(program):
    changes=[]
    class SentenceBoundaries(ast.NodeTransformer):
        function=None
        def visit_FunctionDef(self,node):
            saved=self.function;self.function=node.name
            result=self.generic_visit(node);self.function=saved
            return result
        def visit_Call(self,node):
            node=self.generic_visit(node)
            if (self.function not in ('definition_clause','sentence_at','extract_holders')
                    or not isinstance(node.func,ast.Attribute) or not node.args):return node
            f=node.func;first=node.args[0]
            if f.attr in ('find','rfind') and isinstance(first,ast.Constant) and first.value=='.':
                helper='source_sentence_dot' if f.attr=='find' else 'source_previous_sentence_dot'
                replacement=ast.Call(func=ast.Name(id=helper,ctx=ast.Load()),
                                     args=[deepcopy(f.value),*deepcopy(node.args[1:])],keywords=[])
            elif (self.function=='extract_holders' and f.attr=='find'
                  and isinstance(first,ast.Name) and first.id=='stop'):
                replacement=ast.IfExp(test=ast.Compare(left=deepcopy(first),ops=[ast.Eq()],
                    comparators=[ast.Constant(value='.')]),
                    body=ast.Call(func=ast.Name(id='source_sentence_dot',ctx=ast.Load()),
                                  args=[deepcopy(f.value),*deepcopy(node.args[1:])],keywords=[]),orelse=node)
            else:return node
            changes.append({'function':self.function,'before':ast.dump(node,include_attributes=False),
                            'after':ast.dump(replacement,include_attributes=False)})
            return ast.copy_location(replacement,node)
    original=ast.parse(program);updated=SentenceBoundaries().visit(deepcopy(original))
    if not changes:return program,changes
    updated.body.extend(ast.parse(HELPERS).body);ast.fix_missing_locations(updated)
    result=ast.unparse(updated)+'\n';validate_procedure(result,allow_helpers=True)
    literals=lambda tree:{n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
    if not literals(updated)-literals(original)<={'.'}:
        raise ValueError('Punctuation repair introduced a nonpunctuation string literal')
    return result,changes


def prepare():
    p,_,public=setup()
    if list((FOLDER/'reuse').glob('*/*.json')) or (FOLDER/'reuse_initial').exists():
        raise ValueError('Freeze the necessary repair before reading any future material')
    grading=read(GRADING);libraries={};receipts={}
    for arm in ('ConstraintAcquire','FreeUpdate'):
        library=read(FOLDER/arm/'learned.json');original=deepcopy(library)
        library['source_program'],changes=repair(library['source_program'])
        libraries[arm]=library
        receipts[arm]={'changes':changes,'original_library_sha256':digest(original),
            'repaired_library_sha256':digest(library),'same_public_punctuation_rewrite':True,
            'no_new_legal_rule_or_native_label':True}
    assert not receipts['ConstraintAcquire']['changes']
    assert receipts['FreeUpdate']['changes']
    rows=[]
    for key in p['acquisition_sources']:
        source=public[key]
        for view in source['views']:
            name=name_for(key,view);initial=read(FOLDER/'initial'/name)
            library=libraries['FreeUpdate']
            o=observe(object(),'offline-boundary-repair',key,library,
                source_text=view['public']['source_text'],units=view_units(view),source_output=initial['upstream'])
            o['context']['id']=digest({'source':key,'view':view['id']})
            actual=evaluate_view(library,o,source,view,grading[key][view['id']])
            old=read(FOLDER/'acquisition/FreeUpdate'/name)
            if actual['feedback']['reason']=='execution_error':raise ValueError(actual['feedback']['error'])
            row={'source':key,'view':view['id'],'observation':o,'original':old['feedback'],**actual}
            immutable_json(HERE/'acquisition/FreeRepaired'/name,row)
            rows.append({'source':key,'view':view['id'],
                'before_correct':old['feedback']['views'][0]['score']['correct'],
                'after_correct':actual['feedback']['views'][0]['score']['correct']})
    if sum(r['after_correct']for r in rows)!=12 or any(r['before_correct'] and not r['after_correct']for r in rows):
        raise ValueError('Inspect the actual training-only repair; do not change it using future feedback')
    for arm,library in libraries.items():immutable_json(HERE/arm/'library.json',library)
    nofit=deepcopy(libraries['ConstraintAcquire']);nofit['selected_rule_ids']=nofit['suggested_rule_ids']
    immutable_json(HERE/'NoFit/library.json',nofit)
    immutable_json(HERE/'repair_receipt.json',{'rows':rows,'architecture_receipts':receipts,
        'models_added':0,'all_original_records_preserved':True,
        'remaining_legal_role_or_scope_omissions_not_repaired':True})
    immutable_json(HERE/'freeze.json',{'control_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'libraries':{arm:digest(library)for arm,library in libraries.items()},'NoFit_library_sha256':digest(nofit),
        'future_sources':p['reuse_sources'],'future_materials_and_labels_not_read_for_repair':True,
        'post_TRAIN_necessary_parser_fix_not_a_new_method_arm':True,'new_model_requests':0})


def verify():
    p,_,public=setup();freeze=read(HERE/'freeze.json')
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=freeze['control_source_sha256']:
        raise ValueError('Frozen repair-control source changed')
    for arm,expected in freeze['libraries'].items():
        if digest(read(HERE/arm/'library.json'))!=expected:raise ValueError('Frozen repair library changed')
    if digest(read(HERE/'NoFit/library.json'))!=freeze['NoFit_library_sha256']:
        raise ValueError('NoFit changed after control freeze')
    return p,public


def reuse():
    p,public=verify()
    if list((FOLDER/'reuse_scores').glob('*/*.json')):
        raise ValueError('Save all unscored control execution before scoring the fixed pair')
    for key in p['reuse_sources']:
        source=public[key]
        for view in source['views']:
            name=name_for(key,view)
            for arm in ('NoFit','FreeUpdate'):
                library=read(HERE/arm/'library.json');dst=HERE/'reuse'/arm/name
                if dst.exists():continue
                if arm=='NoFit':o=read(FOLDER/'reuse/ConstraintAcquire'/name)['observation']
                else:
                    initial=read(FOLDER/'reuse_initial'/name)
                    o=observe(object(),'frozen-boundary-control',key,library,
                        source_text=view['public']['source_text'],units=view_units(view),source_output=initial['upstream'])
                    o['context']['id']=digest({'source':key,'view':view['id']})
                immutable_json(dst,{'source':key,'view':view['id'],'observation':o,
                    **evaluate_view(library,o,source,view),'new_model_requests':0})


def score():
    p,public=verify()
    if any(not (HERE/'reuse'/a/name_for(k,v)).exists()for a in ('NoFit','FreeUpdate')
           for k in p['reuse_sources']for v in public[k]['views']):
        raise ValueError('Complete all unscored fixed control executions first')
    grading=read(GRADING)
    for key in p['reuse_sources']:
        for view in public[key]['views']:
            name=name_for(key,view)
            for arm in ('NoFit','FreeUpdate'):
                row=read(HERE/'reuse'/arm/name);library=read(HERE/arm/'library.json')
                immutable_json(HERE/'scores'/arm/name,evaluate_view(library,row['observation'],public[key],view,grading[key][view['id']]))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['prepare','reuse','score']);args=ap.parse_args()
    {'prepare':prepare,'reuse':reuse,'score':score}[args.phase]()
