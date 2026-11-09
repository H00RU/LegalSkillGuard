"""Actual-source dependency slice and countermodel; no model/label access.

The alternative formal worlds are diagnostic possibilities of the current
abstraction. They are not new TRAIN cases, legal facts, or scoring labels.
"""
from datetime import datetime,timezone
import hashlib,json,re,sqlite3
from pathlib import Path
import z3
ROOT=Path(__file__).resolve().parents[2]
A=ROOT/'artifacts/rr_method_redesign_20261109'
REPORT=ROOT/'reports/method_redesign_20261109'

def read(p):return json.loads(p.read_text())

def main():
 s=read(A/'legal_relations_exceptions_native_v3_20261109/seal.json')
 program=read(A/'legal_grounded_replay_v1_20261109/frozen_library.json')['program']
 case=next(c for c in read(A/'legal_grounded_replay_v1_20261109/shared_grounded_cases.json')['cases'] if c['ordinal']==87)
 public=next(c for c in s['cases'] if c['ordinal']==87)
 known_negative=[r for r in case['facts'] if not r['atom']['positive']]
 assert len(known_negative)==1 and known_negative[0]['atom']['arguments']==['Alice','Bob','2017']
 target=case['query']['predicate'];queue=[target];seen=set();slice_rules=[]
 while queue:
  p=queue.pop()
  if p in seen:continue
  seen.add(p)
  for r in program['rules']:
   if r['head']['predicate']==p:
    slice_rules.append({'id':r['id'],'authority':r['authority'],'head':r['head'],'body':r['body'],'quote':r['quote']})
    queue.extend(a['predicate'] for a in r['body'])
 source151=next(p['rules'] for p in s['policies'] if p['section']==151)
 def source_span(begin,end):
  a=source151.index(begin);b=source151.index(end,a);return {'quote':source151[a:b].strip(),'start':a,'end':b}
 missing=[{'authority':'151(a)','role':'Exemptions provided by151 become deductions','source':source_span('(a) Allowance','(b) Taxpayer'),'compiled_rule':False},
          {'authority':'151(b)','role':'A separate spouse-exemption/deduction constructor not represented by151(c)','source':source_span('(b) Taxpayer','(c) Additional'),'compiled_rule':False}]
 # All these are logical possibilities of an incomplete input abstraction,
 # never assertions about the actual case or its native benchmark label.
 alice_allowed=z3.Bool('Alice_allowable_for_Bob_2017')
 other_allowed=z3.Bool('unrepresented_claimant_allowable_for_Bob_2017')
 solver=z3.Solver();solver.add(z3.Not(alice_allowed));exists=z3.Or(alice_allowed,other_allowed)
 models=[]
 for value in (False,True):
  solver.push();solver.add(exists==value);status=solver.check();model=solver.model() if status==z3.sat else None
  models.append({'exists':value,'status':str(status),'Alice_allowed':z3.is_true(model.eval(alice_allowed)) if model else None,'other_allowed':z3.is_true(model.eval(other_allowed)) if model else None});solver.pop()
 assert all(m['status']=='sat' for m in models)
 source_code=(ROOT/'legal_skill_guard/rr/legal_predicate_skills.py').read_text()
 assert "if None in q[1]:refute=z3.BoolVal(False)" in source_code
 with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
  counts=dict(db.execute('select role,count(*) from calls group by role'));assert db.execute("select count(*) from calls where status='reserved'").fetchone()[0]==0
 out={'captured_utc':datetime.now(timezone.utc).isoformat(),'ordinal':87,'public_input_sha256':hashlib.sha256(json.dumps(public,sort_keys=True).encode()).hexdigest(),'actual_query':case['query'],'actual_explicit_negative':known_negative,'actual_dependency_slice':slice_rules,'missing_source_dependencies':missing,
 'named_person_domain':sorted({r['atom']['arguments'][0] for r in case['facts'] if r['atom']['predicate']=='case_subject_year'}),
 'domain_completeness_established_by_current_interface':False,'source_program_has_unresolved_sections':program['unresolved'],
 'solver_gap':'Negative existential projection is disabled unconditionally, even if an appropriate complete scope could later be established. This is an implementation limitation, not a model prediction error.',
 'source_gap':'The local151(c)-only deduction constructor is not a complete implementation of the whole151 dependency referenced by63(c)(5). Missing translated source must not be treated as false.',
 'abstraction_countermodels':models,'countermodels_are_new_data_or_supervision':False,
 'interpretation_limit':'This establishes only that one explicit negative does not logically fix an unrepresented claimant in the current abstraction. It does not prove the native SARA case ambiguous, add a perfect-anchor requirement, or justify mapping all unknowns to Contradiction.',
 'minimum_next_fix':'Establish task-native closure/scope from the actual benchmark execution contract and finish the required source dependency or justify its irrelevance; then implement negative projection within that declared scope. Do not add a blanket unknown-to-false adapter.',
 'related_functional_output_risk':'The local program leaves151(d)(3) and the151(d)(5) period test unresolved. A general amount cannot be called full-policy stable merely because the local rule set has one result. Native72 has an independently active source zero exception, but no whole-policy completion claim is made.',
 'official_task_sources':[{'url':'https://nlp.jhu.edu/law/sara_v2/','supports':'Binary applicability output format, not an automatic completeness certificate for a partial learned IR.'},{'url':'https://hazyresearch.stanford.edu/legalbench/tasks/sara_entailment.html','supports':'Native task is binary entailment classification, not an added three-class benchmark.'}],
 'current_predictions_or_grades_modified':False,'counts_total':counts,'new_model_calls':0,'new_oracle_views':0,'new_sources':0,'TEST_opened':False,'goal_complete':False}
 (REPORT/'legal_87_closure_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'dependencies':[r['id'] for r in slice_rules],'missing':[m['authority'] for m in missing],'formal_countermodels':models,'new_calls':0,'predictions_unchanged':True},ensure_ascii=False))
if __name__=='__main__':main()
