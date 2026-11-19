"""Replay ContractNLI skill updates with a source-bound oral-coverage check."""

from collections import Counter
from pathlib import Path
import json
import re
import sqlite3
from statistics import mean

from experiments.convergence_formal_b1_observe import POINTER as FIRST_OBSERVE
from experiments.convergence_formal_train_fit import CNI, M2, ORDINARY, pointer as fit_pointer
from experiments.convergence_formal_train_observe import load_roster, pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_disposition_scope import TrainingJournal, spans_for
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.shared_semantics import SourceCase, Theory, allowed_relation, matches_assertions
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_CNI_oral_scope_20261119'
TASK = 'nda-3'
ENTAILMENT = 'Entailment'
NOT_MENTIONED = 'NotMentioned'
CONTRADICTION = 'Contradiction'
ORAL = re.compile(r'\b(?:oral(?:ly)?|verbal(?:ly)?)\b',re.I)
ORAL_EXCLUSION = re.compile(
    r'\b(?:excludes?|does not include|shall not include|shall not cover|shall in no event cover)'
    r'\s+(?:\w+\s+){0,4}(?:oral|verbal)\s+(?:information|disclosures?|communications?)\b',re.I)
# Form predicates modify the information at disclosure. A return obligation,
# an oral notice, or an entire-agreement recital cannot introduce this edge.
FORM = re.compile(r'\b(?:in (?:any|whatever) form|regardless of its form or medium)\b',re.I)
DEFINITION = re.compile(
    r'\bConfidential Information["”\x27]?\s*(?:,\s*whenever used in this Agreement,\s*)?'
    r'(?:under this Agreement consists of|as used herein|(?:shall )?means?|(?:(?:also|shall) )?includes?)\b',re.I)
ENUMERATION = re.compile(r'^\(([a-z]|[ivx]+)\)\s',re.I)
MEDIA_ALTERNATIVE = re.compile(r'^\([a-z]\) if provided orally or visually, is identified as confidential',re.I)
APPLIES = re.compile(r'\bshall apply to all Confidential Information regardless of its form or medium\b',re.I)
DEEMED = re.compile(r'^This information received from a party, either orally or in writing,.*shall be deemed to be confidential information',re.I)
PROTECTED_RECITAL = re.compile(r'^WHEREAS .*Confidential Information .*shall be protected from further disclosure',re.I)
INCORPORATING_RECITAL = re.compile(
    r'^WHEREAS .* disclose Confidential Information \(as defined below\) to a Receiving Party, whether orally',re.I)
INFORMATION_DEFINITION = re.compile(r'\bhereinafter referred to as the ["“]Information[."”]',re.I)
PROTECT_INFORMATION = re.compile(r'\bwill keep the Information strictly confidential\b',re.I)
PROVIDER = re.compile(r'\bdisclosed by ([A-Z][A-Z0-9&.-]+) directly or indirectly\b')
DUTY_PROVIDER = re.compile(r'^The Receiving Party shall treat as strictly confidential any and all information disclosed to it by ([A-Z][A-Z0-9&.-]+)\b')


def oral_proof(view):
    """Return independently checkable source paths and retain unresolved scope."""
    clauses = [' '.join(s.split()) for s in spans_for(view)]
    if any(ORAL_EXCLUSION.search(clause) for clause in clauses):
        return []
    proofs = []
    for i, clause in enumerate(clauses):
        if (DEFINITION.search(clause) or APPLIES.search(clause)) and (ORAL.search(clause) or FORM.search(clause)):
            if not clause.endswith('which'):
                proofs.append(('same_clause', (i,)))
        if DEFINITION.search(clause) and clause.endswith(':'):
            for j in range(i+1, min(i+8,len(clauses))):
                if not ENUMERATION.search(clauses[j]):
                    break
                if 'oral disclosures' in clauses[j].lower():
                    proofs.append(('definition_list', (i,j)))
        if MEDIA_ALTERNATIVE.search(clause) and i>=2:
            if (DEFINITION.search(clauses[i-2]) and clauses[i-2].endswith('which')
                    and re.match(r'^\([a-z]\) if in writing, is marked',clauses[i-1],re.I)):
                proofs.append(('conditional_oral_designation', (i-2,i-1,i)))
        if DEEMED.search(clause):
            lead = next((j for j in range(i-1,max(-1,i-4),-1)
                         if 'selected information' in clauses[j].lower() and ORAL.search(clauses[j])),None)
            if lead is not None:
                proofs.append(('deemed_information', (lead,i)))
        if INFORMATION_DEFINITION.search(clause) and re.search(r'\b(?:written or oral)\b',clause,re.I):
            for j in range(i+1,min(i+13,len(clauses))):
                if PROTECT_INFORMATION.search(clauses[j]):
                    proofs.append(('defined_information_and_duty', (i,j)))
                    break
        if clause.startswith('Information within the meaning of this Agreement') and ORAL.search(clause):
            provider = PROVIDER.search(clause)
            for j in range(i+1,min(i+5,len(clauses))):
                duty = DUTY_PROVIDER.search(clauses[j])
                if provider and duty and provider[1]==duty[1]:
                    proofs.append(('same_provider_information_and_duty', (i,j)))
                    break
        if INCORPORATING_RECITAL.search(clause):
            for j in range(i+1,min(i+6,len(clauses))):
                if PROTECTED_RECITAL.search(clauses[j]):
                    proofs.append(('expressly_backed_recital', (i,j)))
                    break
    return sorted(set(proofs))


