"""Apply the same verified source scope to all archived MAUD joint-scope readers."""

import json
from pathlib import Path
import re
import sqlite3
from zipfile import ZipFile

from experiments import convergence_revision6_maud_branch_preamble as branch
from experiments import convergence_revision6_maud_joint_scope as joint
from experiments import convergence_revision6_maud_selective_import as selective
from experiments import convergence_revision6_maud_subsection_readback as subsection
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_maud_joint_scope_controls'
POINTER = HANDOFF / f'{STAGE}_current.json'
release = branch.release
fit = joint.fit
archive = release.parallel.parent_views
ORDINARY, NEGATIVE = fit.TASKS
CONTROLS = ('fixed', 'direct')


def public_proofs(source):
    """Collect established determinate outputs without treating missing cues as negatives."""
    fixed = {}
    if match := branch.proof(source):
        fixed['separate_sibling_preambles'] = match['answer']
    if subsection.proof(source):
        fixed['express_subsection_proviso'] = {ORDINARY: 'Yes', NEGATIVE: 'No'}
    if match := release.proof(source):
        fixed['section_reference'] = dict.fromkeys(match['targets'], 'Yes')
    if (match := release.parallel.proof(source)) and match['scope'] in release.parallel.ATTACHED:
        fixed['aligned_omission'] = {NEGATIVE: 'Yes'}
    if (match := selective.proof(source)) and match['negative_import_includes_pandemic_condition']:
        fixed['explicit_numbered_import'] = {NEGATIVE: 'Yes'}
    previous = release.parallel.previous
    attached = previous.attachment_proof(previous.view_for(source)['public'])
    if attached['attached_negative_exception']:
        fixed['negative_preamble_exception'] = {NEGATIVE: 'Yes'}
    elif attached['separate_headers']:
        fixed['separate_governing_headers'] = {NEGATIVE: 'No'}
    return fixed


def resolved(proofs):
    values = {}
    for family in fit.TASKS:
        known = {output[family] for output in proofs.values() if family in output}
        if len(known) > 1:
            raise ValueError('Conflicting source controls require source adjudication before replay')
        if known:
            values[family] = known.pop()
    return values


def restore(config, cases, grade):
    original, _, previous, _, count = joint.restore_previous(cases, config, grade)
    root, binding, stored = branch.archive.bound_result(joint)
    wire = read(root / 'wire_tasks.json')
    bank = read(root / 'sealed_predictions.json')
    baseline = {name: bank[route] for name, route in
                (('synthesized', 'previous_synthesized'), ('fixed', 'fixed'), ('direct', 'direct'))}
    if previous != binding['prior_terminal'] or digest(wire) != binding['wire_sha256'] or baseline != original:
        raise ValueError('Keep the unchanged controls and the actual joint codebook')
    executor = fit.FrozenExecutor(None, root, config)
    receipts = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for key, case in cases.items():
            identity = f'revision6-M1-maud-joint-scope-{root.name[:12]}:{digest(key)}'
            physical_wire(db, set(cases), identity, key)
            encoded, = db.execute('select result from calls where id=?', (identity,)).fetchone()
            result = json.loads(encoded)
            request = read(Path(result['artifact_directory']) / 'request.json')['payload']
            messages, schema = wire[key]
            decoded, error = joint.decode(schema, result)
            if (joint.query(case) != (messages, schema)
                    or request != executor.payload(messages=messages, thinking=False, schema=schema)
                    or decoded != bank['synthesized'][key] or error is not None):
                raise ValueError('Use the exact original successful joint-scope responses')
            receipts[key] = {'request_sha256': digest(request), 'response_sha256': digest(result['content'])}
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or count != 30 or len(receipts) != 10:
        raise ValueError('Require 40 original physical responses and no live dispatch')
    return bank, stored['terminal_sha256'], receipts, ledger


def differences(cases, bank, labels):
    outcomes = {name: joint.outcomes(cases, row, labels) for name, row in bank.items()}
    native = {name: {
        family: sum(row['grade'] for row in rows if row['view'] == task)
        for family, task in fit.TASKS.items()
    } for name, rows in outcomes.items()}
    pairs = {name: paired_source_effect(rows, outcomes['synthesized'])
             for name, rows in outcomes.items() if name != 'synthesized'}
    return {'correct': native, 'paired_joint_scope': pairs}


