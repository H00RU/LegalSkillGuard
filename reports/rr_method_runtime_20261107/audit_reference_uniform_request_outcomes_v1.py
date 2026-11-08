"""Read original TRAIN records and settled ledger responses; never generate."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--prefix-sources', type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    if args.prefix_sources is not None and not 1 <= args.prefix_sources <= len(seal['sources']['train']):
        raise ValueError('A comparison prefix must belong to the original fixed TRAIN sources')
    with sqlite3.connect('file:' + str((root / seal['ledger_path']).resolve()) + '?mode=ro', uri=True) as db:
        physical = db.execute('select id,role,source,request_hash,status,result from calls').fetchall()
    by_hash = {}
    for call_id, role, source, request_hash, status, result in physical:
        if role == 'executor' and status == 'completed':
            by_hash.setdefault((source, request_hash), []).append((call_id, json.loads(result)))
    rows = []
    records_audited = 0
    for position, source in enumerate(seal['sources']['train'], 1):
        if args.prefix_sources is not None and position > args.prefix_sources:
            break
        path = stage / 'build/sources' / (digest(source) + '.json')
        if not path.exists():
            break
        record = json.loads(path.read_text())
        records_audited += 1
        prediction = record['prediction']
        for call in prediction['calls']:
            matches = [(call_id, response) for call_id, response in by_hash.get((source, call['request_hash']), [])
                if response.get('content') == call['raw_content']]
            assert len(matches) == 1, (source, call['request_hash'], len(matches))
            call_id, response = matches[0]
            assert response['thinking_requested'] is False
            assert not response.get('reasoning_content')
            if call.get('physical_origin_call_id'):
                assert call['physical_origin_call_id'] == call_id
            analysis = call['analysis']
            error = analysis.get('error') or {}
            rows.append({'source_position': position, 'source': source, 'dataset': record['dataset'],
                'step': call['step'], 'purpose': call['purpose'], 'physical_call_id': call_id,
                'request_hash': call['request_hash'],
                'raw_content_sha256': hashlib.sha256(call['raw_content'].encode()).hexdigest(),
                'finish_reason': response['finish_reason'],
                'usage': response.get('usage'), 'original_physical_elapsed_seconds': response['elapsed_seconds'],
                'replayed_exact_paid_wire': bool(call.get('physical_origin_call_id')),
                'program_status': analysis.get('program_status'),
                'error_type': error.get('error_type') if isinstance(error, dict) else None,
                'error': (error.get('error') if isinstance(error, dict) else str(error)),
                'field_path': error.get('field_path') if isinstance(error, dict) else None,
                'A_actual': analysis.get('A_main_path_executed', False),
                'B_actual': analysis.get('B_main_path_executed', False)})

    def summarize(items):
        return {'logical_responses': len(items),
            'distinct_paid_origin_responses': len({r['physical_call_id'] for r in items}),
            'exact_paid_replays': sum(r['replayed_exact_paid_wire'] for r in items),
            'finish_reasons': dict(Counter(r['finish_reason'] for r in items)),
            'length_fraction': sum(r['finish_reason'] == 'length' for r in items) / len(items) if items else None,
            'program_status_counts': dict(Counter(r['program_status'] for r in items)),
            'error_type_counts': dict(Counter(r['error_type'] for r in items if r['error_type']))}

    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'run_id': args.run_id,
        'original_fixed_TRAIN_sources': len(seal['sources']['train']),
        'requested_comparison_prefix_sources': args.prefix_sources,
        'source_records_audited': records_audited,
        'totals': summarize(rows),
        'by_dataset': {bank: summarize([r for r in rows if r['dataset'] == bank])
            for bank in sorted({r['dataset'] for r in rows})},
        'rows': rows, 'thinking_OFF_verified_for_all_rows': True,
        'elapsed_is_original_physical_generation_not_current_replay_wall_time': True,
        'format_or_type_success_is_not_source_semantic_acceptance': True,
        'new_model_or_oracle_calls': 0, 'DEV_or_TEST_labels_read': False,
        'ledger_reset': False, 'goal_complete': False}
    out = root / args.output
    tmp = out.with_suffix(out.suffix + '.tmp')
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(out)
    print(json.dumps({k: v for k, v in result.items() if k not in {'rows', 'by_dataset'}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
