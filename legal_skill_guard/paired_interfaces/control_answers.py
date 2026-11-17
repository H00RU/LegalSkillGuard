"""Lossless public native codecs for independent control source bundles."""
from copy import deepcopy

from legal_skill_guard.skill_evolution.native import answer_wire_schema, decode_answer, record_schema
from legal_skill_guard.skill_evolution.objects import digest


def source_bundle(source):
    views = deepcopy(source['views'])
    if len({v['id'] for v in views}) != len(views):
        raise ValueError('Native task identities must be unique within the mother source')
    public = {'native_views': [{'id': view['id'], 'public': deepcopy(view['public'])} for view in views]}
    if source['dataset'] == 'ContractNLI' and len(views) == 17:
        # A single NDA is reused by the 17 official hypotheses. Keep each
        # hypothesis and its sentence inventory while transmitting the exact
        # document once. Older four-view pilots retain their original wire.
        documents = {}
        for view in public['native_views']:
            fields = view['public']
            context = {name: fields.pop(name) for name in ('source_text', 'sentence_spans')}
            identity = digest(context)
            documents.setdefault(identity, context)
            fields['document_ref'] = identity
        public['shared_documents'] = documents
        public['document_reference_instruction'] = (
            'For every hypothesis, use the document and sentence spans identified by document_ref '
            'in shared_documents. Sentence evidence indices refer to that inventory.')
    return {'id': 'all_native_source_tasks',
            'public': public,
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
