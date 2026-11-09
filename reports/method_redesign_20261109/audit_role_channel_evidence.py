"""Check whole-role bundle copying against real labels AND reported spans.

This audits a stricter observable hypothesis, not the model's private reasoning.
Reported evidence can itself be wrong, so it is never a trusted semantic anchor.
"""
import json
from legal_skill_guard.rr.semantic_frames import frame_vector,reader_vector
from experiments.rr_v2_semantic_learning import STAGE,REPORT,read,annotations,response


def alignment(quote,frame):
    if quote is None:return {'roles':[],'missing':True,'ambiguous':False}
    roles=[role for role in ('work_activity','payment_medium') if frame[role] is not None and frame[role] in quote]
    return {'roles':roles,'missing':False,'ambiguous':len(roles)!=1}


def main():
    seal=read(STAGE/'seal.json');gold=annotations(seal,'induction');rows=[]
    for c in seal['cases']:
        if c['fold']!='induction':continue
        frame=gold[c['case_id']]['frame'];h=frame_vector({'values':frame})
        for mode in ('direct','reader'):
            values=response(c,mode)['validation']['decoded']['values']
            labels=(frame_vector if mode=='direct' else reader_vector)({'values':values})
            for i,role in enumerate(('work_activity','payment_medium')):
                evidence=values[role] if mode=='direct' else values['evidence_work' if i==0 else 'evidence_medium']
                a=alignment(evidence,frame);other=('payment_medium','work_activity')[i]
                copied_label=labels[i]==h[1-i]
                whole_copy=copied_label and (other in a['roles'] or (frame[other] is None and evidence is None))
                rows.append({'case_id':c['case_id'],'mother':c['source'],'reader':mode,'role':role,
                    'h':h,'observed_class':labels[i],'class_wrong':labels[i]!=h[i],
                    'reported_evidence':evidence,'alignment':a,
                    'other_role_class_matches':copied_label,'whole_bundle_copy_possible':whole_copy,
                    'own_role_span_reported':role in a['roles'],
                    'source_span_membership_is_not_semantic_proof':True})
    errors=[r for r in rows if r['class_wrong']]
    out={'new_model_calls':0,'induction_mothers':2,'real_output_fields':len(rows),'class_error_fields':len(errors),
         'error_fields_whose_labels_also_match_other_role':sum(r['other_role_class_matches'] for r in errors),
         'error_fields_compatible_with_observable_whole_bundle_copy':sum(r['whole_bundle_copy_possible'] for r in errors),
         'rows':rows,
         'whole_bundle_copy_counterexample':'TRAIN71:controlled direct work reports the correct domestic-service span but the wrong true class. A transformation copying both the other role value and its source span does not produce this observed bundle.',
         'mixed_reporting_counterexample':'TRAIN79:controlled reader work has the correct false class but evidence only for the payment role. The medium has a wrong false class and work-role evidence. A single whole-pair swap does not explain both labels and evidence.',
         'interpretation':'The frozen four-label model measures class-level transformations. It does not establish a source-binding-copy mechanism or cognitive cause. Richer citation/reporting error remains possible; observed spans cannot be promoted to anchors.',
         'model_refit_or_old_results_changed':False,'goal_complete':False}
    (REPORT/'M2_role_bundle_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ('rows','whole_bundle_copy_counterexample','mixed_reporting_counterexample','interpretation')}))


if __name__=='__main__':main()
