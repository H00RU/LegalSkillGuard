import json

from legal_skill_guard.paired_interfaces.cni_retention_witnesses import (
    decode,
    query,
    verify_consumer,
)

PAYLOAD = {'indexed_spans': [{'id': i, 'text': f'Source {i}'} for i in range(4)]}


def read(grant, bar, checked=True):
    _, schema = query(PAYLOAD)
    payload = {'grant': {'state': grant[0], 'evidence': grant[1]},
               'bar': {'state': bar[0], 'evidence': bar[1]}, 'scope_checked': checked}
    return decode(PAYLOAD, schema, {'finish_reason': 'stop', 'content': json.dumps(payload)})[0]


def test_each_polarity_has_distinct_evidence_with_original_consumer_precedence():
    assert verify_consumer() == 243
    assert read(('operative', [2, 3]), ('operative', [1])) == {'answer': 'Entailment', 'evidence': [2, 3]}
    assert read(('ruled_out', []), ('operative', [1])) == {'answer': 'Contradiction', 'evidence': [1]}


def test_unresolved_or_uncited_grant_does_not_turn_a_bar_into_a_definite_result():
    assert read(('unresolved', []), ('operative', [2])) == {'answer': None, 'evidence': []}
    assert read(('operative', []), ('operative', [2])) == {'answer': None, 'evidence': []}
    assert read(('ruled_out', []), ('operative', [2]), checked=False) == {'answer': None, 'evidence': []}


def test_transport_arrays_are_supported_and_duplicate_evidence_is_rejected_locally():
    _, schema = query(PAYLOAD)
    assert 'uniqueItems' not in schema['properties']['bar']['properties']['evidence']
    assert read(('ruled_out', []), ('operative', [2, 2])) == {'answer': None, 'evidence': []}
