import jsonschema
import pytest

from legal_skill_guard.openexempt import answer_schema
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import with_ev_inventory
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_schema_control import ReversibleWire
from legal_skill_guard.skill_evolution.native import answer_wire_schema, decode_answer


FEDERAL = '11 U.S.C. § 522(d)(3)'
WISCONSIN = 'Wis. Stat. § 815.18(3)(d)'
OREGON = 'Or. Rev. Stat. § 18.345(1)(f)'
PUBLIC_INPUT = (
    f'Question\nStatutes:\n{FEDERAL}\n{WISCONSIN}\n{OREGON}\n\nSolved Reasoning Steps:\n'
    'The Debtor may claim property exemptions under Federal and Wisconsin statutes.\n\n'
    'Facts:\nA valuation of $500.00 has been assigned to the table owned by the debtor.\n\n'
    'Output contract: Provide the asset claim plan.'
)


def test_oe_scope_binds_exact_resolved_jurisdictions_for_both_views():
    views = [{'id': family, 'public': {'original_input': PUBLIC_INPUT},
              'answer_schema': answer_schema(family)} for family in ('EC', 'EV')]
    source = {'dataset': 'OpenExempt', 'views': views}
    legacy = with_ev_inventory(source)
    bounded = with_ev_inventory(source, jurisdiction_scope=True)
    assert all('supplied_jurisdiction_scope' not in v['public'] for v in legacy['views'])
    assert [v['public']['original_input'] for v in bounded['views']] == [PUBLIC_INPUT, PUBLIC_INPUT]
    expected_citations = {'citations': [FEDERAL, WISCONSIN],
                          'premise': 'The Debtor may claim property exemptions under Federal and Wisconsin statutes.'}
    assert [v['public']['supplied_jurisdiction_scope'] for v in bounded['views']] == [expected_citations] * 2
    ec, ev = bounded['views']
    original_ec = {'answer': [{'asset': 'table', 'claims': [FEDERAL]}], 'evidence_sentence_ids': []}
    assert decode_answer('OpenExempt', ec, original_ec) == ({'table': [FEDERAL]}, [])
    wrong_ec = {'answer': [{'asset': 'table', 'claims': [OREGON]}], 'evidence_sentence_ids': []}
    with pytest.raises(jsonschema.ValidationError):
        decode_answer('OpenExempt', ec, wrong_ec)
    ev_schema = answer_wire_schema('OpenExempt', ev)
    aliases = {'field_aliases': [{'original': 'claim_value', 'alias': 'amount'}], 'fields_first': ['claim_value']}
    codec = ReversibleWire(ev_schema, aliases)
    native_ev = {'citation': WISCONSIN, 'claim_value': 500}
    ev_wire = {'answer': {'asset_1': [native_ev]}, 'evidence_sentence_ids': []}
    assert decode_answer('OpenExempt', ev, codec.restore(codec.encode(ev_wire))) == ({'table': [native_ev]}, [])
    wrong_ev = {'answer': {'asset_1': [{'citation': OREGON, 'claim_value': 500}]}, 'evidence_sentence_ids': []}
    with pytest.raises(jsonschema.ValidationError):
        codec.encode(wrong_ev)


@pytest.mark.parametrize('ambiguous', [
    PUBLIC_INPUT.replace('Federal and Wisconsin', 'Federal and Virginia'),
    PUBLIC_INPUT.replace(WISCONSIN + '\n', ''),
    PUBLIC_INPUT.replace('Facts:\n', 'The Debtor may claim property exemptions under Oregon statutes.\nFacts:\n'),
    PUBLIC_INPUT.replace('Solved Reasoning Steps:', 'Unsolved Questions:'),
])
def test_oe_scope_uses_original_wire_without_an_unambiguous_premise(ambiguous):
    assert supplied_jurisdiction_scope(ambiguous) is None
    original = {'id': 'EC', 'public': {'original_input': ambiguous}, 'answer_schema': answer_schema('EC')}
    enriched, = with_ev_inventory({'dataset': 'OpenExempt', 'views': [original]},
                                   jurisdiction_scope=True)['views']
    assert enriched == original


def test_oe_scope_rejects_modified_bound_citations():
    forged = supplied_jurisdiction_scope(PUBLIC_INPUT)
    forged['citations'].append(OREGON)
    view = {'id': 'EV', 'public': {'original_input': PUBLIC_INPUT, 'supplied_jurisdiction_scope': forged},
            'answer_schema': answer_schema('EV')}
    with pytest.raises(ValueError, match='original public premise'):
        answer_wire_schema('OpenExempt', view)
