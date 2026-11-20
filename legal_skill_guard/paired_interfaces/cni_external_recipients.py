"""Ground permitted access by external advisers in a ContractNLI source."""

import re

from legal_skill_guard.paired_interfaces import cni_recipient_evidence as recipients


EXTERNAL = re.compile(r'\b(?:professional advis[eo]rs?|independent consultants?)\b', re.I)
RECEIVER = re.compile(r'^(?:\d+(?:\.\d+)*\.? )?the receiving party\b', re.I)
DEFINED_ACCESS = re.compile(
    r'\bundertakes to permit access to the Confidential Information only to its Representatives\b',
    re.I,
)
NAMED_ACCESS = re.compile(
    r'\bshall restrict access to the Confidential Information to those agents and professional advis[eo]rs '
    r'to whom disclosure is necessary\b', re.I,
)
DISCLOSURE_RECIPIENT = re.compile(
    r'^With respect to any Confidential Information disclosed to it or to which it has access, '
    r'(?P<party>[A-Z][A-Za-z]+) affirms that it shall:',
)
NECESSARY_DISCLOSURE = re.compile(
    r'^(?P<party>[A-Z][A-Za-z]+) shall restrict disclosure of such Confidential Information '
    r'to its employees and/or consultants with a need to know\b',
)
PRIOR_CONSENT = re.compile(
    r'\b(?:consent|approval|authorization|permission)\s+(?:of|from|by)\b|'
    r'\b(?:prior|written) (?:consent|approval|authorization|permission)\b', re.I,
)


def paths(spans):
    """Require a visible grant to the receiving party and an explicit outside class."""
    lines = [' '.join(span.split()) for span in spans]
    declarations = [(i, line[match.end():]) for i, line in enumerate(lines)
                    if (match := recipients.DECLARATION.match(line))]
    parties = [(match['party'], i) for i, line in enumerate(lines) if (match := DISCLOSURE_RECIPIENT.match(line))]
    witnesses = {}
    for i, line in enumerate(lines):
        operative = recipients.SEPARATE_DUTY.split(line, maxsplit=1)[0]
        if match := NECESSARY_DISCLOSURE.match(operative):
            leads = [j for party, j in parties if party == match['party'] and j < i]
            if len(leads) == 1 and not PRIOR_CONSENT.search(operative):
                witnesses[i] = [leads[0], i]
            continue
        if not RECEIVER.match(line) or PRIOR_CONSENT.search(line):
            continue
        if NAMED_ACCESS.search(line):
            witnesses[i] = [i]
        elif DEFINED_ACCESS.search(line) and len(declarations) == 1:
            (index, definition), = declarations
            if EXTERNAL.search(definition.split(';', 1)[0]):
                witnesses[i] = sorted((index, i))
    return witnesses


def apply(native, witnesses):
    """Complete an already cited permission or resolve a uniquely proved grant."""
    cited = set(native['evidence_sentence_ids'])
    if native['answer'] == 'Entailment':
        touched = [chain for anchor, chain in witnesses.items() if anchor in cited]
        if len(touched) == 1:
            return {**native, 'evidence_sentence_ids': sorted(cited | set(touched[0]))}
        return native
    if len(witnesses) == 1:
        (chain,) = witnesses.values()
        return {**native, 'answer': 'Entailment', 'handled': True, 'reason': None,
                'evidence_sentence_ids': chain}
    return native
