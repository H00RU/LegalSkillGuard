"""Restore exact source overlap for negative covenants in the fixed B8 MAUD release."""

import json
from pathlib import Path
import sqlite3

from experiments import convergence_revision5_maud_adoption_scope as adoption
from experiments import convergence_revision5_maud_parent_definition_coverage as parent_views
from experiments import convergence_revision5_maud_section_scope as previous
from experiments import convergence_revision5_release_dev as release
from experiments import convergence_revision6_ec_property_release as ec_release
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import maud_parallel_excerpt as local
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_maud_parallel_release'
POINTER = HANDOFF / 'revision6_maud_parallel_release_current.json'
TASK = parent_views.NEGATIVE
MAUD = previous.MAUD
ATTACHED = {'attached_in_negative_preamble', 'attached_by_explicit_clause_list'}


def proof(source):
    texts = {v['id']: parent_views.unpage(v['public']['source_text']) for v in source['views']}
    return local.attachment(texts[TASK], texts[parent_views.ORDINARY])


def train_proofs(db):
    checkpoint, study, batches = adoption.archive_context()
    journal = previous.TrainingJournal(checkpoint, study, batches)
    evidence, archived, verified = {}, {}, set()
    refs = set()
    for batch, group in enumerate(batches, 1):
        for ordinal, source in enumerate(s for s in group if s['dataset'] == MAUD and s['project_split'] == 'train'):
            found = proof(source)
            if found is None:
                continue
            key = source['key']
            stage, spec, end = previous.bound_stage(previous.FIRST if batch == 1 else previous.observe_pointer(batch))
            path = spec['native_grade_paths'][MAUD]
            refs.add((path, spec['native_grade_sha256'][path]))
            evidence[key] = {**found, 'TRAIN_position': [batch, ordinal],
                             'original_TRAIN_terminal_sha256': sha(stage / 'terminal.json')}
            archived[key] = {}
            for arm in previous.ARMS:
                settled = journal._observations(arm, batch)
                recorded = read(journal.directory(arm, batch) / 'predictions' / (digest(key) + '.json'))
                if (digest(recorded) != settled['predictions'][key]
                        or settled['train_observation_sha256'] != end['observation_receipts'][arm]):
                    raise ValueError('Preserve the exact original TRAIN views and responses')
                result = recorded['result']
                identity = previous.verify_prediction(db, key, result)
                _, payload = previous.response(db, key, identity)
                adoption.verify_views(payload, source)
                verified.add(identity)
                archived[key][arm] = result['native'][TASK]['answer']
    if not verified:
        raise ValueError('An exact TRAIN observation must support comparison with the original excerpts')
    grade, = refs
    return evidence, archived, grade, len(verified)


class ParallelExcerptActor:
    def __init__(self, parent, cells, proofs):
        self.parent = ec_release.PropertyReleaseActor(parent, cells)
        self.proofs = proofs

    def __call__(self, source, library, purpose):
        baseline = self.parent(source, library, purpose)
        if source['dataset'] != MAUD:
            return baseline
        scope = self.proofs.get(source['key'])
        original = baseline['native'][TASK]
        if scope is None or scope['scope'] not in ATTACHED or original['answer'] == 'Yes':
            return baseline
        update = {**original, 'answer': 'Yes', 'handled': True}
        return {**baseline, 'native': {**baseline['native'], TASK: update}}


def verify_original_inputs(db, sealed_originals, sources, keys):
    seen = set()
    for arm, (folder, prediction_seal, score) in sealed_originals.items():
        for key in keys:
            source = sources[key]
            saved = read(folder / 'predictions' / (digest(key) + '.json'))
            if (digest(saved) != prediction_seal['predictions_sha256'][key]
                    or saved['library_sha256'] != score['libraries'][MAUD]
                    or saved['public_source_sha256'] != digest(source)):
                raise ValueError('Both sibling views must be sourced from the original fixed DEV request')
            before = set(seen)
            previous.verify_wire(db, key, saved['result'], seen)
            for identity in seen - before:
                record, = db.execute('select result from calls where id=?', (identity,)).fetchone()
                response = json.loads(record)
                request = read(Path(response['artifact_directory']) / 'request.json')['payload']
                adoption.verify_views(request, source)
    return len(seen)


