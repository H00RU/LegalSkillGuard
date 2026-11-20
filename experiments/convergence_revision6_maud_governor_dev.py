"""Compare a compiled MAUD covenant interface on the original DEV anchor failures."""

import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments import convergence_revision6_maud_operative_attribution as prior
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import maud_covenant_governors as governors
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_maud_governor_dev'
POINTER = HANDOFF / f'{STAGE}_current.json'
ARCHIVE = prior.measured.visible.fixed_dev
fit, archived, controls, visible = prior.fit, prior.measured.anchored, prior.controls, prior.measured.visible
ROLES = ('synthesized', 'fixed', 'direct')
PURPOSE = 'skill_dev'


def query(case, role):
    if role != 'synthesized':
        return archived.query(case, role)
    public = case['public']
    values = governors.joint_values(public['candidate_clause_anchors'])
    schema = fit.record_schema({
        'observations': fit.record_schema(dict.fromkeys(public['focus_markers'], {'enum': list(values)})),
        archived.COVERAGE: fit.record_schema({family: {'type': 'boolean'} for family in fit.TASKS}),
    })
    guide = (
        'For each marker choose one ordinary=...;negative=... pair. For each family select an anchor '
        'only if the marker is an operative pandemic condition governing that anchor. Verify both the '
        'condition and its actual effect. Use excluded only when checked and ruled out. Use unresolved '
        'when the relation remains unverified. checked_coverage is true for a family only when all '
        'relevant markers and visible text for that task have been checked.'
    )
    return ([{'role': 'system', 'content': '\n'.join((archived.GUIDANCE, archived.INSTRUCTIONS, guide))},
             {'role': 'user', 'content': json.dumps(public, ensure_ascii=False, sort_keys=True)}], schema)


def decode(case, schema, role, raw):
    if role != 'synthesized':
        return archived.decode(case, schema, role, raw)
    missing = {family: {'answer': None, 'focus': None} for family in fit.TASKS}
    if raw['finish_reason'] != 'stop':
        return missing, raw['finish_reason']
    try:
        value = json.loads(raw['content'])
        jsonschema.validate(value, schema)
    except (ValueError, jsonschema.ValidationError):
        return missing, 'invalid_transport'
    inventory = case['public']['candidate_clause_anchors']
    pairs = governors.joint_values(inventory)
    rows = {}
    for marker, selection in value['observations'].items():
        ports = governors.project(inventory, pairs[selection])
        rows[marker] = {**dict(zip(fit.FAMILIES.values(), ports, strict=True)), fit.TRIGGER_NAME: True}
    return fit.consume(rows, value[archived.COVERAGE]), None


def archived_conflicts():
    checked = controls.branch.archive.bound_result
    stage, spec, terminal = checked(prior.measured)
    previous, _, disposition = checked(prior)
    _, cases, _, _, _ = archived.materials()
    wire = read(stage / 'wire_tasks.json')
    path = stage / 'sealed_predictions.json'
    if (sha(path) != terminal['predictions_sha256'] or digest(wire) != spec['matched_wire_sha256']
            or sha(previous / 'sealed_predictions.json') != disposition['predictions_sha256']):
        raise ValueError('Use the sealed original TRAIN comparison')
    raw = read(path)['raw']
    calls, ledger = prior.restored(cases, spec, spec['executor'], stage, raw, wire)
    conflicts = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for identity, case in zip(calls, cases.values(), strict=True):
            (encoded,) = db.execute('select result from calls where id=?', (identity,)).fetchone()
            observations = json.loads(json.loads(encoded)['content'])['observations']
            inventory = case['public']['candidate_clause_anchors']
            bad = 0
            for item in observations.values():
                values = [inventory[val]['candidate_family'] if val in inventory
                          else prior.measured.edges.EXCLUDED.get(val) for val in item.values()]
                if values[0] is not None and values[0] == values[1]:
                    bad += 1
            if bad:
                conflicts['-'.join(map(str, case['position']))] = bad
    if not conflicts:
        raise ValueError('The same-family wire ambiguity must be observed in actual TRAIN responses')
    return {'original_train_terminal': terminal['terminal_sha256'], 'calls_sha256': digest(calls),
            'calls_reused': len(calls), 'conflicting_slots_by_train_position': conflicts, 'preliminary_ledger': ledger}


