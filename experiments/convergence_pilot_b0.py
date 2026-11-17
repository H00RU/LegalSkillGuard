"""Run the common fixed-input baseline on the locked 20-source TRAIN pilot."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_learning import direct_program
from legal_skill_guard.paired_interfaces.diversity import score as score_diversity
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/legal_skill_convergence_20261117'
HANDOFF = BASE / 'handoff'
POINTER = HANDOFF / 'pilot_b0_current.json'
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
LEGACY_TRAIN = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_status(out, state):
    payload = {'artifact_root': str(out.relative_to(ROOT)), **state}
    temp = POINTER.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    temp.replace(POINTER)


def cells_for(source):
    if source['dataset'] == 'OpenExempt':
        # EV receives solved premises that are separate from the EC task.
        for view in source['views']:
            yield {**source, 'views': [view]}
    else:
        yield source


def prepare():
    roster_receipt = read(HANDOFF / 'sealed_source_roster_current.json')
    roster = ROOT / roster_receipt['artifact_root'] / 'binding.json'
    lock = read(roster)
    if digest(lock) != roster_receipt['roster_sha256']:
        raise ValueError('Data roster binding changed')
    normalized = ROOT / lock['normalized_root'] / 'train'
    sources = {source['key']: source for source in read(normalized / 'public.json')}
    originals = []
    for entry in lock['fixed_pilot']:
        source = sources[entry['source']]
        if digest(source) != entry['public_sha256']:
            raise ValueError('TRAIN pilot source bytes differ')
        originals.append(source)
    expected = Counter({'OpenExempt': 4, 'ContractNLI': 4, 'MAUD': 4,
                        'RuleArena_Airline': 4, 'LegalBench_Diversity': 4})
    if Counter(source['dataset'] for source in originals) != expected:
        raise ValueError('The TRAIN pilot must contain four roots per dataset')
    legacy_golds = LEGACY_TRAIN / 'grading.json'
    contract_golds = normalized / 'CNI_MAUD_grading_only.json'
    diversity_golds = ROOT / read(HANDOFF / 'diversity_train_current.json')['artifact_root'] / 'grading.json'
    grading_paths = {
        'OpenExempt': legacy_golds, 'RuleArena_Airline': legacy_golds,
        'ContractNLI': contract_golds, 'MAUD': contract_golds,
        'LegalBench_Diversity': diversity_golds,
    }
    grade_cache = {path: read(path) for path in set(grading_paths.values())}
    for source in originals:
        expected_tasks = {view['id'] for view in source['views']}
        actual_tasks = set(grade_cache[grading_paths[source['dataset']]][source['key']])
        if actual_tasks != expected_tasks:
            raise ValueError('Native TRAIN annotation coverage changed for ' + source['dataset'])
    paths = [
        'experiments/convergence_pilot_b0.py',
        'legal_skill_guard/paired_interfaces/formal_actors.py',
        'legal_skill_guard/paired_interfaces/control_programs.py',
        'legal_skill_guard/paired_interfaces/control_worker.py',
        'legal_skill_guard/paired_interfaces/control_answers.py',
        'legal_skill_guard/paired_interfaces/control_tools.py',
        'legal_skill_guard/paired_interfaces/formal_tools.py',
        'legal_skill_guard/paired_interfaces/control_learning.py',
        'legal_skill_guard/skill_evolution/native.py',
        'legal_skill_guard/skill_evolution/clients.py',
        'legal_skill_guard/skill_evolution/ledger.py',
        'legal_skill_guard/rr/client.py',
    ]
    program = direct_program()
    binding = {
        'study_id': 'convergence_pilot20_B0_v1',
        'pilot_source_roster_sha256': digest(lock),
        'source_sha256': {name: sha(ROOT / name) for name in paths},
        'grading_paths': {name: str(path.relative_to(ROOT)) for name, path in grading_paths.items()},
        'grading_file_sha256': {str(path.relative_to(ROOT)): sha(path) for path in set(grading_paths.values())},
        'sources_digest': digest(originals), 'program': program,
        'executor': read(HANDOFF / 'executor_readiness.json')['executor_config'],
        'per_source_model_budget': 'one native bundle, two independent calls for the separate OpenExempt tasks',
        'development_only': True,
    }
    out = BASE / 'pilot20_B0' / digest(binding)
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'reused_terminal': True, 'new_calls': 0}))
        return
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'public_TRAIN_pilot.json', originals)
    # Confirm the new context layout preserves all CNI text and spans
    # mechanically, without presenting any source text to stdout.
    for source in originals:
        if source['dataset'] != 'ContractNLI':
            continue
        public = source_bundle(source)['public']
        for actual, expected_view in zip(public['native_views'], source['views']):
            presentation = deepcopy(actual['public'])
            presentation.update(public['shared_documents'][presentation.pop('document_ref')])
            if presentation != expected_view['public']:
                raise ValueError('Compact ContractNLI context changed a native task')
    count = sum(1 for source in originals for _ in cells_for(source))
    write_status(out, {'status': 'prepared', 'mothers': len(originals), 'executor_cells': count})
    print(json.dumps({'prepared': str(out.relative_to(ROOT)), 'mothers': len(originals),
                      'executor_cells': count}), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'reused_terminal': True, 'new_calls': 0}))
        return
    binding = read(out / 'binding.json')
    for name, expected in (binding['source_sha256'] | binding['grading_file_sha256']).items():
        if sha(ROOT / name) != expected:
            raise ValueError('Bound implementation or grading bytes changed: ' + name)
    sources = read(out / 'public_TRAIN_pilot.json')
    if digest(sources) != binding['sources_digest']:
        raise ValueError('Locked TRAIN binding changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('Settle existing physical requests before starting')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-pilot-B0-' + digest(binding)[:16],
                             sources={'train': [source['key'] for source in sources], 'dev': [], 'test': []},
                             binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.exact_replay_roots = tuple(sorted((BASE / 'm2_update_probe').glob('*')))
    executor.readiness()
    actor = ProgramActor(executor, out, max_calls=1)
    program = binding['program']
    grades = {dataset: read(ROOT / path) for dataset, path in binding['grading_paths'].items()}
    rows = []
    write_status(out, {'status': 'running', 'pid': os.getpid(), 'completed': 0})
    try:
        for source in sources:
            predictions = {}
            for cell in cells_for(source):
                result = actor.execute(program, cell, 'skill_actor')
                actor.verify_program_result(cell, program, 'skill_actor', result)
                predictions.update(result['native'])
            dataset = source['dataset']
            native_grades = {}
            for view in source['views']:
                name = view['id']
                guess = predictions[name]
                annotation = grades[dataset][source['key']][name]
                native_grades[name] = grade_view(
                    dataset, view, annotation, guess['answer'], guess['evidence_sentence_ids'])
            row = {'source': source['key'], 'dataset': dataset, 'native': predictions, 'grades': native_grades}
            immutable_json(out / 'source_results' / (digest(source['key']) + '.json'), row)
            rows.append(row)
            write_status(out, {'status': 'running', 'pid': os.getpid(), 'completed': len(rows)})
        by_dataset = defaultdict(lambda: defaultdict(list))
        cni_evidence = []
        diversity_predictions = {}
        for row in rows:
            for name, grade in row['grades'].items():
                label = name if row['dataset'] in ('OpenExempt', 'MAUD') else 'native'
                by_dataset[row['dataset']][label].append(grade['grade'])
                if 'evidence_f1' in grade:
                    cni_evidence.append(grade['evidence_f1'])
            if row['dataset'] == 'LegalBench_Diversity':
                diversity_predictions[row['source']] = row['native']['native']['answer']
        report = {dataset: {family: {'values': scores,
                                    'mean': sum(score or 0.0 for score in scores) / len(scores)}
                            for family, scores in families.items()}
                  for dataset, families in by_dataset.items()}
        report['LegalBench_Diversity'].update(score_diversity(
            diversity_predictions,
            {source: grades['LegalBench_Diversity'][source] for source in diversity_predictions}))
        report['ContractNLI']['evidence_f1'] = {
            'mean': sum(cni_evidence) / len(cni_evidence) if cni_evidence else None,
            'scored_annotations': len(cni_evidence),
        }
        terminal = {'status': 'completed', 'mothers': len(rows), 'native_metrics_per_library': report,
                    'not_independent_validation': True}
        immutable_json(out / 'terminal.json', terminal)
        write_status(out, terminal)
        print(json.dumps(terminal, ensure_ascii=False), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'completed': len(rows),
                           'error_type': type(error).__name__})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    args = parser.parse_args()
    (prepare if args.phase == 'prepare' else run)()