def run():
    base, terminal, bound = release.stage(release.POINTER)
    ec_home = ROOT / read(ec_release.POINTER)['artifact_root']
    ec_terminal = verify(read(ec_home / 'terminal.json'), 'terminal_sha256')
    if ec_terminal['archive_terminal_sha256'] != terminal['terminal_sha256'] or ec_terminal['TEST_opened']:
        raise ValueError('Keep the original cumulative DEV release and OpenExempt amendment')
    cohort, original, study, _ = release.formal.common.archive()
    if digest(cohort) != bound['DEV_public_sha256']:
        raise ValueError('Require the original fixed DEV source roster')
    sources = {s['key']: s for s in cohort if s['dataset'] == MAUD and s['project_split'] == 'dev'}
    proofs = {key: proof(source) for key, source in sources.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        evidence, training_archive, train_grade, paid_train = train_proofs(db)
        paid_dev = verify_original_inputs(db, original, sources, [k for k, p in proofs.items() if p])
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or len(sources) != 16:
        raise ValueError('Require the complete fixed MAUD DEV and settled research ledger')
    cells = release.parent_cells(base, terminal)
    path = study['grading_paths'][MAUD]
    spec = {
        'stage': 'revision6_maud_parallel_release', 'original_terminal_sha256': terminal['terminal_sha256'],
        'previous_EC_amendment': ec_terminal['terminal_sha256'], 'DEV_grade_sha256': study['grading_file_sha256'][path],
        'TRAIN_grade_sha256': train_grade[1], 'proof_sha256': digest(proofs), 'TRAIN_proofs_sha256': digest(evidence),
        'TEST_opened': False, 'source_sha256': {str(Path(name).relative_to(ROOT)): sha(Path(name))
                                               for name in (__file__, local.__file__, release.__file__, ec_release.__file__)},
    }
    actor = ParallelExcerptActor(base, cells, proofs)
    bank = {}
    for arm in release.ARMS:
        library = {'arm': arm, 'batch': 8}
        bank[arm] = {}
        for key, source in sources.items():
            old = actor.parent(source, library, 'skill_dev')['native']
            new = actor(source, library, 'skill_dev')['native']
            if {n: v for n, v in old.items() if n != TASK} != {n: v for n, v in new.items() if n != TASK}:
                raise ValueError('The exact other two MAUD tasks must be inherited')
            bank[arm][key] = {'prior': old[TASK], 'amended': new[TASK]}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    for name, h in spec['source_sha256'].items():
        snapshot = out / 'source_snapshot' / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            with snapshot.open('xb') as stream:
                stream.write((ROOT / name).read_bytes())
        if sha(snapshot) != h:
            raise ValueError('Retain the exact proof and cumulative actor')
    pred = immutable_json(out / 'sealed_predictions.json', bank)
    immutable_json(out / 'source_proofs.json', {'train': evidence, 'dev': proofs})
    grader, train_path = ROOT / path, ROOT / train_grade[0]
    if ('dev' not in grader.parts or sha(grader) != spec['DEV_grade_sha256']
            or 'train' not in train_path.parts or sha(train_path) != spec['TRAIN_grade_sha256']):
        raise ValueError('Use only original native split scoring after the seal')
    labels, train_labels = read(grader), read(train_path)
    rows = {}
    for arm, outputs in bank.items():
        result = {'prior': [], 'amended': []}
        for key, values in outputs.items():
            view = previous.view_for(sources[key])
            for mode, value in values.items():
                native = grade_view(MAUD, view, labels[key][TASK], value['answer'])
                result[mode].append({'source': key, 'view': TASK, 'grade': native['grade']})
        rows[arm] = {'before_correct': sum(r['grade'] for r in result['prior']),
                     'after_correct': sum(r['grade'] for r in result['amended']),
                     'predictions_changed': sum(v['prior'] != v['amended'] for v in outputs.values()),
                     'paired_effect': paired_source_effect(result['prior'], result['amended'])}
    result = sealed({
        'status': 'settled_revision6_maud_parallel_release', 'binding_sha256': out.name,
        'TRAIN_controls': [{**r, 'native_answer': train_labels[key][TASK]['answer'],
                            'original_reads': training_archive[key],
                            'would_attach': r['scope'] in ATTACHED} for key, r in evidence.items()],
        'DEV_evidence': [{**p, 'native_answer': labels[key][TASK]['answer'],
                          'proof_has_pandemic_scope': p['scope'] in ATTACHED}
                         for key, p in proofs.items() if p],
        'DEV_mothers': len(sources), 'per_arm': rows, 'predictions_sha256': pred,
        'original_requests_verified': {'train': paid_train, 'dev': paid_dev},
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
