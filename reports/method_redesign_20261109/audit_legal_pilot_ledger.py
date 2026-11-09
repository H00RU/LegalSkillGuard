"""Read-only physical ledger preservation and cost accounting for the finite pilot."""
from datetime import datetime,timezone
import hashlib,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'reports/method_redesign_20261109'
ORIGIN=Path('/media/sangfor/vdb/legal-skill-backups/method_redesign_20261109_start/ledger.sqlite3')
LEDGER=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
PREFIXES=('legal_relations_exceptions_native_v1_20261109:','legal_relations_exceptions_native_v2_20261109:','legal_relations_exceptions_native_v3_20261109:','legal_relations_shared_direct_v1_20261109:')

def main():
 with sqlite3.connect('file:'+str(LEDGER)+'?mode=ro',uri=True) as db,sqlite3.connect('file:'+str(ORIGIN)+'?mode=ro',uri=True) as old:
  for table in ('calls','meta','oracle_views'):
   before=old.execute('select * from '+table).fetchall();after=db.execute('select * from '+table).fetchall()
   assert set(before)<=set(after),table
  counts={role:n for role,n in db.execute('select role,count(*) from calls group by role')};pending=db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
  raw=db.execute('select id,role,source,status,result from calls order by reserved_at,id').fetchall()
  historic={name:db.execute('select * from '+name+' order by 1').fetchall() for name in ('calls','meta','oracle_views')}
  historic['calls']=[x for x in historic['calls'] if not x[0].startswith(PREFIXES)]
  namespace=tuple('method_runtime_policy:'+p[:-1] for p in PREFIXES)
  historic['meta']=[x for x in historic['meta'] if x[0] not in namespace]
  historic_hash=hashlib.sha256(json.dumps(historic,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  old_hash=json.loads((REPORT/'composed_channel_results.json').read_text())['ledger_after']['logical_sha256']
  assert historic_hash==old_hash, 'A pre-pilot ledger row changed'
  preserved_hashes=json.loads((REPORT/'reader_backoff_integrity.json').read_text())['preserved_file_hashes']
  assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in preserved_hashes.items())
  calls=[]
  for cid,role,src,status,text in raw:
   if not cid.startswith(PREFIXES):continue
   w=json.loads(text);usage=w.get('usage') or w.get('invocation',{}).get('usage') or {}
   calls.append({'id':cid,'role':role,'source':src,'physical_status':status,'input_tokens':usage.get('prompt_tokens',usage.get('input_tokens')),'output_tokens':usage.get('completion_tokens',usage.get('output_tokens')),'reasoning_output_tokens_subset':usage.get('reasoning_output_tokens'),'elapsed_seconds':w.get('elapsed_seconds'),'finish_reason':w.get('finish_reason'),'thinking_requested':w.get('thinking_requested'),'physical_request_charged':True,'client_retries':0,'provider_internal_retries':'not observable for teacher CLI','known_incremental_executor_api_cash_usd':w.get('incremental_api_cash_usd'),'gpu_cost_usd':None,'teacher_actual_cash_invoice_available':w.get('actual_cash_invoice_available')})
  assert len(calls)==8 and sum(c['role']=='executor' for c in calls)==6 and pending==0
  pid=958223;stat=Path(f'/proc/{pid}/stat').read_text();start=int(stat[stat.rindex(')')+2:].split()[19]);assert start==486445918
  rows=[]
  for proc in Path('/proc').iterdir():
   if not proc.name.isdigit():continue
   try:argv=(proc/'cmdline').read_bytes().split(b'\0')
   except (FileNotFoundError,PermissionError,ProcessLookupError):continue
   if b'-m' in argv and any(a.startswith(b'experiments.rr_v2_legal') for a in argv):rows.append(int(proc.name))
  out={'captured_utc':datetime.now(timezone.utc).isoformat(),'counts_total':counts,'pending':pending,'new_physical_calls':{'executor':6,'teacher':2},'calls':calls,'original1382_call_rows_preserved':len(old.execute('select * from calls').fetchall()),'original184_meta_rows_preserved':len(old.execute('select * from meta').fetchall()),'original130_oracle_rows_preserved':len(old.execute('select * from oracle_views').fetchall()),'all_pre_pilot_call_rows_retained':len(raw)-len(calls),'entire_pre_pilot_logical_snapshot_reproduced':historic_hash,'old_frozen_files_unchanged':preserved_hashes,'new_oracle_views':0,'no_ledger_reset':True,'current_research_clients':rows,'original_model_service':{'pid':pid,'start_ticks':start,'unchanged':True},'executor_sums':{'input_tokens':sum(c['input_tokens'] for c in calls if c['role']=='executor'),'output_tokens':sum(c['output_tokens'] for c in calls if c['role']=='executor'),'request_elapsed_seconds_sum':sum(c['elapsed_seconds'] for c in calls if c['role']=='executor')},'teacher_sums':{'input_tokens':sum(c['input_tokens'] for c in calls if c['role']=='teacher'),'output_tokens':sum(c['output_tokens'] for c in calls if c['role']=='teacher'),'request_elapsed_seconds_sum':sum(c['elapsed_seconds'] for c in calls if c['role']=='teacher')},'total_cash_cost_usd':None,'known_executor_incremental_API_cash_usd':0,'reason_total_cash_is_unknown':'Existing local GPU cost and teacher actual invoice are unavailable; incremental executor API price is not total research cost.','goal_complete':False,'TEST_started':False,'new_full_build_started':False}
 (REPORT/'legal_native_pilot_ledger.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:out[k] for k in ('counts_total','pending','new_physical_calls','executor_sums','teacher_sums','current_research_clients')},ensure_ascii=False))
if __name__=='__main__':main()
