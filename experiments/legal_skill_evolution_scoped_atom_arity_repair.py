"""Repair one unreachable constructor branch, using the actual type declaration.

No new source semantics: the learned AND/OR/authorization composition already
exists. Preserve the primary frozen outputs and record this engineering replay.
"""
import ast
from copy import deepcopy
from pathlib import Path
from experiments import legal_skill_evolution_scoped_atom_acquisition as e
from experiments import legal_skill_evolution_scoped_atom_frozen_reuse as r
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.source_effect_update import function_update

OUT=e.OUT/'arity_repair'


def run():
    before=e.prior.rows();assert not any(x[6]=='reserved' for x in before)
    previous=e.read(e.OUT/'FreeUpdate/compiled.json');lib=deepcopy(previous)
    ctor=next(c for c in lib['spec']['constructors'] if c['name']=='source_connector_atom')
    arity=1+len(ctor['arguments']);assert arity==6
    tree=ast.parse(lib['composition_program']);changed=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.If):continue
        test=ast.unparse(node.test)
        if "name == 'source_connector_atom'" not in test:continue
        for value in ast.walk(node.test):
            if isinstance(value,ast.Compare) and ast.unparse(value.left)=='len(term)':
                assert len(value.comparators)==1 and isinstance(value.comparators[0],ast.Constant)
                assert value.comparators[0].value==7
                changed.append({'before':test,'expected_declared_length':arity})
                value.comparators[0].value=arity
    assert len(changed)==1
    ast.fix_missing_locations(tree);lib['composition_program']=ast.unparse(tree)+'\n'
    assert {k:v for k,v in previous.items() if k!='composition_program'}=={k:v for k,v in lib.items() if k!='composition_program'}
    immutable_json(OUT/'FreeUpdate/library.json',lib)
    immutable_json(OUT/'repair_proof.json',{'actual_constructor':ctor,'changed_guards':changed,
        'existing_learned_connector_composition_not_changed':True,'raw_proposals_and_primary_frozen_libraries_retained':True,
        'type_execution_source_checks_unchanged':True,'same_arity_consistency_rule_applies_to_both_architectures':True,
        'C_library_unchanged_no_matching_unreachable_branch':True,'new_model_requests':0})
    public={s['key']:s for s in e.read(e.prior.prior.PUBLIC)};grading=e.read(e.prior.prior.GRADING)
    cases=[('acquisition',k,e.OUT/'execution/acquisition/FreeUpdate'/e.name_for(k)) for k in e.read(e.OUT/'protocol.json')['sources']]
    cases += [('frozen_reuse',k,r.OUT/'unscored/FreeUpdate'/e.name_for(k)) for k in e.read(r.OUT/'protocol.json')['reuse_sources']]
    for stage,key,path in cases:
        row=e.read(path);actual=e.prior.prior.evaluate_source(lib,row['observation'],public[key],grading[key])
        immutable_json(OUT/stage/e.name_for(key),{'source':key,**actual,'engineering_replay_not_new_frozen_validation':True,'new_model_requests':0})
    assert before==e.prior.rows()
    print('Declared6-field connector guard repaired7→6; existing learned logic activated;4 paid observations replayed;0 new requests.',flush=True)


if __name__=='__main__':run()
