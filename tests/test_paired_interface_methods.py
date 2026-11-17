"""Mechanism boundaries; fixtures are synthetic and never efficacy evidence."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import inspect
from textwrap import dedent
import unittest

from legal_skill_guard.paired_interfaces import residual as m1
from legal_skill_guard.paired_interfaces import structural_channel as m2


def order_consumer(u, c):
    if u['start'] is None or u['end'] is None:
        return {'before': None, 'after': None}
    return {'before': u['start'] < u['end'], 'after': u['start'] > u['end']}


def duration_consumer(u, c):
    if u['start'] is None or u['end'] is None:
        return {'before': None, 'duration': None}
    return {'before': u['start'] < u['end'],
            'duration': u['end'] - u['start'] >= 2 if c['needs_duration'] else None}


def module(function=order_consumer):
    program = dedent(inspect.getsource(function))
    return m1.FiniteModule.build('test_local_interval',
        {'start': [None, 0, 1, 2], 'end': [None, 0, 1, 2],
         'status': ['stated', 'unknown', 'not_stated', 'negated'], 'irrelevant': ['x', 'y']},
        [{'needs_duration': False}, {'needs_duration': True}], function,
        consumer_sha256=hashlib.sha256(program.encode()).hexdigest(),
        source_scope={'source_fields': ['facts'], 'local_unit': 'one anchored service interval'},
        protected_status_fields=['status'], program_source=program)


class ResidualMethodTests(unittest.TestCase):
    def test_preserved_consumer_is_connected_without_using_the_grader(self):
        from experiments.two_method_airline_module import build
        result = build()
        candidate = result['candidates']['candidates'][0]
        self.assertEqual(result['finite_states'], 101)
        self.assertEqual(result['remaining_contexts'], 36)
        self.assertEqual(candidate['operation'], 'residual_value_partition')
        self.assertEqual(len(candidate['domains']['bag_weight_lbs__residual_code']), 4)
        self.assertIn('integers', m1.reader_prompt(candidate))
        self.assertFalse(candidate['source_scope']['reader_receives_question_or_expected_fee'])
        self.assertFalse(candidate['certificate']['source_semantics_or_reader_accuracy_certified'])

    def test_auto_order_interface_and_decoder_preserve_all_contexts(self):
        spec = module()
        result = m1.propose(spec)
        candidate = next(c for c in result['candidates'] if c['operation'] == 'order_projection')
        self.assertNotIn('start', candidate['domains'])
        self.assertNotIn('end', candidate['domains'])
        for state, outputs in zip(spec.states, spec.outcomes):
            for context, expected in zip(spec.contexts, outputs):
                self.assertEqual(m1.decode(candidate, m1.encode(candidate['features'], state), context,
                                           module_binding=spec.binding), expected)
        self.assertFalse(result['candidate_generation_uses_native_labels_or_model_outputs'])

    def test_duration_in_another_context_prevents_overcompression(self):
        spec = module(duration_consumer)
        result = m1.propose(spec)
        rejected = next(r for r in result['rejected'] if r['operation'] == 'order_projection')
        self.assertTrue(rejected['rejected_by']['context']['needs_duration'])
        self.assertNotEqual(rejected['rejected_by']['left_output'], rejected['rejected_by']['right_output'])
        for candidate in result['candidates']:
            self.assertIn('start', candidate['domains'])
            self.assertIn('end', candidate['domains'])

    def test_necessary_refinement_and_unknown_semantics(self):
        spec = module()
        result = m1.propose(spec, baseline_fields=['start'])
        candidate = result['candidates'][0]
        self.assertEqual(candidate['operation'], 'necessary_refinement')
        self.assertIn('status', candidate['domains'])
        self.assertEqual(set(candidate['domains']['status']), {'stated', 'unknown', 'not_stated', 'negated'})
        self.assertNotIn('irrelevant', candidate['domains'])

    def test_invalid_world_is_distinct_from_legal_none(self):
        spec = m1.FiniteModule.build('validity', {'local_value': [0, 1]}, [{'remaining': False}],
            lambda u, c: None, valid_domain=lambda u, c: u['local_value'] == 1,
            consumer_sha256='a' * 64,
            source_scope={'source_fields': ['facts'], 'local_unit': 'local clause'})
        witness = m1.witness(spec, [])
        self.assertNotEqual(witness['left_output']['valid'], witness['right_output']['valid'])

    def test_anchor_layout_is_a_real_read_grammar_change(self):
        spec = module()
        candidates = m1.propose(spec)['candidates']
        flat, anchored = candidates
        self.assertNotEqual(m1.reader_schema(flat), m1.reader_schema(anchored))
        local = spec.states[0]
        read = {'status': 'complete', 'observation': {'source_anchor': 'service:0',
                'relations': m1.encode(anchored['features'], local)},
                'evidence': [{'field': 'facts', 'quote': 'Alice worked.'}]}
        self.assertTrue(m1.validate_read(anchored, read, {'facts': 'Alice worked.'})['supported'])
        read['evidence'][0]['quote'] = 'Alice worked abroad.'
        with self.assertRaisesRegex(ValueError, 'contiguous'):
            m1.validate_read(anchored, read, {'facts': 'Alice worked.'})

    def test_decoder_rejects_other_versions_and_unseen_domain(self):
        spec = module()
        candidate = m1.propose(spec)['candidates'][0]
        reading = m1.encode(candidate['features'], spec.states[0])
        with self.assertRaisesRegex(ValueError, 'changed'):
            m1.decode(candidate, reading, spec.contexts[0], module_binding='other')
        self.assertFalse(m1.decode(candidate, reading, {'needs_duration': 'undeclared'},
                                   module_binding=spec.binding)['valid'])
        with self.assertRaisesRegex(ValueError, 'answers'):
            m1.FiniteModule.build('bad', {'answer': [True, False]}, [{}], lambda u, c: u,
                consumer_sha256='a' * 64, source_scope={'source_fields': ['facts'], 'local_unit': 'x'})


def graphs(prefix='', extra_event=False):
    p, q, e, f = [prefix + name for name in ('person0', 'person1', 'event0', 'event1')]
    nodes = ((p, 'person'), (q, 'person'), (e, 'event'), (f, 'event'))
    if extra_event:
        nodes += ((prefix + 'event2', 'event'),)
    facts = frozenset({m2.Fact('agent', (e, p)), m2.Fact('patient', (e, q)),
                       m2.Fact('exception', (e,)), m2.Fact('eligible', (p,))})
    ref = m2.Graph(nodes, facts, 'fixture-schema', 'typed-service')
    obs = replace(ref, facts=frozenset((facts - {m2.Fact('agent', (e, p)), m2.Fact('patient', (e, q)),
                                               m2.Fact('exception', (e,))}) |
                                      {m2.Fact('agent', (e, q)), m2.Fact('patient', (e, p)), m2.Fact('exception', (f,))}))
    return ref, obs


def pair(source, ref, obs, *, role='calibration', version='fixture-version'):
    return m2.Pair(source, ref, obs, version, role, 'synthetic unit-test fixture; no legal-data claim')


def worker_eligible(graph):
    eligible = {fact.arguments[0] for fact in graph.facts if fact.predicate == 'eligible'}
    return any(f.arguments[-1] in eligible for f in graph.facts if f.predicate == 'agent')


class StructuralMethodTests(unittest.TestCase):
    def setUp(self):
        self.reference, self.observed = graphs()
        self.dictionary = m2.learn_dictionary([
            pair('development', self.reference, self.observed, role='development')])

    def test_learned_joint_rewrite_transfers_node_identities(self):
        reference, observed = graphs('new-source:')
        learned = self.dictionary['edits'][1]
        self.assertIn(observed, learned.images(reference))
        self.assertTrue(all('person0' not in arg and 'event0' not in arg
                            for fact in learned.before + learned.after for arg in fact.arguments))

    def test_multiple_bindings_remain_multiple_graphs(self):
        reference, observed = graphs(extra_event=True)
        images = self.dictionary['edits'][1].images(reference)
        self.assertIn(observed, images)
        self.assertGreater(len(images), 1)

    def test_systematic_role_error_generalizes_to_a_new_event_count(self):
        p, q = ('p', 'q')
        def world(count, swapped=False):
            nodes = ((p, 'person'), (q, 'person')) + tuple((f'e{i}', 'service_event') for i in range(count))
            facts = frozenset(f for i in range(count) for f in (
                m2.Fact('worker', (f'e{i}', q if swapped else p)),
                m2.Fact('employer', (f'e{i}', p if swapped else q))))
            return m2.Graph(nodes, facts, 'fixture-roles', 'service')
        development = pair('roles-dev', world(2), world(2, True), role='development')
        learned = m2.learn_dictionary([development])
        systematic = [edit for edit in learned['edits'] if edit.all_matches]
        self.assertTrue(systematic)
        self.assertTrue(any(edit.images(world(3)) == frozenset({world(3, True)}) for edit in systematic))

    def test_conditional_edit_without_matching_anchor_keeps_unknown_channel_open(self):
        graph = m2.Graph((('p', 'person'),), frozenset({m2.Fact('eligible', ('p',))}), 'fixture-schema', 'typed-service')
        self.assertEqual(self.dictionary['edits'][1].images(graph), frozenset({graph}))

    def test_ambiguous_source_alignment_is_not_assigned_a_probability(self):
        pairs = [pair(str(i), self.reference, frozenset({self.reference, self.observed})) for i in range(24)]
        channel = m2.fit(pairs, self.dictionary, version='fixture-version', unknown_mode='detectable_residual')
        self.assertEqual(channel.diagnostics['ambiguous_observation_alignments'], 24)
        replay = m2.full_trace_replay(pairs, worker_eligible, {self.reference: 1.})
        self.assertEqual(replay['empirical_risk_interval'], [0., 1.])
        self.assertNotIn('empirical_risk', replay)

    def test_same_mother_repetition_cannot_shrink_uncertainty(self):
        pairs = [pair(str(i), self.reference, self.observed if i % 4 == 0 else self.reference) for i in range(24)]
        a = m2.fit(pairs, self.dictionary, version='fixture-version', unknown_mode='detectable_residual')
        b = m2.fit(pairs * 3, self.dictionary, version='fixture-version', unknown_mode='detectable_residual')
        self.assertEqual(m2.risk(a, worker_eligible, {self.reference: 1.}, version='fixture-version')['interval'],
                         m2.risk(b, worker_eligible, {self.reference: 1.}, version='fixture-version')['interval'])
        self.assertEqual(a.diagnostics['independent_mothers_by_reference'],
                         b.diagnostics['independent_mothers_by_reference'])

    def test_common_mixture_moments_use_heterogeneous_source_clusters(self):
        pairs = []
        for i in range(24):
            reference, _ = graphs('source-' + str(i) + ':')
            pairs.append(pair(str(i), reference, reference))
        channel = m2.fit(pairs, self.dictionary, version='fixture-version', unknown_mode='detectable_residual')
        self.assertEqual(channel.diagnostics['confidence_unit_count'], 24)
        weights = {p.reference: 1 / len(pairs) for p in pairs}
        risk = m2.risk(channel, worker_eligible, weights, version='fixture-version')
        self.assertLess(risk['interval'][1], 1.)
        self.assertTrue(channel.diagnostics['conditional_common_mixture_assumption'])

    def test_unrestricted_unknowns_keep_unit_upper_bound(self):
        pairs = [pair(str(i), self.reference, self.reference) for i in range(64)]
        channel = m2.fit(pairs, self.dictionary, version='fixture-version')
        risk = m2.risk(channel, worker_eligible, {self.reference: 1.}, version='fixture-version')
        self.assertAlmostEqual(risk['interval'][1], 1.)
        selection = m2.select({'a': channel, 'b': channel}, worker_eligible, {self.reference: 1.},
                              versions={'a': 'fixture-version', 'b': 'fixture-version'},
                              costs={'a': 0., 'b': .1}, baseline='a')
        self.assertFalse(selection['risk_upper_bounds_differ'])

    def test_full_trace_control_and_scope_guards(self):
        pairs = [pair(str(i), self.reference, self.observed if i % 4 == 0 else self.reference) for i in range(128)]
        channel = m2.fit(pairs, self.dictionary, version='fixture-version', unknown_mode='detectable_residual')
        replay = m2.full_trace_replay(pairs, worker_eligible, {self.reference: 1.})
        self.assertEqual(replay['empirical_risk'], .25)
        risk = m2.risk(channel, worker_eligible, {self.reference: 1.}, version='fixture-version')
        self.assertLessEqual(risk['interval'][0], .25)
        self.assertGreaterEqual(risk['interval'][1], .25)
        self.assertFalse(m2.risk(channel, worker_eligible, {self.reference: 1.}, version='wrong')['supported'])
        novel, _ = graphs('novel:')
        self.assertFalse(m2.risk(channel, worker_eligible, {novel: 1.}, version='fixture-version')['supported'])
        transferred = m2.risk(channel, worker_eligible, {novel: 1.}, version='fixture-version', allow_stationary_transfer=True)
        self.assertTrue(transferred['conditional_stationary_transfer'])
        with self.assertRaisesRegex(ValueError, 'overlap'):
            m2.fit([pair('development', self.reference, self.observed)], self.dictionary, version='fixture-version')


if __name__ == '__main__':
    unittest.main()
