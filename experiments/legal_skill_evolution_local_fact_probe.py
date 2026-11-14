"""Two fixed TRAIN local-fact probes using the preserved flat signed-atom wire.

No full training, test labels, teacher request, thinking/config scan, synthetic
prompt example or new source. This tests source representation, not method gains.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_gap_acquisition as e
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.legal_predicate_skills import FACT
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

RUN = 'legal_skill_evolution_local_facts_20261114'
OUT = e.ROOT / 'artifacts' / RUN
PREDICATES = {
    'action': ['id', 'kind', 'material_quote'],
    'event': ['id', 'kind'],
    'any_of': ['group_id', 'left_id', 'right_id'],
    'all_of': ['group_id', 'left_id', 'right_id'],
    'trigger': ['action_or_action_group_id', 'event_or_event_group_id'],
    'timing': ['action_or_action_group_id', 'timing_quote'],
    'actor': ['action_or_action_group_id', 'actor_quote'],
}
GROUNDED = deepcopy(FACT)
GROUNDED['properties']['unit_id'] = {'type': 'integer'}
GROUNDED['required'].append('unit_id')
SCHEMA = obj({'facts': {'type': 'array', 'items': GROUNDED},
    'unresolved': {'type': 'array', 'items': {'type': 'string'}}})
SYSTEM = '''Extract an executable graph of SOURCE FACTS for the focus clauses.
Do not answer any legal benchmark question. Read the full original contract for
context, but describe ONLY disposal actions imposed in the given focus units.
Use the flat signed-atom schema. Each atom has a declared predicate and ordered
string arguments. IDs such as a1/e1/g1 are local node identifiers, never answers.

action(id,kind,material_quote): kind is return or destroy. material_quote is an
EXACT short substring of that action's unit describing its own material; do not
copy the return material into destruction unless the clause actually shares it.
event(id,kind): kind is request, agreement_end, or project_end. Expiration and
termination of the Agreement count as agreement_end; ending the Project is a
different event. Do not infer an end event from the verb destroy or return.
any_of(group,left,right) encodes OR. all_of(group,left,right) encodes AND. Group
members must be both actions/action groups or both events/event groups. Recursion
allows more than two members. Do not turn an alternative into two duties.
trigger(action_or_group,event_or_group): that event/group activates THAT action
or group. Separate actions with different triggers. Two alternative events for
one action can use any_of; independent trigger facts also give separate branches.
timing(action_or_group,timing_quote): optional exact raw timing qualifier. Keep
branch-dependent text, e.g. time after receipt of demand, verbatim. Do not silently
transfer a request-specific deadline to a different event. actor(action_or_group,
actor_quote): optional exact stated actor; unresolved implicit actors stay unknown.

Every fact includes unit_id and quote: a short VERBATIM supporting substring of
the cited current unit. Node facts cite their own clause. A cross-unit trigger
edge can cite its governing header; the action/event nodes retain both sources.
Use positive=true for these positive facts. No invented negative/absence facts.
All predicate names and arities must match the supplied signatures. No variables
or free-text reasoning in arguments. Every referenced node must be declared.
Do not complete omitted obligations or missing referenced rules; put remaining
interpretation limits in unresolved. Return only the schema object.
'''


def setup():
    path = OUT / 'protocol.json'
    if not path.exists():
        previous, _, public = e.setup()
        tasks = []
        for prefix, ids in [('e7b78d42', [34]), ('6fce8464', [15, 20, 21])]:
            key = next(k for k in previous['acquisition_sources'] if k.startswith('ContractNLI:' + prefix))
            source, units, _ = e.previous.prior.prior.source_material(e.previous.PARENT, public, key)
            selected = [u for u in units if u['id'] in ids]
            assert len(selected) == len(ids)
            tasks.append({'source': key, 'full_source_text': source['source_text'],
                'focus_units': selected, 'all_current_units': units})
        immutable_json(OUT / 'tasks.json', tasks)
        rows = e.previous.prior.rows(); assert not any(r[6] == 'reserved' for r in rows)
        immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in rows})
        files = [Path(__file__), e.ROOT / 'legal_skill_guard/rr/legal_predicate_skills.py',
            e.ROOT / 'legal_skill_guard/skill_evolution/clients.py', e.ROOT / 'legal_skill_guard/skill_evolution/ledger.py']
        for f in files:
            dst = OUT / 'source_snapshot' / f.relative_to(e.ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
        immutable_json(path, {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
            'sources': [t['source'] for t in tasks], 'executor_profile': previous['executor_profile'],
            'planned_source_representation_probes': 2, 'teacher_requests': 0,
            'no_full_training_DEV_TEST_or_paper': True, 'schema': SCHEMA, 'system': SYSTEM,
            'no_new_source_or_synthetic_prompt_example': True, 'thinking': False,
            'source_sha256': {str(f.relative_to(e.ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
            'tasks_sha256': hashlib.sha256((OUT / 'tasks.json').read_bytes()).hexdigest()})
    protocol = e.read(path)
    for f, sha in protocol['source_sha256'].items():
        assert hashlib.sha256((e.ROOT / f).read_bytes()).hexdigest() == sha, f
    assert hashlib.sha256((OUT / 'tasks.json').read_bytes()).hexdigest() == protocol['tasks_sha256']
    ledger = EvolutionLedger(e.previous.prior.prior.LEDGER, run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    return protocol, ledger, e.read(OUT / 'tasks.json')


def compile_facts(value, units):
    """Ground the existing signed-fact wire and execute its finite typed graph."""
    import jsonschema
    jsonschema.validate(value, SCHEMA)
    by_unit = {u['id']: u['text'] for u in units}
    nodes = {}; groups = {}; triggers = []; timings = []; provenance = {}
    for row in value['facts']:
        atom = row['atom']; name = atom['predicate']; args = atom['arguments']
        if name not in PREDICATES or len(args) != len(PREDICATES[name]):
            raise ValueError('Wrong predicate/arity: ' + name)
        if not atom['positive'] or any(not x or x.startswith('?') for x in args):
            raise ValueError('Positive grounded graph facts required; no missing-fact negation')
        if row['unit_id'] not in by_unit or not row['quote'] or row['quote'] not in by_unit[row['unit_id']]:
            raise ValueError('Fact evidence is not verbatim in the stated current unit')
        if name in ('action', 'event', 'any_of', 'all_of'):
            identity = args[0]
            if identity in nodes or identity in groups:
                raise ValueError('Distinct current graph node identifiers required')
            if name == 'action':
                if args[1] not in ('return', 'destroy') or args[2] not in by_unit[row['unit_id']]:
                    raise ValueError('Action kind and material must be current source readings')
                nodes[identity] = ('action', args[1], args[2])
            elif name == 'event':
                if args[1] not in ('request', 'agreement_end', 'project_end'):
                    raise ValueError('Explicit current event kind required')
                nodes[identity] = ('event', args[1])
            else:
                groups[identity] = (name, args[1], args[2])
            provenance[identity] = [row['unit_id']]
        elif name == 'trigger':
            triggers.append((args[0], args[1], row['unit_id']))
        elif name in ('timing', 'actor'):
            if args[1] not in by_unit[row['unit_id']]:
                raise ValueError('Quoted timing/actor cannot be paraphrased')
            if name == 'timing': timings.append(args)
    def resolve(identity, stack=()):
        if identity in stack:
            raise ValueError('Cyclic source graph')
        if identity in nodes:
            return nodes[identity], set(provenance[identity])
        if identity not in groups:
            raise ValueError('Undeclared graph node: ' + identity)
        op, left, right = groups[identity]
        a, ap = resolve(left, (*stack, identity)); b, bp = resolve(right, (*stack, identity))
        def sort(t):
            return t[0] if t[0] in ('event', 'action') else sort(t[1])
        if sort(a) != sort(b):
            raise ValueError('An action/event mixed group is ill-typed')
        children = sorted([a, b], key=repr)
        return (op, *children), ap | bp | set(provenance[identity])
    def kind(t):
        return t[0] if t[0] in ('action', 'event') else kind(t[1])
    bindings = []
    for action, event, unit in triggers:
        a, ap = resolve(action); b, bp = resolve(event)
        if kind(a) != 'action' or kind(b) != 'event':
            raise ValueError('Trigger must join an action to its event')
        bindings.append({'action': a, 'event': b, 'support_ids': sorted(ap | bp | {unit})})
    for target, _ in timings:
        t, _ = resolve(target)
        if kind(t) != 'action': raise ValueError('Timing needs its own current action')
    return {'bindings': bindings, 'timings': timings, 'unresolved': value['unresolved'],
        'source_semantics_certified': False, 'strict_type_and_quote_checks': True}


def request():
    protocol, ledger, tasks = setup()
    client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
    for task in tasks:
        dst = OUT / 'results' / e.name_for(task['source'])
        if dst.exists(): continue
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': json.dumps({
            'predicates': PREDICATES, 'full_source_text': task['full_source_text'],
            'focus_units': task['focus_units']}, ensure_ascii=False)}]
        result = client.generate(RUN + ':' + task['source'], source=task['source'], purpose='skill_replay',
            messages=messages, thinking=False, schema=SCHEMA)
        try:
            value = json.loads(result['content']); executed = compile_facts(value, task['all_current_units'])
            status = {'status': 'typed_graph_executed', 'executed': executed}
        except Exception as error:
            status = {'status': 'rejected', 'error_type': type(error).__name__, 'error': str(error)}
        immutable_json(dst, {'source': task['source'], 'physical_response': result, 'validation': status,
            'not_a_C_or_U_contribution_pass': True})
        print(json.dumps({'source': task['source'], 'validation': status}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['preflight', 'run'])
    phase = parser.parse_args().phase
    with (e.ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if phase == 'preflight':
            setup(); print(json.dumps({'offline': True, 'physical_requests': 0}), flush=True)
        else:
            request()
