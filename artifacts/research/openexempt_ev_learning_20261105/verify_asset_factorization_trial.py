"""Independent actual-request, key-only merge and whole-case score verification."""
from __future__ import annotations
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from jsonschema import validate
from experiments.openexempt_online import actor_payload, native_claim_feedback
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import read, sha
from legal_skill_guard.learning.legal_namespace import decode_asset_references, decode_reference, public_asset_catalog, public_catalog
from legal_skill_guard.openexempt import evaluate, metrics

BASE = Path(__file__).resolve().parent
OUT = BASE / 'asset_factorization_TRAIN8_run01'


def main():
    terminal, protocol = read(OUT / 'terminal.json'), read(OUT / 'protocol.json')
    assert terminal['state'] == 'completed'
    cfg = read(ROOT / 'configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json')
    rows = {(r['case_id'], r['family']): r for r in read(ROOT / cfg['input_packet'])['rows']}
    records = read(OUT / 'scored_records.json')
    bank, ids = protocol['parent_bank'], protocol['source_ids']
    sources = {str(p): sha(p) for p in [Path(__file__), OUT / 'protocol.json', OUT / 'terminal.json', OUT / 'scored_records.json']}
    for path, digest in protocol['frozen_files'].items():
        assert sha(path) == digest, path
    totals = {arm: {'calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0} for arm in ['empty', 'skills']}
    unique = set()
    reconstructed = {arm: {} for arm in ['empty', 'skills']}
    for cid in ids:
        row = rows[cid, 'EV']; assets, citations = public_asset_catalog(row), public_catalog(row)
        for arm in ['empty', 'skills']:
            original_messages, original_schema, _ = actor_payload(row, [] if arm == 'empty' else bank,
                grounded=True, direct_numeric=True, asset_references=True)
            answer, errors = {}, []
            for ref, name in assets.items():
                raw_path = OUT / 'native' / f'{cid}_{arm}_{ref}.json'
                inp_path = raw_path.with_suffix('.input.json')
                raw, inp = read(raw_path), read(inp_path)
                assert raw['transport_error'] is None and len(raw['calls']) == 1
                req, wire_response = raw['calls'][0]['request'], raw['calls'][0]['response']
                assert req['messages'] == inp['messages']
                assert req['response_format']['json_schema']['schema'] == inp['schema']
                for key in ['temperature', 'top_p', 'top_k', 'seed', 'max_tokens']:
                    assert req[key] == protocol['generation'][key]
                assert wire_response['id'] == raw['response']['raw_id']
                assert wire_response['id'] not in unique; unique.add(wire_response['id'])
                messages = copy.deepcopy(original_messages)
                changes = 0
                for message in messages:
                    for old, new in [
                        ('Include every listed ID, using [] when no exemption is applicable.',
                         'This request covers exactly the focus asset_ref specified in the last message; output only that key, using [] when no exemption is applicable. Other asset mentions and all facts remain context.'),
                        ('exactly all supplied case-local asset_ref keys',
                         'exactly the focus case-local asset_ref key specified in the last message')]:
                        changes += message['content'].count(old)
                        message['content'] = message['content'].replace(old, new)
                messages.append({'role': 'user', 'content': json.dumps({'focus_asset_ref': ref}, separators=(',', ':'))})
                assert changes == 2 and messages == req['messages']
                schema = copy.deepcopy(original_schema)
                schema['required'] = [ref]; schema['properties'] = {ref: schema['properties'][ref]}
                assert schema == inp['schema']
                assert any(row['components']['facts'] in m['content'] for m in messages)
                assert any(row['components']['statutes'] in m['content'] for m in messages)
                try:
                    submitted = json.loads(raw['response']['content']); validate(submitted, schema)
                    if raw['response']['finish_reason'] != 'stop': raise ValueError('incomplete')
                    decoded = decode_asset_references(submitted, {ref: name})
                    claims = [{'citation': decode_reference(c['citation_ref'], citations), 'claim_value': c['claim_value']}
                              for c in decoded[name]]
                    assert name not in answer; answer[name] = claims
                except (ValueError, TypeError, KeyError) as exc:
                    errors.append(repr(exc))
                for key in ['prompt_tokens', 'completion_tokens']:
                    totals[arm][key] += raw['response'][key]
                totals[arm]['calls'] += 1
                sources[str(raw_path)], sources[str(inp_path)] = sha(raw_path), sha(inp_path)
            reconstructed[arm][cid] = None if errors else answer
    assert len(unique) == len(protocol['jobs']) == 38
    summaries = {}
    original_costs = {}
    for arm, rs in records.items():
        assert {r['case_id'] for r in rs} == set(ids) and len(rs) == 8
        errors = {k: 0 for k in ['invalid_response', 'correct', 'missing', 'incorrect_value', 'extra_or_duplicate']}
        cost = {'logical_responses': len(rs), 'prompt_tokens': 0, 'completion_tokens': 0}
        for r in rs:
            row = rows[r['case_id'], 'EV']; target_path = ROOT / cfg['grading_directory'] / f"{r['case_id']}.json"
            target = read(target_path)['targets']['EV']
            answer = r['parsed']['answer'] if r['parse_error'] is None else None
            if arm.startswith('factorized_'):
                assert answer == reconstructed[arm.removeprefix('factorized_')][r['case_id']]
            else:
                raw = read(ROOT / r['raw_call_path']); inp = read((ROOT / r['raw_call_path']).with_suffix('.input.json'))
                messages, schema, _ = actor_payload(row, [] if arm == 'whole_empty' else bank,
                    grounded=True, direct_numeric=True, asset_references=True)
                assert messages == inp['messages'] and schema == inp['schema']
                for key in ['prompt_tokens', 'completion_tokens']: cost[key] += raw['response'][key]
            assert evaluate(row, answer, target) == r['score']
            fb = native_claim_feedback(r, target)
            for key in errors: errors[key] += int(fb.get(key, 0))
        summary = {'all8': metrics(rs)['EV'], 'errors': errors,
            'current4': metrics([r for r in rs if r['case_id'] in protocol['current_source_ids']])['EV'],
            'prior4': metrics([r for r in rs if r['case_id'] not in protocol['current_source_ids']])['EV']}
        assert summary == terminal['conditions'][arm]
        summaries[arm] = summary
        if arm.startswith('whole_'): original_costs[arm] = cost
    result = {'all_38_actual_requests_and_unique_response_ids_verified': True,
        'all_facts_statutes_skills_and_eligibility_context_preserved': True,
        'only_output_scope_sentences_schema_root_and_focus_ID_changed': True,
        'all_merged_numeric_values_and_citations_verbatim_from_model_submissions': True,
        'all_32_condition_case_scores_and_error_counts_recomputed': True,
        'predeclared_eight_source_sample_unchanged': True,
        'all_frozen_bindings_unchanged': True, 'new_teacher_calls': 0,
        'factorized_costs': totals, 'historical_whole_case_costs': original_costs,
        'full_case_predictions_saved_before_scoring': (OUT / 'full_case_predictions_before_grading.json').stat().st_mtime_ns < (OUT / 'scored_records.json').stat().st_mtime_ns,
        'source_sha256': sources, 'formal_method_or_paper_changed': False}
    RunStore.immutable_json(OUT / 'independent_verification_v1.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'source_sha256'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
