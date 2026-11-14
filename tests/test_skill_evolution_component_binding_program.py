from experiments import legal_skill_evolution_observation_component_execute as execution
from legal_skill_guard.skill_evolution.case_observation_contract import apply_adapter
from legal_skill_guard.skill_evolution.component_binding_program import binding_program
from legal_skill_guard.skill_evolution.observation_component_library import convert


def test_compiled_traced_adapter_preserves_actual_model_observations():
    public = {s['key']: s for s in execution.read(
        execution.acquisition.previous.parent.OUT / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: execution.acquisition.current_case_interface(r['kernel'])
        for r in execution.read(execution.acquisition.previous.parent.OUT / 'SARA_native_kernel_bank.json')}
    libraries = execution.libraries()
    cases = []
    for path in (execution.OUT / 'acquisition').rglob('*.json'):
        row = execution.read(path)
        if 'grounded' in row and 'observation' in row:
            cases.append(row)
    assert len(cases) >= 8
    for row in cases:
        sid = row['source']
        library, ids = libraries[row['candidate']], row['plan']['component_ids']
        kernel, case = kernels[sid], public[sid]['views'][0]['public']
        contract = {'binding_program': binding_program(library, ids)}
        traced_input = apply_adapter(contract, kernel, case, row['observation'], literal_context={})
        assert traced_input == convert(library, ids, kernel, case, row['observation'])
