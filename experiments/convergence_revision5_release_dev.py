"""Compose the latest bound native repairs over the revised formal five-library DEV cohort."""

import json
from functools import lru_cache
from pathlib import Path

from experiments import convergence_revision5_cni_agreement_event_attachment as cni
from experiments import convergence_revision5_formal_native as formal
from experiments import convergence_revision5_oe_pa_monetary as pa
from experiments.convergence_formal_train_fit import EXTERNAL_ARM
from experiments.convergence_oe_metrics import summarize as exemption_metrics
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision5_release_B8_DEV_20261119'
POINTER = HANDOFF / 'revision5_release_B8_DEV_current.json'
CNI, OE = 'ContractNLI', 'OpenExempt'
ARMS = ConvergenceEvaluation.arms
DATASETS = sorted(ConvergenceEvaluation.datasets)
CONTRASTS = formal.common.CONTRASTS


def stage(pointer):
    current = read(pointer)
    root = ROOT / current['artifact_root']
    terminal = verify(read(root / 'terminal.json'), 'terminal_sha256')
    spec = read(root / 'binding.json')
    if (terminal['terminal_sha256'] != current['terminal_sha256'] or terminal['TEST_opened']
            or terminal['binding_sha256'] != digest(spec) or root.name != digest(spec)):
        raise ValueError('Require the exact completed DEV stage')
    return root, terminal, spec


def verified_bank(path, expected):
    if sha(path) != expected:
        raise ValueError('Native predictions differ from their sealed receipt')
    return read(path)


def later_outputs(parent):
    cni_root, cni_terminal, cni_spec = stage(cni.POINTER)
    role_root, role_terminal, _ = stage(cni.roles.POINTER)
    _, composed_terminal, composed_spec = stage(cni.events.composed.POINTER)
    if (cni_spec['prior_TERMINAL'] != role_terminal['terminal_sha256']
            or cni_spec['reused_formal_DEV_prediction_sha256'] != sha(role_root / 'formal_cni_dev_predictions.json')
            or composed_spec['parent_B8_terminal_sha256'] != parent['terminal_sha256']
            or composed_terminal['predictions_sha256']['train'] != cni_spec['last_composition_TRAIN_prediction_sha256']):
        raise ValueError('The ContractNLI cumulative amendment must use the exact revised DEV ancestry')
    cni_bank = verified_bank(cni_root / 'formal_cni_dev_predictions.json',
                             cni_terminal['formal_CNI_DEV']['predictions_sha256'])
    oe_root, oe_terminal, oe_spec = stage(pa.POINTER)
    _, ec_terminal, ec_spec = stage(pa.ec.POINTER)
    if (oe_spec['B8_EC_terminal_sha256'] != ec_terminal['terminal_sha256']
            or ec_spec['parent_terminal_sha256'] != parent['terminal_sha256']):
        raise ValueError('The two OpenExempt tasks must share the same revised DEV ancestry')
    oe_bank = verified_bank(oe_root / 'predictions.json', oe_terminal['predictions_sha256'])['B8']
    return {CNI: cni_bank, OE: oe_bank}, {CNI: cni_terminal, OE: oe_terminal}


class ReleaseActor:
    def __init__(self, parent, cells, updates):
        self.parent = parent
        self.cells = cells
        self.updates = updates

    @lru_cache(maxsize=None)
    def original(self, arm, key):
        directory = self.parent / 'dev/B8' / arm
        entry = read(directory / 'predictions' / (digest(key) + '.json'))
        if digest(entry) != self.cells[arm][0]['predictions_sha256'][key]:
            raise ValueError('A parent prediction lost its seal')
        return entry

    def __call__(self, source, library, purpose):
        key, dataset, arm = source['key'], source['dataset'], library['arm']
        native = self.original(arm, key)
        score = self.cells[arm][1]
        if (purpose != 'skill_dev' or source['project_split'] != 'dev' or library['batch'] != 8
                or native['library_sha256'] != score['libraries'][dataset]
                or native['public_source_sha256'] != digest(source)):
            raise ValueError('Reuse only the exact original revised DEV arm, library and source')
        parent = native['result']
        if dataset not in self.updates:
            return parent
        if dataset == CNI:
            revised = self.updates[dataset][arm][key]
        else:
            revised = {task: {'answer': answer} for task, answer in self.updates[dataset][arm]['shared_PA'][key].items()}
        if set(revised) != set(parent['native']):
            raise ValueError('Do not drop native tasks during composition')
        output = {}
        for task, correction in revised.items():
            old = parent['native'][task]
            output[task] = {**old, **correction}
            if correction['answer'] is not None:
                output[task]['handled'] = True
            elif old['answer'] is not None:
                raise ValueError('A revision cannot silently remove a handled prediction')
        return {**parent, 'native': output, 'DEV_amendment_source_sha256': digest(revised)}

    def verify_saved(self, source, library, purpose, result):
        if self(source, library, purpose) != result:
            raise ValueError('Release predictions must reproduce the sealed amendment')