def verify_teacher(db, stage, binding, decision, scope):
    identity = decision['teacher_call']
    status,role,purpose,root,fingerprint,body = db.execute(
        'select status,role,purpose,source,request_hash,result from calls where id=?',(identity,)).fetchone()
    assert (status,role,purpose)==('completed','teacher','skill_teacher')
    folder = stage/'calls'/digest(identity)
    request,result = (read(folder/file) for file in ('request.json','result.json'))
    run_id = identity.partition(':teacher:')[0]
    origin, = db.execute("select value from meta where key='spec'").fetchone()
    policy, = db.execute('select value from meta where key=?',('external_legal_skill_policy:'+run_id,)).fetchone()
    policy = json.loads(policy)
    assert policy['execution_binding']==binding and set(scope)<=set(policy['sources']['train'])
    assert result==json.loads(body)
    assert digest({'request':request,'origin_spec':json.loads(origin),'policy':policy})==fingerprint
    assert digest(result['value'])==decision['proposal_sha256']
    assert request['source_ids']==result['source_ids']==list(scope) and root==scope[0]
    assert request['config']==binding['teacher_config']
    assert result['model']==request['config']['model']=='gpt-6.1-sol'
    assert request['config']['reasoning_effort']=='high'
    feedback = json.loads(request['user_prompt'])
    assert feedback['public_task_family']==CNI and feedback['source_or_label_examples_included'] is False
    assert not any('relation' in field or 'semantic' in field for field in feedback)
    return {'native_tasks':feedback['total_native_tasks'],'teacher_feedback_sha256':digest(feedback),
            'teacher_response_sha256':result['response_sha256'],'relation_feedback_present':False}


def verify_prediction(db, roster, key, view, prediction, verified, expected_program):
    entry, = prediction['reads']
    trace, = entry['execution']['traces']
    identity = trace['physical_call_id']
    if identity not in verified:
        physical_wire(db,roster,identity,key)
        verified.add(identity)
    body, = db.execute('select result from calls where id=?',(identity,)).fetchone()
    actual = json.loads(body)
    assert actual['content']==trace['raw_content'] and actual['finish_reason']=='stop'
    native = prediction['native']
    assert entry['execution']['program_sha256']==expected_program
    raw = json.loads(actual['content'])['value']
    assert set(raw)==native.keys() and raw[TASK]['answer']==native[TASK]['answer']
    assert raw[TASK]['evidence_sentence_ids']==native[TASK]['evidence_sentence_ids']
    req = read(Path(actual['artifact_directory'])/'request.json')['payload']
    content = req['messages'][-1]['content']
    assert view['public']['question'] in content
    assert any(json.dumps(view['public']['source_text'],ensure_ascii=style)[1:-1] in content for style in (True,False))
    return native


