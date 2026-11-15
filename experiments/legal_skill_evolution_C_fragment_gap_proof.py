"""Prove the measured disclosure coverage gap inside the frozen positive G.

No new reading and no benchmark change. With positive derived dependencies,
the maximal rule set bounds every subset. A missing possible output in that
maximal program cannot be recovered by reweighting or selecting old rules.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_C_fragment_update as prior
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import execute


def run():
    library=prior.read(prior.OUT/'C/selected_before_reuse.json')['library']
    original=deepcopy(library);language=library['language']
    assert all(atom['sign']=='positive'or language['signatures'][atom['predicate']]['kind']=='observed'
        for rule in language['rules']for atom in rule['body'])
    library['selected_rule_ids']=[r['id']for r in language['rules']]
    disclosure_outputs={r['predicate']for r in library['renderers']
        if r['term'][0]in ('permission','prohibition','complete_source_no_disclosure_permission')}
    protocol=prior.read(prior.OUT/'protocol.json');rows=[]
    for sid in protocol['fixed_reuse_sources']:
        obs=prior.read(prior.OUT/'C/observations'/(digest(sid)+'.json'))
        actual=execute(library,obs)['composition']
        assert actual['status']=='sat'and actual['complete']
        possible=[r for r in actual['possible_outputs']if r['predicate']in disclosure_outputs]
        choices={q['id']:q['operation']for q in obs['visible_inputs']['queries']}
        modes=[{'id':a['id'],'actual_choice':a['choice']}for a in obs['visible_inputs']['answers']
            if choices[a['id']]=='disclosure_modality']
        rows.append({'source':sid,'maximal_rule_count':len(language['rules']),
            'subset_count_bounded':2**len(language['rules']),'exact_solver_complete':True,
            'possible_disclosure_outputs':possible,'no_old_subset_can_emit_disclosure':not possible,
            'actual_modality_answers':modes,'not_a_global_model_impossibility_claim':True})
    immutable_json(prior.OUT/'C/maximal_disclosure_gap_proof.json',{'rows':rows,
        'monotonicity_basis':'positive heads and derived dependencies; explicit observed negatives fixed',
        'source_library_sha256':digest(original),'new_model_requests':0,'goal_complete':False})
    print(json.dumps([{'source':r['source'],'old_subsets_bounded':r['subset_count_bounded'],
        'gap_proven':r['no_old_subset_can_emit_disclosure']}for r in rows]),flush=True)


if __name__=='__main__':run()
