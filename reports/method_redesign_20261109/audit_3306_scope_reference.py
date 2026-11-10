"""Execute exact native scope clauses on explicit admitted-wage fixtures.

No native case/goal/label is opened. Public TRAIN73 supplies only the two directed
payment/service identities. Admission, payment-year and cash variables are varied
as SOFTWARE COMPLETIONS; they are not supplied as missing facts for that case.
"""
from datetime import datetime,timezone
import hashlib,json,os,re,sqlite3,subprocess,tarfile,tempfile
from pathlib import Path
import z3
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'legal_3306_scope_reference_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/legal_3306_scope_results.json'
RUNTIME=Path('/home/yndx/hhy/legal-skill-rr-v2/.local-tools/rr-v2-swipl/root/usr')
EXPECTED='6d283f999cfb578d704aa5586a593dd78b89b834006d4277af81f2008a094455'
NAMES=['s3306_a_1_is_wages','s3306_a_1_A','s3306_a_1_is_day_of_employment',
       's3306_a_3_is_wages','s3306_a_3','s3306_a_4']


def read(p):return json.loads(p.read_text())


def ledger():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def exact_clause(text,name):
    start=re.search(r'^'+re.escape(name)+r'\(',text,re.M).start()
    # These six inspected native clauses have no interior end-of-line full stop.
    # Extract byte-identical source, rather than translating their legal logic.
    end=re.search(r'\.[ \t]*(?:%[^\n]*)?$',text[start:],re.M).end()+start
    return {'name':name,'start_character':start,'end_character':end,'text':text[start:end]}


FIXTURE=r'''
:- dynamic inputs/5.
% s3306_b is an admitted-wage input relation ONLY in this isolated fixture.
% No values below are asserted to be the native case's missing payment dates.
s3306_b(3200,domestic_payment,domestic_service,"Alice","Bob","Alice","Bob",_) :- inputs(_,_,1,_,_).
s3306_b(4500,other_payment,other_service,"Bob","Alice","Bob","Alice",_) :- inputs(_,_,_,1,_).
purpose_(domestic_service,"domestic service").
purpose_(other_service,"work").
start_(domestic_payment,payyear(Y)) :- inputs(Y,_,_,_,_).
start_(other_payment,payyear(Y)) :- inputs(_,Y,_,_,_).
first_day_year(Y,lower(Y)).
last_day_year(Y,upper(Y)).
is_before(payyear(Y),upper(Z)) :- Y=<Z.
is_before(lower(Z),payyear(Y)) :- Z=<Y.
means_(domestic_payment,"cash") :- inputs(_,_,_,_,1).
means_(domestic_payment,"hay") :- inputs(_,_,_,_,2).
s3306_c(domestic_service,"Alice","Bob",possible_workday,2018).
s3306_c(other_service,"Bob","Alice",possible_workday,2018).
main :-
 forall((member(DY,[2016,2017,2018,2019]),member(OY,[2016,2017,2018,2019]),
         member(DA,[0,1]),member(OA,[0,1]),member(Cash,[0,1,2])),
   (retractall(inputs(_,_,_,_,_)),assertz(inputs(DY,OY,DA,OA,Cash)),
    (s3306_a_1_A("Alice",2018,_)->AW=1;AW=0),
    (s3306_a_1_A("Bob",2018,_)->BW=1;BW=0),
    findall(D,s3306_a_1_is_day_of_employment("Alice",_,D),Days),length(Days,ND),
    (s3306_a_3("Alice",_,DW,2018)->Domestic=1;DW=0,Domestic=0),
    (s3306_a_4()->A4=1;A4=0),
    format('~d ~d ~d ~d ~d ~d ~d ~d ~d ~d ~d~n',[DY,OY,DA,OA,Cash,AW,BW,ND,DW,Domestic,A4]))).
'''


def symbolic_upper_bound():
    # Membership in the year window and wage admission are unconstrained. The
    # native helper's actor/service predicates alone exclude both rows for Alice.
    eligible=z3.Bools('domestic_admitted other_admitted')
    periods=z3.Bools('domestic_in_window other_in_window')
    cash=z3.Bool('domestic_cash')
    rows=[('Alice','domestic service',3200),('Bob','work',4500)]
    def scoped(person):
        return z3.Sum(*[z3.If(z3.And(e,t,z3.BoolVal(p==person),z3.BoolVal(k not in ['domestic service','agricultural labor'])),a,0)
            for (p,k,a),e,t in zip(rows,eligible,periods)])
    general=scoped('Alice')>=1500
    domestic=z3.And(eligible[0],periods[0],cash,z3.IntVal(3200)>=1000)
    bad_global=z3.Or(general,domestic)
    solver=z3.Solver();solver.add(scoped('Alice')!=0);zero=solver.check();assert zero==z3.unsat
    solver=z3.Solver();solver.add(bad_global!=general);bad=solver.check();assert bad==z3.sat
    model=solver.model();return {'Alice_general_wage_sum_nonzero_is_unsatisfiable':str(zero),
        'all_payment_period_and_admission_booleans_unconstrained':True,
        'no_new_payment_date_or_cash_fact_filled':True,
        'flattened_status_has_a_counterexample':str(bad),
        'counterexample_is_software_completion_not_native_facts':{str(x):str(model.eval(x,model_completion=True)) for x in [*eligible,*periods,cash]},
        'not_a_whole_native_source_fidelity_certificate':True}


