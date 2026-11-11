"""Exact function from f8e173c; replay evidence, not an active runtime."""
def schedule_lift(library, trigger_rows, arm):
    if arm not in LIFT_ARMS:
        return None
    for row in trigger_rows:
        if row['selection_grade'] is None or row['selection_grade'] >= 1:
            continue
        attempted = set()
        for view in row['views']:
            execution = view['execution']
            attempted.update(e['skill_id'] for e in execution.get('events', [])
                             if e.get('kind') == 'APPLY')
            attempted.update(e['skill_id'] for e in execution.get('failed_candidates', [])
                             if not e.get('static_proof'))
        for identity in sorted(attempted & library.skills.keys()):
            skill = library.skills[identity]
            blocks = [b for b in coupled_blocks(skill)
                      if all(skill.premises[n]['mode'] == 'constant' for n in b)]
            if blocks:
                names = sorted(blocks, key=lambda b: (-len(b), b))[0]
                return {'skill_id': identity, 'old_hash': skill.hash,
                        'premises': list(names), 'trigger_source': row['source']}
    return None
