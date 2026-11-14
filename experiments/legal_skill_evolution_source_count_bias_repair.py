"""Actual B8 C counterevidence: finite representation counts as a bias repair.

The same raw24 source reads are used. This is a TRAIN-only deterministic common
feature/candidate repair, not new teacher learning or proof of a contribution.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_batch_update as update
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.open_acquisition import execute
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_rules import validate_language,validate_context
from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review
from legal_skill_guard.skill_evolution.source_observations import fact
from legal_skill_guard.skill_evolution.source_projection_counts import add_counts


ROOT=update.train.ROOT
OUT=ROOT/'artifacts/legal_skill_evolution_source_count_bias_repair_20261115'
PROJECTION={'name':'parsed_operative_disclosure_permissions','constructor':'acq_disclosure_v3',
    'arguments_equal':[{'position':1,'value':'operative_permission'}]}


def run():
    old=update.train.OUT/'B8/ConstraintAcquire'
    library=deepcopy(update.train.read(old/'compiled_candidate.json'))
    before=digest(library)
    language=library['language']
    language['signatures']['input_projection_count']={'arguments':['input_projection_name','representation_count'],'kind':'observed'}
    language['constants']['input_projection_name']=[PROJECTION['name']]
    language['constants']['representation_count']=[0]
    rule=deepcopy(next(r for r in language['rules'] if r['id']=='compose_complete_no_disclosure_query_v1'))
    original_id=rule['id'];rule['id']='compose_complete_no_disclosure_without_parsed_permission_v1'
    rule['body'].append(fact('input_projection_count',PROJECTION['name'],0));rule['cost']+=1
    language['rules'].append(rule)
    library['selected_rule_ids']=[r for r in library['selected_rule_ids'] if r!=original_id]+[rule['id']]
    library['input_projection_definitions']=[PROJECTION]
    validate_language(language)
    public={s['key']:s for s in update.train.read(update.train.parent.PREPARED/'public.json')if s['dataset']=='ContractNLI'}
    grading=update.train.read(update.train.parent.PREPARED/'grading.json')
    task=update.train.read(old.parent/'teacher_task.json')
    immutable_json(OUT/'candidate_library.json',library)
    rows=[]
    for entry in task['tasks']:
        sid=entry['source_id'];raw_path=old/'candidate_results'/update.train.previous.old.name_for(sid)
        raw=update.train.read(raw_path)
        observation=add_counts(raw['observation'],[PROJECTION]);validate_context(observation['context'],language)
        result=execute(library,observation)
        checker=with_disposal_review(update.train.previous.old.previous.prior.prior.checker(library,public[sid],grading[sid]),
            sid,task.get('shared_reviewed_source_scope_checks',[]),library['spec']['decision_program'],
            authorization_review=task.get('shared_branch_authorization_review'))
        feedback=checker(result['source_output'])
        row={'source':sid,'raw_observation_sha256':digest(raw['observation']),
            'actual_projection':observation['structural_projection_receipt'],
            'source_output':result['source_output'],'feedback':feedback,
            'correct':sum(bool(v['score']and v['score']['correct'])for v in feedback['views']),
            'unresolved':sum(not v['core_executed']for v in feedback['views']),
            'source_review_passed':feedback.get('source_review_passed',True),'new_model_calls':0}
        immutable_json(OUT/'results'/update.train.previous.old.name_for(sid),row)
        rows.append(row)
    receipt={'source_library_before_sha256':before,'new_library_sha256':digest(library),
        'same24_actual_TRAIN_source_reads_no_reissue':True,'new_model_calls':0,
        'native_correct':sum(r['correct']for r in rows),'native_total':4*len(rows),
        'unresolved':sum(r['unresolved']for r in rows),'all_existing_source_reviews_pass':all(r['source_review_passed']for r in rows),
        'row_summary':[{k:r[k]for k in ('source','correct','unresolved','source_review_passed')}for r in rows],
        'old_best_checked_native_correct':89,'old_proposal_native_correct_but_source_counterevidence':93,
        'ordinary_Free_B8_native_correct':92,
        'not_new_teacher_acquisition_or_global_optimum_or_method_contribution':True,
        'source_input_counts_are_common_code_expressible_by_Free':True,
        'not_promoted_into_current_frozen_library':True,'DEV_TEST_not_read':True,'goal_complete':False}
    immutable_json(OUT/'result.json',receipt)
    print(json.dumps({k:receipt[k]for k in ('native_correct','native_total','unresolved','all_existing_source_reviews_pass','new_model_calls')}),flush=True)


if __name__=='__main__':run()
