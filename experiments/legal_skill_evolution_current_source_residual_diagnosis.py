"""TRAIN-only exact diagnosis over subsets of current emitted source roots.

This relaxed interface is NOT all possible G programs, full legal semantics, or
an accepted repair. It asks whether merely selecting different existing roots
could correct the actual residuals. Paid observations and consumer stay fixed.
"""
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import hashlib
import json

from experiments import legal_skill_evolution_source_projection_runtime as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.span_compiler import execute_json
from legal_skill_guard.skill_evolution.open_acquisition import execute

ROOT=current.ROOT
OUT=ROOT/'artifacts/legal_skill_evolution_source_residual_diagnosis_20261115'
CONSUMED={'define_representative','complete_source_no_disclosure_permission',
    'complete_source_no_disposal_obligation','complete_source_no_retention_effect',
    'source_residual_observation_v3','disposal_obligation','retention_permission',
    'retention_exception','retention_prohibition','absolute_retention_prohibition',
    'permission','prohibition'}


def run():
    read=current.update.train.read
    library=read(current.OUT/'ConstraintAcquire/library.json')
    program=library['spec']['decision_program']
    assert program.count('def apply(inputs,premises):')==1
    batch_program=program.replace('def apply(inputs,premises):','def consumer_apply(inputs,premises):',1)+'''

def apply(inputs,premises):
    results=[]
    for roots in inputs['root_sets']:
        results.append(consumer_apply(inputs['case'],{'nodes':inputs['nodes'],'roots':roots}))
    return {'results':results}
'''
    public={s['key']:s for s in read(current.update.train.parent.PREPARED/'public.json') if s['dataset']=='ContractNLI'}
    grading=read(current.update.train.parent.PREPARED/'grading.json')
    summaries=[]
    for path in sorted((current.OUT/'ConstraintAcquire/results').glob('*.json')):
        actual=read(path)
        if actual['correct']==4:continue
        sid=actual['source'];assert public[sid]['split']=='train'
        statements=actual['source_output']['statements']
        active=[i for i,r in enumerate(statements) if r['term'][0] in CONSUMED]
        fixed=[i for i in range(len(statements)) if i not in active]
        roots=[sorted(fixed+list(c)) for n in range(len(active)+1) for c in combinations(active,n)]
        assert len(roots)==2**len(active)
        nodes=[{'id':i,'term':deepcopy(r['term']),'child_ids':[]} for i,r in enumerate(statements)]
        full_index=roots.index(list(range(len(statements))))
        old_views={v['view']:v for v in actual['feedback']['views']}
        views=[]
        for view in public[sid]['views']:
            if old_views[view['id']]['score']['correct']:continue
            values=execute_json(batch_program,{'case':{'task_id':view['id'],'question':view['public']['question']},
                'nodes':nodes,'root_sets':roots},{},allow_helpers=True)['results']
            assert values[full_index]==old_views[view['id']]['execution']['value']
            assert len(values)==len(roots)
            matching=[]
            for index,value in enumerate(values):
                if value['handled'] and value['used_nodes'] and grade_view('ContractNLI',view,grading[sid][view['id']],value['answer'])['correct']:
                    matching.append({'roots':roots[index],'answer':value['answer']})
            views.append({'view':view['id'],'original_value':values[full_index],
                'relaxed_root_subsets_exhaustively_executed':len(roots),
                'core_correct_subset_count':len(matching),'example_matching_subsets':matching[:8],
                'fallback_never_counts_as_a_correcting_theory':True,
                'diagnosis':'current_emitted_vocabulary_or_consumer_insufficient' if not matching else
                    'root_selection_or_interaction_may_repair_but_source_validity_not_proved'})
        result={'source':sid,'actual_source_roots':len(statements),'variable_consumed_roots':len(active),
            'fixed_nonconsumed_roots':fixed,'actual_full_execution_parity':True,'views':views,
            'not_full_G_language_or_full_semantic_inexpressibility':True,'new_model_calls':0}
        immutable_json(OUT/(path.name),result);summaries.append(result)
    immutable_json(OUT/'result.json',{'TRAIN_only':True,'DEV_TEST_not_read':True,'source_library_sha256':hashlib.sha256((current.OUT/'ConstraintAcquire/library.json').read_bytes()).hexdigest(),
        'consumer_program_sha256':hashlib.sha256(program.encode()).hexdigest(),
        'same_actual_paid_source_outputs':True,'no_rule_or_source_fact_added':True,
        'scope':'All subsets of current consumed root vocabulary, holding all other actual roots fixed.',
        'results':summaries,'not_an_accepted_repair_or_global_representation_certificate':True,
        'new_model_calls':0,'goal_complete':False})
    print(json.dumps([{'source':r['source'],'views':[(v['view'],v['core_correct_subset_count'],v['relaxed_root_subsets_exhaustively_executed']) for v in r['views']]} for r in summaries]),flush=True)


