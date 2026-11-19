"""Evaluate positive cross-citation conflicts on actual archived PA updates."""

import json
import re
import sqlite3
from collections import Counter
from itertools import product
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_oe_assertion_coverage as archive
from experiments import convergence_revision5_oe_paired_forms as paired
from experiments import convergence_revision5_oe_scoped_forms as forms
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_oe_m2_source_placement import direct_title_scope
from legal_skill_guard.paired_interfaces.convergence_ec_inventory import bind_classification
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision5_oe_m2_cross_citation_20261119'
POINTER = HANDOFF / 'revision5_oe_m2_cross_citation_current.json'
TASKS = ('EC', 'EV')
APPAREL = '42 Pa. Cons. Stat. § 8124(a)(1)'
SEWING = '42 Pa. Cons. Stat. § 8124(a)(3)'
CITATIONS = (APPAREL, SEWING)
SCOPE_LINES = {
    '42 Pa. Cons. Stat. § 8124(a)': 'b2e9cfb95c12bc456a7cb1606a726417741a73293c923bde9b0f78f821ac356a',
    APPAREL: 'b9156ea6a006ef28026cf73357a7ad2dcc141e81b91e5ba3f942b0c0ec066fe7',
    SEWING: '6042664c3dd428d35828b1f739327ceecd540fb41003d1ce333ff38a1208dd96',
}
REVIEWED_PRINCIPAL = re.compile(
    r'\b(?:bowl|dress shirt|dishwasher|wireless router|blender|child booster seat|ice maker|windbreaker)\b', re.I)


def witnesses(present, titles):
    """Enumerate one eligible item type and independently scoped view titles."""
    observed = [(task, c) for task in TASKS for c in present[task]]
    domains = [(False, True) if titles[t] is None else (titles[t],) for t in TASKS]
    for kind, ec_title, ev_title in product((None, *CITATIONS), *domains):
        holds = dict(zip(TASKS, (ec_title, ev_title), strict=True))
        if all(holds[task] and c == kind for task, c in observed):
            yield (kind, ec_title, ev_title)


def direct_support(present, titles):
    """The direct comparator receives the same two clauses and title premises."""
    return (len(present['EC'] | present['EV']) <= 1
            and all(not present[t] or titles[t] is not False for t in TASKS))


def positive_citations(task, answer, asset):
    claims = answer.get(asset, [])
    if task == 'EC':
        return set(claims) & set(CITATIONS)
    return {c['citation'] for c in claims if c['citation'] in CITATIONS and c['claim_value'] > 0}


def scope(ec, ev, views):
    public = paired.form_context(ec)
    if public != paired.form_context(ev):
        raise ValueError('The two native views must describe the same principal inventory items')
    if any(len(REVIEWED_PRINCIPAL.findall(name.split(' with ', 1)[0])) != 1 for name in public['assets']):
        raise ValueError('The source-reviewed principal items exclude mixed apparel-and-sewing-machine assets')
    titles = {}
    for case, task in zip((ec, ev), TASKS, strict=True):
        text = views[task]['public']['original_input']
        if text != case['public']['source_text']:
            raise ValueError('The verified PA source audit and measured native case must match')
        statutes = text.partition('\nStatutes:\n')[2].partition('\nSolved Reasoning Steps:\n')[0].splitlines()
        for key, h in SCOPE_LINES.items():
            bound = [line for title, line in zip(statutes, statutes[1:]) if title == key]
            if len(bound) != 1 or digest(bound[0]) != h:
                raise ValueError('The exact apparel and sewing provisions must be supplied in both views')
        _, inventory, _ = title_inventory(text)
        titles[task] = {row['description']: row['filing_interest_established'] for row in inventory.values()}
    return public['assets'], titles


def candidate_b8(db, source, incumbent_sha, incumbent_native):
    run = ROOT / read(pointer(8))['artifact_root']
    stop = read(run / 'terminal.json')
    old = read(run / 'binding.json')
    decisions = read(run / 'matched_decisions.json')
    directory = run / 'candidates' / ORDINARY / OE
    measurements = read(directory / 'measurements.json')
    decision = decisions['teacher'][ORDINARY][OE]
    if (run.name != digest(old) or digest(decisions) != stop['matched_decisions_sha256'] or stop['TEST_opened']
            or decision != read(directory / 'decision.json')
            or digest(measurements['predictions']) != decision['predictions_sha256']
            or digest(measurements['candidate']) != decisions['relation'][OE]['matched_proposal_sha256']):
        raise ValueError('Use the exact candidate measured and selected in the original B8 fit')
    key = source['key']
    before, after = (x['result'] if 'result' in x else x
                     for x in (incumbent_native, measurements['predictions'][key]))
    known = set()
    archive.verify_native(db, source, before, incumbent_sha, known)
    archive.verify_native(db, source, after, digest(measurements['candidate']), known)
    return {role: {task: result['native'][task]['answer'] for task in TASKS}
            for role, result in zip(('incumbent', 'proposal'), (before, after), strict=True)}, known, sha(run/'terminal.json')


