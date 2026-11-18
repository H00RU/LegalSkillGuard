"""Compare paired allocation reads on the fixed OpenExempt TRAIN variant group."""

import argparse
import json
import sqlite3

import jsonschema

from experiments.convergence_oe_feedback_pair import OE, POINTER as FEEDBACK, ROLES, materials, support
from experiments.convergence_oe_scoped_proposal import OWNERSHIP_FIELD
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'B8_OE_joint_component_current.json'
COMPONENTS = ('forwarded', 'withheld')
SCHEMA = record_schema({part: {'type': 'string', 'enum': ['full', 'zero', 'unresolved']} for part in COMPONENTS})
SYSTEM = (
    'Read the named asset in this one source text under the supplied reader policy. '
    'Return the forwarded and withheld allocations together for that same asset. '
    'Debtor ownership forwards the full value and withholds zero. '
    'Nonownership withholds the full value and forwards zero. '
    'The stated amount alone does not establish either title or allocation. '
    'Use unresolved for each component that the policy leaves unresolved. '
    'Return only the two requested tags.'
)


def group_versions(context):
    """Keep the original query ordering for independent and shared validation."""
    versions = {}
    for index, query in enumerate(context['inputs']):
        common = {k: v for k, v in query.items() if k != 'requested_component'}
        version = versions.setdefault(digest(common), {'public': common, 'indices': {}})
        component = query['requested_component']
        if component in version['indices']:
            raise ValueError('A source version has repeated allocation queries')
        version['indices'][component] = index
    if len(versions) != 2 or any(set(v['indices']) != set(COMPONENTS) for v in versions.values()):
        raise ValueError('Use the original and edited amounts with both components in each')
    return versions


def bound_materials():
    spec, _, base, _, _, _, context, _ = materials()
    stage = ROOT / read(FEEDBACK)['artifact_root']
    original, earned = (read(stage / name) for name in ('binding.json', 'terminal.json'))
    if (stage.name != digest(spec) or stage.name != digest(original) or earned['status'] != 'completed_B8_OE_feedback_pair'
            or earned['TEST_opened'] or read(stage / 'source_snapshot_receipt.json')['files'] != original['source_sha256']):
        raise ValueError('Use the completed paired feedback study and its exact source archive')
    failure = read(stage / 'shared_explanation.json')['audit']
    if (failure['support'] != {'shared': {'retained': 0, 'possible': 2},
                              'independent_completions': {'retained': 2, 'possible': 16}}
            or [r['read_tag'] for r in failure['typed_reads']] != ['zero', 'zero', 'zero', 'unresolved']
            or earned['outcome']['shared_feedback_minus_independent']['EC'] <= 0.0):
        raise ValueError('The joint reading intervention requires the measured conflicting native-positive proposal')
    programs = {'incumbent': base['programs'][OE]}
    for role in ROLES:
        program = read(stage / (role + '.json'))['candidate']
        if digest(program) != earned['outcome']['condition_results'][role]['program_sha256']:
            raise ValueError('A matched feedback proposal changed')
        programs[role] = program
    versions = group_versions(context)
    paths = {*spec['source_sha256'], str(__file__).removeprefix(str(ROOT) + '/')}
    binding = {'stage': 'OpenExempt_paired_allocation_read_after_B8_feedback',
               'feedback_terminal_sha256': sha(stage / 'terminal.json'),
               'context_binding_sha256': digest(context['binding']),
               'queries_sha256': digest(versions), 'wire_sha256': digest([SYSTEM, SCHEMA]),
               'program_sha256': {name: digest(program) for name, program in programs.items()},
               'source_sha256': {path: sha(ROOT / path) for path in sorted(paths)},
               'executor': spec['executor'], 'planned_requests': 6, 'TEST_opened': False}
    return binding, context, versions, programs


def run(execute):
    binding, context, versions, programs = bound_materials()
    out = BASE / 'B8_OE_joint_component' / digest(binding)
    if (HANDOFF / 'formal_B8_TEST_current.json').exists():
        raise ValueError('Finish TRAIN diagnostics before the held-out freeze')
    if execute and (not POINTER.exists() or ROOT / read(POINTER)['artifact_root'] != out):
        raise ValueError('Use the prepared common wire and unchanged native proposals')
    immutable_json(out / 'binding.json', binding)
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json'), sort_keys=True), flush=True)
        return
    if not execute:
        write_status(out, {'status': 'prepared', 'planned_requests': 6, 'TEST_opened': False}, POINTER)
        print(out.relative_to(ROOT), flush=True)
        return

    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('The serial generation slot is in use')
    root, = {case.root_id for case in context['cases']}
    run_id = 'convergence-B8-OE-joint-component-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': [root], 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    outcomes = {}
    for role, program in programs.items():
        write_status(out, {'status': 'running', 'arm': role, 'TEST_opened': False}, POINTER)
        rows = {}
        for version, query in versions.items():
            public = query['public']
            payload = {**public, 'quoted_reader_policy': program[OWNERSHIP_FIELD]}
            messages = [{'role': 'system', 'content': SYSTEM},
                        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, sort_keys=True)}]
            identity = run_id + ':projection:' + digest([role, version, messages, SCHEMA])
            raw = reader.generate(identity, source=root, purpose='skill_actor', messages=messages,
                                  schema=SCHEMA, thinking=False)
            verify_physical_response(reader, identity=identity, source=root, purpose='skill_actor',
                                     content_sha256=digest(raw['content']), usage=raw['usage'],
                                     finish_reason=raw['finish_reason'])
            try:
                if raw['finish_reason'] != 'stop':
                    raise ValueError('Incomplete paired allocation read')
                tags = json.loads(raw['content'])
                jsonschema.validate(tags, SCHEMA)
                amount = public['independently_verified_source_facts']['stated_value_dollars']
                values = {part: {'full': amount, 'zero': 0, 'unresolved': None}[tag] for part, tag in tags.items()}
                failure = None
            except (ValueError, jsonschema.ValidationError) as error:
                values, tags, failure = dict.fromkeys(COMPONENTS), dict.fromkeys(COMPONENTS), type(error).__name__
            for part, index in query['indices'].items():
                rows[index] = {'read_tag': tags[part], 'value': values[part], 'failure': failure,
                               'request': identity, 'case': context['cases'][index].source_id}
        ordered = [rows[i] for i in range(len(context['cases']))]
        same_scope = support(context, ordered) if all(r['failure'] is None for r in ordered) else None
        outcomes[role] = {'tags': [r['read_tag'] for r in ordered], 'support': same_scope}
        immutable_json(out / (role + '.json'), {'responses': ordered, **outcomes[role]})
    with ledger.transaction() as db:
        calls = db.execute("select status,result from calls where id like ?", (run_id + ':%',)).fetchall()
    if len(calls) != binding['planned_requests'] or any(status != 'completed' for status, _ in calls):
        raise ValueError('All three programs need their two actual paired allocation requests')
    result = {'status': 'completed_B8_OE_joint_component', 'outcomes': outcomes,
              'executor_calls': len(calls), 'executor_tokens': sum(json.loads(raw)['usage']['total_tokens']
                  for _, raw in calls), 'new_native_calls': 0, 'new_teacher_calls': 0, 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'TEST_opened': False}, POINTER)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
