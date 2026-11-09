"""Can a fixed error operator explain each existing original/edit trajectory?

Satisfiability audit only. No refit, prediction claim, output repair or model
call. Composed operand/unknown operations are error descriptions, not a relaxed
semantic acceptance rule.
"""
from itertools import product
import json
from legal_skill_guard.rr.semantic_learning import OPS, transform
from experiments.rr_v2_semantic_learning import REPORT,STAGE,read,check_frozen


GRAMMAR=[{'source_role':source,'transfer':transfer} for source in (0,1)
         for transfer in ('identity','negate','unknown_as_false','unknown_as_true')]
GRAMMAR.append({'source_role':None,'transfer':'erase'})


def value(h,program):
    if program['transfer']=='erase':return 2
    v=h[program['source_role']]
    if program['transfer']=='negate':return 1-v if v!=2 else 2
    if program['transfer']=='unknown_as_false':return 0 if v==2 else v
    if program['transfer']=='unknown_as_true':return 1 if v==2 else v
    return v


def main():
    f=check_frozen();train=f['training_rows'];held=read(REPORT/'M1M2_real_TRAIN_results.json')['rows'];rows=[]
    for mother in sorted({r['mother'] for r in train+held}):
        trajectory=[r for r in train+held if r['mother']==mother]
        old=[list(op) for op in OPS if all(transform(r['h'],op)==r['y'] for r in trajectory)]
        minimum=min((sum(v!='self' for v in op) for op in old),default=None)
        extended=[]
        for i in range(4):
            extended.append([p for p in GRAMMAR if all(value(r['h'],p)==r['y'][i] for r in trajectory)])
        count=1
        for supported in extended:count*=len(supported)
        rows.append({'mother':mother,'fold':'induction' if any(r['mother']==mother for r in train) else 'previously_observed_excluded',
                     'cases':[{'case_id':r['case_id'],'h':r['h'],'y':r['y']} for r in trajectory],
                     'old_grammar_fixed_channel_count':len(old),'old_grammar_minimum_edits':minimum,
                     'old_grammar_minimal_channels':[op for op in old if sum(v!='self' for v in op)==minimum],
                     'compositional_fixed_channel_count':count,'compositional_slot_version_spaces':extended,
                     'time_varying_channel_required_by_these_class_labels':False if count else None})
    out={'new_model_calls':0,'evidence_type':'Post-hoc class-level satisfiability on existing real trajectories, not predictive validation',
         'rows':rows,'compositional_primitive_grammar':GRAMMAR,
         'new_statistical_model_fitted':False,'frozen_models_unchanged':True,'semantic_acceptance_checks_unchanged':True,
         'finding':'Both induction trajectories admit fixed operators already in the frozen grammar. The apparent TRAIN79 mode change can be a fixed negate-payment class map with unknown propagation.',
         'missing_composition_example':'TRAIN83 has no fixed operator in the original grammar, but reading the other role then mapping unknown to false explains the previously unsupported slot; this is a missing composition, not evidence requiring a new time-varying mechanism.',
         'decision':'Do not build a transition-model framework or buy additional calls based only on observed output changes. Whole source-binding/reporting behavior remains a separate unresolved question.',
         'goal_complete':False}
    (REPORT/'M2_channel_transport_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'new_calls':0,'counts':[{'cases':[c['case_id'] for c in r['cases']],
        'old_fixed':r['old_grammar_fixed_channel_count'],'composed_fixed':r['compositional_fixed_channel_count']} for r in rows],
        'time_varying_channel_implementation_justified':False}))


if __name__=='__main__':main()
