"""Build an ordinary, semantics-preserving reader-helper control corpus.

This is a baseline asset for prospective abstraction learning, not an abstraction
learning contribution. It removes unreachable inherited code and groups exact
alpha-equivalent dependency closures with the same used constructor meanings.
No legal term, rule, alias or label is created.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.span_compiler import execute_json,execution_source_units

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/legal_skill_evolution_reader_bank_20261113'
read=lambda p:json.loads(p.read_text())
digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

PROGRAMS={
    'source_v5':'artifacts/legal_skill_evolution_scoped_acquisition_v5_20261113/phase2/ScopedGrammar/adapted_proposal.json',
    'open_effect':'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/SourceEffect/compiled.json',
    'independent_open':'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/IndependentOpen/compiled.json',
    'local_fragments':'artifacts/legal_skill_evolution_binding_TRAIN_v2_20261113/frontend_compiled.json'}


def dependency_graph(code):
    tree=ast.parse(code)
    if any(not isinstance(n,ast.FunctionDef) for n in tree.body):
        raise ValueError('This control only extracts actual pure function modules')
    functions={n.name:n for n in tree.body}
    if len(functions)!=len(tree.body):raise ValueError('Shadowed function identity')
    # Include function values as well as direct calls, so a passed callback is
    # not incorrectly classified as dead. No dynamic reflection is permitted
    # by the common execution engine.
    dependencies={name:{n.id for n in ast.walk(fn) if isinstance(n,ast.Name)
                       and isinstance(n.ctx,ast.Load) and n.id in functions}
                  for name,fn in functions.items()}
    return tree,functions,dependencies


def closure(start,dependencies):
    selected=set(start)
    while True:
        more=set().union(*(dependencies[n] for n in selected))-selected
        if not more:return selected
        selected|=more


def fingerprints(functions,dependencies,spec):
    schema={c['name']:c for c in spec['constructors']};done={};visiting=set()
    def one(name):
        if name in done:return done[name]
        if name in visiting:raise ValueError('Recursive helper needs a different canonicalization')
        visiting.add(name)
        dep={n:one(n) for n in sorted(dependencies[name])}
        fn=deepcopy(functions[name]);fn.name='F';locals_={}
        for arg in [*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs]:
            locals_.setdefault(arg.arg,'a'+str(len(locals_)))
        for n in ast.walk(fn):
            if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store):
                locals_.setdefault(n.id,'v'+str(len(locals_)))
        class Alpha(ast.NodeTransformer):
            def visit_arg(self,node):
                node.arg=locals_[node.arg];return node
            def visit_Name(self,node):
                if node.id in locals_:node.id=locals_[node.id]
                elif node.id in dep:node.id='h'+dep[node.id]
                return node
        fn=Alpha().visit(fn)
        used={n.value for n in ast.walk(fn) if isinstance(n,ast.Constant)
              and isinstance(n.value,str) and n.value in schema}
        signature={'AST':ast.dump(fn,include_attributes=False),
            'used_constructor_definitions':{n:schema[n] for n in sorted(used)}}
        done[name]=digest(signature);visiting.remove(name);return done[name]
    for name in functions:one(name)
    return done


if __name__=='__main__':
    db=sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    before=list(db.execute('select * from calls order by id'))
    assert not any(r[6]=='reserved' for r in before)
    public_path=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    public={s['key']:s for s in read(public_path)}
    protocol=read(ROOT/'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/protocol.json')
    keys=protocol['teacher_sources']
    groups={};programs={};replays=[]
    for label,path in PROGRAMS.items():
        value=read(ROOT/path);code=value.get('source_program',value.get('program'))
        spec=value.get('grammar',value.get('spec'))
        tree,functions,deps=dependency_graph(code);active=closure({'apply'},deps)
        codes={n:ast.get_source_segment(code,functions[n]) for n in functions}
        pruned='\n\n'.join(codes[n] for n in functions if n in active)+'\n'
        hashes=fingerprints(functions,deps,spec)
        helper_code='\n\n'.join(codes[n] for n in functions if n in active and n!='apply')+'\n'
        immutable_json(OUT/'programs'/(label+'.json'),{'origin_path':path,'origin_sha256':hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),
            'constructors':spec['constructors'],'original_code':code,'active_program':pruned,
            'all_active_helpers':helper_code,'not_a_new_learned_program':True})
        programs[label]={'origin_path':path,'functions':len(functions),'reachable':len(active),
            'unreachable':sorted(set(functions)-active),'active_helpers':len(active)-1,
            'original_characters':len(code),'active_characters':len(pruned),'active_helper_characters':len(helper_code),
            'active_function_fingerprints':{n:hashes[n] for n in sorted(active)}}
        for name in sorted(active-{'apply'}):
            h=hashes[name];entry=groups.setdefault(h,{'id':h,'occurrences':[]})
            needed=closure({name},deps)
            entry['occurrences'].append({'program':label,'function':name,
                'dependency_functions':sorted(needed),
                'dependency_closure_characters':sum(len(codes[n])+2 for n in needed),
                'source_code':codes[name],
                'fingerprint_is_exact_code_not_source_semantics_certification':True})
        for key in keys:
            source=public[key];pub=source['views'][0]['public']
            units,mapping=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
            inputs={'source_text':pub['source_text'],'source_spans':units}
            original=execute_json(code,deepcopy(inputs),{},allow_helpers=True)
            extracted=execute_json(pruned,deepcopy(inputs),{},allow_helpers=True)
            assert original==extracted,(label,key)
            replays.append({'program':label,'source':key,'original_output_digest':digest(original),
                            'extracted_output_digest':digest(extracted),'exact_output_preserved':True})
    after=list(db.execute('select * from calls order by id'));assert before==after
    copied=[g for g in groups.values() if len(g['occurrences'])>1]
    result={'source_program_count':len(programs),'programs':programs,
        'total_functions':sum(p['functions'] for p in programs.values()),
        'total_reachable_functions':sum(p['reachable'] for p in programs.values()),
        'unreachable_inherited_functions':sum(len(p['unreachable']) for p in programs.values()),
        'active_helper_occurrences':sum(p['active_helpers'] for p in programs.values()),
        'exact_typed_dependency_classes':len(groups),'repeated_classes':len(copied),
        'ordinary_function_extraction_control':True,'new_parameterized_computation_abstractions_learned':0,
        'all_outputs_preserved_on_current_common_inputs':True,'replays':replays,
        'not_a_replay_of_old_scientific_scores':True,'native_labels_or_DEV_TEST_loaded':False,
        'held_new_TRAIN_sources_opened':False,'new_model_requests':0,
        'old_ledger_rows_unchanged':len(after),'ledger_sha256':digest(after),
        'source_ids_are_overlapping_training_parents_not_independent_program_count_times_eight':True,
        'initial_source_v5_was_inherited_by_both_open_updates_and_the_local_decoder':True,
        'source_truth_or_future_utility_not_established_by_code_equivalence':True,'goal_complete':False}
    immutable_json(OUT/'helper_classes.json',{'groups':list(groups.values())})
    immutable_json(OUT/'completed.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('programs','replays')},ensure_ascii=False))
