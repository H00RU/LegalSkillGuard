"""Isolate native response syntax failures with zero new model requests."""

import argparse
import base64
import json
import sqlite3
import tempfile
from types import SimpleNamespace

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_observe import pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_programs import ControlProgramRuntime
from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_tools import legal_tools
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.terminal_json import recover_json


class OfflineReplay(FrozenExecutor):
    def __init__(self, path, config, source, wire, response):
        super().__init__(SimpleNamespace(run_id='offline-transport-replay'), path, config)
        self.source, self.wire, self.response = source, wire, response
        self.verified = False

    def generate(self, identity, *, source, purpose, messages, schema, thinking):
        wire = self.payload(messages=messages, thinking=thinking, schema=schema)
        if (self.verified or source != self.source or purpose != 'skill_actor' or thinking is not False
                or json.dumps(wire, ensure_ascii=False).encode() != self.wire):
            raise ValueError('An offline replay requires the original single exact reader request')
        self.verified = True
        return self.response


def _native_utility(cell, execution, gold):
    native = ProgramActor._native(cell, execution)
    return {v['id']: grade_view(cell['dataset'], v, gold[v['id']], native[v['id']]['answer'],
            native[v['id']]['evidence_sentence_ids'])['grade'] if native[v['id']]['handled'] else 0.0
            for v in cell['views']}


def _replay(stage, binding, source, identity, actual, path, execution, trace):
    if trace['raw_content'] != actual['content'] or trace['usage'] != actual['usage'] or execution['core_executed']:
        raise ValueError('The alleged truncation disagrees with the physical response or its original execution')
    result = {'physical_call_id': identity, 'source_sha256': digest(source), 'new_model_calls': 0}
    try:
        _, recovery = recover_json(actual['content'], trace['schema'], finish_reason=actual['finish_reason'])
    except ValueError as exc:
        return {**result, 'recovery': 'refused', 'structural_reason': str(exc)}
    saved = read(path.with_name('input.json'))
    cell, = (s for s in common_cells(source) if source_bundle(s)['public'] == saved['inputs']['public'])
    bundle = source_bundle(cell)
    tools, assets = legal_tools(cell, bundle)
    wire = read(stage / 'calls' / digest(identity) / 'wire_request.json')
    parsed = actual['content'].rstrip(' \t\r\n') + '}' * recovery['object_closures']
    simulated = {**actual, 'content': parsed, 'finish_reason': 'stop'}
    with tempfile.TemporaryDirectory(prefix='legal-skill-whitespace-replay-') as temp:
        reader = OfflineReplay(temp, binding['executor'], source['key'], base64.b64decode(wire['body_b64']), simulated)
        runtime = ControlProgramRuntime(reader, temp, max_calls=1, shared_assets=assets, legal_tools=tools)
        try:
            repaired = runtime.run(saved['program'], cell, bundle, purpose='skill_actor')
        except Exception as exc:
            if not reader.verified:
                raise
            return {**result, 'recovery': recovery, 'native_decoder_failure': type(exc).__name__}
        if not reader.verified or not repaired['core_executed']:
            raise ValueError('The repair must execute the unchanged native composer offline')
    dataset = source['dataset']
    grading_path = binding['native_grade_paths'][dataset]
    if sha(ROOT / grading_path) != binding['native_grade_sha256'][grading_path]:
        raise ValueError('Use the original TRAIN scorer')
    gold = read(ROOT / grading_path)[source['key']]
    return {**result, 'pinned_original_wire_sha256': wire['body_sha256'], 'recovery': recovery,
            'recorded_native_utility': _native_utility(cell, execution, gold),
            'counterfactual_native_utility': _native_utility(cell, repaired, gold)}


def run(batch):
    status = read(pointer(batch))
    stage = ROOT / status['artifact_root']
    binding = read(stage / 'binding.json')
    study = read(ROOT / binding['checkpoint_root'] / 'binding.json')
    roster = load_roster(study)[batch - 1]
    if (binding['batch'] != batch or digest(binding) != stage.name
            or binding['ordered_sources_sha256'] != digest(roster)):
        raise ValueError('Cannot mix evidence across different TRAIN cohorts')
    sources = {s['key']: s for s in roster if s['project_split'] == 'train'}
    run_id = f'convergence-formal-B{batch}-observe-{stage.name[:16]}'
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        completed = {i: (key, json.loads(raw)) for i, key, raw in db.execute(
            "select id,source,result from calls where status='completed' and purpose='skill_actor' and id like ?",
            (run_id + ':program:%',))}
    results = []
    for path in (stage / 'program_executions').glob('*/result.json'):
        execution = read(path)
        for trace in execution['traces']:
            identity = trace.get('logical_call_id')
            if identity not in completed:
                continue
            key, actual = completed[identity]
            if actual['finish_reason'] == 'length':
                results.append(_replay(stage, binding, sources[key], identity, actual, path, execution, trace))
    result = {'TRAIN_batch': batch, 'observation_status_at_audit': status['status'], 'anchor_binding': stage.name,
              'rows': sorted(results, key=lambda r: r['physical_call_id']), 'new_model_calls': 0,
              'historical_result_edited': False, 'TEST_opened': False}
    out = BASE / 'whitespace_transport_audit' / digest(result) / 'terminal.json'
    immutable_json(out, result)
    print(json.dumps({'receipt': str(out.relative_to(ROOT)), 'responses': len(results),
                      'recoverable': sum(isinstance(row['recovery'], dict) and 'counterfactual_native_utility' in row
                                         for row in results)}, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=int, choices=range(2, 9), required=True)
    run(parser.parse_args().batch)
