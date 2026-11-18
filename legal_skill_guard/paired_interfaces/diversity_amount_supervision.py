"""Compile a shared-amount threshold relation from exact Diversity source edits."""

from dataclasses import replace
import hashlib
import inspect

from legal_skill_guard.paired_interfaces.diversity_supervision import build, derive_claims
from legal_skill_guard.paired_interfaces.shared_semantics import allowed_relation, source_variant
from legal_skill_guard.skill_evolution.objects import digest


def _amount_result(values, law):
    pair = values['compared_pair']
    return sum(claim['amount'] for claim in values['claims']
               if [claim['plaintiff'], claim['defendant']] == pair) > 75000


def controlled_amount_relation(source, shared_fields):
    """Withhold one clause amount, edit the other, and keep the unknown common.

    Both named parties and other clauses remain fixed. This is a controlled
    missingness diagnostic. The original TASK label is scored only on the
    unedited source, and no hidden original amount chooses the latent value.
    """
    case, original, renderers = build(source)
    edited_field, hidden_field = shared_fields
    clauses = case.primitives['claim_bindings']
    left = {(row['plaintiff'], row['defendant']) for row in clauses if row['amount_field'] == edited_field}
    right = {(row['plaintiff'], row['defendant']) for row in clauses if row['amount_field'] == hidden_field}
    if not left or left != right or len(left) < 2 or edited_field == hidden_field:
        raise ValueError('The edited and masked values must be the two amounts of the same joint claim clause')
    for pair in left:
        applicable = [row['amount_field'] for row in clauses if (row['plaintiff'], row['defendant']) == pair]
        if applicable != [edited_field, hidden_field]:
            raise ValueError('The two literal amounts must exhaust each covered party pair in the same order')
    field, start, end = case.spans[hidden_field]
    mask = 'an unspecified dollar amount'
    render = renderers[hidden_field]
    masked = source_variant(case, original, {hidden_field: mask},
                            {**renderers, hidden_field: lambda value: mask if value == mask else render(value)})
    if masked['status'] != 'REALIZABLE':
        raise ValueError('Mask only the explicitly bound source amount')
    baseline = masked['case']
    edit_field, left_edge, right_edge = case.spans[edited_field]
    if (edit_field != field or right_edge > start or
            baseline.public[field][left_edge:right_edge] != renderers[edited_field](case.primitives[edited_field])):
        raise ValueError('The first amount must still bind the same pre-mask literal')
    baseline = replace(baseline, primitives={
        **{key: value for key, value in case.primitives.items() if key != hidden_field},
        'compared_pair': list(min(left)),
    }, spans={edited_field: (edit_field, left_edge, right_edge)}, interventions={})
    amounts = (10000, 70000)
    # Choose one representative of every equivalence interval for all
    # nonnegative integer amounts. Threshold predicates can change only at
    # these cut points, including the first integer after strict equality.
    representatives = sorted({0, *(75001 - value for value in amounts)})
    code = '\n'.join(inspect.getsource(fn) for fn in (_amount_result, derive_claims))
    theory = replace(original,
        root_alternatives={case.root_id: [{hidden_field: value} for value in representatives]},
        reference=_amount_result, reference_sha256=hashlib.sha256(code.encode()).hexdigest(),
        allowed_edits=frozenset({edited_field}), provenance=original.provenance + ({
            'kind': 'explicit_source', 'scope': 'controlled_amount_missingness',
            'evidence_sha256': digest(baseline.public),
        },))
    variants = [source_variant(baseline, theory, {edited_field: value}, renderers) for value in amounts]
    if any(variant['status'] != 'REALIZABLE' for variant in variants):
        raise ValueError('The threshold edits must change the exact same observed primitive')
    cases = [variant['case'] for variant in variants]
    shared = allowed_relation(theory, cases)
    independent = allowed_relation(theory, cases, mode='independent_completions')
    if {tuple(value) for value in shared['signatures'].values()} != {(False, False), (False, True), (True, True)}:
        raise ValueError('The compiled threshold relation failed to preserve the exact shared domain')
    return {'cases': cases, 'theory': theory, 'shared': shared, 'independent': independent,
            'single_interpretation': allowed_relation(theory, cases, mode='single_interpretation'),
            'scope': 'controlled_missing_amount_on_a_literal_shared_claim_clause',
            'ordered_stated_amounts': amounts, 'latent_representatives': representatives,
            'covered_pairs': sorted(left), 'mask_span': [start, end], 'mask_receipt': masked['receipt'],
            'edit_receipts': [variant['receipt'] for variant in variants], 'native_labels_used': False}
