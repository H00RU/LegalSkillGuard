"""Actual truncated A replies: diagnose full-K echo without repairing output."""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.pal_refinement import refinement_request
from legal_skill_guard.rr.source_execution import accept_followup,assess_source
from legal_skill_guard.rr.checkpoint import immutable_json

stage=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v6_20261109'
seal=json.loads((stage/'seal.json').read_text())
public={s['key']:s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']}
rows=[]
for index in (6,11):
    sid=seal['sources']['train'][index];journal=stage/'build/journals'/digest(sid)
    request=json.loads((journal/'request1.json').read_text());old=request['prepared']
    assert old['program_format']=='pal_fragment_lines_v1'
    old_payload=json.loads(old['messages'][1]['content'])
    initial=json.loads(json.loads((journal/'state0.json').read_text())['state_json'])
    program=initial['program'];library={'patterns':old_payload['runtime_contract']['available_learned_patterns']}
    compiled=compile_source(public[sid],program,library=library)
    messages,schema,charged=refinement_request(compiled,old['selected'],old['context_closure'],old['names'],
        old_payload['factual_observation_tasks'],old['schema']['properties']['factual_observations'],library)
    payload=json.loads(messages[1]['content'])
    assert payload['CURRENT_units']==old_payload['CURRENT_units']
    assert payload['selected_source_units']==old_payload['selected_source_units']
    assert payload['selected_legal_subexpressions']==old_payload['selected_legal_subexpressions']
    assert payload['factual_observation_tasks']==old_payload['factual_observation_tasks']
    assert charged==old['context_closure']
    assert 'accepted_program' not in payload and payload['accepted_query_is_immutable']
    assert all('value' not in b for b in payload['read_only_catalog']['bindings'])
    assert all(not ({'value','condition','body'}&set(r)) for field in ('rules','scopes','local_names') for r in payload['read_only_catalog'][field])
    assert compiled['program']==program
    record=json.loads((stage/'build/sources'/(digest(sid)+'.json')).read_text())
    raw=record['prediction']['calls'][1]['raw_content'];m=re.search(r'"program_lines"\s*:\s*\[',raw);assert m
    # Extract complete strings for counting only; never reconstruct a reply.
    decoder=json.JSONDecoder();pos=m.end();lines=[]
    while True:
        while pos<len(raw) and raw[pos] in ' \r\n\t,':pos+=1
        try:line,end=decoder.raw_decode(raw,pos)
        except json.JSONDecodeError:break
        if not isinstance(line,str):break
        lines.append(line);pos=end
    old_names={r['name'] for field in ('bindings','observations','nodes','scopes','clauses') for r in program[field]}
    echoed=[]
    for line in lines:
        match=re.match(r'^(?:def\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|\()',line)
        if match and match[1] in old_names:echoed.append(match[1])
    assert len(set(echoed))>=49
    try:
        response=json.loads(raw)
        recovered,observed=accept_followup(compiled,old,response,library=library)
    except Exception as exc:
        rejection={'type':type(exc).__name__,'error':str(exc)[:350]}
    else:
        assert recovered['program']['query']==program['query']
        for field in ('bindings','observations','scopes','clauses'):
            current={r['name']:r for r in recovered['program'][field]}
            assert all(digest(current[r['name']])==digest(r) for r in program[field])
        assessment=assess_source(recovered,observed)
        rejection={'recovered_by_identical_declaration_omission':True,'remaining_status':assessment['status'],
            'answer':assessment['answer'],'omitted_identical_declarations':len(recovered['deterministic_adaptations']),
            'core_success_claimed':False}
    rows.append({'source':sid,'original_order':index+1,'actual_raw_response_sha256':hashlib.sha256(raw.encode()).hexdigest(),
        'complete_prefix_lines_counted_only':len(lines),'protected_declarations_echoed':len(set(echoed)),
        'protected_binding_names':len(program['bindings']),'selected_source_units':old['selected'],
        'exact_source_texts_targets_factual_tasks_and_charges_unchanged':True,
        'accepted_program_and_query_not_modified':True,'new_request_contains_no_accepted_definition_bodies':True,
        'factual_rows_precede_optional_patch_lines_in_new_schema':list(schema['properties'])==['factual_observations','program_lines'],
        'old_message_characters':sum(len(m['content']) for m in old['messages']),
        'new_message_characters':sum(len(m['content']) for m in messages),
        'actual_response_outcome_after_identity_adapter':rejection,'missing_output_not_reconstructed':True,
        'real_validation_of_new_contract_pending':True})
result={'rows':rows,'new_model_or_oracle_calls':0,'labels_read':False,'scope_and_type_and_grounding_checks_unchanged':True,
    'full_goal_complete':False,'purpose':'Remove the observed full-program echo trigger while preserving the same source-local A repair task. A shorter prompt is not a semantic success.'}
immutable_json(ROOT/'reports/rr_method_runtime_20261107/reference_A_patch_contract_v23_offline.json',result)
print(json.dumps(result,ensure_ascii=False))