def prepare():
    cohort, _, study, parent = ARCHIVE.archive()
    dev = [source for source in cohort if source['dataset'] == fit.MAUD]
    cases, source_proofs, eligibility = {}, {}, {}
    for index, source in enumerate(dev, 1):
        case = fit.group(source, [index])
        if case is None:
            continue
        public = case['public']
        excerpts = public['original_excerpts']
        old = governors.anchors.inventory(excerpts)
        more = governors.supplemental_inventory(excerpts, old)
        own_negative = [key for key, item in more.items() if item['excerpt'] == public['task_excerpts']['negative']]
        inventory = {**old, **more}
        if not own_negative or {row['candidate_family'] for row in inventory.values()} != set(fit.TASKS):
            continue
        key = source['key']
        public['candidate_clause_anchors'] = inventory
        cases[key] = case
        eligibility[index] = {'source_sha256': digest(key), 'new_target_anchors': own_negative,
                              'legacy_target_anchors': sum(a['candidate_family'] == 'negative'
                                                           and a['excerpt'] == public['task_excerpts']['negative']
                                                           for a in old.values())}
        source_proofs[key] = {
            'scope': controls.resolved(controls.public_proofs(source)),
            'visibility': visible.source_evidence(source, [index]),
            'explicit_preamble': (prior.proof(source) or {}).get('answer', {}),
        }
    if len(dev) != 16 or not cases or any(row['project_split'] != 'dev' for row in dev):
        raise ValueError('Run the source-based selection on the original fixed MAUD DEV roster')
    prompts = {key: {role: query(case, role) for role in ROLES} for key, case in cases.items()}
    if any(len({tuple(msg[1].items()) for msg, _ in rows.values()}) != 1 for rows in prompts.values()):
        raise ValueError('All roles must receive byte-identical public inputs')
    locator = study['grading_paths'][fit.MAUD]
    if 'dev' not in Path(locator).parts:
        raise ValueError('Grade only with the original fixed DEV references')
    evidence = archived_conflicts()
    evidence.pop('preliminary_ledger')
    dependencies = (__file__, governors.__file__, governors.anchors.__file__, prior.__file__, ARCHIVE.__file__,
                    controls.__file__, visible.__file__, archived.__file__, fit.__file__, prior.measured.__file__,
                    prior.preambles.__file__, visible.witness.__file__)
    spec = {
        'stage': STAGE, 'executor': study['executor'], 'TEST_opened': False, 'partition': 'DEV',
        'fixed_DEV_terminal_sha256': parent, 'fixed_DEV_public_mothers': len(dev),
        'eligibility': eligibility, 'TRAIN_wire_evidence': evidence,
        'local_equivalence_states': governors.check_equivalence(), 'source_proofs_sha256': digest(source_proofs),
        'prompts_sha256': digest(prompts), 'DEV_grade_path': locator,
        'DEV_grade_sha256': study['grading_file_sha256'][locator], 'planned_physical_reads': len(cases) * len(ROLES),
        'design': 'Previously viewed fixed DEV, public-only scope of missing target anchors. Compare a single joint '
                  'operative-edge code with the fixed trigger and per-family anchors and direct native reading. All '
                  'arms receive the exact same excerpts, anchor inventory, source rules and per-source read budget.',
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in dependencies},
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    immutable_json(out / 'wire_tasks.json', prompts)
    immutable_json(out / 'source_proofs.json', source_proofs)
    fit.snapshot(out, spec['source_sha256'])
    return out, spec, cases, prompts, source_proofs


