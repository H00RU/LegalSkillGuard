"""Continue C on its actual seven unresolved TRAIN views, with local edits.

M2 may be running while this file prepares offline evidence. Teacher dispatch
uses the same single-client lock and is serial. Existing eight sources, source
programs, failed replacements and the continuous ledger are retained.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_source_gap_acquisition as old
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_function_patch import apply_function_edits
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, unpack_programs, INSTRUCTION, PROGRAM_INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues, render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT


ROOT = old.ROOT
RUN = 'legal_skill_evolution_source_local_update_20261114'
OUT = ROOT / 'artifacts' / RUN
REPAIR_PREFIXES = ('a5b0361', '62fda7', '8fb38')
ARMS = old.ARMS
COMMON = '''Continue the existing C legal-rule acquisition and its independent
strong ordinary program control. This is the SAME fixed eight original TRAIN
contracts, not new data or a new goal. Both teachers see the same source text,
units, supervision, actual programs, unresolved results and scoped source review.
Use function edits to the CURRENT source_program, preserving untouched code;
do not regenerate an unrelated complete module. Each edit has exact name/code.
New helper functions may be added. The host reconstructs the actual module and
validates all source/typing constraints before any deployment.

The concrete missing cases are seven UNRESOLVED views, not seven executed wrong
answers. Two short contracts have no acquired disposal atom and never establish
source-scoped absence; another has an elliptical recipient permission residual
and a request-only return clause. Existing G is optimal under the fixed old
representation. Re-searching the same G cannot acquire the missing distinction.
Inspect the FULL supplied text. A matcher finding no atom is not proof that the
source contains no rule. An actual scope-justified complete-source absence may
be learned as a separate factual source observation. Preserve generic copying/
use/disclosure prohibitions and their exceptions; absence of an explicit
post-disposal retention clause is not permission for unrestricted retention.

Current C25/32, own-consumer Free21/32, SAME-C-consumer Free23/32. The primary
new comparison uses that same frozen C consumer for BOTH libraries. Its code,
constructor meanings and source evidence conventions are supplied. Both may
use the same canonical output vocabulary. Do not modify decision_functions or
native labels to manufacture gains. decision_functions must be[]. No new model
reads in the source pipeline: operations and reading_contracts must be[], plan
must issue no queries. Current old legal roots remain unless contradicted by
actual source evidence. Every new legal field retains its actual joint support.

Keep the original source shape/qualifiers and uncertainty. For8fb the return
clause says IF REQUESTED; preserve that trigger and blank deadline. Do not
invent Agreement termination merely to force its native nda16 label. Keep
elliptical wording as source evidence rather than pretending the original text
had an explicit verb it lacks. Native NLI interpretation and source acquisition
are distinct. No full-source perfection or zero-fallback gate is added.

For C, new Norms must be produced by actual G composition of the acquired source
concepts. Source-program direct new Norm emission is not allowed. Reuse valid
old G; add/repair the actual missing shared relations where needed. Preserve
role, action and source-scope distinctions rather than a precompleted policy
packet switch. Suggested IDs are proposals, not proof of a learned selection.
For Free, unrestricted pure source/composition programs may emit Norms directly,
reuse every shared concept, cached correct source policy and the same ontology.
Ordinary programs expressing the same logic do not invalidate acquisition
reliability; an independently acquired strong control absorbing the effect does.

Output the existing schema except source_program is replaced by
source_function_edits:[{name,code}]. A no-change function need not be repeated.
All other fields retain their actual definitions. Use truly new constructors
only; do not redeclare changed meanings under old names. For unchanged fields,
return their current valid values. Pure modules, no imports, nested functions,
lambdas, IO, source-ID/company-name branches or native-answer lookup.
'''


def read(path):
    return json.loads(path.read_text())


def schema_for(arm):
    schema = deepcopy(old.C_SCHEMA if arm == 'ConstraintAcquire' else old.FREE_SCHEMA)
    schema['properties'].pop('source_program')
    schema['required'].remove('source_program')
    schema['properties']['source_function_edits'] = {'type': 'array', 'items': record_schema({
        'name': {'type': 'string'}, 'code': {'type': 'string'}})}
    schema['required'].append('source_function_edits')
    return schema


def prepare_offline():
    if (OUT / 'teacher_task.json').exists():
        return read(OUT / 'teacher_task.json')
    prior = read(old.OUT / 'teacher_task.json')
    libraries = {'ConstraintAcquire': read(old.OUT / 'unbound_provenance_replay/library.json'),
                 'FreeUpdate': read(old.OUT / 'FreeUpdate/compiled.json')}
    shared_consumer = (ROOT / 'artifacts/legal_skill_evolution_source_absence_consumer_20261114/after.py').read_text()
    for library in libraries.values():
        library['spec']['decision_program'] = shared_consumer
    report = read(ROOT / 'reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_source_gap/source_results.json')
    tasks, attribution = [], []
    for task in prior['tasks']:
        key = task['source_id']
        actual = {}
        for arm in ARMS:
            if arm == 'ConstraintAcquire':
                result = read(old.OUT / 'unbound_provenance_replay/execution' / old.name_for(key))
            else:
                result = read(old.OUT / 'unbound_pure_preview' / arm / old.name_for(key))['actual']
            output = result['execution']['source_output']
            # The full current text remains above; do not repeat it once per
            # residual unit in composition_uses. No unique legal term is lost.
            actual[arm] = {'complete': output['complete'], 'unresolved': output['unresolved'],
                'nonresidual_statements': [s for s in output['statements'] if 'residual' not in s['term'][0]],
                'native_feedback': result['feedback'],
                'duplicate_full_text_residual_arguments_not_repeated': True}
        selected = any(prefix in key for prefix in REPAIR_PREFIXES)
        tasks.append({'source_id': key, 'full_source_text': task['full_source_text'],
            'source_units': task['source_units'], 'incoming_source_output': task['incoming_source_output'],
            'native_TRAIN_supervision': task['native_TRAIN_supervision'],
            'actual_current': actual, 'repair_target': selected})
        row = next(r for r in report['rows'] if r['source'] == key)
        for view in row['ConstraintAcquire']['per_view']:
            if view['score'] is None:
                attribution.append({'source': key, 'view': view['view'],
                    'classification': 'unresolved_not_executed_wrong_answer',
                    'actual_source_unresolved': actual['ConstraintAcquire']['unresolved']})
    assert len(attribution) == 7
    task = {'tasks': tasks, 'current_libraries': libraries,
        'repair_sources': [t['source_id'] for t in tasks if t['repair_target']],
        'preservation_sources': [t['source_id'] for t in tasks if not t['repair_target']],
        'source_function_patch_code': (ROOT / 'legal_skill_guard/skill_evolution/source_function_patch.py').read_text(),
        'common_frozen_consumer': shared_consumer,
        'common_declared_absence_interface_repair': read(ROOT / 'artifacts/legal_skill_evolution_source_absence_consumer_20261114/result.json'),
        'common_observed_signatures': prior['common_observed_signatures'],
        'encoder_code': prior['encoder_code'], 'observer_code': prior['observer_code'],
        'exact_fixed_representation_certificate': read(old.OUT / 'certified_revision/certificate.json'),
        'actual_failure_attribution': attribution,
        'same_information_and_original_TRAIN_only': True,
        'no_new_full_training_DEV_TEST': True}
    packed = pack_programs(task)
    assert unpack_programs(packed) == task
    immutable_json(OUT / 'teacher_task.json', task)
    immutable_json(OUT / 'unresolved_attribution.json', attribution)
    checks = []
    for arm in ARMS:
        schema = schema_for(arm)
        issues = strict_output_schema_issues(schema)
        system = COMMON + '\n' + (old.C_PART + '\n' + old.previous.prior.prior.C_SPEC if arm == 'ConstraintAcquire' else old.FREE_PART)
        system += '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION
        user = json.dumps(packed, ensure_ascii=False, separators=(',', ':'))
        size = len(render_structured_codex_prompt(system, user))
        assert not issues and size <= CODEX_TURN_INPUT_CHARACTER_LIMIT
        checks.append({'arm': arm, 'schema_issues': issues, 'request_characters': size,
                       'task_sha256': digest(task), 'model_calls': 0})
    immutable_json(OUT / 'offline_preflight.json', checks)
    print(json.dumps({'repair_sources': len(task['repair_sources']), 'preservation_sources': len(task['preservation_sources']),
        'actual_unresolved_views': len(attribution), 'teacher_preflight': checks, 'new_model_calls': 0}), flush=True)
    return task


def acquire(only_arm=None):
    task = prepare_offline()
    parent = read(old.OUT / 'protocol.json')
    path = OUT / 'protocol.json'
    if not path.exists():
        before = old.previous.prior.rows()
        assert not any(row[6] == 'reserved' for row in before)
        files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/source_function_patch.py',
                 ROOT / 'tests/test_skill_evolution_source_function_patch.py']
        protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
            'sources': [t['source_id'] for t in task['tasks']],
            'repair_sources': task['repair_sources'], 'preservation_sources': task['preservation_sources'],
            'new_sources': 0, 'executor_requests_planned': 0, 'teacher_jobs': 2,
            'same_frozen_consumer_primary_comparison': True,
            'teacher_profile': parent['teacher_profile'], 'executor_profile': parent['executor_profile'],
            'task_sha256': digest(task), 'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
        immutable_json(path, protocol)
        immutable_json(OUT / 'ledger_before_row_hashes.json', {row[0]: digest(row) for row in before})
        for source in files:
            dest = OUT / 'source_snapshot' / source.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source.read_bytes())
    protocol = read(path)
    assert digest(task) == protocol['task_sha256']
    for name, expected in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN, sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    for arm in ARMS:
        if only_arm is not None and arm != only_arm:
            continue
        output = OUT / arm / 'teacher.json'
        if output.exists():
            continue
        system = COMMON + '\n' + (old.C_PART + '\n' + old.previous.prior.prior.C_SPEC if arm == 'ConstraintAcquire' else old.FREE_PART)
        system += '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION
        system += '\nAllowed attributes:' + ','.join(sorted(old.METHODS)) + '\nAllowed calls:' + ','.join(sorted(old.CALLS))
        result = FrozenTeacher(ledger, OUT, protocol['teacher_profile']).propose(RUN + ':' + arm + ':update',
            source_ids=protocol['sources'], system_prompt=system,
            user_prompt=json.dumps(pack_programs(task), ensure_ascii=False, separators=(',', ':')), output_schema=schema_for(arm))
        immutable_json(output, result)
        print(json.dumps({'arm': arm, 'local_source_update_saved': True}), flush=True)


def compile_candidates():
    task = read(OUT / 'teacher_task.json')
    public = {s['key']: s for s in read(old.previous.prior.prior.PUBLIC)}
    for arm in ARMS:
        raw = read(OUT / arm / 'teacher.json')['value']
        jsonschema.validate(raw, schema_for(arm))
        packet = deepcopy(raw)
        edits = packet.pop('source_function_edits')
        program, preservation = apply_function_edits(task['current_libraries'][arm]['source_program'], edits)
        packet['source_program'] = program
        assert packet['decision_functions'] == [] and packet['operations'] == [] and packet['reading_contracts'] == []
        library, receipt, proposal = old.compile_raw(task['current_libraries'][arm], packet, arm, public)
        own = deepcopy(library)
        library['spec']['decision_program'] = task['common_frozen_consumer']
        immutable_json(OUT / arm / 'compiled_before_common_consumer_assignment.json', own)
        immutable_json(OUT / arm / 'compiled.json', library)
        immutable_json(OUT / arm / 'function_patch_preservation.json', preservation)
        immutable_json(OUT / arm / 'compilation_receipt.json', receipt)
        print(json.dumps({'arm': arm, 'candidate_compiled': True, 'edited_functions': preservation['edited_functions']}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['offline', 'acquire', 'compile'])
    parser.add_argument('--arm', choices=list(ARMS))
    args = parser.parse_args()
    if args.phase == 'offline':
        prepare_offline()
        return
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.phase == 'acquire':
            acquire(args.arm)
        else:
            compile_candidates()


if __name__ == '__main__':
    main()
