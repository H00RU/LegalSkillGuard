"""Validate the locked per-hypothesis screen on the next original B3 and B5 cohorts."""

import argparse
import base64
import fcntl
import json
import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_task_screen as ordinary
from experiments import convergence_revision6_cni_task_screen_parse as parse
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_task_screen_forward'
POINTER = HANDOFF / f'{STAGE}_current.json'
archive, screen, CNI = ordinary.previous, ordinary.screen, ordinary.CNI
parent = ordinary.parent
TRANSITIONS = ((3, parent.ORDINARY), (5, archive.EXTERNAL_ARM))


def input_wire(source, program, executor):
    predicate, = program['predicates']
    if predicate['id'] == 'read':
        return parent.wire(source, program, executor)
    if (predicate['id'] != 'native' or program['composition'].strip() !=
            "def compose(inputs, predict, extractors):\n"
            "    return predict('native', {'public': inputs['public'], 'answer_schema': inputs['native_answer_schema']})"):
        raise ValueError('Use the exact original one-call native reader')
    # Both native callback names produce the same public wire. Keep the original program for execution.
    return parent.wire(source, {**program, 'predicates': [{**predicate, 'id': 'read'}], 'composition':
                       'def compose(inputs, predict, extractors):\n'
                       '    return predict("read", {"public": inputs["public"], "answer_schema": inputs["native_answer_schema"]})'},
                       executor)


def existing_requests(db, source, payload):
    expected = json.dumps(payload, ensure_ascii=False).encode()
    found = []
    for identity, value in db.execute(
        "select id,result from calls where source=? and role='executor' and purpose='skill_actor' "
        "and status='completed' and id not like ? order by reserved_at,id", (source, STAGE + '-%'),
    ):
        folder = Path(json.loads(value)['artifact_directory'])
        wire = folder / 'wire_request.json'
        if wire.is_file() and base64.b64decode(read(wire)['body_b64'], validate=True) == expected:
            found.append((identity, folder.parent.parent))
    return found


def material(db, batch, arm, journal, roster, executor, labels):
    fit, fit_config, stop = archive.bound_stage(parent.fit_pointer(batch))
    _, obs_config, observed = archive.bound_stage(parent.observe_pointer(batch))
    later, later_config, following = archive.bound_stage(parent.observe_pointer(batch + 1))
    folder = fit / 'candidates' / arm / CNI
    decisions = read(fit / 'matched_decisions.json')
    decision = decisions['teacher'][arm][CNI]
    current = read(folder / 'measurements.json')
    earlier = read(folder / 'prior_TRAIN_regression.json')
    entering, adopted = [journal.library(arm, at) for at in (batch - 1, batch)]
    base = entering['programs'][CNI]
    reversible = arm == archive.EXTERNAL_ARM
    schema = current['candidate'] if reversible else None
    proposal = base if reversible else current['candidate']
    if (digest(decisions) != stop['matched_decisions_sha256'] or read(folder / 'decision.json') != decision
            or decision['selected'] != 'candidate' or CNI in entering.get('schema_proposals', {})
            or digest(current['predictions']) != decision['predictions_sha256']
            or digest(earlier) != decision['earlier_TRAIN_regression']['evidence_sha256']
            or adopted['programs'][CNI] != proposal or adopted.get('schema_proposals', {}).get(CNI) != schema
            or any(cfg['executor'] != executor for cfg in (fit_config, obs_config, later_config))):
        raise ValueError('Require the exact archived candidate, earlier comparisons and adopted next-batch carrier')
    roles = (screen.INCUMBENT, screen.PROPOSAL)
    known, bank, sources, positions = set(), {}, {}, {}
    for number, rows in enumerate(roster[:batch], 1):
        for index, source in enumerate((s for s in rows if s['dataset'] == CNI), 1):
            key = source['key']
            old, new = ((earlier['before'][key], earlier['candidate'][key]) if number < batch else
                        (archive.observed(journal, arm, batch, key, observed), current['predictions'][key]))
            archive.verify_pair([archive.physical(db, source, old, base, None),
                                 archive.physical(db, source, new, proposal, schema)], known)
            bank[key] = dict(zip(roles, (old['native'], new['native']), strict=True))
            if source['project_split'] != 'train':
                raise ValueError('Keep all calibration sources inside original TRAIN')
            sources[key], positions[key] = source, [number, index]
    if len(sources) != 3 * batch or len(known) != 2 * len(sources):
        raise ValueError('The original full training prefix is required')
    proof = {key: ordinary.proof_for(source) for key, source in sources.items()}
    shared = {key: {role: ordinary.apply_proofs(sources[key], rows[role], proof[key]) for role in roles}
              for key, rows in bank.items()}
    native_fit = archive.score_fit(sources, shared, {key: labels[key] for key in sources})
    groups = [{'position': positions[key], **archive.guard.compatibility(rows[roles[0]], rows[roles[1]], proof[key]),
               'disagreements': sorted(task for task in native_fit
                                       if rows[roles[0]][task]['answer'] != rows[roles[1]][task]['answer'])}
              for key, rows in bank.items() if proof[key]]
    policies = screen.select(groups, native_fit)
    different = {task for task in native_fit if len({row['programs'][task] for row in policies.values()}) > 1}
    if not different:
        raise ValueError('Only run a transition with different frozen program allocations')

    forward = {}
    for index, source in enumerate((s for s in roster[batch] if s['dataset'] == CNI), 1):
        key = source['key']
        common = ordinary.proof_for(source)
        residual = sorted(different - common.keys())
        saved = archive.observed(journal, arm, batch + 1, key, following)
        if source['project_split'] != 'train' or (schema and saved['schema_library_sha256'] != adopted['snapshot_sha256']):
            raise ValueError('Use only the original later TRAIN measurement of the adopted reader')
        call, _ = archive.physical(db, source, saved, proposal, schema)
        wire = input_wire(source, base, executor)
        seen, = db.execute('select result from calls where id=?', (call,)).fetchone()
        tested = read(Path(json.loads(seen)['artifact_directory']) / 'request.json')['payload']
        if ({k: v for k, v in wire.items() if k not in ('messages', 'response_format')}
                != {k: v for k, v in tested.items() if k not in ('messages', 'response_format')}
                or [m for m in wire['messages'] if m['role'] == 'user']
                != [m for m in tested['messages'] if m['role'] == 'user']):
            raise ValueError('The actual archived proposal must have the same public input and decoding settings')
        forward[key] = {'position': [batch + 1, index], 'source': source, 'proof': common,
                        'active': residual, 'candidate': saved['native'], 'candidate_id': call, 'wire': wire,
                        'replay': existing_requests(db, key, wire) if residual else []}
    return {'batch': batch, 'program': base, 'fit': [groups, native_fit], 'policies': policies,
            'different': sorted(different), 'forward': forward, 'fit_ids': known,
            'terminals': [sha(fit / 'terminal.json'), sha(later / 'terminal.json')],
            'program_hashes': {roles[0]: digest(base), roles[1]: digest(schema or proposal)}}


