"""Offline identification audit on existing observations, not synthetic trials."""
import json
from legal_skill_guard.rr.semantic_learning import OPS, transform
from experiments.rr_v2_semantic_learning import STAGE, REPORT, read, check_frozen


def explanations(h,y):
    matching=[op for op in OPS if transform(h,op)==y]
    edits=min(sum(v!='self' for v in op) for op in matching)
    return edits,[list(op) for op in matching if sum(v!='self' for v in op)==edits]


def main():
    f=check_frozen();data=read(REPORT/'M1M2_real_TRAIN_results.json');rows=[]
    for r in f['training_rows']:
        if r['y']==r['h']*2:continue
        edits,operators=explanations(r['h'],r['y'])
        rows.append({'case_id':r['case_id'],'h':r['h'],'y':r['y'],
                     'minimum_edits':edits,'equally_simplest_explanations':operators,
                     'count':len(operators),'unique_operator_identified':len(operators)==1})
    # A real excluded observation refutes a particular explanation of the
    # training R error. This is diagnosis, not an allowed refit/second test.
    held=next(r for r in data['rows'] if r['case_id']=='TRAIN88:controlled')
    competing={name:transform(held['h'],op) for name,op in {
        'R.medium_reads_work':('self','self','self','other'),
        'R.medium_negates_medium':('self','self','self','negate_self')}.items()}
    out={'new_model_calls':0,'all_values_from_existing_real_TRAIN':True,'induction_error_explanations':rows,
         'excluded_diagnostic':{'case_id':held['case_id'],'h':held['h'],'observed':held['y'],
               'frozen_training_R_error_alternative_predictions':competing,
               'used_to_refit':False},
         'M1_gap':'Frozen program uses R.work to emit medium constants. It never executes the teacher-proposed material question or constrains source-role bindings; identical ordinary tree absorbs it.',
         'M2_gap':'Training role-copy and polarity alternatives can predict the same real error. More repetitions of the same h/y do not identify the operator. Need an actually distinguishing observation, not a renamed template or a forced anchor.',
         'decision':'No unchanged requests or wider build justified by this pilot. Preserve the two designs; require a concrete source-grounded question/learning difference before another finite validation.',
         'goal_complete':False}
    (REPORT/'M1M2_identification_gap.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'ambiguities':[(r['case_id'],r['count']) for r in rows],
                      'existing_excluded_diagnostic':out['excluded_diagnostic'],'new_calls':0}))


if __name__=='__main__':main()
