"""Verify the complete fixed TRAIN32 study from actual calls, never partial scores."""
from __future__ import annotations
import collections
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from jsonschema import ValidationError, validate
from experiments.openexempt_online import actor_payload, native_claim_feedback
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import read, sha
from legal_skill_guard.learning.legal_namespace import decode_asset_references, decode_reference, public_asset_catalog, public_catalog
from legal_skill_guard.openexempt import evaluate, metrics

BASE = Path(__file__).resolve().parent
OUT = BASE / 'asset_factorization_B1_B8_TRAIN32_resource_run02'
FIRST = BASE / 'asset_factorization_B1_B8_TRAIN32_run01'
SCREEN = BASE / 'asset_factorization_TRAIN8_run01'


def expected_payload(row, bank, asset=None):
    messages, schema, _ = actor_payload(row, bank, grounded=True, direct_numeric=True, asset_references=True)
    if asset is None: return messages, schema
    messages, schema = copy.deepcopy(messages), copy.deepcopy(schema)
    changes = 0
    for message in messages:
        for old, new in [
            ('Include every listed ID, using [] when no exemption is applicable.',
             'This request covers exactly the focus asset_ref specified in the last message; output only that key, using [] when no exemption is applicable. Other asset mentions and all facts remain context.'),
            ('exactly all supplied case-local asset_ref keys',
             'exactly the focus case-local asset_ref key specified in the last message')]:
            changes += message['content'].count(old)
            message['content'] = message['content'].replace(old, new)
    assert changes == 2
    schema['required'] = [asset]; schema['properties'] = {asset: schema['properties'][asset]}
    messages.append({'role': 'user', 'content': json.dumps({'focus_asset_ref': asset}, separators=(',', ':'))})
    return messages, schema


