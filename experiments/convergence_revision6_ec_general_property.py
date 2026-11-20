"""Isolate source-supported EC gains of the B2 Oregon and B6 Illinois proposals."""

from collections import Counter
from pathlib import Path
import re
import sqlite3
from statistics import mean

from experiments import convergence_revision5_oe_category_scope as archive
from experiments import convergence_revision5_oe_illinois_asset_attribution as illinois
from experiments import convergence_revision6_candidate_asset_binding as ev
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_ec_inventory import bind_classification
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_ec_general_property'
POINTER = HANDOFF / 'revision6_ec_general_property_current.json'
OREGON = 'Or. Rev. Stat. § 18.345(1)(p)'
ILLINOIS = illinois.CITATION
TEXT = {
    OREGON: "The debtor's interest, not to exceed $400 in value, in any personal property.",
    ILLINOIS: illinois.RULE,
}
# Keep Oregon's personal-property predicate distinct from whether a particular
# item is used personally. Only use familiar tangible property categories.
TANGIBLE = re.compile(
    r'\b(?:crossover|SUV|sedan|truck|outback|ironing board|washer-dryer|hearing aids|'
    r'bracelet|ring|earrings|necklace|nightstands?|camisole|jacket|slacks|scarf|'
    r'fountain|flute|shoes|suit|puffer|shawl|cabinets?|chair|table|washer)\b', re.I,
)
FIT = {2: OREGON, 6: ILLINOIS}
ROLES = ('entering', 'candidate')
formal = ev.formal


def source_claims(view, citation):
    text = view['public']['original_input']
    scope = supplied_jurisdiction_scope(text)
    if view['id'] != 'EC' or not scope or citation not in scope['citations']:
        return set()
    laws = text.partition('\nStatutes:\n')[2].partition('\nSolved Reasoning Steps:\n')[0].strip()
    blocks = [text.partition('\n')[::2] for text in laws.split('\n\n')]
    if [body for name, body in blocks if name == citation] != [TEXT[citation]]:
        return set()
    try:
        _, assets, _ = title_inventory(text)
    except ValueError:
        return set()
    return {a['description'] for a in assets.values()
            if a['filing_interest_established'] is True
            and archive.cents(a['amount_quote']) > 0
            and (citation == ILLINOIS or TANGIBLE.search(a['description']))}


def common_scope(view, answer):
    if not isinstance(answer, dict):
        return answer
    scope = supplied_jurisdiction_scope(view['public']['original_input'])
    if scope is None:
        raise ValueError('Original eligible jurisdiction must be known')
    allowed = set(scope['citations'])
    return {name: [law for law in laws if law in allowed]
            for name, laws in bind_classification(view, answer).items()}


def assertion(answer, name, citation):
    return citation in (answer or {}).get(name, [])


def project(entering, candidate, support, citation):
    if not isinstance(entering, dict):
        return entering, entering
    scoped, direct = dict(entering), dict(entering)
    for name in sorted(support):
        if assertion(entering, name, citation):
            continue
        direct[name] = [*entering.get(name, []), citation]
        if assertion(candidate, name, citation):
            scoped[name] = direct[name]
    return scoped, direct


def view_for(source):
    return next(v for v in source['views'] if v['id'] == 'EC')


def native(db, source, saved, program, verified):
    (part,) = (x for x in saved['result']['reads'] if set(x['native']) == {'EC'})
    if part['execution']['program_sha256'] != program:
        raise ValueError('An EC observation must use the exact candidate or entering program')
    answer = archive.ec_read(db, source, saved, verified, 'train')
    return common_scope(view_for(source), answer)


def measure_fit(db):
    results, views, programs, stages, refs, paid = {}, {}, {}, {}, set(), set()
    for batch, citation in FIT.items():
        fit, spec, end = archive.bound_stage(formal.pointer(batch))
        decisions = read(fit / 'matched_decisions.json')
        patch = read(fit / 'candidates' / formal.ORDINARY / formal.OE / 'measurements.json')
        ck = ROOT / spec['checkpoint_root']
        study = read(ck / 'binding.json')
        batches = formal.load_roster(study)
        journal = ev.archive.TrainingJournal(ck, study, batches)
        prior = digest(journal.library(formal.M2, batch - 1)['programs'][formal.OE])
        proposed = digest(patch['candidate'])
        record = decisions['relation'][formal.OE]
        if (end['batch'] != batch or digest(decisions) != end['matched_decisions_sha256']
                or proposed != record['matched_proposal_sha256']
                or digest(patch['predictions']) != decisions['teacher'][formal.ORDINARY][formal.OE]['predictions_sha256']):
            raise ValueError('The original training proposal or observations changed')
        refs.add(ev.grades_ref(read(ROOT / spec['observations_root'] / 'binding.json')))
        stages[str(batch)] = sha(fit / 'terminal.json')
        cohort = [s for s in batches[batch - 1] if s['dataset'] == formal.OE and s['project_split'] == 'train']
        if len(cohort) != 4:
            raise ValueError('Keep the original four training mothers for each proposal')
        observed = journal._observations(formal.M2, batch)
        routed, applicability = {}, {}
        for index, source in enumerate(cohort):
            key = source['key']
            view = view_for(source)
            saved = read(journal.directory(formal.M2, batch) / 'predictions' / (digest(key) + '.json'))
            if digest(saved) != observed['predictions'][key]:
                raise ValueError('Use the original entering EC response')
            base = native(db, source, saved, prior, paid)
            new = native(db, source, {'result': patch['predictions'][key]}, proposed, paid)
            support = source_claims(view, citation)
            scoped, direct = project(base, new, support, citation)
            views[key] = view
            routed[key] = {'entering': base, 'whole_candidate': new,
                           'citation_scoped_candidate': scoped, 'same_information_direct': direct}
            if support:
                applicability[key] = {'position': index, 'proofs': sorted(support),
                                      'gained_assertions': sorted(name for name in support
                                                                 if assertion(scoped, name, citation)
                                                                 and not assertion(base, name, citation))}
        positive = sum(len(x['gained_assertions']) for x in applicability.values())
        if not positive:
            raise ValueError('The archived candidate must have an exact supported new eligibility assertion')
        later = [(n, view_for(s)) for n, group in enumerate(batches, 1) if n > batch
                 for s in group if s['dataset'] == formal.OE and s['project_split'] == 'train']
        covered = [(n, view) for n, view in later if source_claims(view, citation)]
        forwarded = sum(
            proposed in {digest(journal.library(arm, n - 1)['programs'][formal.OE])
                         for arm in (formal.M2, formal.ORDINARY)}
            for n, _ in covered
        )
        results[str(batch)] = {'predictions': routed, 'proofs': applicability, 'citation': citation,
                               'later_TRAIN_covered_mothers': len(covered),
                               'later_TRAIN_covered_mothers_with_exact_proposal': forwarded,
                               'historical_whole_M2_status': record['status']}
        programs[str(batch)] = [prior, proposed]
    grade, = refs
    if len(paid) != 16:
        raise ValueError('Exactly two original classification responses per fitted mother')
    return results, views, grade, stages, programs, len(paid)


