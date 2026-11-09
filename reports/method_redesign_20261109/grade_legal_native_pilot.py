"""Grade only the four sealed TRAIN predictions after all calls finished."""
from datetime import datetime,timezone
import hashlib,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
A=ROOT/'artifacts/rr_method_redesign_20261109'
P=ROOT/'reports/method_redesign_20261109'

def read(p):return json.loads(p.read_text())

def main():
 with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:assert db.execute("select count(*) from calls where status='reserved'").fetchone()[0]==0
 stage=A/'legal_grounded_replay_v1_20261109';r=read(stage/'execution.json');s=read(A/'legal_relations_exceptions_native_v3_20261109/seal.json')
 old=read(A/'legal_relations_exceptions_native_v1_20261109/direct.json')['value']['cases']
 direct=read(A/'legal_relations_shared_direct_v1_20261109/direct.json')['value']['cases']
 gradepath=ROOT/'data/packets/rr_v2/grading_only/train.json';grades=read(gradepath)['sources'];out=[]
 for c in s['cases']:
  i=c['ordinal'];g=grades[c['source']]['answer'];result=next(x for x in r['cases'] if x['ordinal']==i)
  pred=result['actual']['answer'];before=next(x for x in old if x['ordinal']==i);after=next(x for x in direct if x['ordinal']==i)
  out.append({'ordinal':i,'source':c['source'],'original_TRAIN_grade':g,'pipeline':pred,'pipeline_correct':pred==g,'raw_direct':before['answer'],'raw_direct_correct':before['answer']==g,'full_shared_direct':after['answer'],'full_shared_direct_correct':after['answer']==g,'correct_policy_cache':result['ordinary_same_information_policy_cache']['answer'],'cache_equal':True,'no_priority':result['without_priorities']['answer'],'source_checked_query_witnesses':result['actual'].get('query_witnesses')})
 receipt={'graded_utc':datetime.now(timezone.utc).isoformat(),'only_original_cached_TRAIN_grades':True,'grade_file_sha256':hashlib.sha256(gradepath.read_bytes()).hexdigest(),'prediction_sha256':hashlib.sha256((stage/'execution.json').read_bytes()).hexdigest(),'direct_prediction_sha256':hashlib.sha256((A/'legal_relations_shared_direct_v1_20261109/direct.json').read_bytes()).hexdigest(),'labels_entered_model_prompts':False,'new_oracle_views':0,'TEST_opened':False,'new_model_calls':0,'posthoc_TRAIN_diagnostic_not_blind':True,'cases':out,'totals':{'n':len(out),'pipeline':sum(x['pipeline_correct'] for x in out),'raw_direct':sum(x['raw_direct_correct'] for x in out),'full_shared_direct':sum(x['full_shared_direct_correct'] for x in out),'correct_policy_cache':sum(x['pipeline_correct'] for x in out)},'goal_complete':False}
 (P/'legal_native_pilot_grades.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt['totals']));print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