def complete_candidate_envelope():
    """Check the all-rules positive closure, without a new optimizer/model run.

    For these three residuals only, the fixed consumer has a single-root
    witness property: nda-5 Entailment needs one employee permission (with
    positive representative definitions); nda-16 Entailment needs one endpoint
    disposal; nda-20 NotMentioned needs one absence/non-full-disposal root.
    All definitions maximize employee tags and never remove them. Thus an
    absent witness in the all-rules envelope excludes every G-subset here.
    A found witness does NOT establish joint feasibility or source truth.
    """
    read=current.update.train.read
    library=read(current.OUT/'ConstraintAcquire/library.json')
    all_rules=deepcopy(library)
    all_rules['selected_rule_ids']=[r['id'] for r in library['language']['rules']]
    program=library['spec']['decision_program']
    batch=program.replace('def apply(inputs,premises):','def consumer_apply(inputs,premises):',1)+'''

def apply(inputs,premises):
    results=[]
    for roots in inputs['root_sets']:
        results.append(consumer_apply(inputs['case'],{'nodes':inputs['nodes'],'roots':roots}))
    return {'results':results}
'''
    public={s['key']:s for s in read(current.update.train.parent.PREPARED/'public.json') if s['dataset']=='ContractNLI'}
    grading=read(current.update.train.parent.PREPARED/'grading.json')
    results=[]
    for prior in read(OUT/'result.json')['results']:
        sid=prior['source']
        original=next(read(p) for p in (current.OUT/'ConstraintAcquire/results').glob('*.json') if read(p)['source']==sid)
        observation=original['observation']
        assert not observation['context']['unknown_groups']
        actual=execute(all_rules,observation)
        assert actual['composition']['complete'] and actual['composition']['status']=='sat'
        statements=actual['source_output']['statements']
        definitions=[i for i,r in enumerate(statements) if r['term'][0]=='define_representative']
        roots=[sorted(set(definitions+[i])) for i,r in enumerate(statements)
            if r['term'][0] in CONSUMED and i not in definitions]
        nodes=[{'id':i,'term':r['term'],'child_ids':[]} for i,r in enumerate(statements)]
        views=[]
        for residual in prior['views']:
            vid=residual['view'];view=next(v for v in public[sid]['views'] if v['id']==vid)
            expected=next(a for a in ('Entailment','Contradiction','NotMentioned')
                if grade_view('ContractNLI',view,grading[sid][vid],a)['correct'])
            assert (vid,expected) in {('nda-5','Entailment'),('nda-16','Entailment'),('nda-20','NotMentioned')}
            values=execute_json(batch,{'case':{'task_id':vid,'question':view['public']['question']},
                'nodes':nodes,'root_sets':roots},{},allow_helpers=True)['results']
            witnesses=[{'roots':r,'terms':[statements[i] for i in r]} for r,v in zip(roots,values)
                if v['handled'] and v['used_nodes'] and v['answer']==expected]
            views.append({'view':vid,'desired_original_TRAIN_answer':expected,
                'all_acquired_rules_output_witness_count':len(witnesses),'example_witnesses':witnesses[:3],
                'diagnosis':'G_selection_or_joint_source_constraints_not_excluded' if witnesses else
                    'current_positive_G_output_language_or_consumer_cannot_express_required_answer',
                'joint_G_feasibility_and_source_semantics_not_inferred_from_singletons':True})
        results.append({'source':sid,'all_rules':len(all_rules['selected_rule_ids']),
            'complete_all_rules_outputs':len(actual['composition']['certain_outputs']),
            'all_rendered_roots':len(statements),'representative_definitions':len(definitions),'views':views})
    immutable_json(OUT/'all_rules_envelope.json',{'actual_original_TRAIN_only':True,'fully_observed_positive_language':True,
        'same_acquired_rules_renderers_source_readings_and_consumer':True,'results':results,
        'scope':'Specific three residuals under the stated single-root witness property of this frozen consumer.',
        'not_a_proof_of_missing_English_concepts_or_full_source_correctness':True,'new_model_calls':0})
    print(json.dumps([{'source':r['source'],'rules':r['all_rules'],'outputs':r['complete_all_rules_outputs'],
        'views':[(v['view'],v['all_acquired_rules_output_witness_count'],v['diagnosis']) for v in r['views']]} for r in results]),flush=True)


if __name__=='__main__':run()
