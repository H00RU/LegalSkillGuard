"""Real paid outputs distinguish formatting from operative missing semantics."""
import json
from pathlib import Path
import pytest

from legal_skill_guard.rr.clause_scope import syntax_only_source_unit
from legal_skill_guard.rr.coverage import evaluate,digest,Unsupported
from legal_skill_guard.rr.pal_frontend import parse_pal,pal_prompt
from legal_skill_guard.rr.source_format import native_output_metadata
from legal_skill_guard.rr.source_inference import native_fallback

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('text',['11 U.S.C. § 522(d)(3)','735 Ill. Comp. Stat. 5/12-1001(a)','| --- | :---: | ---: |'])
def test_addresses_and_empty_alignment_rows_have_no_rule_body(text):
    assert syntax_only_source_unit(text)


@pytest.mark.parametrize('text',['### First Bag','##### Over 50 lbs / 23 kgs to 53 lbs / 24 kgs',
    '| Regions | Basic Economy |','| South America | $100 |','(3) household goods up to $700','11 U.S.C. § 522(d)(3) applies only if employed'])
def test_operative_headings_cells_and_conditions_remain_semantic_obligations(text):
    assert not syntax_only_source_unit(text)


def test_paid_airline_partial_preserves_every_operative_unknown_after_layout_handling():
    from legal_skill_guard.rr.compiler_templates import validate_template
    from legal_skill_guard.rr.source_program import source_theory
    p=ROOT/'artifacts/rr_method_runtime_20261107/reference_frontend_prior_airline2_partial_v14_20261108/compiler_template.json'
    compiled=validate_template(json.loads(p.read_text()));st=compiled['structure']
    unknown={r.source for r in source_theory(compiled).residuals if r.unknown_scope}
    original={'s24','s41','s56','s63','s128','s132','s141','s149',
        's23','s40','s55','s62','s127','s131','s140','s148','s22','s39','s54','s61','s126','s130','s139'}
    formatting={c.id for c in st.ledger.clauses if c.id in original and syntax_only_source_unit(st.ledger.text[c.start:c.end])}
    assert len(formatting)==8 and unknown==original-formatting
    assert all(st.roles[s]['role']=='rule' for s in original)


def test_literal_list_addition_uses_existing_concat_and_preserves_both_branches():
    code='@rule("s0", otherwise=False)\ndef allowed():\n    return True\nquery = (["A"] if allowed() else []) + (["B"] if allowed() else []) + []'
    expr=parse_pal(code)['query'];assert expr['op']=='concat'
    assert evaluate(expr,{'allowed':True})==['A','B']
    assert evaluate(expr,{'allowed':False})==[]
    assert parse_pal(code.replace('(["A"] if allowed() else []) + (["B"] if allowed() else []) + []','1 + 2'))['query']['op']=='add'
    mixed=parse_pal(code.replace('(["A"] if allowed() else []) + (["B"] if allowed() else []) + []','[1] + 2'))['query']
    with pytest.raises(Unsupported):evaluate(mixed,{})


def test_source_only_citation_vocabulary_is_shared_with_native_fallback():
    source=json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources'][0]
    metadata=native_output_metadata(source);vocabulary=metadata['public_citation_vocabulary']
    assert '11 U.S.C. § 522(d)(3)' in vocabulary and not any(s.startswith('s') and s[1:].isdigit() for s in vocabulary)
    for messages in [pal_prompt(source),native_fallback(source)[0]]:
        payload=json.loads(messages[1]['content']);current=payload.get('CURRENT',payload)
        assert {k:current[k] for k in metadata}==metadata
    assert native_output_metadata({'dataset':'SARA_v2_Binary'})=={}


def test_two_view_rule_text_interning_preserves_every_source_identity_and_context():
    from legal_skill_guard.rr.source_structure import inspect_source,compact_contexts
    source=json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources'][0]
    payload=json.loads(pal_prompt(source)[1]['content']);st=inspect_source(source);contexts=compact_contexts(st)
    expected=[{'id':c.id,**st.roles[c.id],'text':st.ledger.text[c.start:c.end],'context':contexts[c.id]} for c in st.ledger.clauses]
    expanded=[];by_id={};references=0
    for unit in payload['CURRENT']['units']:
        unit=dict(unit)
        if 'same_text_as' in unit:
            assert unit['view']=='EV' and unit['role']=='rule'
            parent=by_id[unit.pop('same_text_as')];assert parent['view']=='EC'
            unit['text']=parent['text'];references+=1
        expanded.append(unit);by_id[unit['id']]=unit
    assert expanded==expected and references==152


def test_actual_partial_teacher_compaction_keeps_domains_and_missing_rules():
    from legal_skill_guard.rr.compiler_templates import validate_template
    from legal_skill_guard.rr.source_program import source_theory
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_frontend_prior_openexempt1_partial_v22_20261109'
    audit=json.loads((stage/'recovery_audit.json').read_text());item=json.loads((stage/'compiler_template.json').read_text())
    compiled=validate_template(item);unknown={r.source for r in source_theory(compiled).residuals if r.unknown_scope}
    assert unknown==set(audit['unknown_source_units']) and len(unknown)==150
    assert audit['all_declared_Boolean_completions_compared']==256
    assert audit['pure_identity_scopes_eliminated']==144
    assert len(compiled['program']['scopes'])==4 and len(compiled['program']['clauses'])==12
    assert len(compiled['observations'])==8 and audit['executor_core_success'] is False
