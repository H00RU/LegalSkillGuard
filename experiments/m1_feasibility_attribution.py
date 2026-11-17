"""Finite attribution checks on already sealed M1 outputs. No model or repair."""
from copy import deepcopy
import json
from pathlib import Path

from experiments.m1_finite_feasibility import OUT, ROOT, read
from legal_skill_guard.paired_interfaces.asset_interfaces import frozen_skill
from legal_skill_guard.paired_interfaces.native_graph_consumers import partial_skill
from legal_skill_guard.rr.checkpoint import immutable_json


def check():
    assert (OUT/'terminal.json').exists()
    cases=read(OUT/'offline_cases.json'); scores=read(OUT/'native_scores.json')
    comparisons=[]; unsupported_assertions=[]; complete_checks=[]
    skill=frozen_skill()
    for c in cases:
        if c['plan']['name']!='local_records':continue
        record=c['current_actual']['ports']
        if record is None or not record['inventory_complete'] or record['unresolved']:continue
        # Compare F and generated F' on the SAME actual port values. Missing
        # statically unused fields remain unknown, rather than fabricated false.
        inputs={'governing_regime':c['plan']['public_context']['governing_regime'],
                'output_family':c['view']['native_tasks'][0]}
        domains=[]
        for field,port in skill['inputs'].items():
            if port['type']=='array':
                inputs[field]=[]
                for i,a in enumerate(record['assets']):
                    value=a['fields'].get(field,{'status':'unread','value':None})
                    x=value['value'] if value['status'] in ('stated','negated') else None
                    inputs[field].append(x)
                    if x is None and field.startswith('asset_is_'):
                        domains.append({'path':[field,i],'values':[False,True]})
        inputs['number_of_debtors']=record['globals'].get('number_of_debtors',{}).get('value')
        full=partial_skill(skill,inputs,domains)
        native=c['current_actual']['native'][inputs['output_family']]
        assert (full['handled'],full['answer']) == (native['handled'],native['answer'])
        comparisons.append({'source':c['source']['key'],'view':c['view_id'],
            'full_and_generated_same_actual_inputs_answer_equal':True,'handled':full['handled'],
            'full_result':full,'generated_result':native})
        # Only uniquely source-anchored reviewed attributes are compared; no
        # label or reference fact is used to modify the recorded prediction.
        reference=c['source_card']['port_record']['assets']
        for a in record['assets']:
            matches=[r for r in reference if r['unit_id']==a['unit_id'] and r['quote'] in a['quote']]
            if len(matches)!=1:continue
            r=matches[0]
            for field,value in a['fields'].items():
                expected=r['fields'].get(field)
                if expected and expected['status']=='unknown' and value['status'] in ('stated','negated'):
                    unsupported_assertions.append({'source':c['source']['key'],'view':c['view_id'],
                        'unit_id':a['unit_id'],'source_quote':a['quote'],'field':field,
                        'reviewed_cell':expected,'actual_cell':value,
                        'source_review_is_not_independent_whole_case_gold':True})
        ref=c['reference_probe']['native'][inputs['output_family']]
        for w in ref.get('contrasting_or_representative_completions',[]):
            result=partial_skill(dict(skill,procedure=c['plan']['residual_program']['procedure']),
                                 w['completion_witness'],[])
            assert result['handled'] and result['answer']==w['result']['answer']
            complete_checks.append({'source':c['source']['key'],'view':c['view_id'],
                'completion_inputs':w['completion_witness'],'answer':result['answer'],
                'reference_reason':ref['reason']})
    assert len(comparisons)==3
    assert len(unsupported_assertions)==2
    selected=read(OUT/'terminal.json')['selection']
    cal=scores['calibration_diagnostic']
    positives=[r for r in cal if r['candidate']==selected['M1'] and r['grade']>0]
    flagged={(r['source'],r['view']) for r in unsupported_assertions}
    assert len(positives)==2 and all((r['source'],r['view']) in flagged for r in positives)
    result={'decision':'stop_current_M1_expansion_preserve_prototype',
        'raw_native_F1_gain_retained':True,'raw_native_F1_macro':1/3,
        'native_exact_correct_all_three_arms':0,'diagnostic_native_tasks_per_arm':4,
        'automatic_semantic_program_rewrite_implemented':True,
        'same_actual_input_full_F_vs_generated_F_prime_checks':comparisons,
        'all_positive_diagnostic_rows_have_unknown_to_known_assertions':True,
        'review_disagreements':unsupported_assertions,'reference_completion_replays':complete_checks,
        'reference_completion_check_count':len(complete_checks),
        'generated_interface_improves_source_faithfulness_established':False,
        'ordinary_prompt_is_two_candidate_selection_not_exhaustive_prompt_optimization':True,
        'cannot_establish_general_method_failure_from_three_TRAIN_mothers':True,
        'precise_revision_before_any_reconsideration':[
            'Align ownership/category field semantics with explicit official task assumptions; preserve genuinely unknown cases.',
            'Certify source-grounded extraction separately from native partial F1; never certify using the reference graph in production.',
            'Close source-input and fixed-consumer scope gaps using training evidence before any broader M1 claim.'],
        'no_additional_generation_or_training_authorized_by_this_result':True,
        'new_model_calls_in_attribution':0,'original_predictions_scores_references_unchanged':True,
        'M2_remains_stopped':True,'Goal_complete':False}
    immutable_json(OUT/'attribution_decision.json',result)
    print(json.dumps({'decision':result['decision'],'same_input_F_checks':len(comparisons),
        'unknown_to_known_positive_rows':len(unsupported_assertions),'completion_checks':len(complete_checks),
        'new_calls':0},ensure_ascii=False))


if __name__=='__main__':check()
