"""Actual cached-law reuse, source-only reference checks and one raw control.

The diagnostic mutant tests sufficiency of the existing seven obligations. It
is never a model output, learned repair, new native case or installed artifact.
"""
import ast
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,sqlite3,tarfile
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.python_scalar_module import compile_function
from legal_skill_guard.rr.semantic_contracts import compare_modules,evaluate
from legal_skill_guard.rr.source_obligations import compile_module,verify

ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'reports/method_redesign_20261109'
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
SCOPE=BASE/'legal_scope_replay_v1_20261110'
PLAIN=BASE/'legal_plain_python_v1_20261110'


def read(path):return json.loads(path.read_text())


def main():
    scoped=read(SCOPE/'execution_closed_before_grading.json');grade=read(SCOPE/'TRAIN_grade.json')
    s=read(PLAIN/'seal.json');result=read(PLAIN/'executor.json');wire=result['physical_response']
    assert grade['correct'] and grade['prediction_closed_before_label']
    assert result['validation']['status']=='compiled_source_contract_control'
    assert result['source_obligations']['all_supplied_obligations_verified'] is False
    assert result['reference_comparison']['equivalent_over_supplied_domain'] is False
    for stage in (SCOPE,PLAIN):
        seal=read(stage/'seal.json')
        for path,expected in seal['files'].items():
            assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
        protocol=REPORT/('legal_scope_replay_protocol.md' if stage==SCOPE else 'legal_plain_python_protocol.md')
        assert hashlib.sha256(protocol.read_bytes()).hexdigest()==seal['protocol_sha256']
    old=BASE/'redesign_source_roles_v1_20261109/teacher_sara63_basic_deduction.json'
    assert hashlib.sha256(old.read_bytes()).hexdigest()==read(SCOPE/'seal.json')['raw_module_sha256']
    # This records sufficiency of the current checks, not a model repair.
    tree=ast.parse(wire['content'])
    class FixTwoNumericMisreads(ast.NodeTransformer):
        def visit_BinOp(self,node):
            node=self.generic_visit(node)
            if isinstance(node.op,ast.Mult) and isinstance(node.left,ast.Constant) and node.left.value==200:
                node.left=ast.copy_location(ast.Constant(2),node.left)
            return node
        def visit_IfExp(self,node):
            node=self.generic_visit(node)
            if isinstance(node.test,ast.Name) and node.test.id=='is_2018_through_2025_taxable_year' and isinstance(node.body,ast.Constant) and isinstance(node.orelse,ast.Constant) and (node.body.value,node.orelse.value)==(18000,3000):
                node.body=ast.copy_location(ast.Constant(12000),node.body)
            return node
    mutant_code=ast.unparse(ast.fix_missing_locations(FixTwoNumericMisreads().visit(tree)))+'\n'
    (PLAIN/'diagnostic_only_mutant_NOT_model_output.py').write_text(mutant_code)
    compiled=compile_function(mutant_code,s['signature'])
    value=deepcopy(s['teacher_reference']);value['expression']=compiled['expression']
    module=compile_module(value,s['policy']);checks=verify(module)
    assert checks['all_supplied_obligations_verified']
    comparison=compare_modules(compiled['expression'],s['teacher_reference']['expression'],s['signature'],s['teacher_reference']['domain'])
    assert not comparison['equivalent_over_supplied_domain']
    binding={k:False if t=='boolean' else 10000 for k,t in s['signature'].items()}
    binding['is_c5_dependent']=True
    actual=evaluate(compiled['expression'],s['signature'],binding)
    expected=evaluate(s['teacher_reference']['expression'],s['signature'],binding)
    assert (actual,expected)==(10250,3000)
    # An ordinary counterfactual-base clamp already repairs this isolated bug.
    class DisableDependent(ast.NodeTransformer):
        def visit_Name(self,node):
            return ast.copy_location(ast.Constant(False),node) if node.id=='is_c5_dependent' else node
    base=ast.unparse(ast.fix_missing_locations(DisableDependent().visit(ast.parse(compiled['expression'],mode='eval')).body))
    ordinary_clip='min(('+compiled['expression']+'),('+base+'))'
    clip_check=compare_modules(ordinary_clip,s['teacher_reference']['expression'],s['signature'],s['teacher_reference']['domain'])
    assert clip_check['equivalent_over_supplied_domain']
    diagnostic={'kind':'offline_checker_sufficiency_probe_not_a_model_repair',
        'actual_raw_executor_program_not_changed':True,'diagnostic_mutant_changes':['200 percent mis-scaling','B/C substitution value confusion'],
        'diagnostic_mutant_still_has_cap_composition_error':True,'seven_original_obligations':checks,
        'full_reference_comparison':comparison,'explicit_symbolic_software_counterexample':{'binding':binding,'mutant_value':actual,'correct_cache_value':expected},
        'interpretation':'Passing all seven supplied source properties is insufficient: a cap cannot increase an already smaller nominal amount. The full reference check still rejects the program.',
        'ordinary_base_clipping_full_domain_check':clip_check,
        'ordinary_clipping_not_a_new_learned_mechanism':True,'new_native_examples':0,'used_to_repair_or_score_a_model_as_passed':False}
    immutable_json(PLAIN/'checker_sufficiency_diagnostic.json',diagnostic)
    # Only policy implementation members are read; no official case/label file.
    members={}
    with tarfile.open(ROOT/'data/cache/rr_v2/sara_v2.tar.gz') as archive:
        for section in ('2','152','63'):
            name=f'sara_v2/statutes/prolog/section{section}.pl';blob=archive.extractfile(name).read();text=blob.decode()
            members[name]={'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob)}
            if section=='2':
                body=text[text.index('s2_b_3_B(Taxp,Dependent,Taxy) :-'):]
                assert all('s152_d_2_'+k+'(' in body for k in 'ABCDEFGH')
            if section=='63':
                assert 's63_c_7_ii(Taxy,Amount) :-\n    Taxy>2017,\n    Taxy<2026,\n    Amount is 12000.' in text
    reference={'source_implementation_members_only':members,'case_or_test_labels_read_from_archive':False,
        'formal_reference_not_sent_to_models_or_used_to_create_the_recovered_program':True,
        'section63_reference_checked_after_execution_closed':True,
        '63_c_7_ii_is_year_to_local_amount_not_full_taxpayer_deduction':True,
        '2_b_3_B_explicitly_checks_alternative_non_H_relationship_paths':True,
        'counterfactual_or_reason_preservation_not_new_capability_over_full_correct_cache':True,
        'no_new_but_for_model_requests':True,
        'primary_sources':[
            'https://a3nm.net/work/seminar/slides/20210909-holzenberger.pdf',
            'https://github.com/SgfdDttt/sara_v2',
            'https://book.catala-lang.org/en/5-3-scopes-toplevel.html',
            'https://book.catala-lang.org/en/5-4-definitions-exceptions.html',
            'https://law.mit.edu/pub/aidrivenstatutoryreasoning/release/1'],
        'interpretation':'SARA already treats this counterfactual; Catala has scoped calls/states/defaults, and the2024 software-engineering article uses the same63 base-substitution/doubling example. Do not claim these operations as new.'}
    immutable_json(SCOPE/'source_implementation_review.json',reference)
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        snapshot={t:db.execute('select * from '+t+' order by 1').fetchall() for t in ('calls','meta','oracle_views')}
        counts=dict(db.execute('select role,count(*) from calls group by role'))
        pending=db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    historical=deepcopy(snapshot)
    historical['calls']=[x for x in historical['calls'] if not x[0].startswith('legal_plain_python_v1_20261110:')]
    historical['meta']=[x for x in historical['meta'] if x[0] not in ('method_runtime_policy:legal_scope_replay_v1_20261110','method_runtime_policy:legal_plain_python_v1_20261110')]
    historical['oracle_views']=[x for x in historical['oracle_views'] if (x[0],x[1])!=(grade['source'],grade['view_hash'])]
    assert digest(historical)==scoped['ledger_before']['logical_sha256']
    assert counts=={'executor':1376,'teacher':59} and pending==0
    service=Path('/proc/958223/stat').read_text()
    start_ticks=int(service[service.rindex(')')+2:].split()[19]);assert start_ticks==486445918
    clients=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:argv=(proc/'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError,PermissionError,ProcessLookupError):continue
        if b'-m' in argv and any(a.startswith(b'experiments.rr_v2_legal_') for a in argv):clients.append(int(proc.name))
    assert clients==[]
    admission={'compiled':True,'execution_checked':True,'semantic_admission':'rejected',
        'existing_source_obligations_verified':5,'existing_source_obligations_refuted':2,
        'full_domain_teacher_reference_equivalence':False,
        'raw_program_entered_learning_or_active_library':False,
        'new_native_success_from_this_executor_program':False,'goal_complete':False}
    immutable_json(PLAIN/'semantic_admission.json',admission)
    out={'captured_utc':datetime.now(timezone.utc).isoformat(),'counts_total':counts,'pending':pending,
        'new_charged_attempts':{'executor':1,'teacher':0},'new_physical_dispatches':{'executor':1,'teacher':0},
        'new_TRAIN_oracle_views':1,'all_pre_turn_rows_preserved_sha256':digest(historical),
        'current_research_clients':clients,'original_model_service':{'pid':958223,'start_ticks':start_ticks,'unchanged':True},
        'current_full_ledger_logical_sha256':digest(snapshot),'original_source_module_unchanged':True,
        'source_cache_replay':{'original_TRAIN_ordinal':85,'prediction':grade['prediction'],'correct':grade['correct'],
                               'ordinary_cache_also_correct':True,'fallback_used':False,'model_calls':0,
                               'historical_four_case_predictions_or_scores_changed':False},
        'ordinary_python_control':{'compiled':True,'semantic_admission':'rejected','finish_reason':wire['finish_reason'],
            'thinking_requested':wire['thinking_requested'],'input_tokens':wire['usage']['prompt_tokens'],
            'output_tokens':wire['usage']['completion_tokens'],'elapsed_seconds':wire['elapsed_seconds'],
            'source_role_contract_supplied_from_previous_teacher':True,
            'independent_role_learning_or_complete_native_reasoning_tested':False},
        'checker_sufficiency_probe':{'all7_properties_pass_but_program_wrong':True,'ordinary_clipping_is_sufficient_for_isolated_cap_bug':True},
        'new_method_contribution_established':False,'but_for_candidate_not_promoted':True,
        'new_source_or_seed_added':False,'TEST_started':False,'main_training_started':False,
        'known_incremental_executor_API_cash_usd':0,'GPU_cash_cost_usd':None,'teacher_actual_prior_invoice_usd':None,
        'total_project_cash_cost_usd':None,'new_teacher_model_tokens':0,'goal_complete':False}
    (REPORT/'legal_scope_and_python_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
