"""Read-only source-acquisition comparison and cumulative-ledger preservation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.legal_support_ranges import INPUTS, compare_support_functions, evaluate_pal

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'reports/method_redesign_20261109'
INITIAL = 'legal_support_acquisition_v1_20261110'
RUN = 'legal_support_teacher_v1_20261110'
STAGE = ROOT / 'artifacts/rr_method_redesign_20261109' / RUN
BEFORE = '62339e3ea0357313d9ac923220bce86c43efde49fe60f7964cb1c5e08df89154'


def read(path):
    return json.loads(path.read_text())


def main():
    seal = read(STAGE / 'seal.json')
    for path, expected in seal['files'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
    protocol = REPORT / 'legal_support_teacher_protocol.md'
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == seal['protocol_sha256']
    assert seal['case_facts_queries_answers_or_DEV_provided'] is False
    original = ROOT / 'artifacts/rr_method_redesign_20261109' / INITIAL
    old_seal = read(original / 'seal.json')
    for path, expected in old_seal['files'].items():
        assert hashlib.sha256((original / 'frozen_source' / path).read_bytes()).hexdigest() == expected, path
    assert hashlib.sha256((REPORT / 'legal_support_acquisition_protocol.md').read_bytes()).hexdigest() == old_seal['protocol_sha256']
    dbpath = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(dbpath) + '?mode=ro', uri=True) as db:
        snapshot = {t: db.execute('select * from ' + t + ' order by 1').fetchall()
                    for t in ('calls', 'meta', 'oracle_views')}
        counts = dict(db.execute('select role,count(*) from calls group by role'))
        pending = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
        raw = db.execute('select id,role,source,status,result from calls order by reserved_at,id').fetchall()
    historic = {k: list(v) for k, v in snapshot.items()}
    historic['calls'] = [x for x in historic['calls'] if not x[0].startswith((INITIAL + ':', RUN + ':'))]
    historic['meta'] = [x for x in historic['meta'] if x[0] not in ('method_runtime_policy:' + INITIAL, 'method_runtime_policy:' + RUN)]
    h = hashlib.sha256(json.dumps(historic, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert h == BEFORE, 'A pre-acquisition ledger/meta/oracle row changed'
    assert pending == 0, 'Do not publish a terminal comparison with an unresolved request'
    records = {arm: read(STAGE / (arm + '.json')) for arm in ('profile', 'pal')}
    assert not (STAGE / 'review.json').exists(), 'No optional review was dispatched after provenance rejection'
    calls = []
    for cid, role, source, status, result in raw:
        if not cid.startswith((INITIAL + ':', RUN + ':')):
            continue
        w = json.loads(result)
        usage = w.get('usage') or w.get('invocation', {}).get('usage') or {}
        calls.append({'id': cid, 'role': role, 'source': source, 'status': status,
                      'input_tokens': usage.get('prompt_tokens', usage.get('input_tokens')),
                      'output_tokens': usage.get('completion_tokens', usage.get('output_tokens')),
                      'reasoning_output_tokens_subset': usage.get('reasoning_output_tokens'),
                      'elapsed_seconds': w.get('elapsed_seconds'),
                      'physical_dispatch_occurred': False if cid == INITIAL + ':review' else True,
                      'finish_reason': w.get('finish_reason'),
                      'thinking_requested': w.get('thinking_requested'),
                      'client_retries': 0, 'ledger_attempt_charged': True})
    assert len(calls) == 5
    assert sum(c['status'] == 'failed' for c in calls) == 1
    assert all(c['status'] == 'completed' for c in calls if c['id'] != INITIAL + ':review')
    assert sum(c['role'] == 'executor' for c in calls) == 2
    assert all(c['thinking_requested'] is False for c in calls if c['role'] == 'executor')
    p, b = records['profile'], records['pal']
    assert p['validation']['status'] == 'structurally_valid'
    assert b['validation']['status'] == 'rejected' and b['validation']['error'] == 'PAL quote absent from source'
    # Compare the executable components; the whole PAL artifact stays rejected.
    evaluate_pal(b['value'], {k: [] for k in INPUTS}, 'focus')
    comparison = compare_support_functions(p['value'], b['value'])
    comparison['component_only_diagnostic_not_acceptance_of_rejected_artifact'] = True
    assert comparison['equivalent_for_all_abstract_input_sets']
    quote_errors = [{'index': i, 'actual': q, 'expected': 'verbatim supplied source substring'}
                    for i, q in enumerate(b['value']['quotes'])
                    if not any(q in text for text in seal['material']['source_blocks'].values())]
    assert len(quote_errors) == 1
    service = Path('/proc/958223/stat').read_text()
    start_ticks = int(service[service.rindex(')')+2:].split()[19])
    assert start_ticks == 486445918
    clients = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc/'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if b'-m' in argv and any(a.startswith(b'experiments.rr_v2_legal_support') for a in argv):
            clients.append(int(proc.name))
    assert clients == [], 'An acquisition client is still live'
    summary = {}
    for role in ('executor', 'teacher'):
        subset = [c for c in calls if c['role'] == role and c['status'] == 'completed']
        summary[role] = {k: sum(c[k] for c in subset)
                         for k in ('input_tokens', 'output_tokens', 'elapsed_seconds')}
    out = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'run_id': RUN,
           'counts_total': counts, 'pending': pending,
           'new_charged_attempts': {'executor': 2, 'teacher': 3},
           'new_physical_dispatches': {'executor': 2, 'teacher': 2},
           'local_teacher_schema_preflight_failure_retained_as_charged_attempt': 1, 'calls': calls,
           'cost_sums': summary, 'all_pre_acquisition_logical_rows_preserved_sha256': h,
           'new_oracle_views': 0, 'no_ledger_reset': True,
           'current_acquisition_clients': clients,
           'original_model_service': {'pid':958223, 'start_ticks':start_ticks, 'unchanged':True},
           'common_TRAIN_material_sha256': hashlib.sha256(json.dumps(
               seal['material'], sort_keys=True).encode()).hexdigest(),
           'independent_acquisitions_same_exogenous_material': True,
           'case_facts_queries_or_answers_in_acquisition': False,
           'profile_validation': p['validation'], 'pal_validation': b['validation'],
           'initial_executor_profile_rejected': read(original / 'profile.json')['validation'],
           'initial_executor_pal_original_short_circuit_validation_was_incorrect': True,
           'initial_executor_pal_after_fix': 'rejected: undeclared support name knowndeduction151',
           'original_failed_outputs_or_ledger_rows_overwritten': False,
           'exact_abstract_range_function_comparison': comparison,
           'optional_shared_teacher_review_dispatched': False,
           'reason_review_not_dispatched': 'Original protocol requires both full artifacts valid; flat artifact has a nonverbatim quote. No retry purchased to manufacture acceptance.',
           'pal_source_quote_failures': quote_errors,
           'rejected_pal_expression_or_quotes_repaired': False,
           'source_semantics_check': {
               'kind': 'researcher_read_only_source_obligation_check_not_formal_NL_proof',
               '151a': 'Every exemption claimant is forwarded to deduction151.',
               '151b': 'Any direct151b claimant is focus or a spouse peer; ignored conditions can only shrink entitlement.',
               '151c_152a': 'The dependency path preserves the claimant/subject/year projection and includes explicit positive interface seeds.',
               '152c': 'Relationship and shared-abode are necessary; their conservative supersets may be intersected. Unknown relevant peers remain TOP.',
               '152d': 'Enumerated family/in-law or household candidates cover the necessary relationship alternatives; other conditions only restrict them.',
               '151d_152b': 'Amounts and disqualifications introduce no new positive claimant.',
               'assumptions': ['supplied simplified TRAIN statutes only', 'declared input families are sound upper bounds', 'unread relevant anchors are TOP', 'no population closure from mentioned names'],
               'does_not_prove_anchor_extractor_completeness': True},
           'candidate_promoted': False,
           'decision': 'Source-compiler feasibility established; independent compact executable component is exactly equivalent. Whole flat artifact rejected for provenance, so do not claim full acquisition parity or a summary win. No more same-purpose calls.',
           'manual_reference_anchor_frame_is_not_a_native_neural_success': True,
           'native_four_case_predictions_unchanged': True,
           'known_executor_incremental_API_cash_usd': 0, 'GPU_cash_cost_usd': None,
           'teacher_invoice_cash_cost_usd': None, 'total_cash_cost_usd': None,
           'provider_internal_teacher_retries': 'not observable',
           'new_full_build_started': False, 'TEST_started': False, 'goal_complete': False}
    path = REPORT / 'legal_support_acquisition_results.json'
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
