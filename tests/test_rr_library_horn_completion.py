"""The actual learned executor, rather than an ordinary-Horn substitute, enters Omega."""
from copy import deepcopy
from pathlib import Path
import json

from legal_skill_guard.rr.coverage import certificate,complete,digest
from legal_skill_guard.rr.public_horn import LibraryHornQuery,parse_public


def library():
    root=Path(__file__).resolve().parents[1]
    return json.loads((root/'artifacts/rr_v2_formal_build_20261106/run_citation_fix/B1.frozen.json').read_text())['content']


def case(read=None,patterns=None):
    public={'answer_type':'three_valued_owa','facts':['Alice is red.','Alice is round.'],
        'rules':['If something is red and round then it is green.'],'query':'Alice is green.'}
    parsed=parse_public(public)
    theory=parsed.partial_theory([c.id for c in parsed.ledger.clauses] if read is None else read)
    base=theory.query
    theory.query=LibraryHornQuery(base.fixed_facts,base.choices,base.rules,base.query,
        deepcopy(library() if patterns is None else patterns))
    return theory


def test_actual_stored_graph_is_evaluated_in_both_different_answer_completions():
    theory=case(['s0','s2','s3']);before=digest(theory.query.library)
    result=complete(theory)
    assert result.status=='translation_unresolved'
    assert sorted(w.answer for w in result.worlds)==['True','Unknown']
    assert theory.query.execute({'fact_s1':True})['pattern_uses']
    assert theory.query.execute({'fact_s1':False})['pattern_uses']
    assert digest(theory.query.library)==before


def test_complete_source_proof_and_main_trace_use_the_same_stored_executor():
    theory=case();result=complete(theory);proof=certificate(theory,result)
    execution=theory.query.execute(theory.facts)
    assert result.answer==execution['answer']=='True'
    assert proof['completion_count']==1 and execution['pattern_uses']
    assert not proof['natural_language_faithfulness_proven']


def test_missing_or_corrupt_library_never_uses_a_correct_predefined_join_to_certify():
    for frozen in ({'patterns':[]},library()):
        frozen=deepcopy(frozen)
        if frozen['patterns']:frozen['patterns'][0]['pattern']['basis']='changed'
        theory=case(patterns=frozen)
        result=complete(theory)
        assert result.status=='unsupported_no_certificate' and result.answer is None
