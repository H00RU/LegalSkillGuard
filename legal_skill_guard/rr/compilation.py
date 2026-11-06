"""Compile/plan the actual next request, using the serving tokenizer's cost."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from .coverage import SourceLedger, complete, plan_batch
from .engine import _program, proposal_schema, source_text, wire_messages
from .public_horn import parse_public
from .client import request_payload


def source_theory(source, previous):
    if not previous.get('completion_assessment'):
        # Invalid/unsupported prior IR is repair evidence, never a compiled K.
        return None
    proposal = previous.get('proposal', {})
    if proposal.get('program', {}).get('kind') == 'public_horn':
        theory = parse_public(source['public']).partial_theory(proposal['compiled_units'])
        if theory.version != previous['completion_assessment']['theory_hash']:
            raise ValueError('Public Horn residual state differs from source')
        return theory
    if proposal.get('program', {}).get('kind') != 'expression':
        return None
    ledger = SourceLedger.from_text(source_text(source))
    units = {c.id: ledger.text[c.start:c.end] for c in ledger.clauses}
    theory = _program(proposal['program'], set(units), units, ledger=ledger,
                      declared=proposal['compiled_units']).get('completion_theory')
    if theory is not None and theory.version != previous['completion_assessment']['theory_hash']:
        raise ValueError('Current source/compiled state differs from its residual theory')
    return theory


def prepare_request(source, *, previous=None, compilation='answer_separating',
                    system_suffix='', user_suffix='', tokenize=None,
                    request_config=None, thinking=True, planning_seconds=5):
    schema = proposal_schema(source['dataset'], source=source, previous=previous)
    ledger = SourceLedger.from_text(source_text(source))
    theory = source_theory(source, previous) if previous else None
    if theory is not None:
        ledger = theory.ledger
    residual = list(previous.get('residual_units', [])) if previous else []
    by_id = {c.id: c for c in ledger.clauses}
    measured = {}

    def render(selected):
        closure = ledger.closure(set(selected))
        prompt = wire_messages(source, previous=previous, selected_units=closure)
        prompt[0]['content'] += system_suffix
        prompt[1]['content'] += user_suffix
        prompt[1]['content'] += '\nRead the selected source units and their shared context once: ' + json.dumps({
            'context_closure': sorted(closure),
            'source_ledger_hash': ledger.version})
        return prompt

    def cost(closure):
        key = tuple(sorted(closure))
        if key not in measured:
            # Render the same selected/context record that will be dispatched.
            # Context units can include already compiled shared definitions.
            selected = sorted(set(closure) & set(residual))
            prompt = render(selected)
            count = tokenize(prompt)['count']
            if type(count) is not int or count < 0:
                raise ValueError('Invalid serving request token count')
            measured[key] = count
        return measured[key]

    action = None
    if previous is None:
        prompt = wire_messages(source)
        prompt[0]['content'] += system_suffix
        prompt[1]['content'] += user_suffix
    else:
        selected, basis = residual, 'conservative_full_source_no_separation_claim'
        plan = None
        if compilation == 'generic_CEGAR_fixed_batch':
            selected, basis = residual[:1], 'generic_fixed_one_unit'
        elif compilation == 'full':
            basis = 'full_source_translation'
        elif theory is not None and tokenize is not None and request_config is not None:
            plan = plan_batch(theory, cost, request_config['context_tokens'] - request_config['max_tokens'],
                              seconds=max(0, min(planning_seconds, 5)))
            if plan.status == 'separation_complete':
                selected, basis = list(plan.selected), plan.status
            else:
                basis = 'conservative_full_source_after_' + plan.status
        elif theory is not None:
            basis = 'token_cost_unavailable'
        if not selected:
            selected, basis = sorted(by_id), 'full_source_IR_repair'
        closure = ledger.closure(set(selected))
        prompt = render(selected)
        action = {'selected': list(selected), 'context_closure': sorted(closure),
                  'selection_basis': basis, 'joint_separation_complete': basis == 'separation_complete',
                  'source_ledger_hash': ledger.version,
                  'batch_plan': asdict(plan) if plan is not None else None}
        if tokenize is not None and request_config is not None:
            actual = tokenize(prompt)['count']
            empty = render([])
            base = tokenize(empty)['count']
            payload = request_payload(request_config, messages=prompt, thinking=thinking, schema=schema)
            action['request_cost'] = {'model_calls': 1, 'input_tokens': actual,
                'base_request_tokens': base, 'selected_context_increment_tokens': actual - base,
                'reserved_output_tokens': request_config['max_tokens'],
                'context_limit_tokens': request_config['context_tokens'],
                'wire_body_sha256': hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest(),
                'cost_basis': 'actual_chat_template_tokens_of_serialized_dispatch_payload'}
            if plan is not None and plan.status == 'separation_complete' and actual != plan.cost:
                raise ValueError('Planned and actual serialized request costs differ')
            if actual + request_config['max_tokens'] > request_config['context_tokens']:
                raise ValueError('Selected request exceeds context; no truncation')
    return {'messages': prompt, 'schema': schema, 'action': action}
