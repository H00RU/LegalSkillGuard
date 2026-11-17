"""Prefix-matched comparison budgets with exact-observation reuse.

Physical ledger costs are never reset. Each control arm also charges each
distinct source/purpose/frozen wire observation once,including old paid cache
hits. Repeating a callback is not another independent observation or cost.
Unknown metering consumes the unchanged serving-context upper bound.
"""
import hashlib
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces.control_accounting import usage_summary
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.objects import digest


class ComparisonBudgetExhausted(BudgetError):
    """A recorded pre-generation comparison refusal,not a physical failure."""


def primary_comparison_cap(ledger, paired_records, *, context_tokens):
    identities = sorted({row['physical_call_id'] for row in paired_records})
    rows = []
    with ledger.transaction() as db:
        for identity in identities:
            row = db.execute('select role,purpose,status,result from calls where id=?', (identity,)).fetchone()
            if row is None or row[:3] != ('executor', 'skill_actor', 'completed'):
                raise BudgetError('A primary comparison observation is not a completed TRAIN physical read')
            rows.append((identity, row[2], row[3]))
    summary = usage_summary(rows, context_tokens=context_tokens)
    return {'primary_physical_response_ids': identities, 'unique_primary_observations': len(identities),
            'input_plus_output_token_cap': summary['conservatively_charged_input_plus_output_tokens'],
            'primary_usage': summary, 'old_paid_responses_count_as_logical_training_information': True,
            'physical_cost_is_reported_separately': True}


