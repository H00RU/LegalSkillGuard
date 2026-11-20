"""Certify complete disposition when duties are split across operative spans."""

import re

from legal_skill_guard.paired_interfaces import cni_disposition_closure as closure

EXEMPTION = re.compile(
    r'\b(?:shall|will|must) not be (?:destroyed|returned) until\b'
    r'|\b(?:is|are|be) (?:not required|exempt) (?:to|from)\b[^.;]{0,85}\b(?:return|destroy|erase|delet)\w*\b'
    r'|\b(?:may|can|is permitted to)\b[^.;]{0,65}\b(?:retain|keep|maintain)\b',
    re.I,
)
NUMBER = re.compile(r'^\d+(?:\.\d+)+$')
MUTUAL_REQUEST = re.compile(
    r'^if the disclosing party so requests(?: in writing)?, the receiving party shall (?:immediately|promptly)\b\s*[:—-]*$',
    re.I,
)
ALL_DISCLOSED = re.compile(
    r'^return all confidential information including (?:all )?copies to the disclosing party\s*;?\s*and\s*$',
    re.I,
)
ALL_COPIES = re.compile(
    r'^destroy or permanently erase all copies made by the receiving party\b[^.;]{0,100}'
    r'\bprocure that anyone to whom the receiving party has supplied copies destroys or permanently erases such copies\b',
    re.I,
)
EVALUATION_DEFINITION = re.compile(r'\bthe term [“"]Evaluation Material[”"] means all information\b', re.I)
PROTECT_EVALUATION = re.compile(r'\bwill keep the Evaluation Material (?:strictly )?confidential\b', re.I)
DISPOSITION_HEADING = re.compile(r'^Return or Destruction of Documents$', re.I)
NONPROCEED = re.compile(r'^if you determine that you do not wish to proceed with a transaction\b', re.I)
TRIGGER = re.compile(r'^in that case, or in the event that$', re.I)
NOT_CONSUMMATED = re.compile(r'^\(i\) a transaction is not consummated by you or$', re.I)
REQUEST = re.compile(r'^\(ii\) at any time the company so requests, you will promptly$', re.I)
HOLDERS = r'in your possession or in the possession of any of your representatives'
RETURN_BRANCH = re.compile(
    rf'^\(a\) deliver to the company all (?:of the |the )?evaluation material, '
    rf'including all copies\b[^.;]{{0,180}}\b{HOLDERS} or$', re.I,
)
DESTROY_BRANCH = re.compile(rf'^\(b\) destroy all (?:the )?evaluation material {HOLDERS}\b', re.I)
INLINE_RETURN = re.compile(
    r'\brecipient agrees to return to the company\b[^.;]{0,100}\bwritten request all confidential information,'
    r' including but not limited to\b[^.;]{0,180}\bcopies thereof\b', re.I,
)
ALL_MEDIA = re.compile(
    r'^upon request of [^,.;]+, the company shall promptly return all copies of the confidential information,'
    r' in whatever form or media, to [^,.;]+, or certify the destruction of all such confidential information\b',
    re.I,
)
WITHOUT_COPIES = re.compile(
    r'^the receiving party shall return information provided to it any time upon request\b[^.;]{0,190}'
    r'\bor destroy it without retaining any copies or records thereof\b',
    re.I,
)


def new_paths(lines):
    paths = []
    for i, line in enumerate(lines):
        if any(rule.search(line) for rule in (INLINE_RETURN, ALL_MEDIA, WITHOUT_COPIES)):
            paths.append({'form': 'all_material_inline', 'evidence': [i]})
        if NUMBER.fullmatch(line) and i + 3 < len(lines):
            one, two = f'{line}.1 ', f'{line}.2 '
            if (MUTUAL_REQUEST.search(lines[i + 1]) and lines[i + 2].startswith(one)
                    and ALL_DISCLOSED.search(lines[i + 2][len(one):]) and lines[i + 3].startswith(two)
                    and ALL_COPIES.search(lines[i + 3][len(two):])):
                paths.append({'form': 'numbered_duties', 'evidence': [i + 1, i + 2, i + 3]})
        if (DISPOSITION_HEADING.search(line) and i + 6 < len(lines)
                and any(EVALUATION_DEFINITION.search(text) for text in lines[:i])
                and any(PROTECT_EVALUATION.search(text) for text in lines[:i])):
            checks = (NONPROCEED, TRIGGER, NOT_CONSUMMATED, REQUEST, RETURN_BRANCH, DESTROY_BRANCH)
            if all(rule.search(text) for rule, text in zip(checks, lines[i + 1:i + 7], strict=True)):
                paths.append({'form': 'explicit_alternatives', 'evidence': list(range(i + 1, i + 7))})
    return paths


def proof(spans):
    lines = [' '.join(span.split()) for span in spans]
    if any(closure.LATER_EXCEPTION.search(line) or EXEMPTION.search(line) for line in lines):
        return None
    if prior := closure.proof(lines):
        return {'form': 'all_copies_legacy', 'evidence': prior['evidence']}
    paths = new_paths(lines)
    if len(paths) == 1:
        return paths[0]
    return None


def project(native, complete):
    """Retain supported negative readings and repair only a certified closure."""
    if complete is None:
        return native
    evidence = complete['evidence']
    if native['answer'] == 'Contradiction' and set(evidence).issubset(native['evidence_sentence_ids']):
        return native
    return {**native, 'answer': 'Contradiction', 'evidence_sentence_ids': evidence}
