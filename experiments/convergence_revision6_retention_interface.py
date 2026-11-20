"""Fit a scoped ContractNLI retention reader on original TRAIN, then compare on fixed DEV."""

import argparse
from collections import Counter
import fcntl
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_cni_disposition_scope as disposition
from experiments import convergence_revision5_cni_trigger_coverage as scope_review
from experiments import convergence_revision5_m2_cni_disposition_retention as review
from experiments import convergence_revision6_retention_scope as diagnosis
from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_retention_interface as interface
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


CNI, TASK = review.DATASET, interface.TASK
HOME = BASE / 'revision6_retention_interface'
TRAIN_ROLES = ('fixed', 'synthesized', 'direct')
# Add the independently reviewed reproduction/disposal split, two complete
# contracts with no applicable disposition, and two additional forms of a bar.
TRAIN_POSITIONS = frozenset(review.REVIEWS) | {(7, 2), (3, 1), (4, 1), (2, 2), (4, 2)}


def pointer(partition):
    return HANDOFF / f'revision6_retention_interface_{partition}_current.json'


def case(source):
    view, = (row for row in source['views'] if row['id'] == TASK)
    spans = disposition.spans_for(view)
    return {'source': source['key'], 'view': view, 'payload': {
        'document': view['public']['source_text'],
        'question': view['public']['question'],
        'indexed_spans': [{'id': i, 'text': span} for i, span in enumerate(spans)],
    }}


def training(study, parent):
    audits = {r['source']: r for r in read(scope_review.HOME / 'source_inventory.json')}
    registered = {r['source']: r for r in read(scope_review.REGISTRY)['reviews']
                  if r['kind'] == 'literal_semantic_graph' and r['view'] == 'v0'}
    selected, references, grades = {}, {}, set()
    for batch, roster in enumerate(review.load_roster(study), 1):
        stage_pointer = disposition.FIRST_OBSERVE if batch == 1 else disposition.observe_pointer(batch)
        stage = ROOT / read(stage_pointer)['artifact_root']
        spec, end = (read(stage / name) for name in ('binding.json', 'terminal.json'))
        if stage.name != digest(spec) or end['TEST_opened'] or spec['batch'] != batch:
            raise ValueError('Require original training observations in their original order')
        name = spec['native_grade_paths'][CNI]
        grades.add((name, spec['native_grade_sha256'][name]))
        for index, source in enumerate(s for s in roster if s['dataset'] == CNI):
            if (batch, index) not in TRAIN_POSITIONS:
                continue
            key = source['key']
            a = audits[key]
            card = registered[key]
            view = next(v for v in source['views'] if v['id'] == disposition.TASK)
            if (source['project_split'] != 'train' or a['source_sha256'] != digest(view['public'])
                    or sha(ROOT / card['path']) != card['sha256']
                    or a['graph_card']['sha256'] != card['sha256']):
                raise ValueError('The complete TRAIN source must match the original review')
            selected[key] = case(source)
            references[key] = {'position': (batch, index), 'source_review': card['sha256'],
                               'observation_terminal': sha(stage / 'terminal.json')}
    if len(selected) != len(TRAIN_POSITIONS):
        raise ValueError('All preregistered source forms must be present')
    grade, = grades
    return selected, grade, references, parent['terminal_sha256']


def development(study):
    train = ROOT / read(pointer('train'))['artifact_root']
    fitted = verify(read(train / 'terminal.json'), 'terminal_sha256')
    library = verify(read(train / 'TRAIN_batch_libraries/B8.json'), 'snapshot_sha256')
    if library['snapshot_sha256'] != fitted['library_sha256'] or library['active'] != 'synthesized':
        raise ValueError('The fixed DEV reader requires positive comparative TRAIN evidence')
    stage = ROOT / read(dev_pointer(8))['artifact_root']
    spec, end = (read(stage / name) for name in ('binding.json', 'terminal.json'))
    data = ROOT / spec['b0_dev_data_root']
    public = read(data / 'public_DEV_sources.json')
    if (stage.name != digest(spec) or end['TEST_opened'] or len(public) != 80
            or digest(public) != study['DEV_public_sha256']
            or digest(public) != read(data / 'binding.json')['DEV_public_sha256']):
        raise ValueError('Keep the original fixed DEV cohort and exposure boundary')
    sources = {s['key']: case(s) for s in public if s['dataset'] == CNI and s['project_split'] == 'dev'}
    if len(sources) != 16:
        raise ValueError('Use the entire original fixed ContractNLI DEV cohort')
    name = study['grading_paths'][CNI]
    return sources, (name, study['grading_file_sha256'][name]), library, fitted['terminal_sha256']