def replay(db, roster, views, journal, verified, batch):
    stage = ROOT/read(fit_pointer(batch))['artifact_root']
    binding = read(stage/'binding.json')
    terminal = read(stage/'terminal.json')
    original = read(stage/'matched_decisions.json')
    assert not terminal['TEST_opened'] and stage.name==digest(binding)
    assert terminal['matched_decisions_sha256']==digest(original)
    assert all(sha(stage/'source_snapshot'/p)==h for p,h in binding['source_sha256'].items())
    obs = ROOT/binding['observations_root']
    assert sha(obs/'terminal.json')==binding['observations_terminal_sha256']
    proof = original['teacher'][ORDINARY][CNI]
    assert proof['selected']=='candidate' and not original['relation'][CNI]['relation_in_scope']
    folder = stage/'candidates'/ORDINARY/CNI
    native = read(folder/'measurements.json')
    back = read(folder/'prior_TRAIN_regression.json')
    assert proof['predictions_sha256']==digest(native['predictions'])
    assert proof['earlier_TRAIN_regression']['evidence_sha256']==digest(back) and back['holds']
    expected_program = digest(native['candidate'])
    prior_program = digest(journal.library(ORDINARY,batch-1)['programs'][CNI])
    assert journal.library(ORDINARY,batch)['programs'][CNI]==native['candidate']
    assert journal.library(M2,batch)['programs'][CNI]==native['candidate']
    assert original['relation'][CNI]['matched_proposal_sha256']==expected_program
    teacher = verify_teacher(db,stage,binding,proof,[k for k in views if views[k]['batch']==batch])
    pairs = {}
    observations = journal._observations(ORDINARY,batch)
    for key in (*back['before'],*native['predictions']):
        if views[key]['batch']==batch:
            archive = read(journal.directory(ORDINARY,batch)/'predictions'/(digest(key)+'.json'))
            assert observations['predictions'][key]==digest(archive)
            before,after = archive['result'],native['predictions'][key]
        else:
            before,after = back['before'][key],back['candidate'][key]
        view = views[key]['view']
        pairs[key] = [verify_prediction(db,roster,key,view,pred,verified,program)
                      for pred,program in ((before,prior_program),(after,expected_program))]
    return {'teacher':teacher,'accepted_both_libraries':True,'frozen_fit_files':len(binding['source_sha256']),
            'saved_native_gain':proof['native_utility_delta'],'saved_prior_native_gain':back['native_utility_delta'],
            'pairs':pairs}


def coverage_supported(value):
    return value is None or value==ENTAILMENT


def shared_check(views, paths, bank):
    keys = [k for k in bank if paths[k]]
    if not keys:
        return set()
    law = 'verbal_coverage_v1'
    theory = Theory({law:[{}]},{k:[{}] for k in keys},lambda values,_: values['oral_coverage'],
                    sha(Path(__file__)),
                    provenance=({'kind':'explicit_source','evidence_sha256':digest(
                        [(digest(views[k]['view']['public']),paths[k]) for k in keys])},))
    cases = [SourceCase(k,k,law,views[k]['view']['public'],{'oral_coverage':ENTAILMENT}) for k in keys]
    observed = [bank[k][TASK]['answer'] for k in keys]
    direct = all(map(coverage_supported,observed))
    for mode in ('shared','independent_completions'):
        signatures = allowed_relation(theory,cases,mode=mode)['signatures']
        assert list(signatures.values())==[[ENTAILMENT]*len(keys)]
        assert direct==any(matches_assertions(observed,r) for r in signatures.values())
    return {k for k,p in zip(keys,observed,strict=True) if not coverage_supported(p)}


def predict(paths, bank, *, linked):
    result = {}
    for key,native in bank.items():
        current = native[TASK]
        available = [(kind,ids) for kind,ids in paths[key] if linked or kind=='same_clause']
        if available:
            ids = sorted({i for _,path in available for i in path})
            current = {**current,'handled':True,'answer':ENTAILMENT,'evidence_sentence_ids':ids}
            native = {**native,TASK:current}
        result[key] = native
    return result


def score(views, actual, labels):
    exact, f1, joint, total_correct = [], [], [], 0
    for key,pred in actual.items():
        native = pred[TASK]
        value = grade_view(CNI,views[key]['view'],labels[key][TASK],native['answer'],native['evidence_sentence_ids'])
        exact.append(value['grade'])
        f1.append(value['evidence_f1'])
        joint.append(value['grade']*value['evidence_f1'])
        total_correct += sum(row['answer']==labels[key][question]['answer'] for question,row in pred.items())
    return {'oral_correct':sum(exact),'oral_evidence_f1':mean(f1),'correct_with_evidence_f1':mean(joint),
            'all_hypotheses_correct':total_correct,'mothers':len(actual)}


