"""Actual source/semantic boundary regressions for the public grammar adapter."""
from copy import deepcopy
import io
import random
from contextlib import redirect_stdout
import unittest

from legal_skill_guard._vendor.nqg.model.qcfg import qcfg_rule
from legal_skill_guard.skill_evolution.compositional_compiler import (
    acquired_pairs, atom, induce, pack, parse_window, record_from_target,
    rule_json, from_json, source_tokens, unatom, unpack)
from tests.test_skill_evolution_span_compiler import fixture
from legal_skill_guard._vendor.nqg.model.induction import split_utils
from legal_skill_guard.skill_evolution.nqg_indexed_splits import find_possible_splits


class CompositionalCompilerChecks(unittest.TestCase):
    def test_indexed_candidates_exactly_match_upstream_including_recursive_rules(self):
        examples = [
            ('a x c', '( left x )'), ('a x a x', '( x x )'),
            ('a NT_1 c', '( left NT_1 )'),
            ('a NT_1 b NT_2 c', '( NT_2 left NT_1 )'),
            ('a NT_1 b', '( NT_1 NT_1 )'),
            ('a x y b', '( x y left )')]
        rng = random.Random(0)
        for source, target in examples:
            goal = qcfg_rule.rule_from_string(source + ' ### ' + target)
            all_pairs = split_utils._get_split_candidates(goal, False)
            all_known = sorted({r for pair in all_pairs for r in pair})
            for fraction in [.1, .5, .9]:
                known = {r for r in all_known if rng.random() < fraction}
                self.assertEqual(find_possible_splits(goal, known, False),
                    split_utils.find_possible_splits(goal, known, False), (source, target, fraction))

    def test_lossless_atoms_cannot_collide_with_grammar_or_field_syntax(self):
        for text in ['NT_1', '( record )', 'Recipient’s', 'line\nquote "\\', '中文']:
            self.assertEqual(unatom(atom(text)), text)
            self.assertNotIn(atom(text), {'NT_1', 'NT_2', '(', ')'})
        value = ['record', 'kind', ['condition', ['raw', 'A (or B) may act.']]]
        self.assertEqual(unpack(pack(value)), value)
        for invalid in ['(', ')', pack(value) + ' ' + pack('extra')]:
            with self.assertRaises(ValueError):unpack(invalid)

    def test_actual_source_binding_and_role_witness_required(self):
        spec = fixture(); materials = {x['source']: x['quote'] for x in spec['seeds']}
        pairs, shapes, _ = acquired_pairs(spec, materials)
        pair = next(p for p in pairs if p['provenance'][0]['type'] == 'record')
        original = next(s['quote'] for s in spec['seeds'] if ' '.join(source_tokens(s['quote'])) == pair['source'])
        record = record_from_target(pair['target'], original, shapes, spec)
        self.assertEqual(record['values']['entities'], ['entity_x'] if 'workers' in original else ['entity_y'])
        with self.assertRaises(ValueError):record_from_target(pair['target'], 'Unrelated clause.', shapes, spec)
        corrupt = unpack(pair['target']);corrupt.append(['missing_rule', 'invented'])
        with self.assertRaises(ValueError):record_from_target(pack(corrupt), original, shapes, spec)

    def test_raw_field_cannot_bypass_its_source_constructor(self):
        spec = fixture();spec['seeds'][0]['slots'].append({'name': 'actor', 'quote': 'Sender', 'lexicon': None})
        materials = {x['source']: x['quote'] for x in spec['seeds']}
        pairs, shapes, _ = acquired_pairs(spec, materials)
        pair = next(p for p in pairs if p['provenance'][0]['type'] == 'record' and atom('raw') in p['target'])
        obj = unpack(pair['target'])
        for field in obj[2:]:
            if field[0] == 'actor':field[1] = 'Sender'
        with self.assertRaises(ValueError):record_from_target(pack(obj), materials['a'], shapes, spec)

    def test_partial_role_list_is_preserved_and_not_made_exhaustive(self):
        spec = fixture();spec['seeds'] = [deepcopy(spec['seeds'][0])]
        spec['seeds'][0]['quote'] = 'Sender may pass red item to workers and visitors now.'
        spec['seeds'][0]['slots'][0]['quote'] = 'workers and visitors'
        # Restrict the acquired aliases to actual materials, as the host does.
        spec['lexicons'][0]['entries'] = spec['lexicons'][0]['entries'][:1]
        materials = {'a': spec['seeds'][0]['quote']}
        pairs, shapes, _ = acquired_pairs(spec, materials)
        pair = next(p for p in pairs if p['provenance'][0]['type'] == 'record')
        record = record_from_target(pair['target'], materials['a'], shapes, spec)
        self.assertEqual(record['values']['entities'], ['entity_x'])
        self.assertIs(record['lexical']['entities']['complete'], False)

    def test_official_induction_composes_and_roundtrips_without_task_answers(self):
        # Generic transduction, not a new legal performance example.
        pairs = [{'source': 'a x c', 'target': '( left x )'},
                 {'source': 'a y c', 'target': '( left y )'},
                 {'source': 'x', 'target': 'x'}, {'source': 'y', 'target': 'y'}]
        with redirect_stdout(io.StringIO()):rules = induce(pairs)
        self.assertTrue(any(r.arity for r in rules))
        from legal_skill_guard._vendor.nqg.model.qcfg import qcfg_parser
        for p in pairs:self.assertTrue(qcfg_parser.can_parse(p['source'], p['target'], rules))
        self.assertEqual([from_json(rule_json(r)) for r in rules], rules)

    def test_chart_collects_real_record_subspans_without_question_filter(self):
        spec = fixture();materials = {x['source']: x['quote'] for x in spec['seeds']}
        pairs, shapes, _ = acquired_pairs(spec, materials)
        p = next(p for p in pairs if p['provenance'][0]['type'] == 'record')
        rule = qcfg_rule.QCFGRule(tuple(p['source'].split()), tuple(p['target'].split()), 0)
        original = next(s['quote'] for s in spec['seeds'] if ' '.join(source_tokens(s['quote'])) == p['source'])
        text = 'Unrelated prefix. ' + original + ' Unrelated suffix.'
        rows, errors = parse_window(text, [rule], shapes, spec)
        self.assertFalse(errors);self.assertEqual(len(rows), 1)
        a, b = rows[0]['span'];self.assertEqual(text[a:b], original)
        self.assertTrue(rows[0]['derivation'])


if __name__ == '__main__':unittest.main()
