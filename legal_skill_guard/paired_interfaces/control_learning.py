"""Independent program acquisition contracts and measured token accounting."""
import json
from collections import Counter
import hashlib

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.paired_interfaces.control_programs import validate_program
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.native import record_schema


def proposal_schema():
    predicate = record_schema({'id': {'type': 'string'}, 'prompt': {'type': 'string'},
        'schema_mode': {'type': 'string', 'enum': ['fixed', 'native']}, 'schema_json': {'type': 'string'}})
    program = record_schema({'predicates': {'type': 'array', 'items': predicate},
        'extractors': {'type': 'array', 'items': record_schema({'id': {'type': 'string'}, 'code': {'type': 'string'}})},
        'composition': {'type': 'string'}})
    return record_schema({'program': program, 'policy_rationale': {'type': 'string'},
        'changes_from_previous': {'type': 'array', 'items': {'type': 'string'}}})


CRITIQUE_SCHEMA = record_schema({'policy_rules': {'type': 'array', 'items': {'type': 'string'}},
    'seed_rationales': {'type': 'array', 'items': record_schema({
        'source': {'type': 'string'}, 'rationale': {'type': 'string'}})},
    'implementation_advice': {'type': 'string'}})


def direct_program():
    return {'predicates': [{'id': 'native', 'schema_mode': 'native', 'schema': {},
        'prompt': 'Answer every supplied native task using its own full public input, including supplied statutes, solved givens, facts and question. Keep different native views separate. Return the native answers and any requested source evidence in the exact supplied wire schema.'}],
        'extractors': [], 'composition': "def compose(inputs, predict, extractors):\n    return predict('native', {'public': inputs['public'], 'answer_schema': inputs['native_answer_schema']})\n"}


def program_from_proposal(value, source_ids):
    program = value['program']
    result = {'predicates': [{k: v for k, v in p.items() if k != 'schema_json'}
                            | {'schema': json.loads(p['schema_json'])} for p in program['predicates']],
              'extractors': program['extractors'], 'composition': program['composition']}
    validate_program(result)
    # Full dataset identities may be evidence provenance for the teacher, but
    # cannot become an inference lookup table in the learned program.
    if any(source in json.dumps(result, ensure_ascii=False) for source in source_ids):
        raise ValueError('A source identity was embedded in the inference program')
    return result


def validate_teacher_schemas():
    for schema in (proposal_schema(), CRITIQUE_SCHEMA):
        issues = strict_output_schema_issues(schema)
        if issues:
            raise ValueError('A teacher contract is not transport-ready: ' + str(issues))


def pack_teacher_payload(payload):
    """Deduplicate identical long strings without deleting any feedback."""
    counts = Counter()
    def count(value):
        if isinstance(value, str) and len(value) >= 256:
            counts[value] += 1
        elif isinstance(value, dict):
            for v in value.values():
                count(v)
        elif isinstance(value, list):
            for v in value:
                count(v)
    count(payload)
    texts, locations = {}, []
    def encode(value, path):
        if isinstance(value, str) and counts[value] > 1:
            key = hashlib.sha256(value.encode()).hexdigest()
            texts[key] = value
            locations.append(path)
            return {'$shared_text': key}
        if isinstance(value, dict):
            return {k: encode(v, path + [k]) for k, v in value.items()}
        if isinstance(value, list):
            return [encode(v, path + [i]) for i, v in enumerate(value)]
        return value
    encoded = encode(payload, [])
    return {'encoding': 'lossless_identical_long_string_table_v1', 'text_table': texts,
            'referenced_string_paths': locations, 'payload': encoded}


def unpack_teacher_payload(record):
    value = json.loads(json.dumps(record['payload']))
    for path in record['referenced_string_paths']:
        parent = value
        for key in path[:-1]:
            parent = parent[key]
        reference = parent[path[-1]] if path else value
        text = record['text_table'][reference['$shared_text']]
        if hashlib.sha256(text.encode()).hexdigest() != reference['$shared_text']:
            raise ValueError('An exact shared teacher text changed')
        if path:
            parent[path[-1]] = text
        else:
            value = text
    return value


def settled_token_usage(ledger, prefix):
    with ledger.transaction() as db:
        rows = db.execute('SELECT id,status,result FROM calls WHERE id LIKE ? AND role=?',
                          (prefix + ':%', 'executor')).fetchall()
    count, tokens, unknown, pending = 0, 0, [], []
    for identity, status, raw in rows:
        if status == 'reserved':
            pending.append(identity)
            continue
        count += 1
        value = json.loads(raw)
        usage = value.get('usage', {})
        if any(type(usage.get(k)) is not int for k in ('prompt_tokens', 'completion_tokens')):
            unknown.append(identity)
        else:
            tokens += usage['prompt_tokens'] + usage['completion_tokens']
    return {'settled_physical_requests': count, 'known_input_plus_output_tokens': tokens,
            'unpriced_requests': unknown, 'pending_requests': pending}


class TokenBudgetExecutor:
    """Allow shorter calls within the same measured executor-token ceiling.

    This is a comparison budget, not a revival of historical request caps.
    Full unchanged max_tokens is reserved before a new physical generation.
    Unknown charged usage blocks further spending until it is reconciled.
    """
    def __init__(self, executor, token_cap):
        self.executor, self.ledger = executor, executor.ledger
        if type(token_cap) is not int or token_cap <= 0:
            raise ValueError('A positive comparison budget must be resolved from actual primary reads')
        self.token_cap = token_cap

    def generate(self, call_id, **kwargs):
        with self.ledger.transaction() as db:
            old = db.execute('SELECT status FROM calls WHERE id=?', (call_id,)).fetchone()
        if old:
            return self.executor.generate(call_id, **kwargs)
        used = settled_token_usage(self.ledger, self.ledger.run_id)
        if used['pending_requests'] or used['unpriced_requests']:
            raise BudgetError('Settle/reconcile actual control requests before further budgeted generation')
        count = self.executor.tokenize(kwargs['messages'], thinking=False)['count']
        reservation = count + self.executor.config['max_tokens']
        if used['known_input_plus_output_tokens'] + reservation > self.token_cap:
            raise BudgetError('Shared measured token budget exhausted before the next physical request')
        return self.executor.generate(call_id, **kwargs)
