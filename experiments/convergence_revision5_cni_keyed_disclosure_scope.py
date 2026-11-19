"""Replay the bound clause reader with outside assertions checked against source IDs."""

from collections import Counter
import json
from pathlib import Path
import sqlite3
from statistics import mean

from experiments import convergence_revision5_cni_keyed_disclosure as pilot
from legal_skill_guard.rr.checkpoint import immutable_json


HOME = pilot.BASE / 'revision5_CNI_keyed_disclosure_scope_20261119'
TABLE = pilot.ROOT / 'reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_KEYED_DISCLOSURE_20261119.json'


def reconcile(case, raw):
    """Normalize a contradicted scope flag while preserving cited IDs and all legal fields."""
    obj = json.loads(raw['content'])
    covered = {index for group in case['public']['groups'].values() for index in group}
    evidence = set(obj['outside_evidence'])
    if obj['outside_scope'] and obj['whole_document_checked'] and evidence and evidence <= covered:
        return {**raw, 'content': json.dumps({**obj, 'outside_scope': False})}, True
    return raw, False


def summarize(metrics):
    return {'correct': int(sum(r['grade'] for r in metrics)),
            'evidence_f1': mean(r['evidence_f1'] for r in metrics),
            'correct_and_evidence_f1': mean(r['evidence_f1'] * r['grade'] for r in metrics)}


def run():
    spec, cases, prior = pilot.materials()
    stage = pilot.ROOT/pilot.read(pilot.POINTER)['artifact_root']
    archived = pilot.read(stage/'terminal.json')
    assert pilot.digest(spec) == stage.name and archived['status'] == pilot.DONE
    assert archived['predictions_sha256'] == pilot.sha(stage/'predictions.json')
    assert all(pilot.sha(stage/'source_snapshot'/k) == v for k,v in spec['source_sha256'].items())
    predictions = pilot.read(stage/'predictions.json')
    track = {}
    corrected = Counter(dict.fromkeys(pilot.ROLES, 0))
    with sqlite3.connect(pilot.LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert ledger == archived['ledger'] and not ledger.get('reserved')
        for case, row in zip(cases, predictions, strict=True):
            key = case['key']
            track[key] = {}
            for role, entry in row.items():
                raw, wire = pilot.response(db, key, entry['physical_id'])
                messages, schema = pilot.contract(case, role)
                assert wire == pilot.request_payload(spec['executor'], messages=messages, thinking=False, schema=schema)
                assert pilot.decode(case, role, raw) == (entry['answer'], entry['status'])
                normalized, applicable = reconcile(case, raw)
                corrected[role] += applicable
                answer, status = pilot.decode(case, role, normalized)
                if role == 'direct':
                    assert answer == entry['answer'] and status == entry['status']
                track[key][role] = {'previous': entry['answer'], 'normalized': answer, 'status': status}
    source_control = pilot.common.TABLE
    binding = {'runner_sha256': pilot.sha(Path(__file__)), 'paired_terminal_sha256': pilot.sha(stage/'terminal.json'),
               'source_control_sha256': pilot.sha(source_control), 'original_TRAIN_grade_sha256': spec['grade_sha256']}
    out = HOME/pilot.digest(binding)
    immutable_json(out/'binding.json', binding)
    immutable_json(out/'predictions.json', track)
    p = pilot.ROOT/spec['grade']
    assert p.parent.name == 'train' and pilot.sha(p) == spec['grade_sha256']
    train, _, _, _ = pilot.common.archive.collect(*pilot.common.archive.archive_context(), 'train')
    entries = pilot.read(p)
    annotations = {key: entries[key][pilot.common.TASK] for key in train}
    outcomes = {role: {'previous': [], 'normalized': []} for role in pilot.ROLES}
    majority, selected_labels = [], Counter()
    for case in cases:
        key = case['key']
        annotation = annotations[key]
        selected_labels[annotation['answer']] += 1
        counts = Counter(v['answer'] for parent, v in annotations.items() if parent != key)
        expected, _ = counts.most_common(1)[0]
        major = pilot.grade_view('ContractNLI', case['view'], annotation, expected, [])
        majority.append(major)
        for role, saved in track[key].items():
            for revision in outcomes[role]:
                row = saved[revision]
                metrics = pilot.grade_view('ContractNLI', case['view'], annotation, row['answer'], row['evidence_sentence_ids'])
                outcomes[role][revision].append({**metrics, 'source': key, 'view': pilot.common.TASK})
    dev, _, _, _ = pilot.common.archive.collect(*pilot.common.archive.archive_context(), 'dev')
    dev_eligible = sum(bool(pilot.eligible_groups(next(v for v in s['views'] if v['id'] == pilot.common.TASK))) for s in dev.values())
    diagnostics = {r: {k: summarize(v) for k,v in cells.items()} for r,cells in outcomes.items()}
    for role in pilot.ROLES:
        assert diagnostics[role]['previous']['correct'] == archived['scores'][role]['correct']
    result = {'status': 'settled_revision5_CNI_keyed_disclosure_scope', 'binding': binding, 'new_executor_calls': 0,
              'verified_new_trial_physical_calls': sum(len(r) for r in predictions), 'ledger': ledger,
              'measured_TRAIN_trial': archived, 'scope_flag_corrections_by_arm': dict(corrected),
              'retrospective_scope_normalization': diagnostics, 'original_TRAIN_labels_in_trial': dict(selected_labels),
              'leave_one_mother_out_TRAIN_majority': summarize(majority),
              'normalized_synthesized_vs_fixed_accuracy': pilot.paired_source_effect(outcomes['fixed']['normalized'], outcomes['synthesized']['normalized']),
              'eligible_fixed_DEV_texts_no_new_reads': dev_eligible,
              'source_only_control': pilot.read(source_control)['partition_results']}
    immutable_json(out/'terminal.json', result)
    immutable_json(TABLE, result)
    print(out.relative_to(pilot.ROOT), json.dumps(diagnostics), summarize(majority), dev_eligible, flush=True)


if __name__ == '__main__':
    run()
