"""Versioned v2 decoding/alignment of all18 fixed paid OE responses.

No model transport object,no new request,no grading and no candidate selection.
Old source snapshots and actual ledger results are verified,not overwritten.
This is deterministic reuse of the same18 responses,not18 independent trials.
"""
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, serialize_pair, sha
from legal_skill_guard.paired_interfaces.asset_graph_pairs import pair_from_port_record
from legal_skill_guard.paired_interfaces.asset_port_decoder_v2 import consume, decode
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


ORIGINAL = BASE / 'asset_port_reads_v1/71eee85048e48fe8ebf7f4a190c4df814cdc5f36efc1b1c450123c3e05b72f3c'
PREFLIGHT = BASE / 'formal_read_preflight_v1/6e22e5920c3df1aac061f9bd159788e44b30c9bd570fc9f740c4c0894a56058f'


def main():
    old_protocol = read(ORIGINAL / 'protocol.json')
    terminal = read(ORIGINAL / 'terminal.json')
    if terminal['outputs'] != 18:
        raise ValueError('The original physical integration is not fully terminal')
    # Historical sources are checked at their own snapshots. Current science
    # can evolve after a verified boundary without falsifying old hashes.
    for name, expected in old_protocol['source_sha256'].items():
        if sha(ORIGINAL / 'source_snapshot' / name) != expected:
            raise ValueError('An original frozen implementation snapshot changed')
    original = read(ORIGINAL / 'paired_reads.json')
    if len(original) != 18:
        raise ValueError('Every original read,including failures,must remain')
    cards_path = ROOT / old_protocol['reference_manifest_path']
    if sha(cards_path) != old_protocol['reference_manifest_sha256']:
        raise ValueError('The original source-reference manifest changed')
    cards = {(row['source'], row['view']): row for row in read(cards_path)['reviews']}
    plan_assets = read(PREFLIGHT / 'plan_assets.json')['OE_by_public_regime']
    plans = {plan['version']: plan for candidates in plan_assets.values() for plan in candidates}
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    if sha(public_path) != read(PREFLIGHT / 'protocol.json')['TRAIN_public_sha256']:
        raise ValueError('Original TRAIN public bytes changed')
    train = {source['key']: source for source in read(public_path)}
    paths = [Path(__file__).relative_to(ROOT), 'legal_skill_guard/paired_interfaces/asset_port_decoder_v2.py',
        'legal_skill_guard/paired_interfaces/asset_graph_pairs.py', 'legal_skill_guard/paired_interfaces/asset_interfaces.py',
        'legal_skill_guard/paired_interfaces/program_residual.py', 'legal_skill_guard/paired_interfaces/native_graph_consumers.py',
        'legal_skill_guard/paired_interfaces/partial_consumer_worker.py', 'legal_skill_guard/paired_interfaces/scope_learning.py',
        'legal_skill_guard/skill_evolution/native.py']
    binding = {str(path): sha(ROOT / path) for path in paths}
    protocol = {'experiment': 'paid_OE_source_anchor_ambiguity_decoder_v2', 'source_sha256': binding,
        'original_protocol_sha256': sha(ORIGINAL / 'protocol.json'),
        'original_paid_reads_sha256': sha(ORIGINAL / 'paired_reads.json'),
        'original_source_reference_manifest_sha256': sha(cards_path),
        'decoder_change': 'keep all literal source-span supports and all injective asset alignments;do not require unique row quotes',
        'unchanged_rejections': ['nonliteral source quotes', 'unaligned arrays', 'guessed unknown values', 'non-stop generation'],
        'raw_values_statuses_source_quotes_and_scope_bits_changed': False,
        'native_law_F_and_premises_changed': False, 'new_model_requests': 0,
        'no_native_grading_or_plan_selection': True, 'old_results_and_failures_preserved': True,
        'old_channels_not_inherited_or_pooled': True, 'new_independent_trials': 0}
    out = BASE / 'asset_port_redecode_v2' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    results = []
    ledger = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(ledger) + '?mode=ro', uri=True) as db:
        for old in original:
            call_id = old['physical_call_id']
            physical = db.execute('select status,result from calls where id=?', (call_id,)).fetchone()
            if physical is None or physical[0] != 'completed':
                raise ValueError('A paid read is not physically settled in the original ledger')
            response = json.loads(physical[1])
            original_result = read(ORIGINAL / 'calls' / digest(call_id) / 'result.json')
            if response != original_result:
                raise ValueError('A paid response differs from its original immutable physical artifact')
            plan = plans[old['raw_read_version']]
            source = train[old['source']]
            task, mapping = inputs(source)
            units = next(view['source_units'] for view in task['views'] if view['view_id'] == old['view'])
            card_row = cards[old['source'], old['view']]
            card_path = ROOT / card_row['card_path']
            if sha(card_path) != card_row['card_sha256']:
                raise ValueError('An original source port review changed')
            errors, raw, decoded, receipt = [], None, None, None
            if response['finish_reason'] != 'stop':
                errors.append('Original non-stop generation finish: ' + str(response['finish_reason']))
            try:
                raw, _ = restore_enum_transport(strict_json(response['content']), plan['schema'])
                decoded, receipt = decode(plan, raw, units)
            except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
                errors.append(type(error).__name__ + ': ' + str(error))
            version = digest({'actual_raw_read_version': old['raw_read_version'],
                              'executor': old_protocol['executor'], 'new_pipeline_source_sha256': binding})
            pair, alignment = pair_from_port_record(read(card_path), decoded, plan, units,
                source=old['source'], role=old['role'], provenance=digest([call_id, sha(card_path), digest(protocol)]),
                version=version, production_errors=errors)
            native = {name: consume(plan, decoded, name) for name, view in mapping.items() if view == old['view']} if not errors else {}
            row = {'source': old['source'], 'role': old['role'], 'view': old['view'], 'plan': old['plan'],
                'physical_call_id': call_id, 'raw_read_version': old['raw_read_version'], 'channel_version': version,
                'original_production_errors': old['production_errors'], 'v2_production_errors': errors,
                'raw_port_read': raw, 'decoder_receipt': receipt, 'pair': serialize_pair(pair),
                'alignment': alignment, 'native_outputs_recomputed_offline': native,
                'new_physical_request_or_independent_trial': False}
            immutable_json(out / 'reads' / digest([old['source'], old['view'], old['raw_read_version']]) / 'decoded.json', row)
            results.append(row)
    immutable_json(out / 'paired_reads.json', results)
    summary = {'paid_outputs_reused': len(results),
        'v1_production_decode_accepted': sum(not row['original_production_errors'] for row in results),
        'v2_production_decode_accepted': sum(not row['v2_production_errors'] for row in results),
        'v2_ambiguous_alignment_reads': sum(row['alignment'].get('alignments', 0) > 1 for row in results),
        'v2_native_tasks_handled_in_offline_replay': sum(result['handled'] for row in results
            for result in row['native_outputs_recomputed_offline'].values()),
        'native_accuracy_or_advantage_not_evaluated': True, 'new_model_requests': 0,
        'new_independent_trials': 0, 'old_channels_and_failures_not_overwritten': True}
    immutable_json(out / 'summary.json', summary)
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), **summary}, ensure_ascii=False))


if __name__ == '__main__':
    main()
