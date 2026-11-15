"""Separate retained neural and learned raw-source concepts on paid TRAIN data.

No model client or new source. This diagnoses the actual 11 corrections and
10 regressions, not a new full matrix or a selected deployable policy.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_C_TRAIN_runtime as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_effect_update import function_update

ROOT=current.ROOT
OUT=ROOT/'artifacts/legal_skill_evolution_C_reader_branch_attribution_20261115'


def run():
    library=current.read(ROOT/'artifacts/legal_skill_evolution_C_TRAIN_fit_owner_scope_20261115/selected.json')['library']
    p=current.read(current.OUT/'protocol.json')
    results={}
    for label,function in [('RetainedNeural','legal_neural'),('LearnedRaw','legal_raw')]:
        variant=deepcopy(library)
        apply='''def apply(inputs,premises):
    queries=[]
    answers=[]
    fragments=[]
    unresolved=[]
    FUNCTION(inputs,queries,answers,fragments,unresolved)
    return {'queries':queries,'answers':answers,'fragments':fragments,'unresolved':unresolved}
'''.replace('FUNCTION',function)
        variant['source_concept_program']=function_update(variant['source_concept_program'],[apply])
        immutable_json(OUT/label/'candidate.json',variant);rows=[]
        for sid in p['sources']:
            path=OUT/label/'rows'/(digest(sid)+'.json')
            if path.exists():row=current.read(path)
            else:
                raw=current.read(current.OUT/'C/raw_observations'/(digest(sid)+'.json'))
                observation=current.convert(variant,raw)
                row=current.assess(variant,observation,sid);immutable_json(path,row)
            rows.append(row)
        results[label]={'native_correct':sum(r['native_correct']for r in rows),'native_total':96,
            'source_failures':[r['source']for r in rows if not r['hard_source_pass']],
            'unresolved':sum(r['unresolved']for r in rows)}
        print(json.dumps({'condition':label,**results[label]}),flush=True)
    immutable_json(OUT/'result.json',{'conditions':results,'Full_C':{'native_correct':71,'native_total':96},
        'same_G_and_actual_neural_reads':True,'new_model_calls':0,'not_a_deployable_selected_policy':True,
        'only_original_24_TRAIN':True,'DEV_TEST_accessed':False,'goal_complete':False})


if __name__=='__main__':run()
