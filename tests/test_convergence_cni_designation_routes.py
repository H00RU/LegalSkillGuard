from experiments.convergence_revision5_cni_designation_routes import (
    APPLIES, C, E, REQUIRES, compile_layouts, compose, consume_world, direct,
)


def test_rewritten_interface_retains_unknowns_and_uses_bound_routes():
    _, _, assets = compile_layouts()
    assert len(assets['fixed']['decoder']) == 9
    assert len(assets['synthesized']['decoder']) < 9
    assert consume_world({APPLIES: None, REQUIRES: True}, {}) == {'open_route': False, 'gated_route': None}


def test_one_unresolved_route_blocks_universal_but_linked_exception_survives():
    gated = {'open_route': False, 'gated_route': True}
    unresolved = {'open_route': None, 'gated_route': None}
    open_route = {'open_route': True, 'gated_route': False}
    anchors = [(1, 2), (1, 3)]
    assert compose([gated, unresolved], anchors, True)['answer'] is None
    assert compose([gated, gated], anchors, False)['answer'] is None
    assert compose([gated, gated], anchors, True) == {'answer': E, 'evidence': [1, 2, 3]}
    assert compose([gated, open_route], anchors, False) == {'answer': C, 'evidence': [1, 3]}


def test_direct_control_requires_marking_in_each_medium():
    lead = {'text': 'Confidential Information includes all information which'}
    case = {
        'anchors': [[1, 2], [1, 3]],
        'complete_routes': True,
        'anchor_spans': [[lead, {'text': '(a) if in writing, is marked as confidential, or'}],
                         [lead, {'text': '(b) if orally disclosed, is identified as confidential.'}]],
    }
    assert direct(case) == {'answer': E, 'evidence': [1, 2, 3]}
