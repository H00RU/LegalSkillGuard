"""Audit saved physical dispatch and source-only diagnosis, without generation."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.source_code import SourceCodeError, compiler_response_schema, decode_compiler_response
from legal_skill_guard.rr.source_program import compiler_prompt
from legal_skill_guard.rr.source_validation import validation_feedback
from legal_skill_guard.rr.wire_validation import validate_wire


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2];stage=root/'artifacts/rr_method_runtime_20261107'/args.run_id
    seal=json.loads((stage/'seal.json').read_text());result=json.loads((stage/'result.json').read_text())
    with sqlite3.connect('file:'+str(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        row=db.execute('select status,result from calls where id=?',(args.run_id+':compile',)).fetchone()
        counts=dict(db.execute('select role,count(*) from calls group by role'))
        pending=db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    assert row[0]=='completed';response=json.loads(row[1]);directory=Path(response['artifact_directory'])
    wire=json.loads((directory/'wire_request.json').read_text());body=base64.b64decode(wire['body_b64'])
    assert hashlib.sha256(body).hexdigest()==wire['body_sha256'];actual=json.loads(body)
    schema=compiler_response_schema(seal['source'],seal['config']['library'])
    assert schema==seal['schema']
    expected=MethodExecutor(None,stage,seal['config']['executor']).payload(
        messages=[{'role':'system','content':seal['system']},{'role':'user','content':seal['user']}],
        thinking=False,schema=schema)
    assert actual==expected
    actual_schema=actual['response_format']['json_schema']['schema']
    ordered_hash=hashlib.sha256(json.dumps(actual_schema,ensure_ascii=False).encode()).hexdigest()
    assert ordered_hash==seal['schema_order_sha256']
    fresh_units=json.loads(compiler_prompt(seal['source'],seal['config']['library'])[1])['units']
    assert json.loads(seal['user'])['units']==fresh_units
    decoded=json.loads(response['content']);validate_wire(decoded,schema)
    try:
        program=decode_compiler_response(decoded,seal['source'],seal['config']['library'])
        feedback=validation_feedback(seal['source'],program)
    except SourceCodeError as exc:
        feedback={'previous_error':{'type':type(exc).__name__,'message':str(exc),'diagnostics':exc.diagnostics}}
    receipt={'checked_utc':datetime.now(timezone.utc).isoformat(),'run_id':args.run_id,
        'source':seal['source']['key'],'wire_body_sha256':wire['body_sha256'],
        'actual_HTTP_payload_equals_sealed_messages_fresh_schema_and_locked_sampler':True,
        'schema_serialization_order_matches_seal':True,'all_original_public_units_preserved':True,
        'thinking_requested':response['thinking_requested'],'reasoning_content_present':bool(response['reasoning_content']),
        'finish_reason':response['finish_reason'],'usage':response['usage'],'elapsed_seconds':response['elapsed_seconds'],
        'incremental_executor_API_cash_usd':response['incremental_api_cash_usd'],
        'executor_GPU_allocation_cost_usd':response['gpu_cost_usd'],
        'raw_content_sha256':hashlib.sha256(response['content'].encode()).hexdigest(),
        'strict_metadata_passed':True,'source_only_validation_feedback':feedback,
        'result_status':result['status'],'error_type':result.get('error_type'),'error_path':result.get('field_path'),
        'conditional_source_certificate':bool(result.get('after',{}).get('certificate')),
        'TRAIN_semantic_match':result.get('TRAIN_score',{}).get('task_correct'),
        'ledger_counts':counts,'pending':pending,'new_model_or_oracle_calls':0,'test_labels_read':False,
        'full_goal_complete':False}
    (root/'reports/rr_method_runtime_20261107'/(args.run_id+'_dispatch_diagnosis.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:receipt[key] for key in ('run_id','strict_metadata_passed','finish_reason','usage','elapsed_seconds','error_path','ledger_counts','pending','new_model_or_oracle_calls')}))


if __name__=='__main__':main()
