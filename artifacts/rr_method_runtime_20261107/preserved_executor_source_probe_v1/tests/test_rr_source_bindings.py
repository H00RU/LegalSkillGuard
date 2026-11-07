"""Actual multi-line witness contract and preservation of typed provenance."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.coverage import Unsupported,digest
from legal_skill_guard.rr.engine import decode_slots
from legal_skill_guard.rr.source_bindings import decode_source_bindings
from legal_skill_guard.rr.source_structure import inspect_source


def test_actual_public_witnesses_can_use_all_required_factual_lines():
    root=Path(__file__).resolve().parents[1]
    public=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())
    source=next(s for s in public['sources'] if s['key']=='ProofWriter_OWA_depth5:f39b4cd5a6faf7e199c568e2487db5b6b0e27fadefef4f319d42655e4fe04d94')
    st=inspect_source(source);units={c.id:st.ledger.text[c.start:c.end] for c in st.ledger.clauses}
    ids=[key for key,text in units.items() if text in {'Dave is green.','Harry is green.'}]
    value={'columns':['person'],'rows':[['Dave'],['Harry']],'closed':True}
    old={'name':'green','type':'relation','value':value,'source':ids[0]}
    with pytest.raises(ValueError):decode_slots({'bindings':[old]},set(units),units)
    slots,covered,checks=decode_source_bindings([{'name':'green','type':'relation','value':value,'sources':ids}],units)
    assert slots['green'].rows==(('Dave',),('Harry',))
    assert covered==set(ids) and all(c['pass'] for c in checks)
    value['rows'].append(['InventedPerson'])
    with pytest.raises(Unsupported,match='grounding'):
        decode_source_bindings([{'name':'green','type':'relation','value':value,'sources':ids}],units)


@pytest.mark.parametrize('sources',[[],['s0','s0'],['missing']])
def test_invalid_evidence_sets_do_not_get_default_provenance(sources):
    with pytest.raises(Unsupported):
        decode_source_bindings([{'name':'n','type':'integer','value':7,'sources':sources}],{'s0':'Seven is 7.'})


def test_multi_source_banks_still_cannot_clone_one_resource():
    units={'s0':'rule owner period limit 100.'}
    value=[{'key':['rule','owner','period'],'balance':100,'policy':'input_order','order_observable':True}]
    bindings=[{'name':name,'type':'allowance_bank','value':deepcopy(value),'sources':['s0']} for name in ['first','second']]
    with pytest.raises(ValueError,match='cloned'):decode_source_bindings(bindings,units)


def test_single_amount_uses_the_same_literal_audit_as_amount_collections():
    binding={'name':'paid','type':'amount','sources':['s0'],'value':{'value':7,'unit':'USD','owner':'Alice',
        'period':'2018','lineage':['s0'],'stage':'element'}}
    slots,_,_=decode_source_bindings([binding],{'s0':'Alice paid USD 7 in 2018.'})
    assert slots['paid'].value==7
    binding['value']['value']=999
    with pytest.raises(Unsupported,match='grounding'):decode_source_bindings([binding],{'s0':'Alice paid USD 7 in 2018.'})


def test_singleton_provenance_adaptation_preserves_actual_paid_scope_program():
    from legal_skill_guard.rr.source_program import compile_source,source_theory
    root=Path(__file__).resolve().parents[1]
    # The fixture is a documented representation-only projection, never a new
    # model response or a fabricated correction to the program's semantics.
    receipt=json.loads((root/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    compiled=compile_source(receipt['source'],receipt['canonical_program'])
    theory=source_theory(compiled,receipt['observed'])
    assert theory.version==receipt['original_after_theory_hash']
    assert digest(compiled['slots'])==receipt['original_slots_hash']
