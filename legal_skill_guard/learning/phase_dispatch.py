"""Bounded scheduling of independent work, never a learning or answer policy.

The internal frozen evaluator supplies the request-key locking and ordered,
failure-draining precedent. This version also bounds outstanding work and remote
teacher concurrency. No client, model, prompt, grader, retry or fallback lives here.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, CancelledError, ThreadPoolExecutor, wait
from functools import wraps
import threading
from typing import Callable, Iterable, TypeVar

from legal_skill_guard.utils.hashing import canonical_json_sha256

T = TypeVar('T')
R = TypeVar('R')


class PhaseDispatch:
    def __init__(self, config, *, environment=None, on_failure=lambda: None):
        declared = config.get('phase_dispatch')
        if declared is None:
            self.native_workers = self.teacher_workers = 1
            self.required_max_num_seqs = 1
        else:
            if (config.get('execution_contract') != 'direct_statutory_claims'
                    or config.get('execution_contract_version') != 14):
                raise ValueError('Parallel phases are declared only for the current direct EC/EV contract')
            if (not isinstance(declared, dict)
                    or set(declared) != {'policy', 'native_workers', 'teacher_workers',
                                         'required_max_num_seqs'}
                    or declared['policy'] != 'ordered_independent_phases_v1'):
                raise ValueError('Declare the complete independent-phase scheduling policy')
            for name, values in [('native_workers', (1, 4)), ('teacher_workers', (1, 2)),
                                 ('required_max_num_seqs', (1, 4))]:
                if type(declared[name]) is not int or declared[name] not in values:
                    raise ValueError('Invalid declared dispatch setting: ' + name)
            self.native_workers = declared['native_workers']
            self.teacher_workers = declared['teacher_workers']
            self.required_max_num_seqs = declared['required_max_num_seqs']
            argv = (environment or {}).get('actual_argv', [])
            try:
                if argv.count('--max-num-seqs') != 1:
                    raise ValueError('Ambiguous serving sequence limit')
                observed = int(argv[argv.index('--max-num-seqs') + 1])
            except (ValueError, IndexError, TypeError):
                raise ValueError('Capture the actual single-model serving sequence limit') from None
            if observed != self.required_max_num_seqs:
                raise ValueError('Declared dispatch and captured serving profile disagree')
            # Four request workers against a one-sequence server can overlap
            # remote reflection with inference; they do NOT establish GPU batching.
            if self.required_max_num_seqs == 4 and self.native_workers != 4:
                raise ValueError('Four-sequence execution must explicitly dispatch four workers')
        self.progress_lock = threading.RLock()
        self.state_lock = threading.Lock()
        self._key_guard = threading.Lock()
        self._key_locks = {}
        self._teacher_slots = threading.BoundedSemaphore(self.teacher_workers)
        self._on_failure = on_failure

    def receipt(self):
        return {'policy': 'ordered_independent_phases_v1',
                'native_workers': self.native_workers,
                'teacher_workers': self.teacher_workers,
                'required_max_num_seqs': self.required_max_num_seqs}

    @staticmethod
    def payload_key(generation, builder):
        """Use the same complete payload, schema and generation cache identity."""
        def key(*args, **kwargs):
            messages, schema, *_ = builder(*args, **kwargs)
            return canonical_json_sha256({'messages': messages, 'schema': schema,
                                          'generation': generation})
        return key

    def locked_requests(self, function, key):
        """Serialize only identical complete wires, retaining the original actor."""
        if self.native_workers == 1:
            return function

        @wraps(function)
        def guarded(*args, **kwargs):
            fingerprint = key(*args, **kwargs)
            with self._key_guard:
                lock = self._key_locks.setdefault(fingerprint, threading.Lock())
            with lock:
                return function(*args, **kwargs)
        return guarded

    def limited_teacher(self, function):
        """Also cap teachers called from concurrent ACE case trajectories."""
        if self.native_workers == self.teacher_workers == 1:
            return function

        @wraps(function)
        def guarded(*args, **kwargs):
            with self._teacher_slots:
                return function(*args, **kwargs)
        return guarded

    def native(self, function: Callable[[T], R], items: Iterable[T]) -> list[R]:
        return self._ordered(function, items, self.native_workers)

    def teacher(self, function: Callable[[T], R], items: Iterable[T]) -> list[R]:
        return self._ordered(function, items, self.teacher_workers)

    def _ordered(self, function, items, workers):
        values = list(items)
        if workers == 1:
            return [function(item) for item in values]
        if not values:
            return []
        failed = threading.Event()
        error_lock, first_error = threading.Lock(), []
        missing = object()
        results = [missing] * len(values)

        def signal_failure(exc=None):
            with error_lock:
                if exc is not None and not first_error:
                    first_error.append(exc)
                notify = not failed.is_set()
                failed.set()
            if notify:
                self._on_failure()

        def invoke(index):
            if failed.is_set():
                raise CancelledError('Independent phase already failed')
            try:
                return function(values[index])
            except BaseException as exc:
                signal_failure(exc)
                raise

        pool = ThreadPoolExecutor(max_workers=workers)
        pending = {}
        next_index = 0
        try:
            while next_index < min(workers, len(values)):
                pending[pool.submit(invoke, next_index)] = next_index
                next_index += 1
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                if first_error:
                    raise first_error[0]
                for future in sorted(done, key=pending.__getitem__):
                    results[pending.pop(future)] = future.result()
                if first_error:
                    raise first_error[0]
                while len(pending) < workers and next_index < len(values) and not failed.is_set():
                    pending[pool.submit(invoke, next_index)] = next_index
                    next_index += 1
            if first_error:
                raise first_error[0]
            if any(value is missing for value in results):
                raise RuntimeError('An independent phase cannot omit a planned result')
        except BaseException:
            signal_failure()
            for future in pending:
                future.cancel()
            raise
        finally:
            # Actual in-flight responses and costs must be saved before the
            # caller writes its failure terminal or considers any next phase.
            pool.shutdown(wait=True, cancel_futures=True)
        return results