def score(cases, outputs, labels):
    rows, summary = {}, {}
    for role, bank in outputs.items():
        rows[role] = records = []
        for key, result in bank.items():
            native = grade_view(CNI, cases[key]['view'], labels[key][TASK], result['answer'], result['evidence'])
            records.append({'source': key, 'view': TASK, 'valid': native['valid'],
                            'grade': native['grade'], 'evidence_f1': native['evidence_f1'],
                            'grounded': native['grade'] * native['evidence_f1']})
        summary[role] = {'correct': sum(row['grade'] for row in records),
                         'native_valid': sum(row['valid'] for row in records),
                         'evidence_f1': mean(row['evidence_f1'] for row in records),
                         'grounded': mean(row['grounded'] for row in records)}
    effects = {role: {metric: paired_source_effect(*[
        [{**row, 'grade': row[metric]} for row in rows[arm]] for arm in (role, 'synthesized')
    ]) for metric in ('grade', 'evidence_f1', 'grounded')} for role in rows if role != 'synthesized'}
    return summary, effects


def opened_binding(partition):
    _, _, previous = diagnosis.load_parent(diagnosis)
    checkpoint = ROOT / read(review.BOOTSTRAP)['artifact_root']
    study = read(checkpoint / 'binding.json')
    if checkpoint.name != digest(study) or study['executor']['enable_thinking'] is not False:
        raise ValueError('Keep the sealed study and executor profile')
    cases, grade, fitted, reference = (training(study, previous) if partition == 'train' else development(study))
    module, assets = interface.layouts()
    versions = {name: asset['version'] for name, asset in assets.items()}
    if partition == 'dev' and versions != fitted['interfaces']:
        raise ValueError('The DEV reader must be the exact acquired TRAIN version')
    roles = TRAIN_ROLES if partition == 'train' else ('synthesized', 'direct')
    wires = {key: {role: interface.request(value['payload'], role) for role in roles} for key, value in cases.items()}
    if any(arms[roles[0]][0][1] != arms[role][0][1] for arms in wires.values() for role in roles):
        raise ValueError('Only the interface assignment may vary')
    files = (str(Path(__file__).relative_to(ROOT)), str(Path(interface.__file__).relative_to(ROOT)),
             'legal_skill_guard/paired_interfaces/residual.py', 'legal_skill_guard/rr/client.py',
             'legal_skill_guard/skill_evolution/native.py', 'legal_skill_guard/skill_evolution/clients.py')
    return cases, grade, fitted, roles, wires, {
        'partition': partition, 'executor': study['executor'], 'reference_TERMINAL': reference,
        'source_pool_sha256': digest(cases), 'readers_sha256': digest(wires), 'grade_sha256': grade[1],
        'training_evidence_sha256': digest(fitted), 'source_sha256': {name: sha(ROOT / name) for name in files},
        'consumer_states': len(module.states), 'consumer_sha256': module.binding, 'interfaces': versions,
        'roles': roles, 'TEST_opened': False,
    }


def acquired_library(out, binding, predictions, summary, sources, pred_sha):
    def rank(role):
        return (summary[role]['correct'], summary[role]['grounded'])
    selected = max(('fixed', 'synthesized'), key=rank)
    known_error, = (key for key, v in sources.items() if tuple(v['position']) == (7, 2))
    repaired = predictions['synthesized'][known_error]['answer'] == interface.CONTRADICTION
    active = selected if selected == 'synthesized' and repaired and rank(selected) > rank('direct') else None
    library = sealed({
        'batch': 8, 'binding_sha256': out.name, 'interfaces': binding['interfaces'],
        'selected': selected, 'active': active, 'TRAIN_scores': summary, 'TRAIN_predictions_sha256': pred_sha,
        'B7_original_error_repaired_by_synthesis': repaired,
        'consumer_sha256': binding['consumer_sha256'],
        'scope': 'ContractNLI nda-20 on the same complete protected contract and original native spans',
    }, 'snapshot_sha256')
    immutable_json(out / 'TRAIN_batch_libraries/B8.json', library)
    return library