def measure(out, spec, cases, prompts, proofs):
    executor = fit.FrozenExecutor(None, out, spec['executor'])
    executor.readiness()
    capacity = spec['executor']['context_tokens'] - spec['executor']['max_tokens']
    if any(executor.tokenize(messages, thinking=False)['count'] > capacity
           for rows in prompts.values() for messages, _ in rows.values()):
        raise ValueError('Every full same-information prompt must fit the frozen executor')
    ledger = fit.EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                                 sources={'train': [], 'dev': list(cases), 'test': []}, binding=spec)
    executor.ledger = ledger
    bank = {role: {} for role in ROLES}
    records = []
    for key, case in cases.items():
        for role in ROLES:
            messages, schema = prompts[key][role]
            identity = f'{ledger.run_id}:{digest(key)}:{role}'
            write_status(out, {'status': 'running', 'settled': len(records), 'current_request': identity}, POINTER)
            raw = executor.generate(identity, source=key, purpose=PURPOSE, thinking=False,
                                    messages=messages, schema=schema)
            fit.verify_physical_response(executor, identity=identity, source=key, purpose=PURPOSE,
                                         content_sha256=digest(raw['content']), usage=raw['usage'],
                                         finish_reason=raw['finish_reason'])
            bank[role][key], error = decode(case, schema, role, raw)
            proof = {'call_id': identity, 'tokens': raw['usage']['total_tokens'], 'error': error,
                     'native': bank[role][key], 'wire_restored_from_cache': raw.get('cache_hit', False)}
            records.append(proof)
            immutable_json(out / 'responses' / f'{digest(identity)}.json', proof)
            print(f'DEV paired reads settled {len(records)}/{spec["planned_physical_reads"]}', flush=True)
    same_scope = visible.common_scope(bank, {key: row['scope'] for key, row in proofs.items()})
    comparable = visible.common_scope(visible.revise(same_scope, {key: row['visibility'] for key, row in proofs.items()}),
                                      {key: row['explicit_preamble'] for key, row in proofs.items()})
    prediction_sha = immutable_json(out / 'sealed_predictions.json', {'raw': bank, 'same_information': comparable})
    grade = ROOT / spec['DEV_grade_path']
    if 'dev' not in grade.parts or sha(grade) != spec['DEV_grade_sha256']:
        raise ValueError('Score only original DEV grades after the predictions are sealed')
    labels = read(grade)
    scores = {phase: controls.differences(cases, outputs, labels)
              for phase, outputs in (('raw', bank), ('same_information', comparable))}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        totals = dict(db.execute('select status,count(*) from calls group by status'))
        own = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                              (ledger.run_id + ':%',)))
    if own != {'completed': spec['planned_physical_reads']} or totals.get('reserved'):
        raise ValueError('The experiment must settle all original fixed DEV calls')
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': prediction_sha,
        'fixed_DEV_mothers': len(cases), 'scores': scores, 'ledger': totals,
        'new_executor_requests': len(records), 'new_tokens': sum(r['tokens'] for r in records),
        'errors': dict(Counter(r['error'] for r in records if r['error'] is not None)),
        'new_teacher_requests': 0, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


def run(dispatch):
    out, spec, cases, prompts, proofs = prepare()
    if (out / 'terminal.json').exists():
        verify(read(out / 'terminal.json'), 'terminal_sha256')
        print(out, flush=True)
        return
    if not dispatch:
        write_status(out, {'status': 'prepared', 'planned_reads': spec['planned_physical_reads']}, POINTER)
        print(out, flush=True)
        return
    if out != ROOT / read(POINTER)['artifact_root']:
        raise ValueError('Dispatch only the registered immutable revised case comparison')
    with (out / 'driver.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, spec, cases, prompts, proofs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run'))
    run(parser.parse_args().command == 'run')
