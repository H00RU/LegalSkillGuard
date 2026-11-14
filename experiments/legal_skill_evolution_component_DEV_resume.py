"""Reuse unaffected fixed DEV predictions after the pre-dispatch profile fix."""
from pathlib import Path
import hashlib
import json
import shutil
import sqlite3

from experiments import legal_skill_evolution_mixed_dev as dev
from legal_skill_guard.rr.checkpoint import immutable_json


def run():
    previous=dev.ROOT/'artifacts/legal_skill_evolution_mixed_component_DEV_20261115'
    before=dev.read(dev.ROOT/'artifacts/legal_skill_evolution_mixed_component_freeze_20261115/frozen_manifest.json')
    after=dev.read(dev.frozen.OUT/'frozen_manifest.json')
    assert before['libraries']==after['libraries']
    assert before['recipes']==after['recipes']
    assert before['executor_profile']==after['executor_profile']
    assert before['original_128_TRAIN_sources']==after['original_128_TRAIN_sources']
    changed={name for name,sha in before['bound_files_sha256'].items() if after['bound_files_sha256'].get(name)!=sha}
    assert changed=={'experiments/legal_skill_evolution_mixed_dev.py','experiments/legal_skill_evolution_mixed_freeze.py'},changed
    with sqlite3.connect('file:'+str(dev.ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
    copies=[]
    for name in ('source','source_events','initial/GenericView','exact_replay_receipts'):
        for path in sorted((previous/name).rglob('*')):
            if not path.is_file():continue
            target=dev.OUT/path.relative_to(previous)
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():assert target.read_bytes()==path.read_bytes()
            else:shutil.copy2(path,target)
            copies.append({'original':str(path.relative_to(dev.ROOT)),'relative':str(path.relative_to(previous)),
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    immutable_json(dev.OUT/'resume_receipt.json',{'same_goal':True,'same_frozen_B8_libraries_recipes_model_and_data':True,
        'scientific_runtime_changes':sorted(changed),
        'fix':'Pass the already frozen executor profile to the real component reader in DEV.',
        'old_component_errors_and_scores_preserved_in':str(previous.relative_to(dev.ROOT)),
        'unaffected_source_and_Generic_predictions_reused':True,
        'failed_pre_dispatch_component_records_not_relabelled_as_model_outputs':True,
        'new_teacher_calls':0,'new_model_calls_for_migration':0,'copied_files':copies,
        'no_TEST_read':True,'goal_complete':False})
    print(json.dumps({'unaffected_files_preserved':len(copies),'new_model_calls':0,'B8_library_changes':0}),flush=True)


if __name__=='__main__':run()
