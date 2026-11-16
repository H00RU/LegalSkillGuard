import unittest
from interface import FiniteSpec, INVALID, collision, compile_grouping, synthesize, verify


class ResidualSynthesisTests(unittest.TestCase):
    def test_synthesizes_date_threshold_partition(self):
        spec = FiniteSpec.build(range(6), (2, 4), lambda day, cutoff: day <= cutoff,
                                lambda u, c: True)
        result = synthesize(spec)
        self.assertEqual(len(set(result.encoding.values())), 3)
        self.assertEqual(result.encode(0), result.encode(2))
        self.assertNotEqual(result.encode(2), result.encode(3))
        self.assertTrue(verify(spec, result))

    def test_all_contexts_not_only_observed_one(self):
        spec = FiniteSpec.build((0, 1), ("ignored", "used"),
            lambda u, c: 0 if c == "ignored" else u, lambda u, c: True)
        witness = collision(spec, {0: 0, 1: 0})
        self.assertEqual(witness.context, "used")
        self.assertEqual(len(set(synthesize(spec).encoding.values())), 2)

    def test_multiquery_outputs_preserved(self):
        spec = FiniteSpec.build((0, 1, 2), (0,),
            lambda u, c: (u > 0, u > 1), lambda u, c: True)
        result = synthesize(spec)
        self.assertEqual(len(set(result.encoding.values())), 3)
        self.assertTrue(verify(spec, result))

    def test_unknown_not_negation_when_consumer_distinguishes(self):
        spec = FiniteSpec.build(("yes", "no", "unknown"), (0,),
            lambda u, c: (u == "yes", u == "unknown"), lambda u, c: True)
        result = synthesize(spec)
        self.assertNotEqual(result.encode("no"), result.encode("unknown"))
        self.assertTrue(verify(spec, result))

    def test_unknown_may_merge_only_if_full_output_equal(self):
        spec = FiniteSpec.build(("no", "unknown"), (0,),
            lambda u, c: False, lambda u, c: True)
        self.assertEqual(len(set(synthesize(spec).encoding.values())), 1)

    def test_invalid_is_not_valid_none(self):
        spec = FiniteSpec.build((0, 1), (0,), lambda u, c: None,
                               lambda u, c: u == 1)
        result = synthesize(spec)
        self.assertEqual(result.decode(result.encode(0), 0), INVALID)
        self.assertNotEqual(result.encode(0), result.encode(1))
        self.assertTrue(verify(spec, result))

    def test_common_context_compatibility_is_not_transitive(self):
        # a~b and b~c on common valid contexts, yet a != c at context z.
        allowed = {("a", "x"), ("a", "z"), ("b", "x"),
                   ("b", "y"), ("c", "y"), ("c", "z")}
        def f(u, c):
            return int(u == "c" and c == "z")
        spec = FiniteSpec.build(("a", "b", "c"), ("x", "y", "z"),
                               f, lambda u, c: (u, c) in allowed)
        def common_compatible(u, v):
            return all(f(u, c) == f(v, c) for c in spec.contexts
                       if (u, c) in allowed and (v, c) in allowed)
        self.assertTrue(common_compatible("a", "b"))
        self.assertTrue(common_compatible("b", "c"))
        self.assertFalse(common_compatible("a", "c"))
        self.assertEqual(len(set(synthesize(spec).encoding.values())), 3)
        self.assertTrue(verify(spec, synthesize(spec)))

    def test_reject_wholeworld_answer_encoder(self):
        spec = FiniteSpec.build((0, 1), (0, 1), lambda u, c: u ^ c,
                               lambda u, c: True)
        whole_world_answers = {(u, c): u ^ c for u in (0, 1) for c in (0, 1)}
        with self.assertRaisesRegex(ValueError, "local states"):
            compile_grouping(spec, whole_world_answers)

    def test_wrong_single_context_answer_grouping_rejected(self):
        spec = FiniteSpec.build((0, 1), (0, 1), lambda u, c: u and c,
                               lambda u, c: True)
        with self.assertRaisesRegex(ValueError, "Insufficient grouping"):
            compile_grouping(spec, {0: 0, 1: 0})

    def test_invalid_world_does_not_call_function(self):
        def f(u, c):
            if u == 0:
                raise AssertionError("Invalid state was executed")
            return True
        spec = FiniteSpec.build((0, 1), (0,), f, lambda u, c: u == 1)
        self.assertTrue(verify(spec, synthesize(spec)))

    def test_missing_context_fails_closed(self):
        spec = FiniteSpec.build((0,), (0,), lambda u, c: True, lambda u, c: True)
        with self.assertRaises(KeyError):
            synthesize(spec).decode(0, "unseen")


if __name__ == "__main__":
    unittest.main()
