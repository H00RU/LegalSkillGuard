"""Inventory accepted learning and dedicated mechanisms without model calls."""
from datetime import datetime, timezone
import json
from pathlib import Path

from experiments.legal_skill_evolution import PROFILE
from legal_skill_guard.skill_evolution.study import load_json, PILOT_ARMS
from legal_skill_guard.skill_evolution.objects import Library, coupled_blocks


def main():
    root = Path(__file__).resolve().parents[2]
    folder = root / load_json(PROFILE)['artifacts']
    rows = []
    for arm in PILOT_ARMS:
        for path in sorted((folder / arm).glob('update_B*.json')):
            receipt = load_json(path)
            library = Library.load(folder / arm / ('B' + str(receipt['batch']) + '.json'))
            skills = []
            for skill in library.skills.values():
                skills.append({'id': skill.id, 'version': skill.version, 'hash': skill.hash,
                    'origin_parents': sorted({o['source_id'] for o in skill.source_provenance}),
                    'declared_read_input_count': sum(p['mode'] == 'read' for p in skill.inputs.values()),
                    'current_source_premise_read_count': sum(p['mode'] == 'read' for p in skill.premises.values()),
                    'fixed_source_premise_count': sum(p['mode'] == 'constant' for p in skill.premises.values()),
                    'declared_coupled_blocks': coupled_blocks(skill),
                    'semantic_records': list(skill.semantic_records),
                    'note': 'Input-vs-premise declarations are teacher proposals, not independently verified semantic roles.'})
            lift_revisions = []
            if receipt['selected_candidate'] is not None:
                candidates = sorted((folder / arm / ('B' + str(receipt['batch']) + '_candidates')).glob('*.json'))
                if candidates:
                    candidate = load_json(next(p for p in candidates if int(p.stem) == receipt['selected_candidate']))
                    lift_revisions = [r['skill_id'] for i, r in enumerate(candidate['revisions'])
                        if receipt['selected_mask'] & (1 << i) and r.get('operation') == 'lift']
            rows.append({'arm': arm, 'batch': receipt['batch'], 'accepted_skill_count': len(library.skills),
                'skills': skills, 'accepted_dedicated_lift_revisions_this_update': lift_revisions,
                'learned_revision_pattern_count': len(library.revision_patterns),
                'learned_pattern_ids_this_update': receipt['learned_pattern_ids'],
                'initial_dependency_creation_is_not_joint_revision_learning': True})
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'goal_complete': False, 'evidence_scope': 'settled pilot updates only; not formal DEV/TEST',
        'library_inventory': rows,
        'dedicated_mechanisms_require_actual_events_and_other_parent_validation': True}
    target = Path(__file__).with_name('learned_mechanism_inventory.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'settled_updates': len(rows), 'latest_by_arm': {
        arm: {k: next(r for r in reversed(rows) if r['arm'] == arm)[k]
              for k in ('batch', 'accepted_skill_count', 'learned_revision_pattern_count')}
        for arm in PILOT_ARMS if any(r['arm'] == arm for r in rows)}}))


if __name__ == '__main__':
    main()
