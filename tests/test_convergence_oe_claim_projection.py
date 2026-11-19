from experiments.convergence_revision5_oe_claim_projection import anchor_leading_articles, claim_projection, span_names
from legal_skill_guard.paired_interfaces.asset_interfaces import frozen_skill
from legal_skill_guard.paired_interfaces.program_residual import specialize
from tests.test_convergence_oe_asset_projection import case


def test_article_case_requires_unique_same_unit_and_an_exact_body():
    text = 'A desk and a bike worth $40.00 are listed near a desk and a desk.'
    rows = [{'unit_id': i, 'quote': q} for i, q in [
        (0, 'A bike worth $40.00'), (0, 'A bike worth $50.00'), (1, 'A bike worth $40.00'),
        (0, 'a Desk'), (0, 'A DESK')]]
    result, count = anchor_leading_articles({'assets': rows}, [{'id': 0, 'text': text}])
    assert count == 1
    assert result['assets'] == [{**rows[0], 'quote': 'a bike worth $40.00'}, *rows[1:]]


def test_span_binding_trims_only_the_assets_own_literal_valuation():
    quote = 'A desk appraised at $20.00 and a bike worth $40.00 are owned by both debtors.'
    inventory = {'a': {'description': 'desk', 'source_quote': quote, 'amount_quote': '$20.00'},
                 'b': {'description': 'bike', 'source_quote': quote, 'amount_quote': '$40.00'}}
    def row(name):
        return {'quote': quote, 'fields': {'asset_descriptions': {'value': name, 'status': 'stated'}}}
    names = ['A desk appraised at $20.00', 'A bike worth $40.00', 'A desk appraised at $40.00',
             'desk and bike']
    result = span_names({'assets': list(map(row, names))}, inventory)
    assert [r['fields']['asset_descriptions']['value'] for r in result['assets']] == [
        'desk', 'bike', names[2], names[3]]


def test_claimwise_consumer_keeps_the_invariant_claim_and_withholds_unknown_eligibility():
    plan, record, _, _ = case()
    skill = frozen_skill()
    plan['public_context'] = {'governing_regime': 'Federal and Pennsylvania'}
    context = {**plan['public_context'], 'output_family': 'EC'}
    residual = specialize(skill['procedure'], context, allowed_context_fields=set(context))
    plan.update(residual_program=residual, residual_required_fields=residual['input_fields'])
    fields = record['assets'][0]['fields']
    fields['asset_is_personal_tangible_property'] = {'value': None, 'status': 'unknown'}
    fields['asset_is_wearing_apparel'] = {'value': False, 'status': 'negated'}
    fields['asset_is_personal_nonbusiness_property'] = {'value': True, 'status': 'stated'}
    plan['array_fields'] = sorted(fields)
    whole, claims = claim_projection(plan, {**record, 'assets': record['assets'][:1]}, 'EC', skill)
    assert whole == {}
    assert claims == {'desk': [skill['premises']['pennsylvania_general_property_citation']['value']]}
