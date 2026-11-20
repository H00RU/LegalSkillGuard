"""Re-read a MAUD exception's two covenants in one source-local scope field."""

import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments import convergence_revision6_maud_covenant_fit as fit
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_maud_joint_scope'
POINTER = HANDOFF / 'revision6_maud_joint_scope_current.json'
ROLE = 'synthesized'
# Values denote the attachment of each source exception, before deciding if
# the condition is a pandemic response or whether the native scope is complete.
SCOPE = {
    'both': (True, True),
    'ordinary_only': (True, False),
    'negative_only': (False, True),
    'neither': (False, False),
    'ordinary_applies_negative_unresolved': (True, None),
    'negative_applies_ordinary_unresolved': (None, True),
    'ordinary_excluded_negative_unresolved': (False, None),
    'negative_excluded_ordinary_unresolved': (None, False),
    'both_unresolved': (None, None),
}
ENCODE = {pair: code for code, pair in SCOPE.items()}
ORDINARY, NEGATIVE = fit.FAMILIES.values()
FIELD = 'covenants_governed_by_this_exception'


def query(case):
    fields = {FIELD: {'enum': list(SCOPE)}, fit.TRIGGER_NAME: {'enum': [True, False, None]}}
    row = fit.record_schema(fields)
    schema = fit.record_schema({
        'observations': fit.record_schema(dict.fromkeys(case['public']['focus_markers'], row)),
        'checked_coverage': fit.record_schema(dict.fromkeys(fit.TASKS, {'type': 'boolean'})),
    })
    details = (
        'For each focus marker, first locate the occurrence in its named excerpt. Follow the clause '
        'from that occurrence to the duty or restriction it qualifies, reading beyond the focus snippet '
        'in the full excerpt. Choose one scope for that occurrence. Use both when this very exception '
        'governs the ordinary-course duty and the negative interim restrictions, including by explicit '
        'incorporation. When the same wording occurs separately under two different duties, scope '
        'each occurrence by its own text. An only code requires that the other attachment was checked '
        'and excluded. Use a code with unresolved for an attachment that cannot be checked. Choose the '
        'scope independently of whether the occurrence is a pandemic response. Set is_pandemic_condition '
        'to true if it is an operative pandemic exception, including implementation of named pandemic '
        'measures, false for a different condition or a mention with no operative role, and null if unread. '
        'Mark checked_coverage true for a question only after checking its relevant markers and text.'
    )
    return ([{'role': 'system', 'content': fit.GUIDANCE + '\n' + details},
             {'role': 'user', 'content': json.dumps(case['public'], ensure_ascii=False, sort_keys=True)}], schema)


def projections(row):
    ordinary, negative = SCOPE[row[FIELD]]
    return {ORDINARY: ordinary, NEGATIVE: negative, fit.TRIGGER_NAME: row[fit.TRIGGER_NAME]}


def check_equivalence():
    module = fit.scope.module()
    for state in module.states:
        original = fit.scope.local_consumer(state, {})
        code = ENCODE[(original[ORDINARY], original[NEGATIVE])]
        if projections({FIELD: code, fit.TRIGGER_NAME: original[fit.TRIGGER_NAME]}) != original:
            raise ValueError('The scope wire must preserve all original outcomes and unknowns')
    return len(module.states)


def decode(schema, raw):
    missing = {family: {'answer': None, 'focus': None} for family in fit.TASKS}
    if raw['finish_reason'] != 'stop':
        return missing, raw['finish_reason']
    try:
        value = json.loads(raw['content'])
        jsonschema.validate(value, schema)
    except (ValueError, jsonschema.ValidationError):
        return missing, 'invalid_transport'
    local = {marker: projections(row) for marker, row in value['observations'].items()}
    return fit.consume(local, value['checked_coverage']), None