def parent_cells(root, terminal):
    cells = {}
    for arm in ARMS:
        directory = root / 'dev/B8' / arm
        seal = verify(read(directory / 'prediction_seal.json'), 'prediction_seal_sha256')
        score = verify(read(directory / 'scores.json'), 'cell_sha256')
        if (score['cell_sha256'] != terminal['per_arm'][arm]['cell_sha256']
                or score['prediction_seal_sha256'] != seal['prediction_seal_sha256']
                or seal['task_sha256'] != digest(read(directory / 'task.json'))):
            raise ValueError('Earlier DEV cells cannot be replaced by unsealed results')
        cells[arm] = seal, score
    return cells


def m2_program_changes(archive):
    checkpoint, study, roster = cni.base.archive.archive_context()
    journal = TrainingJournal(checkpoint, study, roster)
    libraries = {arm: journal.library(arm, 8) for arm in ARMS if arm != EXTERNAL_ARM}
    for arm, library in libraries.items():
        if dict.fromkeys(DATASETS, library['snapshot_sha256']) != archive[arm][2]['libraries']:
            raise ValueError('Mechanism activation must use the same B8 library as the original actor')
    return {
        name: {d: libraries[active]['programs'][d] != libraries[control]['programs'][d] for d in DATASETS}
        for name, (active, control) in CONTRASTS.items() if name.startswith('M2')
    }


def units(rows, dataset, view=None, metric='grade'):
    selected = [r for r in rows if r['dataset'] == dataset and (view is None or r['view'] == view)]
    return [{'source': r['source'], 'view': r['view'], 'grade':
             r['grade'] if metric == 'grade' else r['native_metrics'].get(metric, 0.)} for r in selected]


def effects(before, after):
    result = {}
    for dataset in DATASETS:
        tasks = sorted({r['view'] for r in before if r['dataset'] == dataset}) if dataset in ('MAUD', OE) else []
        result[dataset] = {
            task: paired_source_effect(units(before, dataset, task), units(after, dataset, task))
            for task in tasks
        } if tasks else {'native': paired_source_effect(units(before, dataset), units(after, dataset))}
    result[CNI]['evidence_f1'] = paired_source_effect(
        units(before, CNI, metric='evidence_f1'), units(after, CNI, metric='evidence_f1'))
    return result


def contrast_reports(rows, bank, cohort):
    return {
        name: {
            'native_output_differences': differences(bank[active], bank[control], cohort),
            'effects': effects(rows[control], rows[active]),
        }
        for name, (active, control) in CONTRASTS.items()
    }


def differences(active, control, cohort):
    result = dict.fromkeys(DATASETS, 0)
    for source in cohort:
        key = source['key']
        for task, a in active[key].items():
            b = control[key][task]
            if (a['handled'], a.get('answer'), a.get('evidence_sentence_ids', [])) != (
                    b['handled'], b.get('answer'), b.get('evidence_sentence_ids', [])):
                result[source['dataset']] += 1
    return result


