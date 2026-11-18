from experiments.convergence_oe_natural_relation import build_natural_group
from experiments.convergence_oe_conditioned_value_probe import _condition
from experiments.convergence_oe_title_partition_probe import crossed_groups, joint_group
from legal_skill_guard.paired_interfaces.convergence_oe_title_value import compile_title_value
from legal_skill_guard.paired_interfaces.shared_semantics import matches_assertions


def test_both_component_orientations_retain_one_unknown_title_across_four_queries():
    text = 'A debtor possesses a bicycle appraised at $900.00.'
    literal = '$900.00'
    start = text.index(literal)
    source = {'key': 'OpenExempt:fixture', 'views': [{'id': 'EC', 'public': {'original_input': text}}]}
    natural = build_natural_group(source, 'a' * 64, 'bicycle', (start, start + len(literal)), 900)
    original = compile_title_value(natural)
    groups = crossed_groups(original)
    pair = [{'ownership': None, 'stated_value': 900, 'title_filtered_value': 0},
            {'ownership': None, 'stated_value': 1000, 'title_filtered_value': 1000}]
    zeros = [{**row, 'title_filtered_value': 0} for row in pair]
    for group in groups.values():
        assert [case.public for case in group['cases']] == [case.public for case in original['cases']]
        assert any(matches_assertions(pair, signature) for signature in group['shared']['signatures'].values())
        assert any(matches_assertions(zeros, signature) for signature in group['independent']['signatures'].values())
        assert not any(matches_assertions(zeros, signature) for signature in group['shared']['signatures'].values())
    joint = joint_group(groups)
    assert any(matches_assertions(pair + pair, sig) for sig in joint['independent']['signatures'].values())
    assert not any(matches_assertions(pair + pair, sig) for sig in joint['shared']['signatures'].values())
    _, shared, independent = _condition(joint)
    for mode, projected in (('shared', shared), ('independent', independent)):
        original_values = {tuple(row['title_filtered_value'] for row in rows)
                           for rows in joint[mode]['signatures'].values()}
        assert original_values == {tuple(rows) for rows in projected['signatures'].values()}
