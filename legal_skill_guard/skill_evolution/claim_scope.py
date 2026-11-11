"""A conservative check of an explicitly declared final proposition.

This does not infer scope from a dataset, skill name or background citation.
Unrecognized/ambiguous descriptions remain unknown. It is not a verifier of
the legal procedure or of the truth of any local model output.
"""
import re


CLAUSE = r'(?P<section>\d+)(?P<path>(?:\s*\([A-Za-z0-9]+\))*)'
CITATION = re.compile(r'(?:§|\bsection\b)\s*' + CLAUSE, re.I)
FINAL_CLAIM = re.compile(r'\banswer\s+to\s+the\s+current\s+(?:§|section\s+)\s*' +
    CLAUSE + r'\s+(?:proposition|claim|question)\b', re.I)


def parts(match):
    return (match['section'], *re.findall(r'\(([A-Za-z0-9]+)\)', match['path']))


def declared_claim_mismatch(skill, view):
    description = skill.outputs.get('answer', {}).get('description')
    if not isinstance(description, str):
        return None
    declarations = {parts(m) for m in FINAL_CLAIM.finditer(description)}
    mentioned = {parts(m) for m in CITATION.finditer(description)}
    if len(declarations) != 1 or mentioned != declarations:
        return None
    declared = next(iter(declarations))
    bound_inputs = []
    for name, port in skill.inputs.items():
        prompt = port.get('question', '')
        if (port['mode'] == 'read' and re.search(r'\bcurrent\s+question\b', prompt, re.I)
                and re.search(r'\baffirm\b|\bask\s+whether\b', prompt, re.I)
                and {parts(m) for m in CITATION.finditer(prompt)} == {declared}):
            bound_inputs.append({'port': name, 'question': prompt})
    if not bound_inputs:
        return None  # A source-specific description alone is not an applicability contract.
    question = view['public'].get('question')
    if not isinstance(question, str):
        return None
    queries = {parts(m) for m in CITATION.finditer(question)}
    if len(queries) != 1:
        return None
    queried = next(iter(queries))
    if declared[:len(queried)] == queried or queried[:len(declared)] == declared:
        return None  # Exact or ancestor scope; this check does not prove incompatibility.
    return {'kind': 'explicit_final_claim_mismatch', 'declared_clause': list(declared),
        'queried_clause': list(queried), 'output_description': description,
        'query_bound_input_ports': bound_inputs,
        'current_question': question, 'legal_rule_truth_inferred': False,
        'source_ids_labels_or_dataset_gate_used': False}
