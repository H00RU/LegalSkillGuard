"""Check the TRAIN-bound allowance compiler on the original B8 Airline DEV cell."""

import json
from collections import Counter
from pathlib import Path
import sqlite3

from experiments.convergence_formal_curves import pointer
from experiments.convergence_pilot_b0 import LEDGER, ROOT, read, sha
from experiments.convergence_revision5_airline_allowance import (
    ARM, BENCHMARK, DATASET, HOME, inventory, paid_answer, policy, public_geography, totals,
)
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


TRAIN_STAGE = '617e38400510cf901091dccf20f805662c3d4071b566fd91317ed24ffca406cd'
METHODS = ('joint_assignment','source_order','overweight_only_order','exact_enumeration')


def run():
    experiment = HOME/TRAIN_STAGE
    train = read(experiment/'binding.json')
    assert digest(train)==experiment.name
    assert train['runner_sha256']==sha(Path(__file__).with_name('convergence_revision5_airline_allowance.py'))
    assert train['benchmark_assignment_reference_sha256']==sha(BENCHMARK)
    stage = ROOT/read(pointer(8))['artifact_root']
    runtime,run_end = (read(stage/p) for p in ('binding.json','terminal.json'))
    assert stage.name==digest(runtime) and run_end['batch']==8 and not run_end['TEST_opened']
    assert all(sha(stage/'source_snapshot'/f)==h for f,h in runtime['source_sha256'].items())
    checkpoint = ROOT/runtime['checkpoint_root']
    study = read(checkpoint/'binding.json')
    assert digest(study)==runtime['checkpoint_binding_sha256']
    current = checkpoint/'dev'/'B8'/ARM
    task = read(current/'task.json')
    seal = verify(read(current/'prediction_seal.json'),'prediction_seal_sha256')
    archived = verify(read(current/'scores.json'),'cell_sha256')
    assert archived['cell_sha256']==run_end['cell_sha256'][ARM] and archived['partition']=='dev'
    assert seal['task_sha256']==digest(task) and archived['prediction_seal_sha256']==seal['prediction_seal_sha256']
    b0 = ROOT/runtime['b0_dev_data_root']
    full = read(b0/'public_DEV_sources.json')
    assert digest(full)==read(b0/'binding.json')['DEV_public_sha256'] and len(full)==80
    assert seal['predictions_sha256'].keys()=={s['key'] for s in full}
    sources = {s['key']:s for s in full if s['dataset']==DATASET and s['project_split']=='dev'}
    assert len(sources)==16
    grade = study['grading_paths'][DATASET]
    assert 'dev' in Path(grade).parts
    protocol = {'experiment':'common_allowance_rule_B8_DEV','TRAIN_rule_sha256':train['runner_sha256'],
                'TRAIN_summary_sha256':sha(experiment/'summary.json'),'DEV_cohort_sha256':digest(sources),
                'original_B8_DEV_terminal_sha256':sha(stage/'terminal.json'),
                'DEV_grade_file_sha256':study['grading_file_sha256'][grade],
                'runner_sha256':sha(Path(__file__)),'unsupported_policy':'retain the original sealed result',
                'new_model_requests':0}
    out=HOME/'B8_DEV'/digest(protocol)
    immutable_json(out/'binding.json',protocol)
    geo=public_geography()
    paid,results=set(),{}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for key,source in sources.items():
            saved = read(current/'predictions'/(digest(key)+'.json'))
            assert saved['source']==key and saved['dataset']==DATASET
            assert saved['library_sha256']==archived['libraries'][DATASET]
            assert seal['predictions_sha256'][key]==digest(saved)
            before=paid_answer(db,source,saved['result'],paid,expected_purpose='skill_dev')
            public=source['views'][0]['public']
            row={'original':before}
            try:
                rule=policy(public,geo)
                _,bags=inventory(public['facts'],rule)
                row.update(totals(bags,rule))
                row['route']=rule['route']
            except ValueError as error:
                row['unresolved']=str(error)
                row.update(dict.fromkeys(METHODS,before))
            results[key]=row
    assert len(paid)==16
    immutable_json(out/'prediction_replay.json',results)
    assert sha(ROOT/grade)==protocol['DEV_grade_file_sha256']
    native=read(ROOT/grade)
    raw_scores={r['source']:r for r in archived['source_scores'] if r['dataset']==DATASET}
    cells={mode:[] for mode in ('original',*METHODS)}
    for key,r in results.items():
        for mode in cells:
            outcome=grade_view(DATASET,sources[key]['views'][0],native[key]['native'],r[mode])['grade']
            if mode=='original':
                assert raw_scores[key]['answer']==r[mode] and raw_scores[key]['grade']==outcome
            cells[mode].append({'source':key,'view':'native','grade':outcome})
    summary={'common_rule_only':True,'DEV_mothers':len(results),'original_physical_responses_verified':len(paid),
             'source_supported_mothers':sum('unresolved' not in r for r in results.values()),
             'unresolved_reasons':dict(Counter(r['unresolved'] for r in results.values() if 'unresolved' in r)),
             'joint_different_than_source_order_mothers':sum(r['joint_assignment']!=r['source_order']
                                                            for r in results.values()),
             'exact_native':{m:sum(r['grade'] for r in rows) for m,rows in cells.items()},
             'paired_joint_minus_original':paired_source_effect(cells['original'],cells['joint_assignment']),
             'paired_joint_minus_source_order':paired_source_effect(cells['source_order'],cells['joint_assignment']),
             'new_model_requests':0,'TRAIN_rule_sha256':train['runner_sha256'],'runner_sha256':protocol['runner_sha256']}
    immutable_json(out/'summary.json',summary)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**summary},sort_keys=True))


if __name__=='__main__':
    run()
