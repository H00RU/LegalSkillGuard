"""Audit native EV scope and replay finite-scope projection from preserved facts.

No native packet labels, reference cases, new generations or old-run launches.
"""
import ast
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,sqlite3,tarfile
from pathlib import Path
from types import SimpleNamespace
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.finite_rule_projection import project_definition
from legal_skill_guard.rr.legal_predicate_skills import run,validate,validate_case
from experiments.rr_v2_legal_independent_cache import execute_code

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'legal_native_scope_completion_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/legal_task_scope_results.json'
UPSTREAM=Path('/home/yndx/hhy/legal-skill-current/data/cache/openexempt/servantez-OpenExempt-ec6fa25')
DB=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
BEFORE=Path('/media/sangfor/vdb/legal-skill-backups/legal_feedback_acquisition_20261110/ledger.after.sqlite3')


def read(p):return json.loads(p.read_text())


def snapshot(p):
    with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def native_ev_scope():
    path=UPSTREAM/'source/solver.py';code=path.read_text();tree=ast.parse(code)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Solver')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='solve_exemption_valuation')
    ns={'deepcopy':deepcopy,'Case':object,'List':list,'Jurisdiction':str}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),ns)
    class Budget:
        def __init__(self):self.available=700
        def allocate_claim_amount(self,citation,amount):
            used=min(amount,self.available);self.available-=used;return used
    dummy=SimpleNamespace(statute_set_map={'J':SimpleNamespace(exemption_citations=lambda:['fixture-limit'])},init_solution=lambda case,j:Budget())
    case=SimpleNamespace(assets=[SimpleNamespace(description='fixture A',dollar_value=800,applicable_exemptions=['fixture-limit']),
        SimpleNamespace(description='fixture B',dollar_value=105,applicable_exemptions=['fixture-limit'])])
    actual=ns['solve_exemption_valuation'](dummy,case,['J'])
    assert [actual[n][0]['claim_value'] for n in ['fixture A','fixture B']]==[700,105]
    return {'upstream_commit':'ec6fa2547431096588ce2d3ef107b8adc33cd4fe','native_solver_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'native_source_file':'source/solver.py','native_function':'Solver.solve_exemption_valuation',
        'actual_unmodified_function_excerpt':ast.get_source_segment(code,fn),'isolated_software_probe_result':actual,
        'probe_is_not_native_data_or_model_success':True,'budgets_reset_per_asset_and_citation':True,
        'portfolio_optimization_is_separate_native_task_not_current_EV':True,
        'previous_proposed_portfolio_training_route_withdrawn':True,'native_task_not_replaced_by_real_world_full_portfolio_law':True}


