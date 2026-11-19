"""Bind a disclosure duty to the agreement event on sealed ContractNLI TRAIN and DEV."""

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_cni_disposition_roles as roles
from experiments import convergence_revision5_cni_keyed_disclosure_scope as keyed

base = keyed.pilot.common
events = roles.events
TASK = base.TASK
HOME = events.BASE / 'revision5_CNI_agreement_event_attachment_20261119'
POINTER = events.HANDOFF / 'revision5_CNI_agreement_event_attachment_current.json'
E, N = events.E, events.N
BILATERAL_NEGATION = re.compile(
    r'\bneither (?:party\b|(?:you|the receiv\w+ party|the recipient) nor '
    r'(?:you|your representatives|the other party|its representatives)\b)'
    r'[^.;]{0,90}?\b(?:shall|will|may)\b[^.;]{0,90}?\b(?:disclose|publicize|advertise)\b', re.I)
PASSIVE_BAR = re.compile(
    r'^\s*(?:\d+[.)]\s*)?(?P<object>[^,;]{0,140}?)\s+'
    r'(?:cannot|may not|shall not|must not|will not)\s+be\s+(?:disclosed|publicized|announced)\b', re.I)
PROCESS_FACT = re.compile(r'\b(?:the )?fact that\b.{0,80}\b(?:discussions?|negotiations?)\s+'
                          r'(?:have taken place|are taking place)\b', re.I)
POTENTIAL_TRANSACTION = re.compile(r'\bthe fact that a (?:possible )?transaction is '
                                   r'(?:being considered|under (?:a |an )?contract)\b', re.I)
RESTATED_BAR = re.compile(
    r'^it is (?:thus|therefore) forbidden to make\b[^;]*\bdisclosure\b[^;]*'
    r'\bof this agreement being in force\b', re.I)
SEPARATE_DUTY = re.compile(r'\b(?:and|but)\s+(?:shall|will|must|may|agrees? to)\b', re.I)
NEGATED_RESTRICTION = re.compile(
    r'\b(?:be required to|be obligated to|not restrict|be prevented from|'
    r'be prohibited from|nothing[^.;]*preclude)\b', re.I)
TALKS = re.compile(
    r'\b(?:content, nature or extent of the discussions proceeding in connection herewith|'
    r'discussions or negotiations covered by this agreement|'
    r'confirmation of all or any part of the discussions or negotiations)\b', re.I)
ARRANGEMENT_LIST = re.compile(
    r'^\([a-z]\)\s+not to discuss with\b[^.;]{0,130}\babout the nature of (?:the )?arrangement entered between\b',
    re.I)
AUDITOR_DUTY = re.compile(r'\bauditor affirms that it shall\s*:$', re.I)
LIST_ITEM = re.compile(r'^\(([a-z])\)\s+', re.I)


def list_duty(spans, i):
    """Require intervening items to stay inside the same alphabetically ordered list."""
    if not ARRANGEMENT_LIST.match(spans[i]):
        return ()
    start = next((j for j in range(i - 1, max(-1, i - 24), -1) if AUDITOR_DUTY.search(spans[j])), None)
    if start is None:
        return ()
    expected = ord('a')
    j = start + 1
    while j <= i:
        text = spans[j]
        if (item := LIST_ITEM.match(text)) and ord(item[1]) == expected:
            expected += 1
        elif (j > start + 1 and j + 1 < i and text.startswith('(i) ')
              and spans[j + 1].startswith('(ii) ') and spans[j - 1].lower().endswith((' on', ':'))):
            j += 1
        elif item or not text or text.endswith(':'):
            return ()
        j += 1
    return start, i


def source_proof(view, implied_confirmation):
    family, previous = base.compile_scope(view)
    if family in ('explicit_bar', 'explicit_grant', 'defined_object_bar', 'ambiguous'):
        return family, previous
    spans = [base.archive.clean(t) for t in base.archive.span_inventory(view)]
    for i, text in enumerate(spans):
        for clause in base.BREAK.split(text):
            if NEGATED_RESTRICTION.search(clause):
                continue
            if (passive := PASSIVE_BAR.search(clause)) and base.EVENT.search(passive['object']):
                ids = [i]
                if i + 1 < len(spans) and RESTATED_BAR.search(spans[i + 1]):
                    ids.append(i + 1)
                return 'passive_bar_on_event', {'answer': E, 'evidence_sentence_ids': ids}
            if match := BILATERAL_NEGATION.search(clause) or base.BAR.search(clause):
                object_text = SEPARATE_DUTY.split(clause[match.end():], maxsplit=1)[0]
                if base.EVENT.search(object_text) or PROCESS_FACT.search(object_text):
                    return 'explicitly_bound_event', {'answer': E, 'evidence_sentence_ids': [i]}
                if implied_confirmation and TALKS.search(object_text):
                    return 'facts_confirming_talks', {'answer': E, 'evidence_sentence_ids': [i]}
                if implied_confirmation and POTENTIAL_TRANSACTION.search(object_text):
                    return 'related_transaction_unconfirmed_scope', {'answer': E, 'evidence_sentence_ids': [i]}
        if implied_confirmation and (ids := list_duty(spans, i)):
            return 'list_duty_for_entered_arrangement', {'answer': E, 'evidence_sentence_ids': list(ids)}
    return family, previous


