"""Apply one independently verified sibling-preamble check to all MAUD readers."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_agreement_disclosure_release as archive
from experiments import convergence_revision6_maud_section_reference as release
from experiments import convergence_revision6_maud_subsection_readback as previous
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import maud_branch_preamble as preamble
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_maud_branch_preamble'
POINTER = HANDOFF / f'{STAGE}_current.json'
fit = previous.exp.fit


def proof(source):
    excerpts = {v['id']: v['public']['source_text'] for v in source['views']}
    return preamble.attachment(*(excerpts[task] for task in fit.TASKS.values()))


def apply(native, witness):
    if witness is None:
        return native
    return {
        role: row if row['answer'] == witness['answer'][role] else
        {**row, 'answer': witness['answer'][role], 'focus': None}
        for role, row in native.items()
    }


def run():
    _, cases, _, grade, _ = previous.exp.materials()
    old, binding, terminal = archive.bound_result(previous)
    _, _, original = archive.bound_result(previous.exp)
    if (binding['previous_TRAIN_terminal'] != original['terminal_sha256']
            or sha(grade) != binding['TRAIN_grade_sha256'] or 'train' not in grade.parts):
        raise ValueError('Continue the verified subsection correction and exact original TRAIN grades')
    before = read(old / 'sealed_predictions.json')
    if set(before) != set(fit.ROLES) or any(set(bank) != set(cases) for bank in before.values()):
        raise ValueError('Keep the same three measured arms and all nine source mothers')

    _, _, batches = fit.previous.archive_context()
    train = {source['key']: ([number, index], source) for number, batch in enumerate(batches, 1)
             for index, source in enumerate(s for s in batch if s['dataset'] == fit.MAUD)}
    _, cohort, originals, _, base = release.base_actor()
    dev = {source['key']: source for source in cohort if source['dataset'] == fit.MAUD
           and source['project_split'] == 'dev'}
    if (len(train) != 24 or len(dev) != 16 or len(originals) != 5
            or any(source['project_split'] != 'train' for _, source in train.values())):
        raise ValueError('Use the full original MAUD TRAIN and fixed five-arm DEV sources')
    train_proofs = {key: proof(source) for key, (_, source) in train.items()}
    dev_proofs = {key: proof(source) for key, source in dev.items()}
    if any(dev_proofs.values()):
        raise ValueError('A covered fixed DEV source requires a separately bound native replay')
    after = {role: {key: apply(row, train_proofs[key]) for key, row in bank.items()}
             for role, bank in before.items()}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('Settle the last model run before the archive replay')

    hashes = {str(Path(path).relative_to(ROOT)): sha(Path(path)) for path in (
        __file__, preamble.__file__, preamble.section.__file__, preamble.anchors.__file__, previous.__file__,
    )}
    spec = {
        'stage': STAGE, 'TRAIN_grade_sha256': sha(grade), 'TRAIN_sibling_proofs_sha256': digest(train_proofs),
        'fixed_DEV_coverage_sha256': digest(dev_proofs), 'fixed_DEV_preexisting_actor': base,
        'previous_TRAIN_terminal': terminal['terminal_sha256'], 'source_sha256': hashes, 'TEST_opened': False,
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    fit.snapshot(out, hashes)
    immutable_json(out / 'source_proofs.json', {'TRAIN': train_proofs, 'DEV': dev_proofs})
    pred_hash = immutable_json(out / 'sealed_predictions.json', after)

    labels = read(grade)
    hits = {k: train[k][0] for k, found in train_proofs.items() if found is not None}
    for key in hits:
        if train_proofs[key]['answer'] != {family: labels[key][task]['answer']
                                          for family, task in fit.TASKS.items()}:
            raise ValueError('Resolve a source-proof disagreement before accepting the common check')
    scores, effects = fit.score(cases, after, labels)
    corrected = {role: {
        family: sum(before[role][key][family]['answer'] != row[family]['answer'] for key, row in bank.items())
        for family in fit.TASKS
    } for role, bank in after.items()}
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': pred_hash,
        'TRAIN_mothers': len(train), 'TRAIN_scope_proofs': len(hits), 'TRAIN_scope_positions': sorted(hits.values()),
        'matched_TRAIN_mothers': len(cases), 'matched_TRAIN_scope_proofs': len(cases.keys() & hits.keys()),
        'before': terminal['shared_source_rule_scores'], 'after': scores, 'paired_M1_effects': effects,
        'changed_native_answers_by_arm': corrected, 'fixed_DEV_mothers': len(dev), 'fixed_DEV_coverage': 0,
        'advance': all(v['paired_source_bootstrap_95'][0] > 0 for v in effects.values()),
        'reused_TRAIN_model_responses': terminal['TRAIN_original_requests_verified'],
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'ledger': ledger, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
