"""Reconcile recorded identities without opening sealed TEST annotations."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
PATTERN = re.compile(r'(?:OpenExempt|SARA_v2_Binary|ContractNLI|RuleArena_Airline|MAUD):[0-9a-f]{64}')


def main():
    frozen = ROOT / 'artifacts/legal_skill_evolution_20261111/frozen_test_v1'
    if (frozen / 'native_materialization.json').exists():
        print(json.dumps({'qualification_snapshot_preserved': True,
            'reason': 'B8 materialization already exists; authorized frozen evaluation does not retroactively contaminate its qualification snapshot',
            'new_model_calls': 0}))
        return
    manifest_path = ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    original = {r['key'] for dataset in manifest['datasets'].values() for r in dataset['test']}
    prequalified = json.loads((REPORT / 'CNLI_TEST_replacement_prequalification.json').read_text())
    exposed = prequalified['replaces']['key']
    replacement = prequalified['prequalified_replacement']
    qualified = (original - {exposed}) | {replacement['key']}
    assert len(original) == len(qualified) == 160 and exposed in original
    teacher_paths = set()
    for root in (Path('/home/yndx/hhy/legal-skill-current'), ROOT):
        teacher_paths.update((root / 'runs').glob('*/teacher/**/wire_request.json'))
        teacher_paths.update((root / 'artifacts/rr_v2_preflight').glob('**/request.json'))
        teacher_paths.update((root / 'artifacts/legal_skill_evolution_20261111').glob('*/calls/*/request.json'))
    scanned, hits, prompt_hashes = [], [], set()
    for path in sorted(teacher_paths):
        raw = path.read_bytes()
        value = json.loads(raw)
        prompt = value.get('user_prompt')
        if not isinstance(prompt, str):continue
        combined = value.get('system_prompt', '') + '\n' + prompt
        prompt_hashes.add(hashlib.sha256(combined.encode()).hexdigest())
        keys = set(PATTERN.findall(combined))
        match = sorted(keys & qualified)
        if match:hits.append({'request_path': str(path), 'qualified_TEST_identity_mentions': match})
        scanned.append({'request_path': str(path), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(), 'current_original_TEST_key_mentions': sorted(keys & original)})
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        direct = [{'id': i, 'role': role, 'source': source, 'purpose': purpose, 'status': status}
            for i, role, source, purpose, status in db.execute('select id,role,source,purpose,status from calls')
            if source in qualified]
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'sealed_TEST_annotation_files_opened': False, 'native_TEST_answers_accessed': False,
        'original_manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'fixed_TRAIN_and_DEV_changed': False, 'source_count': 160,
        'known_exposed_removed_for_confirmatory_freeze': prequalified['replaces'],
        'predeclared_hash_order_replacement': replacement,
        'qualified_TEST_source_keys': sorted(qualified),
        'teacher_request_key_audit': {'requests': scanned, 'request_artifact_file_count': len(scanned),
            'distinct_system_user_prompt_count': len(prompt_hashes),
            'artifact_copies_are_not_physical_request_counts': True,
            'qualified_identity_mentions_for_review': hits},
        'native_ContractNLI_archive_sha256_before_TEST': hashlib.sha256(
            (ROOT / 'data/cache/rr_v2/contract-nli.zip').read_bytes()).hexdigest(),
        'native_archive_integrity_hash_only_no_annotation_deserialization': True,
        'continuous_ledger_qualified_TEST_requests': direct,
        'previous_native_ID_mother_and_fulltext_audits_still_required': [
            'CNLI_historical_mother_identity_audit.json', 'historical_teacher_exposure_audit.json',
            'CNLI_TEST_replacement_prequalification.json', 'OE_historical_law_only_packet_audit.json',
            'old_parameter_training_manifest_identity_audit.json'],
        'qualification_scope': 'recorded project exposure, including canonical mother identity; no model-pretraining or unrecorded-external-activity claim',
        'not_B8_freeze': True, 'native_materialization_and_hash_checks_deferred_until_B8': True}
    (REPORT / 'qualified_TEST_identity_plan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'teacher_request_artifact_files_checked': len(scanned),
        'distinct_prompt_inputs': len(prompt_hashes), 'qualified_identity_mentions': len(hits),
        'direct_qualified_TEST_requests': len(direct), 'sealed_TEST_opened': False,
        'qualified_source_counts': {d: sum(k.startswith(d + ':') for k in qualified) for d in manifest['datasets']}}))


if __name__ == '__main__':main()
