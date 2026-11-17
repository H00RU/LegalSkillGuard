"""Lossless public native codecs for independent control source bundles."""
from copy import deepcopy

from legal_skill_guard.skill_evolution.native import answer_wire_schema, decode_answer, record_schema


def source_bundle(source):
    views = deepcopy(source['views'])
    if len({v['id'] for v in views}) != len(views):
        raise ValueError('Native task identities must be unique within the mother source')
    return {'id': 'all_native_source_tasks',
            'public': {'native_views': [{'id': v['id'], 'public': v['public']} for v in views]},
            'answer_schema': record_schema({v['id']: v['answer_schema'] for v in views}),
            'bundle_native_views': views}


def wire_schema(dataset, view):
    if 'bundle_native_views' in view:
        return record_schema({v['id']: answer_wire_schema(dataset, v) for v in view['bundle_native_views']})
    return answer_wire_schema(dataset, view)


def decode_native(dataset, view, value):
    if 'bundle_native_views' in view:
        expected = {v['id'] for v in view['bundle_native_views']}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError('A native bundle must return every current task exactly once')
        answers, evidence = {}, {}
        for native in view['bundle_native_views']:
            answers[native['id']], evidence[native['id']] = decode_answer(dataset, native, value[native['id']])
        return answers, evidence
    return decode_answer(dataset, view, value)
