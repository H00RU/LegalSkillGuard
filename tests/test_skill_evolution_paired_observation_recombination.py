from experiments import legal_skill_evolution_mixed_component_training as training
from legal_skill_guard.skill_evolution.paired_observation_recombination import coordinate_candidates


def test_real_rejected_pair_recombines_existing_versions_without_schema_code_drift():
    old_root = training.ROOT / 'artifacts/legal_skill_evolution_mixed_component_training_source_review_20261115'
    base = training.actor.libraries()['CoverageRecombine/0']
    response = training.read(old_root / 'B1/CoverageRecombine/teacher.json')
    full = {'retained': base}
    for index, proposal in enumerate(response['value']['candidates']):
        full[str(index)] = training.actor.candidate_library(base, proposal)
    bank = coordinate_candidates(full)
    assert len(bank) > len(full)
    original_units = [c for lib in full.values() for c in lib['components']]
    old_family = next(c for c in base['components'] if c['id'] == 'family_relationship_residence')
    revised_givens = next(c for c in full['0']['components'] if c['id'] == 'explicit_legal_givens')
    assert any(old_family in lib['components'] and revised_givens in lib['components'] for lib in bank.values())
    for library in bank.values():
        assert library['shared_helpers'] == base['shared_helpers']
        assert all(component in original_units for component in library['components'])
