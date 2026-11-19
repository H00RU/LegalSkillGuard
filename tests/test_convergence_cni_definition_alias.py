import json

import pytest

from experiments.convergence_revision5_cni_definition_alias import renamed_document, replace_wire
from legal_skill_guard.skill_evolution.objects import digest


def test_alias_updates_evidence_offsets_without_moving_native_indices():
    first = '“Representatives” means employees and advisors.'
    second = 'The party may disclose to its Representatives.'
    source = first + '\n' + second
    spans = [[0, len(first)], [len(first) + 1, len(source)]]
    revised, corrected, occurrences = renamed_document(source, spans, 0, {1})
    assert occurrences == 2 and revised.replace('Review Participants', 'Representatives') == source
    record = {'source_text': source, 'sentence_spans': spans}
    key = digest(record)
    record['evidence_units'] = [{'start': a, 'end': b, 'id': i, 'text': source[a:b]}
                                for i, (a, b) in enumerate(spans)]
    public = {'shared_documents': {key: record}, 'native_views': [{'public': {'document_ref': key}}]}
    payload = {'messages': [{'role': 'system', 'content': 'fixed'},
                            {'role': 'user', 'content': json.dumps({'public': public}, sort_keys=True)}]}
    result = replace_wire(payload, source, spans, revised, corrected)
    assert result[0] == payload['messages'][0]
    edited = json.loads(result[1]['content'])['public']
    new_key, = edited['shared_documents']
    assert edited['native_views'][0]['public']['document_ref'] == new_key != key
    for i, row in enumerate(edited['shared_documents'][new_key]['evidence_units']):
        a, b = corrected[i]
        assert (row['id'], row['start'], row['end'], row['text']) == (i, a, b, revised[a:b])


def test_alias_refuses_to_perturb_a_broken_native_boundary():
    source = 'Representatives means employees. The party may disclose to Representatives.'
    anchor = source.index(' The')
    with pytest.raises(ValueError, match='boundary splits'):
        renamed_document(source, [[0, anchor], [anchor + 1, len(source)], [2, 5]], 0, {1})
