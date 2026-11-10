"""Current-goal authorization over the existing immutable physical-call history.

Only the atomic transaction/terminal-record operations are shared with the
historical preflight ledger. Its6000/20, source-call and repair-round stops are
not current authorization. Scope, exact cache identity and pending-request
reconciliation remain enforced.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

from .coverage import digest
from .ledger import BudgetError, BudgetLedger


class MethodLedger:
    transaction = BudgetLedger.transaction
    finish = BudgetLedger.finish

    PURPOSES = {
        'method_primitive_observation': ('train', 'executor'),
        'method_train_compile': ('train', 'teacher'),
        'method_train_synthesis': ('train', 'executor'),
        'method_thinking_comparison': ('train', 'executor'),
        'method_dev': ('dev', 'executor'),
        'method_transfer_diagnostic': ('dev', 'executor'),
    }

    def __init__(self, path, *, run_id, binding, sources, authorization_hash, question):
        self.path = Path(path)
        if not self.path.exists():
            raise BudgetError('Continue the existing ledger; do not initialize a replacement')
        if set(sources) != {'train', 'dev'} or set(sources['train']) & set(sources['dev']):
            raise BudgetError('Current runtime requires disjoint fixed TRAIN/DEV allowlists')
        if not run_id or set(binding) != {'code_hash', 'config_hash'} or not all(binding.values()) or not question or not authorization_hash:
            raise BudgetError('A concrete versioned experiment question and authorization are required')
        self.run_id = run_id
        self.execution_binding = dict(binding)
        self.sources = {k: tuple(v) for k,v in sources.items()}
        if any(len(v) != len(set(v)) for v in self.sources.values()):
            raise BudgetError('Duplicate source in the fixed allowlist')
        self.policy = {'run_id': run_id, 'execution_binding': self.execution_binding,
            'sources': self.sources, 'authorization_hash': authorization_hash, 'question': question,
            'physical_call_caps': None, 'repair_round_cap': None,
            'test_authorized': False, 'new_paid_services_authorized': False}
        self.policy = json.loads(json.dumps(self.policy))
        with self.transaction() as db:
            row = db.execute("select value from meta where key='spec'").fetchone()
            if not row:
                raise BudgetError('Missing original ledger origin; no reset permitted')
            self.spec = json.loads(row[0])
            key = 'method_runtime_policy:' + run_id
            prior = db.execute('select value from meta where key=?', (key,)).fetchone()
            if prior and json.loads(prior[0]) != self.policy:
                raise BudgetError('Changed scientific/configuration policy needs an independent run identity')
            if not prior:
                db.execute('insert into meta values (?,?)', (key, json.dumps(self.policy, sort_keys=True)))

    def _source(self, source):
        if source not in set(self.sources['train']) | set(self.sources['dev']):
            raise BudgetError('Source outside fixed TRAIN/DEV scope; TEST remains disabled')

    def reserve(self, call_id, *, role, purpose, source, request):
        if purpose not in self.PURPOSES or self.PURPOSES[purpose][1] != role:
            raise BudgetError('Current purpose/role mismatch')
        partition = self.PURPOSES[purpose][0]
        if source not in self.sources[partition] or not call_id.startswith(self.run_id + ':'):
            raise BudgetError('Request differs from fixed experiment source/partition/namespace')
        request_hash = digest({'request': request, 'origin_spec': self.spec, 'policy': self.policy})
        with self.transaction() as db:
            prior = db.execute('select role,purpose,source,request_hash,status,result from calls where id=?', (call_id,)).fetchone()
            if prior:
                if prior[:4] != (role,purpose,source,request_hash):
                    raise BudgetError('Paid request identity changed')
                if prior[4] != 'completed':
                    raise BudgetError('Reserved/failed requests stay charged; reconcile or record an explicit new attempt')
                return {'dispatch': False, 'result': json.loads(prior[5])}
            if db.execute("select 1 from calls where status='reserved'").fetchone():
                raise BudgetError('Reconcile the existing physical request before dispatch')
            db.execute('insert into calls values (?,?,?,?,?,?,?,?,NULL)',
                (call_id, role, purpose, 'method_' + partition, source, request_hash, 'reserved', time.time()))
        return {'dispatch': True, 'request_hash': request_hash}

    def reserve_oracle(self, source, view_hash):
        if source not in self.sources['train'] or source.startswith('ContractNLI:'):
            raise BudgetError('No DEV/TEST feedback or invented ContractNLI counterfactual oracle')
        with self.transaction() as db:
            if db.execute('select 1 from oracle_views where source=? and view_hash=?', (source, view_hash)).fetchone():
                raise BudgetError('Already charged view: reuse its compatible saved label')
            db.execute('insert into oracle_views values (?,?,?)', (source, view_hash, time.time()))

    def export(self):
        with self.transaction() as db:
            rows = db.execute('select * from calls order by reserved_at,id').fetchall()
            views = db.execute('select * from oracle_views order by source,reserved_at').fetchall()
        names = ('id','role','purpose','bucket','source','request_hash','status','reserved_at','result')
        calls = [dict(zip(names,row)) for row in rows]
        for row in calls:
            row['result'] = json.loads(row['result']) if row['result'] else None
        return {'historical_spec': self.spec, 'active_policy': self.policy,
            'calls': calls, 'oracle_views': views,
            'executor_used': sum(row[1]=='executor' for row in rows),
            'teacher_used': sum(row[1]=='teacher' for row in rows)}
