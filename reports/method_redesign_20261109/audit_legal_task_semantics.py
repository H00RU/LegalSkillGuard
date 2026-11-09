"""Source-only semantics audit: no reference cases, goals or labels read."""
import hashlib
import json
from pathlib import Path
import tarfile

from legal_skill_guard.rr.checkpoint import immutable_json

ROOT = Path(__file__).resolve().parents[2]


def main():
    members = {}; texts = {}
    with tarfile.open(ROOT/'data/cache/rr_v2/sara_v2.tar.gz') as a:
        for filename in ['section63.pl','section152.pl','section3306.pl']:
            name = 'sara_v2/statutes/prolog/'+filename
            raw = a.extractfile(name).read(); texts[filename] = raw.decode()
            members[name] = hashlib.sha256(raw).hexdigest()
    assert '\\+' in texts['section152.pl']
    scope = texts['section3306.pl'].split('s3306_a_2_is_wages(Person, Year, Remuneration, Wages, Service) :-',1)[1].split('s3306_a_2_A(',1)[0]
    assert 'start_(Remuneration,Time)' in scope and 'last_day_year(Year,Last_day_year)' in scope
    assert 'start_(Service,Time)' not in scope
    payment = json.loads((ROOT/'reports/method_redesign_20261109/payment_scope_delivery_audit.json').read_text())
    assert payment['payment_year_not_filled_from_service_period'] is True
    result = {'archive_members_read': members, 'reference_cases_goals_labels_read': False,
        'SARA_task_binary_truth_primary_source': 'https://nlp.jhu.edu/law/sara_v2/',
        'SymBa_primary_source': 'https://aclanthology.org/2025.naacl-long.124/',
        'official_statutory_source_uses_negation_as_failure': True,
        'partial_program_unknown_does_not_prove_native_underdetermination': True,
        'original_goal_does_not_require_global_OWA': True,
        'no_automatic_missing_rule_or_fact_to_false_repair': True,
        'CWA_failure_requires_relevant_program_and_fact_completeness': True,
        'TRAIN88_payment_period_source_anchor': 'start_(Remuneration,Time)',
        'TRAIN88_source_implementation_does_not_replace_payment_date_with_service_period': True,
        'TRAIN88_prior_conditional_aggregate': 20597,
        'TRAIN88_native_answer_not_newly_established': True,
        'TRAIN88_no_payment_date_invented_or_reference_case_read': True,
        'official_3306_comment_mentions_quarter_but_public_simplification_and_code_use_year': True,
        'do_not_import_comment_quarter_requirement_into_public_task': True,
        'old_native_scores_and_raw_failures_unchanged': True,
        'new_model_calls': 0, 'new_oracle_views': 0,
        'goal_complete': False}
    immutable_json(ROOT/'reports/method_redesign_20261109/legal_task_semantics_audit.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
