"""Compare two lossless transports for the empty MAUD evidence field."""

import argparse
import base64
from collections import Counter
from copy import deepcopy
import fcntl
from itertools import product
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY, pointer as fit_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_m2_cni_disposition_retention import verify_prediction
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


MAUD = 'MAUD'
MODES = ('literal_constant', 'omit_reconstruct')
FIELD = 'evidence_sentence_ids'
SCHEMA_PROMPT = 'Return compact JSON matching this exact schema: '
HOME = BASE / 'revision5_MAUD_zero_evidence_20261119'
POINTER = HANDOFF / 'revision5_MAUD_zero_evidence_current.json'
DONE = 'settled_MAUD_empty_evidence_wire_TRAIN'


def transport(payload, mode):
    """Replace only fields whose native domain consists of the empty list."""
    messages = deepcopy(payload['messages'])
    system, = (m for m in messages if m['role'] == 'system')
    prefix, embedded = system['content'].split(SCHEMA_PROMPT, 1)
    old = payload['response_format']['json_schema']['schema']
    schema = json.loads(embedded)
    if old != schema or mode not in MODES:
        raise ValueError('Require the same unchanged native schema in both request positions')
    tasks = schema['properties']['value']['properties']
    for item in tasks.values():
        fields = item['properties']
        if set(fields) != {'answer', FIELD} or fields[FIELD]['type'] != 'array' or fields[FIELD]['maxItems'] != 0:
            raise ValueError('The transport cannot erase variable evidence')
        if mode == 'literal_constant':
            fields[FIELD] = {'const': []}
        else:
            del fields[FIELD]
            item['required'].remove(FIELD)
    system['content'] = prefix + SCHEMA_PROMPT + json.dumps(schema, ensure_ascii=False, separators=(',', ':'))
    return messages, schema


def restore(value, schema, original, mode):
    jsonschema.validate(value, schema)
    result = deepcopy(value)
    if mode == 'omit_reconstruct':
        for task in result['value'].values():
            task[FIELD] = []
    jsonschema.validate(result, original)
    return result


def verify_exhaustive(payload):
    schema = payload['response_format']['json_schema']['schema']
    tasks = schema['properties']['value']['properties']
    outcomes = [task['properties']['answer']['enum'] for task in tasks.values()]
    for answers in product(*outcomes):
        native = {'value':{key:{'answer':answer,FIELD:[]} for key,answer in zip(tasks,answers,strict=True)}}
        for mode in MODES:
            _, reduced_schema = transport(payload,mode)
            reduced = deepcopy(native)
            if mode == 'omit_reconstruct':
                for task in reduced['value'].values():
                    del task[FIELD]
            assert restore(reduced,reduced_schema,schema,mode)==native
    return len(list(product(*outcomes)))


def response(db, source, physical_id):
    physical_wire(db,{source},physical_id,source)
    row, = db.execute('select result from calls where id=?',(physical_id,)).fetchone()
    raw = json.loads(row)
    folder = Path(raw['artifact_directory'])
    wire = read(folder/'wire_request.json')
    return raw, json.loads(base64.b64decode(wire['body_b64'],validate=True))


