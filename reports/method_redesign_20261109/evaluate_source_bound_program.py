"""Post-hoc offline source binding repair and same-material wrapper control.

All induction uses only the original two induction mothers. Excluded texts and
teacher annotations were seen in the preceding pilot: this is regression on
real records, not a fresh blind experiment or a model-generated IR success.
"""
from datetime import datetime,timezone
import hashlib
import json
from legal_skill_guard.rr.source_discrimination import (learn_selector,execute_selector,
                                                      compile_discrimination,apply_constraints)
from legal_skill_guard.rr.semantic_frames import frame_vector,reader_vector
from legal_skill_guard.rr.coverage import digest
from experiments.rr_v2_semantic_learning import STAGE,REPORT,ROOT,read,check_frozen,annotations,response


def training_examples():
    seal=read(STAGE/'seal.json');gold=annotations(seal,'induction');examples=[]
    for c in seal['cases']:
        if c['fold']!='induction':continue
        questions=read(STAGE/'teacher'/(digest(c['source'])+'.json'))['value']['discrimination_questions']
        examples.append({'case_id':c['case_id'],'mother':c['source'],'facts':c['facts'],'frame':gold[c['case_id']]['frame'],
                         'questions':questions,
                         'direct':frame_vector(response(c,'direct')['validation']['decoded']),
                         'reader':reader_vector(response(c,'reader')['validation']['decoded'])})
    return examples


def main():
    check_frozen();examples=training_examples();ordinary=learn_selector(examples);skill=compile_discrimination(examples)
    seal=read(STAGE/'seal.json');gold=annotations(seal,'excluded');rows=[]
    program={'captured_utc':datetime.now(timezone.utc).isoformat(),'evidence_type':'New offline source-program prototype on previously observed real TRAIN; not blind',
             'source_files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [
                 'legal_skill_guard/rr/source_discrimination.py','reports/method_redesign_20261109/evaluate_source_bound_program.py']},
             'induction_cases':[e['case_id'] for e in examples],'ordinary_wrapper':ordinary,'M1_source_bound_skill':skill,
             'new_model_calls':0,'original_frozen_pilot_unchanged':True,'semantic_certificate':False}
    for c in seal['cases']:
        if c['fold']!='excluded':continue
        baseline=execute_selector(ordinary,c['facts'],c['focus'])
        raw_reader=reader_vector(response(c,'reader')['validation']['decoded'])
        actual=apply_constraints(skill,c['facts'],c['focus'],raw_reader);g=gold[c['case_id']]['frame'];h=frame_vector({'values':g})
        exact=any(all(candidate['values'][r]==g[r] for r in ('payer','payee','work_activity','payment_medium')) for candidate in actual['candidates'])
        rows.append({'case_id':c['case_id'],'mother':c['source'],'variant':c['variant'],'gold_frame':g,'gold_h':h,
                     'M1':actual,'ordinary_wrapper':baseline,'source_frame_candidate_exact':exact,
                     'same_predictions':actual['prediction']==baseline['prediction'],
                     'M1_pair_correct':actual['prediction']==h,'ordinary_pair_correct':baseline['prediction']==h})
    result={'captured_utc':program['captured_utc'],'evidence_type':program['evidence_type'],'new_model_calls':0,
            'induction_mothers':2,'regression_mothers':2,'cases':rows,
            'M1_correct':sum(r['M1_pair_correct'] for r in rows),
            'ordinary_wrapper_correct':sum(r['ordinary_pair_correct'] for r in rows),
            'candidate_exact_coverage':sum(r['source_frame_candidate_exact'] for r in rows),
            'same_underlying_source_program':ordinary==skill['selector'],
            'runtime_questions_issued':0,'M1_question_skill_validated':False,
            'new_binding_implementation_exists':True,'novelty_or_incremental_efficacy_established':False,'goal_complete':False}
    (REPORT/'M1_source_bound_program.json').write_text(json.dumps(program,ensure_ascii=False,indent=2)+'\n')
    (REPORT/'M1_source_bound_regression.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}))


if __name__=='__main__':main()
