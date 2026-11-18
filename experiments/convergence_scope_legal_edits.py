"""Recheck the sole native-positive SCOPE proposal on reversible contract role renamings."""

import argparse
from copy import deepcopy
import json
import math
import re
import sqlite3

from experiments.convergence_compact_teacher_pilot import pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_compact_proposal import compile_proposal
from legal_skill_guard.paired_interfaces.convergence_training import measure_program_prefix
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'scope_legal_edits_current.json'
RENAMES = {'Company': 'CompanyQ', 'Parent': 'ParentR'}


def rename_roles(source):
    """Rename defined role tokens consistently across the complete native bundle."""
    if source['dataset'] != 'MAUD' or source['project_split'] != 'train':
        raise ValueError('This edit is scoped to the original MAUD TRAIN bundle')
    edited = deepcopy(source)
    forward = re.compile(r'\b(?:' + '|'.join(RENAMES) + r')\b')
    back = {value: key for key, value in RENAMES.items()}
    inverse = re.compile(r'\b(?:' + '|'.join(back) + r')\b')
    spans = []
    for old, new in zip(source['views'], edited['views'], strict=True):
        for field in ('source_text', 'question'):
            text = old['public'][field]
            if inverse.search(text):
                raise ValueError('A replacement already occurs as an original token')
            updated = forward.sub(lambda match: RENAMES[match[0]], text)
            if inverse.sub(lambda match: back[match[0]], updated) != text:
                raise ValueError('A role rename must round-trip the complete public input')
            spans.extend({'task': old['id'], 'field': field, 'start': match.start(), 'end': match.end(),
                          'original': match[0], 'edited': RENAMES[match[0]]} for match in forward.finditer(text))
            new['public'][field] = updated
    if not spans or digest(source) == digest(edited):
        raise ValueError('A valid legal variant must change an explicit role reference')
    return {'source': edited, 'parent_source_sha256': digest(source), 'role_token_edits': spans,
            'edited_source_sha256': digest(edited), 'inverse_restores_every_public_task_field': True}


