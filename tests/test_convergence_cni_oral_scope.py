from experiments.convergence_revision5_cni_oral_scope import oral_proof


def view(*clauses):
    doc = ''
    spans = []
    for clause in clauses:
        spans.append((len(doc), len(doc) + len(clause)))
        doc += clause + '\n'
    return {'public': {'source_text': doc, 'sentence_spans': spans}}


def test_public_definition_binds_only_the_governed_oral_enumerated_item():
    data = view('“Confidential Information” under this Agreement consists of:',
                '(i) all records disclosed by a party;',
                '(ii) all observations and oral disclosures related to the exchange.',
                'The recipient shall provide written and oral notice of a breach.')
    assert oral_proof(data) == [('definition_list', (0, 2))]


def test_link_to_confidentiality_duty_requires_the_same_provider():
    form = ('Information within the meaning of this Agreement shall include any data which are '
            'disclosed by ALPHA directly or indirectly, in oral or written form.')
    duty = 'The Receiving Party shall treat as strictly confidential any and all information disclosed to it by '
    assert oral_proof(view(form, duty + 'ALPHA.')) == [('same_provider_information_and_duty', (0, 1))]
    assert oral_proof(view(form, duty + 'BETA.')) == []


def test_oral_notice_is_separate_from_the_information_definition():
    data = view('“Confidential Information” means the files furnished by the company.',
                'The recipient shall provide oral notice if legally compelled to disclose any information.')
    assert oral_proof(data) == []


def test_express_oral_exclusion_blocks_generic_medium_coverage():
    data = view('“Confidential Information” means customer data provided in any form.',
                'The agreement explicitly excludes oral disclosures.')
    assert oral_proof(data) == []