def main():
    obs = ROOT/read(observe_pointer(3))['artifact_root']
    base = read(obs/'binding.json')
    checkpoint = ROOT/base['checkpoint_root']
    binding = read(checkpoint/'binding.json')
    roster = load_roster(binding)
    journal = TrainingJournal(checkpoint,binding,roster)
    views = {s['key']:{'batch':i,'view':next(v for v in s['views'] if v['id']==TASK)}
             for i,cohort in enumerate(roster,1) for s in cohort if s['dataset']==CNI and s['project_split']=='train'}
    assert len(views)==24
    paths = {key:oral_proof(row['view']) for key,row in views.items()}
    grade_file = ROOT/base['native_grade_paths'][CNI]
    grade_sha = base['native_grade_sha256'][base['native_grade_paths'][CNI]]
    assert 'train' in grade_file.relative_to(ROOT).parts
    spec = {'study':'CNI_source_bound_oral_coverage','TRAIN_roster_sha256':digest(roster),
            'source_paths_sha256':digest(paths),'runner_sha256':sha(Path(__file__)),
            'grade_sha256':grade_sha,'new_requests':0,'comparison':'B3/B4 candidates and chronological B5-B8 entering programs'}
    out = HOME/digest(spec)
    immutable_json(out/'protocol.json',spec)
    immutable_json(out/'source_paths.json',paths)
    verified, replays, forward = set(), {}, {}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        totals = dict(db.execute('select status,count(*) from calls group by status'))
        assert not totals.get('reserved')
        for batch in (3,4):
            replays[batch] = replay(db,views,views,journal,verified,batch)
        for key,row in views.items():
            batch = row['batch']
            if batch<5:
                continue
            stage = ROOT/read(observe_pointer(batch))['artifact_root']
            history = journal._observations(ORDINARY,batch)
            assert read(stage/'terminal.json')['observation_receipts'][ORDINARY]==history['train_observation_sha256']
            archive = read(journal.directory(ORDINARY,batch)/'predictions'/(digest(key)+'.json'))
            assert history['predictions'][key]==digest(archive)
            skill = digest(journal.library(ORDINARY,batch-1)['programs'][CNI])
            forward[key] = verify_prediction(db,views,key,row['view'],archive['result'],verified,skill)
    comparisons, deltas = {}, {}
    for batch,replay_value in replays.items():
        before = {key:pair[0] for key,pair in replay_value['pairs'].items()}
        candidate = {key:pair[1] for key,pair in replay_value['pairs'].items()}
        source_errors = {role:shared_check(views,paths,bank)
                         for role,bank in (('incumbent',before),('candidate',candidate))}
        deltas[batch] = {**{k:v for k,v in replay_value.items() if k!='pairs'},
                         'new_conflicts':len(source_errors['candidate']-source_errors['incumbent']),
                         'fixed_conflicts':len(source_errors['incumbent']-source_errors['candidate'])}
        comparisons[f'B{batch}'] = {'incumbent':before,'adopted':candidate,
                                    'adopted_local':predict(paths,candidate,linked=False),
                                    'adopted_linked':predict(paths,candidate,linked=True)}
    comparisons['forward'] = {'adopted':forward,'adopted_local':predict(paths,forward,linked=False),
                               'adopted_linked':predict(paths,forward,linked=True)}
    immutable_json(out/'predictions.json',comparisons)
    assert sha(grade_file)==grade_sha
    labels = read(grade_file)
    stats = {name:{arm:score(views,pred,labels) for arm,pred in values.items()} for name,values in comparisons.items()}
    result = {'source_path_forms':dict(Counter(kind for values in paths.values() for kind,_ in values)),
              'source_witness_mothers':sum(bool(p) for p in paths.values()),
              'source_witness_native_non_entails':sum(bool(p) and labels[k][TASK]['answer']!=ENTAILMENT for k,p in paths.items()),
              'natural_adoption_replays':deltas,'condition_results':stats,
              'matched_shared_independent_and_direct':True,'paid_responses_verified':len(verified),
              'new_model_requests':0,'ledger':totals,'runner_sha256':spec['runner_sha256']}
    immutable_json(out/'summary.json',result)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**result},sort_keys=True))


if __name__=='__main__':
    main()
