"""Replay the bounded ordinary fact search and check immutable cumulative history."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tarfile

from experiments.rr_v2_legal_fact_boundary import ROOT, RUN, STAGE, offline, parse_search
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest

REPORT = ROOT/'reports/method_redesign_20261109'
BEFORE = Path('/media/sangfor/vdb/legal-skill-backups/legal_independent_cache_20261110/ledger.after.sqlite3')
BACKUP = Path('/media/sangfor/vdb/legal-skill-backups/legal_fact_boundary_20261110')
DB = ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'


def read(p): return json.loads(p.read_text())


def snapshot(p):
    with sqlite3.connect('file:'+str(p)+'?mode=ro', uri=True) as c:
        return {t: c.execute('select * from '+t+' order by 1').fetchall() for t in ('calls','meta','oracle_views')}


def source_semantics():
    # Read source-law members only; never extract reference cases/goals/labels.
    result = {}
    with tarfile.open(ROOT/'data/cache/rr_v2/sara_v2.tar.gz') as archive:
        for filename in ['section63.pl', 'section152.pl']:
            name = 'sara_v2/statutes/prolog/'+filename
            raw = archive.extractfile(name).read(); text = raw.decode(); lines = text.splitlines()
            result[filename] = {'archive_member': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                'negation_as_failure_lines': [{'line': i+1, 'text': line.strip()} for i, line in enumerate(lines) if '\\+' in line]}
    assert result['section152.pl']['negation_as_failure_lines']
    return {'official_source_uses_negation_as_failure': True, 'source_law_files_only': result,
            'original_task_has_binary_truth': True,
            'partial_compilation_is_NOT_certified_complete_CWA_program': True,
            'unknown_from_our_partial_program_is_not_proof_of_native_task_underdetermination': True,
            'benchmark_CWA_does_NOT_authorize_defaulting_after_generation_or_extraction_failure': True,
            'native87_previous_unknown_and_grade_unchanged': True,
            'new_native_predictions_or_grades': 0,
            'official_task_definition': 'https://nlp.jhu.edu/law/sara_v2/',
            'official_paper': 'https://aclanthology.org/2021.acl-long.213/',
            'interpretation': 'Future controls must use the original dataset semantics. Strong negatives/unknown in the current partial Horn module are a module design choice, not a new global Goal acceptance criterion. Proving CWA failure requires the relevant programme/facts to be complete; no silent fallback or missing-premise-to-false repair.'}


def main():
    before = snapshot(BEFORE); current = snapshot(DB); old = deepcopy(current)
    old['calls'] = [r for r in old['calls'] if not r[0].startswith(RUN+':')]
    old['meta'] = [r for r in old['meta'] if r[0] != 'method_runtime_policy:'+RUN]
    assert old == before and len(current['calls']) == len(before['calls'])+2
    assert len(current['oracle_views']) == 134
    assert not [r for r in current['calls'] if r[6] == 'reserved']
    seal = read(STAGE/'seal.json'); checks = offline(); assert checks == read(STAGE/'offline.json')
    frozen = {}
    for p, expected in seal['files'].items():
        raw = (ROOT/p).read_bytes(); assert hashlib.sha256(raw).hexdigest() == expected
        dest = STAGE/'frozen'/p; dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert dest.read_bytes() == raw
        else: dest.write_bytes(raw)
        frozen[p] = expected
    rows = []; wires = []
    for n in ['13', '81']:
        value = read(STAGE/f'fact_search_{n}.json'); w = value['physical_response']; wires.append(w)
        assert w['thinking_requested'] is False and w['finish_reason'] == 'stop'
        assert w['reasoning_content'] in [None, '']
        parsed = parse_search(w['content'], seal['cases'][n]['public']['facts'])
        assert parsed == value['search_parse']
        if n == '13': assert parsed['status'] == 'no_direct_fact'
        else:
            assert parsed['selections'] == ["Bob counts as Alice's dependent under section 152(c)(1) for 2015."]
            assert parsed['all_verbatim']
        rows.append({'existing_TRAIN_ordinal': int(n), 'source': seal['cases'][n]['key'],
                     'response': w['content'], 'result': parsed, 'task_prediction': None,
                     'ordinary_prompt_not_new_mechanism': True})
    semantics = source_semantics()
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(),
        'counts_total': {r: sum(c[1] == r for c in current['calls']) for r in ['executor','teacher']},
        'pending': 0, 'new_charged_attempts': {'executor': 2, 'teacher': 0},
        'new_physical_dispatches': {'executor': 2, 'teacher': 0},
        'all_pre_turn_rows_equal_backup': True, 'pre_turn_counts': {k: len(v) for k,v in before.items()},
        'all_pre_turn_rows_preserved_sha256': digest(old), 'current_ledger_logical_sha256': digest(current),
        'new_TRAIN_oracle_views': 0, 'rows': rows, 'offline': checks, 'source_semantics': semantics,
        'bound_source_copies': frozen,
        'executor_prompt_tokens': sum(w['usage']['prompt_tokens'] for w in wires),
        'executor_output_tokens': sum(w['usage']['completion_tokens'] for w in wires),
        'executor_request_elapsed_seconds': sum(w['elapsed_seconds'] for w in wires),
        'executor_incremental_API_cash_usd': 0, 'teacher_actual_cash_invoice_usd': None,
        'GPU_cost_usd': None, 'total_project_cash_cost_usd': None,
        'synthetic_validator_probe_not_real_model_failure': True,
        'negative_examples_and_API_meaning_given_to_ordinary_control': True,
        'unsupported_qualification_observed': False,
        'decision': 'Do not implement a dedicated direct-fact gate or buy equivalent repeated responses for13/81. Reuse ordinary fact/rule separation and negative examples. Check source-derived interface contracts against a from-source ordinary/SARA-style acquisition control before committing to another contribution claim.',
        'two_contributions_established': False, 'goal_complete': False, 'new_full_build': False,
        'full_evaluation_matrix': False, 'TEST_labels_read': False, 'paper_started': False}
    # Capture independently replayable physical request ledger delta; old rows
    # remain only in the preserved cumulative ledger/backup, never republished.
    delta = [dict(zip(['id','role','purpose','bucket','source','request_hash','status','reserved_at','result'], r))
             for r in current['calls'] if r[0].startswith(RUN+':')]
    for r in delta: r['result'] = json.loads(r['result'])
    immutable_json(STAGE/'request_ledger_delta.json', {'new_calls': delta, 'oracle_unchanged': True})
    immutable_json(STAGE/'source_semantics_audit.json', semantics)
    immutable_json(STAGE/'frozen_manifest.json', {'files': frozen, 'goal_complete': False})
    immutable_json(REPORT/'legal_fact_boundary_results.json', result)
    BACKUP.mkdir(parents=True, exist_ok=True)
    path = BACKUP/'ledger.after.sqlite3'
    if not path.exists():
        with sqlite3.connect(DB) as src, sqlite3.connect(path) as dst: src.backup(dst)
    assert snapshot(path) == current
    print(json.dumps({k: result[k] for k in ['counts_total','pending','new_charged_attempts','executor_prompt_tokens','executor_output_tokens','executor_request_elapsed_seconds','all_pre_turn_rows_equal_backup','decision']}, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
