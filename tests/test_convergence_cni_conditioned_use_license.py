from experiments.convergence_revision5_cni_conditioned_use_license import overlay, specialize


def test_one_known_proposition_leaves_its_protected_status_readable():
    model, full = specialize(('purpose_scope',))
    assert len(model.states) == 81
    assert {role: len(asset['features']) for role, asset in full.items()} == {'fixed': 4, 'synthesized': 3}
    _, reduced = specialize(('purpose_scope',), preserve_status=False)
    assert {role: len(asset['features']) for role, asset in reduced.items()} == {'fixed': 3, 'synthesized': 2}


def test_two_known_labels_do_not_determine_two_protected_statuses():
    tasks = ('purpose_scope', 'no_rights_grant')
    model, full = specialize(tasks)
    assert len(model.states) == 9
    assert all(len(v['features']) == 2 for v in full.values())
    _, native_only = specialize(tasks, preserve_status=False)
    assert native_only == {'fixed': None, 'synthesized': None}


def test_common_source_overlay_keeps_the_unresolved_question_with_the_reader():
    before = {'purpose_scope': {'answer': None, 'evidence': []},
              'no_rights_grant': {'answer': 'NotMentioned', 'evidence': []}}
    proof = {'purpose_scope': (4, 6)}
    assert overlay(before, proof) == {'purpose_scope': {'answer': 'Entailment', 'evidence': [4, 6]},
                                     'no_rights_grant': before['no_rights_grant']}
    assert before['purpose_scope']['answer'] is None
