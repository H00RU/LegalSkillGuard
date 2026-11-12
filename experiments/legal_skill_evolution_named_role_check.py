"""One real retry tied to literal actor binding and its offline regressions."""
from pathlib import Path
import hashlib
import json

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime


def read(p):return json.loads(p.read_text())


def main():
    root = Path(__file__).resolve().parents[1]
    original = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
    run_id = 'legal_skill_evolution_named_role_check_20261112'
    folder = root / 'artifacts' / run_id
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    prior = root / 'artifacts/legal_skill_evolution_case_support_check_20261112'
    prepared = original / 'artifacts/legal_skill_evolution_20261111/prepared/train'
    protocol = read(prior / 'protocol.json');key = protocol['parents'][0]
    source = next(s for s in read(prepared / 'public.json') if s['key'] == key)
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    library = Library.load(prior / 'generated_library.json')
    binding = {'reason': 'Previous real read inverted employer/employee. Bind named roles literally from the unchanged native query before the same helper read.',
        'source': key, 'library_hash': library.hash, 'offline_regressions_passed': 75,
        'no_teacher_or_law_program_change': True, 'no_DEV_TEST_or_full_training': True,
        'code': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in
            ['legal_skill_guard/skill_evolution/runtime.py', 'legal_skill_guard/skill_evolution/task_roles.py',
             'experiments/legal_skill_evolution_named_role_check.py']}}
    immutable_json(folder / 'protocol.json', binding)
    budget = EvolutionLedger(original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=run_id, sources={'train': [key], 'dev': [], 'test': []}, binding=digest(binding))
    result = SkillRuntime(FrozenReads(FrozenExecutor(budget, folder, profile['executor']))).run(
        source, source['views'][0], library, fallback=False)
    score = grade_view(source['dataset'], source['views'][0], read(prepared / 'grading.json')[key]['native'],
                       result['answer'], result['evidence_sentence_ids'])
    value = {'execution': result, 'score': score, 'goal_complete': False,
             'engineering_check_only_not_independent_method_evidence': True}
    immutable_json(folder / 'completed.json', value)
    return value


if __name__ == '__main__':
    value = main()
    print(json.dumps({'score': value['score'], 'core': value['execution']['core_executed'], 'goal_complete': False}))
