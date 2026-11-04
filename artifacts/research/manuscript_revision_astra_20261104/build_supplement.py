"""Package existing evidence; never execute an actor or modify original records."""
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PACKAGE = HERE / 'Supplementary_Data_1_20261104.zip'
BUILDING = PACKAGE.with_name(PACKAGE.stem + '.building.zip')

def read(path):
    return json.loads((ROOT / path).read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

files = set()
frozen_checks = {}
# Include the complete local Python module closure, not only each experiment's
# explicit binding list. Auxiliary imports can be needed for offline analysis.
for directory in ['experiments', 'legal_skill_guard', 'third_party']:
    files.update(str(p.relative_to(ROOT)) for p in (ROOT / directory).rglob('*.py')
                 if '__pycache__' not in p.parts and '.git' not in p.parts)
for stem in ['openexempt_complete_output_utility_public_assets128_20261030_run01',
             'openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05']:
    manifest = read('configs/' + stem + '.frozen.json')
    for name, expected in manifest['files'].items():
        assert digest(ROOT / name) == expected, name
        if name in frozen_checks:
            assert frozen_checks[name] == expected, name
        frozen_checks[name] = expected
        files.add(name)
    files.update('configs/' + stem + suffix for suffix in ['.json', '.frozen.json'])

matrix_path = 'artifacts/launches/openexempt_v6_final_after_withheld_20261031_run01/actual_final_matrix_config.json'
matrix = read(matrix_path)
files.add(matrix_path)
evaluation_manifest_path = str(Path(matrix_path).with_suffix('.frozen.json'))
evaluation_manifest = read(evaluation_manifest_path)
files.add(evaluation_manifest_path)
assert digest(ROOT / matrix_path) == evaluation_manifest['config_sha256']
for name, expected in evaluation_manifest['files'].items():
    assert digest(ROOT / name) == expected, name
    if name in frozen_checks:
        assert frozen_checks[name] == expected, name
    frozen_checks[name] = expected
    files.add(name)
for arm in matrix['arms']:
    if 'source_config' not in arm:
        continue
    cfg_path = arm['source_config']
    files.update([cfg_path, str(Path(cfg_path).with_suffix('.frozen.json'))])
    cfg = read(cfg_path)
    run = ROOT / 'runs' / cfg['run_id']
    for name in ['completion.json', 'initialization.json', 'terminal_preservation.json']:
        if (run / name).is_file():
            files.add(str((run / name).relative_to(ROOT)))
    if (run / 'publications').is_dir():
        files.update(str(p.relative_to(ROOT)) for p in (run / 'publications').glob('*.json'))

for name in [
    'legal_openexempt_complete_output_utility_public_assets128_20261030_run01',
    'legal_openexempt_v6_strict_policy_control_public_assets128_20261030_run01',
    'legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05',
    'legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01',
]:
    files.update(str(p.relative_to(ROOT)) for p in (ROOT / 'runs' / name).rglob('*') if p.is_file())

for name in ['openexempt_closed_feedback_public_assets128_20261021',
             'openexempt_IID128_confirmatory_TEST_20261030']:
    files.update(str(p.relative_to(ROOT)) for p in (ROOT / 'data/packets' / name).rglob('*') if p.is_file())
for directory in ['paper/tables', 'paper/figures/utility_learning_curves_20261030',
                  'paper/figures/utility_method_overview_20261030']:
    files.update(str(p.relative_to(ROOT)) for p in (ROOT / directory).rglob('*') if p.is_file())
files.update([
    'paper/utility_skill_manuscript_working_20261030.md',
    'paper/sections-zh/utility_skill_manuscript_working_20261030.md',
    'paper/utility_skill_references_20261030.bib',
    'paper/render_utility_review.py',
    'paper/submission_materials_en_20261104.md',
    'paper/README.md',
    'GITHUB_LATEST.md',
    'docs/reports/PAPER_ASTRA_REVISION_20261104.md',
    'docs/research/PAPER_REPRODUCTION_GUIDE_20261102.md',
])
export = ROOT / 'artifacts/research/manuscript_review_20261030/utility_v6_astra_revision_v16_delivery_20261104'
files.update(str(p.relative_to(ROOT)) for p in export.iterdir() if p.is_file())

# Reuse the exact previously audited offline checks. Only paths/import setup and
# table lookup (new appendix tables now precede the old tables) are adapted.
prior = read('artifacts/research/openexempt_skillcommit_20261102/manuscript_quality_review_readonly_reproduction_20261104.json')
checks = HERE / 'offline_checks'
checks.mkdir(exist_ok=True)
for section in ['all_2816_frozen_scores_and_aggregates',
                'paired_bootstraps_tables_and_training_curves',
                'raw_HTTP_decode_cost_and_source_split']:
    command = prior['sections'][section]['executed_read_only_command'].rstrip()
    assert command.startswith(".venv/bin/python - <<'PY'\n") and command.endswith('\nPY')
    code = command.split('\n', 1)[1].rsplit('\nPY', 1)[0]
    if section == 'paired_bootstraps_tables_and_training_curves':
        code = code.replace('en[3]["cells"]',
            'next(t for t in en if "Strict object match EC / EV" in t["cells"][0])["cells"]')
        code = code.replace('en[4]["cells"]',
            'next(t for t in en if t["cells"][0][0] == "Comparator")["cells"]')
        code = code.replace('en[5]["cells"]',
            'next(t for t in en if t["cells"][0][0] == "Task")["cells"]')
    prefix = ('import os, sys\nfrom pathlib import Path\n'
              'root = Path(__file__).resolve().parents[4]\n'
              'os.chdir(root)\nsys.path.insert(0, str(root))\n')
    (checks / (section + '.py')).write_text(prefix + code + '\n')

# Expose the observed scope concentration, without re-embedding or retuning.
sc = ROOT / 'runs/legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05'
library = json.loads((sc / 'publications/final.json').read_text())['library']
memories = {m['id']: m for pool in library.values() for items in pool.values() for m in items}
ev_deliveries = [json.loads(p.read_text()) for p in (sc / 'TEST_delivery').glob('*_EV.json')]
id_sets = Counter(tuple(sorted(d['memory_ids'])) for d in ev_deliveries)
assert len(ev_deliveries) == 128 and len(id_sets) == 1
selected = next(iter(id_sets))
assert all('Illinois' in memories[mid]['description']['when'] for mid in selected)
scope = {'purpose': 'Recorded deployment scope, not an intervention or causal attribution',
         'EV_tasks': 128, 'distinct_EV_selected_sets': 1,
         'selected_complete_memories': [memories[mid] for mid in selected],
         'Illinois_sources': 28, 'other_sources': 100,
         'new_embedding_or_model_calls': 0}
(HERE / 'skillcommit_delivery_scope_readout.json').write_text(json.dumps(scope, ensure_ascii=False, indent=2) + '\n')

for name in ['analyze_existing_records.py', 'render_revised_figure.py', 'build_supplement.py',
             'verify_revision.py', 'render_pdf_contact_sheets.py',
             'final_consistency_validation.json', 'visual_review_receipt.json',
             'fresh_original_scores_statistics_and_raw_records.json',
             'recorded_candidates_both_policies.json', 'all_condition_error_decomposition.json',
             'data_distribution_and_overlap.json', 'bootstrap_numerical_sensitivity_not_replacement.json',
             'all_2816_source_scores_and_claim_counts.csv', 'skillcommit_delivery_scope_readout.json',
             'SUPPLEMENT_README.md']:
    files.add(str((HERE / name).relative_to(ROOT)))
files.update(str(p.relative_to(ROOT)) for p in checks.glob('*.py'))
files.add('artifacts/research/openexempt_skillcommit_20261102/manuscript_quality_review_readonly_reproduction_20261104.json')
files.add('artifacts/research/openexempt_skillcommit_20261102/run05_terminal_public_query_retrieval_fidelity_20261104.json')
for name in ['paper/utility_skill_manuscript_working_20261030.md',
             'paper/sections-zh/utility_skill_manuscript_working_20261030.md']:
    assert (ROOT / name).is_file()
entries = []
for name in sorted(files):
    path = ROOT / name
    assert path.is_file(), name
    assert path.resolve().is_relative_to(ROOT), name
    assert not any(t in name.lower() for t in ['.env', '/.ssh/', 'api_key', 'credentials']), name
    entries.append({'path': name, 'bytes': path.stat().st_size, 'sha256': digest(path)})

manifest = {'purpose': 'Offline source and evidence supplement; no model weights or credentials',
            'files': entries, 'frozen_files_verified': len(frozen_checks),
            'additional_source_scope': 'Complete current local Python imports, captured for offline portability; original binding manifests remain unchanged',
            'scores_and_original_records_modified': False,
            'new_model_teacher_calls': 0}
with zipfile.ZipFile(BUILDING, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as z:
    z.writestr('SUPPLEMENT_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    for entry in entries:
        z.write(ROOT / entry['path'], entry['path'])
with zipfile.ZipFile(BUILDING) as z:
    for entry in entries:
        with z.open(entry['path']) as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == entry['sha256'], entry['path']
        assert digest(ROOT / entry['path']) == entry['sha256'], entry['path']
BUILDING.replace(PACKAGE)
receipt = {'package': str(PACKAGE.relative_to(ROOT)), 'package_sha256': digest(PACKAGE),
           'package_bytes': PACKAGE.stat().st_size, 'uncompressed_bytes': sum(e['bytes'] for e in entries),
           'files': len(entries), 'all_zip_members_hash_verified': True,
           'all_source_files_unchanged_during_packaging': True,
           'frozen_files_verified': len(frozen_checks), 'new_model_teacher_calls': 0}
(HERE / 'supplement_package_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt))