def main():
    terminal, protocol = read(OUT / 'terminal.json'), read(OUT / 'protocol.json')
    assert terminal['state'] == 'completed'
    assert terminal['prior_phase_new_EV_generations'] == 129
    assert terminal['actual_new_EV_generations'] == 40
    assert terminal['total_new_EV_generations_across_resource_phases'] == 169
    cfg = read(ROOT / 'configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json')
    rows = {(r['case_id'], r['family']): r for r in read(ROOT / cfg['input_packet'])['rows']}
    banks, ids = protocol['frozen_banks'], protocol['source_ids']
    saved = read(OUT / 'scored_records.json')
    sources = {str(p): sha(p) for p in [Path(__file__), OUT / 'terminal.json', OUT / 'protocol.json', OUT / 'scored_records.json']}
    for path, digest in protocol['frozen_files'].items(): assert sha(path) == digest, path
    unique_ids, source_counts, requested_models = set(), collections.Counter(), set()
    logical_costs = {a: collections.Counter() for a in banks}
    reconstructed = {a: {} for a in banks}

    def actual_call(path, messages, schema):
        seen = set()
        while True:
            assert path.resolve().is_relative_to(ROOT.resolve()) and path not in seen
            seen.add(path)
            data, inp = read(path), read(path.with_suffix('.input.json'))
            sources[str(path)], sources[str(path.with_suffix('.input.json'))] = sha(path), sha(path.with_suffix('.input.json'))
            assert inp['messages'] == messages and inp['schema'] == schema
            if data.get('calls'):
                assert len(data['calls']) == 1 and data.get('transport_error') is None
                req, wire = data['calls'][0]['request'], data['calls'][0]['response']
                requested_models.add(req['model'])
                assert req['messages'] == messages and req['response_format']['json_schema']['schema'] == schema
                for k in ['temperature', 'top_p', 'top_k', 'seed', 'max_tokens']:
                    assert req[k] == protocol['generation'][k]
                response = data['response']
                assert wire['id'] == response['raw_id']
                assert (wire['choices'][0]['message'].get('content') or '').strip() == response['content']
                assert wire['usage']['prompt_tokens'] == response['prompt_tokens']
                assert wire['usage']['completion_tokens'] == response['completion_tokens']
                return response, path
            assert data['exact_wire_reuse_not_new_generation']
            source = ROOT / data['reused_from']
            assert sha(source) == data['source_sha256']
            assert read(source)['response'] == data['response']
            path = source

    def decode(response, schema, row, assets):
        submitted = json.loads(response['content']); validate(submitted, schema)
        if response['finish_reason'] != 'stop': raise ValueError('incomplete native response')
        values = decode_asset_references(copy.deepcopy(submitted), assets)
        return {a: [{'citation': decode_reference(c['citation_ref'], public_catalog(row)), 'claim_value': c['claim_value']}
                    for c in claims] for a, claims in values.items()}

    for cid in ids:
        row = rows[cid, 'EV']; assets = public_asset_catalog(row)
        for arm in banks:
            merged, errors = {}, []
            for asset, name in assets.items():
                messages, schema = expected_payload(row, banks[arm], asset)
                assert any(row['components']['facts'] in m['content'] for m in messages)
                assert any(row['components']['statutes'] in m['content'] for m in messages)
                response, leaf = actual_call(OUT / 'native' / f'{cid}_{arm}_{asset}.json', messages, schema)
                assert response['raw_id'] not in unique_ids; unique_ids.add(response['raw_id'])
                label = 'screen' if leaf.is_relative_to(SCREEN) else 'phase1' if leaf.is_relative_to(FIRST) else 'continuation' if leaf.is_relative_to(OUT) else 'unexpected'
                assert label != 'unexpected'; source_counts[label] += 1
                logical_costs[arm].update({k: response[k] for k in ['prompt_tokens', 'completion_tokens']})
                try:
                    part = decode(response, schema, row, {asset: name})
                    assert not merged.keys() & part.keys(); merged.update(part)
                except (ValidationError, ValueError, TypeError, KeyError) as exc: errors.append(repr(exc))
            reconstructed[arm][cid] = None if errors else merged
    assert len(unique_ids) == 186 and source_counts == {'screen': 17, 'phase1': 129, 'continuation': 40}
    details, report, whole_costs, oracle = {}, {}, {}, []
    for arm, records in saved.items():
        assert len(records) == 32 and {r['case_id'] for r in records} == set(ids)
        errors = collections.Counter(); case_rows = {}; cost = collections.Counter()
        for record in records:
            cid, bank = record['case_id'], banks[arm.removeprefix('whole_').removeprefix('factorized_')]
            row = rows[cid, 'EV']; target_path = ROOT / cfg['grading_directory'] / f'{cid}.json'
            target = read(target_path)['targets']['EV']; sources[str(target_path)] = sha(target_path)
            answer = record['parsed']['answer'] if record['parse_error'] is None else None
            if arm.startswith('factorized_'):
                assert answer == reconstructed[arm.removeprefix('factorized_')][cid]
            else:
                messages, schema = expected_payload(row, bank)
                response, _ = actual_call(ROOT / record['raw_call_path'], messages, schema)
                cost.update({k: response[k] for k in ['prompt_tokens', 'completion_tokens']})
                if record['parse_error'] is None:
                    assert decode(response, schema, row, public_asset_catalog(row)) == answer
            assert evaluate(row, answer, target) == record['score']
            fb = native_claim_feedback(record, target)
            errors.update({k: int(fb.get(k, 0)) for k in ['invalid_response', 'correct', 'missing', 'incorrect_value', 'extra_or_duplicate']})
            case_rows[cid] = {'score': record['score'], 'feedback': fb}
        cohorts = {'all32': set(ids), 'current16': set(protocol['current_source_ids']),
                   'prior16': set(ids)-set(protocol['current_source_ids']), 'screen8': set(protocol['screen_source_ids']),
                   'remaining24': set(ids)-set(protocol['screen_source_ids'])}
        summary = {name: metrics([r for r in records if r['case_id'] in cases])['EV'] for name, cases in cohorts.items()}
        summary['errors'] = dict(errors)
        assert summary == terminal['conditions'][arm]
        report[arm], details[arm] = summary, case_rows
        if arm.startswith('whole_'): whole_costs[arm] = dict(cost)
    for cid in ids:
        row = rows[cid, 'EV']; target = read(ROOT / cfg['grading_directory'] / f'{cid}.json')['targets']['EV']
        oracle.append({'case_id': cid, 'family': 'EV', 'score': evaluate(row, target, target)})
    assert len(requested_models) == 1
    pairs = [('whole_B1', 'factorized_B1'), ('whole_B8', 'factorized_B8'),
             ('whole_B1', 'whole_B8'), ('factorized_B1', 'factorized_B8')]
    paired = {}
    for before, after in pairs:
        cases = []
        for cid in ids:
            a, b = details[before][cid], details[after][cid]
            cases.append({'case_id': cid, 'current': cid in protocol['current_source_ids'],
                'screen_source': cid in protocol['screen_source_ids'],
                'native_gain_pp': 100*(b['score']['f1']-a['score']['f1']),
                'full_gain_pp': 100*(b['score']['full_output_f1']-a['score']['full_output_f1']),
                'before_errors': a['feedback'], 'after_errors': b['feedback']})
        paired[before+'__to__'+after] = {'native_sources_improved': sum(r['native_gain_pp']>1e-10 for r in cases),
            'native_sources_harmed': sum(r['native_gain_pp'] < -1e-10 for r in cases), 'cases': cases}
    result = {'scope': 'Completed existing TRAIN32 diagnostic, not TEST or independent learning repetition',
        'all186_actual_call_identities_alias_links_generation_and_scopes_verified': True,
        'source_counts': dict(source_counts), 'all_model_claims_merged_verbatim_no_semantic_repairs': True,
        'same_requested_model_for_new_and_historical_calls': sorted(requested_models),
        'all128_full_case_condition_scores_and_errors_independently_recomputed': True,
        'all_frozen_bindings_unchanged': True, 'conditions': report, 'paired': paired,
        'logical_factorized_tokens_per_bank_including_reused_responses': {k: dict(v) for k,v in logical_costs.items()},
        'historical_whole_case_tokens_per_bank': whole_costs,
        'native_target_self_score_ceiling_diagnostic_not_a_replacement_metric': metrics(oracle)['EV'],
        'all_full_case_predictions_saved_before_grading': (OUT/'full_case_predictions_before_grading.json').stat().st_mtime_ns <= (OUT/'scored_records.json').stat().st_mtime_ns,
        'original_phase1_budget_failure_retained': (FIRST/'failure.json').exists(),
        'source_sha256': sources, 'formal_method_or_manuscript_changed': False}
    RunStore.immutable_json(OUT / 'independent_verification_and_paired_errors_v1.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['source_sha256','paired','conditions']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
