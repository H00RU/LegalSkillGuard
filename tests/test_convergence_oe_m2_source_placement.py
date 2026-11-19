from itertools import product

from experiments.convergence_revision5_oe_m2_source_placement import (
    compile_edit, direct_title_scope, title_conditional_support,
)
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory


def test_title_direction_keeps_only_source_supported_conflicts():
    assert not title_conditional_support(False, True, True, None)
    assert title_conditional_support(False, True, None, True)
    assert all(title_conditional_support(*state) == direct_title_scope(*state)
               for state in product((None, True, False), repeat=4))


def test_edit_changes_the_amount_in_the_disclosed_group_only():
    source = (
        'Task\nStatutes:\n11 U.S.C. § 522(d)(3); 42 Pa. Cons. Stat. § 8123.\n'
        'Solved Reasoning Steps:\nThe Debtor may claim property exemptions under Federal and Pennsylvania statutes.\n'
        'Facts:\nAda Martin (hereinafter the Debtor) filed for bankruptcy on 1/2/2024.\n'
        'Ada has disclosed ownership of assets, including a chair ($14.00), a desk ($20.00), and a lamp ($40.00).'
        '\nOutput contract:\n')
    _, assets, receipts = title_inventory(source)
    edit = compile_edit('train-source', 'EV', source, 'asset_2', assets, receipts)
    base, updated = edit['cases']
    assert base.public['asset'] == updated.public['asset'] == 'desk'
    assert updated.public['text'] == source.replace('$20.00', '$21.00')
    assert base.root_id == updated.root_id and base.law_scope == updated.law_scope
    assert edit['receipt']['shared_signatures'] == 2 and edit['receipt']['independent_signatures'] == 4
