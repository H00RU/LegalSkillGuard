import json
from itertools import combinations

import pytest

from experiments.convergence_revision5_oe_scoped_forms import FIXED, FORMS, PORTS, RELATION, proof, worlds
from experiments.convergence_revision5_oe_scoped_forms_dev import contract, decode
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory


def task(quote):
    return ('CASES\nFacts:\nAda Martin (hereinafter the Debtor) filed for bankruptcy on 1/2/2024.\n'
            + quote + '\nOutput contract:\n')


def test_title_scope_binds_group_to_named_filer_without_upgrading_possession():
    text = task('Records show that Ada possesses a desk with a value of $20.00. '
                'Both a chair worth $40.00 and a lamp with a value of $15.00 belong to Martin.')
    count, inventory, _ = title_inventory(text)
    assert count == 1
    assert [(a['description'], a['filing_interest_established']) for a in inventory.values()] == [
        ('desk', None), ('chair', True), ('lamp', True)]


def test_title_scope_rejects_an_unresolved_holder():
    with pytest.raises(ValueError, match='outside the resolved filing group'):
        title_inventory(task('A desk appraised at $20.00 is the property of Morgan.'))


def test_title_factored_fixed_control_passes_same_facts_into_consumer():
    count, inventory, _ = title_inventory(task('Ada owns a vest worth $20.00.'))
    case = {'public': {'inventory': inventory}, 'debtor': count, 'family': 'EV',
            'truth': {'asset_1': (True, True, True)}}
    fixed, schema = contract(case, FIXED)
    scoped, _ = contract(case, RELATION)
    assert fixed[-1] == scoped[-1]
    assert set(schema['properties']['asset_1']['properties']) == set(PORTS[1:])
    residual = proof()['residuals']['EV']
    coordinates = {'asset_1': {p: True for p in PORTS[1:]}}
    relation = {'asset_1': ['wearing_apparel']}
    predictions = [decode(case, arm, {'finish_reason': 'stop', 'content': json.dumps(value)}, residual)
                   for arm, value in ((FIXED, coordinates), (RELATION, relation))]
    assert predictions[0]['raw'] == predictions[1]['raw']
    assert predictions[0]['raw']['vest']


def test_extra_form_coupling_retains_an_empty_completion_for_invariant_claims():
    for title in (False, True, None):
        expanded = 0
        for size in range(1, len(FORMS) + 1):
            for forms in combinations(FORMS, size):
                linked = worlds(title, forms)
                columns = ({row[index] for row in linked} for index in (1, 2))
                axes = tuple(next(iter(v)) if len(v) == 1 else None for v in columns)
                independent = worlds(title, fixed=(None, *axes))
                if linked != independent:
                    expanded += 1
                    assert forms == ('out_of_scope', 'wearing_apparel')
                    assert (False, False, False) in linked and (False, False, False) in independent
                    assert (title is True, True, True) in linked and (title is True, True, True) in independent
        assert expanded == 1