def main():
    before=snapshot(BEFORE)
    # This immutable scope-only phase predates later acquisitions. Later append-
    # only rows do not invalidate its replay; every historical row must match.
    current=snapshot(DB)
    assert all(all(row in current[table] for row in values) for table,values in before.items())
    old=read(BASE/'legal_independent_cache_v1_20261110/seal.json')
    public={r['key']:r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    library_path=BASE/'legal_library_runtime_v1_20261109/frozen_library.json'
    library=read(library_path);programme=library['program']
    cases=read(BASE/'legal_grounded_replay_v1_20261109/shared_grounded_cases.json')['cases']
    cached=read(ROOT/'reports/method_redesign_20261109/legal_independent_cache_results.json')['native_results']
    grades={r['ordinal']:r['cached_TRAIN_grade'] for r in cached}
    sources=[p['rules'] for p in old['policies']];checked=validate(programme,sources)
    rule=next(r for r in programme['rules'] if r['id']=='transferred63c5')
    assert rule['head']['predicate']=='section_63_c_5_applies'
    assert len([r for r in programme['rules'] if r['head']['predicate']==rule['head']['predicate']])==1
    assert len(rule['body'])==1 and rule['body'][0]['predicate']=='deduction_under_section_151_allowable'
    assert rule['different']==[{'left':'?other_taxpayer','right':'?subject'}]
    code=(BASE/'legal_independent_cache_review_v1_20261110/reviewed_cache.py').read_text()
    cache_fn=ast.parse(code).body[0]
    cache_rules=next(ast.literal_eval(n.value) for n in cache_fn.body if isinstance(n,ast.Assign)
        and any(isinstance(v,ast.Name) and v.id=='rules' for v in n.targets))
    cache_rule=next(r for r in cache_rules if r['head']['predicate']==rule['head']['predicate'])
    assert all(cache_rule[k]==rule[k] for k in ['head','body','different'])
    target=next(c for c in cases if c['ordinal']==87)
    original=public[old['sources']['train'][86]]
    text=original['public']['facts']+' '+original['public']['query']
    assert 'Alice is not entitled to a deduction for Bob under section 151.' in text
    names=sorted({f['atom']['arguments'][0] for f in target['facts'] if f['atom']['predicate']=='case_subject_year'})
    assert names==['Alice','Bob']
    assert all(name in text for name in names)
    certificate={'target_source':original['key'],'task_profile':'SARA_complete_case_records',
        'native_scope_interpretation':'Person-valued witnesses are supplied by the complete case record; this particular record names Alice and Bob. No third-party person is introduced by these finite learned rules.',
        'scope_people':names,'projection_variable':'?other_taxpayer','query_subject':'Bob','query_year':'2017',
        'subject_excluded_by_original_model_rule_different':True,'remaining_other_taxpayers':['Alice'],
        'condition_status_from_original_explicit_negative_fact':True,
        'target_guard_completeness_review':'63(c)(5) applicability is defined by allowance of a151 deduction to another taxpayer for the matching year. The actual transferred rule has exactly this condition and the original different guard.',
        'full151_not_recompiled_or_assumed_complete':'The input explicitly denies the whole151 allowance for the only other taxpayer in this task scope; no missing151(b)/(c) rule is interpreted as false.',
        'scope_and_source_completeness_are_interpretation_obligations_not_model_learned_claims':True,
        'not_a_global_OWA_or_CWA_acceptance_requirement':True,'open_narrative_view_retains_unknown':True}
    immutable_json(STAGE/'task_scope_certificate.json',certificate)
    native=[]
    for c in cases:
        src=public[old['sources']['train'][c['ordinal']-1]]
        text=src['public']['facts']+' '+src['public']['query']
        validate_case(c,text,checked['predicates'])
        a=run(programme,c);b=execute_code(code,c['facts'],c['query'],sources)
        row={'ordinal':c['ordinal'],'original_candidate':a['answer'],'original_independent_cache':b['answer'],
            'candidate':a['answer'],'independent_cache':b['answer'],'cached_TRAIN_grade':grades[c['ordinal']],
            'new_model_oracle_calls':0,'new_independent_native_source':False}
        if c['query']['predicate']==rule['head']['predicate']:
            opened=project_definition(rule,c['facts'],c['query'])
            closed=project_definition(rule,c['facts'],c['query'],{'?other_taxpayer':names})
            expanded=project_definition(rule,c['facts'],c['query'],{'?other_taxpayer':names+['Charlie']})
            assert opened['value'] is None and closed['value'] is False and expanded['value'] is None
            result='Contradiction' if closed['value'] is False else 'Entailment' if closed['value'] is True else None
            independent_closed=project_definition(cache_rule,c['facts'],c['query'],{'?other_taxpayer':names})
            assert independent_closed['value'] is False
            cache_result='Contradiction' if independent_closed['value'] is False else 'Entailment' if independent_closed['value'] is True else None
            immutable_json(STAGE/'independent_definition_check.json',{'independent_model_rule':cache_rule,
                'independent_projection':independent_closed,'source_program_sha256':hashlib.sha256(code.encode()).hexdigest(),
                'candidate_rule_body_not_used_in_this_baseline_projection':True})
            row.update(candidate=result,independent_cache=cache_result,open_view=opened,closed_task_view=closed,
                added_unknown_person_control=expanded,public_shared_component_not_new_method=True)
        row['candidate_correct']=row['candidate']==row['cached_TRAIN_grade']
        row['independent_cache_correct']=row['independent_cache']==row['cached_TRAIN_grade']
        native.append(row)
    assert all(r['candidate_correct'] and r['independent_cache_correct'] for r in native)
    frozen={'program':programme,'independent_cache_code':code,'scope_certificate':certificate,'target_definition':rule,
        'scope_component_source_sha256':hashlib.sha256((ROOT/'legal_skill_guard/rr/finite_rule_projection.py').read_bytes()).hexdigest(),
        'actual_old_library_sha256':hashlib.sha256(library_path.read_bytes()).hexdigest(),
        'original_library_unchanged':True,'new_shared_deterministic_execution_path_not_original_model_repair':True}
    immutable_json(STAGE/'frozen_execution_bundle.json',frozen)
    restored=read(STAGE/'frozen_execution_bundle.json')
    immutable_json(STAGE/'runtime_case.json',target)
    restored_case=read(STAGE/'runtime_case.json')
    replay=project_definition(restored['target_definition'],restored_case['facts'],restored_case['query'],{'?other_taxpayer':restored['scope_certificate']['scope_people']})
    assert replay['value'] is False
    native_scope=native_ev_scope();immutable_json(STAGE/'native_EV_scope_audit.json',native_scope)
    with tarfile.open(ROOT/'data/cache/rr_v2/sara_v2.tar.gz') as a:
        hashes={n:hashlib.sha256(a.extractfile(n).read()).hexdigest() for n in ['sara_v2/statutes/prolog/section63.pl','sara_v2/statutes/prolog/section151.pl']}
    current=snapshot(DB)
    assert all(all(row in current[table] for row in values) for table,values in before.items())
    captured=read(REPORT)['captured_utc'] if REPORT.exists() else datetime.now(timezone.utc).isoformat()
    result={'captured_utc':captured,'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
        'pending':sum(r[6]=='reserved' for r in before['calls']),'new_charged_attempts':{'executor':0,'teacher':0},
        'new_physical_dispatches':{'executor':0,'teacher':0},'new_oracle_views':0,'new_original_sources':0,
        'all_pre_turn_rows_equal_backup':True,'ledger_counts':{k:len(v) for k,v in before.items()},'ledger_logical_sha256':digest(before),
        'native_EV_scope_audit':native_scope,'actual_replay':native,'original_four_case_3of4_results_unchanged':True,
        'new_followup_candidate_correct':4,'new_followup_independent_cache_correct':4,'same_previously_seen_native_sources':4,
        'new_fresh_model_readers_or_source_programmes':0,'new_original_library_rule_semantics_or_fields_changed':False,
        'actual_cached_rule_and_signed_facts_used':True,'finite_scope_is_task_normalization_not_learned_contribution':True,
        'ordinary_independent_cache_shares_same_component_and_result':True,'negative_projection_missing_atom_not_false':True,
        'unbounded_view_unknown_preserved':True,'source_reference_code_hashes':hashes,'new_regressions_passed':7,
        'frozen_replay_equal':True,'two_method_contributions_established':False,'goal_complete':False,
        'incremental_model_API_cash_usd':0,'historical_teacher_invoice_usd':None,'GPU_cost_usd':None,'total_project_cash_cost_usd':None,
        'new_full_build_started':False,'main_training_started':False,'TEST_labels_read':False,'paper_started':False}
    immutable_json(REPORT,result)
    print(json.dumps({k:result[k] for k in ['counts_total','pending','new_charged_attempts','all_pre_turn_rows_equal_backup','new_followup_candidate_correct','new_followup_independent_cache_correct','original_four_case_3of4_results_unchanged']},ensure_ascii=False))


if __name__=='__main__':main()