def supported_output(saved, proof):
    if proof is None:
        return saved
    if saved['answer'] == proof['answer'] and set(proof['evidence_sentence_ids']) <= set(saved['evidence_sentence_ids']):
        return saved
    return proof


def paired_reads(spec, cases):
    p = keyed.pilot
    stage = p.ROOT / p.read(p.POINTER)['artifact_root']
    terminal = p.read(stage / 'terminal.json')
    if (stage.name != p.digest(spec) or terminal['status'] != p.DONE
            or p.sha(stage / 'predictions.json') != terminal['predictions_sha256']
            or any(p.sha(stage / 'source_snapshot' / n) != h for n, h in spec['source_sha256'].items())):
        raise ValueError('Use the original settled, same-source request pairing')
    rows = {}
    with sqlite3.connect(p.LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for case, records in zip(cases, p.read(stage / 'predictions.json'), strict=True):
            rows[case['key']] = {}
            for role, record in records.items():
                raw, wire = p.response(db, case['key'], record['physical_id'])
                messages, schema = p.contract(case, role)
                if wire != p.request_payload(spec['executor'], messages=messages, thinking=False, schema=schema):
                    raise ValueError('An archived request differs from its recorded reader contract')
                if p.decode(case, role, raw) != (record['answer'], record['status']):
                    raise ValueError('An archived response differs from its recorded reader output')
                rows[case['key']][role] = p.decode(case, role, keyed.reconcile(case, raw)[0])[0]
    return rows, p.sha(stage / 'terminal.json')


def outputs(before, strict, broad):
    return {'composed': before, 'explicit_attachment': supported_output(before, strict),
            'including_facts_that_confirm': supported_output(before, broad)}


def matched_prior(views, strict, training_labels, part):
    """Fit a label-only abstention fallback on TRAIN, excluding the current TRAIN mother."""
    predictions = {}
    for key in views:
        counts = Counter(label for mother, label in training_labels.items() if part == 'dev' or mother != key)
        label, _ = counts.most_common(1)[0]
        majority = {'answer': label, 'evidence_sentence_ids': []}
        predictions[key] = {'training_majority': majority, 'explicit_then_training_majority': strict[key][1] or majority}
    return predictions


def joint_evidence(cells, mode, views, labels):
    scores = []
    for key, variants in cells.items():
        row = variants[mode]
        metrics = keyed.pilot.grade_view(
            events.legacy.DATASET, views[key], labels[key][TASK], row['answer'], row['evidence_sentence_ids']
        )
        scores.append(metrics['grade'] * metrics['evidence_f1'])
    return mean(scores)


def run():
    ledger = events.ledger_status()
    context = base.archive.archive_context()
    rp = events.ROOT / events.read(roles.POINTER)['artifact_root']
    prior = events.verify(events.read(rp / 'terminal.json'), 'terminal_sha256')
    role_receipt = events.read(events.HANDOFF / 'revision5_CNI_disposition_roles_terminal_20261119.json')
    composed = events.ROOT / events.read(events.composed.POINTER)['artifact_root']
    composed_terminal = events.verify(events.read(composed / 'terminal.json'), 'terminal_sha256')
    pairing, cases, _ = keyed.pilot.materials()
    reads, paired_terminal = paired_reads(pairing, cases)
    source_files = [Path(__file__), Path(base.__file__), Path(keyed.__file__), Path(keyed.pilot.__file__)]
    spec = {'stage': 'agreement_event_attachment_TRAIN_DEV',
            'prior_TERMINAL': prior['terminal_sha256'], 'paired_terminal_sha256': paired_terminal,
            'source_sha256': {str(p.relative_to(events.ROOT)): events.sha(p) for p in source_files},
            'reused_formal_DEV_prediction_sha256': role_receipt['formal_B8_DEV_predictions_sha256'],
            'last_composition_TRAIN_prediction_sha256': composed_terminal['predictions_sha256']['train']}
    out = HOME / events.digest(spec)
    events.immutable_json(out / 'binding.json', spec)
    if (out / 'terminal.json').exists():
        print(out)
        return
    results, predictions, prior_predictions, partitions = {}, {}, {}, {}
    for part in ('train', 'dev'):
        sources, _, grade, _ = base.archive.collect(*context, part)
        path = rp / 'formal_cni_dev_predictions.json' if part == 'dev' else composed / 'train_predictions.json'
        expected = spec['reused_formal_DEV_prediction_sha256' if part == 'dev'
                        else 'last_composition_TRAIN_prediction_sha256']
        if (events.sha(path) != expected
                or events.sha(grade) != events.read(composed / 'binding.json')[part.upper() + '_grade_sha256']
                or part not in grade.parts):
            raise ValueError('The evaluation must bind unchanged native development predictions and labels')
        views = {k: next(v for v in s['views'] if v['id'] == TASK) for k, s in sources.items()}
        strict = {k: source_proof(v, False) for k, v in views.items()}
        broad = {k: source_proof(v, True) for k, v in views.items()}
        original = events.read(path)
        bank = {arm: {k: outputs(native[TASK], strict[k][1], broad[k][1]) for k, native in cells.items()}
                for arm, cells in original.items()}
        if part == 'train':
            for arm in keyed.pilot.ROLES:
                bank['paired_' + arm] = {k: outputs(arms[arm], strict[k][1], broad[k][1]) for k, arms in reads.items()}
        predictions[part] = events.immutable_json(out / f'{part}_predictions.json', bank)
        partitions[part] = (grade, views, sources, strict, broad, bank)
    training_grade = events.read(partitions['train'][0])
    training_labels = {k: training_grade[k][TASK]['answer'] for k in partitions['train'][1]}
    priors = {}
    for part, (_, views, _, strict, _, _) in partitions.items():
        priors[part] = matched_prior(views, strict, training_labels, part)
        prior_predictions[part] = events.immutable_json(out / f'{part}_TRAIN_prior_predictions.json', priors[part])
    dev_grade, _, dev, _, _, dev_bank = partitions['dev']
    formal_before = events.read(rp / 'formal_cni_dev_predictions.json')
    formal_after = {arm: {k: {**native, TASK: dev_bank[arm][k]['explicit_attachment']}
                         for k, native in cells.items()} for arm, cells in formal_before.items()}
    formal_hash = events.immutable_json(out / 'formal_cni_dev_predictions.json', formal_after)
    for part, (grade, views, _, strict, broad, bank) in partitions.items():
        labels = events.read(grade)
        def score(cells):
            original_mothers = {k: {'views': [v]} for k, v in views.items() if k in cells}
            pairs = {mode: {k: {TASK: row[mode]} for k, row in cells.items()} for mode in next(iter(cells.values()))}
            return {mode: events.composed.score(original_mothers, pairs['composed'], realized, labels)
                    for mode, realized in pairs.items() if mode != 'composed'}
        def conflicts(proofs):
            return dict(Counter(family for k, (family, proof) in proofs.items()
                                if proof and labels[k][TASK]['answer'] != proof['answer']))
        results[part] = {
            'mothers': len(views), 'compiled_strict_scope': dict(Counter(v[0] for v in strict.values())),
            'compiled_broad_scope': dict(Counter(v[0] for v in broad.values())),
            'native_and_proof_disagreements': {'strict': conflicts(strict), 'exploratory': conflicts(broad)},
            'arms': {arm: score(cells) for arm, cells in bank.items()},
        }
        reference = bank['common_teacher_skill_learning']
        for name, keys in [('full', views), ('paired', [c['key'] for c in cases] if part == 'train' else [])]:
            if keys:
                cells = {k: {'composed': reference[k]['composed'], **priors[part][k]} for k in keys}
                results[part][name + '_prior_control'] = score(cells)
        if part == 'train':
            paired = {arm: bank['paired_' + arm] for arm in keyed.pilot.ROLES}
            paired_views = {c['key']: {'views': [views[c['key']]]} for c in cases}
            results[part]['paired_synthesized_vs_fixed'] = {
                mode: events.composed.score(
                    paired_views,
                    {k: {TASK: paired['fixed'][k][mode]} for k in paired_views},
                    {k: {TASK: paired['synthesized'][k][mode]} for k in paired_views},
                    labels,
                )
                for mode in ('composed', 'explicit_attachment', 'including_facts_that_confirm')
            }
            results[part]['paired_native_and_evidence_joint'] = {
                arm: {mode: joint_evidence(cells, mode, views, labels)
                      for mode in ('composed', 'explicit_attachment', 'including_facts_that_confirm')}
                for arm, cells in paired.items()
            }
    labels = events.read(dev_grade)
    integrated = {
        'predictions_sha256': formal_hash,
        'updated_native_slot': TASK,
        'CNI_views_per_arm': sum(len(s['views']) for s in dev.values()),
        'other_library_views_reused_per_arm': 112,
        'arms': {arm: events.composed.score(dev, recorded, formal_after[arm], labels)
                 for arm, recorded in formal_before.items()},
    }
    if events.ledger_status() != ledger or ledger.get('reserved'):
        raise ValueError('A local replay cannot change the continuous model ledger')
    record = events.sealed({'status': 'settled_CNI_agreement_event_attachment', 'binding_sha256': out.name,
                            'results': results, 'predictions_sha256': predictions,
                            'prior_predictions_sha256': prior_predictions,
                            'verified_paired_TRAIN_responses': len(reads) * len(keyed.pilot.ROLES),
                            'formal_CNI_DEV': integrated,
                            'new_model_calls': 0, 'TEST_opened': False, 'ledger': ledger}, 'terminal_sha256')
    events.immutable_json(out / 'terminal.json', record)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'status': record['status'], 'terminal_sha256': record['terminal_sha256'],
                                   'artifact_root': str(out.relative_to(events.ROOT))}) + '\n')
    pending.replace(POINTER)
    print(out)


if __name__ == '__main__':
    run()
