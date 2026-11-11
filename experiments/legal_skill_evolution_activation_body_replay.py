"""Re-evaluate BOTH original TRAIN proposals after one semantics-preserving adapter.

No teacher client is constructed. Original proposal files and failure receipts
remain unchanged; all new executor work continues the original physical ledger.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from legal_skill_guard.skill_evolution.study import Study
from reports.legal_skill_evolution_run_20261111.formal_cost_footprints import usage

ROOT = Path('/media/sangfor/vdb/legal-skill-runtime/engineering/lift-corev-activation-20261112')
ORIGINAL = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
PRIOR = ROOT / 'artifacts/legal_skill_evolution_activation_repair_20261112'
FOLDER = PRIOR / 'body_adapter_replay'
RUN = 'legal_skill_evolution_activation_body_adapter_20261112'


def read(path):return json.loads(path.read_text())


def main():
    protocol = read(PRIOR / 'protocol.json')
    if not (PRIOR / 'completed.json').exists():raise RuntimeError('Preserve original terminal probe first')
    ledger_path = ORIGINAL / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(ledger_path) + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():raise RuntimeError('Actual in-flight request exists')
        teachers = {json.loads(r[0])['request_sha256'] for r in db.execute(
            "select result from calls where role='teacher' and status='completed' and id like ?",
            (protocol['run_id'] + ':%',))}
    responses = {arm: read(PRIOR / arm / 'teacher_B1.json') for arm in ('Full', 'FreeEvolution')}
    if any(r['request_sha256'] not in teachers for r in responses.values()):
        raise RuntimeError('An original independent proposal lacks its settled teacher ledger record')
    source_ids = protocol['independent_acquisition']['sources']
    profile = read(ORIGINAL / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    manifest = read(ORIGINAL / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    partitions = {p: [r['key'] for rows in manifest['datasets'].values() for r in rows[p]] for p in ('train', 'dev', 'test')}
    binding = {'parent_protocol_hash': digest(protocol), 'teacher_calls': 0,
        'raw_teacher_response_hashes': {a: digest(r) for a, r in responses.items()},
        'code': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))},
        'dispatcher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'sources': source_ids, 'same_legal_rules_and_correctness': True,
        'format_change': 'Complete body AST wrapped with declared apply(inputs,premises) signature; no semantics added.'}
    immutable_json(FOLDER / 'protocol.json', binding)
    budget = EvolutionLedger(ledger_path, run_id=RUN, sources=partitions, binding=digest(binding))
    study = object.__new__(Study)
    study.root, study.folder, study.stage = ROOT, FOLDER, 'body_adapter_diagnostic'
    study.profile = {**profile, 'prior_logical_replay_executions': {}}
    study.records = {r['key']: r for r in read(ORIGINAL / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    study.grading = read(ORIGINAL / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    study.ledger = budget;study.executor = FrozenExecutor(budget, FOLDER, profile['executor'])
    study.executor.exact_replay_roots = [PRIOR, ORIGINAL / profile['artifacts']]
    study.reads = FrozenReads(study.executor);study.runtime = SkillRuntime(study.reads)
    study.arms = ('Full', 'FreeEvolution');study.batches = [source_ids];study.order = source_ids
    study.initialize()
    for arm in study.arms:
        immutable_json(FOLDER / arm / 'teacher_B1.json', responses[arm])
        study.initial_batch(arm, 1)
    for arm in study.arms:study.update(arm, 1)
    final = {}
    for arm in study.arms:
        library = Library.load(study.library_path(arm, 1))
        rows = [study.parent(k, library) for k in source_ids]
        final[arm] = {'library_hash': library.hash, 'skill_count': len(library.skills),
            'dependency_ports': sum(p['mode'] == 'skill' for s in library.skills.values() for p in s.inputs.values()),
            'pattern_count': len(library.revision_patterns), 'parents': rows,
            'same_TRAIN_fit_not_independent_validation': True}
    with budget.transaction() as db:
        rows = [{'id': i, 'role': r, 'status': s, 'result': json.loads(raw) if raw else {}}
                for i, r, s, raw in db.execute('select id,role,status,result from calls where id like ?', (RUN + ':%',))]
    result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
        'new_teacher_calls': 0, 'physical_accounting': usage(rows), 'arms': final,
        'new_physical_call_ids': [r['id'] for r in rows], 'test_used': False}
    immutable_json(FOLDER / 'completed.json', result)
    print(json.dumps({'completed': True, 'new_teacher_calls': 0, 'new_physical': len(rows),
        'scores': {arm: [r['native_grade'] for r in value['parents']] for arm, value in final.items()}}), flush=True)


if __name__ == '__main__':main()
