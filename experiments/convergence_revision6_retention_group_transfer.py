"""Evaluate the two B5 acquisition decisions on exact archived fixed CNI DEV reads."""

import json
from pathlib import Path
import sqlite3
from statistics import mean

from experiments import convergence_revision5_cni_nonsolicitation as bound
from experiments import convergence_revision5_cni_oral_dev as wire
from experiments import convergence_revision6_retention_group_selection as selection
from experiments.convergence_formal_curves import pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE/'revision6_retention_group_transfer'
POINTER = HANDOFF/'revision6_retention_group_transfer_current.json'
POLICIES = ('chronological','candidate_driven')
CNI = selection.retention.DATASET
EXTERNAL = selection.retention.EXTERNAL_ARM


def native_request(db, source, result, proposal, program, verified):
    key = source['key']
    native = wire.verify_wire(db,key,result,verified)
    if proposal is None:
        execution = result['reads'][0]['execution']
        if execution['program_sha256'] != digest(program):
            raise ValueError('Require the B5 entering native consumer')
        trace = execution['traces'][0]
    else:
        trace, = result['schema_reads']
        if trace['proposal_sha256'] != digest(proposal):
            raise ValueError('Require the actual adopted schema proposal')
    identity = trace['physical_call_id']
    record = json.loads(db.execute('select result from calls where id=?',(identity,)).fetchone()[0])
    request = read(Path(record['artifact_directory'])/'request.json')['payload']
    body, = (m['content'] for m in request['messages'] if m['role']=='user')
    public = json.loads(body)['public']
    transport = {k:v for k,v in request.items() if k not in ('messages','response_format')}
    return native, {'public':public,'transport':transport}


def materials(db, saved_libraries):
    cases, predictions, inputs = {}, {}, {}
    stage_terminals, verified = {}, set()
    grade = None
    for policy,batch in zip(POLICIES,(8,4),strict=True):
        stage, spec, end = bound.bound_stage(pointer(batch))
        if spec['batch'] != batch or end['TEST_opened']:
            raise ValueError('Use preexisting sealed fixed-DEV checkpoints')
        stage_terminals[policy] = sha(stage/'terminal.json')
        checkpoint = ROOT/spec['checkpoint_root']
        study = read(checkpoint/'binding.json')
        journal = TrainingJournal(checkpoint,study,selection.retention.load_roster(study))
        library = journal.library(EXTERNAL,batch)
        proposal = library.get('schema_proposals',{}).get(CNI)
        required = saved_libraries[policy]
        program = library['programs'][CNI]
        if proposal != required['schema_proposal'] or program != required['program']:
            raise ValueError('The archived DEV reader must equal the acquired TRAIN policy snapshot')
        dev_path = ROOT/spec['b0_dev_data_root']
        raw = read(dev_path/'public_DEV_sources.json')
        if digest(raw) != read(dev_path/'binding.json')['DEV_public_sha256']:
            raise ValueError('Use the original authorization and exact source list')
        current = {s['key']:s for s in raw if s['dataset']==CNI and s['project_split']=='dev'}
        if len(current) != 16 or (cases and cases != current):
            raise ValueError('Both archives must cover the same sixteen CNI mothers')
        name = study['grading_paths'][CNI]
        label_binding = (name,study['grading_file_sha256'][name])
        if grade is not None and grade != label_binding:
            raise ValueError('The original native scorer binding changed')
        grade, cases = label_binding,current
        directory = checkpoint/'dev'/f'B{batch}'/EXTERNAL
        seal = verify(read(directory/'prediction_seal.json'),'prediction_seal_sha256')
        cell = verify(read(directory/'scores.json'),'cell_sha256')
        if (cell['cell_sha256'] != end['cell_sha256'][EXTERNAL]
                or cell['prediction_seal_sha256'] != seal['prediction_seal_sha256']
                or seal['task_sha256'] != digest(read(directory/'task.json'))
                or cell['libraries'][CNI] != library['snapshot_sha256']):
            raise ValueError('The archived native outputs must retain the original prediction seal')
        bank = predictions[policy] = {}
        sources = inputs[policy] = {}
        for key,source in cases.items():
            row = read(directory/'predictions'/(digest(key)+'.json'))
            if digest(row) != seal['predictions_sha256'][key] or row['public_source_sha256'] != digest(source):
                raise ValueError('An original DEV prediction changed or crossed sources')
            bank[key],sources[key] = native_request(db,source,row['result'],proposal,program,verified)
    if inputs['chronological'] != inputs['candidate_driven']:
        raise ValueError('Only the learned schema route may differ in the transfer comparison')
    if len(verified) != 2*len(cases):
        raise ValueError('Two different actual reads are required for every source')
    return cases,predictions,grade,stage_terminals,len(verified),digest(inputs['chronological'])


