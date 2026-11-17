"""Actual program worker and original18 paid-read replay;no model dispatch."""
from copy import deepcopy
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import sqlite3
from types import SimpleNamespace
import unittest

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read
from legal_skill_guard.paired_interfaces.control_learning import direct_program
from legal_skill_guard.paired_interfaces.formal_actors import (
    InterfaceActor, ProgramActor, verify_physical_response, restore_airline_wire_order)
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.objects import digest


class WireFixture:
    def __init__(self, response):
        self.response, self.calls = response, []
        self.ledger = SimpleNamespace(run_id='constructed_formal_actor_fixture')
        self.config = {'enable_thinking': False, 'fixture': True}

    def generate(self, identity, **kwargs):
        self.calls.append((identity, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return deepcopy(self.response)


class FormalActorTests(unittest.TestCase):
    def source(self):
        return {'key': 'SARA_v2_Binary:constructed', 'dataset': 'SARA_v2_Binary', 'views': [
            {'id': 'native', 'public': {'facts': 'constructed fixture', 'question': 'True or false?'},
             'answer_schema': {'type': 'boolean'}}]}

    def test_direct_seed_uses_actual_program_worker_native_codec_and_OFF_profile(self):
        response = {'content': json.dumps({'value': {'native': {'answer': True, 'evidence_sentence_ids': []}}}),
                    'finish_reason': 'stop', 'usage': {}, 'elapsed_seconds': 0, 'cache_hit': False}
        executor = WireFixture(response)
        library = sealed({'arm': 'empty', 'batch': 0, 'program': direct_program()}, 'snapshot_sha256')
        with tempfile.TemporaryDirectory() as tmp:
            actor = ProgramActor(executor, tmp, max_calls=10, physical_verifier=lambda **kw: None)
            first = actor(self.source(), library, 'skill_dev')
            self.assertTrue(first['native']['native']['answer'])
            self.assertTrue(first['program_execution_completed'])
            self.assertFalse(first['learned_main_path_executed'])
            self.assertEqual(first['execution_mode'], 'direct_empty')
            self.assertFalse(first['fallback_executed'])
            actor(self.source(), library, 'skill_dev')
            self.assertEqual(len(executor.calls), 1)
            self.assertEqual(executor.calls[0][1]['purpose'], 'skill_dev')
            self.assertFalse(executor.calls[0][1]['thinking'])

    def test_physical_failure_stops_and_cannot_become_cached_abstention(self):
        executor = WireFixture(BudgetError('constructed failed transport'))
        library = sealed({'arm': 'empty', 'batch': 0, 'program': direct_program()}, 'snapshot_sha256')
        with tempfile.TemporaryDirectory() as tmp:
            actor = ProgramActor(executor, tmp, max_calls=10, physical_verifier=lambda **kw: None)
            with self.assertRaises(BudgetError):
                actor(self.source(), library, 'skill_dev')
            with self.assertRaisesRegex(BudgetError, 'unreceived physical'):
                actor(self.source(), library, 'skill_dev')
            self.assertEqual(len(executor.calls), 1)

    def test_all18_original_paid_OE_responses_follow_formal_actor_without_gold(self):
        original = BASE / 'asset_port_reads_v1/71eee85048e48fe8ebf7f4a190c4df814cdc5f36efc1b1c450123c3e05b72f3c'
        preflight = BASE / 'formal_read_preflight_v1/6e22e5920c3df1aac061f9bd159788e44b30c9bd570fc9f740c4c0894a56058f'
        records = read(original / 'paired_reads.json')
        source_keys = {row['source'] for row in records}
        public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
                  if s['key'] in source_keys}
        requests = read(original / 'requests.json')
        table = {}
        for request in requests:
            row = next(row for row in records if (row['source'], row['view'], row['raw_read_version']) ==
                       (request['source'], request['opaque_view'], request['version']))
            table[digest([request['source'], request['messages'], request['schema']])] = read(
                original / 'calls' / digest(row['physical_call_id']) / 'result.json')
        class ArchiveExecutor(WireFixture):
            def generate(self, identity, **kwargs):
                self.calls.append(identity)
                return deepcopy(table[digest([kwargs['source'], kwargs['messages'], kwargs['schema']])])
        executor = ArchiveExecutor(None); executor.config = read(original / 'protocol.json')['executor']
        with tempfile.TemporaryDirectory() as tmp:
            actor = InterfaceActor(executor, tmp, plan_assets=read(preflight / 'plan_assets.json'),
                                   source_inputs=inputs, pipeline_binding={'fixture_replay': 'v2'},
                                   physical_verifier=lambda **kw: None)
            output = []
            for source in public.values():
                for view in actor.views(source):
                    for plan in view['plans']:
                        value = actor.measure(source, view, plan, 'skill_actor')
                        self.assertEqual(value, actor.measure(source, view, plan, 'skill_actor'))
                        output.append(value)
            self.assertEqual(len(executor.calls), 18)
            self.assertEqual(sum(not row['production_errors'] for row in output), 14)
            self.assertEqual(sum(value['handled'] for row in output for value in row['native'].values()), 3)
            self.assertTrue(all(row['source_reference_or_native_label_used'] is False for row in output))

    def test_default_cached_response_verifier_rejects_changed_or_failed_physical_rows(self):
        db = sqlite3.connect(':memory:'); self.addCleanup(db.close)
        db.execute('create table calls(id text,status text,source text,purpose text,result text)')
        physical = {'content': '{}', 'usage': {'prompt_tokens': 5, 'completion_tokens': 2}, 'finish_reason': 'stop'}
        db.execute('insert into calls values(?,?,?,?,?)', ('fixture', 'completed', 'source', 'skill_dev', json.dumps(physical)))
        @contextmanager
        def transaction():
            yield db
        executor = SimpleNamespace(ledger=SimpleNamespace(transaction=transaction))
        kw = {'identity': 'fixture', 'source': 'source', 'purpose': 'skill_dev',
              'content_sha256': digest('{}'), 'usage': physical['usage'], 'finish_reason': 'stop'}
        verify_physical_response(executor, **kw)
        with self.assertRaisesRegex(BudgetError, 'differs from its actual'):
            verify_physical_response(executor, **{**kw, 'content_sha256': digest('changed')})
        db.execute("update calls set status='failed'")
        with self.assertRaisesRegex(BudgetError, 'no matching completed'):
            verify_physical_response(executor, **kw)

    def test_M1_static_choice_still_requires_its_actual_calibrated_reader_version(self):
        preflight = BASE / 'formal_read_preflight_v1/6e22e5920c3df1aac061f9bd159788e44b30c9bd570fc9f740c4c0894a56058f'
        source = next(s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
                      if s['key'] == 'OpenExempt:d7a7ea93cee4a34d9e80d95eed868bb20bbc9726fa4f6c1131be9be93bd64102')
        executor = WireFixture(None)
        with tempfile.TemporaryDirectory() as tmp:
            actor = InterfaceActor(executor, tmp, plan_assets=read(preflight / 'plan_assets.json'),
                source_inputs=inputs, pipeline_binding={'fixture': 'changed pipeline'})
            view = actor.views(source)[0]
            library = sealed({'arm': 'M1_only', 'batch': 1, 'M1_choices': {'OpenExempt': {'plan': 'columns'}},
                'raw_reader_channel_versions': [{'dataset': 'OpenExempt', **view['scope'],
                                                'plan': 'columns', 'version': '0' * 64}]}, 'snapshot_sha256')
            with self.assertRaisesRegex(ValueError, 'different actual reader/decoder'):
                actor(source, library, 'skill_dev')
            self.assertEqual(executor.calls, [])

    def test_saved_program_predictions_recheck_physical_evidence_without_generation(self):
        response = {'content': json.dumps({'value': {'native': {'answer': True, 'evidence_sentence_ids': []}}}),
                    'finish_reason': 'stop', 'usage': {}, 'elapsed_seconds': 0, 'cache_hit': False}
        executor = WireFixture(response); changed = [False]
        def physical(**kwargs):
            if changed[0]: raise BudgetError('constructed orphaned physical response')
        library = sealed({'arm': 'empty', 'batch': 0, 'program': direct_program()}, 'snapshot_sha256')
        with tempfile.TemporaryDirectory() as tmp:
            actor = ProgramActor(executor, tmp, max_calls=10, physical_verifier=physical)
            result = actor(self.source(), library, 'skill_dev')
            actor.verify_saved(self.source(), library, 'skill_dev', result)
            changed[0] = True
            with self.assertRaisesRegex(BudgetError, 'orphaned physical'):
                actor.verify_saved(self.source(), library, 'skill_dev', result)
            self.assertEqual(len(executor.calls), 1)

    def test_saved_interface_read_must_match_the_sealed_prior_choice(self):
        original = BASE / 'asset_port_reads_v1/71eee85048e48fe8ebf7f4a190c4df814cdc5f36efc1b1c450123c3e05b72f3c'
        preflight = BASE / 'formal_read_preflight_v1/6e22e5920c3df1aac061f9bd159788e44b30c9bd570fc9f740c4c0894a56058f'
        actual = read(original / 'paired_reads.json')
        table = {digest([r['source'], r['messages'], r['schema']]): read(original / 'calls' /
                 digest(next(v['physical_call_id'] for v in actual if (v['source'], v['view'], v['raw_read_version']) ==
                        (r['source'], r['opaque_view'], r['version']))) / 'result.json')
                 for r in read(original / 'requests.json')}
        class ArchiveExecutor(WireFixture):
            def generate(self, identity, **kwargs):
                self.calls.append(identity)
                return deepcopy(table[digest([kwargs['source'], kwargs['messages'], kwargs['schema']])])
        executor = ArchiveExecutor(None); executor.config = read(original / 'protocol.json')['executor']
        source = next(s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
                      if s['key'] == actual[0]['source'])
        with tempfile.TemporaryDirectory() as tmp:
            actor = InterfaceActor(executor, tmp, plan_assets=read(preflight / 'plan_assets.json'), source_inputs=inputs,
                pipeline_binding={'constructed_replay_fixture': True}, physical_verifier=lambda **kw: None)
            views = actor.views(source)
            library = sealed({'arm': 'M1_only', 'batch': 1,
                'M1_choices': {'OpenExempt': {'plan': 'columns', 'supported': True}},
                'raw_reader_channel_versions': [{'dataset': 'OpenExempt', **view['scope'], 'plan': 'columns',
                    'version': actor.channel_version(next(p for p in view['plans'] if p['name'] == 'columns'))}
                    for view in views]}, 'snapshot_sha256')
            result = actor(source, library, 'skill_actor')
            actor.verify_saved(source, library, 'skill_actor', result)
            count = len(executor.calls)
            changed = deepcopy(result); changed['decisions'][0]['choice']['plan'] = 'records'
            with self.assertRaisesRegex(BudgetError, 'sealed prior choice'):
                actor.verify_saved(source, library, 'skill_actor', changed)
            self.assertEqual(len(executor.calls), count)

    def test_original_paid_wires_including_Airline_schema_order_remain_identical(self):
        from experiments.two_method_formal_study import PREFLIGHT, wire_reuse_audit
        bank = read(PREFLIGHT / 'plan_assets.json'); pilot = read(BASE / 'pilot_lock.json')
        restored = restore_airline_wire_order(bank, pilot['plans']['RuleArena_Airline'])
        self.assertEqual(digest(restored), digest(bank))
        audit = wire_reuse_audit(restored, pilot['executor'])
        self.assertEqual(len(audit['literal_paid_wire_matches']), 132)
        self.assertEqual(audit['new_model_requests'], 0)
        original = bank['unchanged_libraries']['RuleArena_Airline'][0]
        changed = restored['unchanged_libraries']['RuleArena_Airline'][0]
        executor = WireFixture(None)
        with tempfile.TemporaryDirectory() as tmp:
            actor = InterfaceActor(executor, tmp, plan_assets=bank, source_inputs=inputs, pipeline_binding={'fixture': True})
            self.assertNotEqual(actor.channel_version(original), actor.channel_version(changed))


if __name__ == '__main__':
    unittest.main()
