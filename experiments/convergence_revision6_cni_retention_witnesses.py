"""Measure a retention reader with separate evidence slots against exact controls."""

import argparse
import fcntl
import json
import re
import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_notice_coverage_links as prior
from experiments import convergence_revision6_retention_grant_replay as grants
from experiments import convergence_revision6_retention_interface as archived
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_retention_witnesses as witness
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_retention_witnesses'
POINTER = HANDOFF / f'{STAGE}_current.json'
ROLES = ('synthesized', 'fixed', 'direct')
DEFERRED_CARVEOUT = re.compile(
    r'^that portion of the information which consists of analyses, compilations, forecasts, studies or '
    r'other documents prepared by us\b[^.;]{0,110}\bwill be held by us and kept confidential\b[^.;]{0,140}'
    r'\bor destroyed upon your request\b', re.I,
)
RETURN_ALL_OTHER = re.compile(
    r'^all copies of the information\b[^.;]{0,180}\bexcept for that portion of the information which '
    r'consists of analyses, compilations, forecasts, studies or other documents prepared by us\b'
    r'[^.;]{0,110}\bwill be returned to you immediately upon your request\b', re.I,
)


def common_proof(case):
    lines = [' '.join(span['text'].split()) for span in case['payload']['indexed_spans']]
    if proof := prior.previous.scope.prohibition(lines):
        return {'answer': archived.interface.CONTRADICTION, 'evidence': sorted(set(proof))}
    linked = [[i - 1, i] for i, line in enumerate(lines) if i and DEFERRED_CARVEOUT.search(line)
              and RETURN_ALL_OTHER.search(lines[i - 1])]
    if len(linked) == 1:
        return {'answer': archived.interface.ENTAILMENT, 'evidence': linked[0]}
    return None


