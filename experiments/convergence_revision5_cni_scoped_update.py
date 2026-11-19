"""Replay a rejected ContractNLI bundle update at its calibrated hypothesis scope."""

import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import sqlite3
from statistics import mean

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, pointer as fit_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_linked_evidence import DATASET, span_inventory
from experiments.convergence_revision5_m2_cni_disposition_retention import verify_prediction
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_schema_control import measure_schema
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


TASK = 'nda-5'
HOME = BASE / 'revision5_CNI_scoped_update_20261119'
POINTER = HANDOFF / 'revision5_CNI_scoped_update_current.json'
DONE = 'settled_CNI_scoped_update_forward_TRAIN'
MISMATCH = HANDOFF / 'revision5_CNI_scoped_update_wire_mismatch_20261119.json'
POLICIES = ('incumbent', 'whole_candidate', 'hypothesis_route', 'source_checked_route', 'direct')
REVIEW = (
    ('affiliate_employees_only', 28, 'employees of companies directly or indirectly owned or controlled'),
    ('recipient_employees', 20, 'those of its officers, directors and employees'),
    ('ambiguous_duty', 25, 'hold and maintain the Confidential Information in the strictest of confidence'),
)


def scored(source, gold, result):
    grades = {}
    for view in source['views']:
        task = view['id']
        native = result[task]
        grades[task] = grade_view(DATASET, view, gold[task], native['answer'], native['evidence_sentence_ids'])
    return grades


def delta(sources, gold, prior, changed):
    gains = Counter()
    for source in sources:
        key = source['key']
        before = scored(source, gold[key], prior[key]['native'])
        after = scored(source, gold[key], changed[key]['native'])
        for task in before:
            gains[task] += after[task]['grade'] - before[task]['grade']
    return gains


def verify_public_wire(db, source, identity):
    key = source['key']
    physical_wire(db, {key}, identity, key)
    raw, = db.execute('select result from calls where id=?',(identity,)).fetchone()
    result = json.loads(raw)
    request = read(Path(result['artifact_directory'])/'request.json')['payload']
    user, = (row['content'] for row in request['messages'] if row['role']=='user')
    actual = json.loads(user)['public']
    cell, = common_cells(source)
    expected = source_bundle(cell)['public']
    assert actual == expected
    doc, = actual['shared_documents'].values()
    assert doc['evidence_units'] and len(doc['evidence_units'])==len(doc['sentence_spans'])


