"""Replay four existing fixed nda-11 responses without opening native labels."""
import ast,base64,hashlib,importlib.util,json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.source_code import SourceCodeError
from legal_skill_guard.rr.pal_frontend import parse_pal as current_parse
from legal_skill_guard.rr.scoped_program import compile_query
from legal_skill_guard.rr.ir_types import IRTypeError

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'artifacts/rr_method_redesign_20261109/recorded_contract_failure_audit_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/recorded_contract_failure_results.json'
TARGETS={111:'ContractNLI:4d4e550ac17660215ea791c0b3a37cbef136c2e7642e6cbeb3cc9a3df43eeb40',
         115:'ContractNLI:62fda7e904de3c7f48fe38d41908127e324a6a8da77d21d4465816e57cf90f54'}


def ledger():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    before=ledger();rows=[]
    seal=json.loads((ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v8_20261109/seal.json').read_text())
    parser_hashes={}
    for path in ['legal_skill_guard/rr/pal_frontend.py','legal_skill_guard/rr/source_code.py']:
        actual=STAGE/'historical_pal_frontend.py' if path.endswith('/pal_frontend.py') else ROOT/path
        sha=hashlib.sha256(actual.read_bytes()).hexdigest()
        assert sha==seal['files'][path],path
        parser_hashes[path]=sha
    spec=importlib.util.spec_from_file_location('legal_skill_guard.rr._recorded_pal_reader',STAGE/'historical_pal_frontend.py')
    historical=importlib.util.module_from_spec(spec);spec.loader.exec_module(historical)
    for ordinal,key in TARGETS.items():
        calls=[row for row in before['calls'] if row[0].startswith('method_runtime_reference_v8_20261109:build:') and row[4]==key]
        assert len(calls)==2
        for row in calls:
            cid=row[0];result=json.loads(row[8]);directory=Path(result['artifact_directory'])
            sent_wire=json.loads((directory/'wire_request.json').read_text())
            sent_bytes=base64.b64decode(sent_wire['body_b64'])
            assert hashlib.sha256(sent_bytes).hexdigest()==sent_wire['body_sha256']
            sent=json.loads(sent_bytes)
            received=json.loads(base64.b64decode(json.loads((directory/'wire_response.json').read_text())['body_b64']))
            assert received['choices'][0]['message']['content']==result['content']
            assert received['choices'][0]['finish_reason']==result['finish_reason']
            assert sent['chat_template_kwargs']['enable_thinking'] is False and result['thinking_requested'] is False
            assert sent['temperature']==0.6 and sent['top_p']==0.95 and sent['top_k']==20 and sent['seed']==45 and sent['max_tokens']==8192
            code=result['content'];current=json.loads(sent['messages'][-1]['content'])['CURRENT']
            units={u['id']:u for u in current['units']}
            try:historical.parse_pal(code)
            except SourceCodeError as error:diagnostic=str(error)
            else:raise AssertionError('A historical rejected program unexpectedly parses')
            try:tree=ast.parse(code)
            except SyntaxError:tree=None
            declarations=[];quoted_query_ids=[];constant_membership=[]
            if tree is not None:
                for statement in tree.body:
                    if isinstance(statement,ast.FunctionDef):
                        declarations.append(statement.name)
                        for decorator in statement.decorator_list:
                            if isinstance(decorator,ast.Call):
                                for arg in decorator.args:
                                    if isinstance(arg,ast.Constant) and arg.value in units and units[arg.value]['role']=='query':quoted_query_ids.append(arg.value)
                for node in ast.walk(tree):
                    if isinstance(node,ast.Compare) and len(node.ops)==1 and isinstance(node.ops[0],ast.In) and isinstance(node.left,ast.Constant) and isinstance(node.comparators[0],ast.Constant):
                        left,right=node.left.value,node.comparators[0].value
                        if isinstance(left,str) and isinstance(right,str):
                            constant_membership.append({'left':left,'right':right,'value':left in right,
                                'right_is_native_hypothesis_not_document':any(u['role']=='query' and u['text']==right for u in units.values())})
            one={'TRAIN_ordinal':ordinal,'call_id':cid,'attempt':int(cid.rsplit(':',1)[1]),'source':key,
                 'finish_reason':result['finish_reason'],'usage':result['usage'],'elapsed_seconds':result['elapsed_seconds'],
                 'thinking_requested':False,'parser_error_replayed':diagnostic,
                 'duplicate_function_names':sorted({n for n in declarations if declarations.count(n)>1}),
                 'query_source_ids_used_as_rule_ownership':sorted(set(quoted_query_ids)),
                 'constant_string_membership_tests':constant_membership,
                 'response_sha256':hashlib.sha256(code.encode()).hexdigest(),
                 'sent_body_sha256':sent_wire['body_sha256'],'raw_response_accepted_or_repaired':False}
            rows.append(one)
            immutable_json(STAGE/('TRAIN'+str(ordinal)+'_attempt'+str(one['attempt'])+'.json'),
                {'audit':one,'exact_sent_body':sent,'original_response_content':code,
                 'original_wire_request':sent_wire,'original_wire_response':json.loads((directory/'wire_response.json').read_text())})
    assert len(rows)==4 and sum(r['finish_reason']=='stop' for r in rows)==3 and sum(r['finish_reason']=='length' for r in rows)==1
    assert len([m for r in rows for m in r['constant_string_membership_tests'] if m['right_is_native_hypothesis_not_document']])==1
    assert before==ledger()
    report={'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
        'new_model_calls':0,'new_oracle_views':0,'new_native_grades':0,'new_native_pairs':0,
        'ledger_rows_unchanged':True,'replayed_parser_matches_historical_sealed_sources':parser_hashes,
        'fixed_existing_TRAIN_ordinals':list(TARGETS),'historical_physical_calls_inspected':4,
        'historical_complete_stop_responses':3,'historical_truncated_responses':1,
        'rows':rows,'native_expected_answers_not_opened_or_inferred':True,
        'visible_source_has_exceptions_not_reconstructible_by_deduplication':True,
        'current_toy_action_bug_not_claimed_cause_of_historical_failures':True,
        'old_unified_IR_89_source_truncation_statistic_not_overwritten':True,
        'no_unsupported_input_insufficiency_or_general_model_incapacity_inference':True,
        'method_advantage_and_legal_semantic_recovery_not_established':True,
        'two_contributions_established':False,'goal_complete':False}
    immutable_json(REPORT,report)
    after=[]
    for row in rows:
        original=json.loads((STAGE/('TRAIN'+str(row['TRAIN_ordinal'])+'_attempt'+str(row['attempt'])+'.json')).read_text())
        try:current_parse(original['original_response_content'])
        except SourceCodeError as error:after.append({'call_id':row['call_id'],'error':str(error)})
        else:raise AssertionError('Syntax support must not silently accept another unresolved defect')
    fragment='query = entailment_label(flag == True)'
    try:historical.parse_pal(fragment)
    except SourceCodeError as error:before_error=str(error)
    else:raise AssertionError('The recorded interface mismatch was not reproduced')
    p=current_parse(fragment);compiled=compile_query(p['nodes'],p['query'],{},domains={'flag':(False,True)})
    outcomes={str(v):compiled.evaluate({'flag':v}) for v in [False,True]}
    assert outcomes=={'False':'Contradiction','True':'Entailment'}
    invalid=current_parse('query = entailment_label("Entailment")')
    try:compile_query(invalid['nodes'],invalid['query'],{})
    except IRTypeError as error:diagnostics=error.diagnostics
    else:raise AssertionError('Non-Boolean projection was accepted')
    repair={'new_model_calls':0,'new_oracle_views':0,'native_grade_or_raw_success_claim':False,
        'before_boolean_expression_error':before_error,'after_boolean_expression_IR':p,
        'explicit_boolean_completion_outcomes':outcomes,'unresolved_flag_is_not_defaulted':True,
        'invalid_string_argument_diagnostics':diagnostics,'all_four_original_responses_still_rejected':after,
        'existing_graph_projection_path_preserved':True,'pal_related_regressions_passed':30,
        'current_pal_frontend_sha256':hashlib.sha256((ROOT/'legal_skill_guard/rr/pal_frontend.py').read_bytes()).hexdigest(),
        'semantic_rules_or_source_ownership_not_filled':True,'goal_complete':False}
    immutable_json(STAGE/'projection_interface_repair.json',repair)
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False))
    for r in rows:print(json.dumps(r,ensure_ascii=False))


if __name__=='__main__':main()
