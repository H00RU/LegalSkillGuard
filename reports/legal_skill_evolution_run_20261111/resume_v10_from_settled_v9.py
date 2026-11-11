"""Restore settled state; archive accidental duplicates without using them."""
import ast
import json
from pathlib import Path
import shutil
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import Library, Skill
from legal_skill_guard.skill_evolution.runtime import aligned_array_ports
from legal_skill_guard.skill_evolution.study import Study, load_json, PILOT_ARMS


def main():
    root = Path(__file__).resolve().parents[2]
    study = Study(root, load_json(root / 'configs/legal_skill_evolution_pilot_v10_20261111.json'))
    source = root / 'artifacts/legal_skill_evolution_20261111/pilot_v9'
    snapshot = source / 'source_snapshot/legal_skill_guard/skill_evolution/runtime.py'
    tree = ast.parse(snapshot.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'aligned_array_ports')
    old = {'ast': ast}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<frozen-v9-inference>', 'exec'), old)
    with sqlite3.connect('file:' + str(study.ledger.path) + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone(), 'Wait for the actual in-flight request to settle'
        before = db.execute('select role,status,count(*) from calls group by role,status').fetchall()
        duplicate_calls = db.execute("select id,role,status from calls where id like 'legal_skill_evolution_pilot_v10_%'").fetchall()
        assert len(duplicate_calls) == 2 and all(role == 'executor' and status != 'reserved' for _, role, status in duplicate_calls)
        checked, changed_rejected = 0, []
        for arm in PILOT_ARMS:
            library = Library.load(source / arm / 'B1.json')
            receipt = load_json(source / arm / 'update_B1.json')
            assert library.hash == receipt['new_library_hash']
            for skill in library.skills.values():
                assert old['aligned_array_ports'](skill) == aligned_array_ports(skill)
                checked += 1
            for entry in library.provisional_edits:
                for revision in entry.get('revisions') or []:
                    skill = Skill.from_dict(revision['new'])
                    if old['aligned_array_ports'](skill) != aligned_array_ports(skill):
                        changed_rejected.append({'arm': arm, 'candidate': entry['candidate_index'], 'skill': skill.id,
                            'not_in_accepted_library': skill.id not in library.skills,
                            'old_table_preserved_as_old_code_evidence': True})
        archive = study.folder / 'unintended_initial_replay_before_state_import'
        archive.mkdir()
        for name in (*PILOT_ARMS, 'view_results', 'native_direct_baselines'):
            destination = study.folder / name
            if destination.exists():destination.rename(archive / name)
            shutil.copytree(source / name, destination)
        for arm in PILOT_ARMS:
            receipt = load_json(study.folder / arm / 'update_B1.json')
            assert Library.load(study.library_path(arm, 1)).hash == receipt['new_library_hash']
        after = db.execute('select role,status,count(*) from calls group by role,status').fetchall()
        assert before == after
    immutable_json(study.folder / 'state_import.json', {'source_profile': 'configs/legal_skill_evolution_pilot_v9_20261111.json',
        'new_model_calls_during_import': 0, 'physical_statuses_before_after': before,
        'all_four_B1_updates_and_B2_prefix_preserved': True, 'accepted_skills_with_identical_read_contracts': checked,
        'changed_inference_for_rejected_candidates': changed_rejected,
        'unintended_duplicate_physical_requests': duplicate_calls, 'duplicate_outputs_excluded_from_original_first_attempts': True,
        'duplicate_costs_not_removed_from_ledger': True, 'cause': 'A failed migration assertion was followed by preflight/launch without checking its exit status',
        'correction': 'Import must finish and pass before any separate model launch; only accepted-library runtime identity is asserted, not rejected candidate recompilation identity'})
    hold = study.folder / 'HOLD_GENERATION'
    if hold.exists():hold.rename(archive / 'HOLD_BEFORE_STATE_IMPORT')
    print(json.dumps({'all_B1_updates_preserved': 4, 'accepted_skills_unchanged': checked,
        'new_model_calls_during_import': 0, 'unintended_duplicates_retained_and_excluded_from_scores': len(duplicate_calls)}), flush=True)


if __name__ == '__main__':
    main()
