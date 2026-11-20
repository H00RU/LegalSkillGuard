"""Give matched copy readers the same certified mention roles and governors."""

import json
import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_copy_action_train as measured
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces import cni_copy_mention_roles as roles
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_copy_mention_roles'
POINTER = HANDOFF / f'{STAGE}_current.json'
common = measured.prior
archive, legacy, CNI, TASK = common.archive, common.legacy, common.CNI, common.TASK


def proof(source):
    view = common.view_for(source)
    return roles.compile_mentions(legacy.span_inventory(view), legacy.source_groups(view), legacy.literal)


def project(native, certified):
    revised = roles.project({'answer': native['answer'], 'evidence': native['evidence_sentence_ids']}, certified)
    return {**native, 'answer': revised['answer'], 'evidence_sentence_ids': revised['evidence']}


class CopyMentionActor:
    def __init__(self, parent, proofs):
        self.parent = parent
        self.proofs = proofs

    def __call__(self, source, library, purpose):
        result = self.parent(source, library, purpose)
        if (source['dataset'] != CNI or source['project_split'] != 'dev' or library['batch'] != 8
                or purpose != 'skill_dev' or not (proof := self.proofs.get(source['key']))):
            return result
        native = result['native']
        return {**result, 'native': {**native, TASK: project(native[TASK], proof)}}


def matched_reads(db, folder, binding, terminal, grade, phases, prompts, baseline, certified):
    path = folder / 'sealed_predictions.json'
    if sha(path) != terminal['predictions_sha256'] or digest(prompts) != binding['wire_sha256']:
        raise ValueError('Keep the actual matched reader executions and original source')
    original = read(path)
    reader = measured.FrozenExecutor(None, folder, binding['executor'])
    requests, patched = set(), {}
    for phase, bank in original.items():
        cases = phases[phase]
        for key, case in cases.items():
            for name in measured.scope.ROLES:
                identity = f'{measured.STAGE}-{folder.name[:12]}:{digest(key)}:{name}'
                source, status, blob = db.execute('select source,status,result from calls where id=?', (identity,)).fetchone()
                physical = json.loads(blob)
                request = read(ROOT / physical['artifact_directory'] / 'request.json')['payload']
                messages, schema = prompts[key][name]
                decoded, error = measured.scope.decode(case['public'], name, schema, physical)
                if (source != key or status != 'completed' or
                        request != reader.payload(messages=messages, thinking=False, schema=schema) or
                        error or decoded != bank[name][key]):
                    raise ValueError('The paid wire, source or readout differs from the frozen pair')
                requests.add(identity)
        if any(bank[arm][key] != value for arm, old in baseline.items() for key, value in old.items() if key in cases):
            raise ValueError('Keep the exact archived reference readers')
        patched[phase] = {arm: {key: roles.project(row, certified[key]) for key, row in records.items()}
                          for arm, records in bank.items()}
    if len(requests) != terminal['new_executor_requests'] or sha(grade) != binding['TRAIN_grade_sha256']:
        raise ValueError('Replay precisely the settled original TRAIN requests')
    return original, patched, requests


def dev_replay(db, dev, originals, actor, certified, previous):
    parent_state = read(HANDOFF / 'run_state.json')['revision6_cni_copy_approval']
    p = read(common.POINTER)
    folder = ROOT / p['artifact_root']
    terminal = verify(read(folder / 'terminal.json'), 'terminal_sha256')
    path = folder / 'sealed_predictions.json'
    if (folder.name != parent_state['binding_sha256'] or terminal['terminal_sha256'] != p['terminal_sha256']
            or sha(path) != terminal['predictions_sha256'] or terminal['TEST_opened']):
        raise ValueError('Keep the last released fixed DEV copy judgments')
    historical = read(path)['dev']
    reads, banks, complete = {}, {}, {}
    replay = CopyMentionActor(actor, certified)
    for arm, (directory, seal, cell) in originals.items():
        bank = {'before': {}, 'after': {}}
        complete[arm] = {}
        library = {'arm': arm, 'batch': 8}
        for key, source in dev.items():
            before = actor(source, library, 'skill_dev')['native']
            result = before[TASK]
            if result != historical[arm]['after'][key]:
                raise ValueError('Reproduce all original copy-approval projections')
            revised = replay(source, library, 'skill_dev')['native']
            if any(row != revised[task] for task, row in before.items() if task != TASK):
                raise ValueError('Keep every other hypothesis in the cumulative reader')
            complete[arm][key] = revised
            updated = revised[TASK]
            bank['before'][key], bank['after'][key] = result, updated
            if result != updated:
                original = read(directory / 'predictions' / f'{digest(key)}.json')
                if (digest(original) != seal['predictions_sha256'][key]
                        or original['public_source_sha256'] != digest(source)
                        or original['library_sha256'] != cell['libraries'][CNI]):
                    raise ValueError('Use the exact original fixed DEV inputs')
                archive.checked_result(db, source, original['result'], reads, dev=True)
        banks[arm] = bank
    if previous != terminal['terminal_sha256']:
        raise ValueError('Use the released cumulative source state')
    return banks, complete, reads