def prepare():
    scope = ROOT / read(pointer('scope'))['artifact_root']
    prior, terminal = read(scope / 'binding.json'), read(scope / 'terminal.json')
    parent = ROOT / prior['parent_root']
    common, sources = read(parent / 'binding.json'), read(parent / 'train_sources.json')
    if (scope.name != digest(prior) or digest(common) != prior['parent_binding_sha256']
            or terminal['status'] != 'completed' or digest(sources) != common['pilot_source_sha256']
            or {name for name, row in terminal['libraries'].items() if row['selected'] == 'candidate'} != {'MAUD'}):
        raise ValueError('Use exactly the settled fixed-cohort SCOPE selection and its sole positive update')
    target = scope / 'measured_libraries/MAUD.json'
    measurement = read(target)
    keys = [source['key'] for source in sources]
    candidate = compile_proposal(measurement['proposal'], keys)
    measured = measurement['measurement']
    selected = [source for source in sources if source['dataset'] == 'MAUD']
    if (measurement['summary'] != terminal['libraries']['MAUD'] or digest(candidate) != measured['program_sha256']
            or [(src['key'], digest(src)) for src in selected] != [(row['source'], row['public_sha256'])
                                                                 for row in measured['source_rows']]):
        raise ValueError('The candidate and all four original prediction inputs must bind the actual measurements')
    variants = [rename_roles(source) for source in selected]
    if len(variants) != 4:
        raise ValueError('Keep every original MAUD pilot source in the legal edit check')
    b0 = ROOT / read(HANDOFF / 'pilot_b0_current.json')['artifact_root']
    if sha(b0 / 'terminal.json') != common['common_terminal_receipts'][str(b0.relative_to(ROOT))]:
        raise ValueError('The common native predictions changed')
    incumbent = read(b0 / 'binding.json')['program']
    paths = set(prior['source_sha256']) | {'experiments/convergence_scope_legal_edits.py'}
    grade_path = common['grading_paths']['MAUD']
    binding = {'study': 'MAUD_ROLE_RENAMING_SAME_SOURCES_SCOPE_REGRESSION', 'scope_root': str(scope.relative_to(ROOT)),
               'scope_terminal_sha256': sha(scope / 'terminal.json'), 'scope_MAUD_measurement_sha256': sha(target),
               'parent_root': str(parent.relative_to(ROOT)), 'parent_binding_sha256': digest(common),
               'source_sha256': {path: sha(ROOT / path) for path in sorted(paths)},
               'variant_proof_sha256': digest(variants), 'executor': prior['executor'], 'grade_path': grade_path,
               'grade_file_sha256': common['grading_file_sha256'][grade_path],
               'programs': {'incumbent': incumbent, 'candidate': candidate},
               'all_roles_renamed_consistently': True, 'original_legal_conditions_and_native_labels_preserved': True,
               'early_gate': 'only evaluate variants of originally positive library updates',
               'regression_gate': 'no candidate-only error on an edited task whose original candidate grade was correct'}
    out = BASE / 'scope_legal_edits' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'variants.json', variants)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'mothers': len(variants), 'logical_reader_cells': 8}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    binding, variants = read(out / 'binding.json'), read(out / 'variants.json')
    scope = ROOT / binding['scope_root']
    parent = ROOT / binding['parent_root']
    originals = read(parent / 'train_sources.json')
    originals = [source for source in originals if source['dataset'] == 'MAUD']
    if (out.name != digest(binding) or digest(variants) != binding['variant_proof_sha256']
            or [rename_roles(source) for source in originals] != variants
            or digest(read(parent / 'binding.json')) != binding['parent_binding_sha256']
            or sha(scope / 'terminal.json') != binding['scope_terminal_sha256']
            or sha(scope / 'measured_libraries/MAUD.json') != binding['scope_MAUD_measurement_sha256']
            or any(sha(ROOT / path) != expected for path, expected in binding['source_sha256'].items())):
        raise ValueError('The frozen programs, source edits or original evidence are no longer identical')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Wait for the current physical request before continuing')
    edited = [row['source'] for row in variants]
    keys = [source['key'] for source in edited]
    ledger = EvolutionLedger(LEDGER, run_id='convergence-SCOPE-legal-edit-' + out.name[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    actor = ProgramActor(reader, out, max_calls=1)
    annotations = {}

    def grade(key):
        if not annotations:
            path = ROOT / binding['grade_path']
            if sha(path) != binding['grade_file_sha256']:
                raise ValueError('The native TRAIN labels used for the independent invariance check changed')
            annotations.update(read(path))
        return annotations[key]

    scores = {}
    write_status(out, {'status': 'running', 'mothers': len(variants), 'logical_reader_cells': 8}, POINTER)
    try:
        for name, program in binding['programs'].items():
            scores[name] = measure_program_prefix(actor, program, edited, grade_provider=grade, visible_prefix=keys)
            immutable_json(out / (name + '_measurement.json'), scores[name])
        originals_scores = {row['source']: row['native_task_utilities'] for row in
                            read(scope / 'measured_libraries/MAUD.json')['measurement']['source_rows']}
        regressions = []
        exact_counts = dict.fromkeys(scores, 0)
        for base, after in zip(scores['incumbent']['source_rows'], scores['candidate']['source_rows'], strict=True):
            source = base['source']
            if source != after['source'] or base['public_sha256'] != after['public_sha256']:
                raise ValueError('Both programs must read the same edited documents')
            for task, base_grade in base['native_task_utilities'].items():
                new_grade = after['native_task_utilities'][task]
                exact_counts['incumbent'] += base_grade == 1
                exact_counts['candidate'] += new_grade == 1
                if originals_scores[source][task] == base_grade == 1 and new_grade != 1:
                    regressions.append({'source': source, 'task': task})
        mean = {name: math.fsum(row['native_utility'] for row in proof['source_rows']) / len(keys)
                for name, proof in scores.items()}
        keep = not regressions and mean['candidate'] >= mean['incumbent']
        result = {'status': 'completed', 'edited_mothers': len(keys), 'edited_tasks': len(keys) * 3,
                  'exact_by_program': exact_counts, 'mean_by_program': mean, 'regressions': regressions,
                  'MAUD_selection_after_edit': 'candidate' if keep else 'incumbent',
                  'source_edits_are_independent_mothers': False,
                  'physical_calls': {name: sum(len(row['physical_call_ids']) for row in proof['source_rows'])
                                     for name, proof in scores.items()}, 'TEST_opened': False}
        immutable_json(out / 'terminal.json', result)
        write_status(out, result, POINTER)
        print(json.dumps({**result, 'regressions': len(regressions)}), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'error_type': type(error).__name__}, POINTER)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
