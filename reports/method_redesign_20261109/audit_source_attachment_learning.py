"""Audit the completed, frozen source-learning pilot without new generation."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import math
import sqlite3

from experiments.rr_v2_source_attachment_learning import ROOT,BASE,STAGE,read,sha,snapshot
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.contract_compiler_runtime import scope_answer
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.source_attachment_learning import problem,choose,project
from reports.method_redesign_20261109.evaluate_source_attachment_learning import controls

BACKUP=Path('/media/sangfor/vdb/legal-skill-backups/source_attachment_learning_20261110')


def main():
    current=snapshot()
    with sqlite3.connect('file:'+str(BACKUP/'ledger.before.sqlite3')+'?mode=ro',uri=True) as db:
        before={t:db.execute('select * from '+t+' order by 1').fetchall() for t in current}
    assert all(r in current[t] for t in before for r in before[t])
    added={t:[r for r in current[t] if r not in before[t]] for t in current}
    assert len(added['calls'])==9 and len(added['meta'])==5 and not added['oracle_views']
    assert all(r[1]=='executor' and r[6]=='completed' for r in added['calls'])
    assert not [r for r in current['calls'] if r[6]=='reserved']
    freeze=read(STAGE/'reuse_freeze.json')
    for path,h in freeze['files'].items():assert sha(ROOT/path)==h,path
    assert sha(STAGE/'learned_attachment_parameters.json')==freeze['models_sha256']
    assert sha(STAGE/'controls_and_training_replay.json')==freeze['controls_sha256']
    seal=read(STAGE/'seal.json');learned=read(STAGE/'learned_attachment_parameters.json');control=read(STAGE/'controls_and_training_replay.json')
    predictions=read(STAGE/'fixed_source_reuse_predictions.json');replay=[]
    for row in predictions['results']:
        key=row['key'];raw=read(STAGE/(key+'_forest.json'))
        entry={'key':key,'original_mother':raw['material']['source'],'total_seed_claims':raw['material']['total_seed_claims'],
               'selected_claims':len(raw['material']['graph']['rules']),'forest_acquired':raw['accepted']}
        if raw['accepted']:
            p=problem(raw['material'],raw['forest'],[])
            restored=controls(raw,p,learned['models'],control['retrieval_memory'])
            for name,selection in restored.items():
                state=project(raw['material'],raw['forest'],selection['choice'])
                stored=row['controls'][name]['selection']
                assert selection['choice']==stored['choice']
                for field,value in selection.items():
                    if field=='score':assert math.isclose(value,stored[field],rel_tol=1e-12,abs_tol=1e-12)
                    else:assert value==stored[field]
                assert all(state[k]==row['controls'][name][k] for k in state)
            a=row['controls']['marginal'];b=row['controls']['frozen_proposal_prior']
            entry.update(cold_restore_equal=True,learned_choice_equals_frozen_prior=a['selection']['choice']==b['selection']['choice'],
                learned_source_state_equals_frozen_prior=all(a[k]==b[k] for k in ['graph','residuals','readings']),
                programs={name:{rid:r['program'] for rid,r in value['readings'].items()} for name,value in row['controls'].items()},
                selected_seed_head_counts={name:sum(r['proposal_rank']==len(json.loads(raw['wire']['content'])[rid]) for rid,r in value['readings'].items()) for name,value in row['controls'].items()},
                cross_action_exception_choices={name:sum(r['exception_target'] is not None for r in value['readings'].values()) for name,value in row['controls'].items()})
        else:entry.update(error=raw['error'],cold_restore_equal=None)
        replay.append(entry)
    assert all(r['learned_source_state_equals_frozen_prior'] for r in replay if r['forest_acquired'])
    # Restore the actual updated111 component into the preserved full cache.
    # Other three native TRAIN mothers remain the same paid program's graph.
    regression={}
    for name in ['marginal','hard_em']:
        raw=read(STAGE/'p111_forest.json');p=problem(raw['material'],raw['forest'],seal['partial_source_feedback']['p111'])
        state=project(raw['material'],raw['forest'],choose(learned['models'][name],p)['choice'])
        rows=[]
        for m in seal['training']:
            if not m['examples']:continue
            graph=deepcopy(m['graph'])
            if m['key']=='p111':
                changed={r['id']:r for r in state['graph']['rules']};ids={r['id'] for r in raw['material']['graph']['rules']}
                graph['rules']=[changed[r['id']] if r['id'] in changed else r for r in graph['rules'] if r['id'] not in ids or r['id'] in changed]
            for example in m['examples']:
                answer=scope_answer(graph,m['document'],example['id'])
                rows.append({'training_key':m['key'],'query':example['id'],'answer':answer['answer'],
                             'native_answer':example['answer'],'correct':answer['answer']==example['answer'],
                             'new_core_success_not_claimed':True})
        assert len(rows)==8
        regression[name]={'correct':sum(r['correct'] for r in rows),'n':8,'rows':rows,
                          'primarily_inherited_seed_results_not_eight_new_core_updates':True}
    calls=[]
    for r in added['calls']:
        value=json.loads(r[8]);assert value['thinking_requested'] is False and not value['reasoning_content'] and value['finish_reason']=='stop'
        calls.append({'id':r[0],'source':r[4],'status':r[6],'usage':value['usage'],'elapsed_seconds':value['elapsed_seconds'],
                      'finish_reason':value['finish_reason'],'thinking_requested':False,'reasoning_content_empty':True,
                      'request_hash':r[5],'incremental_local_api_cash_usd':0,'GPU_allocation_usd':None})
    delta={'before_rows':{t:len(v) for t,v in before.items()},'after_rows':{t:len(v) for t,v in current.items()},
           'old_rows_preserved':True,'new_calls':calls,'new_meta':added['meta'],'new_oracle_views':[],
           'ledger_logical_sha256':digest(current),'pending':0}
    immutable_json(STAGE/'request_ledger_delta.json',delta)
    review={'source_only_original_TRAIN_mothers':[114,116,117,118],'native_hypothesis_predictions_or_labels_added':0,
      'not_four_new_sources_or_eight_independent_benchmark_items':True,'selected_claim_denominator':8,
      'source_findings':[
       {'key':'p114','finding':'Both current receiver-scope claims were anchored by the reader to the general prohibition, while the source separately grants qualified disclosure to Representatives/employees. The learned selector leaves NOT(O(A)) unchanged. Recipient-specific grant/ban and their consent qualifications have not been recovered faithfully; do not assign a new native NLI label.'},
       {'key':'p116','finding':'Every reading of rule-2 cites shall disclose ... where the actual source says will disclose .... This is a content-word substitution, not case/whitespace normalization. The whole requested forest is rejected; rule-1 has candidate fragments but was not silently substituted for this missing claim.'},
       {'key':'p117','finding':'The source explicitly says shall not ... disclose in both selected scopes. Learned/prior NOT(O(A)) does not preserve that conduct prohibition. The ordinary lexical/tree control selects F(A), a more faithful main operator. Paragraph4.3 and named exceptions remain additional qualification gaps; this is not a whole-source or new native success claim.'},
       {'key':'p118','finding':'All five paths agree. The reader reuses a prohibition span across an original definition-derived claim and the actual prohibition; it omits express prior written consent from both selected qualification sets. No learned improvement, no new norm count, and no complete semantic pass is claimed.'}],
      'semantics_interpretation':'F(A) versus NOT(P(A)) is not counted as improvement without a locked permission convention; NOT(BREACH(A)) is a different legal consequence. Literal/schema success is separate from source correctness.',
      'mechanism_coverage':{'unseen_selected_slices':'All eight selected claims were share claims because the preserved seed found no return/retain pair in these four sources.',
                            'unseen_cross_action_binding_executions':0,'not_an_added_all_branches_gate':True},
      'decision':'Stop this source-interpretation reranking candidate. It updates parameters on the three annotated sources, but makes no changed source interpretation on the three executable fixed slices; the fourth has acquisition failure. No free-program/DEV expansion is justified to rescue this result. The bottleneck is now source-to-node/operator/qualification acquisition, not a missing optimizer or budget.',
      'first_contribution_established':False,'two_contributions_established':False,'goal_complete':False}
    immutable_json(STAGE/'source_semantic_review.json',review)
    out={'counts_total':{role:sum(r[1]==role for r in current['calls']) for role in ['executor','teacher']},'pending':0,
         'ledger_rows':{t:len(v) for t,v in current.items()},'new_charged_attempts':{'executor':9,'teacher':0},
         'new_native_labels_or_oracle_views':0,'all_old_rows_preserved':True,'all_real_generations_stop':True,'executor_OFF_verified_on_all_nine':True,
         'cost':{'input_tokens':sum(x['usage']['prompt_tokens'] for x in calls),
                 'output_tokens':sum(x['usage']['completion_tokens'] for x in calls),
                 'input_plus_output_tokens':sum(x['usage']['total_tokens'] for x in calls),
                 'elapsed_generation_seconds':sum(x['elapsed_seconds'] for x in calls),
                 'incremental_local_api_cash_usd':0,'teacher_calls':0,'GPU_allocation_usd':None,'project_total_cash_usd':None,
                 'author_partial_annotation_elapsed_seconds':None,'author_supervision_not_free_or_model_discovered':True},
         'annotated_TRAIN_sources':3,'partial_source_constraints':3,
         'training_fit':{key:{name:value['training_compatible'] for name,value in values.items()} for key,values in control['training_replay'].items()},
         'native_TRAIN_regression':regression,'fixed_source_reuse':replay,'source_semantic_review':review,
         'restored_parameter_and_output_replay_equal':True,'compiler_cache_seed_and_learning_attribution_separate':True,
         'unseen_method_changed_outputs':0,'unseen_decodable_slices':3,'unseen_acquisition_failures':1,
         'no_unseen_method_semantic_gain_observed':True,'old_0_of_89_full_executor_IR_denominator_unchanged':True,
         'DEV_started':False,'TEST_started':False,'main_training_started':False,'paper_started':False,
         'goal_status':'active','goal_complete':False,'first_contribution_established':False,'two_contributions_established':False}
    assert current==snapshot()
    immutable_json(ROOT/'reports/method_redesign_20261109/source_attachment_learning_results.json',out)
    immutable_json(STAGE/'final_audit.json',out)
    if not (BACKUP/'ledger.after.sqlite3').exists():
        with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as src,sqlite3.connect(BACKUP/'ledger.after.sqlite3') as dst:src.backup(dst)
    print(json.dumps({'counts':out['counts_total'],'cost':out['cost'],'decodable':3,'unchanged_from_prior':3,'native_regression':{k:v['correct'] for k,v in regression.items()},'goal_complete':False}))


if __name__=='__main__':main()
