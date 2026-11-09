"""Offline repair over real learned call/negative input; no new supervision."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,sqlite3,time
from pathlib import Path
import z3
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.legal_predicate_skills import evaluate_guard,run
ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'artifacts/rr_method_redesign_20261109'
OUT=A/'legal_guard_call_repair_v1_20261109'
REPORT=ROOT/'reports/method_redesign_20261109'


def read(p):return json.loads(p.read_text())


def ledger():
 with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
  tables={t:c.execute('select * from '+t+' order by 1').fetchall() for t in ('calls','meta','oracle_views')}
  assert c.execute("select count(*) from calls where status='reserved'").fetchone()[0]==0
  counts=dict(c.execute('select role,count(*) from calls group by role'))
 return {'sha256':hashlib.sha256(json.dumps(tables,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'counts_total':counts}


def main():
 before=ledger();program=read(A/'legal_grounded_replay_v1_20261109/frozen_library.json')['program']
 cases=read(A/'legal_grounded_replay_v1_20261109/shared_grounded_cases.json')['cases']
 real=next(c for c in cases if c['ordinal']==87);source=read(A/'legal_relations_exceptions_native_v3_20261109/seal.json')['cases'][-1]
 assert source['ordinal']==87
 rule=next(r for r in program['rules'] if r['id']=='transferred63c5')
 assert rule['guard_quote'] in source['rules']
 negative=next(r for r in real['facts'] if r['atom']['predicate']=='deduction_under_section_151_allowable')
 assert negative['atom']=={'predicate':'deduction_under_section_151_allowable','arguments':['Alice','Bob','2017'],'positive':False}
 assert negative['quote'] in source['facts']
 files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['legal_skill_guard/rr/legal_predicate_skills.py','experiments/rr_v2_legal_guard_call_replay.py','tests/test_rr_legal_guard_call.py']}
 preserved={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [A/'legal_relations_exceptions_native_v3_20261109/facts.json',A/'legal_grounded_replay_v1_20261109/execution.json',REPORT/'legal_native_pilot_grades.json']}
 seal={'files':files,'preserved':preserved,'question':'Can a real explicitly negative callee input settle its quoted point guard without inventing callee rules or universalizing a single claimant?','no_new_model_or_oracle_calls':True,'native87_not_a_new_success':True,'goal_complete':False}
 immutable_json(OUT/'seal.json',seal)
 start=time.monotonic();bound=deepcopy(real);bound['query']['arguments']=['Alice','Bob','2017']
 old=run(program,bound);point=evaluate_guard(program,bound,'transferred63c5')
 native=evaluate_guard(program,real,'transferred63c5')
 finite=evaluate_guard(program,real,'transferred63c5',domains={0:['Alice']})
 larger=evaluate_guard(program,real,'transferred63c5',domains={0:['Alice','UnrepresentedClaimant']})
 assert old['answer'] is None and point['condition_value'] is False
 assert native['condition_value'] is None and finite['condition_value'] is False and larger['condition_value'] is None
 reference=evaluate_guard(deepcopy(program),deepcopy(bound),'transferred63c5');assert point==reference
 # Unresolved d3 percentage cannot change a source d2 zero amount. This is a
 # common arithmetic obligation, not a learned new rule or full-policy proof.
 percentage=z3.Int('unresolved_percentage');solver=z3.Solver();solver.add((0*(100-percentage))/100!=0)
 assert solver.check()==z3.unsat
 all_original=[]
 previous=read(A/'legal_grounded_replay_v1_20261109/execution.json')['cases']
 for c in cases:
  output=run(program,c);saved=next(r for r in previous if r['ordinal']==c['ordinal'])['actual']
  assert output==saved
  all_original.append({'ordinal':c['ordinal'],'answer':output['answer'],'unchanged':True})
 elapsed=time.monotonic()-start
 immutable_json(OUT/'call_contract_library.json',{'rule':rule,'learned_signature':next(p for p in program['predicates'] if p['name']==rule['head']['predicate']),'origin':'real source-only TRAIN151(d)(2) program with exact63(c)(5) antecedent reuse; unchanged','semantic_status':'evaluation of the antecedent, not contraposition of a generic Horn rule'})
 restored=read(OUT/'call_contract_library.json');assert restored['rule']==rule
 after=ledger();assert before==after
 for p,h in preserved.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
 out={'captured_utc':datetime.now(timezone.utc).isoformat(),'actual_negative_input':negative,'source_guard':rule['guard_quote'],
      'ground_call_before':old,'ground_call_after':point,'original_unbounded_native87':native,
      'finite_formal_question_not_native87':finite,'larger_formal_scope_not_a_TRAIN_case':larger,
      'native_predictions':all_original,'native_scoring_repeated':False,'native87_core_success':False,
      'missing151ab_needed_for_this_ground_call':False,'full_unbounded_scope_or_source_completion_claimed':False,
      'same_information_ordinary_guard_evaluator_equal':point==reference,'independent_contribution_established':False,
      'zero_amount_percentage_omission_check':{'status':'unsat','claim':'Zero reduced by any integer percentage stays zero','not_full_policy_completion':True},
      'new_rules_or_facts_inserted':False,'new_model_calls':0,'new_oracle_views':0,'new_sources':0,
      'elapsed_seconds':elapsed,'ledger_before':before,'ledger_after':after,'frozen_library_exact_reload':True,
      'goal_complete':False}
 immutable_json(OUT/'results.json',out)
 print(json.dumps({'actual_bound_guard':point['condition_value'],'native87':native['condition_value'],'original_predictions':all_original,'ordinary_control_equal':True,'new_model_calls':0,'ledger':after,'elapsed_seconds':elapsed},ensure_ascii=False))

if __name__=='__main__':main()
