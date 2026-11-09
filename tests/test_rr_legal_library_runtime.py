import json
from pathlib import Path
from legal_skill_guard.rr.legal_library_runtime import execute_library
A=Path(__file__).resolve().parents[1]/'artifacts/rr_method_redesign_20261109/legal_grounded_replay_v1_20261109'

def data():return json.loads((A/'frozen_library.json').read_text()),json.loads((A/'shared_grounded_cases.json').read_text())['cases']


def test_saved_real_library_dispatches_source_roles_and_negative_callee_without_native_default():
 library,cases=data();rows={c['ordinal']:execute_library(library,c) for c in cases}
 assert rows[81]['answer']=='Entailment'
 assert rows[81]['source_calls'][0]['arguments']==['Alice','Bob','2015']
 assert rows[86]['source_calls'][0]['arguments']==['Alice','Bob','2015']
 assert rows[86]['answer']=='Entailment'
 assert rows[87]['answer'] is None
 assert len(rows[87]['source_calls'])==1
 call=rows[87]['source_calls'][0]
 assert call['arguments']==['Alice','Bob','2017']
 assert call['observed_callee_polarity'] is False
 assert call['condition']['condition_value'] is False
 assert call['callee_recompiled'] is False


def test_real_numeric_query_still_consumes_source_priority_effects():
 library,cases=data();r=execute_library(library,next(c for c in cases if c['ordinal']==72))
 assert r['answer']=='Contradiction'
 assert r['mechanism']=='scoped_terminal_effects'
 assert r['proof']['suppressed']