def run():
    folder, spec, train_grade, phases, prompts, baseline = measured.prepare()
    current = read(measured.POINTER)
    end = verify(read(folder / 'terminal.json'), 'terminal_sha256')
    if (ROOT / current['artifact_root'] != folder or current['terminal_sha256'] != end['terminal_sha256']
            or end['TEST_opened']):
        raise ValueError('Preserve the settled copy-action experiment')
    train, _, tracked_grade, _ = archive.collect(*archive.archive_context(), 'train')
    actor, dev, originals, study, _ = common.prior.prepare()
    if (len(train), len(dev), len(originals)) != (24, 16, 5) or sha(tracked_grade) != sha(train_grade):
        raise ValueError('Preserve complete original TRAIN and fixed DEV')
    certified = {split: {key: proof(source) for key, source in sources.items()}
                 for split, sources in (('TRAIN', train), ('DEV', dev))}
    released_copy = common.CopyApprovalActor(actor, {key: p for key, source in dev.items()
                                                    if (p := common.source_proof(source))})
    old_copy_terminal = read(common.POINTER)['terminal_sha256']
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger.get('reserved') or read(HANDOFF / 'run_state.json')['active_tasks']:
            raise ValueError('Compare only after previous runs have ended')
        old, new, active = matched_reads(db, folder, spec, end, train_grade, phases, prompts, baseline, certified['TRAIN'])
        fixed, complete, dev_reads = dev_replay(db, dev, originals, released_copy, certified['DEV'], old_copy_terminal)
        if active & set(dev_reads):
            raise ValueError('Keep actual scoped TRAIN independent from original fixed DEV')

    files = (__file__, roles.__file__, measured.__file__, common.__file__, legacy.__file__)
    dev_relative = study['grading_paths'][CNI]
    dev_grade = ROOT / dev_relative
    grade_sha = study['grading_file_sha256'][dev_relative]
    if 'dev' not in dev_grade.parts or sha(dev_grade) != grade_sha:
        raise ValueError('Use original DEV without reading TEST references')
    lock = {
        'stage': STAGE, 'TEST_opened': False, 'original_action_terminal': end['terminal_sha256'],
        'original_copy_approval_terminal': old_copy_terminal,
        'source_roles_sha256': digest(certified), 'train_grade_sha256': sha(train_grade), 'dev_grade_sha256': grade_sha,
        'physical_reads_sha256': {'TRAIN': digest(sorted(active)), 'DEV': digest(sorted(dev_reads))},
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in files},
        'design': 'Retrospective common-rule replay of the fixed TRAIN readers, and exploratory five-arm fixed DEV.',
    }
    out = BASE / STAGE / digest(lock)
    immutable_json(out / 'binding.json', lock)
    snapshot(out, lock['source_sha256'])
    immutable_json(out / 'source_roles.json', certified)
    tag = immutable_json(out / 'sealed_predictions.json', {'TRAIN': new, 'DEV': fixed, 'cumulative_DEV': complete})
    labels = {'TRAIN': read(train_grade), 'DEV': read(dev_grade)}
    scopes = {split: {
        'mothers': len(rows),
        'resolved_absent': sum(rule.get('complete_non_creation', False) for rule in rows.values()),
        'resolved_absent_reference_conflicts': sum(rule.get('complete_non_creation', False) and
            labels[split][key][TASK]['answer'] != 'NotMentioned' for key, rule in rows.items()),
        'governed_mothers': sum(bool(rule.get('governors')) for rule in rows.values()),
        'added_role_mothers': sum(bool(rule.get('added_roles')) for rule in rows.values()),
    } for split, rows in certified.items()}
    training = {mode: {phase: measured.score(phases[phase], bank, labels['TRAIN']) for phase, bank in arms.items()}
                for mode, arms in (('before', old), ('shared_roles', new))}
    if digest(training['before']) != digest(end['comparison']):
        raise ValueError('Require exact original matched TRAIN scores before the source change')
    development = {arm: common.score(bank, dev, labels['DEV']) for arm, bank in fixed.items()}
    shared = (all(not row['resolved_absent_reference_conflicts'] for row in scopes.values()) and
              not any(row['classification_regressions'] or row['evidence_regressions'] for row in development.values())
              and any(row['correct'][1] > row['correct'][0] for row in development.values()))
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'source_scope': scopes, 'matched_TRAIN_replay': training, 'fixed_DEV': development,
        'full_fixed_DEV': common.prior.scores(complete, dev, labels['DEV']),
        'supports_shared_DEV_projection': shared,
        'supports_expansion': 'forward' in new and measured.favorable(training['shared_roles']['forward'], forward=True),
        'reused_physical_requests': {'TRAIN': len(active), 'DEV': len(dev_reads)},
        'TEST_opened': False, 'new_executor_requests': 0, 'new_teacher_requests': 0, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
