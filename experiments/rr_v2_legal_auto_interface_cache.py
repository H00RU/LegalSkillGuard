"""Ordinary cache learns its own API from the initial two source policies.

This closes the initial-information gap in the conditional cache control. The
role hints and local source scope match the original acquisition; no zero-hint
requirement, existing legal API, rule body, case or answer is supplied.
"""
import argparse,ast,hashlib,json
from pathlib import Path
from experiments.rr_v2_legal_independent_cache import check_code,execute_code
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import PRED
from legal_skill_guard.rr.method_client import MethodTeacher,TEACHER_BINARY,TEACHER_SHA
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
RUN='legal_auto_interface_cache_v1_20261110';STAGE=BASE/RUN
SCHEMA=obj({'interface':{'type':'array','items':PRED},'code':{'type':'string'},'unresolved':{'type':'array','items':{'type':'string'}}})


def read(p):return json.loads(p.read_text())


def offline():
    assert strict_output_schema_issues(SCHEMA)==[]
    code="def law_cache(facts, query):\n    return solve({'predicates':facts['interface'],'rules':[],'priorities':[],'unresolved':[]}, facts['facts'], query)"
    interface=[{'name':'given','roles':['person','year'],'functional':False,'meaning':'explicit software fixture'}]
    q={'predicate':'given','arguments':['A','2017'],'positive':True}
    for sign,expected in [(True,'Entailment'),(False,'Contradiction')]:
        facts=[{'atom':q|{'positive':sign},'quote':'fixture'}]
        assert execute_code(code,{'interface':interface,'facts':facts},q,['fixture'])['answer']==expected
    assert execute_code(code,{'interface':interface,'facts':[]},q,['fixture'])['answer'] is None
    return {'passed':4,'new_model_calls':0,'same_public_solver_and_ordinary_code_runner':True}


def prepare():
    old=read(BASE/'legal_relations_exceptions_native_v1_20261109/seal.json')
    requests=[read(p) for p in (BASE/'legal_relations_exceptions_native_v1_20261109/calls').glob('*/request.json')]
    request=next(r for r in requests if r.get('purpose')=='method_train_compile')
    original=old['system_prompt']
    common=original.replace('Learn a reusable compact legal relation program','Learn a reusable ordinary Python legal policy cache with its own declared predicate interface',1)
    common=common.replace('Return only the schema object.','Follow the ordinary-cache output contract below.')
    system=common+(
        '\nThe preceding scientific scope, role hints and source-grounding rules are exactly those supplied to the original relation compiler. '
        'They specify optional public solver compatibility, not a requirement to use rules. '
        'No already learned legal predicate names, argument-role arrays or rule bodies are provided. The only named generic predicate is the same neutral case_subject_year roster. '
        'Return interface, code, unresolved. Interface declares every predicate your callable uses: name, ordered roles, functional, meaning. '
        'Choose the legal names/roles yourself from the two sources. Code defines one ordinary law_cache(facts,query) function. '
        'facts is an envelope with interface equal to your returned interface and facts equal to signed atom records {atom:{predicate,arguments,positive},quote}. '
        'query has predicate,arguments,positive; null query arguments project unasked participants. Return a dict with answer Entailment, Contradiction or null and optional proof diagnostics. '
        'You may write ordinary Python or call solve(program, signed_facts, query), the same public source-checked supported-model engine available to the relation method. '
        'For solve, program has predicates, rules, priorities, unresolved using the same structures described above, and predicates may be read from facts["interface"] to avoid duplicating your interface. '
        'Ordinary collections and set,frozenset,list,dict,tuple,str,int,bool,len,sorted,enumerate,zip,any,all,min,max,sum,isinstance are available. '
        'No imports, classes, nested declarations, decorators, annotations, defaults, filesystem/network or dynamic calls; one top-level function, ordinary assignments/loops/conditionals/returns. '
        'Do not hardcode people, case years or answers. Only source policy constants are allowed. '
        'No tools, browsing, file reads or code execution during generation. This is initial API and rule acquisition, not a per-case answer.')
    user=json.dumps({'policies':old['policies'],'existing_API_or_rule_body_supplied':False,
        'local_scope_matches_original_relation_acquisition':True,'same_substantive_role_hints_not_a_zero_hint_experiment':True,
        'no_cases_native_queries_or_answers_supplied':True},ensure_ascii=False)
    protocol=ROOT/'reports/method_redesign_20261109/legal_auto_interface_cache_protocol.md'
    paths=['experiments/rr_v2_legal_auto_interface_cache.py','experiments/rr_v2_legal_independent_cache.py',
        'legal_skill_guard/rr/legal_predicate_skills.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    assert hashlib.sha256(Path(TEACHER_BINARY).read_bytes()).hexdigest()==TEACHER_SHA
    s={'run_id':RUN,'config':old['config'],'sources':old['sources'],'source_ids':request['source_ids'],
        'source_policies':old['policies'],'messages':{'system':system,'user':user},'schema':SCHEMA,'files':files,
        'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
        'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'offline':offline(),
        'original_initial_system_prompt_sha256':hashlib.sha256(original.encode()).hexdigest(),
        'no_existing_legal_API_or_rules_cases_labels_provided':True,'neutral_roster_and_role_hints_shared':True,
        'matched_local_source_scope_151_152_only':True,'not_a_whole_cohort_or_full_build':True,'goal_complete':False}
    immutable_json(STAGE/'seal.json',s);return s


def main(action):
    s=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'offline':s['offline'],'new_model_calls':0}));return
    out=STAGE/'source.json'
    if out.exists():print(json.dumps({'existing':str(out),'no_redispatch':True}));return
    l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
        question='Initial-source ordinary Python cache with its own model-generated predicate API versus the original source-induced relation API/programme. Same151/152 local scope, role hints and public solver; no given learned API or cases. Acquisition and downstream-use evidence must be separated; not a new mechanism claim.')
    w=MethodTeacher(l,STAGE,s['config']['teacher']).summarize(RUN+':source',source_ids=s['source_ids'],system_prompt=s['messages']['system'],user_prompt=s['messages']['user'],output_schema=s['schema'])
    result={'physical_response':w,'value':w['value'],'goal_complete':False,'native_cases_executed':False}
    try:
        check_code(w['value']['code']);api=w['value']['interface'];names=[p['name'] for p in api]
        if len(set(names))!=len(names) or any(not p['roles'] or len(set(p['roles']))!=len(p['roles']) for p in api):raise ValueError('Invalid predicate interface')
        result['status']='API_and_code_captured_not_yet_source_semantically_accepted'
    except Exception as exc:result.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
    immutable_json(out,result)
    print(json.dumps({'status':result['status'],'predicate_count':len(w['value']['interface']),'elapsed_seconds':w['elapsed_seconds'],'native_cases_executed':False},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','generate']);main(p.parse_args().action)
