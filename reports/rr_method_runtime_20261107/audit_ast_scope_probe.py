"""Verify paid AST probe dispatch and result attribution, without generation."""
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.rr.compiler_contract import compiler_response_schema
from legal_skill_guard.rr.source_program import compiler_prompt


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
    schema=actual['response_format']['json_schema']['schema'];assert schema==seal['schema']
    assert hashlib.sha256(json.dumps(schema,ensure_ascii=False).encode()).hexdigest()==seal['schema_order_sha256']
    expected=request_payload(seal['config']['executor'],messages=[{'role':'system','content':seal['system']},
        {'role':'user','content':seal['user']}],thinking=False,schema=schema)
    assert actual==expected
    assert json.loads(seal['user'])['units']==json.loads(compiler_prompt(seal['source'],seal['config']['library'])[1])['units']
    receipt={'checked_utc':datetime.now(timezone.utc).isoformat(),'run_id':args.run_id,
        'source':seal['source']['key'],'wire_body_sha256':wire['body_sha256'],
        'actual_HTTP_equals_sealed_prompt_schema_and_locked_profile':True,'ordered_schema_hash_matches':True,
        'all_original_public_units_preserved':True,
        'schema_also_matches_current_version':schema==compiler_response_schema(seal['source'],seal['config']['library']),
        'thinking_requested':response['thinking_requested'],'reasoning_content_present':bool(response['reasoning_content']),
        'finish_reason':response['finish_reason'],'usage':response['usage'],'elapsed_seconds':response['elapsed_seconds'],
        'raw_content_sha256':hashlib.sha256(response['content'].encode()).hexdigest(),
        'status':result['status'],'error_type':result.get('error_type'),'field_path':result.get('field_path'),
        'error_summary':str(result.get('error',''))[:400],'TRAIN_score':result.get('TRAIN_score'),
        'conditional_certificate':bool(result.get('after',{}).get('certificate')),
        'new_model_calls_by_audit':0,'ledger_counts':counts,'pending':pending,'full_goal_complete':False}
    (root/'reports/rr_method_runtime_20261107'/(args.run_id+'_dispatch_audit.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('run_id','finish_reason','usage','status','error_type','conditional_certificate','ledger_counts','pending')}))


if __name__=='__main__':main()
