from types import SimpleNamespace

from experiments import legal_skill_evolution_observation_component_execute as actor


def test_existing_pure_statute_certificate_bypasses_empty_observation_without_learning_credit(tmp_path):
    bank = actor.read(actor.acquisition.previous.parent.OUT / 'SARA_native_kernel_bank.json')
    entry = next(r for r in bank if r['kernel']['name'] == 's63_c_7_ii')
    kernel = actor.acquisition.current_case_interface(entry['kernel'])
    source = next(s for s in actor.read(actor.acquisition.previous.parent.OUT / 'SARA_corrected_TRAIN_views.json')
        if s['key'] == entry['source'])
    # This client deliberately has no generate/tokenize method. The existing
    # fact-independent certificate, not a guessed source witness, must suffice.
    client = SimpleNamespace(artifacts=tmp_path)
    library = actor.libraries()['CoverageRecombine/0']
    row = actor.execute_one(client, {'shared_public_pure_calculation': True}, 'same_public_path',
        library, entry['source'], kernel, source, 'TRAIN')
    assert row['execution']['handled'] and row['reads'] == []
    assert row['not_learned_observation_success'] is True
    assert row['grounded']['bindings'][0]['witnesses'] == []
