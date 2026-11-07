"""Exact public number words from the actual c4 rejection; no answer repair."""
from fractions import Fraction
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from legal_skill_guard.rr.grounding import _numbers,binding_literal_audit
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.coverage import Unsupported
from legal_skill_guard.rr.source_bindings import decode_source_bindings


@pytest.mark.parametrize('text,value',[('zero',0),('forty-five',45),('one hundred and eighty',180),
    ('five hundred',500),('four hundred',400),('one thousand',1000),('two thousand',2000),
    ('two hundred fifty',250),('five thousand',5000),('two thousand five hundred',2500)])
def test_exact_cardinal_value_is_not_a_bag_of_its_component_numbers(text,value):
    assert _numbers(text+' dollars.')=={Fraction(value)}


@pytest.mark.parametrize('text',['someone','twenty-first','one million','one thousand thousand',
    'one and two','five hundred hundred','negative five','one\nhundred'])
def test_unsupported_number_phrases_do_not_supply_a_guessed_complete_number(text):
    values=_numbers(text)
    if text=='one\nhundred':assert values=={Fraction(1)}
    else:assert values==set()


def test_one_half_keeps_its_exact_fraction_without_a_new_one_binding():
    assert _numbers('one-half')=={Fraction(1,2)}
    assert not binding_literal_audit('integer',1,'one-half',set())['pass']
    assert _numbers('$1,250.50 and two hundred fifty dollars')=={Fraction(2501,2),Fraction(250)}


def test_actual_correct_word_amounts_are_recovered_but_eleven_invented_amounts_stay_rejected():
    root=Path(__file__).resolve().parents[1]
    fixture=json.loads((root/'tests/fixtures/rr_actual_method_c4_cardinals.json').read_text())
    source=next(s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
                if s['key']==fixture['source'])
    program=json.loads(fixture['raw_content']);structure=inspect_source(source)
    units={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
    recovered={'b_ari_exemption_'+name for name in ('wearing_apparel','musical_instruments',
        'horses_cows_poultry','engagement_wedding_rings','library_books','watch','firearms',
        'tools_equipment','farm_machinery')}
    actual=set();rejected=[];names={b['name'] for b in program['bindings']}
    for b in program['bindings']:
        text='\n'.join(units[s] for s in b['sources'])
        check=binding_literal_audit(b['type'],b['value'],text,names)
        if b['name'] in recovered:assert check['pass'];actual.add(b['name'])
        if not check['pass']:rejected.append(b['name'])
    assert actual==recovered and len(rejected)==11
    assert not binding_literal_audit('integer',500,units['s200'],set())['pass']
    assert not binding_literal_audit('integer',15000,units['s201'],set())['pass']
    # Check literal rejection independently of the now-earlier invalid native
    # query rejection. The original program and all eleven errors stay intact.
    with pytest.raises(Unsupported,match='Public literal grounding failed'):
        decode_source_bindings(program['bindings'],units)
    with pytest.raises(ValidationError) as failure:compile_source(source,program)
    assert list(failure.value.path)==['query']
