"""Attach the verified EC asset binding to the existing B8 development cells."""

import json
import sqlite3
from pathlib import Path

from experiments import convergence_revision5_oe_assertion_coverage as gate
from experiments import convergence_revision5_oe_ec_binding as ec
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_common_native_dev import archive
from experiments.convergence_revision5_oe_category_scope import prepare_category
from experiments.convergence_revision5_oe_wildcard_replay import prepare_routes
from legal_skill_guard.paired_interfaces.convergence_ec_inventory import bind_classification
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.paired_interfaces.pilot_metrics import summarize
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision5_oe_ec_formal_20261119'
POINTER = HANDOFF / 'revision5_oe_ec_formal_current.json'


def m2_gate(out, db):
    boards, terminals, programs, wires, grade_path = gate.archived_pairs(db)
    for board in boards.values():
        gate.replay(board)
    prepare_routes(boards)
    predictions, reports = {}, {}
    for batch, board in boards.items():
        board['category'], _ = prepare_category(board['views'], board['wildcard'])
        before = gate.conflict_summary(board, 'category')
        canonical = {}
        for label in ('raw', 'category'):
            canonical[label] = {}
            for role, rows in board[label].items():
                canonical[label][role] = {
                    key: {**output, 'EC': bind_classification(board['original_views'][key]['EC'], output['EC'])}
                    for key, output in rows.items()
                }
        after = gate.conflict_summary({**board, **canonical}, 'category')
        reports[str(batch)] = {'bound_assertions_before': before['bound_assertion'],
                               'bound_assertions_after': after['bound_assertion']}
        predictions[str(batch)] = {'old': board['category'], 'reconciled': canonical['category']}
    prediction_hash = immutable_json(out / 'B7_B8_TRAIN_gate_predictions.json', predictions)
    grades = read(grade_path)
    for batch, bank in predictions.items():
        reports[batch]['native'] = {
            condition: gate.score(boards[int(batch)]['original_views'], arms, grades)
            for condition, arms in bank.items()
        }
    b7 = reports['7']
    before, after = (b7[f'bound_assertions_{suffix}'] for suffix in ('before', 'after'))

    def conditional_decision(conflicts, mode):
        native = b7['native'][mode]['proposal']['paired_vs_incumbent']['mean_change']
        veto = not conflicts['incumbent'] and conflicts['proposal'] > 0
        # compare_conflicts checks equality against the same-information direct test per assertion.
        return ('incumbent' if veto or native <= 0 else 'proposal')

    return {'training_programs': programs, 'archive_terminals': terminals, 'physical_responses_verified': wires,
            'predictions_sha256': prediction_hash, 'replayed_batches': reports,
            'replayed_conditional_shared_and_direct_selection': {'before': conditional_decision(before, 'old'),
                                                                'after': conditional_decision(after, 'reconciled')},
            'original_selection_preserved': True}


def citation_content(answer):
    return {asset: sorted(citations) for asset, citations in answer.items()} if isinstance(answer, dict) else answer


