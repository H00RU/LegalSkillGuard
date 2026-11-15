"""C interventions on the same paid frozen-source reads, with no model client."""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_C_scope_runtime as current
from legal_skill_guard.rr.checkpoint import immutable_json


def run():
    p=current.protocol()
    frozen=current.read(current.OUT/'C/selected_before_reuse.json')
    library=frozen['library']
    uncoupled=deepcopy(library)
    for rule in uncoupled['language']['rules']:
        rule['body']=[atom for atom in rule['body']if atom['predicate']!='fragment_query']
    old=current.read(current.retained.OUT/'C/selected_before_reuse.json')['library']
    nofit=deepcopy(library)
    nofit['selected_rule_ids']=current.read(current.OUT/'C/candidate.json')['selected_rule_ids']
    rows=[]
    for sid in p['fixed_reuse_sources']:
        raw=current.read(current.OUT/'C/raw_observations'/(current.digest(sid)+'.json'))
        observation=current.convert(library,raw)
        old_observation=current.g.program_concepts(old,raw)
        row={'source':sid,'Full':current.g.assess(library,observation,sid),
            'NoClauseBinding':current.g.assess(uncoupled,observation,sid),
            'NoFitSameSelectedProgram':current.g.assess(nofit,observation,sid),
            'PreviousFrozenLibrary':current.g.assess(old,old_observation,sid),
            'same_actual_neural_readings':True,'new_model_requests':0}
        immutable_json(current.OUT/'C/causal_attribution_rows'/(current.digest(sid)+'.json'),row)
        rows.append(row)
        print(json.dumps({'source':sid,'scores':{k:row[k]['native_correct']
            for k in ('Full','NoClauseBinding','NoFitSameSelectedProgram','PreviousFrozenLibrary')}}),flush=True)
    immutable_json(current.OUT/'C/causal_attribution.json',{'rows':rows,'new_model_requests':0,
        'interventions_not_claimed_as_new_generated_observations':True,'goal_complete':False})


if __name__=='__main__':run()
