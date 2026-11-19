from experiments.convergence_revision5_maud_section_scope import attachment_proof, policies


ORDINARY = ('(a) Except for measures taken to respond to COVID-19, '
            'the Company shall conduct its business in the ordinary course. ')
NEGATIVE = '(b) Except as required by law, the Company shall not issue shares.'


def test_separate_ordinary_exception_does_not_attach_to_negative_covenant():
    proof = attachment_proof({'source_text': ORDINARY + NEGATIVE})
    assert proof['separate_headers'] and not proof['deeming_only']
    assert policies({'answer': 'Yes'}, proof) == {
        'original': 'Yes', 'deeming_only': 'Yes', 'separate_headers': 'No',
        'attached_exceptions': 'No',
    }


def test_shared_exception_and_explicit_negative_exception_stay_in_scope():
    for heading in ('(b) Except as permitted by Section 5.1(a), '
                    'the Company shall not issue shares.',
                    '(b) Except in response to COVID-19, the Company shall not issue shares.'):
        proof = attachment_proof({'source_text': ORDINARY + heading})
        assert not proof['separate_headers']
        assert set(policies({'answer': 'Yes'}, proof).values()) == {'Yes'}


def test_explicit_pandemic_exception_attaches_to_its_negative_preamble():
    explicit = ('(b) Except as required by applicable Law (including any COVID-19 Measures), '
                'the Company shall not issue shares.')
    proof = attachment_proof({'source_text': ORDINARY + explicit})
    assert proof['attached_negative_exception'] and not proof['separate_headers']
    result = policies({'answer': 'No'}, proof)
    assert result['attached_exceptions'] == 'Yes' and result['separate_headers'] == 'No'


def test_nested_item_example_does_not_extend_to_the_negative_preamble():
    proof = attachment_proof({'source_text': NEGATIVE + ' Temporary closures in response to COVID-19 may continue.'})
    assert not proof['attached_negative_exception']
    assert policies({'answer': 'No'}, proof)['attached_exceptions'] == 'No'
