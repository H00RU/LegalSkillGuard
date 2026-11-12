"""One concrete repair validation on two already-fixed TRAIN parents."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import Library, apply_revision_package, digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime, LocalReadError
from legal_skill_guard.skill_evolution.teacher import propose, compile_block


def read(path):return json.loads(path.read_text())


def run(root, original):
    run_id = 'legal_skill_evolution_case_support_check_20261112'
    folder = root / 'artifacts' / run_id
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    previous = root / 'artifacts/legal_skill_evolution_role_TRAIN_20261112'
    old = read(previous / 'completed.json')
    protocol = read(previous / 'protocol.json')
    positive, negative = protocol['learning_batches'][1][1], protocol['reuse_parents'][0]
    public = {s['key']: s for s in read(original / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    annotations = read(original / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += [Path(__file__).resolve()]
    binding = {'run_id': run_id, 'parents': [positive, negative],
        'purpose': 'Actual new schema and case-support repair validation, not a new independent method experiment.',
        'offline_regressions_passed': 74, 'source_failures': [
            'Rule-only spouse evidence accepted as a case fact.',
            'Narrow terminal lacked a machine-readable query-clause contract.'],
        'teacher_jobs': 1, 'executor_checks': 'Execute newly generated helper on its native TRAIN case; read the actual negative familial field with the repaired support contract.',
        'unchanged_model_profiles': {'executor': profile['executor'], 'teacher': profile['teacher']},
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'no_DEV_TEST_or_full_training': True, 'no_retry': True}
    immutable_json(folder / 'protocol.json', binding)
    ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(ledger_path) + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile real in-flight requests first')
    budget = EvolutionLedger(ledger_path, run_id=run_id,
        sources={'train': [positive, negative], 'dev': [], 'test': []}, binding=digest(binding))
    reads = FrozenReads(FrozenExecutor(budget, folder, profile['executor']))
    teacher = FrozenTeacher(budget, folder, profile['teacher'])
    initial = next(r for r in read(previous / 'Full/initial_B2.json')['results'] if r['source'] == positive)
    reply = propose(teacher, arm='Full', batch=1, library=Library(), source_records=[public[positive]],
        feedback=[{'source': positive, 'annotations': annotations[positive], 'execution': initial}],
        learned_patterns=[], trigger=[positive], history=[], max_blocks=1)
    immutable_json(folder / 'teacher.json', reply)
    results = []
    for block in reply['value']['blocks']:
        revisions = compile_block(block, Library(), {positive: public[positive]}, 'Full')
        library = apply_revision_package(Library(), revisions, Library().hash)
        library.save(folder / 'generated_library.json')
        view = public[positive]['views'][0]
        execution = SkillRuntime(reads).run(public[positive], view, library, fallback=False)
        results.append({'execution': execution, 'score': grade_view(public[positive]['dataset'], view,
            annotations[positive][view['id']], execution['answer'], execution['evidence_sentence_ids'])})
    fixture = read(root / 'tests/fixtures/skill_evolution_actual_law_as_fact_20261112.json')
    try:
        values, event = reads.read(public[negative], public[negative]['views'][0],
            question=fixture['event']['question'], fields=fixture['field_specs'],
            locator=fixture['event']['locator'], purpose='skill_replay', allow_unresolved=True,
            require_case_support=True)
        negative_result = {'values': values, 'event': event,
            'unsupported_spouse_accepted': values.get('employer_relationship_to_worker') == 'spouse'}
    except LocalReadError as error:
        negative_result = {'values': {}, 'event': error.event, 'error': str(error),
            'unsupported_spouse_accepted': False}
    result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
        'positive_real_schema_and_execution': results, 'negative_case_support': negative_result,
        'no_method_or_strong_control_increment_claimed': True, 'no_DEV_TEST_or_full_training': True}
    immutable_json(folder / 'completed.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('--original-root', type=Path, required=True)
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parents[1], args.original_root)
    print(json.dumps({'completed': True, 'positive': [r['score'] for r in result['positive_real_schema_and_execution']],
        'unsupported_spouse_accepted': result['negative_case_support']['unsupported_spouse_accepted'], 'goal_complete': False}))