def verify_parent(source, case, parent_zip):
    """Check the original excerpt supports the proposed attribution at its governing duty."""
    from hashlib import sha256

    raw = parent_zip.read(f'data/contracts/{source["parent_id"]}.txt')
    if sha256(raw).hexdigest() != source['fulltext_raw_sha256']:
        raise ValueError('Only use the exact original TRAIN parent')
    text = archive.unpage(raw.decode('utf-8-sig'))
    public = case['public']
    excerpts = {family: archive.unpage(public['original_excerpts'][name])
                for family, name in public['task_excerpts'].items()}
    pos = case['position']
    if pos == [1, 2]:
        ordinary = excerpts[ORDINARY]
        neg = excerpts[NEGATIVE]
        if text.count(ordinary) != 1 or text.count(neg) != 1:
            return None
        after = text.split(ordinary, 1)[1]
        qualifier_first = after.startswith('.') and after.index(neg) >= 1
        cue_negative_only = bool(fit.CUE.search(neg)) and not fit.CUE.search(after[:after.index(neg)])
        if qualifier_first and cue_negative_only:
            return {'position': pos, 'supported': {ORDINARY: 'No', NEGATIVE: 'Yes'},
                    'basis': 'The ordinary-course duty ends before the later negative preamble. '
                             'The pandemic condition governs the later expressly stated prohibition.'}
    if pos == [2, 1]:
        ordinary = excerpts[ORDINARY].rpartition('5.1 Affirmative Obligations.')[2].strip()
        negative = excerpts[NEGATIVE]
        if not ordinary or text.count(ordinary) != 1 or text.count(negative) != 1:
            return None
        if (negative.startswith('5.2 Forbearance Covenants.') and negative.endswith(':')
                and re.search(r'\(d\) for any actions taken reasonably and in good faith to respond to COVID', ordinary)
                and 'as contemplated by Section 5.2;' in ordinary and not re.search(r'\b5\.1\b', negative)
                and not fit.CUE.search(negative)):
            return {'position': pos, 'supported': {ORDINARY: 'Yes', NEGATIVE: 'No'},
                    'basis': 'The affirmative section states the response exception and cross-references 5.2. '
                             'The separately printed forbearance preamble has no reciprocal reference or pandemic exception.'}
    return None


def run():
    config, cases, _, grade = fit.materials()
    bank, parent, receipts, ledger = restore(config, cases, grade)
    _, _, roster = fit.previous.archive_context()
    all_train = {s['key']: s for batch in roster for s in batch
                 if s['dataset'] == fit.MAUD and s['project_split'] == 'train'}
    _, dev_roster, _, _, dev_terminal = release.base_actor()
    fixed = {s['key']: s for s in dev_roster if s['dataset'] == fit.MAUD and s['project_split'] == 'dev'}
    if len(all_train) != 24 or len(fixed) != 16 or 'train' not in grade.parts or not cases.keys() <= all_train.keys():
        raise ValueError('Use the full original public coverage inventories and only TRAIN grades')
    evidence = {split: {key: public_proofs(source) for key, source in cohort.items()}
                for split, cohort in (('TRAIN', all_train), ('DEV', fixed))}
    known = {key: resolved(evidence['TRAIN'][key]) for key in cases}
    revised = {name: {key: {family: pred if family not in known[key] else
                           {'answer': known[key][family], 'focus': None} for family, pred in answer.items()}
                     for key, answer in outputs.items()} for name, outputs in bank.items()}
    candidate_positions = {tuple(case['position']): key for key, case in cases.items()}
    with ZipFile(archive.ARCHIVE) as parents:
        attributions = {key: proof for pos in ((1, 2), (2, 1))
                        if (key := candidate_positions.get(pos)) is not None
                        and (proof := verify_parent(all_train[key], cases[key], parents)) is not None}
    paths = (__file__, joint.__file__, branch.__file__, subsection.__file__, selective.__file__,
             release.__file__, release.parallel.__file__, release.parallel.previous.__file__,
             archive.__file__)
    binding = {
        'stage': STAGE, 'partition': 'TRAIN and public DEV coverage', 'prior_joint_scope_terminal': parent,
        'joint_physical_receipts_sha256': digest(receipts), 'common_evidence_sha256': digest(evidence),
        'TRAIN_grade_sha256': sha(grade), 'DEV_source_terminal': dev_terminal,
        'TRAIN_parent_attribution_sha256': digest(attributions), 'TEST_opened': False,
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in paths},
        'parent_only_used_for_attribution': True,
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    fit.snapshot(out, binding['source_sha256'])
    immutable_json(out / 'source_proofs.json', evidence)
    immutable_json(out / 'parent_attribution.json', attributions)
    pred = immutable_json(out / 'sealed_predictions.json', revised)
    labels = read(grade)
    conflicts = [{'position': cases[key]['position'], 'family': family}
                 for key, answers in known.items() for family, result in answers.items()
                 if labels[key][fit.TASKS[family]]['answer'] != result]
    if conflicts:
        raise ValueError('A common scope proof conflicted with an original TRAIN reference')
    metrics = differences(cases, revised, labels)
    residual = []
    for name in CONTROLS:
        for key, case in cases.items():
            for family, task in fit.TASKS.items():
                expected = labels[key][task]['answer']
                left, right = (revised[arm][key][family]['answer'] == expected for arm in (name, 'synthesized'))
                if left != right:
                    proof = attributions.get(key, {}).get('supported', {}).get(family)
                    residual.append({'control': name, 'position': case['position'], 'task': family,
                                     'joint_minus_control': int(right) - int(left),
                                     'parent_supports_reference': proof == expected})
    t = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': pred,
        'original': differences(cases, bank, labels), 'same_information': metrics,
        'matched_mothers': len(cases), 'matched_train_proof_coverage': sum(bool(r) for r in known.values()),
        'public_coverage': {split: [sum(bool(row) for row in cohort.values()), len(cohort)]
                            for split, cohort in evidence.items()},
        'residual_classification_differences': residual, 'parent_attribution': list(attributions.values()),
        'original_physical_reads': 40, 'new_executor_requests': 0, 'new_teacher_requests': 0,
        'TEST_opened': False, 'DEV_grades_used': False, 'ledger': ledger,
        'supports_expanded_validation': all(
            metrics['paired_joint_scope'][name]['paired_source_bootstrap_95'][0] > 0 for name in CONTROLS
        ),
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', t)
    write_status(out, {'status': t['status'], 'terminal_sha256': t['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