def run():
    cohort, _, study, _ = archive()
    sources = {s['key']: s for s in cohort}
    ec_current = read(ec.POINTER)
    replay = ROOT / ec_current['artifact_root']
    result = verify(read(replay / 'terminal.json'), 'terminal_sha256')
    binding = read(replay / 'binding.json')
    if (replay.name != digest(binding) or result['terminal_sha256'] != ec_current['terminal_sha256']
            or sha(replay / 'predictions.json') != result['predictions_sha256']
            or any(sha(ROOT / k) != h for k, h in result['source_sha256'].items())):
        raise ValueError('Expected the sealed classified asset reconciliation')
    old_status = read(ec.INTEGRATED)
    parent = ROOT / old_status['artifact_root']
    parent_terminal = verify(read(parent / 'terminal.json'), 'terminal_sha256')
    if (parent_terminal['terminal_sha256'] != binding['revised_DEV_terminal_sha256']
            or parent_terminal['terminal_sha256'] != old_status['terminal_sha256']):
        raise ValueError('The EC comparison must target the exact integrated B8 development cell')
    spec = {'stage': 'B8_DEV_EC_asset_binding_only', 'parent_terminal_sha256': parent_terminal['terminal_sha256'],
            'comparison_terminal_sha256': result['terminal_sha256'], 'scope': 'OpenExempt EC',
            'model_calls': 0, 'source_sha256': sha(Path(__file__)),
            'counterfactual_sources': {str(Path(m.__file__).relative_to(ROOT)): sha(Path(m.__file__))
                                      for m in (gate,)}}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    if (out / 'terminal.json').is_file():
        print(out, flush=True)
        return
    estimates = read(replay / 'predictions.json')['dev']
    grade_path = study['grading_paths'][ec.DATASET]
    if 'dev' not in Path(grade_path).parts or sha(ROOT / grade_path) != study['grading_file_sha256'][grade_path]:
        raise ValueError('DEV labels must be original and confined to the revised task')
    terminal_cells = {}
    predicted = {}
    for arm, parent_arm in parent_terminal['per_arm'].items():
        folder = parent / 'dev' / 'B8' / arm
        parent_scores = verify(read(folder / 'scores.json'), 'cell_sha256')
        parent_seal = verify(read(folder / 'prediction_seal.json'), 'prediction_seal_sha256')
        if (parent_scores['cell_sha256'] != parent_arm['cell_sha256']
                or parent_scores['prediction_seal_sha256'] != parent_seal['prediction_seal_sha256']
                or parent_seal['task_sha256'] != digest(read(folder / 'task.json'))):
            raise ValueError('Expected the verified parent DEV predictions and native scores')
        predicted[arm] = {}
        for key, source in sources.items():
            old = read(folder / 'predictions' / (digest(key) + '.json'))
            if digest(old) != parent_seal['predictions_sha256'][key] or old['public_source_sha256'] != digest(source):
                raise ValueError('Parent prediction does not bind the same source')
            if source['dataset'] != ec.DATASET:
                continue
            native = old['result']['native']
            ec_prediction = native['EC']
            revised = bind_classification(ec.view_for(source), ec_prediction['answer'])
            if citation_content(revised) != citation_content(estimates[arm][key]['normalize_final']):
                raise ValueError('Asset binding must reproduce the sealed targeted comparison')
            predicted[arm][key] = {'old_prediction_sha256': digest(old),
                                   'native': {**native, 'EC': {**ec_prediction, 'answer': revised}}}
        predictions_sha = immutable_json(out / 'dev/B8' / arm / 'EC_predictions.json', predicted[arm])
        terminal_cells[arm] = {'new_EC_predictions_sha256': predictions_sha,
                               'parent_cell_sha256': parent_scores['cell_sha256'],
                               'preserved_parent_predictions_sha256': parent_seal['prediction_seal_sha256'],
                               'reused_native_views': len(parent_scores['source_scores']) - len(predicted[arm])}
    annotations = read(ROOT / grade_path)
    for arm, rows in predicted.items():
        scores = [{'source': key, 'view': 'EC', 'handled': row['native']['EC']['handled'],
                   'grade': grade_view(ec.DATASET, ec.view_for(sources[key]), annotations[key]['EC'],
                                       row['native']['EC']['answer'])['grade']} for key, row in rows.items()]
        metrics = summarize(scores, {(key, 'EC') for key in rows})
        value = result['scores']['dev'][arm]['normalize_final']['f1']
        if abs(metrics['mother_macro'] - value) > 1e-12:
            raise ValueError('Official EC scoring did not reproduce the targeted comparison')
        score = sealed({**terminal_cells[arm], 'EC_F1': value, 'changed_openexempt_EC_only': True}, 'cell_sha256')
        immutable_json(out / 'dev/B8' / arm / 'EC_scores.json', score)
        terminal_cells[arm] = score
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('SELECT status, count(*) FROM calls GROUP BY status'))
        if ledger.get('reserved') or ledger != result['ledger']:
            raise ValueError('The continuous ledger changed during local DEV')
        m2 = m2_gate(out, db)
    record = sealed({'status': 'settled_EC_revised_B8_DEV', 'cells': terminal_cells, 'binding_sha256': digest(spec),
                     'M2_counterfactual_TRAIN': m2, 'DEV_mothers': 16, 'DEV_changed_task': 'EC',
                     'model_calls': 0, 'ledger': ledger, 'TEST_opened': False}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', record)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'status': record['status'],
                                   'terminal_sha256': record['terminal_sha256']}) + '\n')
    pending.replace(POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
