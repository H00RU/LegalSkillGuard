"""Literal source skeletons assemble model atoms without repairing semantics."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from legal_skill_guard.rr.atom_frontend import atom_slots,atom_prompt,template_atom_values,decode_atom_response
from legal_skill_guard.rr.compiler_templates import make_template
from legal_skill_guard.rr.model_horn import LogicTranslationError,assess_model_horn
from test_rr_model_horn import actual_source,CONTROL
from test_rr_compiler_templates import later_source


def fixture_template():return make_template(actual_source(),CONTROL,{'role':'teacher','call_id':'offline_fixture','request_hash':'offline_fixture'})


def test_real_teacher_compatible_program_roundtrips_through_aligned_atoms_without_new_semantics():
    item=fixture_template();values=template_atom_values(item);parsed,code=decode_atom_response(actual_source(),values)
    result=assess_model_horn(parsed)
    assert len(parsed.facts)==14 and len(parsed.rules)==8 and not parsed.export()['missing_units']
    assert result['answer']=='Unknown' and result['certificate_status']=='completion_stable'


def test_actual_failed_head_and_positive_cold_fragments_are_exposed_separately():
    slots,_=atom_slots(later_source())
    assert slots['s14_0']['text']=='someone eats the dog'
    assert slots['s14_1']['text']=='the dog visits the lion'
    assert slots['s14_2']['text']=='the lion eats the dog'
    assert slots['s17_2']['text']=='they are cold'
    assert slots['s17_2']['literal_polarity_hint']=='positive'
    assert slots['s21_1']['literal_polarity_hint']=='positive'


def test_generation_contract_puts_valid_earlier_examples_before_the_current_problem():
    payload=json.loads(atom_prompt(later_source(),{'compiler_templates':[fixture_template()]})[1]['content'])
    assert list(payload)==['compiler_training_examples','CURRENT_fragments','source_only_feedback']
    assert payload['compiler_training_examples'][0]['translation']['s0_0']=="-chases('cat','squirrel')"
    assert payload['CURRENT_fragments']['s0_0']['text']=='The bald eagle is big.'


@pytest.mark.parametrize('key,value',[
    ('s14_0',"kind('cow')"),  # Wrong source atom is still rejected.
    ('s16_2','round(X)'),     # A flipped sign is not overridden by its source hint.
    ('s16_0','young(X),needs(X,cow)'),
    ('s22_0','True'),
])
def test_false_atoms_and_native_answers_are_not_corrected_from_source_or_an_example(key,value):
    item=fixture_template();values=template_atom_values(item);values[key]=value
    with pytest.raises((ValueError,LogicTranslationError)):decode_atom_response(actual_source(),values)


def test_model_must_supply_every_atom_and_no_new_field_is_used_as_an_answer():
    values=template_atom_values(fixture_template());values.pop('s16_0')
    with pytest.raises(ValidationError):decode_atom_response(actual_source(),values)


def test_all_original_train_logic_sentence_forms_have_explicit_source_skeletons():
    root=Path(__file__).resolve().parents[1]
    sources=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
    checked=0;generic=0
    from legal_skill_guard.rr.source_structure import inspect_source
    from legal_skill_guard.rr.public_horn import parse_rule
    for source in sources:
        if source['dataset']!='ProofWriter_OWA_depth5':continue
        slots,units=atom_slots(source);structure=inspect_source(source);checked+=1
        for clause in structure.ledger.clauses:
            if structure.roles[clause.id]['role']!='rule':continue
            text=structure.ledger.text[clause.start:clause.end]
            assert len(units[clause.id]['keys'])==len(parse_rule(text,clause.id).body)+1
            if not text.startswith('If '):
                generic+=1
                assert slots[units[clause.id]['keys'][-1]]['text'] in text
    assert checked==24 and generic>0


def test_generic_adjective_conjunction_and_negative_head_remain_model_obligations():
    source=deepcopy(actual_source())
    source['public']['rules'][0]='All blue, kind things are not round.'
    from legal_skill_guard.rr.coverage import digest
    source['content_hash']=digest(source['public'])
    slots,units=atom_slots(source);keys=units['s14']['keys']
    assert [slots[k]['text'] for k in keys]==['blue','kind','not round']
    assert [slots[k]['literal_polarity_hint'] for k in keys]==['positive','positive','negative']
    assert 'same universal X' in atom_prompt(source)[0]['content']
