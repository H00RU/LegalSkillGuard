"""Compare the toy solver with ordinary finite relational/truth-table caching.

No native examples are generated, labeled or scored. The complete two-Boolean
guard domain is a SOFTWARE domain, not additional TRAIN/DEV data. Source-text
observations are copied only from an already published public-input audit.
"""
import hashlib,itertools,json,sqlite3,time
from pathlib import Path
import z3
from experiments.rr_v2_norm_query_prototype import classify_permission,consistent_modes
from legal_skill_guard.rr.checkpoint import immutable_json

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'artifacts/rr_method_redesign_20261109/norm_query_control_audit_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/norm_query_control_results.json'
NAMES=('need','written')
WORLDS=[dict(zip(NAMES,values)) for values in itertools.product([False,True],repeat=2)]
CONTEXTS=[{n:v for n,v in zip(NAMES,values) if v is not None}
          for values in itertools.product([None,False,True],repeat=2)]


def ledger():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def guard(mask):
    terms=[]
    for i,world in enumerate(WORLDS):
        if mask & (1<<i):
            terms.append(z3.And(*[z3.Bool(n) if world[n] else z3.Not(z3.Bool(n)) for n in NAMES]))
    return z3.Or(*terms)


def ordinary_cache(rules,definitions):
    """Ordinary finite join followed by materialization; no candidate helpers."""
    cache=[]
    for index,row in enumerate(rules):
        members=definitions[row['recipient']] if row['recipient'] in definitions else [row['recipient']]
        values=[]
        for world in WORLDS:
            expr=z3.substitute(row['guard'],*[(z3.Bool(n),z3.BoolVal(world[n])) for n in NAMES])
            value=z3.simplify(expr)
            assert z3.is_true(value) or z3.is_false(value)
            values.append(z3.is_true(value))
        cache.extend({'rule':index,'action':row['action'],'recipient':member,'effect':row['effect'],
                      'truth_table':values} for member in members)
    return cache


def ordinary_answer(cache,action,recipient,mode,facts):
    worlds=[]
    for i,world in enumerate(WORLDS):
        if any(world[k]!=v for k,v in facts.items()):continue
        active=[r for r in cache if r['action']==action and r['recipient']==recipient and r['truth_table'][i]]
        permit=any(r['effect']=='permission' for r in active)
        forbid=any(r['effect']=='prohibition' for r in active)
        worlds.append((permit and not forbid,forbid and not permit))
    assert worlds
    positive=any(p for p,n in worlds) if mode=='possible' else all(p for p,n in worlds)
    negative=all(n for p,n in worlds)
    return 'Entailment' if positive else 'Contradiction' if negative else None


def main():
    before=ledger();started=time.monotonic()
    definitions={'Representatives':['employee','external_adviser']}
    comparisons=0;counts={'Entailment':0,'Contradiction':0,'Unknown':0}
    for p_mask in range(16):
        for n_mask in range(16):
            rules=[{'effect':'permission','action':'disclose','recipient':'Representatives','guard':guard(p_mask)},
                   {'effect':'prohibition','action':'disclose','recipient':'external_adviser','guard':guard(n_mask)}]
            cache=ordinary_cache(rules,definitions)
            for recipient,mode,facts in itertools.product(['employee','external_adviser'],['possible','operative'],CONTEXTS):
                expected=ordinary_answer(cache,'disclose',recipient,mode,facts)
                actual=classify_permission(rules,definitions,recipient,action='disclose',mode=mode,facts=facts)['answer']
                assert actual==expected,(p_mask,n_mask,recipient,mode,facts,expected,actual)
                comparisons+=1;counts[actual or 'Unknown']+=1
        print(json.dumps({'completed_positive_guard_functions':p_mask+1,'software_comparisons':comparisons}),flush=True)
    assert comparisons==9216
    cross_action=[]
    for effect in ['permission','prohibition']:
        rules=[{'effect':effect,'action':'reverse_engineer','recipient':'employee','guard':z3.BoolVal(True)}]
        answer=classify_permission(rules,{},'employee',action='retain_information')['answer']
        assert answer is None
        cross_action.append({'effect':effect,'query_action':'retain_information','rule_action':'reverse_engineer','answer':answer})
    # Different TRAIN software constraints must select the same profiles under
    # the independent evaluator. These rows are NOT native annotation labels.
    training=[]
    for action,recipient,mask,context in [('disclose','Representatives',12,{}),
            ('disclose','external_adviser',10,{}),('retain_information','employee',15,{'need':True})]:
        rules=[{'effect':'permission','action':action,'recipient':recipient,'guard':guard(mask)}]
        cache=ordinary_cache(rules,definitions)
        target='external_adviser' if recipient=='Representatives' else recipient
        label=ordinary_answer(cache,action,target,'possible',context)
        training.append({'rules':rules,'definitions':definitions,'recipient':target,'action':action,'facts':context,'label':label})
    ordinary_modes=[mode for mode in ['possible','operative'] if all(
        ordinary_answer(ordinary_cache(r['rules'],r['definitions']),r['action'],r['recipient'],mode,r['facts'])==r['label'] for r in training)]
    candidate_modes=consistent_modes(training)
    assert ordinary_modes==candidate_modes==['possible']
    unsupported=[]
    try:
        classify_permission([{'effect':'obligation','action':'return_information','recipient':'employee','guard':z3.BoolVal(True)}],{},'employee',action='return_information')
    except ValueError as error:unsupported.append(str(error))
    assert unsupported
    observations=json.loads((ROOT/'reports/method_redesign_20261109/legal_scope_task_coverage_results.json').read_text())
    observed=[{'TRAIN_ordinal':r['TRAIN_ordinal'],'document_sha256':r['document_sha256'],
               'scope':'existing public text only; not compiled or graded by this audit'}
              for r in observations['TRAIN_lexical_scope_audit'] if r['TRAIN_ordinal'] in [111,115]]
    assert ledger()==before
    result={'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
        'new_model_calls':0,'new_oracle_views':0,'new_native_grades':0,'new_native_pairs':0,'ledger_rows_unchanged':True,
        'software_guard_boolean_variables':list(NAMES),'software_guard_functions_each_side':16,
        'software_partial_contexts':len(CONTEXTS),'software_comparisons':comparisons,'answer_counts':counts,
        'ordinary_relational_cache_and_truth_table_equal_on_declared_domain':True,
        'candidate_and_ordinary_consistent_modes_on_software_constraints':candidate_modes,
        'cross_action_counterexamples_after':cross_action,'obligations_explicitly_unsupported':unsupported,
        'existing_public_text_contexts_used_for_problem_motivation':observed,
        'native_contract_semantics_or_model_acquisition_not_verified':True,
        'same_expressivity_does_not_disprove_a_future_acquisition_or_cost_contribution':True,
        'current_prototype_has_no_extra_learning_mechanism_beyond_ordinary_controls':True,
        'no_causal_latency_advantage_claim':True,'audit_elapsed_seconds':time.monotonic()-started,
        'implementation_sha256':hashlib.sha256((ROOT/'experiments/rr_v2_norm_query_prototype.py').read_bytes()).hexdigest(),
        'data_pair_proposal_authorized':False,'data_pair_proposal_executed':False,
        'data_approval_alone_would_not_justify_promoting_this_prototype_as_two_contributions':True,
        'two_contributions_established':False,'goal_complete':False}
    immutable_json(STAGE/'after_action_binding_and_ordinary_control.json',result)
    immutable_json(REPORT,result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
