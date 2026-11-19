from legal_skill_guard.paired_interfaces import convergence_oe_pa_monetary as pa
from legal_skill_guard.skill_evolution.objects import digest


def view(task, instructions=''):
    text = f'{instructions}\nStatutes:\n{pa.CITATION}\nreviewed clause\nSolved Reasoning Steps:\n'
    return {'id': task, 'public': {'original_input': text}}


def scope(monkeypatch, filers):
    monkeypatch.setattr(pa, 'RULE_SHA256', digest('reviewed clause'))
    monkeypatch.setattr(pa, 'supplied_jurisdiction_scope', lambda _: {'citations': [pa.CITATION]})
    inventory = {'a': {'description': 'first asset', 'filing_interest_established': True,
                       'amount_quote': '$423.00'},
                 'b': {'description': 'second asset', 'filing_interest_established': None,
                       'amount_quote': '$717.00'}}
    monkeypatch.setattr(pa, 'title_inventory', lambda _: (filers, inventory, {}))


def test_positive_single_filer_requires_title_and_exact_fresh_valuation_scope(monkeypatch):
    scope(monkeypatch, 1)
    assert pa.claims(view('EV')) == {}
    assert pa.claims(view('EC')) == {'first asset': 300.0}
    assert pa.claims(view('EV', pa.EV_SCOPE)) == {'first asset': 300.0}
    v = view('EC')
    v['public']['original_input'] = v['public']['original_input'].replace('reviewed clause', 'added condition')
    assert pa.claims(v) == {}


def test_joint_cap_requires_shared_source_assumption_and_replaces_only_its_claim(monkeypatch):
    scope(monkeypatch, 2)
    assert pa.claims(view('EC')) == {}
    new = pa.claims(view('EV', pa.EV_SCOPE + '\n' + pa.JOINT_FACTS))
    assert new == {'first asset': 423.0, 'second asset': 600.0}
    wrong = {'citation': pa.CITATION, 'claim_value': 100.0}
    other = {'citation': 'other statute', 'claim_value': 85.0}
    original = {'first asset': [wrong, other]}
    answer = pa.apply('EV', original, new)
    assert original == {'first asset': [wrong, other]}
    assert answer == {'first asset': [other, {'citation': pa.CITATION, 'claim_value': 423.0}],
                      'second asset': [{'citation': pa.CITATION, 'claim_value': 600.0}]}
