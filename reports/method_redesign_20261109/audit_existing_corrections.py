"""Fixed TRAIN only: what actual correction material exists for design card2?"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
from legal_skill_guard.rr.coverage import digest

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109'
REPORT = Path(__file__).resolve().parent


def main():
    seal = json.loads((OLD / 'seal.json').read_text())
    source_review = {r['source']: r['kind'] for r in json.loads((ROOT / 'reports/rr_method_runtime_20261107/reference_uniform_v10_current_primary_source_semantics.json').read_text())['rows']}
    public = {s['key']: s for s in json.loads((ROOT / 'data/packets/rr_v2/public_train.json').read_text())['sources']}
    rows = []
    for ordinal, key in enumerate(seal['sources']['train'], 1):
        record = json.loads((OLD / 'build/sources' / (digest(key) + '.json')).read_text())
        prediction = record['prediction']
        path = OLD / 'build/journals' / digest(key) / 'state0.json'
        initial = json.loads(json.loads(path.read_text())['state_json'])
        before, after = initial.get('program'), prediction.get('program')
        source_pair = bool(initial['compiled_valid'] and isinstance(before, dict) and isinstance(after, dict))
        changed = [name for name in sorted(set(before or {}) | set(after or {})) if (before or {}).get(name) != (after or {}).get(name)] if source_pair else []
        before_residuals = {r['name'] for r in (before or {}).get('rule_residuals', [])} if isinstance(before, dict) else set()
        after_residuals = {r['name'] for r in (after or {}).get('rule_residuals', [])} if isinstance(after, dict) else set()
        rows.append(dict(ordinal=ordinal, source=key, dataset=record['dataset'],
            policy_hash=digest(public[key]['public'].get('rules', public[key]['public'].get('document', public[key]['public'].get('views')))),
            calls_in_original_prediction=len(prediction['calls']),
            final_program_status=prediction['result']['program_status'],
            final_fallback=prediction['result']['fallback_used'],
            prior_independent_source_review=source_review.get(key),
            executable_source_program_before_and_after=source_pair,
            changed_program_fields=changed,
            rule_residuals_removed=sorted(before_residuals - after_residuals) if source_pair else [],
            observations_changed=initial.get('observation_rows') != prediction.get('observation_rows'),
            complete_function_equivalence_reference_available=False,
            note='Prior source review of a given legal query is not a universal input-domain reference. Horn source equivalence is a separate, already grammar-supported task.'))
    revised = [r for r in rows if r['changed_program_fields']]
    verified_legal = [r for r in revised if r['prior_independent_source_review'] and r['dataset'] != 'ProofWriter_OWA_depth5']
    value = dict(captured_utc=datetime.now(timezone.utc).isoformat(), fixed_TRAIN_sources_audited=len(rows),
        source_program_revisions=len(revised), revisions_by_dataset=dict(Counter(r['dataset'] for r in revised)),
        revised_legal_sources_with_prior_query_semantic_review=[r['ordinal'] for r in verified_legal],
        complete_generic_legal_function_correction_pairs_established_by_original_query_review=0,
        conclusion='The existing build does not by itself provide a multi-origin universally reviewed legal repair corpus. Use raw pairs and source obligations, not case-label matches, before claiming learned source-parametric repair.',
        model_or_oracle_calls=0, DEV_or_TEST_labels_read=False, goal_complete=False, rows=rows)
    (REPORT / 'existing_correction_opportunities.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in value.items() if k != 'rows'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
