from copy import deepcopy

from experiments import legal_skill_evolution_observation_library_train as train
from legal_skill_guard.skill_evolution.component_observation_execution import convert, naive_named_symbol_plan
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.sara_statute_kernel import current_case_interface


def test_external_component_selection_preserves_real_B8_lowering_exactly():
    public={s['key']:s for s in train.read(train.parent.OUT/'SARA_corrected_TRAIN_views.json')}
    kernels={r['source']:current_case_interface(r['kernel']) for r in train.read(train.parent.OUT/'SARA_native_kernel_bank.json')}
    checked=0
    for row in train.read(train.OUT/'B8/scored_results.json')['rows']:
        if 'grounded' not in row:
            continue  # A rejected schema is not fabricated into a converter input.
        library=train.read(train.OUT/'B8'/row['arm']/'library.json')
        pub=public[row['source']]['views'][0]['public']
        actual=convert(library,row['actual_component_ids'],kernels[row['source']],pub,
            deepcopy(row['observation']),literal_context=literal_bindings({'public':pub}))
        assert actual==row['grounded']
        checked+=1
    assert checked==5


def test_named_symbol_set_cover_reproduces_specialized_payment_scope_problem():
    # Existing real TRAIN query, not an invented benchmark or expected answer.
    library=train.read(train.OUT/'B8/ProgramGuided/library.json')
    row=next(r for r in train.read(train.parent.OUT/'SARA_native_kernel_bank.json') if r['kernel']['name']=='s63_c_6_A')
    naive=naive_named_symbol_plan(library,row['kernel'])
    assert 'termination_benefit_events' in naive['component_ids']
    assert 'payment_service_events' not in naive['component_ids']
    assert 'payment_' in naive['required_native_anchors']
    assert naive['not_a_learned_method_or_semantic_coverage_certificate']
