"""Actual stored graph invocation; parser/closure are never counted as learning."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.horn_connectors import predict_with_library


def actual():
    root=Path(__file__).resolve().parents[1]
    public=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())
    source=next(s for s in public['sources'] if s['key']=='ProofWriter_OWA_depth5:f39b4cd5a6faf7e199c568e2487db5b6b0e27fadefef4f319d42655e4fe04d94')
    library=json.loads((root/'artifacts/rr_v2_formal_build_20261106/run_citation_fix/B1.frozen.json').read_text())['content']
    return source,library


def test_actual_later_source_executes_stored_graph_with_factual_witnesses():
    source,library=actual();before=digest(library)
    result=predict_with_library(source['public'],library)
    assert result['status']=='closure_complete' and result['pattern_uses']
    assert any(use['query_relevant'] for use in result['pattern_uses'])
    assert {u['pattern_hash'] for u in result['pattern_uses']}=={library['patterns'][0]['pattern_hash']}
    assert all(u['status']=='executed_main_program' and u['input_witnesses'] for u in result['pattern_uses'])
    assert digest(library)==before and not result['fallback_used'] and not result['A_certificate_issued']


def test_masked_library_cannot_fall_back_to_a_builtin_correct_join():
    source,_=actual();result=predict_with_library(source['public'],{'patterns':[]})
    assert result['status']=='pattern_unavailable' and result['answer'] is None
    assert not result['fallback_used']


def test_staged_pattern_calls_keep_intermediate_witnesses():
    _,library=actual()
    public={'answer_type':'three_valued_owa','facts':['Alice is red.','Alice is round.','Alice is tall.','Bob is red.'],
        'rules':['If something is red and round and tall then it is green.'],'query':'Alice is green.'}
    result=predict_with_library(public,library)
    assert result['answer']=='True'
    second=next(u for u in result['pattern_uses'] if u['node']=='joined_2')
    assert 'joined_1' in second['input_witnesses']
    assert second['input_witnesses']['joined_1']['rows']==[['alice']]


def test_bad_pattern_hash_stops_without_an_answer():
    source,library=actual();library=deepcopy(library)
    library['patterns'][0]['pattern']['basis']='changed'
    result=predict_with_library(source['public'],library)
    assert result['status']=='invalid_graph_or_library' and result['answer'] is None


def test_prediction_runtime_has_no_training_oracle_or_client_import():
    code="""
import sys
import json
from pathlib import Path
from legal_skill_guard.rr.horn_connectors import predict_with_library
root=Path.cwd()
source=next(s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']=='ProofWriter_OWA_depth5:f39b4cd5a6faf7e199c568e2487db5b6b0e27fadefef4f319d42655e4fe04d94')
library=json.loads((root/'artifacts/rr_v2_formal_build_20261106/run_citation_fix/B1.frozen.json').read_text())['content']
assert predict_with_library(source['public'],library)['pattern_uses']
assert not any(x in sys.modules for x in ['legal_skill_guard.rr.source_learning','legal_skill_guard.rr.oracles','legal_skill_guard.rr.client'])
"""
    completed=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,check=False)
    assert completed.returncode==0,completed.stderr
