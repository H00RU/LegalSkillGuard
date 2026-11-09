"""Learn, execute and compare paths on preserved TRAIN; zero new calls.

The complete prior source-bound prototype remains at implementation542b919 and
public80e396. This creates new results rather than overwriting that evidence.
"""
from datetime import datetime,timezone
import hashlib
import json
from legal_skill_guard.rr.source_discrimination import (compile_discrimination,learn_evidence_paths,
    learn_selector,execute_selector,execute_paths,apply_constraints)
from legal_skill_guard.rr.semantic_frames import frame_vector,reader_vector
from experiments.rr_v2_semantic_learning import STAGE,ROOT,REPORT,read,annotations,response,check_frozen
from reports.method_redesign_20261109.evaluate_source_bound_program import training_examples


def main():
    check_frozen();examples=training_examples();skill=compile_discrimination(examples)
    ordinary=learn_evidence_paths(examples,contrast=False)
    seal=read(STAGE/'seal.json');gold=annotations(seal,'excluded');results=[]
    for c in seal['cases']:
        if c['fold']!='excluded':continue
        r=reader_vector(response(c,'reader')['validation']['decoded'])
        m=apply_constraints(skill,c['facts'],c['focus'],r)
        baseline=execute_paths(ordinary,m['candidates']);h=frame_vector({'values':gold[c['case_id']]['frame']})
        results.append({'case_id':c['case_id'],'mother':c['source'],'h':h,'M1_prediction':m['prediction'],
            'ordinary_path_prediction':baseline,'M1_correct':m['prediction']==h,'ordinary_correct':baseline==h,
            'question_actions_required':len(m['question_plan']['actions']),
            'native_query':c['original_query'],'native_legal_answer_produced':False})
    loo=[]
    for mother in sorted({e['mother'] for e in examples}):
        train=[e for e in examples if e['mother']!=mother];held=[e for e in examples if e['mother']==mother]
        comp=compile_discrimination(train);control=learn_evidence_paths(train,contrast=False)
        for e in held:
            candidates=execute_selector(comp['selector'],e['facts'],{'payer':e['frame']['payer'],'payee':e['frame']['payee']})['candidates']
            truth=frame_vector({'values':e['frame']})
            a=execute_paths(comp['learned_evidence_paths'],candidates);b=execute_paths(control,candidates)
            loo.append({'case_id':e['case_id'],'induction_mothers':comp['selector']['training_mothers'],
                'h':truth,'M1_prediction':a,'ordinary_prediction':b,'M1_correct':a==truth,'ordinary_correct':b==truth,
                'version_space_sizes':[len(t['consistent_paths']) for t in comp['learned_evidence_paths']['targets']]})
    paths=skill['learned_evidence_paths'];out={
        'captured_utc':datetime.now(timezone.utc).isoformat(),'new_model_calls':0,
        'evidence_type':'Offline repair/attribution on previously observed real TRAIN; not a new blind experiment',
        'source_files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [
            'legal_skill_guard/rr/source_discrimination.py','reports/method_redesign_20261109/evaluate_evidence_paths.py']},
        'previous_version_preserved_at_implementation':'542b91923d780d02c8bb4fb130c15ccc09e87ff0',
        'previous_public_evidence':'80e3962760c32b8e6c7179b05ea69969860c26dc',
        'learned_skill':skill,'ordinary_same_information_paths':ordinary,'excluded_case_regressions':results,
        'leave_one_induction_mother_out':loo,
        'path_version_spaces_equal':all(a['consistent_paths']==b['consistent_paths'] for a,b in zip(paths['targets'],ordinary['targets'])),
        'additional_paths_eliminated_by_observed_pair_changes':sum(t['contrast_removes_point_consistent_paths'] for t in paths['targets']),
        'M1_correct':sum(r['M1_correct'] for r in results),'ordinary_correct':sum(r['ordinary_correct'] for r in results),
        'loo_M1_correct':sum(r['M1_correct'] for r in loo),'loo_ordinary_correct':sum(r['ordinary_correct'] for r in loo),
        'pair_redundancy_proposition':{
            'assumptions':'Both arms receive all verified point labels for both members of every pair; pair constraints only demand the observed equality/change of these labels.',
            'claim':'Every point-consistent hypothesis already satisfies every such pair constraint; intersecting them does not change the version space, for any hypothesis class.',
            'proof':'For each pair i,j, substitute f(x_i)=y_i and f(x_j)=y_j into [f(x_i)=f(x_j)] iff [y_i=y_j].',
            'does_not_claim':'Counterfactual examples are useless, or all broader discrimination-program designs are equivalent. New examples add point information; executable questions and different generalization/cost policies may still differ.'},
        'decision':'Withhold the independent claim for this path-constraint instance. Do not buy more responses under unchanged fully labeled pair supervision to claim extra information.',
        'native_end_to_end_validation_complete':False,'two_contributions_established':False,'goal_complete':False}
    (REPORT/'M1_learned_dependency_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ('new_model_calls','path_version_spaces_equal','additional_paths_eliminated_by_observed_pair_changes','M1_correct','ordinary_correct','loo_M1_correct','loo_ordinary_correct','goal_complete')}))
    print(json.dumps({'paths':[t['consistent_paths'] for t in paths['targets']],
        'native_queries':[{k:r[k] for k in ('case_id','native_query')} for r in results]},ensure_ascii=False))


if __name__=='__main__':main()
