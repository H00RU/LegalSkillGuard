"""Compare clause-bound covenant readers on the original later MAUD TRAIN batches."""

import argparse
from collections import Counter
import fcntl
import inspect
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments import convergence_revision6_maud_covenant_fit as fit
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import maud_covenant_anchors as anchors
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_maud_covenant_anchors'
HOME = BASE / STAGE
POINTER = HANDOFF / f'{STAGE}_current.json'
COVERAGE = 'checked_coverage'
RULE = ('Every original MAUD TRAIN mother in B5–B8 with a literal pandemic marker and visible candidate '
        'anchors for both families. Select without reading references or responses.')
GUIDANCE = fit.GUIDANCE.replace('a definition, a reporting requirement', 'a reporting requirement')
INSTRUCTIONS = (
    'Candidate clause anchors are literal excerpts with approximate family tags. Confirm the operative '
    'duty and correct party in the original contract. For each focus marker follow its own text to '
    'the actual governed clause attested by that anchor. Check subsection letters and express references. '
    'An explicit reference to a named subclause does not also import its sibling. A heading alone or a '
    'nearby exception does not establish an attachment. An ordinary-course definition that expressly '
    'deems responsive actions to satisfy the duty can qualify; a mere mention in a definition cannot. '
    'An anchor in the other excerpt can be valid when the source expressly connects the two. '
    'Use a null for an attachment not yet resolved. A negative scope or a No requires checking '
    'the relevant visible text. Attach a marker only when it governs the obligation attested by the anchor.'
)


def materials():
    _, study, roster = fit.previous.archive_context()
    cases, excluded, archives, grades = {}, {}, [], set()
    for batch, sources in enumerate(roster[4:], 5):
        stage, config, _ = fit.section.bound_stage(fit.section.observe_pointer(batch))
        archives.append(sha(stage / 'terminal.json'))
        name = config['native_grade_paths'][fit.MAUD]
        grades.add((name, config['native_grade_sha256'][name]))
        for i, source in enumerate(s for s in sources if s['dataset'] == fit.MAUD):
            if source['project_split'] != 'train':
                raise ValueError('Use only original TRAIN mothers')
            position = [batch, i]
            case = fit.group(source, position)
            if case is None:
                excluded[f'B{batch}-{i + 1}'] = 'no literal marker'
                continue
            inventory = anchors.inventory(case['public']['original_excerpts'])
            if {v['candidate_family'] for v in inventory.values()} != set(fit.TASKS):
                excluded[f'B{batch}-{i + 1}'] = 'at least one family missing a visible anchor'
                continue
            case['public']['candidate_clause_anchors'] = inventory
            cases[source['key']] = case
    (name, expected), = grades
    grade = ROOT / name
    if 'train' not in grade.parts or sha(grade) != expected:
        raise ValueError('Require byte-exact original TRAIN references')
    return study['executor'], cases, archives, grade, excluded


def query(case, role):
    public = case['public']
    candidates = public['candidate_clause_anchors']
    markers = tuple(public['focus_markers'])
    if role == 'direct':
        _, schema = fit.query(case, role)
        role_guide = ('Give the two native answers directly. Return the decisive focus marker for Yes. '
                      'Return a null focus for No and unresolved answers.')
    else:
        fields = {fit.TRIGGER_NAME: {'enum': [True, False, None]}}
        if role == 'synthesized':
            domain = {'enum': [*candidates, anchors.NO_ADDITIONAL, None]}
            fields.update(first_anchor=domain, second_anchor=domain)
            role_guide = (
                'For each marker, give the set of governed clause anchors. When there are multiple anchors '
                'for the same family select one, and report both families when this exception governs both. '
                'List applicable anchors in the first and second slots. Use no_additional_anchor for a '
                'slot after checking that there is no further governed family. Use null for an unresolved slot. '
                'Use no_additional_anchor twice only when both attachments were checked and excluded.'
            )
        else:
            for family in fit.TASKS:
                family_ids = [name for name, data in candidates.items() if data['candidate_family'] == family]
                fields[family] = {'enum': [*family_ids, anchors.EXCLUDED, None]}
            role_guide = (
                'For each marker, answer each covenant field independently: give one governed clause anchor '
                'of that family, excluded only after checking that it does not govern that family, or null '
                'for unresolved scope. Check each field even when the other has a governed anchor.'
            )
        role_guide += (' Mark is_pandemic_condition true for an operative pandemic condition, false for a '
                       'different condition or mere mention, and null if unresolved. Mark checked_coverage '
                       'for each task only after checking all relevant markers and covenant text.')
        schema = fit.record_schema({
            'observations': fit.record_schema(dict.fromkeys(markers, fit.record_schema(fields))),
            COVERAGE: fit.record_schema({family: {'type': 'boolean'} for family in fit.TASKS}),
        })
    messages = [{'role': 'system', 'content': f'{GUIDANCE}\n{INSTRUCTIONS}\n{role_guide}'},
                {'role': 'user', 'content': json.dumps(public, ensure_ascii=False, sort_keys=True)}]
    return messages, schema


def decode(case, schema, role, raw):
    if role == 'direct':
        return fit.decode(schema, role, raw)
    missing = {family: {'answer': None, 'focus': None} for family in fit.TASKS}
    if raw['finish_reason'] != 'stop':
        return missing, raw['finish_reason']
    try:
        value = json.loads(raw['content'])
        jsonschema.validate(value, schema)
    except (ValueError, jsonschema.ValidationError):
        return missing, 'invalid_transport'
    local = {}
    candidates = case['public']['candidate_clause_anchors']
    for marker, row in value['observations'].items():
        if role == 'synthesized':
            scope = anchors.project(candidates, row['first_anchor'], row['second_anchor'])
        else:
            scope = tuple(None if row[family] is None else row[family] != anchors.EXCLUDED for family in fit.TASKS)
        local[marker] = dict(zip(fit.FAMILIES.values(), scope, strict=True))
        local[marker][fit.TRIGGER_NAME] = row[fit.TRIGGER_NAME]
    return fit.consume(local, value[COVERAGE]), None