def evaluate(outputs, assets, titles, views):
    predictions, counts, cases = {}, {}, {}
    for role, bank in outputs.items():
        answers = {'EC': bind_classification(views['EC'], bank['EC']), 'EV': bank['EV']}
        conflict = set()
        audit = Counter()
        for asset in assets:
            positives = {task: positive_citations(task, answers[task], asset) for task in TASKS}
            t = {task: titles[task][asset] for task in TASKS}
            if not any(positives.values()):
                continue
            shared = bool(list(witnesses(positives, t)))
            direct = direct_support(positives, t)
            if direct is not shared:
                raise ValueError('Keep the exact same-information direct comparison')
            audit['positive_assets'] += 1
            audit['joint_conflicts'] += not shared
            if not shared and all(len(positives[task]) <= 1 and (not positives[task] or t[task] is not False)
                                  for task in TASKS):
                audit['strict_cross_task_positive_conflicts'] += 1
                prior_conflict = any(not direct_title_scope(
                    citation in answers['EC'][asset] if asset in answers['EC'] else None,
                    True, t['EC'], t['EV']) for citation in positives['EV'])
                audit['strict_conflicts_missed_by_same_citation_title_rule'] += not prior_conflict
                conflict.add(asset)
        cleaned = {task: {} for task in TASKS}
        for task, answer in answers.items():
            for name, entries in answer.items():
                cleaned[task][name] = [
                    item for item in entries if name not in conflict
                    or (item if task == 'EC' else item['citation']) not in CITATIONS]
        predictions[role] = {'canonical': answers, 'omit_conflicting_types': cleaned}
        counts[role] = dict(audit)
        cases[role] = sorted(digest(x) for x in conflict)
    return predictions, counts, cases


def run():
    original = ROOT / read(forms.POINTER)['artifact_root']
    paired_cases = read(original / 'cases.json')
    scope_binding = read(original / 'binding.json')
    if (digest(scope_binding) != original.name or digest(paired_cases) != scope_binding['cases_sha256']
            or read(original / 'terminal.json')['DEV_or_TEST_used']):
        raise ValueError('Require the original independently audited PA TRAIN source roster')
    by_key = {(c['source'], c['family']): {k: v for k, v in c.items() if k != 'truth'} for c in paired_cases}
    all_predictions, counts, scopes = {}, {}, {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('SELECT status,count(*) FROM calls GROUP BY status'))
        if ledger.get('reserved'):
            raise ValueError('The continuous ledger must be settled')
        boards, terminals, programs, wires, grade_path = archive.archived_pairs(db)
        for batch, board in boards.items():
            key, = [k for k in board['original_views'] if (k, 'EC') in by_key]
            views = board['original_views'][key]
            assets, titles = scope(*(by_key[key, t] for t in TASKS), views)
            inputs = {role: bank[key] for role, bank in board['raw'].items()}
            names = f'B{batch}_B7_PROPOSAL_FLOW'
            all_predictions[names], counts[names], scopes[names] = evaluate(inputs, assets, titles, views)
            scopes[names] = {'source': key, 'views': views, 'conflict_ids': scopes[names]}
            if batch != 8:
                continue
            observed = ROOT / read(archive.observe_pointer(8))['artifact_root']
            binding = read(observed / 'binding.json')
            checkpoint = ROOT / binding['checkpoint_root']
            study = read(checkpoint/'binding.json')
            batch_rows = archive.load_roster(study)
            source, = [s for s in batch_rows[7] if s['key'] == key]
            journal = archive.TrainingJournal(checkpoint, study, batch_rows)
            obs = journal._observations(M2, 8)
            saved = read(journal.directory(M2, 8) / 'predictions' / (digest(key)+'.json'))
            if (digest(saved) != obs['predictions'][key] or set(cell['id'] for cell in source['views']) != set(TASKS)
                    or obs['train_observation_sha256'] != read(observed/'terminal.json')['observation_receipts'][M2]):
                raise ValueError('The original B8 incumbent observation must be exact')
            new, actual, stamp = candidate_b8(db, source, programs['incumbent'], saved)
            terminals['B8_fit'] = stamp
            names = 'B8_CONTEMPORANEOUS_PROPOSAL'
            all_predictions[names], counts[names], found = evaluate(new, assets, titles, views)
            scopes[names] = {'source': key, 'views': views, 'conflict_ids': found}
    spec = {'stage': 'M2_positive_cross_citation_conflicts', 'archive_terminals': terminals,
            'paired_scope_evidence_sha256': sha(original/'binding.json'),
            'source_sha256': sha(Path(__file__)), 'TRAIN_only': True, 'physical_responses_in_B7_B8_archive': wires,
            'physical_responses_in_contemporaneous_B8_pair': len(actual), 'TRAIN_grade_sha256': sha(grade_path)}
    out = HOME/digest(spec)
    immutable_json(out/'binding.json', spec)
    if (out/'terminal.json').exists():
        print(out, flush=True)
        return
    prediction_hash = immutable_json(out/'predictions.json', all_predictions)
    grades = read(grade_path)
    results = {}
    for label, measured in all_predictions.items():
        row = scopes[label]
        results[label] = {role: {mode: {task: grade_view(OE, row['views'][task], grades[row['source']][task],
                                                         pair[task])['grade'] for task in TASKS}
                                 for mode, pair in conditions.items()} for role, conditions in measured.items()}
        for role, modes in results[label].items():
            counts[label][role]['mean_change_from_discarding'] = mean(
                modes['omit_conflicting_types'][task] - modes['canonical'][task] for task in TASKS)
    report = sealed({'status': 'settled_M2_cross_citation_TRAIN', 'binding_sha256': digest(spec),
                     'predictions_sha256': prediction_hash, 'observed': counts, 'native_F1_by_view': results,
                     'same_information_direct_matched_shared': True, 'original_update_decisions_preserved': True,
                     'new_model_calls': 0, 'TEST_opened': False, 'ledger': ledger}, 'terminal_sha256')
    immutable_json(out/'terminal.json', report)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'artifact_root': str(out.relative_to(ROOT)),
                                   'terminal_sha256': report['terminal_sha256']})+'\n')
    pending.replace(POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
