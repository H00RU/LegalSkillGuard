"""Carry a witnessed update veto only to contracts with its source role."""

import re

FACT_EVENT = re.compile(
    r'\b(?:fact that|existence of)\b[^.;]{0,170}\b(?:discussions?|negotiations?)\b', re.I,
)
NEGOTIATION_CONFIDENTIALITY = re.compile(
    r'\b(?:confidential|disclos\w*|publish\w*|announc\w*|advertis\w*)\b', re.I,
)
DISCLOSURE = re.compile(r'\b(?:reveal|divulge|disclos(?:e|ed|ure)|transmit)\b', re.I)
REPRESENTATIVES = re.compile(
    r'\b(?:agents?|representatives?|consultants?|advis(?:ers?|ors?)|legal counsel)\b', re.I,
)
RESTRICTION = re.compile(
    r'\b(?:only to|need to know|need-to-know|necessary for|on a strictly confidential basis)\b', re.I,
)
CONTINUING_ORAL = re.compile(
    r'\boral(?:ly)?\s+(?:Information|disclosures?)\b[^.;]{0,150}\b(?:continue\w*|remain\w*)\b'
    r'[^.;]{0,85}\b(?:subject to|protected|confidential)\b', re.I,
)

FAMILIES = {
    'nda-10': 'confidentiality_of_negotiations',
    'nda-7': 'restricted_disclosure_to_representatives',
    'nda-3': 'continuing_coverage_of_oral_information',
}


def matched_spans(task, spans):
    """Identify source wording for the veto family without deciding any label."""
    result = []
    for index, value in enumerate(spans):
        text = ' '.join(value.split())
        if task == 'nda-10':
            matched = FACT_EVENT.search(text) and NEGOTIATION_CONFIDENTIALITY.search(text)
        elif task == 'nda-7':
            matched = DISCLOSURE.search(text) and REPRESENTATIVES.search(text) and RESTRICTION.search(text)
        elif task == 'nda-3':
            matched = CONTINUING_ORAL.search(text)
        else:
            raise ValueError(f'No registered source family for {task}')
        if matched:
            result.append(index)
    return result


def bind_veto(task, source_spans, witness_spans):
    matched = set(matched_spans(task, source_spans)).intersection(witness_spans)
    if not matched:
        raise ValueError('The selected training witness must carry the declared source role')
    return {'task': task, 'source_role': FAMILIES[task], 'witness_matches': sorted(matched)}


def chosen_role(binding, target_spans, *, selected, native_fit):
    if binding['source_role'] != FAMILIES[binding['task']]:
        raise ValueError('Keep the source-role binding from TRAIN')
    return selected if matched_spans(binding['task'], target_spans) else native_fit
