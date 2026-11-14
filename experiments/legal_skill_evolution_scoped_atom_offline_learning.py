"""Zero-model-call examination of the actual acquired source/G learning path.

Proves the deployed C legal outputs do not use reader facts on all four actual
saved executions, then uses the remaining fixed original12 TRAIN materials.
Free source-only is explicitly an offline ordinary-program control, not a fresh
complete neural run. No DEV/TEST or current frozen-reuse repair is performed.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from experiments import legal_skill_evolution_scoped_atom_acquisition as e
from experiments import legal_skill_evolution_scoped_atom_execution as execution
from experiments import legal_skill_evolution_scoped_atom_frozen_reuse as reuse
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.open_acquisition import execute_source_program,fit
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations
from legal_skill_guard.skill_evolution.projected_composition_profiles import admissible_projected_compositions
from legal_skill_guard.skill_evolution.source_composition import statement_fingerprint
from legal_skill_guard.skill_evolution.relational_rules import canonical

OUT=e.OUT/'offline_remaining_TRAIN'


def encode(key,lib,pub,units,source_output):
    return encode_source_observations(key,source_text=pub['source_text'],units=units,source_output=source_output,
        operations=lib['operations'],queries=[],answers=[],scope=lib['scope'],query_scopes={},
        complete_source_absence_choices=lib.get('complete_source_absence_choices'))


def norm_keys(result,lib):
    return sorted(statement_fingerprint(row) for row in result['execution']['source_output']['statements']
        if e.term_sort(row['term'],e.constructors(lib['spec']))=='Norm')


def run():
    before=e.prior.rows();assert not any(r[6]=='reserved' for r in before)
    p=e.read(e.OUT/'protocol.json');rp=e.read(reuse.OUT/'protocol.json');original=e.read(e.PARENT/'protocol.json')
    keys=[k for k in original['acquisition_sources'] if k not in p['sources']+rp['reuse_sources']]
    assert len(keys)==8
    libs={'ConstraintAcquire':e.read(e.OUT/'execution/ConstraintAcquire/learned.json'),
          'FreeUpdate':e.read(e.OUT/'FreeUpdate/compiled.json')}
    public={s['key']:s for s in e.read(e.prior.prior.PUBLIC)}
    immutable_json(OUT/'selection_and_protocol.json',{'same_goal':True,'goal_complete':False,'sources':keys,
        'selection':'All8 remaining mothers from the original fixed12 TRAIN, excluding current2 acquisition and2 frozen reuse; no score-based selection',
        'new_model_requests_allowed':0,'previous_frozen_reuse_not_repaired_or_repeated':True,
        'C_library_sha256':e.digest(libs['ConstraintAcquire']),'Free_library_sha256':e.digest(libs['FreeUpdate']),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'Free_source_only_is_offline_control_not_a_new_full_neural_run':True})
    # The current C rules do not depend on any reading predicate, even transitively.
    banned={'reader_query','query_window','query_focus','reader_observed_value','query_choice','query_unknown','query_unread','evidence_unit','evidence_quote'}
    assert not any(a['predicate'] in banned for rule in libs['ConstraintAcquire']['language']['rules'] for a in rule['body'])
    checks=[]
    for key,folder in [(k,e.OUT/'execution/acquisition/ConstraintAcquire') for k in p['sources']]+[(k,reuse.OUT/'unscored/ConstraintAcquire') for k in rp['reuse_sources']]:
        row=e.read(folder/e.name_for(key));o=row['observation'];v=o['visible_inputs'];lib=libs['ConstraintAcquire']
        pruned=encode(key,lib,{'source_text':v['source_text']},v['units'],v['source_output'])
        original_result=e.prior.prior.evaluate_source(lib,o,public[key],None)
        pruned_result=e.prior.prior.evaluate_source(lib,pruned,public[key],None)
        assert norm_keys(original_result,lib)==norm_keys(pruned_result,lib)
        assert [x['execution']['value'] for x in original_result['feedback']['views']]==[x['execution']['value'] for x in pruned_result['feedback']['views']]
        checks.append({'source':key,'actual_legal_Norms_and_native_decisions_exact_after_deleting_all_reader_facts':True})
    immutable_json(OUT/'actual_C_reader_independence.json',{'checks':checks,'static_reader_predicate_dependencies':[],
        'new_model_requests':0,'source_output_retained_exact':True})
    grading=e.read(e.prior.prior.GRADING)
    for arm,lib in libs.items():
        for key in keys:
            dst=OUT/'sources'/arm/e.name_for(key)
            if dst.exists():continue
            pub,units,up=e.prior.prior.source_material(e.PARENT,public,key)
            output,trace=execute_source_program(lib['source_program'],lib['spec'],source_text=pub['source_text'],units=units,source_output=up)
            o=encode(key,lib,pub,units,output)
            actual=e.prior.prior.evaluate_source(lib,o,public[key],grading[key])
            row={'source':key,'observation':o,'actual':actual,'actual_source_execution':trace,
                 'new_model_requests':0,'not_a_new_full_neural_run':True}
            if arm=='ConstraintAcquire':
                profile=admissible_projected_compositions(lib,o,e.prior.prior.checker(lib,public[key],grading[key]),timeout_seconds=90)
                immutable_json(OUT/'profiles'/e.name_for(key),profile)
                row['profile']=profile
            immutable_json(dst,row)
            print(json.dumps({'arm':arm,'source':key,'correct':sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views']),
                'new_model_requests':0,'profile_status':row.get('profile',{}).get('status')}),flush=True)
    lib=libs['ConstraintAcquire'];records=[e.read(OUT/'sources/ConstraintAcquire'/e.name_for(k)) for k in keys]
    if all(r['profile']['status']=='complete' for r in records):
        learned,result=fit(lib,[e.prior.prior.attach_scored_theories(r['observation'],r['profile']) for r in records],
            prior_rule_ids=lib['selected_rule_ids'],timeout_seconds=90)
        immutable_json(OUT/'fit.json',result)
        if result['status']=='sat':
            immutable_json(OUT/'learned_candidate_NOT_DEPLOYED.json',learned)
            for r in records:
                key=r['source'];immutable_json(OUT/'fitted_execution'/e.name_for(key),
                    e.prior.prior.evaluate_source(learned,r['observation'],public[key],grading[key]))
    assert before==e.prior.rows()
    immutable_json(OUT/'TERMINAL_PRESERVATION.json',{'new_model_requests':0,'all10579_ledger_rows_unchanged':len(before)==10579,
        'ledger_rows_unchanged':len(before),'goal_complete':False,'frozen_libraries_unchanged':True})


if __name__=='__main__':run()
