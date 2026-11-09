"""Finite acquisition test: source-grounded feedback, not a new contribution claim.

The inherited eight-input pool was authored in an earlier source audit. Selection
here sees only inputs and candidate predictions, never their reference labels.
A same-model source/specification-driven control may choose or create inputs.
"""
import argparse,hashlib,itertools,json,sqlite3
from collections import Counter
from pathlib import Path

from experiments.rr_v2_legal_annual_scope import FIELDS,plan_sql,probes,read,reference,sql_value
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodTeacher,TEACHER_BINARY,TEACHER_SHA
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
RUN='legal_feedback_acquisition_v1_20261110';STAGE=BASE/RUN
OPS=['cap','exclude_scope_at_least','exclude_scope_above','include_all']
PAYMENT=obj({'payment_id':{'type':'string'},'payer':{'type':'string'},'payee':{'type':'string'},
 'payment_year':{'type':'integer'},'service_id':{'type':'string'},'amount':{'type':'integer'}})
TEST=obj({'payments':{'type':'array','items':PAYMENT},'expected':{'type':'integer'},'source_quote':{'type':'string'}})
SCHEMA=obj({'tests':{'type':'array','items':TEST}})


def hypotheses():
    out=[]
    for n in range(5):
        for keys in itertools.combinations([x for x in FIELDS if x!='payment_id'],n):
            for op in OPS[:3]:out.append({'scope_keys':list(keys),'threshold':7000,'adjustment':op})
    for op in OPS[:3]:out.append({'scope_keys':['payment_id'],'threshold':7000,'adjustment':op})
    out.append({'scope_keys':[],'threshold':7000,'adjustment':'include_all'})
    assert len(out)==52
    return out


def rows(payments):
    return [dict(zip(FIELDS+['amount'],p)) for p in payments]


def raw_rows(payments):
    return [[p[k] for k in FIELDS+['amount']] for p in payments]


def value(plan,payments):
    return sql_value(plan_sql(plan),payments,[[p[0],'common admitted identity'] for p in payments])


def pool():
    # Existing author-created input pool, explicitly NOT autonomously generated.
    # No old expected value, original native case or native label enters selection.
    out=[]
    for i,p in enumerate(probes()):
        ids={q[0] for q in p['qualifications']}
        out.append({'pool_id':i,'payments':[r for r in p['payments'] if r[0] in ids]})
    return out


def select(pool,plans,budget=4):
    predictions=[[value(h,p['payments']) for p in pool] for h in plans]
    best=None
    for subset in itertools.combinations(range(len(pool)),budget):
        partitions=Counter(tuple(v[i] for i in subset) for v in predictions)
        score=(-len(partitions),max(partitions.values()),sum(len(pool[i]['payments']) for i in subset),subset)
        if best is None or score<best[0]:best=(score,subset,partitions)
    return {'indices':list(best[1]),'distinct_candidate_answer_vectors':len(best[2]),
        'largest_indistinguishable_class':max(best[2].values()),
        'selection_uses_source_reference_labels':False,
        'selection_is_ordinary_finite_version_space_design_not_claimed_new_algorithm':True}


def validate_tests(tests,source,fixed=None):
    if not isinstance(tests,list) or len(tests)!=4:raise ValueError('Exactly four source-contract tests required')
    for t in tests:
        if set(t)!={'payments','expected','source_quote'}:raise ValueError('Feedback fields differ')
        if type(t['expected']) is not int or t['expected']<0:raise ValueError('Expected value must be nonnegative integer')
        if not t['source_quote'] or t['source_quote'] not in source:raise ValueError('Source quote must be exact and nonempty')
        if len(t['payments'])>8:raise ValueError('At most eight admitted payments per local input')
        ids=[]
        for p in t['payments']:
            if set(p)!=set(FIELDS+['amount']):raise ValueError('Input relation fields differ')
            if any(type(p[k]) is not str or not p[k] for k in ['payment_id','payer','payee','service_id']):raise ValueError('Nonempty identity fields required')
            if type(p['amount']) is not int or p['amount']<0 or type(p['payment_year']) is not int:raise ValueError('Invalid payment value')
            ids.append(p['payment_id'])
        if len(ids)!=len(set(ids)):raise ValueError('Physical payment IDs must be unique')
    if fixed is not None and [t['payments'] for t in tests]!=fixed:raise ValueError('The fixed query inputs must not be changed')


def score(tests,source,fixed=None):
    validate_tests(tests,source,fixed)
    checks=[]
    for t in tests:
        data=raw_rows(t['payments']);expected=reference(data,[[p[0],'given admission'] for p in data])
        checks.append({'source_reference_amount':expected,'model_expected_amount':t['expected'],'semantically_correct':expected==t['expected']})
    survivors=[]
    for h in hypotheses():
        if all(value(h,raw_rows(t['payments']))==t['expected'] for t in tests):survivors.append(h)
    all_correct=all(c['semantically_correct'] for c in checks)
    return {'tests':checks,'all_feedback_semantically_correct':all_correct,'survivors':survivors,
        'survivor_count':len(survivors),'unique_reference_plan':survivors==[{'scope_keys':['payer','payee','payment_year'],'threshold':7000,'adjustment':'cap'}],
        'model_quotes_not_treated_as_semantic_proof':True,'all_results_within_fixed_52_class_grammar_only':True}


