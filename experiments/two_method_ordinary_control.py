"""Acquire and repair an independent ordinary-teacher program on fixed D0.

The initial source-derived critique and all three candidate rounds are fixed
before dispatch. Each revision sees complete actual weak traces and native
TRAIN feedback. No M1-generated interface is supplied. Selection uses the
same original development mothers, never the growing feedback file length.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

from legal_skill_guard.inference.codex_cli_client import (
    CODEX_TURN_INPUT_CHARACTER_LIMIT, render_structured_codex_prompt)
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_learning import (
    CRITIQUE_SCHEMA, TokenBudgetExecutor, program_from_proposal, proposal_schema,
    settled_token_usage, validate_teacher_schemas, pack_teacher_payload)
from legal_skill_guard.paired_interfaces.control_programs import ControlProgramRuntime
from legal_skill_guard.paired_interfaces.control_tools import legal_tools, module_assets
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
PUBLIC = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
GRADING = PUBLIC.with_name('grading.json')

SYSTEM = '''Learn a general executable external legal skill for the fixed weak model.
You receive original TRAIN source inputs, their native training feedback,
source-only reference proposals with explicit audit status, and exactly the
same frozen legal assets/tools available to the main method. Do not use a case
identity, filename, source fingerprint, verbatim-case switch, or a stored known
answer as the inference mechanism. Generalize source-supported legal rules.
The executor is the frozen Qwen3-8B with thinking disabled. Its weights never
change. You may freely design named neural predicates, deterministic regex/text
extractors, and Python code composing their outputs. You may call the shared
frozen legal module. You are not restricted to M1's generated interface pool.
Each extractor is def extract(inputs). It may use re and permitted builtins,
but makes no neural/tool calls. Composition is exactly
def compose(inputs, predict, extractors). It may use those builtins, re,
extractors['name'](inputs), predict('predicate_id', json_value), and the global
apply_legal('frozen_legal_module', typed_input). The latter returns a record
with handled/answer, never original case labels or facts. No imports, reflection,
file/network access, nested functions, or other external calls are available.
inputs contains public.native_views, dataset, native_answer_schema,
native_wire_schema, shared_assets, and legal_tools (tool contract descriptors).
The final return is a dict mapping every current native view id to its native
answer; it must satisfy inputs['native_answer_schema']. A predicate with
schema_mode=native returns that decoded answer dict; its raw weak response uses
the supplied native wire contract and preserves evidence in the host trace.
For fixed predicates, schema_json is a complete JSON schema encoded as a string;
for native predicates it is '{}'. Predicates receive only their prompt and the
JSON input supplied by composition; include needed definitions and context.
Do not send the entire shared asset bank to a predicate unnecessarily. Actual
input/output tokens share the same measured ceiling as the primary pilot;
shorter multi-call designs are permitted. All failures and costs are retained.
Use full feedback for source-grounded revisions and preserve correct behavior.
Permitted builtins: min,max,sum,len,abs,round,sorted,all,any,int,float,bool,str,
list,dict,range,enumerate,zip,set,tuple. Standard string/dict/list operations and
re.findall,finditer,match,fullmatch,search,sub,escape and match.group are allowed.
Return only the exact requested structured output.'''
SYSTEM += '''\nAll tools listed in inputs.legal_tools are available by their exact names.
The source_graph_native_module is the common source-anchored graph adapter;
finite_partial_legal_module (OE) preserves null unknown classification values
and executes only when every admissible completion agrees. These common tools
are also available to the main method and are not M1-generated candidates.'''
SYSTEM += '''\nThe user message may encode repeated long strings in text_table.
At each listed referenced_string_paths position, {$shared_text: id} means the
exact full string text_table[id]. Resolve these references when reading source
inputs, programs and traces; nothing was summarized or omitted.'''


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pending():
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        return db.execute("SELECT id FROM calls WHERE status='reserved'").fetchall()


def inputs_for_dataset(dataset, lock, train):
    development = [r for r in lock['rows'] if r['dataset'] == dataset and r['role'] == 'development']
    grades = read(GRADING)
    examples = []
    for row in development:
        source = train[row['key']]
        folder = BASE / 'annotation_v1/proposed_references' / digest(row['key'])
        check, task = read(folder / 'source_checks.json'), read(folder / 'task.json')
        proposal = read(BASE / 'annotation_v1/calls' / digest(check['physical_call_id']) / 'result.json')
        audits = [read(p) for p in sorted((folder / 'audits').glob('*/source_review.json'))]
        examples.append({'source': row['key'], 'input': source_bundle(source),
            'native_TRAIN_feedback': grades[row['key']],
            'source_only_reference_proposal': proposal['value'],
            'proposal_is_not_automatically_gold': True, 'source_only_audits': audits,
            'native_view_to_opaque_source_view': task['native_view_to_opaque_source_view']})
    return {'dataset': dataset, 'fixed_development_examples': examples,
            'shared_legal_assets': module_assets(dataset), 'selection_unit': 'original mother source',
            'native_feedback_is_for_program_learning_not_source_graph_repair': True,
            'calibration_or_structure_evaluation_feedback_supplied': False}


def prepare():
    validate_teacher_schemas()
    lock, source_lock = read(BASE / 'pilot_lock.json'), read(BASE / 'prepared/source_lock.json')
    if sha(PUBLIC) != source_lock['prepared_sha256']['train']['public']:
        raise ValueError('Original TRAIN public bytes changed')
    expected_grading = source_lock['prepared_sha256']['train'].get('grading')
    if expected_grading is not None and sha(GRADING) != expected_grading:
        raise ValueError('Original TRAIN grading bytes changed')
    train = {s['key']: s for s in read(PUBLIC)}
    registry = BASE / 'ordinary_control_v1/active_protocol.json'
    if registry.exists():
        out = ROOT / read(registry)['artifact_root']
        protocol = read(out / 'prepared_protocol.json')
        if sha(PUBLIC) != protocol['TRAIN_public_sha256'] or sha(GRADING) != protocol['TRAIN_grading_sha256']:
            raise ValueError('A bound TRAIN artifact changed')
        for name, expected in protocol['source_sha256'].items():
            if sha(ROOT / name) != expected:
                raise ValueError('A live control source changed: ' + name)
        return out, protocol, lock, source_lock, train
    datasets = sorted({r['dataset'] for r in lock['rows']})
    tasks = {d: inputs_for_dataset(d, lock, train) for d in datasets}
    paths = ['experiments/two_method_ordinary_control.py',
        *['legal_skill_guard/paired_interfaces/' + n + '.py' for n in (
            'control_answers', 'control_learning', 'control_programs', 'control_tools', 'control_worker',
            'consumer_graph_contract', 'public_graph_ports', 'consumer_worker', 'graph_interface', 'legal_consumers', 'numeric_ports')],
        *['legal_skill_guard/paired_interfaces/' + n + '.py' for n in (
            'native_graph_consumers', 'partial_consumer_worker', 'rich_graph_pairs', 'graph_pairs',
            'graph_evidence', 'native_adapters', 'scope_learning')],
        'experiments/two_method_annotate.py',
        'history/rr_v2_20261106/data/cache/rr_v2/RuleArena/airline/gen_questions.py',
        *['legal_skill_guard/skill_evolution/' + n + '.py' for n in (
            'clients', 'ledger', 'native', 'objects', 'grade_worker', 'span_compiler',
            'sara_statute_kernel', 'partial_native_proof', 'literal_statutory_givens', 'statute_input_dependencies')],
        'legal_skill_guard/inference/codex_cli_client.py', 'legal_skill_guard/rr/checkpoint.py',
        'legal_skill_guard/rr/client.py', 'legal_skill_guard/rr/ledger.py', 'legal_skill_guard/rr/scoring.py']
    paths += ['legal_skill_guard/' + name + '.py' for name in (
        '__init__', 'inference/__init__', 'paired_interfaces/__init__', 'rr/__init__',
        'rr/coverage', 'rr/source_structure', 'skill_evolution/__init__',
        'skill_evolution/answer_domain', 'skill_evolution/claim_scope', 'skill_evolution/coupling',
        'skill_evolution/literal_facts', 'skill_evolution/observation_status_schema',
        'skill_evolution/runtime', 'skill_evolution/source_fragments', 'skill_evolution/source_schema',
        'skill_evolution/task_roles', 'utils/__init__', 'utils/hashing')]
    binding = {p: sha(ROOT / p) for p in paths}
    protocol = {'experiment': 'independent_ordinary_teacher_pilot_v1', 'source_sha256': binding,
        'pilot_lock_sha256': sha(BASE / 'pilot_lock.json'), 'TRAIN_public_sha256': sha(PUBLIC),
        'TRAIN_grading_sha256': sha(GRADING), 'teacher': lock['teacher'], 'executor': lock['executor'],
        'dataset_tasks_sha256': {d: digest(t) for d, t in tasks.items()},
        'fixed_mother_roles': [{'source': r['key'], 'role': r['role']} for r in lock['rows']],
        'ordinary_teacher_stages': ['source_policy_critique', 'initial_program', 'full_feedback_repair_1', 'full_feedback_repair_2'],
        'candidate_count_per_dataset': 3, 'program_selection': 'best original development mother-macro, stable candidate order ties',
        'shared_optimizer_teacher_request_ceiling_per_arm': 20,
        'executor_budget_rule': 'sum actual prompt_tokens+completion_tokens for all v1/v2/v3 primary pilot physical executor requests, including integration failures; resolve only after v3 fully settles',
        'comparison_budget_is_tokens_not_equal_cash_or_latency': True,
        'source_bundles_retain_all_native_tasks_and_original_public_inputs': True,
        'development_only_for_acquisition_and_repairs': True,
        'calibration_and_structure_evaluation_once_after_library_freeze': True,
        'no_M1_generated_candidate_pool_supplied': True, 'model_weight_updates': False,
        'all_failures_and_teacher_calls_charged_in_original_ledger': True}
    out = BASE / 'ordinary_control_v1' / digest(protocol)
    immutable_json(out / 'prepared_protocol.json', protocol)
    for name, expected in binding.items():
        dest = out / 'source_snapshot' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / name).read_bytes()
        if dest.exists() and dest.read_bytes() != raw:
            raise ValueError('Prepared control source snapshot changed')
        if not dest.exists():
            dest.write_bytes(raw)
    for dataset, task in tasks.items():
        if len(render_structured_codex_prompt(SYSTEM, json.dumps(pack_teacher_payload(task), ensure_ascii=False))) > CODEX_TURN_INPUT_CHARACTER_LIMIT:
            raise ValueError('Complete independent teacher task exceeds the input cap; no truncation')
        immutable_json(out / 'teacher_inputs' / (dataset + '.json'), task)
    return out, protocol, lock, source_lock, train


def primary_budget(lock):
    protocol = read(BASE / 'pilot_reads_v3/protocol.json')
    train = {s['key']: s for s in read(PUBLIC)}
    from experiments.two_method_annotate import inputs
    expected = {digest([r['key'], v['view_id'], version]): (r['key'], v['view_id'], version) for r in lock['rows']
                for v in inputs(train[r['key']])[0]['views']
                for version in protocol['read_versions'][r['dataset']]}
    if any(not (BASE / 'pilot_reads_v3/reads' / key / 'decoded.json').exists() for key in expected):
        raise RuntimeError('Primary pilot is not terminal/complete; do not dispatch duplicate or overlapping work')
    for key, identity in expected.items():
        value = read(BASE / 'pilot_reads_v3/reads' / key / 'decoded.json')
        if (value['source'], value['opaque_source_view'], value['plan_version']) != identity:
            raise ValueError('A primary terminal output differs from the fixed cohort/view/version')
    if pending():
        raise RuntimeError('An actual physical request remains in flight')
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        rows = db.execute("SELECT id,status,result FROM calls WHERE role='executor' AND id LIKE 'two_method_pilot_reads_%'").fetchall()
    amount, identities = 0, []
    for identity, status, raw in rows:
        usage = json.loads(raw).get('usage', {})
        if status == 'reserved' or any(type(usage.get(k)) is not int for k in ('prompt_tokens', 'completion_tokens')):
            raise RuntimeError('Primary pilot cost is not fully settled and priced')
        amount += usage['prompt_tokens'] + usage['completion_tokens']
        identities.append(identity)
    return {'input_plus_output_token_cap': amount, 'primary_physical_request_ids': sorted(identities),
            'primary_expected_v3_outputs': len(expected), 'currency_or_latency_match_claimed': False}


def propose(teacher, out, task, dataset, stage, extra, schema):
    target = out / 'teacher_outputs' / dataset / (stage + '.json')
    if target.exists():
        return read(target)
    payload = {**task, 'stage': stage, **extra}
    ids = [x['source'] for x in task['fixed_development_examples']]
    identity = teacher.ledger.run_id + ':teacher:' + digest([dataset, stage, payload, schema])
    encoded = pack_teacher_payload(payload)
    immutable_json(target.with_name(stage + '_input.json'), encoded)
    result = teacher.propose(identity, source_ids=ids, system_prompt=SYSTEM,
                             user_prompt=json.dumps(encoded, ensure_ascii=False, sort_keys=True), output_schema=schema)
    record = {'physical_call_id': identity, 'stage': stage, 'value': result['value']}
    immutable_json(target, record)
    return record


def evaluate(program, rows, train, executor, out, stage, role):
    records = []
    for row in rows:
        if row['role'] != role:
            raise ValueError('Control evaluation role differs from its fixed source role')
        source = train[row['key']]
        if digest(source) != row['public_sha256']:
            raise ValueError('A fixed control source changed')
        bundle = source_bundle(source)
        tools, assets = legal_tools(source, bundle)
        path = out / 'predictions' / stage / (digest(row['key']) + '.json')
        if path.exists():
            record = read(path)
        else:
            runtime = ControlProgramRuntime(executor, out, max_calls=executor.token_cap,
                                           shared_assets=assets, legal_tools=tools)
            try:
                value = runtime.run(program, source, bundle)
                record = {'source': row['key'], 'role': role, 'answer': value['answer'],
                          'execution': value, 'error': value['error']}
            except Exception as error:
                execution_path = runtime.execution_path(program, source, bundle)
                record = {'source': row['key'], 'role': role, 'answer': None,
                          'error': type(error).__name__ + ': ' + str(error),
                          'execution': read(execution_path) if execution_path.exists() else None}
            immutable_json(path, record)  # Before opening native grading.
        records.append(record)
    grading = read(GRADING)
    scores = []
    for record in records:
        source = train[record['source']]
        answers = record['answer'] or {}
        native = {}
        for view in source['views']:
            if view['id'] not in answers:
                native[view['id']] = {'grade': 0., 'unresolved_or_failed': True}
            else:
                evidence = []
                for trace in (record.get('execution') or {}).get('traces', []):
                    candidate = trace.get('native_evidence', {})
                    if isinstance(candidate, dict) and view['id'] in candidate:
                        evidence = candidate[view['id']]
                native[view['id']] = grade_view(source['dataset'], view,
                    grading[source['key']][view['id']], answers[view['id']], evidence)
        score = sum(v['grade'] for v in native.values()) / len(native)
        scores.append({'source': source['key'], 'native': native, 'mother_score': score})
    result = {'role': role, 'stage': stage, 'scores': scores,
              'mother_macro': sum(v['mother_score'] for v in scores) / len(scores),
              'all_fixed_sources_in_denominator': True, 'predictions': records}
    immutable_json(out / 'scores' / (stage + '.json'), result)
    return result


def run():
    out, prepared, lock, sources, train = prepare()
    budget = primary_budget(lock)
    protocol = {**prepared, 'resolved_executor_budget': budget}
    immutable_json(out / 'protocol.json', protocol)
    immutable_json(BASE / 'ordinary_control_v1/active_protocol.json', {
        'artifact_root': str(out.relative_to(ROOT)), 'protocol_sha256': sha(out / 'protocol.json')})
    for path, expected in prepared['source_sha256'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('An active control binding changed before dispatch')
    ledger = EvolutionLedger(LEDGER, run_id='two_method_ordinary_control_v1_20261117',
        sources=sources['sources'], binding={'protocol_sha256': sha(out / 'protocol.json')})
    teacher = FrozenTeacher(ledger, out, prepared['teacher'])
    executor = TokenBudgetExecutor(FrozenExecutor(ledger, out, prepared['executor']), budget['input_plus_output_token_cap'])
    selected = {}
    for dataset in sorted(prepared['dataset_tasks_sha256']):
        task = read(out / 'teacher_inputs' / (dataset + '.json'))
        rows = [r for r in lock['rows'] if r['dataset'] == dataset and r['role'] == 'development']
        critique = propose(teacher, out, task, dataset, 'source_policy_critique',
            {'instruction': 'Derive source-supported policy rules, seed-case rationales and implementation advice; do not produce an inference lookup table.'}, CRITIQUE_SCHEMA)
        history = []
        for i in range(3):
            stage = dataset + '_candidate_' + str(i)
            best = max(history, key=lambda r: (r['evaluation']['mother_macro'], -r['index'])) if history else None
            response = propose(teacher, out, task, dataset, 'program_' + str(i),
                {'instruction': 'Acquire a general program.' if i == 0 else
                    'Repair the best program using complete native feedback and actual weak traces. You may revise predicates, extractors and composition. Preserve correct seed behavior.',
                 'source_policy_critique': critique['value'], 'previous_candidates': history,
                 'current_best_program': best['program'] if best else None}, proposal_schema())
            failure = None
            try:
                program = program_from_proposal(response['value'], sources['sources']['train'])
            except Exception as error:
                failure = {'candidate_index': i, 'source': response['physical_call_id'],
                           'error': type(error).__name__ + ': ' + str(error)}
                immutable_json(out / 'invalid_programs' / (stage + '.json'), failure)
                # A syntactically invalid candidate remains an observed failure;
                # a later fixed repair round sees that failure without retries.
                program = {'predicates': [], 'extractors': [],
                           'composition': 'def compose(inputs, predict, extractors):\n    return None\n'}
            evaluation = evaluate(program, rows, train, executor, out, stage, 'development')
            history.append({'index': i, 'program': program, 'proposal': response,
                            'validation_failure': failure, 'evaluation': evaluation})
        winner = max(history, key=lambda r: (r['evaluation']['mother_macro'], -r['index']))
        selected[dataset] = {'program': winner['program'], 'candidate_index': winner['index'],
                             'fixed_development_mother_macro': winner['evaluation']['mother_macro']}
        immutable_json(out / 'frozen_libraries' / (dataset + '.json'), selected[dataset])
    immutable_json(out / 'frozen_libraries.json', {'datasets': selected,
        'calibration_or_structure_evaluation_feedback_used_for_selection': False,
        'main_method_generated_interfaces_used': False})
    for role in ('calibration', 'structure_evaluation'):
        for dataset, selection in selected.items():
            rows = [r for r in lock['rows'] if r['role'] == role and r['dataset'] == dataset]
            if rows:
                evaluate(selection['program'], rows, train, executor, out, dataset + '_' + role, role)
    with ledger.transaction() as db:
        teacher_counts = db.execute('SELECT status,count(*) FROM calls WHERE role=? AND id LIKE ? GROUP BY status',
            ('teacher', ledger.run_id + ':%')).fetchall()
    if teacher_counts != [('completed', 20)]:
        raise ValueError('The fixed four-stage/five-library teacher accounting is incomplete')
    immutable_json(out / 'terminal.json', {'status': 'fixed_ordinary_control_evaluated',
        'executor_usage': settled_token_usage(ledger, ledger.run_id), 'teacher_request_counts': teacher_counts,
        'complete_two_method_goal': False, 'SCOPE_control_completed': False})
    print(json.dumps({'ordinary_control_complete': True, 'artifact_root': str(out)}, ensure_ascii=False), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--wait-for-pid', type=int)
    args = p.parse_args()
    if args.prepare:
        out, protocol, *_ = prepare()
        print(json.dumps({'prepared': str(out), 'datasets': len(protocol['dataset_tasks_sha256']),
                          'new_model_requests': 0}, ensure_ascii=False))
        return
    if args.wait_for_pid is not None:
        proc = Path('/proc') / str(args.wait_for_pid)
        if proc.exists():
            command = (proc / 'cmdline').read_bytes().split(b'\x00')
            if b'experiments.two_method_pilot_reads' not in command:
                raise RuntimeError('The proposed predecessor PID is not the actual pilot reader')
            start = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
        else:
            start = None
        print(json.dumps({'event': 'waiting_for_actual_pilot_exit', 'host_pid': args.wait_for_pid,
                          'observed_start_ticks': start, 'new_model_requests': 0}), flush=True)
        while start is not None:
            try:
                current = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
            except FileNotFoundError:
                break
            if current != start:
                break
            time.sleep(2)
        # A fresh interpreter binds exactly the bytes loaded at dispatch,
        # rather than retaining imported functions from the waiting period.
        os.execv(sys.executable, [sys.executable, '-m', 'experiments.two_method_ordinary_control'])
    run()


if __name__ == '__main__':
    main()
