"""Compare same-information M2 selections before buying missing forward reads."""

import sqlite3
from pathlib import Path

from experiments import convergence_revision6_cni_agreement_disclosure_release as sealed_archive
from experiments import convergence_revision6_oe_residual_acquisition as residual
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_missing_forward_fit'
POINTER = HANDOFF / f'{STAGE}_current.json'


def original_fit(db, batch):
    joint = residual.previous
    archive, formal = joint.archive, joint.FORMAL
    fit, config, terminal = archive.prior.archive.bound_stage(formal.pointer(batch))
    decisions = read(fit / 'matched_decisions.json')
    proposal = read(fit / 'candidates' / formal.ORDINARY / joint.OE / 'measurements.json')
    gate = decisions['teacher'][formal.ORDINARY][joint.OE]
    if (digest(decisions) != terminal['matched_decisions_sha256'] or terminal['batch'] != batch
            or digest(proposal['candidate']) != decisions['relation'][joint.OE]['matched_proposal_sha256']
            or digest(proposal['predictions']) != gate['predictions_sha256']):
        raise ValueError('Verify the original measured proposal and its fit receipt')
    root = ROOT / config['checkpoint_root']
    study = read(root / 'binding.json')
    roster = formal.load_roster(study)
    journal = archive.exact.TrainingJournal(root, study, roster)
    programs = (digest(journal.library(formal.M2, batch - 1)['programs'][joint.OE]), digest(proposal['candidate']))
    carriers = set()
    for arm in ConvergenceEvaluation.arms:
        library = journal.library(arm, batch)
        if library.get('schema_proposals', {}).get(joint.OE) is None:
            carriers.add(digest(library['programs'][joint.OE]))
    if programs[0] == programs[1] or programs[0] not in carriers or programs[1] in carriers:
        raise ValueError('This preflight covers omitted forward proposals with an entering reader')
    sources = [source for source in roster[batch - 1] if source['dataset'] == joint.OE]
    if len(sources) != 4 or any(source['project_split'] != 'train' for source in sources):
        raise ValueError('Use every original source of the omitted TRAIN batch')

    cases, physical = {}, set()
    for position, source in enumerate(sources):
        key = source['key']
        original = (archive.raw_prediction(journal, formal.M2, batch, key), proposal['predictions'][key])
        ev, ev_ids = archive.read_matched(db, source, original, programs)
        ec = [joint.matching_ec(db, source, record, program) for record, program in zip(original, programs, strict=True)]
        if ec[0][2] != ec[1][2]:
            raise ValueError('The physical classification requests must use the same public text and transport')
        physical.update((*ev_ids, ec[0][1], ec[1][1]))
        cases[key] = residual.controlled_case({
            'position': position, 'views': {view['id']: view for view in source['views']},
            'answers': {role: {'EC': receipt[0], 'EV': ev['answers'][role]}
                        for role, receipt in zip(archive.PROGRAMS, ec, strict=True)},
        })
    grade, expected = archive.assets.grades_ref(read(ROOT / config['observations_root'] / 'binding.json'))
    if len(physical) != 16 or 'train' not in Path(grade).parts or sha(ROOT / grade) != expected:
        raise ValueError('Use 16 original matched responses and the exact TRAIN grade')
    return cases, physical, (grade, expected), {
        'original_fit_terminal_sha256': sha(fit / 'terminal.json'),
        'programs': dict(zip(archive.PROGRAMS, programs, strict=True)),
        'has_exact_next_batch_execution': {'incumbent': True, 'proposal': False},
    }


def measure(cases, labels):
    joint = residual.previous
    native_gains = residual.fit_native_residuals(cases, labels)
    eligible = residual.eligible_gains(native_gains)
    groups = {
        row['position']: joint.group_evidence(row, True) for row in cases.values()
        if all(answer is not None for native in row['answers'].values() for answer in native.values())
    }
    choices = joint.joint.select(groups, eligible, require_each_port=True)
    diagnostics = {}
    for key, row in cases.items():
        single = {key: {route: joint.joint.route(row['answers'], route) for route in joint.joint.ROUTES}}
        results = joint.scored({key: row}, single, labels)
        diagnostics[row['position']] = {
            task: sum(b['grade'] - a['grade'] for a, b in zip(results['incumbent'], results[route], strict=True)
                      if a['view'] == task)
            for task, route in (('EC', 'EC_only'), ('EV', 'EV_only'))
        }
    return {'native_gain_after_shared_rules': native_gains, 'eligible_native_gain': eligible,
            'per_source_task_f1_difference': diagnostics, 'eligible_groups': groups, 'choices': choices,
            'logical_screen_requests_per_policy': len(joint.PORTS) * len(joint.archive.PROGRAMS) if groups else 0,
            'needs_missing_forward_read_for_selection_contrast':
                choices['candidate_driven']['route'] != choices['chronological']['route']}


def run():
    joint = residual.previous
    _, residual_binding, previous = sealed_archive.bound_result(residual)
    validated = ROOT / read(joint.VALIDATED_POINTER)['artifact_root']
    validated_binding = read(validated / 'binding.json')
    if digest(validated_binding) != validated.name or residual_binding['prior_validated_terminal'] != read(
            validated / 'terminal.json')['terminal_sha256']:
        raise ValueError('Continue the exact selection policy and matched archive')
    exclusions = validated_binding['excluded']
    if set(exclusions.values()) != {'no_matched_exact_next_batch_reader'} or set(exclusions) != {'2', '5'}:
        raise ValueError('Only evaluate the two previously excluded original fits')
    batches, identities, grade_refs, provenance = {}, set(), set(), {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for batch in map(int, sorted(exclusions)):
            samples, physical, grade_ref, attached = original_fit(db, batch)
            batches[batch], provenance[batch] = samples, attached
            if identities & physical:
                raise ValueError('A batch cannot restore another batch’s physical evidence')
            identities.update(physical)
            grade_refs.add(grade_ref)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if len(grade_refs) != 1 or ledger.get('reserved'):
        raise ValueError('The omitted fits must use the settled continuous ledger and one TRAIN reference')
    (grade, expected), = grade_refs
    binding = {
        'stage': STAGE, 'TEST_opened': False, 'partition': 'TRAIN',
        'residual_selection_terminal': previous['terminal_sha256'], 'grade_sha256': expected,
        'requests_sha256': digest(sorted(identities)), 'shared_train_cases_sha256': digest(batches),
        'provenance': provenance,
        'source_sha256': {str(Path(x).relative_to(ROOT)): sha(Path(x)) for x in (
            __file__, residual.__file__, joint.__file__, joint.archive.__file__, joint.joint.__file__,
        )},
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    snapshot(out, binding['source_sha256'])
    labels = read(ROOT / grade)
    fit = {batch: measure(bank, labels) for batch, bank in batches.items()}
    for batch, result in fit.items():
        for policy, choice in result['choices'].items():
            programs = provenance[batch]['programs']
            active = dict(zip(joint.PORTS, (programs[role] for role in joint.joint.ROUTES[choice['route']]), strict=True))
            library = sealed({'batch': batch, 'choice': choice, 'programs': active,
                              'binding_sha256': out.name}, 'snapshot_sha256')
            immutable_json(out / 'TRAIN_batch_libraries' / f'B{batch}' / f'{policy}.json', library)
    fit_hash = immutable_json(out / 'sealed_predictions.json', fit)
    terminal = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': fit_hash,
        'fit_ONLY': fit, 'same_archived_source_pool': True, 'forward_requested': False,
        'reused_fit_responses': len(identities), 'new_executor_requests': 0, 'new_teacher_requests': 0,
        'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
