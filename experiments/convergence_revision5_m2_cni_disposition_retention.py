"""Check archived CNI updates against separately evidenced disposition and retention."""

from collections import Counter
from itertools import product
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY, pointer
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_disposition_scope import (
    BOOTSTRAP, DATASET, TrainingJournal, load_roster, spans_for,
)
from experiments.convergence_revision5_cni_trigger_coverage import HOME as COVERAGE, review_contract
from legal_skill_guard.paired_interfaces.shared_semantics import (
    SourceCase, Theory, allowed_relation, matches_assertions, source_variant,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_M2_CNI_disposition_retention_20261119'
TASKS = ('nda-16','nda-20')
ENTAIL = 'Entailment'
ABSENT = 'NotMentioned'
DENY = 'Contradiction'
# Retention witnesses refer to the same disposition clause or its stated
# exception. Request-only closure scope was separately reviewed in the
# preceding source inventory. Native labels do not enter these constraints.
REVIEWS = {
    (1,0): (ABSENT, ENTAIL, (77,78), (80,85)),
    (1,1): (ENTAIL, DENY, (29,), (30,)),
    (2,1): (ENTAIL, ENTAIL, (48,), (51,52)),
    (4,0): (ABSENT, ENTAIL, (21,), (22,)),
    (5,1): (ENTAIL, ENTAIL, (35,), (35,)),
    (6,2): (ENTAIL, ENTAIL, (15,20,22), (17,18,25,26)),
    (8,1): (ABSENT, ENTAIL, (90,), (90,)),
}
FIT_COHORT = tuple((batch,arm) for batch in (3,4,5) for arm in (ORDINARY,EXTERNAL_ARM))
RETENTION = re.compile(r'\b(?:retain\w*|held|maintain\w*|archiv\w*|back-up)\b',re.I)


def reference(values, _interpretation):
    return values['disposition'] if values['query']=='close' else values['retention']


def supports(relation, actual):
    return any(matches_assertions(actual,row) for row in relation['signatures'].values())


def local_pair(root, row, source_view):
    pos,source_audit = row
    disposition,retention,action_ids,exception_ids=REVIEWS[pos]
    public=source_view['public']
    spans=spans_for(source_view)
    _, ids, links, _ = review_contract(pos,source_view)
    if (not set(action_ids)<=set(ids)
            or (bool(links)!=(disposition==ENTAIL))
            or any(not RETENTION.search(spans[k]) and k not in (52,85) for k in exception_ids)):
        raise ValueError('Both hypotheses require evidence on the same source')
    if source_audit['source_sha256']!=digest(public):
        raise ValueError('The paired view does not bind the original scope review')
    evidence = digest({'text_and_segmentation':source_audit['source_sha256'],
                       'trigger':action_ids,'exception':exception_ids,
                       'prior_source_review':source_audit['graph_card']['sha256']})
    theory=Theory({root:[{}]},{root:[{}]},reference,sha(Path(__file__)),
                  provenance=({'kind':'independent_source_audit','evidence_sha256':evidence},))
    facts={'disposition':disposition,'retention':retention}
    group=[SourceCase(root+':'+k,root,root,{'text':public['source_text']},{**facts,'query':q})
           for k,q in zip(TASKS,('close','retain'),strict=True)]
    shared=allowed_relation(theory,group)
    independent=allowed_relation(theory,group,mode='independent_completions')
    assert set(shared['signatures'])==set(independent['signatures'])
    for observed in product((ENTAIL,DENY,ABSENT,None), repeat=2):
        direct=all(label is None or label==fact for label,fact in zip(observed,facts.values(),strict=True))
        assert direct==supports(shared,list(observed))==supports(independent,list(observed))
    return facts,shared,independent


def scope_edit_witness(source):
    """Change only the archival exception, and keep the positive disposition obligation."""
    pos,view,prior=source
    assert pos==(5,1)
    text=view['public']['source_text']
    clause=spans_for(view)[35]
    exception='except that Recipient may retain a copy of such Confidential Information solely for archival purpose'
    assert text.count(exception)==1 and exception in clause
    start=text.index(exception)
    root=prior['source']
    options={ENTAIL:exception,DENY:'and Recipient may not retain any copy of such Confidential Information'}
    theory=Theory({root:[{}]},{root:[{}]},reference,sha(Path(__file__)),
                  provenance=({'kind':'independent_source_audit','evidence_sha256':prior['graph_card']['sha256']},),
                  allowed_edits=frozenset({'retention'}))
    base=SourceCase(root+':retention_original',root,root,{'text':text},
                    {'query':'retain','disposition':ENTAIL,'retention':ENTAIL},
                    spans={'retention':('text',start,start+len(exception))})
    result=source_variant(base,theory,{'retention':DENY},{'retention':options.__getitem__})
    assert result['status']=='REALIZABLE'
    edited=result['case']
    assert edited.public['text']==text[:start]+options[DENY]+text[start+len(exception):]
    cases=[base,edited,
           SourceCase(root+':close_original',root,root,base.public,{**base.primitives,'query':'close'}),
           SourceCase(root+':close_edit',root,root,edited.public,{**edited.primitives,'query':'close'},
                      interventions=edited.interventions)]
    a=allowed_relation(theory,cases)
    b=allowed_relation(theory,cases,mode='independent_completions')
    expected=[ENTAIL,DENY,ENTAIL,ENTAIL]
    assert list(a['signatures'].values())==list(b['signatures'].values())==[expected]
    return {'one_exact_source_replacement':True,'edit_receipt_sha256':digest(result['receipt']),
            'expected_local_relation':expected,'same_information_direct_and_independent_sets_equal':True,
            'new_model_reads':0}


def verify_prediction(db, key, result):
    if 'schema_reads' in result:
        trace,=result['schema_reads']
        verify_content=lambda r: digest(r['content'])==trace['response_sha256']
    else:
        entry,=result['reads']
        trace,=entry['execution']['traces']
        verify_content=lambda r: r['content']==trace['raw_content']
    physical=db.execute('select status,role,purpose,source,result from calls where id=?',
                        (trace['physical_call_id'],)).fetchone()
    if physical[:4]!=('completed','executor','skill_actor',key) or not verify_content(json.loads(physical[4])):
        raise ValueError('Use only exact bound native candidate results')
    return trace['physical_call_id']


def proof_type(prediction, facts, shared, independent):
    actual = [prediction['native'][task]['answer'] for task in TASKS]
    failed = {task for task,a,v in zip(TASKS,actual,facts.values(),strict=True) if a is not None and a!=v}
    shared_passes=supports(shared,actual)
    if shared_passes!=supports(independent,actual) or shared_passes!=(not failed):
        raise ValueError('The literal checks must recover the whole pair relation')
    return failed


def source_material(roster):
    audits={r['source']:r for r in read(COVERAGE/'source_inventory.json')}
    cases={}
    for batch,rows in enumerate(roster,1):
        for i,source in enumerate(s for s in rows if s['dataset']==DATASET):
            pos=batch,i
            if pos not in REVIEWS:
                continue
            key=source['key']
            view,=(v for v in source['views'] if v['id']=='nda-16')
            cases[key]=(pos,view,audits[key])
    assert len(cases)==len(REVIEWS)
    return cases


def run():
    checkpoint=ROOT/read(BOOTSTRAP)['artifact_root']
    study=read(checkpoint/'binding.json')
    roster=load_roster(study)
    journal=TrainingJournal(checkpoint,study,roster)
    sources=source_material(roster)
    pairs={key:local_pair(key,(pos,audit),view) for key,(pos,view,audit) in sources.items()}
    edited=scope_edit_witness(next(row for row in sources.values() if row[0]==(5,1)))
    ids=set()
    trials=[]
    fit_source_receipts={}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('begin')
        ledger=dict(db.execute('select status,count(*) from calls group by status'))
        assert ledger.get('reserved',0)==0
        for batch,arm in FIT_COHORT:
            stage=ROOT/read(pointer(batch))['artifact_root']
            t=read(stage/'terminal.json')
            binding=read(stage/'binding.json')
            decisions=read(stage/'matched_decisions.json')
            assert not t['TEST_opened'] and digest(decisions)==t['matched_decisions_sha256']
            assert binding['batch']==batch and stage.name==digest(binding)
            if batch not in fit_source_receipts:
                assert all(sha(stage/'source_snapshot'/f)==tag for f,tag in binding['source_sha256'].items())
                fit_source_receipts[batch]=len(binding['source_sha256'])
            d=decisions['teacher'][arm][DATASET]
            if 'earlier_TRAIN_regression' not in d:
                assert d['native_utility_delta']<=0
                continue
            proof=d['earlier_TRAIN_regression']
            directory=stage/'candidates'/arm/DATASET
            raw=read(directory/'measurements.json')
            regress=read(directory/'prior_TRAIN_regression.json')
            assert digest(regress)==proof['evidence_sha256'] and digest(raw['predictions'])==d['predictions_sha256']
            assert regress['holds']==proof['passed'] and regress['native_utility_delta']==proof['native_utility_delta']
            outcome={'scope_reviewed_source_pairs':0,'baseline_explicit_conflicts':0,
                     'candidate_explicit_conflicts':0,'candidate_new_explicit_conflicts':0,
                     'candidate_repaired_explicit_conflicts':0}
            by_task=Counter()
            new_conflict_types=Counter()
            observed=journal._observations(arm,batch)
            for key,(pos,_,_) in sources.items():
                if pos[0]>batch:
                    continue
                if pos[0]==batch:
                    prior=read(journal.directory(arm,batch)/'predictions'/(digest(key)+'.json'))
                    assert digest(prior)==observed['predictions'][key]
                    before,after=prior['result'],raw['predictions'][key]
                else:
                    before,after=regress['before'][key],regress['candidate'][key]
                ids.update(verify_prediction(db,key,x) for x in (before,after))
                lhs=proof_type(before,*pairs[key])
                rhs=proof_type(after,*pairs[key])
                outcome['scope_reviewed_source_pairs']+=1
                outcome['baseline_explicit_conflicts']+=len(lhs)
                outcome['candidate_explicit_conflicts']+=len(rhs)
                outcome['candidate_new_explicit_conflicts']+=len(rhs-lhs)
                outcome['candidate_repaired_explicit_conflicts']+=len(lhs-rhs)
                by_task.update(rhs-lhs)
                for task in rhs-lhs:
                    case_truth=pairs[key][0]['disposition' if task=='nda-16' else 'retention']
                    answer=after['native'][task]['answer']
                    new_conflict_types[f'{case_truth} reported as {answer}']+=1
            trial={'batch':batch,'arm':'common' if arm==ORDINARY else 'PARSE_style',
                   'native_batch_delta':d['native_utility_delta'],'native_prior_delta':proof['native_utility_delta'],
                   'original_acceptance':d['selected']=='candidate',
                   'both_shared_and_direct_veto_new_conflicts':outcome['candidate_new_explicit_conflicts']>0,
                   'new_conflicts_by_hypothesis':dict(by_task),
                   'new_conflict_label_types':dict(new_conflict_types),**outcome}
            trials.append(trial)
    assert len(trials)==5
    behavior=Counter(tuple((r['original_acceptance'],r['both_shared_and_direct_veto_new_conflicts']))
                     for r in trials)
    result={'source_reviewed_TRAIN_parents':len(sources),'actual_physical_responses_verified':len(ids),
            'trial_scope':'Original native-positive ordinary or matched external CNI proposals at B3 through B5',
            'verified_frozen_TRAIN_fit_source_files_by_batch':fit_source_receipts,
            'candidate_decision_sources':trials,'native_adopted_candidates':sum(r['original_acceptance'] for r in trials),
            'native_adopted_new_conflict_candidates':behavior[True,True],
            'shared_and_independent_different_on_saved_outputs':0,
            'unknown_and_value_combinations_checked_per_reviewed_source':16,
            'four_query_source_edit_check':edited,'new_model_requests':0,'ledger_rows':sum(ledger.values()),
            'DEV_or_TEST_opened':False,'bound_experiment_source_sha256':sha(Path(__file__))}
    immutable_json(HOME/'audited_terminal.json',result)
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':
    run()
