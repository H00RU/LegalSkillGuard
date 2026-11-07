"""Source structure cannot declare a clause irrelevant or make it compiled."""
import json
from pathlib import Path

from legal_skill_guard.rr.engine import source_text
from legal_skill_guard.rr.source_structure import inspect_source


def test_all_original_train_inputs_keep_exact_text_and_field_origin():
    root = Path(__file__).resolve().parents[1]
    sources = json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
    assert len(sources)==128
    for source in sources:
        structure = inspect_source(source)
        assert structure.ledger.text == source_text(source)
        assert set(structure.roles)=={c.id for c in structure.ledger.clauses}
        assert all(c.state=='residual' for c in structure.ledger.clauses)
        assert all(structure.roles[c.id]['role'] in {'rule','fact','query','instruction','heading'} for c in structure.ledger.clauses)


def test_markdown_parent_context_is_preserved_for_selected_fee_row():
    source = {'dataset':'RuleArena_Airline','public':{
        'rules':'# Baggage\n## Checked\nFees depend on destination.\n## Carry on\nA different condition.',
        'prompt':'One bag.'}}
    structure = inspect_source(source)
    assert structure.ledger.closure({'s2'})=={'s0','s1','s2'}
    assert 's3' not in structure.ledger.closure({'s2'})
    assert structure.roles['s5']['role']=='fact'


def test_cross_reference_context_never_erases_untranslated_obligations():
    source = {'dataset':'SARA_v2_Binary','public':{
        'rules':'11 U.S.C. § 522(d)(1)\nA rule.\n11 U.S.C. § 522(d)(5)\nSee 11 U.S.C. § 522(d)(1) and paragraph (2).',
        'facts':'Alice owns a vase.', 'query':'Does the exemption apply?'}}
    structure = inspect_source(source)
    assert 's0' in structure.ledger.closure({'s3'})
    assert structure.unresolved_references['s3']==['paragraph (2)']
    assert all(c.state=='residual' for c in structure.ledger.clauses)
    assert structure.roles['s5']['role']=='query'


def test_parent_statute_preface_is_retained_for_a_child_clause():
    source = {'dataset':'SARA_v2_Binary','public':{
        'rules':'11 U.S.C. § 522(d)\nThe following provisions share this condition.\n11 U.S.C. § 522(d)(3)\nA child provision.',
        'facts':'Alice owns a vase.', 'query':'Does the provision apply?'}}
    structure = inspect_source(source)
    assert structure.ledger.closure({'s3'})=={'s0','s1','s2','s3'}
    assert all(c.state=='residual' for c in structure.ledger.clauses)
