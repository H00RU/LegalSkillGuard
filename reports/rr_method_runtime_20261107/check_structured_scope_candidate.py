"""Offline candidate only: canonical ASTs and fixed source-keyed scope slots.

The live controller keeps its sealed compiler. Null scope entries mean no
accepted scope, exactly as an absent row in the existing SourceIR. This file
does not dispatch, change source, repair model semantics, or claim learning.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.source_execution import assess_source, prepare_followup
from legal_skill_guard.rr.source_program import compile_source, program_schema, source_theory
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.strict_contract import obj
from legal_skill_guard.rr.wire_validation import validate_wire


def rule_ids(source):
    structure=inspect_source(source)
    return [c.id for c in structure.ledger.clauses if structure.roles[c.id]['role']=='rule']


def candidate_schema(source, library=None):
    schema=program_schema(source, library)
    item=deepcopy(schema['properties']['scopes']['items'])
    del item['properties']['source'];item['required'].remove('source')
    schema['properties']['scopes']=obj({sid:{'anyOf':[{'type':'null'},deepcopy(item)]} for sid in rule_ids(source)})
    order=('scopes','clauses','rule_residuals','observations','bindings','nodes','query')
    schema['properties']={key:schema['properties'][key] for key in order}
    schema['required']=list(order)
    return schema


def encode(program, source):
    scopes={}
    for row in program['scopes']:
        if row['source'] in scopes:raise ValueError('Duplicate source scope is not a recoverable mapping')
        scopes[row['source']]={'name':row['name'],'condition':deepcopy(row['condition'])}
    if not set(scopes)<=set(rule_ids(source)):raise ValueError('Non-rule scope provenance')
    result=deepcopy(program)
    result['scopes']={sid:scopes.get(sid) for sid in rule_ids(source)}
    return result


def decode(value, source, library=None):
    validate_wire(value,candidate_schema(source,library))
    result=deepcopy(value)
    result['scopes']=[{'name':row['name'],'source':sid,'condition':row['condition']}
                      for sid,row in value['scopes'].items() if row is not None]
    return result


def main():
    def denied(*a,**k):raise AssertionError('Offline candidate cannot use network or subprocess')
    socket.socket.connect=denied;socket.create_connection=denied;subprocess.run=denied;subprocess.Popen=denied
    root=Path(__file__).resolve().parents[2]
    seal=json.loads((root/'artifacts/rr_method_runtime_20261107/method_runtime_typed_v1_20261107/seal.json').read_text())
    before=science_files(root);assert before==seal['files']
    def book():
        with sqlite3.connect('file:'+str(root/seal['ledger_path'])+'?mode=ro',uri=True) as db:
            return dict(db.execute('select role,count(*) from calls group by role'))
    counts=book()
    case=json.loads((root/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    source,program=case['source'],case['canonical_program']
    restored=decode(encode(program,source),source)
    assert restored==program
    a=compile_source(source,program);b=compile_source(source,restored)
    assert digest(source_theory(a,case['observed']))==digest(source_theory(b,case['observed']))
    assert assess_source(a,case['observed'])==assess_source(b,case['observed'])
    selected=prepare_followup(b,compilation='answer_separating',tokenize=lambda *a,**k:{'count':100},
        request_config={'context_tokens':32768,'max_tokens':8192},thinking=False)
    assert selected['selected']==['s10'] and selected['names']==['b_legally_separated']
    # An omitted scope stays omitted. No null is converted to False or True.
    empty=deepcopy(program);empty['scopes']=[]
    assert decode(encode(empty,source),source)==empty
    packet=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())
    assert packet['split']=='train' and not packet['contains_gold_or_reference_program']
    sources={s['key']:s for s in packet['sources']};rows=[]
    from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
    seen=set()
    for sid in seal['sources']['train']:
        s=sources[sid]
        if s['dataset'] in seen:continue
        seen.add(s['dataset']);schema=candidate_schema(s)
        assert not strict_output_schema_issues(schema)
        rows.append({'dataset':s['dataset'],'source':sid,'fixed_rule_scope_slots':len(rule_ids(s)),
            'schema_sha256':digest(schema),'schema_bytes':len(json.dumps(schema)),
            'strict_schema_issues':[]})
    assert len(rows)==5 and science_files(root)==before
    receipt={'checked_utc':datetime.now(timezone.utc).isoformat(),'candidate_not_activated':True,
        'live_run_id':seal['run_id'],'live_sealed_files_unchanged':True,'paid_case_IR_exact':True,
        'paid_case_full_theory_and_assessment_identical':True,'A_selected':['s10'],
        'untranslated_scope_null_remains_absent_not_false':True,'schema_shapes':rows,
        'network_and_subprocess_blocked':True,'ledger_before':counts,'ledger_after':book(),
        'new_model_calls_by_candidate':0,'grading_packets_opened':False,
        'backend_token_masks_checked':False,'actual_executor_success_proven':False,
        'claim':'Representation feasibility only; no change to live flow, A/B or existing correctness checks.'}
    (root/'reports/rr_method_runtime_20261107/structured_scope_candidate_offline.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:receipt[key] for key in ('candidate_not_activated','paid_case_IR_exact','paid_case_full_theory_and_assessment_identical','live_sealed_files_unchanged','new_model_calls_by_candidate')}))


if __name__=='__main__':main()