def run(partition, execute):
    cases, grade, training_evidence, roles, wires, binding = opened_binding(partition)
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'wire_tasks.json', wires)
    immutable_json(out / 'training_evidence.json', training_evidence)
    marker = pointer(partition)
    if (out / 'terminal.json').exists():
        print(out)
        return
    if not execute:
        write_status(out, {'status': 'prepared', 'planned_calls': len(cases) * len(roles)}, marker)
        print(out)
        return
    if ROOT / read(marker)['artifact_root'] != out:
        raise ValueError('Prepare the exact current comparison before executing')
    lock = (out / 'driver.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for name, expected in binding['source_sha256'].items():
        target = out / 'source_snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with target.open('xb') as file:
                file.write((ROOT / name).read_bytes())
        if sha(target) != expected or sha(ROOT / name) != expected:
            raise ValueError('The bound consumer or transport changed')
    scope = {name: list(cases) if name == partition else [] for name in ('train', 'dev', 'test')}
    ledger = EvolutionLedger(LEDGER, run_id=f'revision6-M1-retention-{partition}-{out.name[:12]}',
                             sources=scope, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    purpose = 'skill_actor' if partition == 'train' else 'skill_dev'
    bank = {role: {} for role in roles}
    usage = {role: Counter() for role in roles}
    for index, (key, value) in enumerate(cases.items()):
        traversal = roles[index % len(roles):] + roles[:index % len(roles)]
        for role in traversal:
            identity = f'{ledger.run_id}:{digest(key)}:{role}'
            messages, schema = wires[key][role]
            try:
                raw = executor.generate(identity, source=key, purpose=purpose, messages=messages, schema=schema,
                                        thinking=False)
            except Exception:
                write_status(out, {'status': 'interrupted', 'completed_mothers': index,
                                   'current_request': identity}, marker)
                raise
            verify_physical_response(executor, identity=identity, source=key, purpose=purpose,
                content_sha256=digest(raw['content']), usage=raw['usage'], finish_reason=raw['finish_reason'])
            prediction, issue = interface.decode(value['payload'], role, schema, raw)
            bank[role][key] = prediction
            usage[role]['tokens'] += raw['usage']['total_tokens']
            usage[role]['wire_valid'] += issue is None
            immutable_json(out / 'responses' / (digest(identity) + '.json'),
                           {'identity': identity, 'prediction': prediction, 'issue': issue})
        write_status(out, {'status': 'running', 'completed_mothers': index + 1}, marker)

    pred = immutable_json(out / 'sealed_predictions.json', bank)
    label_path = ROOT / grade[0]
    if partition not in label_path.parts or sha(label_path) != binding['grade_sha256']:
        raise ValueError('Use only the originally bound native grader after sealing')
    summary, effects = score(cases, bank, read(label_path))
    with ledger.transaction() as db:
        dispatched = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                                    (ledger.run_id + ':%',)))
    if dispatched != {'completed': len(cases) * len(roles)}:
        raise ValueError('Require all physical paired responses')
    library = (acquired_library(out, binding, bank, summary, training_evidence, pred)
               if partition == 'train' else training_evidence)
    end = sealed({
        'status': f'settled_revision6_retention_interface_{partition}', 'binding_sha256': out.name,
        'partition': partition, 'mothers': len(cases), 'consumer_states': binding['consumer_states'],
        'library_sha256': library['snapshot_sha256'], 'active': library['active'], 'scores': summary,
        'synthesized_vs': effects, 'usage': {arm: dict(counts) for arm, counts in usage.items()},
        'predictions_sha256': pred, 'new_executor_requests': dispatched['completed'],
        'new_teacher_requests': 0, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', end)
    write_status(out, {'status': end['status'], 'terminal_sha256': end['terminal_sha256']}, marker)
    print(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('partition', choices=('train', 'dev'))
    parser.add_argument('action', choices=('prepare', 'run'))
    args = parser.parse_args()
    run(args.partition, args.action == 'run')