def materials():
    root = ROOT/read(BOOTSTRAP)['artifact_root']
    study = read(root/'binding.json')
    assert root.name==digest(study)
    roster = load_roster(study)
    journal = TrainingJournal(root,study,roster)
    stage, open_stage, train_terminal = bound_stage(observe_pointer(4))
    fit, fit_binding, fit_terminal = bound_stage(fit_pointer(4))
    assert sha(stage/'terminal.json')==fit_binding['observations_terminal_sha256']
    decisions = read(fit/'matched_decisions.json')
    assert digest(decisions)==fit_terminal['matched_decisions_sha256']
    cases, archived = [], set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        status = dict(db.execute('select status,count(*) from calls group by status'))
        fit_results = {}
        for arm in (ORDINARY,EXTERNAL_ARM):
            measured = read(fit/'candidates'/arm/MAUD/'measurements.json')['predictions']
            decision = decisions['teacher'][arm][MAUD]
            assert digest(measured)==decision['predictions_sha256'] and decision['selected']=='candidate'
            fit_results[arm] = measured
        for source in (s for s in roster[3] if s['dataset']==MAUD):
            assert source['project_split']=='train'
            key = source['key']
            case = {'source':source, 'baseline':{}, 'candidate':{}}
            for arm in (ORDINARY,EXTERNAL_ARM):
                obs = journal._observations(arm,4)
                assert obs['train_observation_sha256']==train_terminal['observation_receipts'][arm]
                stored = read(journal.directory(arm,4)/'predictions'/(digest(key)+'.json'))
                assert digest(stored)==obs['predictions'][key]
                inc, cand = stored['result'], fit_results[arm][key]
                for role, result in (('baseline',inc),('candidate',cand)):
                    physical_id = verify_prediction(db,key,result)
                    raw,payload = response(db,key,physical_id)
                    archived.add(physical_id)
                    item = {'native':result['native'],'finished':raw['finish_reason'],'id':physical_id,
                            'usage':raw['usage']}
                    if role=='baseline' and arm==ORDINARY:
                        case['payload'] = payload
                        case['trailing_space'] = len(raw['content'])-len(raw['content'].rstrip())
                        case['capped_in_evidence'] = raw['finish_reason']=='length' and raw['content'].rstrip().endswith(
                            '"' + FIELD + '":[')
                    case[role][arm]=item
            cases.append(case)
    assert len(cases)==3 and sum(x['capped_in_evidence'] for x in cases)==1
    assert all(verify_exhaustive(x['payload'])==8 for x in cases)
    for case in cases:
        if case['capped_in_evidence']:
            assert len({r['id'] for r in case['baseline'].values()})==1 and case['trailing_space']==16346
    grader = open_stage['native_grade_paths'][MAUD]
    assert 'train' in Path(grader).parts
    code = ('experiments/convergence_revision5_maud_zero_evidence.py',
            'experiments/convergence_revision5_cni_nonsolicitation.py',
            'experiments/convergence_revision5_m2_cni_disposition_retention.py',
            'experiments/convergence_revision5_m2_cumulative_audit.py',
            'legal_skill_guard/skill_evolution/native.py','legal_skill_guard/rr/client.py')
    lock = {'study':'MAUD_B4_empty_evidence_native_preserving_transport', 'TRAIN_only':True,
            'source_sha256':{n:sha(ROOT/n) for n in code},'cases_sha256':digest(cases),
            'observation_terminal_sha256':sha(stage/'terminal.json'),'fit_terminal_sha256':sha(fit/'terminal.json'),
            'executor':fit_binding['executor'],'native_grade_sha256':open_stage['native_grade_sha256'][grader],
            'archived_reads':len(archived),'new_calls':2*len(cases),'native_signatures_checked':8,
            'forecast':'Both transports preserve every native answer. If the gains are transport recovery, '
                       'both should complete the length-capped mother and preserve previously correct answers.'}
    return lock,cases,grader,status


def result_metrics(cases,prediction_pairs,grades):
    results = {}
    for case,extra in zip(cases,prediction_pairs,strict=True):
        source = case['source']
        for mode, row in {**extra,**{f'original_{a}':case['baseline'][a] for a in case['baseline']},
                                **{f'candidate_{a}':case['candidate'][a] for a in case['candidate']}}.items():
            totals = results.setdefault(mode, Counter())
            totals['responses_completed'] += int(row['finished']=='stop')
            totals['output_tokens'] += row['usage']['completion_tokens']
            for view in source['views']:
                output = row['native'][view['id']]
                expected = grades[source['key']][view['id']]
                native = grade_view(MAUD,view,expected,output['answer'],output[FIELD])
                totals['correct'] += int(native['grade'])
                totals['handled'] += int(output['answer'] is not None)
                totals['tasks'] += 1
                if not case['capped_in_evidence']:
                    totals['correct_on_originally_complete_mothers'] += int(native['grade'])
    return results