def prepare():
    path = ROOT / read(ordinary.POINTER)['artifact_root']
    original = verify(read(path / 'terminal.json'), 'terminal_sha256')
    bound = read(path / 'binding.json')
    selector_path = str(Path(screen.__file__).relative_to(ROOT))
    if digest(bound) != path.name or bound['source_sha256'][selector_path] != sha(ROOT / selector_path) or original['TEST_opened']:
        raise ValueError('Use the locked prior per-hypothesis selection rule')
    root, study, roster = archive.archive_context()
    journal = parent.TrainingJournal(root, study, roster)
    _, config, _ = archive.bound_stage(HANDOFF / 'formal_b1_observe_current.json')
    grade = ROOT / config['native_grade_paths'][CNI]
    if 'train' not in grade.parts or sha(grade) != bound['grade_sha256']:
        raise ValueError('Use only the original TRAIN grade file')
    labels = read(grade)
    executor = study['executor']
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        stages = [material(db, batch, arm, journal, roster, executor, labels) for batch, arm in TRANSITIONS]
        if db.execute("select count(*) from calls where status='reserved'").fetchone()[0]:
            raise ValueError('Finish any live request before the scheduled comparison')
    planned = [row['position'] for stage in stages for row in stage['forward'].values()
               if row['active'] and not row['replay']]
    files = (__file__, ordinary.__file__, parse.__file__, screen.__file__, archive.__file__, parent.__file__)
    binding = {'stage': STAGE, 'partition': 'TRAIN', 'executor': executor, 'TEST_opened': False,
               'original_selector_terminal': original['terminal_sha256'], 'grades_sha256': sha(grade),
               'stages': {str(s['batch']): {'programs': s['program_hashes'], 'fit_sha256': digest(s['fit']),
                            'policies_sha256': digest(s['policies']), 'terminals': s['terminals'],
                            'physical_fit_ids_sha256': digest(sorted(s['fit_ids'])),
                            'forward': {key: {'position': row['position'], 'active': row['active'],
                                             'already_measured': row['candidate_id'], 'witnesses_sha256': digest(row['proof']),
                                             'wire_sha256': digest(row['wire']),
                                             'exact_replay': [ident for ident, _ in row['replay']]}
                                        for key, row in s['forward'].items()}} for s in stages},
               'planned_new_requests': planned,
               'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in files}}
    return binding, stages, grade


def run(dispatch):
    binding, stages, grade = prepare()
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    archive.snapshot(out, binding['source_sha256'])
    for stage in stages:
        immutable_json(out / 'fit' / f"B{stage['batch']}.json", {'data': stage['fit'], 'policies': stage['policies']})
        for name, policy in stage['policies'].items():
            immutable_json(out / 'TRAIN_batch_libraries' / f"B{stage['batch']}_{name}.json", sealed({
                'binding_sha256': out.name, 'batch': stage['batch'], 'hypothesis_programs': {
                    task: stage['program_hashes'][role] for task, role in policy['programs'].items()},
            }, 'snapshot_sha256'))
    if (out / 'terminal.json').is_file():
        print(out, flush=True)
        return
    if not dispatch:
        write_status(out, {'status': 'prepared', 'planned_new_requests': len(binding['planned_new_requests'])}, POINTER)
        print(out, binding['planned_new_requests'], flush=True)
        return
    if ROOT / read(POINTER)['artifact_root'] != out:
        raise ValueError('Run only the prepared exact comparison')
    with (out / 'driver.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, binding, stages, grade)


def measure(out, binding, stages, grade):
    forward = {key: row for stage in stages for key, row in stage['forward'].items()}
    ledger = EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                            sources={'train': list(forward), 'dev': [], 'test': []}, binding=binding)
    executor = parent.FrozenExecutor(ledger, out, binding['executor'])
    executor.exact_replay_roots = sorted({path for row in forward.values() for _, path in row['replay']})
    pending = [row for row in forward.values() if row['active']]
    if pending:
        executor.readiness()
        available = binding['executor']['context_tokens'] - binding['executor']['max_tokens']
        if any(executor.tokenize(row['wire']['messages'], thinking=False)['count'] > available for row in pending):
            raise ValueError('Every original complete input must fit the frozen executor')
    actor = parent.ProgramActor(executor, out, max_calls=1)
    results, reads = {}, set()
    for stage in stages:
        for key, row in stage['forward'].items():
            answers = {}
            if row['active']:
                cell, = parent.common_cells(row['source'])
                write_status(out, {'status': 'running', 'current_position': row['position']}, POINTER)
                record = actor.execute(stage['program'], cell, 'skill_actor')
                actor.verify_program_result(cell, stage['program'], 'skill_actor', record)
                if not record['program_execution_completed']:
                    raise ValueError('The untouched entering program did not complete')
                native = record['native']
                with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
                    call = parent.archived(db, row['source'], {'reads': [record], 'native': native},
                                           stage['program'], row['wire'])
                reads.add(call)
                answers = ordinary.apply_proofs(row['source'], native, row['proof'])
                print('Settled', row['position'], row['active'], flush=True)
            candidate = ordinary.apply_proofs(row['source'], row['candidate'], row['proof'])
            results[key] = {name: {task: (answers[task] if task in row['active'] and roles['programs'][task] == screen.INCUMBENT
                                         else candidate[task]) for task in stage['different']}
                            for name, roles in stage['policies'].items()}
    tag = immutable_json(out / 'sealed_predictions.json', results)
    if sha(grade) != binding['grades_sha256']:
        raise ValueError('Read only the bound chronological TRAIN grades')
    metrics = score(results, forward, read(grade))
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        total = dict(db.execute('select status,count(*) from calls group by status'))
        current = dict(db.execute('select status,count(*) from calls where id like ? group by status', (ledger.run_id+':%',)))
    expected = len(binding['planned_new_requests'])
    if current != ({'completed': expected} if expected else {}) or total.get('reserved'):
        raise ValueError('All planned physical requests and only those requests must settle')
    terminal = sealed({'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
                       'paired_forward': metrics, 'new_executor_requests': expected, 'new_teacher_requests': 0,
                       'archived_fit_requests': len(set().union(*(s['fit_ids'] for s in stages))),
                       'adopted_reader_forward_requests': len(forward), 'exact_entering_request_count': len(reads),
                       'TEST_opened': False, 'ledger': total}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out, flush=True)


def score(results, forward, labels):
    units = {name: [] for name in (*screen.SCREENED, 'native_per_hypothesis')}
    individual = {}
    for key, predictions in results.items():
        source = forward[key]['source']
        selected = {task for row in predictions.values() for task in row}
        individual['-'.join(map(str, forward[key]['position']))] = {}
        for name, hypothesis in predictions.items():
            cells = ordinary.scoped.native_rows(source, labels[key],
                {task['id']: hypothesis.get(task['id'], forward[key]['candidate'][task['id']]) for task in source['views']})
            rows = [row for row in cells if row['view'] in selected]
            units[name].extend(rows)
            individual['-'.join(map(str, forward[key]['position']))][name] = [
                {k: v for k, v in row.items() if k != 'source'} for row in rows]
    return {'outcomes_by_position': individual,
            'metrics': {name: {'correct': sum(row['correct'] for row in rows), 'units': len(rows),
                               'correct_class_evidence_F1': mean(row['grounded'] for row in rows)} for name, rows in units.items()},
            'candidate_driven_effects': {name: {m: paired_source_effect(
                *[[{**row, 'grade': row[m]} for row in side] for side in (rows, units['candidate_driven'])])
                for m in ('correct', 'grounded')} for name, rows in units.items() if name != 'candidate_driven'}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    run(parser.parse_args().execute)
