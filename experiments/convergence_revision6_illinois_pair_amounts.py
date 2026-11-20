"""Trace the B6 Illinois proposal's classification and valuation by asset."""

from collections import Counter
from decimal import Decimal
from math import isfinite
from pathlib import Path
import sqlite3
from statistics import mean

from experiments import convergence_revision6_cni_b5_disagreement as previous
from experiments import convergence_revision6_ec_general_property as property_rules
from experiments import convergence_revision5_oe_native_amount_bound as wire
from experiments import convergence_revision5_oe_wildcard_replay as wildcard
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import convergence_oe_illinois_amount as amounts
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_illinois_pair_amounts'
POINTER = HANDOFF / 'revision6_illinois_pair_amounts_current.json'
OE, CITATION = 'OpenExempt', amounts.CITATION
formal = property_rules.formal


def values(answer, asset):
    if not isinstance(answer, dict):
        return set()
    return {Decimal(str(row['claim_value'])) for row in answer.get(asset, []) if row['citation'] == CITATION}


def candidate_amounts(candidate, supported):
    """Only transport amounts that the actual update asserted for this asset."""
    return {asset: amount for asset, amount in supported.items() if values(candidate, asset) == {amount}}


def native_fit(db, sources, proofs):
    fit, binding, terminal = property_rules.archive.bound_stage(formal.pointer(6))
    decisions = read(fit / 'matched_decisions.json')
    fitted = decisions['teacher'][formal.ORDINARY][OE]
    proposal = read(fit / 'candidates' / formal.ORDINARY / OE / 'measurements.json')
    checkpoint = ROOT / binding['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    roster = formal.load_roster(study)
    journal = wire.TrainingJournal(checkpoint, study, roster)
    entry = digest(journal.library(formal.M2, 5)['programs'][OE])
    patch = digest(proposal['candidate'])
    if (terminal['batch'] != 6 or digest(decisions) != terminal['matched_decisions_sha256']
            or patch != decisions['relation'][OE]['matched_proposal_sha256']
            or digest(proposal['predictions']) != fitted['predictions_sha256']):
        raise ValueError('Keep the sealed B6 fit and its original matched teacher candidate')
    known, bank, support = set(), {}, {}
    observation = journal._observations(formal.M2, 6)
    for source in roster[5]:
        key = source['key']
        if key not in proofs or not proofs[key]:
            continue
        if source != sources[key] or source['project_split'] != 'train':
            raise ValueError('Only B6 original TRAIN observations can fit the scope')
        saved = read(journal.directory(formal.M2, 6) / 'predictions' / (digest(key) + '.json'))
        if digest(saved) != observation['predictions'][key]:
            raise ValueError('The entering B6 prediction changed')
        measurements = {}
        for name, result, version in (('entering', saved['result'], entry),
                                       ('proposal', proposal['predictions'][key], patch)):
            category = property_rules.native(db, source, {'result': result}, version, known)
            identity, value = property_rules.ev.archive.verified_ev(db, source, wire.ev_view(source), result, version)
            known.add(identity)
            asset_value = property_rules.ev.scopes(wire.ev_view(source), value)['same_public_jurisdiction']
            measurements[name] = (category, asset_value)
        original, candidate = measurements['entering'], measurements['proposal']
        proof = proofs[key]
        if not proof.keys() <= property_rules.source_claims(property_rules.view_for(source), CITATION):
            raise ValueError('The paired EC and EV inputs must establish title to the same assets')
        accepted = candidate_amounts(candidate[1], proof)
        bank[key] = {'entering': original[1], 'proposal': candidate[1],
                     'candidate_scoped': amounts.apply(original[1], accepted),
                     'same_information_direct': amounts.apply(original[1], proof)}
        for asset, expected in proof.items():
            event = {}
            for role, (category, value) in measurements.items():
                explicit = values(value, asset)
                event[role] = {
                    'classification_cites_target': property_rules.assertion(category, asset, CITATION),
                    'valuation': 'exact' if explicit == {expected} else
                    'omitted' if not explicit else 'explicit_zero' if explicit == {Decimal(0)} else 'other',
                }
            support.setdefault(key, {})[asset] = event
    return bank, support, sha(fit / 'terminal.json'), (entry, patch), len(known)


def score(cases, predictions, labels, left, right):
    def rows(arm):
        records = []
        for key, result in predictions.items():
            native = grade_view(OE, wire.ev_view(cases[key]), labels[key]['EV'], result[arm])
            records.append({'source': key, 'view': 'EV', **native})
        return records

    def metrics(records):
        bank = [row['official_metrics'].get('metrics') or {} for row in records]
        output = {}
        for name in ('precision', 'recall', 'mare'):
            known = [row[name] for row in bank if type(row.get(name)) in (int, float) and isfinite(row[name])]
            output[name] = {'scored': len(known), 'mean': mean(known) if known else None}
        return output

    before, after = rows(left), rows(right)
    if any(r['grade'] is None for r in (*before, *after)):
        raise ValueError('Use two handled native outputs on the complete comparison cohort')
    shifts = Counter('improved' if b['grade'] > a['grade'] else 'regressed'
                     if b['grade'] < a['grade'] else 'same' for a, b in zip(before, after, strict=True))
    return {'mothers': len(before), 'F1': [mean(r['grade'] for r in a) for a in (before, after)],
            'other_official_metrics': {left: metrics(before), right: metrics(after)},
            'directions': dict(shifts), 'paired': paired_source_effect(before, after)}


def run():
    _, _, prior_terminal = previous.development.agreement.bound_result(previous)
    train, _, train_grade, training_archive, _ = wildcard.old_amount_bank('train')
    parent, cohort, originals, study, _ = previous.development.baseline.base_actor()
    sources = {s['key']: s for s in cohort if s['dataset'] == OE and s['project_split'] == 'dev'}
    if len(train) != 32 or len(sources) != 16:
        raise ValueError('Preserve the original OpenExempt TRAIN and fixed DEV denominators')
    supported = {name: {k: amounts.source_amounts(wire.ev_view(s)) for k, s in rows.items()}
                 for name, rows in (('TRAIN', train), ('DEV', sources))}
    # Decimals are represented losslessly as strings in the bound proof file.
    proof_bank = {name: {k: {asset: str(value) for asset, value in amounts_by_asset.items()}
                        for k, amounts_by_asset in rows.items()} for name, rows in supported.items()}
    predictions = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        fitted, incidence, fit_hash, program_hashes, train_count = native_fit(db, train, supported['TRAIN'])
        verified = set()
        for arm, (folder, seal, cell) in originals.items():
            for key, proof in supported['DEV'].items():
                if not proof:
                    continue
                row = read(folder / 'predictions' / (digest(key) + '.json'))
                if (digest(row) != seal['predictions_sha256'][key]
                        or row['public_source_sha256'] != digest(sources[key])
                        or row['library_sha256'] != cell['libraries'][OE]):
                    raise ValueError('Use the original B8 source and wire')
                wire.read_ev(db, sources[key], row, verified, 'dev')
            rows = predictions[arm] = {}
            for key, source in sources.items():
                old = parent(source, {'arm': arm, 'batch': 8}, 'skill_dev')['native']['EV']['answer']
                rows[key] = {'inherited': old, 'same_information_direct': amounts.apply(old, supported['DEV'][key])}
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or not incidence:
        raise ValueError('Require settled original physical responses and applicable B6 evidence')
    name = study['grading_paths'][OE]
    grade = ROOT / name
    binding = {'stage': 'revision6_illinois_pair_amounts', 'prior_DEV': prior_terminal['terminal_sha256'],
               'B6_fit_terminal': fit_hash, 'B6_programs': program_hashes, 'original_TRAIN_archive': training_archive,
               'TRAIN_grade_sha256': sha(train_grade), 'DEV_grade_sha256': study['grading_file_sha256'][name],
               'DEV_cells': {arm: v[2]['cell_sha256'] for arm, v in originals.items()},
               'proofs_sha256': digest(proof_bank), 'TEST_opened': False,
               'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
                   __file__, amounts.__file__, property_rules.__file__, wire.__file__,
               )}}
    root = HOME / digest(binding)
    immutable_json(root / 'binding.json', binding)
    for path, expected in binding['source_sha256'].items():
        snapshot = root / 'source_snapshot' / path
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            with snapshot.open('xb') as handle:
                handle.write((ROOT / path).read_bytes())
        if sha(snapshot) != expected:
            raise ValueError('Preserve the exact source scope and replay')
    pred_hash = immutable_json(root / 'sealed_predictions.json', {'B6': fitted, 'DEV': predictions})
    immutable_json(root / 'proofs.json', proof_bank)
    if 'train' not in train_grade.parts or 'dev' not in grade.parts or sha(grade) != binding['DEV_grade_sha256']:
        raise ValueError('Score only bound native TRAIN/DEV labels after sealing the predictions')
    train_labels, labels = read(train_grade), read(grade)
    evidence = {}
    for part, references in (('TRAIN', train_labels), ('DEV', labels)):
        total, exact = 0, 0
        for key, rows in supported[part].items():
            for asset, expectation in rows.items():
                total += 1
                exact += values(references[key]['EV']['answer'], asset) == {expectation}
        evidence[part] = {'mothers': sum(bool(v) for v in supported[part].values()), 'assets': total,
                          'exact_amounts': exact}
    scores = {arm: score(sources, rows, labels, 'inherited', 'same_information_direct')
              for arm, rows in predictions.items()}
    exploratory = {arm: score(train, fitted, train_labels, 'entering', arm)
                   for arm in ('proposal', 'candidate_scoped', 'same_information_direct')}
    terminal = sealed({'status': 'settled_revision6_illinois_pair_amounts', 'binding_sha256': root.name,
                       'scope': evidence, 'B6_actual_matched_evidence': list(
                           row for assets in incidence.values() for row in assets.values()),
                       'B6_native_scope': exploratory, 'fixed_B8_DEV': scores,
                       'B6_proposal_used_in_DEV': False, 'EV_only_common_rule': True,
                       'archive_requests_verified': {'TRAIN_B6': train_count, 'DEV': len(verified)},
                       'ledger': ledger, 'new_executor_requests': 0, 'new_teacher_requests': 0,
                       'TEST_opened': False, 'predictions_sha256': pred_hash}, 'terminal_sha256')
    immutable_json(root / 'terminal.json', terminal)
    write_status(root, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(root)


if __name__ == '__main__':
    run()