def measure(out, binding, cases, grade, prompts):
    ledger = fit.EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                                 sources={'train': list(cases), 'dev': [], 'test': []}, binding=binding)
    executor = fit.FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    room = binding['executor']['context_tokens'] - binding['executor']['max_tokens']
    if any(executor.tokenize(messages, thinking=False)['count'] > room
           for by_role in prompts.values() for messages, _ in by_role.values()):
        raise ValueError('All three readers must receive both excerpts without truncation')
    bank = {role: {} for role in fit.ROLES}
    tokens, errors, attachment_reads = Counter(), Counter(), Counter()
    for i, (key, case) in enumerate(cases.items()):
        for role in fit.ROLES[i % 3:] + fit.ROLES[:i % 3]:
            identity = f'{ledger.run_id}:{digest(key)}:{role}'
            status = {'status': 'running', 'current_request': identity, 'completed_mothers': i}
            write_status(out, status, POINTER)
            messages, schema = prompts[key][role]
            try:
                raw = executor.generate(identity, source=key, purpose='skill_actor', thinking=False,
                                        messages=messages, schema=schema)
                fit.verify_physical_response(executor, identity=identity, source=key, purpose='skill_actor',
                    content_sha256=digest(raw['content']), usage=raw['usage'], finish_reason=raw['finish_reason'])
                bank[role][key], error = decode(case, schema, role, raw)
                if role == 'synthesized' and error is None:
                    candidates = case['public']['candidate_clause_anchors']
                    for row in json.loads(raw['content'])['observations'].values():
                        if row[fit.TRIGGER_NAME] is True:
                            scope = anchors.project(candidates, row['first_anchor'], row['second_anchor'])
                            attachment_reads[str(scope)] += 1
                tokens[role] += raw['usage']['total_tokens']
                errors[role] += error is not None
                immutable_json(out / 'responses' / f'{digest(identity)}.json',
                               {'call_id': identity, 'native': bank[role][key], 'error': error})
            except Exception:
                write_status(out, {**status, 'status': 'interrupted'}, POINTER)
                raise
    predictions = immutable_json(out / 'sealed_predictions.json', bank)
    if sha(grade) != binding['TRAIN_grade_sha256']:
        raise ValueError('Grade sealed predictions with the original TRAIN references')
    labels = read(grade)
    scores, effects = fit.score(cases, bank, labels)
    directions = {role: {'repairs': 0, 'regressions': 0} for role in fit.ROLES[1:]}
    for key in cases:
        for family, task in fit.TASKS.items():
            right = labels[key][task]['answer']
            model = bank['synthesized'][key][family]['answer'] == right
            for role, counts in directions.items():
                control = bank[role][key][family]['answer'] == right
                counts['repairs'] += model and not control
                counts['regressions'] += control and not model
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        counts = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                                 (ledger.run_id + ':%',)))
        totals = dict(db.execute('select status,count(*) from calls group by status'))
    if counts != {'completed': len(cases) * len(fit.ROLES)} or totals.get('reserved'):
        raise ValueError('Every matched physical call must be accounted for')
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'cohort_size': len(cases),
        'scores': scores, 'effects': effects, 'paired_direction_counts': directions,
        'advance': all(v['paired_source_bootstrap_95'][0] > 0 for v in effects.values()),
        'bound_pandemic_marker_projections': dict(attachment_reads),
        'tokens': dict(tokens), 'wire_errors': dict(errors), 'predictions_sha256': predictions,
        'new_executor_requests': counts['completed'], 'new_teacher_requests': 0, 'TEST_opened': False,
        'ledger': totals,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


def run(execute):
    config, cases, archives, grade, excluded = materials()
    prompts = {key: {role: query(case, role) for role in fit.ROLES} for key, case in cases.items()}
    if any(len({m[1]['content'] for m, _ in by_role.values()}) != 1 for by_role in prompts.values()):
        raise ValueError('All readers must see the same original text and candidate anchors')
    paths = (__file__, anchors.__file__, fit.__file__, fit.scope.__file__,
             inspect.getfile(fit.grade_view), inspect.getfile(fit.FrozenExecutor), inspect.getfile(fit.EvolutionLedger))
    binding = {
        'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'executor': config,
        'cohort_rule': RULE, 'cohort': [c['position'] for c in cases.values()], 'excluded': excluded,
        'TRAIN_observe_terminals': archives, 'TRAIN_grade_sha256': sha(grade), 'wire_sha256': digest(prompts),
        'equivalent_local_scope_states': anchors.check_equivalence(fit.scope.module(), fit.scope.local_consumer),
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in paths},
        'advance_rule': 'Require positive source paired lower 95% bounds against both matched controls.',
    }
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'wire_tasks.json', prompts)
    fit.snapshot(out, binding['source_sha256'])
    if (out / 'terminal.json').exists():
        print(out)
        return
    if not execute:
        write_status(out, {'status': 'prepared', 'physical_requests_planned': len(cases) * len(fit.ROLES)}, POINTER)
        print(out)
        return
    if ROOT / read(POINTER)['artifact_root'] != out:
        raise ValueError('Prepare this exact matched TRAIN comparison first')
    with (out / 'driver.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, binding, cases, grade, prompts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
