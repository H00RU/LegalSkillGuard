"""Read-only final audit of this fixed-material intervention. No generation."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3

from legal_skill_guard.rr.atom_frontend import decode_atom_response
from legal_skill_guard.rr.compiler_evolution import promote_verified_horn
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.model_horn import assess_model_horn

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
OLD_ROOT = Path('/home/yndx/hhy/legal-skill-ir-repair-20261108')
OLD_REL = Path('artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109')
OLD_LEDGER = Path('/media/sangfor/vdb/legal-skill-backups/rr-reference-v26-final-pivbzbhd/ledger.final.sqlite3')


def read(path):
    return json.loads(path.read_text())


def main():
    baseline = read(REPORT / 'baseline.json')
    for rel, expected in baseline['previous_stage_files'].items():
        assert hashlib.sha256((OLD_ROOT / OLD_REL / rel).read_bytes()).hexdigest() == expected, rel
    old_seal = read(OLD_ROOT / OLD_REL / 'seal.json')
    for rel, expected in old_seal['files'].items():
        assert hashlib.sha256((OLD_ROOT / rel).read_bytes()).hexdigest() == expected, rel
    version_map = read(ROOT / 'artifacts/rr_method_efficacy_20261109/source_version_overlays.json')
    for version in version_map.values():
        seal = read(ROOT / version['seal'])
        overlays = {r['path']: r for r in version['overlays_from_final_public_source']}
        for rel, expected in seal['files'].items():
            path = ROOT / (overlays[rel]['archived_bytes'] if rel in overlays else rel)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, rel
    current_ledger = (ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3').resolve()
    with sqlite3.connect('file:' + str(current_ledger) + '?mode=ro', uri=True) as db:
        db.execute('begin')
        current = {r[0]: r for r in db.execute('select * from calls')}
        current_meta = dict(db.execute('select * from meta'))
        current_oracles = set(db.execute('select * from oracle_views'))
    with sqlite3.connect('file:' + str(OLD_LEDGER) + '?mode=ro', uri=True) as db:
        previous = {r[0]: r for r in db.execute('select * from calls')}
        previous_meta = dict(db.execute('select * from meta'))
        previous_oracles = set(db.execute('select * from oracle_views'))
    assert all(current[k] == v for k, v in previous.items())
    assert all(current_meta[k] == v for k, v in previous_meta.items())
    assert current_oracles == previous_oracles
    new = [v for k, v in current.items() if k not in previous]
    assert Counter(r[1] for r in new) == {'executor': 5, 'teacher': 3}
    assert not any(r[6] == 'reserved' for r in current.values())
    cost = read(REPORT / 'cost_and_preservation.json')
    assert {c['id'] for c in cost['calls']} == {r[0] for r in new}
    assert dict(Counter(r[1] for r in current.values())) == cost['current_counts']
    public = {s['key']: s for split in ('train', 'dev') for s in
              read(ROOT / f'data/packets/rr_v2/public_{split}.json')['sources']}
    stage = ROOT / 'artifacts/rr_method_efficacy_20261109/efficacy_compiler_updates_v1_20261109'
    evolution = read(stage / 'seal.json')
    train = set(old_seal['sources']['train'])
    admitted = []
    for item in evolution['admission']:
        assert item['source'] in train
        assert old_seal['sources']['train'][item['ordinal'] - 1] == item['source']
        if item['origin']['role'] != 'executor':
            continue
        record = read(OLD_ROOT / OLD_REL / 'build/sources' / (digest(item['source']) + '.json'))
        template = promote_verified_horn(public[item['source']], record,
                    train_sources=train, ledger_path=current_ledger)
        assert template['template_hash'] == item['template_hash']
        admitted.append(template['template_hash'])
    assert len(admitted) == 21
    snapshots = {}
    for variant, expected in [('B1', 6), ('B8', 25)]:
        path = stage / (variant + '.frozen.json')
        frozen = read(path)
        restored = SkillLibrary.restore(path).export()
        assert restored == frozen['content'] and digest(restored) == frozen['sha256']
        assert len(restored['compiler_templates']) == expected
        for template in restored['compiler_templates']:
            assert template['source']['key'] in train
        result = read(stage / (variant + '.json'))
        parsed, _ = decode_atom_response(public[result['source']],
                     json.loads(result['physical_response']['content']))
        assert not parsed.export()['missing_units']
        rechecked = assess_model_horn(parsed, interface='ordinary_IO_local_binding_repair')
        assert rechecked == result['result']
        assert rechecked['answer'] == 'Unknown' and not rechecked['fallback_used']
        assert not rechecked['B_main_path_executed']
        selected = result['selected_examples']
        assert len(selected) == 1
        assert selected[0] in {t['template_hash'] for t in restored['compiler_templates']}
        snapshots[variant] = {'templates': expected, 'sha256': frozen['sha256'],
                              'source_checked_real_IR': True, 'answer': rechecked['answer']}
    audit = {
        'checked_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'fixed_material_diagnosis_and_selected_revisions_verified',
        'recommendation': 'Do not run formal TEST for the current A/B-specific core claims; stop for review',
        'previous_stage_files_unchanged': len(baseline['previous_stage_files']),
        'previous_science_manifest_files_unchanged': len(old_seal['files']),
        'previous_science_binding': old_seal['code_hash'],
        'new_run_sealed_source_versions_recoverable_with_exact_overlays': len(version_map),
        'original_call_rows_unchanged': len(previous),
        'original_meta_values_unchanged': len(previous_meta),
        'oracle_rows_exactly_unchanged': len(current_oracles),
        'counts_total': cost['current_counts'], 'new_ledger_entries': len(new), 'pending': 0,
        'verified_executor_template_admissions_reproduced': len(admitted),
        'frozen_snapshots_restored_exactly': snapshots,
        'DEV_programs_or_labels_used_for_admission': False,
        'new_models_or_oracles_called_by_this_audit': 0,
        'TEST_started': False, 'paper_started': False,
        'old_128_source_build_or_six_arm_DEV_repeated': False,
        'targeted_regression': '79 passed in 9.32s; see final_targeted_regression.txt',
        'current_A_B_unique_method_advantage_established': False,
        'goal_complete_before_publication_verification': False,
    }
    (REPORT / 'delivery_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in audit.items() if k != 'frozen_snapshots_restored_exactly'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