def prepare():
    state = read(HANDOFF / 'run_state.json')
    if state['phase'] not in (prior.STAGE + '_settled', STAGE + '_running'):
        raise ValueError('Work at the exact registered development boundary')
    if state['active_tasks'] and state['active_tasks'][0]['stage'] != STAGE:
        raise ValueError('Do not overlap another request batch')
    roster, grade, reviews, roles, old_wires, original_binding = archived.opened_binding('train')
    origin = ROOT / read(archived.pointer('train'))['artifact_root']
    original = archived.verify(read(origin / 'terminal.json'), 'terminal_sha256')
    bank = read(origin / 'sealed_predictions.json')
    if (origin.name != digest(original_binding) or original['TEST_opened']
            or original['predictions_sha256'] != sha(origin / 'sealed_predictions.json')
            or digest(read(origin / 'binding.json')) != origin.name
            or digest(old_wires) != original_binding['readers_sha256']):
        raise ValueError('Use the exact early paired TRAIN responses')
    label_path = ROOT / grade[0]
    if 'train' not in label_path.parts or sha(label_path) != grade[1]:
        raise ValueError('Require only the original TRAIN scorer')
    train, _, _, _ = prior.notice.archived.collect(*prior.notice.archived.archive_context(), 'train')
    eligibility = {}
    for index, (key, source) in enumerate(train.items()):
        position = [index // 3 + 1, index % 3 + 1]
        spans = prior.previous.scope.retention.spans_for(prior.previous.view(source))
        unresolved = bool(any(grants.DISPOSAL.search(text) for text in spans)
                          and not grants.source_proofs(spans) and not prior.previous.source_proof(source))
        if unresolved:
            eligibility[key] = position
    engine = archived.FrozenExecutor(None, origin, original_binding['executor'])
    cases, controls, physical, decision = {}, {role: {} for role in roles}, {}, {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for key, position in eligibility.items():
            if key not in roster or position[0] > 4:
                continue
            case = roster[key]
            for role in roles:
                name = f'revision6-M1-retention-train-{origin.name[:12]}:{digest(key)}:{role}'
                source, purpose, state, encoded = db.execute(
                    'select source,purpose,status,result from calls where id=?', (name,),
                ).fetchone()
                raw = json.loads(encoded)
                request = read(Path(raw['artifact_directory']) / 'request.json')
                messages, schema = old_wires[key][role]
                native, err = archived.interface.decode(case['payload'], role, schema, raw)
                if ((source, purpose, state) != (key, 'skill_actor', 'completed') or request['id'] != name
                        or request['payload'] != engine.payload(messages=messages, thinking=False, schema=schema)
                        or native != bank[role][key] or err):
                    raise ValueError('Restore the exact public source, old schema and executed reading')
                controls[role][key] = native
                physical[name] = raw['request_hash']
                if role == 'synthesized':
                    raw_slots = json.loads(raw['content'])['observations']
                    decision[key] = raw_slots
            cases[key] = {**case, 'position': position}
    if (sorted(c['position'] for c in cases.values()) != [[1, 2], [2, 3], [4, 1]]
            or any(row['post_disposition_retention_grant'] is not None or not row['post_disposition_retention_bar']
                   for row in decision.values())):
        raise ValueError('The new evidence slots must address the observed unresolved-grant pattern')
    wires = {key: witness.query(case['payload']) for key, case in cases.items()}
    if any(any(variants[role][0][1] != wires[key][0][1] for role in roles)
           for key, variants in old_wires.items() if key in cases):
        raise ValueError('All conditions see the byte-identical full contract and cited index')
    shared = {key: common_proof(case) for key, case in cases.items()}
    names = (__file__, witness.__file__, archived.__file__, archived.interface.__file__,
             prior.previous.__file__, prior.previous.scope.__file__, grants.__file__)
    spec = {'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'executor': original_binding['executor'],
            'archived_TERMINAL': original['terminal_sha256'], 'grade_sha256': grade[1],
            'public_inputs_sha256': digest(cases), 'new_wire_sha256': digest(wires),
            'controls_sha256': digest(controls), 'archived_physical_reads_sha256': digest(physical),
            'shared_source_rules_sha256': digest(shared), 'consumer_states': witness.check_truth_table(),
            'early_positions': [cases[key]['position'] for key in cases],
            'later_unresolved_positions': [pos for pos in eligibility.values() if pos[0] > 4],
            'planned_new_requests': len(cases),
            'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in names}}
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    prior.previous.employee.base.prior.cumulative.snapshot(out, spec['source_sha256'])
    immutable_json(out / 'wire_tasks.json', wires)
    immutable_json(out / 'archived_sources_and_rules.json', {'physical': physical, 'shared': shared})
    return out, spec, cases, wires, controls, shared, label_path


def execute(out, spec, cases, wires, controls, shared, grade):
    state = read(HANDOFF / 'run_state.json')
    job, = state['active_tasks']
    if (state['phase'] != STAGE + '_running' or job['stage'] != STAGE
            or job['binding_sha256'] != out.name):
        raise ValueError('Register the exact comparison before executing')
    ledger = archived.EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                                      sources={'train': sorted(cases), 'dev': [], 'test': []}, binding=spec)
    model = archived.FrozenExecutor(ledger, out, spec['executor'])
    model.readiness()
    room = spec['executor']['context_tokens'] - spec['executor']['max_tokens']
    if any(model.tokenize(messages, thinking=False)['count'] > room for messages, _ in wires.values()):
        raise ValueError('Do not truncate the original indexed contracts')
    output, actual = {}, []
    for key, case in cases.items():
        identity = f'{ledger.run_id}:{digest(key)}'
        messages, schema = wires[key]
        write_status(out, {'status': 'running', 'position': case['position'], 'settled': len(actual)}, POINTER)
        raw = model.generate(identity, source=key, purpose='skill_actor', messages=messages, schema=schema, thinking=False)
        verify_physical_response(model, identity=identity, source=key, purpose='skill_actor',
                                 content_sha256=digest(raw['content']), usage=raw['usage'],
                                 finish_reason=raw['finish_reason'])
        output[key], error = witness.decode(case['payload'], schema, raw)
        row = {'identity': identity, 'position': case['position'], 'tokens': raw['usage']['total_tokens'], 'error': error}
        immutable_json(out / 'responses' / f'{digest(identity)}.json', {**row, 'native': output[key]})
        actual.append(row)
    raw = {**controls, 'original_synthesized': controls['synthesized'], 'synthesized': output}
    shared_bank = {role: {key: (shared[key] or result) for key, result in bank.items()} for role, bank in raw.items()}
    tag = immutable_json(out / 'sealed_predictions.json', {'raw': raw, 'common_source_rules': shared_bank})
    if 'train' not in grade.parts or sha(grade) != spec['grade_sha256']:
        raise ValueError('Keep original TRAIN labels')
    labels = read(grade)
    raw_native, _ = archived.score(cases, raw, labels)
    matched, paired = archived.score(cases, shared_bank, labels)
    contrast = [[paired[role][metric]['mean_change'] for metric in ('grade', 'grounded')]
                for role in ('fixed', 'direct')]
    advance = all(min(effects) >= 0 and max(effects) > 0 for effects in contrast)
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        totals = dict(db.execute('select status,count(*) from calls group by status'))
    if totals != {**job['ledger_before'], 'completed': job['ledger_before']['completed'] + len(actual)}:
        raise ValueError('Reconcile all new and archived physical calls')
    receipt = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'raw_native': raw_native, 'same_information': matched, 'paired': paired,
        'new_executor_requests': len(actual), 'new_teacher_requests': 0,
        'new_tokens': sum(row['tokens'] for row in actual), 'errors': sum(row['error'] is not None for row in actual),
        'reused_archived_responses': len(cases) * len(ROLES),
        'common_proof_positions': [cases[k]['position'] for k, value in shared.items() if value],
        'advance': advance, 'ledger': totals, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', receipt)
    write_status(out, {'status': receipt['status'], 'terminal_sha256': receipt['terminal_sha256']}, POINTER)
    print(out)


def run(action):
    out, spec, *rest = prepare()
    if (out / 'terminal.json').is_file():
        return
    if action == 'prepare':
        write_status(out, {'status': 'prepared', 'planned_requests': spec['planned_new_requests']}, POINTER)
        print(out)
        return
    with (out / 'driver.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        execute(out, spec, *rest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase)
