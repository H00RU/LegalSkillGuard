"""Shared executable-program substrate for independent strong controls.

Predicates, deterministic text extractors and Python composition are all
expressible. All neural calls go through the frozen, ledger-bound executor.
This is an adaptation substrate, not a completed or official SCOPE run.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import select
import subprocess
import sys

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import GenerationHold
from legal_skill_guard.skill_evolution.native import record_schema, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.paired_interfaces.control_answers import decode_native, wire_schema

BUILTINS = {'min', 'max', 'sum', 'len', 'abs', 'round', 'sorted', 'all', 'any', 'int', 'float',
            'bool', 'str', 'list', 'dict', 'range', 'enumerate', 'zip', 'set', 'tuple'}
METHODS = {'findall', 'finditer', 'match', 'fullmatch', 'search', 'sub', 'escape', 'group', 'groups',
           'start', 'end', 'get', 'items', 'keys', 'values', 'append', 'extend', 'pop', 'sort', 'reverse',
           'lower', 'upper', 'strip', 'lstrip', 'rstrip', 'split', 'rsplit', 'splitlines',
           'startswith', 'endswith', 'find', 'rfind', 'replace', 'join', 'count', 'isdigit'}


def validate_function(source, name, arguments):
    tree = ast.parse(source)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError('One explicit pure function required')
    f = tree.body[0]
    if (f.name != name or [a.arg for a in f.args.args] != arguments or f.decorator_list
            or f.args.defaults or f.args.vararg or f.args.kwarg or f.args.kwonlyargs):
        raise ValueError('Program function signature differs from the declared contract')
    forbidden = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal,
                 ast.Lambda, ast.With, ast.AsyncWith, ast.AsyncFunctionDef, ast.Yield,
                 ast.YieldFrom, ast.Await)
    for node in ast.walk(tree):
        if isinstance(node, forbidden) or isinstance(node, ast.Name) and node.id.startswith('_'):
            raise ValueError('Unsupported effectful or reflective program')
        if isinstance(node, ast.FunctionDef) and node is not f:
            raise ValueError('Nested functions are not an extractor declaration')
        if isinstance(node, ast.Attribute) and node.attr not in METHODS:
            raise ValueError('Unsupported object capability')
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                callbacks = {'predict', 'apply_legal'} if name == 'compose' else set()
                if node.func.id not in BUILTINS | callbacks:
                    raise ValueError('Calls use deterministic primitives or the recorded predicate callback')
            elif isinstance(node.func, ast.Subscript):
                if not isinstance(node.func.value, ast.Name) or node.func.value.id != 'extractors':
                    raise ValueError('Dynamic call is not a declared extractor')
            elif not isinstance(node.func, ast.Attribute):
                raise ValueError('Unsupported call target')
    return True


def validate_program(program):
    identities = [p['id'] for p in program['predicates']]
    names = [p['id'] for p in program['extractors']]
    if len(identities) != len(set(identities)) or len(names) != len(set(names)):
        raise ValueError('Duplicate predicate or extractor identity')
    for extractor in program['extractors']:
        validate_function(extractor['code'], 'extract', ['inputs'])
    validate_function(program['composition'], 'compose', ['inputs', 'predict', 'extractors'])
    for predicate in program['predicates']:
        if predicate['schema_mode'] not in ('fixed', 'native'):
            raise ValueError('Unknown predicate output contract')
        if predicate['schema_mode'] == 'fixed':
            jsonschema.Draft202012Validator.check_schema(predicate['schema'])
    return True


class ProgramBudgetExhausted(RuntimeError):
    pass


class ControlProgramRuntime:
    def __init__(self, executor, artifact_root, *, max_calls, shared_assets=None, legal_tools=None):
        if type(max_calls) is not int or max_calls < 1:
            raise ValueError('The comparison protocol must explicitly provide a shared neural-call budget')
        self.executor, self.root, self.max_calls = executor, Path(artifact_root), max_calls
        self.shared_assets = {} if shared_assets is None else json.loads(json.dumps(shared_assets))
        self.legal_tools = {} if legal_tools is None else dict(legal_tools)
        self.tool_bindings = {name: {k: v for k, v in tool.items() if k != 'invoke'}
                              for name, tool in self.legal_tools.items()}
        for name, tool in self.legal_tools.items():
            if not tool.get('binding_sha256') or not callable(tool.get('invoke')):
                raise ValueError('A legal tool needs its explicit immutable binding and pure host callback')
            jsonschema.Draft202012Validator.check_schema(tool['input_schema'])

    def execution_path(self, program, source, view, *, purpose='skill_actor'):
        identity = digest({'program': program, 'source': source['key'], 'view': view, 'purpose': purpose,
                           'shared_assets': self.shared_assets, 'legal_tools': self.tool_bindings,
                           'max_neural_calls': self.max_calls, 'runtime_contract': 'native-bundle-tools-v2'})
        return self.root / 'program_executions' / identity / 'result.json'

    def run(self, program, source, view, *, purpose='skill_actor'):
        validate_program(program)
        output = self.execution_path(program, source, view, purpose=purpose)
        identity = output.parent.name
        if output.exists():
            return json.loads(output.read_text())
        predicates = {p['id']: p for p in program['predicates']}
        message = {'program': program, 'inputs': {'public': view['public'],
            'native_answer_schema': view['answer_schema'], 'dataset': source['dataset'],
            'native_wire_schema': wire_schema(source['dataset'], view),
            'legal_tools': self.tool_bindings, 'shared_assets': self.shared_assets}}
        immutable_json(output.with_name('input.json'), message)
        process = subprocess.Popen([sys.executable, '-B', '-m',
            'legal_skill_guard.paired_interfaces.control_worker'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        traces, result, error = [], None, None
        held_before_request = False
        try:
            process.stdin.write(json.dumps(message, ensure_ascii=False) + '\n')
            process.stdin.flush()
            while True:
                readable, _, _ = select.select([process.stdout], [], [], 30)
                if not readable:
                    raise TimeoutError('Pure composition did not reach a result or a predicate boundary')
                line = process.stdout.readline()
                if not line:
                    raise RuntimeError('Composition worker exited without a final result')
                event = json.loads(line)
                if event['type'] == 'result':
                    result = event['answer']
                    jsonschema.validate(result, view['answer_schema'])
                    break
                if event['type'] not in ('predicate', 'legal_tool') or event['sequence'] != len(traces):
                    raise ValueError('Invalid predicate callback sequence')
                if event['type'] == 'legal_tool':
                    tool = self.legal_tools[event['tool_id']]
                    jsonschema.validate(event['input'], tool['input_schema'])
                    trace = {'type': 'legal_tool', 'tool': event['tool_id'], 'input': event['input'],
                             'binding_sha256': tool['binding_sha256'], 'status': 'dispatched'}
                    traces.append(trace)
                    value = tool['invoke'](event['input'])
                    json.dumps(value, allow_nan=False)
                    trace.update(value=value, status='validated', new_model_requests=0)
                    process.stdin.write(json.dumps({'value': value}, ensure_ascii=False) + '\n')
                    process.stdin.flush()
                    continue
                if sum(t.get('type', 'predicate') == 'predicate' for t in traces) >= self.max_calls:
                    raise ProgramBudgetExhausted('Declared shared comparison budget exhausted before next call')
                predicate = predicates[event['predicate_id']]
                specification = wire_schema(source['dataset'], view) if predicate['schema_mode'] == 'native' else predicate['schema']
                schema = record_schema({'value': specification})
                messages = [{'role': 'system', 'content': predicate['prompt']
                    + '\nReturn compact JSON matching this exact schema: '
                    + json.dumps(schema, ensure_ascii=False, separators=(',', ':'))},
                    {'role': 'user', 'content': json.dumps(event['input'], ensure_ascii=False, sort_keys=True)}]
                call_id = self.executor.ledger.run_id + ':program:' + digest({
                    'execution': identity, 'sequence': event['sequence'], 'messages': messages, 'schema': schema})
                trace = {'type': 'predicate', 'predicate': event['predicate_id'], 'input': event['input'],
                    'schema': schema, 'logical_call_id': call_id, 'physical_call_id': call_id,
                    'status': 'dispatched'}
                traces.append(trace)
                response = self.executor.generate(call_id, source=source['key'], purpose=purpose,
                    messages=messages, thinking=False, schema=schema)
                trace.update(physical_call_id=response.get('reused_physical_call_id', call_id),
                    usage=response['usage'], elapsed_seconds=response['elapsed_seconds'],
                    cache_hit=bool(response.get('cache_hit')), raw_content=response['content'],
                    finish_reason=response['finish_reason'], status='response_received')
                if response['finish_reason'] != 'stop':
                    raise ValueError('Predicate response is incomplete; do not repair a partial result')
                value = json.loads(response['content'])
                value, enum_receipt = restore_enum_transport(value, schema)
                jsonschema.validate(value, schema)
                decoded = value['value']
                if predicate['schema_mode'] == 'native':
                    decoded, evidence = decode_native(source['dataset'], view, decoded)
                    trace['native_evidence'] = evidence
                trace.update(value=decoded, public_enum_transport=enum_receipt, status='validated')
                process.stdin.write(json.dumps({'value': decoded}, ensure_ascii=False) + '\n')
                process.stdin.flush()
        except Exception as exc:
            held_before_request = isinstance(exc, GenerationHold)
            error = type(exc).__name__ + ': ' + str(exc)
            raise
        finally:
            if process.poll() is None:
                if result is not None and error is None:
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                else:
                    process.kill()
            process.wait(timeout=5)
            record = {'source': source['key'], 'view': view['id'], 'program_sha256': digest(program),
                'answer': result, 'traces': traces, 'error': error, 'fallback_executed': False,
                'worker_returncode': process.returncode, 'worker_stderr': process.stderr.read(),
                'core_executed': result is not None and error is None,
                'model_parameters_updated': False, 'new_independent_trial_claimed_for_cached_reads': False}
            destination = (output.parent / 'generation_interruptions' / (digest(record) + '.json')
                           if held_before_request else output)
            immutable_json(destination, record)
            process.stdin.close(); process.stdout.close(); process.stderr.close()
        return record
