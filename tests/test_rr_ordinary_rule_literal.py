import pytest
from legal_skill_guard.rr.ordinary_rule_literal import lower

CODE="""def law_cache(facts, query):
    quote = 'source text'
    rules = [{'id':'r','head':{'predicate':'p','arguments':['?x'],'positive':True},'body':[{'predicate':'different','arguments':['?x','A'],'positive':True}],'quote':quote}]
    program = {'predicates':facts['interface'],'rules':rules,'priorities':[],'unresolved':[]}
    return solve(program, facts['facts'], query)
"""
SOURCES=[{'section':'fixture','rules':'source text'}]


def test_neutral_field_preserves_explicit_body_constraints_and_quotes():
    p,e=lower(CODE,[{'name':'p'}],SOURCES);r=p['rules'][0]
    assert r['different']==[] and r['body'][0]['predicate']=='different' and r['quote']=='source text'
    assert e['all_bodies_heads_quotes_priorities_and_unresolved_unchanged']


def test_explicit_additional_guard_is_never_replaced():
    p,e=lower(CODE.replace("'quote':quote","'quote':quote,'different':[{'left':'?x','right':'A'}]"),[],SOURCES)
    assert p['rules'][0]['different']==[{'left':'?x','right':'A'}]
    assert not e['rules_with_neutral_empty_additional_guard_field']


@pytest.mark.parametrize('old,new',[
 ("quote = 'source text'","quote = query['answer']"),
 ("quote = 'source text'","quote = str(100)"),
 ("return solve(program, facts['facts'], query)","return {'answer':'Entailment'}"),
 ("quote = 'source text'","quote = 'first'\n    quote = 'second'")])
def test_nonliteral_or_changed_execution_is_rejected(old,new):
    with pytest.raises(ValueError):lower(CODE.replace(old,new),[],SOURCES)


def test_trace_source_spans_are_attached_without_guessing_legal_rules():
    p,e=lower(CODE,[],SOURCES)
    assert p['rules'][0]['authority'].startswith('source_spans:')
    assert e['rules_with_deterministically_attached_trace_provenance']['r']==[{'section':'fixture','start':0,'end':11}]
    with pytest.raises(ValueError,match='source span'):lower(CODE,[],[{'section':'other','rules':'different text'}])
