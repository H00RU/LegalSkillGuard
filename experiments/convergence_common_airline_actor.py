"""Use the same proven fee reader in every formal arm on its public scope."""

import json

import jsonschema

from experiments.convergence_airline_joint_relation import BAG
from experiments.convergence_airline_structured_update import compose_public_rules, literal_schema, measure
from legal_skill_guard.paired_interfaces.airline_public_fees import compile_rule, local_charges, public_domestic_scope
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.skill_evolution.objects import digest


def supported_fee_rule(source):
    if source['dataset'] != 'RuleArena_Airline' or [task['id'] for task in source['views']] != ['native']:
        return None
    public = source['views'][0]['public']
    scope = public_domestic_scope(public)
    if scope is None:
        return None
    literal_bags = list(BAG.finditer(public['facts']))
    if [int(item[1]) for item in literal_bags] != list(range(1, len(literal_bags) + 1)):
        return None
    try:
        rule = compile_rule(public['source_text'], cabin=scope['cabin'])
        local_charges(rule, [{'dimensions': [int(item[i]) for i in (2, 3, 4)], 'weight': int(item[5])}
                             for item in literal_bags])
    except ValueError:
        return None
    return rule


class CommonAirlineActor:
    def __init__(self, actor, executor, root):
        self.actor, self.executor, self.root = actor, executor, root

    @staticmethod
    def _result(rule, measured):
        answer = measured['predictions']['match_bag_max']
        return {'native': {'native': {'handled': answer is not None, 'answer': answer,
                                      'evidence_sentence_ids': [], 'fallback_executed': False}},
                'scoped_common_fee_rule_sha256': digest(rule), 'measured': measured, 'fallback_executed': False}

    def __call__(self, source, library, purpose):
        rule = supported_fee_rule(source)
        if rule is None:
            return self.actor(source, library, purpose)
        return self._result(rule, measure(self.executor, source, self.root, compiled_rule=rule, purpose=purpose))

    def verify_saved(self, source, library, purpose, result):
        rule = supported_fee_rule(source)
        if rule is None:
            self.actor.verify_saved(source, library, purpose, result)
            return
        measured = result['measured']
        if measured['source_sha256'] != digest(source) or not self.root.joinpath(
                'measurements', digest(source) + '.json').is_file():
            raise ValueError('A common fee prediction must retain its exact public measurements')
        artifact = json.loads(self.root.joinpath('measurements', digest(source) + '.json').read_text())
        if artifact != measured:
            raise ValueError('The shared compiled execution differs from the saved read')
        identity = measured['physical_call_id']
        with self.executor.ledger.transaction() as db:
            record = db.execute('select result from calls where id=?', (identity,)).fetchone()
        if record is None or record[0] is None:
            raise ValueError('The shared fee calculation has no settled response')
        physical = json.loads(record[0])
        verify_physical_response(self.executor, identity=identity, source=source['key'], purpose=purpose,
            content_sha256=digest(physical['content']), usage=measured['usage'], finish_reason=physical['finish_reason'])
        bag_count = len(list(BAG.finditer(source['views'][0]['public']['facts'])))
        try:
            if physical['finish_reason'] != 'stop':
                raise ValueError('Incomplete physical read')
            decoded = json.loads(physical['content'])
            jsonschema.validate(decoded, literal_schema(bag_count))
            calculated = compose_public_rules(decoded, bag_count, rule)
        except (ValueError, jsonschema.ValidationError):
            if measured['production_error'] is None or any(v is not None for v in measured['predictions'].values()):
                raise ValueError('Invalid literal fee input cannot yield an asserted native answer')
        else:
            if measured['production_error'] is not None or measured['predictions'] != calculated:
                raise ValueError('The saved fee result must replay the original literals and public consumer')
        if result != self._result(rule, measured):
            raise ValueError('Native output must match the shared compiled consumer')
