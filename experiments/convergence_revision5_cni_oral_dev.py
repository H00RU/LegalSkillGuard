"""Apply the TRAIN-bound oral-scope checks to the existing CNI B8 DEV cells."""

import base64
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments.convergence_formal_curves import pointer
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY
from experiments.convergence_revision5_cni_oral_scope import CNI, HOME, TASK, oral_proof, predict, score
from experiments.convergence_pilot_b0 import LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


TRAIN_STAGE = '500942105ae1e0689765753c5ec8b878f2278bf0d26504801f1ad2ee4b724ad6'
ARMS = (ORDINARY, EXTERNAL_ARM)
METHODS = ('original', 'same_clause', 'linked')


def verify_wire(db, source, result, verified):
    if 'schema_reads' in result:
        trace, = result['schema_reads']
        assert trace['native']==result['native']
        match_response = lambda actual: digest(actual['content'])==trace['response_sha256']
    else:
        entry, = result['reads']
        trace, = entry['execution']['traces']
        assert entry['native']==result['native']
        match_response = lambda actual: actual['content']==trace['raw_content']
    identity = trace['physical_call_id']
    assert identity is not None
    status,role,key,purpose,request_hash,result_json = db.execute(
        'select status,role,source,purpose,request_hash,result from calls where id=?',(identity,)).fetchone()
    assert (status,role,key,purpose)==('completed','executor',source,'skill_dev')
    if identity not in verified:
        actual = json.loads(result_json)
        path = Path(actual['artifact_directory'])
        req,wire = (read(path/name) for name in ('request.json','wire_request.json'))
        body=base64.b64decode(wire['body_b64'],validate=True)
        assert hashlib.sha256(body).hexdigest()==wire['body_sha256'] and json.loads(body)==req['payload']
        assert req['source']==source and req['id']==identity
        assert req['request_hash']==actual['request_hash']==request_hash and read(path/'result.json')==actual
        assert req['payload']['model']=='Qwen/Qwen3-8B' and actual['thinking_requested'] is False
        assert match_response(actual)
        verified.add(identity)
    return result['native']


def paired(views, labels, before, after):
    def rows(data):
        result = []
        for key,prediction in data.items():
            value = prediction[TASK]
            grade = grade_view(CNI,views[key]['view'],labels[key][TASK],value['answer'],value['evidence_sentence_ids'])
            result.append({'source':key,'view':TASK,'grade':grade['grade']*grade['evidence_f1']})
        return result
    return paired_source_effect(rows(before),rows(after))


def run():
    train = HOME/TRAIN_STAGE
    fit = read(train/'protocol.json')
    assert digest(fit)==train.name and sha(Path(__file__).with_name('convergence_revision5_cni_oral_scope.py'))==fit['runner_sha256']
    assert read(train/'summary.json')['runner_sha256']==fit['runner_sha256']
    stage = ROOT/read(pointer(8))['artifact_root']
    binding,terminal = (read(stage/file) for file in ('binding.json','terminal.json'))
    assert stage.name==digest(binding) and terminal['batch']==8 and not terminal['TEST_opened']
    assert all(sha(stage/'source_snapshot'/p)==h for p,h in binding['source_sha256'].items())
    root = ROOT/binding['checkpoint_root']
    study = read(root/'binding.json')
    assert digest(study)==binding['checkpoint_binding_sha256']
    b0 = ROOT/binding['b0_dev_data_root']
    cohort = read(b0/'public_DEV_sources.json')
    assert digest(cohort)==read(b0/'binding.json')['DEV_public_sha256']
    views = {row['key']:{'view':next(v for v in row['views'] if v['id']==TASK)}
             for row in cohort if row['dataset']==CNI and row['project_split']=='dev'}
    assert len(views)==16 and len(cohort)==80
    grade_path = study['grading_paths'][CNI]
    assert 'dev' in Path(grade_path).parts
    protocol = {'partition':'dev','frozen_TRAIN_rule_sha256':fit['runner_sha256'],
                'runner_sha256':sha(Path(__file__)),'TRAIN_terminal_sha256':sha(train/'summary.json'),
                'archived_B8_DEV_terminal_sha256':sha(stage/'terminal.json'),
                'DEV_cohort_sha256':digest(views),'grade_sha256':study['grading_file_sha256'][grade_path],
                'hypothesis':TASK,'arms':list(ARMS),'methods':list(METHODS),'new_model_requests':0}
    out = HOME/'B8_DEV'/digest(protocol)
    immutable_json(out/'protocol.json',protocol)
    paths = {key:oral_proof(row['view']) for key,row in views.items()}
    measured, scored, verified = {}, {}, set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for arm in ARMS:
            directory = root/'dev'/'B8'/arm
            task = read(directory/'task.json')
            seal = verify(read(directory/'prediction_seal.json'),'prediction_seal_sha256')
            cell = verify(read(directory/'scores.json'),'cell_sha256')
            assert cell['partition']=='dev' and cell['cell_sha256']==terminal['cell_sha256'][arm]
            assert seal['task_sha256']==digest(task) and cell['prediction_seal_sha256']==seal['prediction_seal_sha256']
            assert seal['predictions_sha256'].keys()=={row['key'] for row in cohort}
            bank = {}
            for source,view in views.items():
                saved = read(directory/'predictions'/(digest(source)+'.json'))
                assert seal['predictions_sha256'][source]==digest(saved) and saved['dataset']==CNI
                assert saved['source']==source and saved['library_sha256']==cell['libraries'][CNI]
                bank[source]=verify_wire(db,source,saved['result'],verified)
            measured[arm]={'original':bank,'same_clause':predict(paths,bank,linked=False),
                           'linked':predict(paths,bank,linked=True)}
            scored[arm]={r['source']:r for r in cell['source_scores'] if r['dataset']==CNI and r['view']==TASK}
    immutable_json(out/'projected_predictions.json',measured)
    assert sha(ROOT/grade_path)==protocol['grade_sha256']
    labels = read(ROOT/grade_path)
    estimates={}
    for arm,comparison in measured.items():
        for source,data in comparison['original'].items():
            value=data[TASK]
            grade=grade_view(CNI,views[source]['view'],labels[source][TASK],value['answer'],value['evidence_sentence_ids'])
            assert scored[arm][source]['grade']==grade['grade']
            assert scored[arm][source]['native_metrics']['evidence_f1']==grade['evidence_f1']
        estimates[arm] = {'metrics':{mode:score(views,data,labels) for mode,data in comparison.items()},
                          'linked_minus_original_joint_evidence':paired(views,labels,comparison['original'],comparison['linked']),
                          'linked_minus_same_clause_joint_evidence':paired(views,labels,comparison['same_clause'],comparison['linked'])}
    summary={'frozen_TRAIN_rule_sha256':fit['runner_sha256'],'arm_results':estimates,
             'source_cues_found':sum(bool(value) for value in paths.values()),
             'source_cues_with_non_entailment_reference':sum(bool(value) and labels[key][TASK]['answer']!='Entailment'
                                                              for key,value in paths.items()),
             'unique_cached_DEV_physical_responses_verified':len(verified),'new_model_requests':0,
             'B8_DEV_tables_revised':False,'runner_sha256':protocol['runner_sha256']}
    immutable_json(out/'summary.json',summary)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)), **summary},sort_keys=True))


if __name__=='__main__':
    run()