def restore_previous(cases, config, grade):
    pointer = read(fit.POINTER)
    root = ROOT / pointer['artifact_root']
    spec = read(root / 'binding.json')
    terminal = verify(read(root / 'terminal.json'), 'terminal_sha256')
    old = read(root / 'sealed_predictions.json')
    wire = read(root / 'wire_tasks.json')
    if (root.name != digest(spec) or terminal['binding_sha256'] != root.name
            or pointer['terminal_sha256'] != terminal['terminal_sha256'] or terminal['TEST_opened']
            or spec['partition'] != 'TRAIN' or spec['executor'] != config
            or spec['TRAIN_grade_sha256'] != sha(grade) or digest(wire) != spec['wire_sha256']
            or sha(root / 'sealed_predictions.json') != terminal['predictions_sha256']):
        raise ValueError('Use the exact settled first MAUD comparison')
    if any(sha(root / 'source_snapshot' / path) != expected or sha(ROOT / path) != expected
           for path, expected in spec['source_sha256'].items()):
        raise ValueError('The original score and archived source modules must remain byte-identical')
    if set(old) != set(fit.ROLES) or any(set(bank) != set(cases) for bank in old.values()):
        raise ValueError('Keep the same complete original comparison cohort')
    prefix = 'revision6-M1-maud-covenants-' + root.name[:12]
    verify_rows = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for key, case in cases.items():
            for role in fit.ROLES:
                identity = f'{prefix}:{digest(key)}:{role}'
                messages, schema = wire[key][role]
                if fit.query(case, role) != (messages, schema):
                    raise ValueError('Preserve the exact protocol of all archived arms')
                physical_wire(db, set(cases), identity, key)
                result, = db.execute('select result from calls where id=?', (identity,)).fetchone()
                raw = json.loads(result)
                payload = read(Path(raw['artifact_directory']) / 'request.json')['payload']
                expected = fit.FrozenExecutor(None, root, config).payload(
                    messages=messages, thinking=False, schema=schema)
                if payload != expected or fit.decode(schema, role, raw)[0] != old[role][key]:
                    raise ValueError('The actual source, settings and native decision must reproduce')
                verify_rows[identity] = raw['request_hash']
    return old, wire, terminal['terminal_sha256'], digest(verify_rows), len(verify_rows)