def score(rows, views, labels):
    modes = tuple(next(iter(rows.values())))
    scored = {m: [] for m in modes}
    for key, bank in rows.items():
        for arm, output in bank.items():
            value = grade_view(formal.OE, views[key], labels[key]['EC'], output)['grade']
            if value is None:
                raise ValueError('A matched comparison needs an original native score')
            scored[arm].append({'source': key, 'view': 'EC', 'grade': value})
    return {'F1': {m: mean(x['grade'] for x in a) for m,a in scored.items()},
            'source_effect': {arm: paired_source_effect(scored['entering'], grades)
                              for arm, grades in scored.items() if arm != 'entering'}}


def run():
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        fit, train_views, grade, stages, programs, verified = measure_fit(db)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('Reconcile the current research experiment before replay')
    dev_views, archived, dev_grade, metadata = archive.full_archive('dev')
    # Archived DEV roles are kept separate. Neither runs the B2/B6 proposal.
    dev = {}
    counts = Counter()
    for key, viewset in dev_views.items():
        view = viewset['EC']
        proofs = {law: source_claims(view, law) for law in TEXT}
        for law,names in proofs.items():
            counts[law] += bool(names)
        dev[key] = {}
        for arm, rows in archived.items():
            base = common_scope(view, rows[key]['EC'])
            direct = base
            for law, names in proofs.items():
                _, direct = project(direct, {}, names, law)
            dev[key][arm] = {'entering': base, 'same_information_direct': direct}
    if len(dev) != 16:
        raise ValueError('Use the original complete sixteen-source OpenExempt DEV separation')

    fit_metadata = {batch: {k: v for k, v in record.items() if k != 'predictions'} for batch, record in fit.items()}
    spec = {
        'stage': 'revision6_ec_general_property', 'TRAIN_stage_terminal_sha256': stages, 'programs': programs,
        'train_proofs_sha256': digest(fit_metadata), 'TRAIN_grade_sha256': grade[1], 'DEV_grade_sha256': sha(dev_grade),
        'DEV_archives': metadata['EV_archive_terminal_sha256'], 'TEST_opened': False,
        'source_sha256': {str(Path(name).relative_to(ROOT)): sha(Path(name)) for name in (
            __file__, archive.__file__, illinois.__file__, ev.__file__,
        )},
    }
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    for name, h in spec['source_sha256'].items():
        snapshot = out / 'source_snapshot' / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            with snapshot.open('xb') as file:
                file.write((ROOT / name).read_bytes())
        if sha(snapshot) != h:
            raise ValueError('The archived comparison version changed')
    pred = immutable_json(out / 'sealed_predictions.json', {'fit': fit, 'dev': dev})
    grade_path = ROOT / grade[0]
    if 'train' not in grade_path.parts or sha(grade_path) != grade[1] or 'dev' not in dev_grade.parts:
        raise ValueError('Require exact original native annotations only after sealing')
    train_labels, dev_labels = read(grade_path), read(dev_grade)
    training = {batch: {**fit_metadata[batch], **score(row['predictions'], train_views, train_labels)}
                for batch, row in fit.items()}
    native_dev = {arm: score({key: v[arm] for key, v in dev.items()},
                             {key: views['EC'] for key, views in dev_views.items()}, dev_labels)
                  for arm in archived}
    result = sealed({
        'status': 'settled_revision6_ec_general_property', 'binding_sha256': out.name,
        'TRAIN': training, 'DEV_citations_covered_mothers': dict(counts), 'fixed_DEV_shared_control': native_dev,
        'original_EC_requests_verified': {'train': verified, 'dev': metadata['ec_physical']},
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'predictions_sha256': pred,
        'ledger': ledger, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