def run(execute):
    lock,cases,grader,pre = materials()
    out = HOME/digest(lock)
    immutable_json(out/'binding.json',lock)
    if (out/'terminal.json').exists():
        print(json.dumps(read(out/'terminal.json'),sort_keys=True),flush=True)
        return
    if not execute:
        write_status(out,{'status':'prepared','planned_requests':lock['new_calls']},POINTER)
        print(str(out.relative_to(ROOT)),flush=True)
        return
    assert ROOT/read(POINTER)['artifact_root']==out
    flag=(out/'driver.lock').open('a')
    fcntl.flock(flag,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for name,h in lock['source_sha256'].items():
        path=out/'source_snapshot'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('xb') as f:
                f.write((ROOT/name).read_bytes())
        assert sha(path)==h
    run_id = 'convergence-revision5-MAUD-zero-evidence-'+out.name[:16]
    ledger = EvolutionLedger(LEDGER,run_id=run_id,sources={'train':[c['source']['key'] for c in cases],'dev':[],'test':[]},binding=lock)
    reader = FrozenExecutor(ledger,out,lock['executor'])
    reader.readiness()
    pairs=[]
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for index,case in enumerate(cases):
            key = case['source']['key']
            pair = {}
            for mode in MODES if index%2==0 else MODES[::-1]:
                call = f'{run_id}:{index}:{mode}'
                messages,schema = transport(case['payload'],mode)
                expected = reader.payload(messages=messages,thinking=False,schema=schema)
                prior = case['payload']
                assert all(expected[name]==value for name,value in prior.items() if name not in ('messages','response_format'))
                assert all(m in messages for m in prior['messages'] if m['role']=='user')
                write_status(out,{'status':'running','settled_pairs':index,'current_call':call},POINTER)
                result = reader.generate(call,source=key,purpose='skill_actor',messages=messages,thinking=False,schema=schema)
                raw,payload = response(db,key,call)
                assert payload==expected and raw['content']==result['content']
                original = prior['response_format']['json_schema']['schema']
                values = {name:{'answer':None,FIELD:[]} for name in original['properties']['value']['properties']}
                if raw['finish_reason']=='stop':
                    try:
                        values=restore(json.loads(raw['content']),schema,original,mode)['value']
                    except (ValueError,jsonschema.ValidationError):
                        pass
                pair[mode] = {'native':values,'finished':raw['finish_reason'],'usage':raw['usage'],'id':call}
                immutable_json(out/'reads'/f'{index}_{mode}.json',pair[mode])
                print(json.dumps({'mother':index,'mode':mode,'finish_reason':raw['finish_reason']}),flush=True)
            pairs.append(pair)
        now = dict(db.execute('select status,count(*) from calls group by status'))
    assert not now.get('reserved') and now['completed']-pre['completed']==lock['new_calls']
    immutable_json(out/'predictions.json',pairs)
    assert sha(ROOT/grader)==lock['native_grade_sha256']
    grades=read(ROOT/grader)
    terminal={'status':DONE,'new_calls':lock['new_calls'],'archived_reads':lock['archived_reads'],
              'ledger':now,'partition':'TRAIN','original_libraries_preserved':True,
              'native_signatures_preserved':8,'exact_native_results':result_metrics(cases,pairs,grades),
              'methods_equivalent_per_source':all(p['literal_constant']['native']==p['omit_reconstruct']['native'] for p in pairs),
              'capped_response_original_whitespace_chars':16346,
              'new_total_tokens':sum(row['usage']['total_tokens'] for p in pairs for row in p.values()),
              'runner_sha256':sha(Path(__file__)),'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',terminal)
    write_status(out,{'status':DONE,'settled_pairs':len(pairs)},POINTER)
    print(json.dumps(terminal,sort_keys=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
