"""Recover equivalent parse annotations in the existing fixed TRAIN reuse.

No model call and no native answer is used. Original observed world/source
fields and the acquired converter's strict checks remain unchanged.
"""
import hashlib
from pathlib import Path

from experiments import legal_skill_evolution_mixed_component_training as train
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.observation_component_library import component_value
from legal_skill_guard.skill_evolution.observation_scope_normalization import normalize

ROOT = train.ROOT
INPUT = ROOT / 'artifacts/legal_skill_evolution_family_guard_validation_union_fix_20261115'
OUT = ROOT / 'artifacts/legal_skill_evolution_residence_scope_recovery_20261115'
CID = 'family_relationship_residence'


def run():
    read = train.read
    bank = train.actor.acquisition.previous.parent.OUT
    public = {s['key']: s for s in read(bank / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: train.actor.acquisition.current_case_interface(r['kernel'])
        for r in read(bank / 'SARA_native_kernel_bank.json')}
    selected = read(INPUT / 'selected.json')['selected']
    results = {}
    for arm, name in selected.items():
        library = read(INPUT / 'candidate_libraries' / (name + '.json'))
        component = next(c for c in library['components'] if c['id'] == CID)
        case = next(read(p) for p in (INPUT / 'family_results' / name).glob('*.json')
            if read(p)['source'].startswith('SARA_v2_Binary:5c29'))
        sid = case['source']
        assert public[sid]['split'] == 'train'
        observation, receipts = normalize(library, kernels[sid], public[sid]['views'][0]['public'], case['value'])
        parts = [component_value(library, component, kernels[sid], public[sid]['views'][0]['public'], view)
            for view in observation[CID]['views']]
        result = {'source': sid, 'old': case, 'adapted_observation': observation,
            'receipts': receipts, 'parts': parts, 'new_model_calls': 0,
            'original_program_schema_and_checks_unchanged': True,
            'not_a_new_teacher_update_or_independent_method_gain': True,
            'full_native_case_not_evaluated': True}
        immutable_json(OUT / arm / 'result.json', result)
        results[arm] = {'before_complete': case['complete_alternatives'],
            'after_complete': all(p['complete'] for p in parts), 'normalizations': len(receipts),
            'facts': [p['facts'] for p in parts]}
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/observation_scope_normalization.py',
        ROOT / 'experiments/legal_skill_evolution_observation_component_execute.py']
    immutable_json(OUT / 'result.json', {'results': results, 'new_model_calls': 0,
        'native_answers_DEV_TEST_not_loaded': True, 'same_public_recovery_both_arms': True,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'not_a_full_case_reuse_or_contribution_certificate': True, 'goal_complete': False})
    for p in files:
        target = OUT / 'source_snapshot' / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(p.read_bytes())
    print({a: {k: v for k, v in r.items() if k != 'facts'} for a, r in results.items()})


if __name__ == '__main__':
    run()
