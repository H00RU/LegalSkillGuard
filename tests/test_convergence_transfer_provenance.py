from experiments.convergence_b8_transfer import _mask
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.skill_evolution.objects import digest


def test_transfer_mask_removes_programs_learned_exclusively_outside_the_target():
    initial = {'programs': {'target': 'baseline_target', 'other': 'baseline_other',
                            'mixed': 'baseline_mixed', 'shared': 'no_new_training'}}
    programs = {'target': 'learned_target', 'other': 'learned_other', 'mixed': 'learned_jointly',
                'shared': 'no_new_training'}
    origins = {name: {'artifact_sha256': digest(programs[name]), 'training_datasets': datasets}
               for name, datasets in {'target': ['target'], 'other': ['other'],
                                      'mixed': ['target', 'other'], 'shared': []}.items()}
    observations = [{'dataset': 'target', 'source': 'a'}, {'dataset': 'other', 'source': 'b'}]
    interface = sealed({'visible_prefix': ['a', 'b'], 'observations': observations}, 'snapshot_sha256')
    library = sealed({'programs': programs, 'interface_library': interface}, 'snapshot_sha256')

    result = _mask(library, initial, {'a': 'target', 'b': 'other'}, origins, 'target')

    assert result['programs'] == {**programs, 'other': 'baseline_other'}
    assert result['interface_library']['observations'] == observations[:1]
    assert result['interface_library']['visible_prefix'] == ['a']
    verify(result['interface_library'], 'snapshot_sha256')
    verify(result, 'snapshot_sha256')
