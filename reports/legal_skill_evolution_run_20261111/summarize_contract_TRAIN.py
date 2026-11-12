"""Post-hoc accounting for the previously frozen four-parent TRAIN diagnostic.

Reads settled records only; does not generate, relabel or select new examples.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
REPORT = Path(__file__).resolve().parent
RUNS = ['legal_skill_evolution_contract_acquisition_20261112',
        'legal_skill_evolution_contract_updates_20261112']


def read(p):return json.loads(p.read_text())


def write(name, value):
    (REPORT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def native(row):
    views = row['views']
    assert not any(v['controlled'] for v in views)
    expected = sum(v['score']['grade'] for v in views) / len(views)
    assert expected == row['native_grade'] == row['selection_grade']
    return {'source': row['source'], 'library_hash': row['library_hash'],
        'grade': expected, 'core_correct': row['native_core_correct'],
        'fallback_views': row['native_fallback_views'], 'total_views': len(views),
        'views': [{'view': v['view'], 'grade': v['score']['grade'],
            'core': v['execution']['core_executed'], 'fallback': v['execution']['fallback'],
            'answer': v['execution']['answer'], 'error': v['execution'].get('error'),
            'USE': [e for e in v['execution']['events'] if e.get('kind') == 'USE']}
            for v in views]}


def check_table(table, selected):
    """Independently check every measured cell and the original admission rule."""
    n = len(table['revision_hashes']);sources = table['trigger'] + table['history']
    cells = {(c['mask'], c['source']): c for c in table['mixed_version_table']}
    assert len(cells) == (1 << n) * len(sources)
    complete = all(c['measured'] and c['native_parent_grade'] is not None for c in cells.values())
    assert complete == table['complete']
    acceptable = []
    for mask in range(1, 1 << n):
        if not complete:break
        gain = sum(cells[mask, s]['native_parent_grade'] - cells[0, s]['native_parent_grade']
                   for s in table['trigger']) / len(table['trigger'])
        retained = all(cells[mask, s]['native_parent_grade'] >= cells[0, s]['native_parent_grade']
                       for s in table['history'])
        if gain > 0 and retained:acceptable.append(mask)
    minimal = [m for m in acceptable if not any(k != m and k & m == k for k in acceptable)]
    assert table['minimal_blocks'] == minimal
    classification = ('single_sufficient' if any(m.bit_count() == 1 for m in minimal)
                      else 'joint_needed' if minimal else 'harmful_or_unresolved')
    assert table['classification'] == classification
    if selected is not None:assert selected in acceptable
    for c in cells.values():
        if c['trace'] is not None:assert native(c['trace'])['grade'] == c['native_parent_grade']
    return {'classification': classification, 'complete': complete,
        'minimal_masks': minimal, 'acceptable_masks': acceptable,
        'selected_mask': selected, 'cells': [{k: c[k] for k in
            ('mask', 'source', 'native_parent_grade', 'measured')} for c in cells.values()]}


def main():
    acquisition, updates = [ROOT / 'artifacts' / r for r in RUNS]
    done = read(updates / 'completed.json');protocol = read(updates / 'protocol.json')
    assert not done['goal_complete']
    costs = {'by_run': {}, 'request_rows': [], 'cash_invoice_usd': None,
             'cash_note': 'GPU and teacher invoices unavailable; local per-request API cash alone is not total cost. Reasoning output is included in teacher output tokens.'}
    ledger = ORIGINAL / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(ledger) + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        costs['cumulative_physical_counts'] = {r: n for r, n in db.execute('select role,count(*) from calls group by role')}
        for run in RUNS:
            totals = {'physical_requests': Counter(), 'executor_usage': Counter(),
                      'teacher_usage': Counter(), 'executor_all_OFF_empty_reasoning': True,
                      'executor_finish_reasons': Counter(), 'sum_request_seconds': 0}
            for i, role, state, raw in db.execute('select id,role,status,result from calls where id like ? order by reserved_at', (run + ':%',)):
                v = json.loads(raw or '{}');totals['physical_requests'][role] += 1
                usage = v.get('usage', {}) if role == 'executor' else v.get('invocation', {}).get('usage', {})
                totals[role + '_usage'].update({k: x for k, x in usage.items() if type(x) is int})
                seconds = v.get('elapsed_seconds', 0);totals['sum_request_seconds'] += seconds
                if role == 'executor':
                    totals['executor_all_OFF_empty_reasoning'] &= v.get('thinking_requested') is False and not v.get('reasoning_content')
                    totals['executor_finish_reasons'][str(v.get('finish_reason'))] += 1
                costs['request_rows'].append({'id': i, 'role': role, 'status': state,
                    'usage': usage, 'elapsed_seconds': seconds, 'actual_cash_invoice_available': v.get('actual_cash_invoice_available'),
                    **({'thinking_requested': v.get('thinking_requested'), 'reasoning_content': v.get('reasoning_content'),
                        'finish_reason': v.get('finish_reason')} if role == 'executor' else {})})
            costs['by_run'][run] = totals
    results = {'goal_complete': False, 'comparison': 'Shared actual seed isolates update mechanisms; two independent seed acquisitions separately retained.',
        'four_previously_seen_original_TRAIN_parents': protocol['previously_fixed_source_order'],
        'NoSkill': [native(r) for r in done['NoSkill_original_TRAIN_results']], 'arms': {}}
    for arm in protocol['arms']:
        entry = {'updates': [], 'reuse': [native(r) for r in done['reuse_results'][arm]]}
        for batch in (2, 3):
            update = read(updates / arm / f'update_B{batch}.json')
            candidates = []
            for p in sorted((updates / arm / f'B{batch}_candidates').glob('*.json')):
                value = read(p);summary = {'index': int(p.stem), 'error': value.get('error'),
                    'selection_exclusion': value.get('selection_exclusion'), 'pattern_id': value.get('pattern_id'),
                    'revisions': [{'id': r['skill_id'], 'operation': r['operation'], 'old_hash': r['old_hash'],
                        'new_hash': r['new_hash']} for r in value.get('revisions', [])]}
                if value.get('table'):summary['version_table'] = check_table(value['table'], value.get('selected_mask'))
                candidates.append(summary)
            lib = read(updates / arm / f'B{batch}.json')
            entry['updates'].append({'batch': batch, 'initial': [native(r) for r in read(updates / arm / f'initial_B{batch}.json')['results']],
                'receipt': update, 'candidates': candidates,
                'skills': {sid: {'version': s['version'], 'procedure': s['procedure'], 'premises': s['premises'],
                    'outputs': s['outputs'], 'inputs': s['inputs']} for sid, s in lib['skills'].items()},
                'revision_patterns': lib['revision_patterns']})
        results['arms'][arm] = entry
    evidence = REPORT / 'contract_TRAIN_evidence';manifest = []
    for folder in (acquisition, updates):
        for p in sorted(folder.rglob('*')):
            if not p.is_file() or p.suffix not in {'.json', '.py', '.md', '.txt'} or '__pycache__' in p.parts:continue
            dest = evidence / folder.name / p.relative_to(folder);dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():assert dest.read_bytes() == p.read_bytes()
            else:shutil.copyfile(p, dest)
            manifest.append({'path': str(dest.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size})
    write('contract_TRAIN_costs_and_OFF.json', costs)
    write('contract_TRAIN_results.json', results)
    write('contract_TRAIN_evidence_manifest.json', {'utc': datetime.now(timezone.utc).isoformat(), 'files': manifest,
        'all_original_files_preserved': True, 'new_model_calls_by_analysis': 0})
    print(json.dumps({'evidence_files': len(manifest), 'physical_counts': costs['cumulative_physical_counts'],
        'per_arm_final_pattern_counts': {a: len(v['updates'][-1]['revision_patterns']) for a, v in results['arms'].items()}}))


if __name__ == '__main__':main()
