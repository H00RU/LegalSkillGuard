"""Verify locked changes from the four-reader B4 portfolio on later TRAIN contracts."""

import json
import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_b4_candidate_portfolio as fit
from experiments import convergence_revision6_cni_task_screen_forward as replay
from experiments import convergence_revision6_cni_task_screen_parse_later as parse
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_b4_portfolio_later'
POINTER = HANDOFF / f'{STAGE}_current.json'


def exact(db, source, payload, schema):
    key = source['key']
    for identity, _ in replay.existing_requests(db, key, payload):
        row, = db.execute('select result from calls where id=?', (identity,)).fetchone()
        response = json.loads(row)
        request = read(Path(response['artifact_directory']) / 'request.json')
        if request['payload'] != payload or request['id'] != identity:
            raise ValueError('Use the original exact wire and actual settled response')
        if response['finish_reason'] != 'stop':
            continue
        slot = payload['response_format']['json_schema']['schema']
        restored, _ = restore_enum_transport(json.loads(response['content']), slot)
        cell, = fit.parent.common_cells(source)
        bundle = fit.archive.source_bundle(cell)
        result = restored['value']
        if schema is not None:
            codec = fit.archive.ReversibleWire(fit.archive.wire_schema(fit.CNI, bundle), schema)
            result = codec.restore(result)
        answers, evidence = fit.archive.decode_native(fit.CNI, bundle, result)
        return identity, {task: {'answer': value, 'evidence_sentence_ids': evidence[task], 'handled': True}
                          for task, value in answers.items()}
    return None, None


def inputs(previous):
    root, study, roster = fit.archive.archive_context()
    journal = fit.parent.TrainingJournal(root, study, roster)
    ordinary = {role: journal.library(fit.parent.ORDINARY, batch)['programs'][fit.CNI]
                for role, batch in (('ordinary_incumbent', 3), ('ordinary_proposal', 4))}
    entering = journal.library(fit.archive.EXTERNAL_ARM, 3)['programs'][fit.CNI]
    schema = fit.archive.b4.materials()[3]
    programs = {**ordinary, 'parse_incumbent': entering, 'parse_proposal': schema}
    if {role: digest(value) for role, value in programs.items()} != previous['programs']:
        raise ValueError('All later reads must use the measured B4 reader versions')
    _, config, _ = fit.archive.bound_stage(HANDOFF / 'formal_b1_observe_current.json')
    grade = ROOT / config['native_grade_paths'][fit.CNI]
    if 'train' not in grade.parts or sha(grade) != previous['TRAIN_grade_sha256']:
        raise ValueError('Use original TRAIN grades and no DEV/TEST labels')
    later = {row['key']: (row, [batch, index])
             for batch, rows in enumerate(roster[5:], 6)
             for index, row in enumerate((r for r in rows if r['dataset'] == fit.CNI), 1)}
    if len(later) != 9 or any(row['project_split'] != 'train' for row, _ in later.values()):
        raise ValueError('Profile every original TRAIN mother after B5')
    return later, grade, programs, study['executor'], schema


def compare(cases, native, labels):
    units = {}
    for role, answers in native.items():
        units[role] = []
        for key, outputs in answers.items():
            source, _ = cases[key]
            views = {view['id']: view for view in source['views']}
            for task, output in outputs.items():
                result = grade_view(fit.CNI, views[task], labels[key][task],
                                    output['answer'], output['evidence_sentence_ids'])
                units[role].append({'source': key, 'view': task, 'correct': result['grade'],
                                    'grounded': result['grade'] * result['evidence_f1']})
    treated = units['candidate_driven']
    return {
        'native': {role: {'correct': sum(row['correct'] for row in values), 'units': len(values),
                          'correct_class_evidence_F1': mean(row['grounded'] for row in values)}
                   for role, values in units.items()},
        'paired': {role: {metric: paired_source_effect(
            *[[{**row, 'grade': row[metric]} for row in series] for series in (values, treated)]
        ) for metric in ('correct', 'grounded')} for role, values in units.items() if role != 'candidate_driven'},
    }


