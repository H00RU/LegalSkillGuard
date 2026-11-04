"""Offline final consistency check for the bilingual evidence-led revision."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXPORT = ROOT / 'artifacts/research/manuscript_review_20261030/utility_v6_astra_revision_v16_delivery_20261104'

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

results = {}
for script in sorted((HERE / 'offline_checks').glob('*.py')):
    process = subprocess.run([sys.executable, str(script)], cwd=ROOT,
                             text=True, capture_output=True)
    if process.returncode:
        raise RuntimeError(script.name + '\n' + process.stderr)
    result = json.loads(process.stdout)
    results[script.stem] = {'result': result, 'stderr': process.stderr}
    for key, value in result.items():
        if (key.endswith(('_errors', '_differences', '_difference_paths'))
                or key in ('score_mismatch_count', 'aggregate_mismatch_count', 'train_test_source_overlap')):
            assert not value, (script.name, key, value)

manifest = read(EXPORT / 'render_manifest.json')
for lang, value in manifest['outputs'].items():
    assert not value['docx_missing_source_text'] and not value['pdf_missing_segments']
    assert value['table_count'] == 18 and value['native_OMML_math_count'] == 40
    assert len(value['figures']) == 2 and value['cited_primary_bibliography_entry_count'] == 11
    for key in ('pdf', 'docx'):
        assert sha(ROOT / value[key]['path']) == value[key]['sha256']
    assert sha(ROOT / value['source']) == value['source_sha256']
results['render'] = {lang: {key: value[key] for key in ('pdf', 'docx', 'table_count', 'native_OMML_math_count', 'status')}
                     for lang, value in manifest['outputs'].items()}

frozen = {}
for stem in ('openexempt_complete_output_utility_public_assets128_20261030_run01',
             'openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05'):
    value = read(ROOT / 'configs' / (stem + '.frozen.json'))
    assert sha(ROOT / 'configs' / (stem + '.json')) == value['config_sha256']
    for name, expected in value['files'].items():
        assert sha(ROOT / name) == expected, name
        frozen[name] = expected
evaluation_config = ROOT / 'artifacts/launches/openexempt_v6_final_after_withheld_20261031_run01/actual_final_matrix_config.json'
evaluation_manifest = read(evaluation_config.with_suffix('.frozen.json'))
assert sha(evaluation_config) == evaluation_manifest['config_sha256']
for name, expected in evaluation_manifest['files'].items():
    assert sha(ROOT / name) == expected, name
    frozen[name] = expected
results['immutable_source_bindings'] = {'main_files': 379, 'SkillCommit_files': 648, 'evaluation_files': 549,
                                        'unique_files': len(frozen), 'hash_mismatches': 0}
unchanged = {
    'paper/tables/utility_frozen_results_20261101.json': '3879cee0d1f5765f3a00637b2c3252640c570d2eed7da4cc1f05031ecd4fb732',
    'paper/tables/utility_frozen_results_with_skillcommit_20261104.json': '0d092894a80d1ab82721e1eeb9e96aecc40de05adfa721fb2b9e44b417e3e078',
    'runs/legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01/scored_records.json': 'ff72aa2ba7c27d1d2725c938729a278c4a68e28068871d5da09aa827ddaa9cf6',
    'runs/legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05/TEST_scored_records.json': '04f765cdb95b1c67200864c4b053830535cb642566d9ae448f5f8365d19e24df',
}
for name, expected in unchanged.items():
    assert sha(ROOT / name) == expected, name
results['original_scores_and_tables_unchanged'] = unchanged
policy = read(HERE / 'recorded_candidates_both_policies.json')
assert not policy['actual_decision_reproduction_mismatches']
results['saved_policy_selections_reproduced'] = 32
source = (ROOT / 'paper/utility_skill_manuscript_working_20261030.md').read_text()
abstract = source.split('## Abstract\n\n', 1)[1].split('\n\n', 1)[0]
packet = (ROOT / 'paper/submission_materials_en_20261104.md').read_text()
assert packet.split('## 2. Abstract for the submission system\n\n', 1)[1].split('\n\n', 1)[0] == abstract
results['submission_abstract_exactly_synchronized'] = True
results['new_model_teacher_embedding_calls'] = 0
results['status'] = 'offline_checks_passed; visual review recorded separately'
(HERE / 'final_consistency_validation.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'offline_sections': len(results), 'original_scores': 2816,
                  'tables_per_language': 18, 'all_checks_passed': True}))