class PrefixBudgetExecutor:
    def __init__(self, executor, root):
        self.executor, self.ledger, self.config = executor, executor.ledger, executor.config
        self.root = Path(root)
        self.token_cap, self.batch = 0, 0
        self.limit = None

    def set_limit(self, batch, evidence):
        cap = evidence['input_plus_output_token_cap']
        if (type(batch) is not int or not 1 <= batch <= 8 or type(cap) is not int or cap < 0
                or batch < self.batch or cap < self.token_cap):
            raise ValueError('A formal comparison budget must follow the nondecreasing original prefix')
        limit = sealed({'batch': batch, 'evidence': evidence, 'token_cap': cap}, 'limit_sha256')
        immutable_json(self.root / 'limits' / ('B' + str(batch) + '.json'), limit)
        self.limit, self.batch, self.token_cap = limit, batch, cap

    def _physical(self, identity):
        with self.ledger.transaction() as db:
            row = db.execute('select status,source,purpose,result from calls where id=?', (identity,)).fetchone()
        if row is None or row[0] not in ('completed', 'failed'):
            raise BudgetError('A comparison observation has no settled physical response')
        return row, json.loads(row[3])

    def _records(self):
        values = []
        for path in sorted((self.root / 'observations').glob('*.json')):
            record = json.loads(path.read_text()); verify(record, 'observation_sha256')
            physical, response = self._physical(record['physical_call_id'])
            if (physical[0] != record['status'] or physical[1] != record['source']
                    or physical[2] != 'skill_actor' or digest(response) != record['physical_result_sha256']):
                raise BudgetError('A charged comparison response changed in the continuous ledger')
            values.append(record)
        return values

    def summary(self):
        records = self._records()
        charge = sum(r['usage']['conservatively_charged_input_plus_output_tokens'] for r in records)
        known = sum(r['usage']['known_input_plus_output_tokens'] for r in records)
        return {'batch': self.batch, 'token_cap': self.token_cap,
            'unique_logical_observations': len(records), 'charged_input_plus_output_tokens': charge,
            'logical_observation_token_interval': [known, charge],
            'physical_call_ids': sorted({r['physical_call_id'] for r in records}),
            'old_paid_cache_observations': sum(not r['physical_call_id'].startswith(self.ledger.run_id + ':') for r in records),
            'no_new_independent_trial_claim_from_cache': True,
            'actual_physical_cost_requires_original_ledger': True, 'cash_price_inferred': False}

    def declined_request(self, identity):
        if self.limit is None:
            return None
        path = self.root / 'declines' / (digest([self.limit['limit_sha256'], identity]) + '.json')
        if not path.exists():
            return None
        record = json.loads(path.read_text()); verify(record, 'decline_sha256')
        return record

    def _decline(self, identity, source, wire_hash, reason):
        record = sealed({'call_id': identity, 'source': source, 'wire_sha256': wire_hash,
            'limit_sha256': self.limit['limit_sha256'], 'batch': self.batch,
            'reason': reason, 'no_physical_request_dispatched': True}, 'decline_sha256')
        immutable_json(self.root / 'declines' / (digest([self.limit['limit_sha256'], identity]) + '.json'), record)
        raise ComparisonBudgetExhausted(reason)

    def _store(self, path, *, key, identity, source, wire_hash):
        row, response = self._physical(identity)
        if row[1:3] != (source, 'skill_actor'):
            raise BudgetError('A comparison receipt has the wrong physical source/purpose')
        usage = usage_summary([(identity, row[0], row[3])], context_tokens=self.config['context_tokens'])
        record = sealed({'observation_key': key, 'physical_call_id': identity, 'source': source,
            'purpose': 'skill_actor', 'wire_sha256': wire_hash, 'status': row[0],
            'physical_result_sha256': digest(response), 'usage': usage}, 'observation_sha256')
        immutable_json(path, record)
        return record, response

    def generate(self, identity, **kwargs):
        if (self.limit is None or kwargs['purpose'] != 'skill_actor' or kwargs['thinking'] is not False
                or self.config['enable_thinking'] is not False):
            raise BudgetError('Only the current TRAIN comparison prefix may use this executor')
        self.executor.validate_scope(kwargs['source'], kwargs['purpose'], kwargs['thinking'])
        payload = self.executor.payload(messages=kwargs['messages'], thinking=False, schema=kwargs.get('schema'))
        wire_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()
        key = digest([kwargs['source'], kwargs['purpose'], wire_hash])
        path = self.root / 'observations' / (key + '.json')
        records = self._records()
        previous = next((r for r in records if r['observation_key'] == key), None)
        if previous:
            if previous['status'] != 'completed':
                raise BudgetError('The identical failed physical wire remains charged;no retry')
            _, response = self._physical(previous['physical_call_id'])
            immutable_json(self.root / 'accesses' / (digest(identity) + '.json'), {
                'logical_call_id': identity, 'observation_key': key,
                'physical_call_id': previous['physical_call_id'], 'new_physical_requests': 0})
            return {**response, 'cache_hit': True, 'reused_physical_call_id': previous['physical_call_id']}
        accounted = {r['physical_call_id'] for r in records}
        with self.ledger.transaction() as db:
            pending = db.execute("select id from calls where status='reserved'").fetchall()
            own = db.execute("select id,status from calls where role='executor' and id like ?",
                             (self.ledger.run_id + ':%',)).fetchall()
        if pending:
            raise BudgetError('An actual physical request must settle before another generation')
        unrecorded = {i for i, _ in own if i not in accounted}
        if unrecorded - {identity}:
            raise BudgetError('Settle missing comparison receipts before spending more tokens')
        old = next((status for i, status in own if i == identity), None)
        if old is not None:
            # A crash between physical settlement and receipt creation is
            # recoverable only at the same fully bound physical call identity.
            if old != 'completed':
                raise BudgetError('A previous failed physical request cannot be retried')
            prior = self.ledger.reserve(identity, role='executor', purpose='skill_actor', source=kwargs['source'],
                                        request={'thinking': False, 'payload': payload})
            if prior['dispatch']:
                raise BudgetError('A completed recovery identity unexpectedly requested dispatch')
            response = {**prior['result'], 'cache_hit': True}
            self._store(path, key=key, identity=identity, source=kwargs['source'], wire_hash=wire_hash)
            return response
        reservation = self.executor.tokenize(kwargs['messages'], thinking=False)['count'] + self.config['max_tokens']
        if reservation > self.config['context_tokens']:
            self._decline(identity, kwargs['source'], wire_hash, 'Complete predicate input exceeds frozen context')
        used = sum(r['usage']['conservatively_charged_input_plus_output_tokens'] for r in records)
        if used + reservation > self.token_cap:
            self._decline(identity, kwargs['source'], wire_hash, 'Prefix comparison token budget exhausted before generation')
        try:
            response = self.executor.generate(identity, **kwargs)
        except Exception:
            with self.ledger.transaction() as db:
                row = db.execute('select status from calls where id=?', (identity,)).fetchone()
            if row is not None and row[0] == 'failed':
                self._store(path, key=key, identity=identity, source=kwargs['source'], wire_hash=wire_hash)
            raise
        physical = response.get('reused_physical_call_id', identity)
        self._store(path, key=key, identity=physical, source=kwargs['source'], wire_hash=wire_hash)
        return response
