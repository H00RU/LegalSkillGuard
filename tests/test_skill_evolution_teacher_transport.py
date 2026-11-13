"""Complete teacher information must survive reference transport exactly."""
import unittest
from legal_skill_guard.skill_evolution.teacher_transport import pack, unpack, serialized, REFERENCE
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, unpack_programs, PROGRAM_SEGMENTS


class TeacherTransportTests(unittest.TestCase):
    def test_nested_repeated_programs_and_quotes_roundtrip_with_exact_order(self):
        quote = 'A literal legal source with spaces, unicode §, and newline\n' * 20
        record = {'quote': quote, 'number': 0, 'absent': None, 'flag': False}
        value = {'sources': [record, record], 'trace': {'original_quote': quote, 'record': record}}
        packed = pack(value)
        self.assertEqual(serialized(unpack(packed)), serialized(value))
        self.assertLess(len(serialized(packed)), len(serialized(value)))

    def test_equal_values_with_different_key_orders_remain_exact(self):
        value = [{'a':'x'*300,'b':1},{'b':1,'a':'x'*300},['x'*300,False,0,None]]
        self.assertEqual(serialized(unpack(pack(value))), serialized(value))

    def test_reserved_key_and_cycles_are_rejected(self):
        with self.assertRaises(ValueError):pack({REFERENCE:'real_input_key'})
        with self.assertRaises(ValueError):unpack({'encoding':'lossless_shared_JSON_values_v1',
            'shared_values':{'v0':{REFERENCE:'v0'}},'task':{REFERENCE:'v0'}})

    def test_unique_fields_and_types_are_preserved_without_sharing(self):
        value = {'labels':['Yes','No'],'types':[False,0,0.0,None,True],'quote':'a b\n§'}
        self.assertEqual(serialized(unpack(pack(value))), serialized(value))

    def test_actual_helper_sharing_preserves_comments_gaps_and_unicode_bytes(self):
        shared = 'def helper(x):\n    # §: keep this exact comment\n    return x + ' + repr('literal ' * 50) + '\n'
        first = '\n# prefix\n' + shared + '\n\ndef apply(inputs,premises):\n    return helper(1)\n# tail\n'
        second = '\n# different prefix\n' + shared + '\n\ndef apply(inputs,premises):\n    return helper(2)\n'
        task = {'source_program': first, 'spec': {'decision_program': second}, 'ordinary_string': first}
        packed = pack_programs(task)
        self.assertEqual(serialized(unpack_programs(packed)), serialized(task))
        self.assertLess(len(serialized(packed)), len(serialized(task)))

    def test_single_function_and_nonprogram_text_are_not_reinterpreted(self):
        task = {'source_program': 'def apply(inputs,premises):\n    return {}\n',
                'legal_quote': 'def is a word in this source, not program code.'}
        self.assertEqual(unpack_programs(pack_programs(task)), task)
        with self.assertRaises(ValueError):
            pack_programs({PROGRAM_SEGMENTS: ['not an encoded source']})


if __name__ == '__main__':unittest.main()
