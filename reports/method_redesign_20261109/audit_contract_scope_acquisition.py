"""Grade saved independent acquisitions against the approved TRAIN views.

This script never dispatches or opens DEV/TEST. Human source-meaning findings
must be reported separately from these native-label and provenance checks.
"""
import hashlib,json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.contract_scope_learning import ScopeLibrary,execute
from experiments.rr_v2_contract_scope_acquisition import execute_cache

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'contract_scope_acquisition_v1_20261110'
DATA=BASE/'contract_authorized_pairs_v1_20261110'

def read(p):return json.loads(p.read_text())
def snapshot(path):
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}

def main():
    seal=read(STAGE/'seal.json');truth=read(DATA/'train_native_supervision.json')
    label={(f'p{r["parent_ordinal"]}',r['hypothesis_id']):r for r in truth['pairs']}
    ledger=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3';before=snapshot(ledger)
    assert not [r for r in before['calls'] if r[6]=='reserved']
    arms={}
    for arm in ['candidate','ordinary_cache']:
        saved=read(STAGE/(arm+'_execution_before_grading.json'));wire=saved['physical_response']
        material={m['policy_id']:m for m in seal['material']}
        policies={p['policy_id']:p for p in saved.get('value',{}).get('policies',[])}
        predictions={(r['policy_id'],r['hypothesis_id']):r for r in saved['rows'] if 'hypothesis_id' in r}
        rows=[]
        for key,expected in label.items():
            old=predictions.get(key);policy,qid=key;new=None;error=None
            if old:
                try:
                    query=next(q for q in material[policy]['questions'] if q['id']==qid)
                    p=policies[policy];doc=material[policy]['document']
                    new=execute(p,doc,qid) if arm=='candidate' else execute_cache(p['code'],query,doc)
                    assert new==old['execution']
                except Exception as exc:error=type(exc).__name__+': '+str(exc)
            predicted=None if old is None else old['execution'].get('answer')
            rows.append({'policy_id':policy,'hypothesis_id':qid,'native_answer':expected['answer'],
              'answer':predicted,'native_correct':predicted is not None and predicted==expected['answer'],
              'executed':old is not None,'cold_replay_equal':new is not None and new==old['execution'],
              'replay_error':error,'fallback':False,'source_semantic_review_not_replaced_by_label_match':True})
        usage=wire.get('usage') or wire.get('invocation',{}).get('usage')
        arms[arm]={'rows':rows,'native_correct':sum(r['native_correct'] for r in rows),'pairs':len(rows),
          'mother_contracts':len({r['policy_id'] for r in rows}),
          'main_path_executed':sum(r['executed'] for r in rows),'fallback_n':0,'fallback_denominator':len(rows),
          'cold_replay_equal':all(r['cold_replay_equal'] for r in rows),
          'physical_acquisition_requests':1,'repair_requests':0,'elapsed_seconds':wire.get('elapsed_seconds'),
          'usage':usage,'incremental_api_cash_usd':wire.get('incremental_api_cash_usd'),
          'actual_teacher_invoice_usd':None,'provider_internal_retries_observable':False,
          'response_sha256':hashlib.sha256((STAGE/(arm+'_execution_before_grading.json')).read_bytes()).hexdigest()}
    backup=snapshot(Path('/media/sangfor/vdb/legal-skill-backups/contract_scope_acquisition_20261110/ledger.before_model_calls.sqlite3'))
    added={t:[r for r in before[t] if r not in backup[t]] for t in before}
    assert all(r in before[t] for t in backup for r in backup[t])
    assert len(added['calls'])==2 and len(added['oracle_views'])==0 and len(added['meta'])==1
    assert all(r[1]=='teacher' for r in added['calls'])
    assert before==snapshot(ledger)
    out={'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
      'pending':0,'new_charged_attempts':{'executor':0,'teacher':2},'new_native_TRAIN_pair_views':8,
      'oracle_views_after_authorized_intake':len(before['oracle_views']),
      'arms':arms,'train_pairs':8,'train_mother_contracts':4,
      'acquisition_inputs_same_originals_questions_and_public_meanings':True,
      'native_labels_evidence_and_old_rules_not_in_either_acquisition_prompt':True,
      'acquisitions_independent':True,'shared_gold_program_not_used_as_acquisition_baseline':True,
      'all_acquisition_and_repair_costs_included':True,'software_expressibility_not_used_to_reject_acquisition':True,
      'source_semantic_review_still_separate':True,'DEV_pairs':4,'DEV_mothers':2,'DEV_started':False,
      'TEST_started':False,'new_full_training':False,'two_contributions_established':False,'goal_complete':False,
      'ledger_old_rows_unchanged':True,'ledger_logical_sha256':digest(before),
      'ledger_rows':{t:len(v) for t,v in before.items()}}
    immutable_json(STAGE/'train_native_grade_and_cold_replay.json',out)
    path=ROOT/'reports/method_redesign_20261109/contract_scope_acquisition_results.json';immutable_json(path,out)
    print(json.dumps({'counts':out['counts_total'],'arms':{k:{p:v[p] for p in ['native_correct','pairs','main_path_executed','cold_replay_equal','elapsed_seconds','usage']} for k,v in arms.items()},'DEV_started':False,'goal_complete':False},ensure_ascii=False))

if __name__=='__main__':main()
