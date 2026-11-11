"""Durable original6000/20 study ledger with append-only preflight authorization.

Reservations commit before network dispatch. Ambiguous/crashed calls stay charged
and require explicit reconciliation; resuming never silently dispatches twice.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .coverage import digest

DATASETS = ("OpenExempt", "RuleArena_Airline", "SARA_v2_Binary",
            "ProofWriter_OWA_depth5", "ContractNLI")
BUCKETS = {"full_build_including_pilot": 256, "thinking_comparison": 40,
           "dev_six_arms": 864, "frozen_test_six_arms": 3456, "B1_test_M11": 576,
           "diagnostics": 384, "native_empty": 192, "shared_retries_and_recovery": 232}
PURPOSES = {"thinking_probe": "thinking_comparison", "pilot_ingestion": "full_build_including_pilot",
            "preflight_bug_retry": "shared_retries_and_recovery", "pilot_teacher_summary": "teacher"}


class BudgetError(RuntimeError):
    pass


class BudgetLedger:
    def __init__(self, path: Path, *, sources: dict[str, list[str]], code_hash: str,
                 config_hash: str):
        self.path = Path(path)
        if set(sources) != set(DATASETS) or any(len(v) != 4 for v in sources.values()):
            raise BudgetError("Preflight requires exactly four locked sources per benchmark")
        flat = [s for values in sources.values() for s in values]
        if len(set(flat)) != 20 or any(not s for s in flat):
            raise BudgetError("Source identities must be unique and nonempty")
        if not code_hash or not config_hash:
            raise BudgetError("Code and configuration must be bound before generation")
        self.spec = {"sources": sources, "code_hash": code_hash, "config_hash": config_hash,
                     "protocol": "LSG-RR-v2", "original_executor_cap": 6000,
                     "original_teacher_cap": 20, "preflight_executor_cap": 100,
                     "preflight_teacher_cap": 2}
        self.execution_binding = {"code_hash": code_hash, "config_hash": config_hash}
        self.is_bugfix_revision = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS calls (
                id TEXT PRIMARY KEY, role TEXT NOT NULL, purpose TEXT NOT NULL,
                bucket TEXT NOT NULL, source TEXT NOT NULL, request_hash TEXT NOT NULL,
                status TEXT NOT NULL, reserved_at REAL NOT NULL, result TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS oracle_views (
                source TEXT NOT NULL, view_hash TEXT NOT NULL, reserved_at REAL NOT NULL,
                PRIMARY KEY(source, view_hash))""")
            existing = db.execute("SELECT value FROM meta WHERE key='spec'").fetchone()
            if existing and json.loads(existing[0]) != self.spec:
                origin = json.loads(existing[0])
                revisions = db.execute("SELECT value FROM meta WHERE key IN ('model_rerun','bugfix','processing_continuation','strict_schema_round2') OR key LIKE 'repair_revision:%' OR key LIKE 'study_revision:%'").fetchall()
                comparable = {k: v for k, v in self.spec.items() if k not in self.execution_binding}
                original_comparable = {k: v for k, v in origin.items() if k not in self.execution_binding}
                if comparable != original_comparable or not any(
                        json.loads(row[0]).get("new_binding") == self.execution_binding for row in revisions):
                    raise BudgetError("Ledger binding differs; retain old charged records, do not reset")
                self.spec = origin
                self.is_bugfix_revision = True
            db.execute("INSERT OR IGNORE INTO meta VALUES ('spec', ?)", (json.dumps(self.spec),))

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def _source(self, source: str) -> None:
        if source not in {s for v in self.spec["sources"].values() for s in v}:
            raise BudgetError("Source outside locked training preflight allowlist")

    def start_bugfix_round(self, *, reason: str, affected_sources: list[str],
                           new_code_hash: str | None = None, new_config_hash: str | None = None) -> None:
        if not reason or not affected_sources:
            raise BudgetError("A concrete implementation error and affected sources are required")
        for source in affected_sources:
            self._source(source)
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM meta WHERE key='bugfix'").fetchone():
                raise BudgetError("Only one targeted live bugfix round")
            db.execute("INSERT INTO meta VALUES ('bugfix', ?)",
                       (json.dumps({"reason": reason, "sources": affected_sources,
                                    "new_binding": {"code_hash": new_code_hash or self.spec["code_hash"],
                                                    "config_hash": new_config_hash or self.spec["config_hash"]}}),))

    def reserve(self, call_id: str, *, role: str, purpose: str, source: str,
                request: dict) -> dict:
        self._source(source)
        if purpose not in PURPOSES or role not in {"executor", "teacher"}:
            raise BudgetError("Preflight purpose/role forbidden; formal run stays disabled")
        if (role == "teacher") != (purpose == "pilot_teacher_summary"):
            raise BudgetError("Teacher purpose/role mismatch")
        request_hash = digest({"request": request, "spec": self.spec,
                               "execution_binding": self.execution_binding})
        with self.transaction() as db:
            active = db.execute("SELECT value FROM meta WHERE key='study_preflight_authorization'").fetchone()
            if active:
                off = db.execute("select 1 from meta where key='executor_thinking_off_authorization'").fetchone()
                if off and role == 'executor' and request.get('thinking') is not False:
                    raise BudgetError('Explicit user policy forbids new thinking-ON generation')
                prior = db.execute('SELECT role,purpose,source,request_hash,status,result FROM calls WHERE id=?', (call_id,)).fetchone()
                if prior:
                    if prior[:4] != (role, purpose, source, request_hash):
                        raise BudgetError('Call ID binding changed')
                    if prior[4] != 'completed':
                        raise BudgetError('Previously reserved/failed call stays charged; no implicit redispatch')
                    return {'dispatch': False, 'result': json.loads(prior[5])}
                plan = db.execute('SELECT value FROM meta WHERE key=?', ('study_request:' + call_id,)).fetchone()
                plan = json.loads(plan[0]) if plan else None
                if not plan or plan['new_binding'] != self.execution_binding or plan['source'] != source or \
                        plan['role'] != role or plan['request_digest'] != digest(request) or \
                        purpose != ('preflight_bug_retry' if role == 'executor' else 'pilot_teacher_summary'):
                    raise BudgetError('Only exact offline-verified fixed-source study preflight requests are authorized')
                if db.execute("SELECT 1 FROM calls WHERE status='reserved'").fetchone():
                    raise BudgetError('Reconcile the running request before another physical dispatch')
                total = db.execute('SELECT count(*) FROM calls WHERE role=?', (role,)).fetchone()[0]
                bucket = PURPOSES[purpose]
                used = db.execute('SELECT count(*) FROM calls WHERE bucket=?', (bucket,)).fetchone()[0]
                if total >= (6000 if role == 'executor' else 20) or used >= BUCKETS.get(bucket, 20):
                    raise BudgetError('Original study role or bucket allocation exhausted')
                db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,NULL)',
                    (call_id, role, purpose, bucket, source, request_hash, 'reserved', time.time()))
                return {'dispatch': True, 'request_hash': request_hash}
            row = db.execute("SELECT value FROM meta WHERE key='cumulative_repair_policy'").fetchone()
            cumulative = json.loads(row[0]) if row else None
            row = db.execute("SELECT value FROM meta WHERE key='model_rerun'").fetchone()
            model_fix = json.loads(row[0]) if row else None
            row = db.execute("SELECT value FROM meta WHERE key='strict_schema_round2'").fetchone()
            second = json.loads(row[0]) if row else None
            second_active = second is not None and second["new_binding"] == self.execution_binding
            if second_active:
                planned = second["calls"].get(call_id)
                if role != "executor" or purpose != "preflight_bug_retry" or not planned or \
                        planned["source"] != source or request.get("thinking") is not True or \
                        digest(request.get("payload")) != planned["payload_hash"]:
                    raise BudgetError("Request outside explicitly authorized schema-only second round")
            if self.is_bugfix_revision and purpose != "preflight_bug_retry":
                if not model_fix or purpose not in {"pilot_ingestion", "pilot_teacher_summary"}:
                    raise BudgetError("A repair revision cannot start a fresh sweep")
                completed = db.execute("SELECT COUNT(*) FROM calls WHERE purpose='preflight_bug_retry' AND status='completed'").fetchone()[0]
                if completed != len(model_fix["calls"]):
                    raise BudgetError("Finish the registered repair before the original same-source pilot")
            prior = db.execute("SELECT role,purpose,source,request_hash,status,result FROM calls WHERE id=?",
                               (call_id,)).fetchone()
            if prior:
                if prior[:4] != (role, purpose, source, request_hash):
                    raise BudgetError("Call ID binding changed")
                if prior[4] == "completed":
                    return {"dispatch": False, "result": json.loads(prior[5])}
                raise BudgetError("Previously reserved/failed call stays charged; no implicit redispatch")
            if cumulative:
                row = db.execute("SELECT value FROM meta WHERE key=?", ('repair_request:' + call_id,)).fetchone()
                plan = json.loads(row[0]) if row else None
                if role != 'executor' or purpose != 'preflight_bug_retry' or not plan or \
                        plan['source'] != source or plan['new_binding'] != self.execution_binding or \
                        request.get('thinking') is not True or digest(request.get('payload')) != plan['payload_hash']:
                    raise BudgetError('Only exact registered cumulative repair/preflight requests are authorized')
                if db.execute("SELECT 1 FROM calls WHERE status='reserved'").fetchone():
                    raise BudgetError('Reconcile the existing physical request before another dispatch')
                counts = dict(db.execute('SELECT role,count(*) FROM calls GROUP BY role').fetchall())
                if counts.get('executor', 0) >= min(96, cumulative['executor_cumulative_max'], 100) or \
                        counts.get('teacher', 0) != cumulative['teacher_baseline']:
                    raise BudgetError('Cumulative96 cap or unchanged teacher2 contract reached')
            if second_active:
                state = json.loads(db.execute("SELECT value FROM meta WHERE key='strict_schema_round2_state'").fetchone()[0])
                used_second = db.execute("SELECT COUNT(*) FROM calls WHERE id IN (" + ",".join("?" for _ in second["order"]) + ")", second["order"]).fetchone()[0]
                executor_used = db.execute("SELECT COUNT(*) FROM calls WHERE role='executor'").fetchone()[0]
                teacher_used = db.execute("SELECT COUNT(*) FROM calls WHERE role='teacher'").fetchone()[0]
                if state["phase"] in {"stopped", "complete"} or state["inflight"] is not None:
                    raise BudgetError("Second-round gate stopped, completed or needs saved-response reconciliation")
                if used_second >= 12 or executor_used >= min(96, second["executor_total_max"]) or teacher_used != second["teacher_baseline"]:
                    raise BudgetError("Second-round physical-call or unchanged-teacher allowance exhausted")
                if second["order"][state["next_index"]] != call_id:
                    raise BudgetError("Second-round precommitted order changed")
                if state["next_index"] >= 2 and not state["gate_passed"]:
                    raise BudgetError("Two-request typed/execution/semantic gate has not passed")
            count = db.execute("SELECT COUNT(*) FROM calls WHERE role=?", (role,)).fetchone()[0]
            # All current calls belong to the original study ledger. Future
            # formal runner must use these same rows, never initialize a new bill.
            if count >= (100 if role == "executor" else 2):
                raise BudgetError("Preflight hard request cap exhausted")
            bucket = PURPOSES[purpose]
            used = db.execute("SELECT COUNT(*) FROM calls WHERE bucket=?", (bucket,)).fetchone()[0]
            limit = {"thinking_comparison": 40, "full_build_including_pilot": 40,
                     "shared_retries_and_recovery": 20, "teacher": 2}[bucket]
            if used >= min(limit, BUCKETS.get(bucket, 20)):
                raise BudgetError("Current allocation exhausted within original global bucket")
            if purpose == "thinking_probe":
                profile = request.get("thinking")
                if type(profile) is not bool:
                    raise BudgetError("Probe must bind actual thinking profile")
                key = f"probe:{source}:{profile}"
                if db.execute("SELECT 1 FROM meta WHERE key=?", (key,)).fetchone():
                    raise BudgetError("No repeated probe sweep for the same source/profile")
                db.execute("INSERT INTO meta VALUES (?, ?)", (key, call_id))
            if purpose == "pilot_ingestion":
                n = db.execute("SELECT COUNT(*) FROM calls WHERE source=? AND purpose=?",
                               (source, purpose)).fetchone()[0]
                if n >= 2:
                    raise BudgetError("Training has at most two joint A/B calls, no third fallback")
            if purpose == "preflight_bug_retry":
                fix = db.execute("SELECT value FROM meta WHERE key='bugfix'").fetchone()
                if cumulative:
                    pass
                elif second_active:
                    pass  # exact source, payload, phase and physical caps checked above
                elif model_fix:
                    if model_fix["calls"].get(call_id) != {"source": source, "thinking": request.get("thinking")}:
                        raise BudgetError("Request outside the one registered source/profile repair")
                elif not fix or source not in json.loads(fix[0])["sources"]:
                    raise BudgetError("Retry source is not in the one recorded bugfix round")
            db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,NULL)",
                       (call_id, role, purpose, bucket, source, request_hash, "reserved", time.time()))
            if second_active:
                state["inflight"] = call_id
                db.execute("UPDATE meta SET value=? WHERE key='strict_schema_round2_state'", (json.dumps(state),))
        return {"dispatch": True, "request_hash": request_hash}

    def register_study_authorization(self, authorization):
        if authorization.get('authority') != 'explicit_user_chat_authorization' or \
                authorization.get('executor_original_study_max') != 6000 or \
                authorization.get('teacher_original_study_max') != 20 or \
                authorization.get('preflight_executor_cap_removed') is not True or \
                authorization.get('preflight_teacher_cap_removed') is not True or \
                authorization.get('main_training_enabled') is not False or \
                authorization.get('no_new_sources') is not True:
            raise BudgetError('Explicit original-budget preflight authorization required')
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM calls WHERE status='reserved'").fetchone():
                raise BudgetError('Existing physical request needs reconciliation')
            key = 'study_preflight_authorization'
            old = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            if old and json.loads(old[0]) != authorization:
                raise BudgetError('Authorization receipt is immutable')
            db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', (key, json.dumps(authorization)))

    def register_study_revision(self, revision, *, new_binding, change, offline_evidence_hash):
        if not revision or not change or not offline_evidence_hash or set(new_binding) != {'code_hash', 'config_hash'}:
            raise BudgetError('Concrete change and current offline evidence required')
        # Runtime/generation parameters remain fixed. Source schema and common-path code may change.
        if new_binding['config_hash'] != self.spec['config_hash']:
            with self.transaction() as db:
                row = db.execute("SELECT value FROM meta WHERE key='executor_thinking_off_authorization'").fetchone()
            override = json.loads(row[0]) if row else None
            if not override or override['new_config_hash'] != new_binding['config_hash']:
                raise BudgetError('Configuration changed without the explicit thinking-OFF authorization')
        record = dict(new_binding=new_binding, change=change, offline_evidence_hash=offline_evidence_hash)
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM meta WHERE key='study_preflight_authorization'").fetchone() or \
                    db.execute("SELECT 1 FROM calls WHERE status='reserved'").fetchone():
                raise BudgetError('Authorization and terminal ledger required')
            key = 'study_revision:' + revision
            old = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            if old and json.loads(old[0]) != record:
                raise BudgetError('Revision evidence is immutable')
            db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', (key, json.dumps(record)))

    def register_thinking_off_authorization(self, authorization):
        """One explicit profile change; all original rows and other settings stay fixed."""
        from copy import deepcopy
        old = authorization['old_semantic_config']
        new = authorization['new_semantic_config']
        expected = deepcopy(old)
        expected['executor']['enable_thinking'] = False
        if authorization.get('authority') != 'explicit_user_chat_authorization' or \
                authorization.get('executor_enable_thinking') is not False or \
                digest(old) != self.spec['config_hash'] or new != expected or \
                digest(new) != authorization['new_config_hash']:
            raise BudgetError('Only the explicitly authorized thinking-OFF change is allowed')
        with self.transaction() as db:
            key = 'executor_thinking_off_authorization'
            prior = db.execute('select value from meta where key=?', (key,)).fetchone()
            if prior:
                if json.loads(prior[0]) != authorization:
                    raise BudgetError('Thinking override receipt is immutable')
                return
            if db.execute("select 1 from calls where status='reserved'").fetchone():
                raise BudgetError('Reconcile the existing request before changing profiles')
            counts = dict(db.execute('select role,count(*) from calls group by role'))
            if any(counts.get(role, 0) != authorization['baseline_counts'].get(role, 0) for role in ['executor','teacher']):
                raise BudgetError('Thinking override baseline differs from persistent accounting')
            db.execute('insert into meta values (?,?)', (key, json.dumps(authorization)))

    def register_study_request(self, call_id, *, revision, source, request, role='executor', step=0):
        self._source(source)
        if role not in {'executor', 'teacher'} or step not in (0, 1):
            raise BudgetError('Invalid fixed preflight request')
        with self.transaction() as db:
            off = db.execute("select 1 from meta where key='executor_thinking_off_authorization'").fetchone()
            if off and role == 'executor' and request.get('thinking') is not False:
                raise BudgetError('New executor requests must use the explicit thinking-OFF profile')
            row = db.execute('SELECT value FROM meta WHERE key=?', ('study_revision:' + revision,)).fetchone()
            if not row:
                raise BudgetError('Register offline-verified revision first')
            revision_record = json.loads(row[0])
            record = dict(new_binding=revision_record['new_binding'], source=source, role=role,
                          step=step, revision=revision, request_digest=digest(request))
            key = 'study_request:' + call_id
            old = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            if old:
                if json.loads(old[0]) != record:
                    raise BudgetError('Planned request is immutable')
                return
            plans = [json.loads(r[0]) for r in db.execute("SELECT value FROM meta WHERE key LIKE 'study_request:%'")]
            if any(p['request_digest'] == record['request_digest'] for p in plans):
                raise BudgetError('Unchanged request must not be repeated')
            if any(p['new_binding'] == record['new_binding'] and p['source'] == source and
                   p['role'] == role and p['step'] == step for p in plans):
                raise BudgetError('Failed sample retry requires code/config change and new offline evidence')
            if role == 'teacher':
                if step != 0 or len(request.get('source_ids', [])) != 16:
                    raise BudgetError('Teacher only summarizes the original first16 batch')
                for sid in request['source_ids']:
                    self._source(sid)
            elif not off and request.get('thinking') is not True:
                raise BudgetError('Preserve selected thinking profile unless explicitly overridden')
            db.execute('INSERT INTO meta VALUES (?,?)', (key, json.dumps(record)))

    def register_cumulative_policy(self, authorization):
        if authorization.get('authority') != 'explicit_user_chat_authorization' or \
                authorization.get('executor_baseline') != 85 or authorization.get('executor_cumulative_max') != 96 or \
                authorization.get('executor_global_hard_max') != 100 or authorization.get('teacher_calls_added') != 0 or \
                authorization.get('repair_round_limit', 'missing') is not None or \
                authorization.get('first_type_failure_stops_session') is not False:
            raise BudgetError('Explicit cumulative96 policy override is required')
        record = {'authorization_hash': digest(authorization), 'executor_cumulative_max': 96,
                  'executor_baseline': 85, 'teacher_baseline': 2, 'sources': self.spec['sources']}
        with self.transaction() as db:
            prior = db.execute("SELECT value FROM meta WHERE key='cumulative_repair_policy'").fetchone()
            if prior:
                if json.loads(prior[0]) != record:
                    raise BudgetError('Cumulative authorization cannot be reset or expanded')
                return record
            counts = dict(db.execute('SELECT role,count(*) FROM calls GROUP BY role').fetchall())
            if counts != {'executor': 85, 'teacher': 2} or db.execute("SELECT 1 FROM calls WHERE status='reserved'").fetchone():
                raise BudgetError('Preserve terminal85/2 ledger before cumulative continuation')
            db.execute("INSERT INTO meta VALUES ('cumulative_repair_policy',?)", (json.dumps(record),))
        return record

    def register_repair_revision(self, revision, *, new_binding, change, offline_evidence_hash):
        if not revision or not change or not offline_evidence_hash or set(new_binding) != {'code_hash', 'config_hash'} or \
                new_binding['config_hash'] != self.spec['config_hash']:
            raise BudgetError('Concrete change and offline evidence required; generation parameters stay fixed')
        record = {'new_binding': new_binding, 'change': change, 'offline_evidence_hash': offline_evidence_hash}
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM meta WHERE key='cumulative_repair_policy'").fetchone() or \
                    db.execute("SELECT 1 FROM calls WHERE status='reserved'").fetchone():
                raise BudgetError('Policy and terminal clients required before revision')
            key = 'repair_revision:' + revision
            prior = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            if prior and json.loads(prior[0]) != record:
                raise BudgetError('Repair revision is immutable')
            db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', (key, json.dumps(record)))
        return record

    def register_repair_request(self, call_id, *, revision, source, payload_hash, mode='validation'):
        self._source(source)
        if mode not in {'validation', 'continuation'} or not payload_hash:
            raise BudgetError('Invalid repair request mode')
        with self.transaction() as db:
            row = db.execute('SELECT value FROM meta WHERE key=?', ('repair_revision:' + revision,)).fetchone()
            if not row:
                raise BudgetError('Offline-verified code revision must be registered first')
            new_binding = json.loads(row[0])['new_binding']
            record = {'new_binding': new_binding, 'revision': revision, 'source': source,
                      'payload_hash': payload_hash, 'mode': mode}
            prior = db.execute('SELECT value FROM meta WHERE key=?', ('repair_request:' + call_id,)).fetchone()
            if prior:
                if json.loads(prior[0]) != record:
                    raise BudgetError('Registered request is immutable')
                return record
            plans = [json.loads(r[0]) for r in db.execute("SELECT value FROM meta WHERE key LIKE 'repair_request:%'")]
            if any(p['source'] == source and p['new_binding'] == new_binding for p in plans):
                raise BudgetError('Same failed sample retry requires a different code/config revision and offline evidence')
            if mode == 'continuation' and not any(json.loads(r[0]).get('pass') for r in
                    db.execute("SELECT value FROM meta WHERE key LIKE 'repair_outcome:%'")):
                raise BudgetError('Validate the repaired contract before normal preflight continuation')
            if db.execute("SELECT 1 FROM calls WHERE status='reserved'").fetchone():
                raise BudgetError('Existing request needs reconciliation')
            db.execute('INSERT INTO meta VALUES (?,?)', ('repair_request:' + call_id, json.dumps(record)))
        return record

    def record_repair_outcome(self, call_id, outcome):
        if outcome.get('pass') and not (outcome.get('typed_schema_pass') and outcome.get('model_IR_executed') and
                outcome.get('source_grounding', {}).get('pass') and outcome.get('program_native_score', {}).get('task_correct')):
            raise BudgetError('Passing requires typed/executed/grounded program and original TRAIN semantics')
        with self.transaction() as db:
            row = db.execute('SELECT status FROM calls WHERE id=?', (call_id,)).fetchone()
            if not row or row[0] not in {'completed', 'failed'}:
                raise BudgetError('Only terminal physical requests can be validated')
            key = 'repair_outcome:' + call_id
            prior = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            if prior and json.loads(prior[0]) != outcome:
                raise BudgetError('Saved validation is immutable')
            db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', (key, json.dumps(outcome)))
        return outcome

    def register_strict_schema_round2(self, *, new_binding: dict, authorization: dict,
                                      calls: dict, order: list[str], forensic_hash: str) -> dict:
        """Append the user's explicit second round, preserving every original row."""
        if set(new_binding) != {"code_hash", "config_hash"} or new_binding["config_hash"] != self.spec["config_hash"] or \
                authorization.get("authority") != "explicit_user_chat_authorization" or \
                authorization.get("allowed_repair_rounds") != 2 or \
                authorization.get("max_new_physical_executor_requests") != 12 or \
                authorization.get("initial_gate_max_requests") != 2 or \
                authorization.get("teacher_calls_added") != 0 or not forensic_hash:
            raise BudgetError("Missing bounded explicit second-round authorization or forensic evidence")
        if len(order) != 12 or set(order) != set(calls) or len({c["source"] for c in calls.values()}) != 12:
            raise BudgetError("Exactly twelve distinct precommitted affected TRAIN sources required")
        for call_id, item in calls.items():
            self._source(item["source"])
            if call_id != f"strict_contract_fix:{item['source']}:True" or not item.get("payload_hash"):
                raise BudgetError("Invalid second-round request identity")
        counts = {d: sum(v["source"].startswith(d + ":") for v in calls.values()) for d in DATASETS}
        if counts != {d: (4 if d in {"OpenExempt", "RuleArena_Airline", "SARA_v2_Binary"} else 0) for d in DATASETS}:
            raise BudgetError("Second round cannot add or replace dataset sources")
        record = {"new_binding": new_binding, "authorization_hash": digest(authorization),
                  "calls": calls, "order": order, "forensic_hash": forensic_hash,
                  "executor_baseline": 84, "executor_total_max": 96, "teacher_baseline": 2,
                  "physical_requests_max": 12, "initial_gate_max": 2}
        with self.transaction() as db:
            prior = db.execute("SELECT value FROM meta WHERE key='strict_schema_round2'").fetchone()
            if prior:
                if json.loads(prior[0]) != record:
                    raise BudgetError("Existing second round is immutable; no third round or changed plan")
                return record
            rows = db.execute("SELECT role,status FROM calls").fetchall()
            if sum(r[0] == "executor" for r in rows) != 84 or sum(r[0] == "teacher" for r in rows) != 2 or \
                    any(r[1] not in {"completed", "failed"} for r in rows) or \
                    not db.execute("SELECT 1 FROM meta WHERE key='model_rerun'").fetchone():
                raise BudgetError("Preserve terminal84/2 ledger and original first repair before registration")
            db.execute("INSERT INTO meta VALUES ('strict_schema_round2', ?)", (json.dumps(record),))
            db.execute("INSERT INTO meta VALUES ('strict_schema_round2_state', ?)", (json.dumps({
                "phase": "gate", "next_index": 0, "inflight": None, "gate_passed": False,
                "outcomes": {}, "stop_reason": None}),))
        return record

    def record_strict_schema_validation(self, call_id: str, outcome: dict) -> dict:
        """Save a gate decision after execution; a failure never releases quota."""
        with self.transaction() as db:
            plan = json.loads(db.execute("SELECT value FROM meta WHERE key='strict_schema_round2'").fetchone()[0])
            state = json.loads(db.execute("SELECT value FROM meta WHERE key='strict_schema_round2_state'").fetchone()[0])
            if call_id in state["outcomes"]:
                if state["outcomes"][call_id] != outcome:
                    raise BudgetError("Saved validation decision differs")
                return state
            status = db.execute("SELECT status FROM calls WHERE id=?", (call_id,)).fetchone()
            if state["inflight"] != call_id or status is None or status[0] not in {"completed", "failed"}:
                raise BudgetError("Reconcile the exact charged response before a new dispatch")
            if type(outcome.get("pass")) is not bool or type(outcome.get("systemic_failure")) is not bool:
                raise BudgetError("Explicit typed/execution/semantic validation decision required")
            if outcome["pass"] and (status[0] != "completed" or not outcome.get("typed_schema_pass") or
                    not outcome.get("model_IR_executed") or not outcome.get("source_grounding", {}).get("pass") or
                    not outcome.get("program_native_score", {}).get("task_correct")):
                raise BudgetError("A gate success needs typed, executed and corresponding semantic evidence")
            if status[0] == "failed" and not outcome["systemic_failure"]:
                raise BudgetError("Charged transport failures must stop the round")
            index = state["next_index"]
            state["outcomes"][call_id] = outcome
            state["inflight"] = None
            state["next_index"] += 1
            if outcome["systemic_failure"] or index < 2 and not outcome["pass"]:
                state["phase"] = "stopped"
                state["stop_reason"] = outcome.get("reason", "initial_gate_not_validated")
            elif state["next_index"] == 2:
                state["gate_passed"] = True
                state["phase"] = "continue"
            elif state["next_index"] == len(plan["order"]):
                state["phase"] = "complete"
            db.execute("UPDATE meta SET value=? WHERE key='strict_schema_round2_state'", (json.dumps(state),))
            return state

    def start_model_rerun_round(self, *, reason: str, new_binding: dict) -> dict:
        """The single actual rerun: exactly the eight faulty OE wire profiles.

        A prior deterministic parser fix may exist; it generated no extra model
        responses. All earlier reservations remain charged in their old rows.
        """
        if not reason or set(new_binding) != {"code_hash", "config_hash"} or \
                new_binding["config_hash"] != self.spec["config_hash"]:
            raise BudgetError("Repair must preserve the generation configuration")
        plan = {f"native_contract_fix:{source}:{thinking}": {"source": source, "thinking": thinking}
                for source in self.spec["sources"]["OpenExempt"] for thinking in (True, False)}
        result = {"reason": reason, "new_binding": new_binding, "calls": plan,
                  "extra_sources_or_profiles": False, "max_actual_rerun_rounds": 1}
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM meta WHERE key='model_rerun'").fetchone() or \
                    db.execute("SELECT 1 FROM calls WHERE purpose='preflight_bug_retry'").fetchone():
                raise BudgetError("Only one actual model rerun round")
            if db.execute("SELECT COUNT(*) FROM calls").fetchone()[0] != 40 or \
                    db.execute("SELECT COUNT(*) FROM calls WHERE purpose='thinking_probe' AND status='completed'").fetchone()[0] != 40:
                raise BudgetError("The original fixed forty calls must be terminal before repair")
            db.execute("INSERT INTO meta VALUES ('model_rerun', ?)", (json.dumps(result),))
        return result

    def register_processing_continuation(self, *, new_binding: dict, generation_binding: dict) -> None:
        """Bind an offline oracle-only repair without authorizing model reruns."""
        if set(new_binding) != {"code_hash", "config_hash"} or generation_binding != self.execution_binding:
            raise BudgetError("Processing continuation must preserve its verified generation binding")
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM calls WHERE status!='completed'").fetchone():
                raise BudgetError("Stop and preserve all model calls before processing repair")
            if db.execute("SELECT 1 FROM meta WHERE key='processing_continuation'").fetchone():
                raise BudgetError("Processing continuation already registered; preserve its history")
            db.execute("INSERT INTO meta VALUES ('processing_continuation', ?)", (json.dumps({
                "new_binding": new_binding, "generation_binding": generation_binding,
                "additional_model_rerun_authorization": False}),))

    def finish(self, call_id: str, *, status: str, result: dict[str, Any]) -> None:
        if status not in {"completed", "failed"}:
            raise BudgetError("Invalid terminal request status")
        with self.transaction() as db:
            prior = db.execute("SELECT status FROM calls WHERE id=?", (call_id,)).fetchone()
            if not prior or prior[0] != "reserved":
                raise BudgetError("Terminal records are immutable")
            db.execute("UPDATE calls SET status=?,result=? WHERE id=?",
                       (status, json.dumps(result, allow_nan=False), call_id))

    def reserve_oracle(self, source: str, view_hash: str) -> None:
        self._source(source)
        if source in self.spec["sources"]["ContractNLI"]:
            raise BudgetError("ContractNLI has no automatic counterfactual gold oracle")
        with self.transaction() as db:
            count = db.execute("SELECT COUNT(*) FROM oracle_views WHERE source=?", (source,)).fetchone()[0]
            if count >= 4:
                raise BudgetError("Combined source oracle budget exhausted")
            try:
                db.execute("INSERT INTO oracle_views VALUES (?,?,?)", (source, view_hash, time.time()))
            except sqlite3.IntegrityError as exc:
                raise BudgetError("Already queried view: reuse recorded label, do not redispatch") from exc

    def export(self) -> dict:
        with self.transaction() as db:
            rows = db.execute("SELECT id,role,purpose,bucket,source,request_hash,status,reserved_at,result "
                              "FROM calls ORDER BY reserved_at,id").fetchall()
            oracle = db.execute("SELECT source,view_hash,reserved_at FROM oracle_views "
                                "ORDER BY source,reserved_at").fetchall()
        keys = ("id", "role", "purpose", "bucket", "source", "request_hash", "status", "reserved_at", "result")
        calls = [dict(zip(keys, r)) for r in rows]
        for row in calls:
            row["result"] = json.loads(row["result"]) if row["result"] else None
        return {"spec": self.spec, "execution_binding": self.execution_binding,
                "calls": calls, "oracle_views": oracle,
                "original_allocation": BUCKETS,
                "executor_used": sum(r[1] == "executor" for r in rows),
                "teacher_used": sum(r[1] == "teacher" for r in rows)}