def offline():
    plans=hypotheses();q=pool();selected=select(q,plans)
    raw=read(BASE/'legal_annual_scope_execution_v1_20261110/finite_scope_identifiability.json')
    # All redundant plan variants agree with their canonical class on the pool.
    for h in raw['all_hypotheses']:
        p=h['plan'];canonical=p|{'scope_keys':[] if p['adjustment']=='include_all' else ['payment_id'] if 'payment_id' in p['scope_keys'] else p['scope_keys']}
        assert canonical in plans
        assert all(value(p,r['payments'])==value(canonical,r['payments']) for r in q)
    projected=read(BASE/'legal_annual_scope_execution_v1_20261110/execution.json')['local_admitted_rows']
    data=raw_rows(projected)
    fit=[h for h in plans if value(h,data)==20597]
    assert len(fit)==28
    assert strict_output_schema_issues(SCHEMA)==[]
    return {'passed':4,'unquotiented_representations':128,'canonical_semantic_classes':52,
        'canonical_classes_fitting_original_local_amount':28,'selected_queries':selected,
        'pool_authored_before_this_experiment_not_learned':True,'new_model_calls':0}


def prepare():
    old=read(BASE/'legal_annual_scope_v3_20261110/seal.json');off=offline();q=pool();selected=off['selected_queries']['indices']
    fixed=[rows(q[i]['payments']) for i in selected]
    common={'source_clause':old['source_excerpt'],'local_contract':'Each row is one unique already-admitted physical payment of nonnegative remuneration. Output the local amount included in wages by3306(b)(1), not a full3306 employer prediction. Other exclusions are outside this component.',
        'input_columns':FIELDS+['amount'],
        'candidate_implementations_to_discriminate':{'threshold':7000,'scope_keys':'Any subset of payment_id,payer,payee,payment_year,service_id; empty means global scope',
            'adjustment':{'cap':'sum min(threshold,group amount)', 'exclude_scope_at_least':'sum group amount except zero when group amount>=threshold',
                'exclude_scope_above':'same whole-group exclusion with >', 'include_all':'sum all amounts without threshold'}},
        'existing_unlabelled_input_pool':[{'pool_id':p['pool_id'],'payments':rows(p['payments'])} for p in q],
        'output_contract':'Exactly four tests, up to eight payment rows each, expected nonnegative integer amount, and a nonempty exact quote from the source grounding the result. No test labels or correct programme are supplied. Do not use tools, files, browsing, code execution, other cases or outside law.'}
    systems={
        'free':'From the statutory source and local input contract, design a strong four-test specification suite. Reason about preconditions, postconditions, boundaries and undefined behavior first; do not copy a candidate implementation as the source of truth. Select or create inputs that discriminate meaningful legal misinterpretations and scope/mutation alternatives, including interactions or entity isolation when useful. You may use any existing unlabelled pool inputs or generate better inputs. Return source-grounded expected amounts and exact source quotes. The suite should catch source-semantic errors, not just execute branches. All candidate families and pool inputs are shared with the fixed-query comparator.',
        'fixed':'Determine the included amount for each of the four fixed local inputs from the statutory source. These inputs were selected using candidate disagreement without any expected answers. Preserve input rows and their order exactly. Do not choose an implementation merely because it occurs in the candidate list; derive each amount from the actual source. Return expected amounts and exact supporting source quotes. The same local source, input pool and candidate families are available to a source/specification-driven free test-generation comparator.'}
    messages={}
    for arm in systems:
        material=dict(common)
        if arm=='fixed':material['fixed_queries_in_required_order']=fixed
        messages[arm]={'system':systems[arm],'user':json.dumps(material,ensure_ascii=False)}
    protocol=ROOT/'reports/method_redesign_20261109/legal_feedback_acquisition_protocol.md'
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['experiments/rr_v2_legal_feedback_acquisition.py',
        'experiments/rr_v2_legal_annual_scope.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py',
        'legal_skill_guard/rr/client.py','legal_skill_guard/inference/codex_cli_client.py']}
    assert hashlib.sha256(Path(TEACHER_BINARY).read_bytes()).hexdigest()==TEACHER_SHA
    seal={'run_id':RUN,'config':old['config'],'sources':old['sources'],'source':old['source'],'source_excerpt':old['source_excerpt'],
        'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
        'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'messages':messages,'fixed_queries':fixed,'schema':SCHEMA,
        'offline':off,'both_prompts_sealed_before_first_dispatch':True,'no_native_case_query_labels_or_correct_code_in_prompts':True,
        'not_a_complete_autonomous_query_generator':True,'teacher_configuration_unchanged':True,'goal_complete':False}
    immutable_json(STAGE/'seal.json',seal);return seal


def main(action):
    if action=='offline':print(json.dumps(offline(),ensure_ascii=False));return
    s=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'offline':s['offline'],'new_model_calls':0}));return
    path=STAGE/(action+'.json')
    if path.exists():print(json.dumps({'existing':str(path),'no_redispatch':True}));return
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
        question='Can source-grounded teacher feedback distinguish scope without author-provided expected labels, and does fixed disagreement-query labeling add anything over strong ordinary source/specification-driven test generation? Finite feedback acquisition pilot, no native task grading or method novelty claim.')
    wire=MethodTeacher(ledger,STAGE,s['config']['teacher']).summarize(RUN+':'+action,source_ids=[s['source']],system_prompt=s['messages'][action]['system'],user_prompt=s['messages'][action]['user'],output_schema=s['schema'])
    result={'physical_response':wire,'value':wire['value'],'goal_complete':False}
    try:result.update(status='source_feedback_scored',scores=score(wire['value']['tests'],s['source_excerpt'],s['fixed_queries'] if action=='fixed' else None))
    except Exception as exc:result.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
    immutable_json(path,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['physical_response','value']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['offline','prepare','free','fixed']);main(p.parse_args().action)