def score(cases, predictions, labels):
    metrics = {}
    for name, subtask in (('all_hypotheses',None),('retention','nda-20'),('disposition','nda-16')):
        bank = {}
        for policy in POLICIES:
            rows = []
            for key,source in cases.items():
                for view in source['views']:
                    task = view['id']
                    if subtask is not None and task != subtask:
                        continue
                    output = predictions[policy][key][task]
                    grade = grade_view(CNI,view,labels[key][task],output['answer'],output['evidence_sentence_ids'])
                    rows.append({'source':key,'view':task,**grade})
            bank[policy] = rows
        features = {}
        for feature in ('grade','evidence_f1'):
            features[feature] = paired_source_effect(*[
                [{**r,'grade':r[feature]} for r in bank[policy]] for policy in POLICIES])
        metrics[name] = {
            'native_tasks':len(bank[POLICIES[0]]),
            'scores':{role:{'correct':sum(r['grade'] for r in rows),
                            'evidence_f1':mean(r['evidence_f1'] for r in rows)} for role,rows in bank.items()},
            'paired_candidate_driven_minus_chronological':features,
        }
    return metrics


def run():
    fit = ROOT/read(selection.POINTER)['artifact_root']
    fitted = verify(read(fit/'terminal.json'),'terminal_sha256')
    if fit.name != digest(read(fit/'binding.json')) or fitted['TEST_opened']:
        raise ValueError('Use the original candidate-directed group decision')
    libraries = {policy:verify(read(fit/'TRAIN_batch_libraries'/f'{policy}.json'),'snapshot_sha256')
                 for policy in POLICIES}
    if {p:v['snapshot_sha256'] for p,v in libraries.items()} != fitted['library_sha256']:
        raise ValueError('A transferred reader was changed after TRAIN')
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        sources,bank,grade,archives,count,wire_hash = materials(db,libraries)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    binding = {'stage':'revision6_retention_group_transfer','fit_TERMINAL':fitted['terminal_sha256'],
               'original_DEV_terminals':archives,'matched_public_and_executor_sha256':wire_hash,
               'DEV_grade_sha256':grade[1],'TEST_opened':False,
               'source_sha256':{str(Path(p).relative_to(ROOT)):sha(Path(p)) for p in (
                   __file__,selection.__file__,wire.__file__)}}
    out = HOME/digest(binding)
    immutable_json(out/'binding.json',binding)
    pred = immutable_json(out/'sealed_predictions.json',bank)
    path = ROOT/grade[0]
    if 'dev' not in path.parts or sha(path) != grade[1]:
        raise ValueError('Use the exact native DEV scorer after sealing both policies')
    native = score(sources,bank,read(path))
    result = sealed({'status':'settled_revision6_retention_group_transfer','binding_sha256':out.name,
                     'native':native,'DEV_mothers':len(sources),'library_sha256':fitted['library_sha256'],
                     'same_source_same_executor_and_budget':True,'original_executor_calls_reused':count,
                     'predictions_sha256':pred,'new_executor_requests':0,'TEST_opened':False,'ledger':ledger},
                    'terminal_sha256')
    immutable_json(out/'terminal.json',result)
    write_status(out,{'status':result['status'],'terminal_sha256':result['terminal_sha256']},POINTER)
    print(out)


if __name__ == '__main__':
    run()