def run(execute=False):
    config, cases, source_refs, grade = fit.materials()
    old, previous_wire, prior, bank_hash, physical = restore_previous(cases, config, grade)
    prompts = {key: query(value) for key, value in cases.items()}
    for key, (messages, _) in prompts.items():
        if any(messages[1] != wire[0][1] for wire in previous_wire[key].values()):
            raise ValueError('The joint representation introduces no additional source material')
    source_paths = (__file__, fit.__file__, fit.scope.__file__, fit.residual.__file__,
                    physical_wire.__code__.co_filename)
    spec = {
        'stage': 'revision6_maud_joint_scope', 'partition': 'TRAIN', 'TEST_opened': False,
        'cohort': [c['position'] for c in cases.values()], 'executor': config, 'TRAIN_grade_sha256': sha(grade),
        'prior_terminal': prior, 'original_requests_sha256': bank_hash, 'TRAIN_observe_terminals': source_refs,
        'wire_sha256': digest(prompts), 'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in source_paths},
        'full_equivalence_states': check_equivalence(), 'codebook_sha256': digest(SCOPE),
        'advance_rule': 'Require positive mother-paired lower 95% bounds over fixed and direct on both tasks combined.',
    }
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    immutable_json(out / 'wire_tasks.json', prompts)
    fit.snapshot(out, spec['source_sha256'])
    if (out / 'terminal.json').exists():
        print(out)
        return
    if not execute:
        write_status(out, {'status': 'prepared', 'physical_requests_planned': len(cases)}, POINTER)
        print(out)
        return
    if ROOT / read(POINTER)['artifact_root'] != out:
        raise ValueError('Prepare the specific targeted TRAIN comparison before execution')
    with (out / 'driver.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, spec, cases, grade, prompts, old, physical)


def outcomes(cases, bank, labels):
    return [{'source': key, 'view': task,
             'grade': fit.grade_view(fit.MAUD, case['views'][task], labels[key][task],
                                    bank[key][family]['answer'])['grade']}
            for key, case in cases.items() for family, task in fit.TASKS.items()]


def measure(out, spec, cases, grade, prompts, previous, physical):
    ledger = fit.EvolutionLedger(LEDGER, run_id='revision6-M1-maud-joint-scope-' + out.name[:12],
                                 sources={'train': list(cases), 'dev': [], 'test': []}, binding=spec)
    executor = fit.FrozenExecutor(ledger, out, spec['executor'])
    executor.readiness()
    fits = spec['executor']['context_tokens'] - spec['executor']['max_tokens']
    if any(executor.tokenize(messages, thinking=False)['count'] > fits for messages, _ in prompts.values()):
        raise ValueError('The complete common public input must fit without truncation')
    joint = {}
    token_count, errors, scope_counts = 0, 0, Counter()
    for i, (key, (messages, schema)) in enumerate(prompts.items()):
        identity = f'{ledger.run_id}:{digest(key)}'
        status = {'status': 'running', 'completed_mothers': i, 'current_request': identity}
        write_status(out, status, POINTER)
        try:
            raw = executor.generate(identity, source=key, purpose='skill_actor',
                                    thinking=False, messages=messages, schema=schema)
            fit.verify_physical_response(executor, identity=identity, source=key, purpose='skill_actor',
                content_sha256=digest(raw['content']), usage=raw['usage'], finish_reason=raw['finish_reason'])
            joint[key], error = decode(schema, raw)
            if error is None:
                scope_counts.update(row[FIELD] for row in json.loads(raw['content'])['observations'].values())
            token_count += raw['usage']['total_tokens']
            errors += error is not None
            immutable_json(out / 'responses' / (digest(identity) + '.json'),
                           {'call_id': identity, 'native': joint[key], 'error': error})
        except Exception:
            write_status(out, {**status, 'status': 'interrupted'}, POINTER)
            raise
    bank = {**previous, 'previous_synthesized': previous[ROLE], ROLE: joint}
    pred = immutable_json(out / 'sealed_predictions.json', bank)
    if 'train' not in grade.parts or sha(grade) != spec['TRAIN_grade_sha256']:
        raise ValueError('Grade the sealed predictions with the original TRAIN references')
    labels = read(grade)
    metrics, comparisons = fit.score(cases, bank, labels)
    comparisons['previous_synthesized'] = paired_source_effect(
        outcomes(cases, bank['previous_synthesized'], labels), outcomes(cases, joint, labels))
    effects = {}
    a = outcomes(cases, joint, labels)
    for baseline in ('fixed', 'direct', 'previous_synthesized'):
        b = outcomes(cases, bank[baseline], labels)
        effects[baseline] = {
            'repairs': sum(x['grade'] > y['grade'] for x, y in zip(a, b, strict=True)),
            'regressions': sum(x['grade'] < y['grade'] for x, y in zip(a, b, strict=True)),
        }
    selected = all(comparisons[k]['paired_source_bootstrap_95'][0] > 0 for k in ('fixed', 'direct'))
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        current = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                                  (ledger.run_id + ':%',)))
        totals = dict(db.execute('select status,count(*) from calls group by status'))
    if current != {'completed': len(cases)} or totals.get('reserved'):
        raise ValueError('Require one verified new read for every original mother')
    result = sealed({
        'status': 'settled_revision6_maud_joint_scope', 'binding_sha256': out.name, 'cohort_size': len(cases),
        'scores': metrics, 'effects': comparisons, 'paired_direction_counts': effects, 'proceed': selected,
        'new_executor_requests': current['completed'], 'new_teacher_requests': 0, 'archive_requests_verified': physical,
        'tokens': token_count, 'wire_errors': errors, 'observed_scope_counts': dict(scope_counts),
        'predictions_sha256': pred, 'TEST_opened': False, 'ledger': totals,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