def materials():
    root = ROOT / read(BOOTSTRAP)['artifact_root']
    spec = read(root / 'binding.json')
    assert digest(spec) == root.name
    roster = load_roster(spec)
    cohorts = [[s for s in batch if s['dataset']==DATASET] for batch in roster[:5]]
    assert all(len(batch)==3 for batch in cohorts)
    assert all(s['project_split']=='train' for batch in cohorts for s in batch)
    journal = TrainingJournal(root, spec, roster)
    fit = ROOT / read(fit_pointer(4))['artifact_root']
    fit_binding, fit_end = (read(fit / name) for name in ('binding.json', 'terminal.json'))
    table = read(fit / 'matched_decisions.json')
    assert fit.name==digest(fit_binding) and fit_end['batch']==4 and not fit_end['TEST_opened']
    assert digest(table) == fit_end['matched_decisions_sha256']
    assert all(sha(fit/'source_snapshot'/file)==value for file,value in fit_binding['source_sha256'].items())
    folder = fit / 'candidates' / EXTERNAL_ARM / DATASET
    decision = read(folder / 'decision.json')
    assert decision == table['teacher'][EXTERNAL_ARM][DATASET]
    assert decision['selected']=='incumbent' and decision['native_utility_delta']>0
    history = read(folder / 'prior_TRAIN_regression.json')
    measured = read(folder / 'measurements.json')
    assert not history['holds'] and digest(history)==decision['earlier_TRAIN_regression']['evidence_sha256']
    assert digest(measured['predictions'])==decision['predictions_sha256']
    assert all(DATASET not in journal.library(EXTERNAL_ARM,n)['schema_proposals'] for n in (3,4))
    assert journal.library(EXTERNAL_ARM,3)['programs'][DATASET]==journal.library(EXTERNAL_ARM,4)['programs'][DATASET]
    incoming, stages, observations = {}, {}, {}
    train_sources = {s['key']:s for cohort in cohorts for s in cohort}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        known = set()
        for batch in (4,5):
            stage = ROOT / read(observe_pointer(batch))['artifact_root']
            binding, terminal = (read(stage / n) for n in ('binding.json','terminal.json'))
            assert digest(binding)==stage.name and not terminal['TEST_opened']
            assert all(sha(stage/'source_snapshot'/file)==value for file,value in binding['source_sha256'].items())
            stages[str(batch)] = sha(stage/'terminal.json')
            observations[batch] = binding
            receipt = journal._observations(EXTERNAL_ARM,batch)
            assert terminal['observation_receipts'][EXTERNAL_ARM]==receipt['train_observation_sha256']
            for source in cohorts[batch-1]:
                key = source['key']
                saved = read(journal.directory(EXTERNAL_ARM,batch)/'predictions'/(digest(key)+'.json'))
                assert digest(saved)==receipt['predictions'][key]
                incoming[key] = saved['result']
        for bank in (history['before'], history['candidate'], measured['predictions'], incoming):
            for key, result in bank.items():
                assert key in train_sources
                identity = verify_prediction(db,key,result)
                if identity not in known:
                    verify_public_wire(db,train_sources[key],identity)
                    known.add(identity)
    labels_file = observations[4]['native_grade_paths'][DATASET]
    assert observations[5]['native_grade_paths'][DATASET]==labels_file and 'train' in Path(labels_file).parts
    grade_hash = observations[4]['native_grade_sha256'][labels_file]
    assert sha(ROOT/labels_file)==grade_hash==observations[5]['native_grade_sha256'][labels_file]
    # Calibration scores use only the B1–B4 keys. B5 scoring follows the prediction seal.
    earlier = sum(cohorts[:3],[])
    all_grades = read(ROOT/labels_file)
    calibration = {s['key']:all_grades[s['key']] for s in earlier+cohorts[3]}
    prior = delta(earlier,calibration,history['before'],history['candidate'])
    current = delta(cohorts[3],calibration,incoming,measured['predictions'])
    selected = sorted(task for task in prior if prior[task]>0)
    assert selected==[TASK] and (sum(prior.values()),prior[TASK],sum(current.values()),current[TASK])==(-10,1,9,2)
    reviews = {}
    for source, (kind, index, cue) in zip(cohorts[4],REVIEW,strict=True):
        view = next(v for v in source['views'] if v['id']==TASK)
        assert cue in span_inventory(view)[index]
        reviews[source['key']] = {'type':kind,'span':index,'source_sha256':digest(view['public'])}
    files = (Path(__file__).resolve().relative_to(ROOT),
             'experiments/convergence_parse_runtime.py',
             'experiments/convergence_revision5_m2_cni_disposition_retention.py',
             'experiments/convergence_revision5_m2_cumulative_audit.py',
             'legal_skill_guard/paired_interfaces/convergence_actors.py',
             'legal_skill_guard/paired_interfaces/convergence_schema_control.py',
             'legal_skill_guard/paired_interfaces/control_answers.py',
             'legal_skill_guard/skill_evolution/clients.py','legal_skill_guard/rr/client.py')
    protocol = {'study':'B4_CNI_hypothesis_scoped_update_on_B5_TRAIN', 'TRAIN_only':True,
                'calibration_hypotheses':selected, 'calibration_mothers':len(earlier),
                'calibration_delta_all':sum(prior.values()),'calibration_delta_scoped':prior[TASK],
                'B4_fit_delta_all':sum(current.values()),'B4_fit_delta_scoped':current[TASK],
                'fit_terminal_sha256':sha(fit/'terminal.json'),'observation_terminal_sha256':stages,
                'public_wire':'original_explicit_zero_based_spans_for_both_readers',
                'invalid_predecessor_receipt_sha256':sha(MISMATCH),
                'proposal_sha256':digest(measured['candidate']), 'cohort_binding':digest(cohorts[4]),
                'review_binding':digest(reviews), 'grade_sha256':grade_hash,'verified_archived_reads':len(known),
                'sources_sha256':{str(file):sha(ROOT/file) for file in files},'executor':fit_binding['executor'],
                'planned_requests':len(cohorts[4]),
                'claim_condition':'Improve the selected native hypothesis with an operative recipient-scope witness. '
                                  'The source-checked policy must beat the direct source rule on the same cohort '
                                  'to justify more readings for this route.',
                'design':'Reuse the B5 pre-update incumbent and replay the exact B4 reversible-schema candidate. '
                         'Compare full adoption and hypothesis routing using the same two response bundles.'}
    return protocol,cohorts[4],incoming,measured['candidate'],reviews,labels_file


def source_supported(review, answer):
    return (review['type']=='recipient_employees' and answer['answer']=='Entailment'
            and review['span'] in answer['evidence_sentence_ids'])


