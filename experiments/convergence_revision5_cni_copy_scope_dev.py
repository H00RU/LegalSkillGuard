"""Replay the settled TRAIN copy-creation control on the original B8 DEV cells."""

import json
from pathlib import Path
import sqlite3

from experiments.convergence_formal_curves import pointer
from experiments.convergence_revision5_cni_copy_scope import (
    DATASET, DONE, EXTERNAL_ARM, HOME, LEDGER, ORDINARY, POINTER, ROOT, TASK,
    bound_stage, estimate, matched_direct, read, sha, source_groups,
)
from experiments.convergence_revision5_cni_oral_dev import verify_wire
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


def run():
    train = ROOT/read(POINTER)['artifact_root']
    train_lock = read(train/'binding.json')
    train_end = read(train/'terminal.json')
    runner = Path(__file__).with_name('convergence_revision5_cni_copy_scope.py')
    assert train.name==digest(train_lock) and train_end['status']==DONE
    assert sha(runner)==train_lock['source_sha256'][str(runner.relative_to(ROOT))]
    assert sha(train/'paired_predictions.json')==train_end['predictions_sha256']
    stage,binding,terminal = bound_stage(pointer(8))
    root = ROOT/binding['checkpoint_root']
    study = read(root/'binding.json')
    assert digest(study)==binding['checkpoint_binding_sha256']
    b0=ROOT/binding['b0_dev_data_root']
    original=read(b0/'public_DEV_sources.json')
    assert digest(original)==read(b0/'binding.json')['DEV_public_sha256']
    views = {s['key']:next(v for v in s['views'] if v['id']==TASK)
             for s in original if s['dataset']==DATASET and s['project_split']=='dev'}
    assert len(original)==80 and len(views)==16
    selected={key:matched_direct(source_groups(view)) for key,view in views.items()}
    grade = study['grading_paths'][DATASET]
    assert 'dev' in Path(grade).parts
    lock={'partition':'fixed_B8_DEV','TRAIN_binding_sha256':sha(train/'binding.json'),
          'TRAIN_terminal_sha256':sha(train/'terminal.json'),'literal_rule_sha256':sha(runner),
          'DEV_runner_sha256':sha(Path(__file__)),'archived_DEV_terminal_sha256':sha(stage/'terminal.json'),
          'DEV_views_sha256':digest(views),'direct_projection_sha256':digest(selected),
          'native_grade_sha256':study['grading_file_sha256'][grade]}
    out=HOME/'DEV'/digest(lock)
    immutable_json(out/'binding.json',lock)
    bank,known = {},set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for arm in (ORDINARY,EXTERNAL_ARM):
            directory=root/'dev'/'B8'/arm
            task=read(directory/'task.json')
            seal=verify(read(directory/'prediction_seal.json'),'prediction_seal_sha256')
            cell=verify(read(directory/'scores.json'),'cell_sha256')
            assert cell['partition']=='dev' and cell['cell_sha256']==terminal['cell_sha256'][arm]
            assert seal['task_sha256']==digest(task) and cell['prediction_seal_sha256']==seal['prediction_seal_sha256']
            assert seal['predictions_sha256'].keys()=={s['key'] for s in original}
            bank[arm]={}
            for key in views:
                saved=read(directory/'predictions'/(digest(key)+'.json'))
                assert digest(saved)==seal['predictions_sha256'][key]
                assert saved['source']==key and saved['library_sha256']==cell['libraries'][DATASET]
                before=verify_wire(db,key,saved['result'],known)[TASK]
                bank[arm][key]={'original':before,'matched_direct':selected[key] if selected[key]['answer'] is not None else before}
    immutable_json(out/'predictions.json',bank)
    assert sha(ROOT/grade)==lock['native_grade_sha256']
    labels=read(ROOT/grade)
    effect={}
    for arm,rows in bank.items():
        points={role:[] for role in ('original','matched_direct')}
        for key,pair in rows.items():
            for role,prediction in pair.items():
                outcome=grade_view(DATASET,views[key],labels[key][TASK],prediction['answer'],prediction['evidence_sentence_ids'])
                points[role].append({'source':key,'view':TASK,'grade':outcome['grade']})
        effect[arm]=paired_source_effect(points['original'],points['matched_direct'])
    result={'status':'settled_CNI_copy_literal_control_fixed_B8_DEV','new_model_requests':0,
            'physical_responses_verified':len(known),'source_rule_resolved':sum(p['answer'] is not None for p in selected.values()),
            'by_arm':{a:estimate(views,p,labels)['metrics'] for a,p in bank.items()},'paired_native':effect,
            'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',result)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**result},sort_keys=True),flush=True)


if __name__=='__main__':
    run()
