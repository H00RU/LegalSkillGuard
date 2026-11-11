"""Bounded Lift proposals: schedule a real attempted skill, never invent a rule.

The teacher supplies only a current-source reading instruction. The host owns
the old skill, the coupled block, types, bindings and the unchanged procedure.
Admission still requires the ordinary complete native replay table.
"""
from dataclasses import asdict

from .objects import coupled_blocks, digest, lift
from .native import record_schema


LIFT_ARMS = {'LiftOnly', 'Full', 'Lift+GenericJoint'}


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


def compile_scheduled_lift(plan, wire, library):
    if not plan or not wire:
        raise ValueError('Scheduled Lift requires an explicit current-source reader')
    old = library.skills[plan['skill_id']]
    if old.hash != plan['old_hash']:
        raise ValueError('Scheduled Lift old skill hash differs')
    names = tuple(sorted(plan['premises']))
    if names not in coupled_blocks(old) or any(old.premises[n]['mode'] != 'constant' for n in names):
        raise ValueError('Scheduled Lift is not a constant coupled block')
    fields = wire['fields']
    if len(fields) != len(names) or {f['name'] for f in fields} != set(names):
        raise ValueError('Lift reader must describe exactly the scheduled fields without duplicates')
    if any(not value.strip() for value in (wire['question'], wire['source_locator'],
                                          *(f['question'] for f in fields))):
        raise ValueError('Lift reader instructions must be nonempty')
    typed = {f['name']: {'type': old.premises[f['name']]['type'], 'question': f['question']}
             for f in fields}
    reader = {'id': 'lift_' + digest({'old': old.hash, 'block': names, 'reader': wire})[:20],
              'question': wire['question'], 'source_locator': wire['source_locator'],
              'fields': typed, 'bindings': {n: n for n in names},
              'schema': record_schema({n: {'type': typed[n]['type']} for n in names})}
    new = lift(old, names, reader)
    return [{'skill_id': old.id, 'old_hash': old.hash, 'new_hash': new.hash,
             'new': asdict(new), 'operation': 'lift',
             'representation_adaptation': {'procedure_unchanged': True,
                 'inputs_outputs_unchanged': True, 'types_and_bindings_from_old_skill': True}}]
