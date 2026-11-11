"""Replay actual teacher contexts to localize errors, without new generation."""
import ast
from collections import Counter
import json
from pathlib import Path

from legal_skill_guard.skill_evolution.objects import Library, coupled_blocks
from legal_skill_guard.skill_evolution.lift_proposals import schedule_lift, LIFT_ARMS
from legal_skill_guard.skill_evolution.teacher import trigger_failure_views

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
BEFORE = 'f8e173cb6bfa7a2b0541617e096c513f46f46446'


def read(path):return json.loads(path.read_text())


def main():
    source = (ROOT / 'reports/legal_skill_evolution_run_20261111/before_failure_focus_scheduler.py').read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'schedule_lift')
    namespace = {'coupled_blocks': coupled_blocks, 'LIFT_ARMS': LIFT_ARMS}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'preserved_before_schedule', 'exec'), namespace)
    previous = namespace['schedule_lift']
    folder = ORIGINAL / 'artifacts/legal_skill_evolution_20261111'
    roots = sorted(folder.glob('pilot_v*')) + sorted(folder.glob('repair_v*')) + [folder / 'formal_v5']
    seen, rows = set(), []
    for phase in roots:
        for path in sorted(phase.glob('*/teacher_B*.json')):
            response = read(path)
            if response['request_sha256'] in seen:continue
            seen.add(response['request_sha256'])
            arm = path.parent.name;batch = int(path.stem.split('_B')[1])
            context = read(path.parent / f'update_context_B{batch}.json')
            cohort = context['cohort'];trigger = cohort[:3]
            current = context['current'];old = Library.load(path.parent / f'B{batch-1}.json')
            feedback = [{'source': k, 'execution': current[k]} for k in cohort]
            focus = trigger_failure_views(feedback, trigger)
            before = previous(old, [current[k] for k in trigger], arm)
            after = schedule_lift(old, [current[k] for k in trigger], arm)
            if any(x['source'] not in trigger or x['grade'] == 1 for x in focus):
                raise ValueError('Failure focus includes a correct or history-only view')
            rows.append({'phase': phase.name, 'arm': arm, 'batch': batch,
                'teacher_request_sha256': response['request_sha256'],
                'trigger': trigger, 'failure_views': focus,
                'before_scheduled_lift': before, 'after_scheduled_lift': after,
                'scheduler_changed': before != after})
    summary = {'new_model_calls': 0, 'TEST_read': False, 'goal_complete': False,
        'teacher_context_count': len(rows), 'failure_view_count': sum(len(r['failure_views']) for r in rows),
        'failure_views_by_task': dict(Counter(f['view'] for r in rows for f in r['failure_views'])),
        'before_lift_plans': sum(r['before_scheduled_lift'] is not None for r in rows),
        'after_lift_plans': sum(r['after_scheduled_lift'] is not None for r in rows),
        'changed_scheduler_contexts': [r for r in rows if r['scheduler_changed']],
        'contexts': rows,
        'interpretation': 'Same source feedback and parent-level acceptance. The patch changes presentation and restricts dedicated Lift scheduling to actual deficient views. It does not prove better acquisition or either contribution; no candidate has been reexecuted.'}
    output = ROOT / 'reports/legal_skill_evolution_run_20261111/failure_focus_TRAIN_replay.json'
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: summary[k] for k in ('teacher_context_count', 'failure_view_count',
        'before_lift_plans', 'after_lift_plans')}, ensure_ascii=False))


if __name__ == '__main__':main()
