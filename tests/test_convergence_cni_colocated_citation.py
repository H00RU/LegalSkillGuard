import pytest

from experiments.convergence_revision5_cni_colocated_citation import canonical_citations


@pytest.mark.parametrize(
    ('permission', 'definition', 'expected_permission', 'expected_definition'),
    [([14], 14, [14], None), ([13, 13, 11], 4, [13, 11], 4), ([], 4, [], 4)],
)
def test_citation_normalization_preserves_native_spans(permission, definition, expected_permission, expected_definition):
    reading = {'relations': {'permission_force': 'allow'},
               'permission_spans': permission, 'definition_span': definition}
    normalized = canonical_citations(reading)
    assert normalized == {'relations': reading['relations'],
                          'permission_spans': expected_permission, 'definition_span': expected_definition}
    assert reading['definition_span'] == definition and reading['permission_spans'] == permission