def run():
    origin, previous, selected = fit.terminal(fit)
    if (sha(origin / 'sealed_predictions.json') != selected['predictions_sha256']
            or digest(selected['choices']) != previous['choices_sha256']
            or read(HANDOFF / 'run_state.json')['active_tasks']):
        raise ValueError('Lock the original selection before opening later TRAIN grades')
    choices = selected['choices']
    for role, choice in choices.items():
        check = verify(read(origin / 'TRAIN_batch_libraries' / f'{role}.json'), 'snapshot_sha256')
        if (check['binding_sha256'] != origin.name or check['programs_by_hypothesis'] != {
            task: previous['programs'][reader] for task, reader in choice['programs'].items()
        }):
            raise ValueError('Every forward policy must use its preserved B4 library')
    cases, grade, programs, executor, schema = inputs(previous)
    tasks = selected['different_hypotheses']
    predictions = {role: {} for role in choices}
    receipts, uncovered, needed, availability = {}, {}, {}, {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger != selected['ledger']:
            raise ValueError('Use the continuous, settled ledger for the no-dispatch replay')
        for key, (source, position) in cases.items():
            proof = fit.current_proofs(source)
            unresolved = sorted(set(tasks) - proof.keys())
            location = '-'.join(map(str, position))
            if unresolved != selected['B6_B8_public_unresolved'][location]:
                raise ValueError('Do not change public applicability after locking')
            readers = {choice['programs'][task] for task in unresolved for choice in choices.values()}
            bank = {}
            needed[location] = sorted(readers)
            availability[location] = []
            for role in sorted(readers):
                wire = (parse.schema_wire(source, schema, executor) if role == 'parse_proposal'
                        else replay.input_wire(source, programs[role], executor))
                identity, native = exact(db, source, wire, schema if role == 'parse_proposal' else None)
                if identity is not None:
                    receipts.setdefault(location, {})[role] = identity
                    bank[role] = fit.ordinary.apply_proofs(source, native, proof)
                    availability[location].append(digest({
                        'user': wire['messages'][1:],
                        'settings': {k: v for k, v in wire.items() if k not in ('messages', 'response_format')},
                    }))
            if len(set(availability[location])) > 1:
                raise ValueError('Every measured reader must see identical public facts and settings')
            for task in tasks:
                required = {choice['programs'][task] for choice in choices.values()} if task in unresolved else set()
                if missing := sorted(required - bank.keys()):
                    uncovered.setdefault(location, {})[task] = missing
                    continue
                for policy, choice in choices.items():
                    chosen = proof[task] if task in proof else bank[choice['programs'][task]][task]
                    predictions[policy].setdefault(key, {})[task] = chosen
    stable = {
        'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'B4_portfolio_terminal': selected['terminal_sha256'],
        'TRAIN_grade_sha256': sha(grade), 'changed_hypotheses': tasks, 'exact_receipts_sha256': digest(receipts),
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
            __file__, fit.__file__, parse.__file__, replay.__file__,
        )},
    }
    out = BASE / STAGE / digest(stable)
    immutable_json(out / 'binding.json', stable)
    fit.archive.snapshot(out, stable['source_sha256'])
    tag = immutable_json(out / 'sealed_predictions.json', predictions)
    labels = read(grade)
    partial = sum(len(v) for v in uncovered.values())
    scores = compare(cases, predictions, labels)
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'later_mothers': len(cases), 'native_units_planned': len(cases) * len(tasks),
        'native_units_without_exact_matched_reads': partial, 'missing_by_position': uncovered,
        'requested_readers_per_position': needed, 'original_TRAIN_calls_reused': sum(map(len, receipts.values())),
        'B6_B8_paired': scores, 'new_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