def outputs(incumbent,candidate,review):
    row = candidate[TASK]
    direct = incumbent[TASK]
    if review['type']=='recipient_employees':
        direct = {'answer':'Entailment','evidence_sentence_ids':[review['span']]}
    return {
        'incumbent':incumbent,
        'whole_candidate':candidate,
        'hypothesis_route':{**incumbent,TASK:row},
        'source_checked_route':{**incumbent,TASK:row} if source_supported(review,row) else incumbent,
        'direct':{**incumbent,TASK:direct},
    }


def score(cohort,predictions,labels):
    rows = {p:{m:[] for m in ('grade','evidence_f1','grounded_grade')} for p in POLICIES}
    for source in cohort:
        key = source['key']
        for policy,native in predictions[key].items():
            for task,r in scored(source,labels[key],native).items():
                for metric,value in (('grade',r['grade']),('evidence_f1',r['evidence_f1']),
                                     ('grounded_grade',r['grade']*r['evidence_f1'])):
                    rows[policy][metric].append({'source':key,'view':task,'grade':value})
    metrics = {p:{k:{m:mean(r['grade'] for r in rr if k=='bundle' or r['view']==TASK)
                     for m,rr in values.items()} for k in ('bundle','selected_hypothesis')}
               for p,values in rows.items()}
    paired = {p:paired_source_effect(rows['incumbent']['grade'],rows[p]['grade']) for p in POLICIES[1:]}
    return metrics,paired


def run(execute):
    protocol,cohort,incoming,proposal,reviews,labels_file = materials()
    out = HOME / digest(protocol)
    immutable_json(out/'binding.json',protocol)
    if (out/'terminal.json').exists():
        print(json.dumps(read(out/'terminal.json'),sort_keys=True),flush=True)
        return
    if not execute:
        write_status(out,{'status':'prepared','planned_requests':protocol['planned_requests']},POINTER)
        print(str(out.relative_to(ROOT)),flush=True)
        return
    assert ROOT/read(POINTER)['artifact_root']==out
    lock = (out/'driver.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for name,expected in protocol['sources_sha256'].items():
        path = out/'source_snapshot'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('xb') as stream:
                stream.write((ROOT/name).read_bytes())
        assert sha(path)==expected
    run_id = 'convergence-revision5-CNI-scoped-update-'+out.name[:16]
    ledger = EvolutionLedger(LEDGER,run_id=run_id,sources={'train':[s['key'] for s in cohort],'dev':[],'test':[]},binding=protocol)
    reader = FrozenExecutor(ledger,out,protocol['executor'])
    reader.readiness()
    predictions,reads = {},[]
    for n,source in enumerate(cohort):
        key = source['key']
        write_status(out,{'status':'running','settled_mothers':n},POINTER)
        cell, = common_cells(source)
        row = measure_schema(reader,out,cell,proposal,'skill_actor')
        reads.append(row)
        immutable_json(out/'reads'/f'{n}.json',row)
        predictions[key] = outputs(incoming[key]['native'],row['native'],reviews[key])
        print(json.dumps({'settled_mothers':n+1,'completed':row['production_error'] is None}),flush=True)
    immutable_json(out/'predictions.json',predictions)
    tokens = 0
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for source,row in zip(cohort,reads,strict=True):
            identity = row['physical_call_id']
            verify_public_wire(db,source,identity)
            cell, = common_cells(source)
            assert row['proposal_sha256']==protocol['proposal_sha256'] and row['source_sha256']==digest(cell)
            tokens += row['usage']['total_tokens']
        statuses = dict(db.execute('select status,count(*) from calls group by status'))
    assert not statuses.get('reserved') and sha(ROOT/labels_file)==protocol['grade_sha256']
    metrics,paired = score(cohort,predictions,read(ROOT/labels_file))
    result = {'status':DONE,'partition':'TRAIN','original_decisions_preserved':True,'forward_mothers':len(cohort),
              'calibration_delta_all':protocol['calibration_delta_all'],'calibration_delta_scoped':protocol['calibration_delta_scoped'],
              'B4_fit_delta_all':protocol['B4_fit_delta_all'],'B4_fit_delta_scoped':protocol['B4_fit_delta_scoped'],
              'verified_archived_reads':protocol['verified_archived_reads'],'new_calls':len(reads),'tokens':tokens,'ledger':statuses,
              'native_results':metrics,'paired_labels_vs_incumbent':paired,
              'source_checked_route_replacements':sum(p['source_checked_route']!=p['incumbent'] for p in predictions.values()),
              'finish_reasons':dict(Counter(row['finish_reason'] for row in reads)),
              'predictions_sha256':sha(out/'predictions.json'),'runner_sha256':sha(Path(__file__))}
    immutable_json(out/'terminal.json',result)
    write_status(out,{'status':DONE,'settled_mothers':len(cohort)},POINTER)
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
