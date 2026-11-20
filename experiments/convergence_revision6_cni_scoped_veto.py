"""Replay source-bound vetoes across the three settled ContractNLI proposals."""

import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_cni_b5_assertion_screen as b5
from experiments import convergence_revision6_cni_task_screen as ordinary
from experiments import convergence_revision6_cni_task_screen_b4_later as ordinary_later
from experiments import convergence_revision6_cni_task_screen_parse as parse
from experiments import convergence_revision6_cni_task_screen_parse_later as parse_later
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_veto_scope as scope
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_scoped_veto'
POINTER = HANDOFF / f'{STAGE}_current.json'
CNI = ordinary.CNI
POLICIES = (*ordinary.screen.SCREENED, 'native_per_hypothesis')
NATIVE_FIT = 'native_per_hypothesis'
EXPECTED_TASKS = {'ordinary_B4': 'nda-10', 'PARSE_B4': 'nda-7', 'ordinary_B5': 'nda-3'}


def load(experiment):
    pointer = read(experiment.POINTER)
    folder = ROOT / pointer['artifact_root']
    spec = read(folder / 'binding.json')
    terminal = verify(read(folder / 'terminal.json'), 'terminal_sha256')
    path = folder / 'sealed_predictions.json'
    if (digest(spec) != folder.name or folder.name != terminal['binding_sha256']
            or pointer['terminal_sha256'] != terminal['terminal_sha256'] or sha(path) != terminal['predictions_sha256']
            or terminal['TEST_opened']):
        raise ValueError('Use the exact settled original policy and measured forward readouts')
    return folder, spec, terminal, read(path)


def source_spans(source, task):
    view = next(v for v in source['views'] if v['id'] == task)
    public = view['public']
    return [public['source_text'][start:end] for start, end in public['sentence_spans']]


def bound_scope(name, fit_data, sources):
    folder, binding, terminal, _ = fit_data
    if name == 'ordinary_B5':
        table = read(folder / 'fit_controls.json')
        if digest(table) != binding['fit_controls_sha256']:
            raise ValueError('Use the original selected B5 source witness')
        policies = table['routes_with_class']
    else:
        policies = terminal['policies']
    selected = policies['candidate_driven']
    task, = selected['blocked']
    if task != EXPECTED_TASKS[name] or set(policies) != set(POLICIES):
        raise ValueError('Preserve all three originally measured update contrasts')
    index = tuple(selected['position'])
    witness, = (source for source in sources.values() if tuple(source['position']) == index)
    source = witness['source']
    proof = (b5.proof_for(source)[0] if name == 'ordinary_B5' else ordinary.proof_for(source))[task]
    hold = scope.bind_veto(task, source_spans(source, task), proof['evidence_sentence_ids'])
    programs = {p: row['programs'][task] for p, row in policies.items()}
    if programs['candidate_driven'] == programs[NATIVE_FIT] or any(
        choice != programs[NATIVE_FIT] for p, choice in programs.items() if p != 'candidate_driven'
    ):
        raise ValueError('Require the original distinct candidate-driven route and strong controls')
    return {**hold, 'witness_position': list(index), 'original_programs': programs,
            'original_training_terminal': terminal['terminal_sha256']}


def replay(cases, source, certificate):
    task = certificate['task']
    versions = certificate['original_programs']
    pooled, matches = {}, []
    for key, values in cases.items():
        spans = source_spans(source[key]['source'], task)
        use = scope.chosen_role(certificate, spans, selected=versions['candidate_driven'], native_fit=versions[NATIVE_FIT])
        from_policy = 'candidate_driven' if use == versions['candidate_driven'] else NATIVE_FIT
        if from_policy == 'candidate_driven':
            matches.append(source[key]['position'])
        pooled[key] = {**values, 'source_scoped_candidate_driven': values[from_policy]}
    return pooled, matches


