"""Complete teacher information must survive reference transport exactly."""
import unittest
from legal_skill_guard.skill_evolution.teacher_transport import pack, unpack, serialized, REFERENCE


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


if __name__ == '__main__':unittest.main()
