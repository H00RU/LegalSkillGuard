"""Replay the real paid primary program and independently check full stored-join rows.

This is offline verification of an earlier real execution, not a new model,
learning, transfer or causal-benefit result. No answer packet is opened.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,socket,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.atom_frontend import decode_atom_response
from legal_skill_guard.rr.model_horn import assess_model_horn
from legal_skill_guard.rr.scoped_program import ScopedQuery
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.checkpoint import immutable_json

def audit(event,args):
 if event in {'socket.connect','socket.bind','socket.sendto','subprocess.Popen','sqlite3.connect'}:
  raise RuntimeError('Paid row replay cannot dispatch, query an oracle, or open the ledger')
 if event=='open' and isinstance(args[0],(str,bytes)) and 'grading_only' in str(args[0]):
  raise RuntimeError('Paid row replay cannot open grading packets')
sys.addaudithook(audit)
before=science_files(ROOT)
run_id='reference_atoms_pw9_v3_20261108';stage=ROOT/'artifacts/rr_method_runtime_20261107'/run_id
seal=json.loads((stage/'seal.json').read_text());saved=json.loads((stage/'result.json').read_text())
paid_path=stage/'calls'/digest(run_id+':parse:0')/'result.json';paid=json.loads(paid_path.read_text())
patterns={p['pattern_hash']:p for p in seal['config']['library']['patterns']}
original=ScopedQuery.execute;checks=[]

def inspect(self,inputs,*,return_environment=False):
 result=original(self,inputs,return_environment=True);env=result['environment']
 for use in result['pattern_uses']:
  item=patterns[use['pattern_hash']];graph=item['pattern']['graphs'][use['variant']]
  assert graph['op']=='join_on' and graph['inputs']==[{'slot':'slot0'},{'slot':'slot1'}]
  left=env[use['role_bindings']['slot0']];right=env[use['role_bindings']['slot1']]
  keys=[use['column_bindings'][k] for k in graph['params']['keys']]
  columns=left.columns+tuple(c for c in right.columns if c not in left.columns)
  rows=[]
  for l in left.rows:
   for r in right.rows:
    if all(l[left.columns.index(k)]==r[right.columns.index(k)] for k in keys):
     rows.append(l+tuple(r[right.columns.index(c)] for c in right.columns if c not in left.columns))
  actual=env[use['node']]
  expected=Counter(rows);observed=Counter(actual.rows)
  check={'pattern_hash':use['pattern_hash'],'variant':use['variant'],'keys':keys,
   'left':{'columns':left.columns,'rows':left.rows},'right':{'columns':right.columns,'rows':right.rows},
   'expected_columns':columns,'expected_rows':rows,'actual_columns':actual.columns,'actual_rows':actual.rows,
   'columns_equal':columns==actual.columns,'complete_row_multisets_equal':expected==observed,
   'duplicates_preserved':expected==observed,'supporting_training_sources':item['evidence_sources']}
  assert check['columns_equal'] and check['complete_row_multisets_equal']
  checks.append(check)
 if not return_environment:result.pop('environment')
 return result
ScopedQuery.execute=inspect
try:
 parsed,code=decode_atom_response(seal['source'],json.loads(paid['content']))
 result=assess_model_horn(parsed,seal['config']['library'],interface='collision_refined')
finally:ScopedQuery.execute=original
assert result==saved['result'] and len(checks)==len(result['execution']['pattern_uses'])==28
assert science_files(ROOT)==before
output={'captured_utc':datetime.now(timezone.utc).isoformat(),'run_id':run_id,
 'actual_paid_request_hash':paid['request_hash'],'actual_raw_sha256':hashlib.sha256(paid['content'].encode()).hexdigest(),
 'exact_actual_result_replayed':True,'graph_calls_checked':len(checks),'all_complete_rows_and_columns_correct':True,
 'checks':checks,'not_only_counts':True,'new_model_requests':0,'new_oracle_views':0,'labels_read':False,
 'current_scientific_bytes_unchanged':True,'offline_replay_of_real_primary_output':True,
 'fresh_B_learning_or_cross_bank_success_claimed':False,'causal_answer_benefit_claimed':False,
 'interpretation':'The28 actual earlier same-bank stored joins reproduce all row identities, columns and multiplicities under an independent nested-loop equality join. The original query already has a factual negative witness; these calls do not prove answer benefit, fresh learning or cross-bank transfer.','full_goal_complete':False}
path=ROOT/'reports/rr_method_runtime_20261107/reference_paid_join_full_rows_v1.json';immutable_json(path,output)
print(json.dumps({k:v for k,v in output.items() if k!='checks'}),flush=True)