def outcome(task, cases, sources, labels):
    answers = {}
    for key, alternatives in cases.items():
        view = next(v for v in sources[key]['source']['views'] if v['id'] == task)
        for arm, row in alternatives.items():
            score = grade_view(CNI, view, labels[key][task], row['answer'], row['evidence_sentence_ids'])
            answers.setdefault(arm, []).append({'source': key, 'view': task, 'correct': score['grade'],
                                               'grounded': score['grade'] * score['evidence_f1']})
    preferred = 'source_scoped_candidate_driven'
    native = {arm: {'correct': sum(r['correct'] for r in bank), 'units': len(bank),
                    'correct_class_evidence_F1': mean(r['grounded'] for r in bank)} for arm, bank in answers.items()}
    effects = {arm: {metric: paired_source_effect(*[
        [{**row, 'grade': row[metric]} for row in bank] for bank in (rows, answers[preferred])
    ]) for metric in ('correct', 'grounded')} for arm, rows in answers.items() if arm != preferred}
    return {'native': native, 'paired_scoped': effects}


def run():
    _, _, roster = ordinary.previous.archive_context()
    train, _, grade, _ = b5.copy.archive.collect(*b5.copy.archive.archive_context(), 'train')
    source = {row['key']: {'source': row, 'position': [batch, index]}
              for batch, rows in enumerate(roster, 1)
              for index, row in enumerate((r for r in rows if r['dataset'] == CNI), 1)}
    if len(source) != 24 or 'train' not in grade.parts or any(
        item['source'] != train[key] or item['source']['project_split'] != 'train' for key, item in source.items()
    ):
        raise ValueError('Preserve the original chronological TRAIN and references')
    _, dev, _, _, _ = b5.copy.common.prior.prepare()
    if len(dev) != 16:
        raise ValueError('Only inspect fixed public DEV scope coverage')
    artifacts = {module: load(module) for module in (ordinary, ordinary_later, parse, parse_later, b5)}
    group_specs = {
        'ordinary_B4': (ordinary, ordinary_later),
        'PARSE_B4': (parse, parse_later),
        'ordinary_B5': (b5, b5),
    }
    certified = {name: bound_scope(name, artifacts[fit], source) for name, (fit, _) in group_specs.items()}
    predictions, activations, routes = {}, {}, {}
    for name, (fit, later) in group_specs.items():
        task = certified[name]['task']
        if fit != later:
            early = artifacts[fit][3]
            routes[name + '_next_batch'] = (name, {
                key: {arm: early[arm][key][task] for arm in POLICIES} for key in early[NATIVE_FIT]
            }, [5])
        routes[name + '_later'] = (name, {
            key: {arm: by_arm[arm][task] for arm in POLICIES} for key, by_arm in artifacts[later][3].items()
        }, [6, 7, 8])
    for name, (group, rows, batches) in routes.items():
        expected = {key for key, row in source.items() if row['position'][0] in batches}
        if set(rows) != expected or len(rows) != 3 * len(batches):
            raise ValueError('Match every original held-later contract in each registered block')
        predictions[name], activations[name] = replay(rows, source, certified[group])
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or read(HANDOFF / 'run_state.json')['active_tasks']:
        raise ValueError('Require all original responses to be settled')
    public_dev = {
        name: [i for i, source in enumerate(dev.values(), 1)
               if scope.matched_spans(binding['task'], source_spans(source, binding['task']))]
        for name, binding in certified.items()
    }
    binding = {
        'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'DEV_labels_opened': False,
        'source_vetoes': certified, 'active_positions': activations, 'public_fixed_DEV_scope': public_dev,
        'TRAIN_grade_sha256': sha(grade), 'original_terminals': {
            module.POINTER.name: row[2]['terminal_sha256'] for module, row in artifacts.items()},
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (
            __file__, scope.__file__, ordinary.__file__, ordinary_later.__file__,
            parse.__file__, parse_later.__file__, b5.__file__,
        )},
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    ordinary.previous.snapshot(out, binding['source_sha256'])
    tag = immutable_json(out / 'sealed_predictions.json', predictions)
    labels = read(grade)
    values = {name: outcome(certified[group]['task'], predictions[name], source, labels)
              for name, (group, _, _) in routes.items()}
    unique = set().union(*(set(rows) for rows in predictions.values()))
    report = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'TRAIN_forward_replay': values, 'independent_forward_mothers': len(unique),
        'shared_source_scope': activations, 'public_fixed_DEV_scope': public_dev,
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', report)
    write_status(out, {'status': report['status'], 'terminal_sha256': report['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
