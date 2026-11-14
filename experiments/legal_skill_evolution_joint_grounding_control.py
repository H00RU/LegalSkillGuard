"""Strong one-read joint repair control before expanding residual learning.

One existing original-TRAIN development mother, original pre-clarification
state, same fixed model and unchanged legal kernel. The model receives the
already learned contracts as a shared asset, not a restricted direct baseline.
"""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_temporal_contract_learning as prior
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import checked_witnesses, kernel_execution
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages


ROOT = prior.ROOT
RUN = 'legal_skill_evolution_joint_grounding_control_20261114'
OUT = ROOT / 'artifacts' / RUN
SYSTEM = '''Repair the factual binding of the supplied unchanged legal program.
Use the current case facts, public statute, actual previous input and program
result. The complete already learned observation/adapter contracts are shared
with you: freely use their event views, parsing, cached correct procedures and
program behavior. Correct all coupled factual input problems in this ONE read;
you are not restricted to one port or to the previous extraction layout.

Do not change the legal program or output a native legal answer. Recheck roles,
event/state time, ongoing versus closed intervals, and other actual inputs only
against the current text. A failed/unread channel is null, not False/zero/[];
resolved finite case extraction with no matching statement may be []. Explicit
statutory givens use the shared native task interpretation already in the kernel.
Never invent an ending date or an event. A case question is not proof of its own
premise. Include exact current facts/question witnesses. Return factual JSON only.
'''


def main():
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        pp = prior.read(prior.OUT / 'protocol.json')
        sid = next(s for s in pp['learning_sources'] if s.split(':')[1].startswith('8175fcb9'))
        case = next(c for c in prior.read(prior.direct.OUT / 'fixed_development_cases.json') if c['source']['key'] == sid)
        kernel = next(k for k in prior.read(prior.OUT / 'kernel_bank.json') if k['name'] == 'separate_return_itemization_gate')
        old = next(r for r in prior.read(prior.OUT / 'scored_results.json')['rows'] if r['source'] == sid and r['arm'] == 'DirectRead')
        task = {'current_case': case['source']['views'][0]['public'],
            'unchanged_legal_program': kernel,
            'actual_previous_observation': old['observation'], 'actual_program_result': old['execution'],
            'shared_already_learned_contracts': {arm: prior.read(prior.OUT / arm / 'teacher.json')['value']['contracts']
                for arm in prior.ARMS},
            'later_source_presence_diagnostic_not_supplied': True,
            'no_native_target_label_supplied': True}
        schema = json.loads(json.dumps(prior.direct.schema_for(kernel), sort_keys=True))
        jsonschema.Draft202012Validator.check_schema(schema)
        before = prior.base.old.rows(); assert not any(r[6] == 'reserved' for r in before)
        if not (OUT / 'protocol.json').exists():
            immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
            immutable_json(OUT / 'task.json', task)
            immutable_json(OUT / 'protocol.json', {'run_id': RUN, 'same_goal': True, 'source': sid,
                'development_only_no_new_source': True, 'new_executor_requests_planned': 1,
                'shared_contract_execution_isolation_not_independent_acquisition': True,
                'all_later_diagnostic_results_withheld': True,
                'no_rule_edit_or_native_answer_fallback': True,
                'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'task_sha256': digest(task), 'schema': schema, 'system': SYSTEM,
                'executor_profile': pp['executor_profile']})
        p = prior.read(OUT / 'protocol.json')
        assert digest(task) == p['task_sha256'] and hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == p['source_sha256']
        ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
            sources={'train': [sid], 'dev': [], 'test': []}, binding=digest(p))
        response = FrozenExecutor(ledger, OUT, p['executor_profile']).generate(RUN + ':JointRepair',
            source=sid, purpose='skill_actor', thinking=False,
            messages=render_messages(SYSTEM, task, schema), schema=decoder_schema(schema)[0])
        assert response['finish_reason'] == 'stop'
        value = json.loads(response['content']); jsonschema.validate(value, schema)
        checked_witnesses(value['witnesses'], task['current_case'])
        inputs = {k: v for k, v in value['inputs'].items() if v is not None}
        execution = kernel_execution(kernel, inputs)
        # Native grading is opened only after the literal physical response.
        ann = prior.read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
        src = case['source']; view = src['views'][0]
        result = {'source': sid, 'observation': value, 'inputs': inputs,
            'execution': execution, 'native_score': grade_view(src['dataset'], view, ann[sid][view['id']], execution['answer']),
            'shared_acquisition_costs_not_free': True, 'fallback': False,
            'physical_call_id': RUN + ':JointRepair', 'goal_complete': False,
            'one_case_mechanism_control_not_full_method_validation': True}
        immutable_json(OUT / 'result.json', result)
        print(json.dumps({'execution': execution, 'score': result['native_score']}), flush=True)


if __name__ == '__main__':
    main()
