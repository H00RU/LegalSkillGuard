"""Current frozen-model study over the preserved physical request history."""
from pathlib import Path
import json
import time

from legal_skill_guard.rr.ledger import BudgetLedger, BudgetError
from .objects import digest


class EvolutionLedger:
    transaction = BudgetLedger.transaction
    finish = BudgetLedger.finish
    PURPOSES = {'skill_actor': ('train', 'executor'), 'skill_replay': ('train', 'executor'),
        'skill_teacher': ('train', 'teacher'), 'skill_dev': ('dev', 'executor'),
        'skill_test': ('test', 'executor')}

    def __init__(self, path, *, run_id, sources, binding, freeze=None):
        self.path = Path(path)
        if not self.path.exists():
            raise BudgetError('Continue the existing physical ledger; never initialize a replacement')
        if set(sources) != {'train', 'dev', 'test'}:
            raise BudgetError('Explicit native partitions required')
        self.sources = {p: tuple(v) for p, v in sources.items()}
        if len(set(sum((list(v) for v in self.sources.values()), []))) != sum(map(len, self.sources.values())):
            raise BudgetError('Parent-source partitions overlap or contain duplicates')
        self.run_id = run_id
        self.freeze = freeze
        self.policy = json.loads(json.dumps({'protocol': 'LSG-LegalSkill-20261111', 'run_id': run_id,
            'sources': self.sources, 'execution_binding': binding, 'freeze': freeze,
            'weight_updates': False, 'teacher_test_access': False,
            'physical_call_caps': None, 'repair_round_cap': None}))
        with self.transaction() as db:
            origin = db.execute("select value from meta where key='spec'").fetchone()
            if not origin:
                raise BudgetError('Original ledger provenance is missing')
            self.spec = json.loads(origin[0])
            key = 'external_legal_skill_policy:' + run_id
            old = db.execute('select value from meta where key=?', (key,)).fetchone()
            if old and json.loads(old[0]) != self.policy:
                raise BudgetError('Changed experiment binding needs an explicit new run identity')
            if not old:
                db.execute('insert into meta values (?,?)', (key, json.dumps(self.policy, sort_keys=True)))

    def _source(self, source):
        if not any(source in values for values in self.sources.values()):
            raise BudgetError('Source outside the fixed study manifest')

    def require_train(self, source_ids):
        if self.freeze is not None:
            raise BudgetError('Frozen evaluation cannot call the teacher or update TRAIN skills')
        if not source_ids or len(set(source_ids)) != len(source_ids) or not set(source_ids) <= set(self.sources['train']):
            raise BudgetError('Teacher input and candidate selection use only fixed TRAIN parents')

    def permit(self, source, purpose, role):
        if self.freeze is not None and role == 'teacher':
            raise BudgetError('Teacher dispatch is disabled for frozen evaluation')
        if purpose not in self.PURPOSES:
            raise BudgetError('Unknown external-study request purpose')
        partition, expected_role = self.PURPOSES[purpose]
        if role != expected_role or source not in self.sources[partition]:
            raise BudgetError('Physical request differs from its role/partition authorization')
        if partition == 'test' and (not self.freeze or self.freeze.get('batch') != 8
                                  or not self.freeze.get('artifact_sha256')):
            raise BudgetError('TEST requires the locked B8 study freeze receipt')

    def reserve(self, call_id, *, role, purpose, source, request):
        self.permit(source, purpose, role)
        if not call_id.startswith(self.run_id + ':'):
            raise BudgetError('Request namespace differs from this bound run')
        if role == 'executor' and request.get('thinking') is not False:
            raise BudgetError('Qwen thinking must remain OFF')
        h = digest({'request': request, 'origin_spec': self.spec, 'policy': self.policy})
        with self.transaction() as db:
            old = db.execute('select role,purpose,source,request_hash,status,result from calls where id=?', (call_id,)).fetchone()
            if old:
                if old[:4] != (role, purpose, source, h):
                    raise BudgetError('Existing physical request identity changed')
                if old[4] != 'completed':
                    raise BudgetError('Failed/reserved requests remain charged; no implicit retry')
                return {'dispatch': False, 'result': json.loads(old[5])}
            if db.execute("select 1 from calls where status='reserved'").fetchone():
                raise BudgetError('Reconcile the real pending request before another dispatch')
            db.execute('insert into calls values (?,?,?,?,?,?,?,?,NULL)',
                       (call_id, role, purpose, 'external_skill_' + self.PURPOSES[purpose][0],
                        source, h, 'reserved', time.time()))
        return {'dispatch': True, 'request_hash': h}
