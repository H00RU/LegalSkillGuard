"""Regression from12 actual acquisition views, never the scored future pair.

This checks a necessary partial-supervision repair. It is not independent method
validation and does not acquire concepts or update operators.
"""
import hashlib
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.maud_source_feedback import evaluate_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import fit
from legal_skill_guard.skill_evolution.theory_supervision import attach_scored_theories
from experiments.legal_skill_evolution_MAUD_rule_acquisition import ROOT, FOLDER, PUBLIC, GRADING, LEDGER, read, name_for

OUT = ROOT / 'artifacts/legal_skill_evolution_MAUD_revision_20261114'


def main():
    assert read(FOLDER / 'TERMINAL_PRESERVATION.json')['fixed_study_complete']
    p = read(FOLDER / 'protocol.json')
    acquisition = set(p['acquisition_sources'])
    public = {s['key']: s for s in read(PUBLIC) if s['key'] in acquisition}
    assert set(public) == acquisition
    grading = {k: v for k, v in read(GRADING).items() if k in acquisition}
    library = read(FOLDER / 'ConstraintAcquire/compiled.json')
    original = digest(library)
    records = [read(FOLDER / 'acquisition/ConstraintAcquire' / name_for(k, v))
               for k in p['acquisition_sources'] for v in public[k]['views']]
    assert len(records) == 12 and {r['source'] for r in records} == acquisition
    observations = [attach_scored_theories(r['observation'], r['profile']) for r in records]
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        before = db.execute('select * from calls order by id').fetchall()
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/relational_learning.py',
             ROOT / 'legal_skill_guard/skill_evolution/open_acquisition.py',
             FOLDER / 'ConstraintAcquire/compiled.json', FOLDER / 'ConstraintAcquire/fit.json']
    files += [FOLDER / 'acquisition/ConstraintAcquire' / name_for(k, v)
              for k in p['acquisition_sources'] for v in public[k]['views']]
    immutable_json(OUT / 'protocol.json', {
        'source_and_input_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'acquisition_sources_only': p['acquisition_sources'], 'native_views': 12,
        'objective': ['native_loss', 'selection_edits_from_actual_proposed_G', 'complexity'],
        'future_pair_not_executed_or_scored': True, 'new_model_requests': 0,
        'not_a_third_contribution_or_fresh_generalization_test': True})
    updated, result = fit(library, observations, timeout_seconds=90,
                          prior_rule_ids=library['suggested_rule_ids'])
    assert result['status'] == 'sat' and result['native_loss'] == 0
    assert result['selection_edits'] == 0
    assert sorted(updated['selected_rule_ids']) == sorted(library['suggested_rule_ids'])
    rows = []
    for r in records:
        source = public[r['source']]
        view = next(v for v in source['views'] if v['id'] == r['view'])
        actual = evaluate_view(updated, r['observation'], source, view, grading[r['source']][r['view']])
        assert actual['feedback']['views'][0]['score']['correct']
        immutable_json(OUT / 'execution' / name_for(r['source'], view), actual)
        rows.append({'source': r['source'], 'view': r['view'], 'correct': True})
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        after = db.execute('select * from calls order by id').fetchall()
    assert after == before and digest(library) == original
    immutable_json(OUT / 'fit.json', result)
    immutable_json(OUT / 'library.json', updated)
    immutable_json(OUT / 'result.json', {
        'old_MDL_selected_rule_ids': read(FOLDER / 'ConstraintAcquire/fit.json')['selected_rule_ids'],
        'revision_selected_rule_ids': updated['selected_rule_ids'], 'acquisition_native_correct': 12,
        'acquisition_native_total': 12, 'selection_edits': 0, 'rows': rows,
        'all_previous_ledger_rows_unchanged': len(before), 'calls_sha256': digest(before),
        'new_model_requests': 0, 'future_pair_not_reexecuted': True,
        'remaining_source_role_errors_not_solved': True, 'extra_C_or_U_gain_established': False,
        'goal_complete': False})
    print('Actual12-view regression: native12/12, all10 proposed mappings retained; zero inference; no future-pair rerun.', flush=True)


if __name__ == '__main__':
    main()
