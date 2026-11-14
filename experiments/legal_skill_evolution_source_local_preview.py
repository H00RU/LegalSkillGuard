"""Execute each new C/control source update on the fixed eight TRAIN sources.

This is the actual new source producer and proposed G, not a re-score of old
observations. A model transport is deliberately unavailable: source-only
proposals cannot silently acquire more evidence while being checked.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import traceback

from experiments import legal_skill_evolution_source_local_update as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.source_function_patch import apply_function_edits


class NoModel:
    def generate(self, *args, **kwargs):
        raise ValueError('Source-only candidate attempted an unplanned model read')


def run(arm, *, proposal=None, output_folder=None, complete_program=False):
    task = current.read(current.OUT / 'teacher_task.json')
    public = {s['key']: s for s in current.read(current.old.previous.prior.prior.PUBLIC)
              if s['dataset'] == 'ContractNLI'}
    grading = current.read(current.old.previous.prior.prior.GRADING)
    raw = proposal if proposal is not None else current.read(current.OUT / arm / 'teacher.json')['value']
    packet = deepcopy(raw)
    if complete_program:
        preservation = {'explicit_complete_program': True, 'original_proposal_unchanged': True}
    else:
        program, preservation = apply_function_edits(task['current_libraries'][arm]['source_program'],
                                                    packet.pop('source_function_edits'))
        packet['source_program'] = program
    library, receipt, proposal = current.old.compile_raw(task['current_libraries'][arm], packet, arm, public)
    library['spec']['decision_program'] = task['common_frozen_consumer']
    if arm == 'ConstraintAcquire':
        library['selected_rule_ids'] = library['suggested_rule_ids']
    folder = output_folder if output_folder is not None else current.OUT / 'unbound_proposed_execution' / arm
    immutable_json(folder / 'library.json', library)
    immutable_json(folder / 'function_patch_preservation.json', preservation)
    immutable_json(folder / 'compilation_receipt.json', receipt)
    rows = []
    for entry in task['tasks']:
        key = entry['source_id']
        target = folder / current.old.name_for(key)
        if target.exists():
            row = current.read(target)
        else:
            pub, units, _ = current.old.previous.prior.prior.source_material(current.old.previous.PARENT, public, key)
            upstream = current.read(current.old.OUT / 'upstream' / current.old.name_for(key))['source_output']
            history = [current.read(current.old.OUT / 'history' / a / current.old.name_for(key))['observation'] for a in current.ARMS]
            history += [current.read(current.old.OUT / 'paid_reading_history' / a / current.old.name_for(key))['observation'] for a in current.ARMS]
            try:
                observation = current.old.observe(NoModel(), 'offline_local_preview:' + arm + ':' + key, key,
                    library, source_text=pub['source_text'], units=units, source_output=upstream,
                    previous_observations=history)
                assert observation['new_model_requests'] == 0
                actual = current.old.previous.prior.prior.evaluate_source(library, observation, public[key], grading[key])
                row = {'source': key, 'arm': arm, 'observation': observation, 'actual': actual,
                    'correct': sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views']),
                    'unresolved': sum(not v['core_executed'] for v in actual['feedback']['views']),
                    'new_model_calls': 0}
            except Exception as error:
                row = {'source': key, 'arm': arm, 'correct': 0, 'unresolved': 4,
                       'error': type(error).__name__ + ': ' + str(error),
                       'traceback': traceback.format_exc(), 'new_model_calls': 0}
            immutable_json(target, row)
        rows.append(row)
        print(json.dumps({key: row[key] for key in ('source', 'correct', 'unresolved')}), flush=True)
    result = {'arm': arm, 'correct': sum(row['correct'] for row in rows), 'total_views': 32,
        'unresolved': sum(row['unresolved'] for row in rows),
        'source_rows': [{key: row[key] for key in ('source', 'correct', 'unresolved')} for row in rows],
        'proposed_G_not_yet_a_new_certified_fit': arm == 'ConstraintAcquire',
        'same_frozen_consumer': True, 'fallback': False, 'new_model_calls': 0,
        'not_full_source_semantic_certification': True, 'goal_complete': False,
        'analysis_driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    immutable_json(folder / 'result.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--arm', required=True, choices=list(current.ARMS))
    run(parser.parse_args().arm)
