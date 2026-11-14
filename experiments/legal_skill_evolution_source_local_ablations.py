"""Execute the learned source/G cross interventions on the existing eight mothers."""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_local_preview as preview
from legal_skill_guard.rr.checkpoint import immutable_json


current = preview.current
OUT = current.OUT / 'unbound_component_interventions'


def run():
    task = current.read(current.OUT / 'teacher_task.json')
    before = task['current_libraries']['ConstraintAcquire']
    after = current.read(current.OUT / 'unbound_proposed_execution/ConstraintAcquire/library.json')
    public = {s['key']: s for s in current.read(current.old.previous.prior.prior.PUBLIC)
              if s['dataset'] == 'ContractNLI'}
    grading = current.read(current.old.previous.prior.prior.GRADING)
    results = {}
    for variant in ('new_phi_old_G', 'old_phi_new_G'):
        library = deepcopy(after)
        if variant == 'new_phi_old_G':
            library['selected_rule_ids'] = before['selected_rule_ids']
        else:
            library['source_program'] = before['source_program']
        immutable_json(OUT / variant / 'library.json', library)
        rows = []
        for entry in task['tasks']:
            key = entry['source_id']
            path = OUT / variant / current.old.name_for(key)
            if path.exists():
                row = current.read(path)
            else:
                pub, units, _ = current.old.previous.prior.prior.source_material(current.old.previous.PARENT, public, key)
                upstream = current.read(current.old.OUT / 'upstream' / current.old.name_for(key))['source_output']
                observation = current.old.observe(preview.NoModel(), variant + ':' + key, key, library,
                    source_text=pub['source_text'], units=units, source_output=upstream)
                assert observation['new_model_requests'] == 0
                actual = current.old.previous.prior.prior.evaluate_source(library, observation, public[key], grading[key])
                row = {'source': key, 'actual': actual, 'observation': observation,
                    'correct': sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views']),
                    'unresolved': sum(not v['core_executed'] for v in actual['feedback']['views'])}
                immutable_json(path, row)
            rows.append({k: row[k] for k in ('source', 'correct', 'unresolved')})
        results[variant] = {'correct': sum(r['correct'] for r in rows), 'total': 32,
                            'unresolved': sum(r['unresolved'] for r in rows), 'rows': rows}
    immutable_json(OUT / 'result.json', {'variants': results, 'new_model_calls': 0,
        'same_native_consumer_and_upstream': True, 'actual_program_execution': True,
        'proposed_selection_not_a_new_fit_certificate': True, 'goal_complete': False})
    print(json.dumps({v: {k: x[k] for k in ('correct', 'total', 'unresolved')}
                      for v, x in results.items()}), flush=True)


if __name__ == '__main__':
    run()