def run():
    ledger = formal.diversity_formal.ledger_status()
    if ledger.get('reserved'):
        raise ValueError('Use a settled continuous ledger')
    root, terminal, parent_spec = stage(formal.CURRENT)
    cohort, original, study, original_terminal = formal.common.archive()
    cells = parent_cells(root, terminal)
    updates, evidence = later_outputs(terminal)
    spec = {'study': 'revision5_cumulative_five_library_B8_DEV',
            'DEV_public_sha256': parent_spec['DEV_public_sha256'],
            'TEST_identities_sha256': parent_spec['TEST_identities_sha256'],
            'original_terminal_sha256': original_terminal,
            'parent_terminal_sha256': terminal['terminal_sha256'],
            'amendments': {d: row['terminal_sha256'] for d, row in evidence.items()},
            'source_sha256': sha(Path(__file__)), 'enforce_physical_actor_audit': True}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    if (out / 'terminal.json').exists():
        print(out)
        return
    identities = read(ROOT / read(formal.DEV_B0)['artifact_root'] / 'sealed_TEST_identity_metadata_only.json')
    sources = {s['key']: s for s in cohort}

    @lru_cache(maxsize=None)
    def labels(path):
        filename = ROOT / path
        if 'dev' not in filename.parts or sha(filename) != study['grading_file_sha256'][path]:
            raise ValueError('Only original DEV grading is authorized here')
        return read(filename)

    def grade(partition, key, seal):
        if partition != 'dev' or set(seal['predictions_sha256']) != sources.keys():
            raise ValueError('Every arm must seal the entire five-library cohort before grading')
        return labels(study['grading_paths'][sources[key]['dataset']])[key]

    eval_dev = ConvergenceEvaluation(out, cohort, identities, binding=spec, grade_provider=grade,
                                      load_test=formal.diversity_formal.no_test)
    actor = ReleaseActor(root, cells, updates)
    reports, rows, bank = {}, {}, {}
    for arm in ARMS:
        library = sealed({'arm': arm, 'batch': 8, 'binding_sha256': out.name,
                         'parent_cell_sha256': cells[arm][1]['cell_sha256']}, 'snapshot_sha256')
        immutable_json(out / 'libraries' / f'{arm}.json', library)
        current = eval_dev.evaluate('dev', arm, 8, dict.fromkeys(DATASETS, library), actor)
        rows[arm] = current['source_scores']
        bank[arm] = {s['key']: actor(s, library, 'skill_dev')['native'] for s in cohort}
        amended = set(evidence)
        if ([x for x in rows[arm] if x['dataset'] not in amended] !=
                [x for x in cells[arm][1]['source_scores'] if x['dataset'] not in amended]):
            raise ValueError('The other three libraries must inherit their exact settled native outputs')
        native = formal._native_metrics(rows[arm], labels, study['grading_paths'])
        pa_scores = evidence[OE]['B8_scores'][arm]
        for task in pa.TASKS:
            expected = pa_scores[task]['shared_PA']['f1']
            if abs(native[OE]['views'][task]['native_utility'] - expected) > 1e-12:
                raise ValueError('OpenExempt scores must reproduce the scoped two-task replay')
        reports[arm] = {
            'cell_sha256': current['cell_sha256'], 'activation': terminal['per_arm'][arm]['activation'],
            'native': native, 'effects_vs_original': effects(original[arm][2]['source_scores'], rows[arm]),
            'effects_vs_revised_parent': effects(cells[arm][1]['source_scores'], rows[arm]),
            'official_OpenExempt_metrics': {
                'original': exemption_metrics(original[arm][2]['source_scores']),
                'earlier_revision': exemption_metrics(cells[arm][1]['source_scores']),
                'current_revision': exemption_metrics(rows[arm]),
            },
        }
    contrasts = contrast_reports(rows, bank, cohort)
    if ledger != formal.diversity_formal.ledger_status():
        raise ValueError('Composing settled DEV predictions requires no new requests')
    record = sealed({'status': 'completed_cumulative_five_library_B8_DEV', 'binding_sha256': out.name,
                     'per_arm': reports, 'contrasts': contrasts,
                     'M2_changed_B8_program_by_library': m2_program_changes(original),
                     'DEV_mothers': len(cohort), 'DEV_views_per_arm': len(next(iter(rows.values()))),
                     'ledger': ledger, 'new_model_calls': 0, 'TEST_opened': False}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', record)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'status': record['status'], 'artifact_root': str(out.relative_to(ROOT)),
                                   'terminal_sha256': record['terminal_sha256']}) + '\n')
    pending.replace(POINTER)
    print(out)


if __name__ == '__main__':
    run()