def main():
    before=ledger()
    with tarfile.open(ROOT/'data/cache/rr_v2/sara_v2.tar.gz') as archive:
        raw=archive.extractfile('sara_v2/statutes/prolog/section3306.pl').read()
    assert hashlib.sha256(raw).hexdigest()==EXPECTED;source=raw.decode()
    clauses=[exact_clause(source,n) for n in NAMES]
    assert 'all 3 types of employer are kept separate' in source
    programme='\n\n'.join(c['text'] for c in clauses)+'\n\n'+FIXTURE
    environment=dict(os.environ);environment['SWI_HOME_DIR']=str(RUNTIME/'lib/swi-prolog')
    environment['LD_LIBRARY_PATH']=str(RUNTIME/'lib')+(':'+environment['LD_LIBRARY_PATH'] if environment.get('LD_LIBRARY_PATH') else '')
    binary=RUNTIME/'bin/swipl';assert binary.is_file()
    version=subprocess.run([str(binary),'--version'],env=environment,capture_output=True,text=True,check=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix='lsg-scope-reference-') as temp:
        path=Path(temp)/'scope.pl';path.write_text(programme)
        result=subprocess.run([str(binary),'-q','-f','none','-s',str(path),'-g','main','-t','halt'],
            env=environment,capture_output=True,text=True,timeout=20)
    if result.returncode or 'ERROR' in result.stderr:raise RuntimeError('exit='+str(result.returncode)+' stdout='+result.stdout[-300:]+' stderr='+result.stderr[-3000:])
    cols=['domestic_year_completion','other_year_completion','domestic_admission','other_admission','cash_mode',
        'Alice_general_A_status','Bob_general_A_status','Alice_general_day_witness_count','Alice_domestic_wages','Alice_domestic_status','a4_invariant']
    rows=[dict(zip(cols,map(int,line.split()))) for line in result.stdout.splitlines() if line.strip()]
    assert len(rows)==192 and all(r['Alice_general_A_status']==r['Alice_general_day_witness_count']==0 for r in rows)
    for r in rows:
        assert r['Bob_general_A_status']==int(bool(r['other_admission'] and r['other_year_completion'] in [2017,2018]))
        expected=bool(r['domestic_admission'] and r['domestic_year_completion'] in [2017,2018] and r['cash_mode']!=2)
        assert r['Alice_domestic_status']==int(expected) and r['a4_invariant']==1
    possible=[r for r in rows if r['Alice_domestic_status']==1];assert possible
    symbolic=symbolic_upper_bound();inspection=read(BASE/'legal_3306_scope_inspection_v1_20261110/source_scope_and_existing_input.json')
    stage={'original_native_source_sha256':EXPECTED,'source_archive_member':'sara_v2/statutes/prolog/section3306.pl',
        'native_case_or_goal_or_label_read':False,'exact_native_clauses':clauses,'fixture_programme':programme,
        'runtime_version':version,'runtime_binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
        'software_completions':rows,'native_clause_execution_stdout':result.stdout,'stderr':result.stderr,
        'SMT_evidence':symbolic,'public_case_basis':inspection['existing_cases'][0]}
    immutable_json(STAGE/'native_reference_and_fixtures.json',stage)
    assert before==ledger()
    report={'captured_utc':datetime.now(timezone.utc).isoformat(),'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
        'pending':0,'new_model_calls':0,'new_oracle_views':0,'new_native_grades':0,'new_original_sources':0,
        'ledger_rows_unchanged':True,'ledger_logical_sha256':digest(before),
        'native_scope_clauses_executed_unmodified':NAMES,'native_reference_separates_three_employer_concepts':True,
        'native_a4_is_invariant_due_to_that_separation':True,'software_completions_not_native_cases':len(rows),
        'Alice_general_scope_excludes_domestic_and_incoming_payment_in_all_completions':True,
        'Alice_domestic_status_possible_but_not_newly_established_for_native_case':True,
        'SMT_evidence':symbolic,'plain_subsection_cache_representation_already_sufficient_for_this_scope_distinction':True,
        'model_acquisition_of_that_cache_not_tested_by_gold_reference_replay':True,
        'existing_learned_3306_programme_covers_annual_b1_component_not_full_a_b_c':True,
        'scope_tags_alone_not_promoted_as_a_new_contribution':True,
        'no_extra_quarter_requirement_or_missing_date_assumption_added':True,
        'two_method_contributions_established':False,'goal_complete':False,'main_training_started':False,
        'TEST_labels_read':False,'paper_started':False}
    immutable_json(REPORT,report)
    print(json.dumps({k:report[k] for k in ['counts_total','new_model_calls','ledger_rows_unchanged','software_completions_not_native_cases','native_reference_separates_three_employer_concepts','model_acquisition_of_that_cache_not_tested_by_gold_reference_replay']},ensure_ascii=False))


if __name__=='__main__':main()
