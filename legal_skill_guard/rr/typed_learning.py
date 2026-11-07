"""Source-local connector synthesis from the joint proposal's typed primitives.

No labels or reference programs generate candidates or bind their inputs. Oracle
answers only filter executed candidates and identify observed interface collisions.
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import asdict
from itertools import combinations
from fractions import Fraction

from .coverage import digest
from .interfaces import Amount, AllowanceBank, Connector, InterfaceError, Observation, Relation, Refinement, refine
from .learning import parameterize_graph


def node(op, child, **params):
    return {'op': op, 'inputs': [child], 'params': params}


def candidates(slots, proposed):
    """Enumerate only well-typed instances of the existing seven-connector DSL."""
    result, seen = [], set()
    def add(graph):
        Connector(graph).validate()
        key = digest(graph)
        if key not in seen and len(result) < 32:
            seen.add(key)
            result.append(graph)
    for graph in proposed:
        add(graph)
    relations = sorted(k for k, v in slots.items() if isinstance(v, Relation))
    amounts = sorted(k for k, v in slots.items() if isinstance(v, list) and v and all(isinstance(a, Amount) for a in v))
    limits = sorted(k for k, v in slots.items() if type(v) is int and v >= 0)
    banks = sorted(k for k, v in slots.items() if isinstance(v, AllowanceBank))
    keys = sorted(k for k, v in slots.items() if isinstance(v, tuple) and len(v) == 3 and all(isinstance(x, str) for x in v))
    relation_lists = sorted(k for k, v in slots.items() if isinstance(v, list) and v and all(isinstance(x, Relation) for x in v))
    for name in relation_lists:
        existence = node('map', {'slot': name}, primitive='exists')
        add(node('fold_reduce', existence, primitive='all'))
        add(node('fold_reduce', existence, primitive='any'))
    for left, right in combinations(relations, 2):
        shared = sorted(set(slots[left].columns) & set(slots[right].columns))
        graph = {'op': 'join_on', 'inputs': [{'slot': left}, {'slot': right}], 'params': {'keys': shared}}
        add(node('project_exists', graph))
        if shared:
            apart = {'op': 'bind_rename', 'inputs': [{'slot': right}],
                     'params': {'from': shared, 'to': ['rhs_' + x for x in shared]}}
            add(node('project_exists', {'op': 'join_on', 'inputs': [{'slot': left}, apart], 'params': {'keys': []}}))
        for column in shared:
            add(node('group_by', graph, keys=[column]))
    for name in amounts:
        add({'slot': name})
        add(node('fold_reduce', {'slot': name}, primitive='sum_amounts'))
        for limit in limits:
            add(node('fold_reduce', node('map', {'slot': name}, primitive='cap', limit_slot=limit, scope='element'), primitive='sum_amounts'))
            add(node('map', node('fold_reduce', {'slot': name}, primitive='sum_amounts'), primitive='cap', limit_slot=limit, scope='closed_group'))
            grouped = node('group_by', {'slot': name}, keys=['owner', 'period', 'unit'])
            reduced = node('map', grouped, primitive='sum_amounts')
            capped = node('map', reduced, primitive='cap', limit_slot=limit, scope='closed_group')
            add(capped)
            add(node('fold_reduce', capped, primitive='sum_amounts'))
        for bank in banks:
            for key in keys:
                thread = node('thread_allowance', {'slot': name}, bank_slot=bank, key_slot=key)
                add(thread)
                add(node('fold_reduce', thread, primitive='sum_amounts'))
    return result


def public_variant(source, grade, view):
    """Materialize authorized fact edits, retaining rules and public provenance."""
    result = deepcopy(source)
    if source['dataset'] == 'OpenExempt':
        if view['values'] == [a['dollar_value'] for a in grade['construction_only_case']['assets']]:
            return result
        for family, text in result['public']['views'].items():
            facts_at = text.rfind('Facts:')
            if facts_at < 0:
                raise ValueError('No unambiguous public Facts block')
            rules, facts = text[:facts_at], text[facts_at:]
            replacements = []
            # Construction descriptors identify already-public edits, never rules,
            # eligibility, primitive outputs or target exemption values.
            for asset, new in zip(grade['construction_only_case']['assets'], view['values'], strict=True):
                description, old = asset['description'], asset['dollar_value']
                pattern = re.escape(description) + r'[^.\n]*?\$([\d,]+(?:\.\d{2})?)'
                matches = list(re.finditer(pattern, facts))
                if len(matches) != 1 or Fraction(matches[0][1].replace(',', '')) != Fraction(str(old)):
                    raise ValueError('Asset edit lacks a unique public value quotation')
                match = matches[0]
                cents = Fraction(str(new)) * 100
                if cents.denominator != 1:
                    raise ValueError('Public currency rendering would require rounding')
                rendered = f'{cents.numerator // 100}.{cents.numerator % 100:02d}'
                replacements.append((match.start(1), match.end(1), rendered))
            for start, end, value in sorted(replacements, reverse=True):
                facts = facts[:start] + value + facts[end:]
            result['public']['views'][family] = rules + facts
    elif source['dataset'] == 'RuleArena_Airline':
        text = result['public']['prompt']
        replacements = []
        for i, (old, new) in enumerate(zip(grade['reference_arguments']['bag_list'], view['arguments']['bag_list'], strict=True), 1):
            if old['weight'] == new['weight']:
                continue
            pattern = rf'(?m)^{i}\. [^\n]*?([\d.]+) lbs'
            matches = list(re.finditer(pattern, text))
            if len(matches) != 1 or Fraction(matches[0][1]) != Fraction(str(old['weight'])):
                raise ValueError('Baggage edit lacks a unique numbered public quotation')
            match = matches[0]
            replacements.append((match.start(1), match.end(1), str(new['weight'])))
        for start, end, value in sorted(replacements, reverse=True):
            text = text[:start] + value + text[end:]
        result['public']['prompt'] = text
    elif source['dataset'] == 'SARA_v2_Binary' and view['edit'] is not None:
        edit = view['edit']
        text = result['public']['facts']
        if edit.get('scope') != 'all_fact_occurrences':
            raise ValueError('A charged single-Prolog-fact edit has no verified natural-language rendering')
        result['public']['facts'] = re.sub(r'\b' + re.escape(edit['old']) + r'\b', edit['new'], text)
        if result['public']['facts'] == text:
            raise ValueError('Person reassignment has no public occurrence')
        result['_entity_reassignment'] = {'old': edit['old'], 'new': edit['new']}
    return result


def bind_variant(source, variant, bindings):
    from .coverage import SourceLedger
    from .engine import decode_slots, source_text
    old = SourceLedger.from_text(source_text(source))
    new = SourceLedger.from_text(source_text(variant))
    if len(old.clauses) != len(new.clauses):
        raise ValueError('Fact edit changed source unit boundaries')
    old_units = {c.id: old.text[c.start:c.end] for c in old.clauses}
    new_units = {c.id: new.text[c.start:c.end] for c in new.clauses}
    rebound = deepcopy(bindings)
    def adapt(value, before, after):
        if type(value) is int:
            a = re.findall(r'(?<!\w)\d[\d,]*(?:\.\d+)?(?!\w)', before)
            b = re.findall(r'(?<!\w)\d[\d,]*(?:\.\d+)?(?!\w)', after)
            if len(a) != len(b):
                raise ValueError('Numeric fact edit lacks positional correspondence')
            mapped = {Fraction(y.replace(',', '')) for x, y in zip(a, b) if Fraction(x.replace(',', '')) == value}
            if len(mapped) != 1:
                raise ValueError('Primitive has no unambiguous public literal rebind')
            target = next(iter(mapped))
            if target.denominator != 1:
                raise ValueError('Integer primitive cannot be rounded')
            return int(target)
        if isinstance(value, list):
            return [adapt(v, before, after) for v in value]
        if isinstance(value, dict):
            # Amount metadata is retained; only the fact value is edited.
            return {k: adapt(v, before, after) if k == 'value' else v for k, v in value.items()}
        return value
    for binding in rebound:
        key = binding['source']
        if old_units[key] != new_units[key]:
            if binding['type'] == 'relation' and variant.get('_entity_reassignment'):
                edit = variant['_entity_reassignment']
                binding['value']['rows'] = [[edit['new'] if cell == edit['old'] else cell for cell in row]
                                           for row in binding['value']['rows']]
                continue
            if binding['type'] not in {'integer', 'amount', 'amounts'}:
                raise ValueError('Changed primitive requires a verified extractor; do not invent it')
            binding['value'] = adapt(binding['value'], old_units[key], new_units[key])
    slots, _ = decode_slots({'bindings': rebound}, set(new_units), new_units)
    return slots


def typed_metadata(slots):
    """Keep semantic relationships/state, never raw names or amount fingerprints."""
    result, seen = {}, set()
    def add(field, value): result.setdefault(field, []).append(value)
    def visit(value):
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, list):
            for item in value: visit(item)
        elif isinstance(value, Relation):
            add('entity_equality', [[{'entity': str(cell)} for cell in row] for row in value.rows])
        elif isinstance(value, Amount):
            add('owner_period_keys', [{'owner': value.owner}, {'period': value.period}])
            add('contribution_lineage', [{'lineage': x} for x in sorted(value.lineage)])
            add('aggregation_stage', value.stage)
            add('membership', [[{'lineage': x}, {'owner': value.owner}, {'period': value.period}] for x in sorted(value.lineage)])
        elif isinstance(value, AllowanceBank):
            for key, state in sorted(value.states.items()):
                add('owner_period_keys', [{'rule': key[0]}, {'owner': key[1]}, {'period': key[2]}])
                add('balance', state.balance)
                add('allocation_policy', state.allocation_policy)
                add('order_observable', state.order_observable)
    for value in slots.values(): visit(value)
    return result


def primitive_io(slots):
    """The actual coarse primitive interface, preserving scalar/list ordering.

    Relations project to existence, Amounts to value/unit; ownership, witness
    rows and state are precisely the information offered by the fine interface.
    Dataset fact multisets are not substituted for executed primitive outputs.
    """
    def project(value):
        if isinstance(value, Relation): return {'type': 'relation', 'exists': value.exists()}
        if isinstance(value, Amount): return {'type': 'amount', 'value': value.value, 'unit': value.unit}
        if isinstance(value, AllowanceBank): return {'type': 'allowance_state_handle'}
        if isinstance(value, tuple): return {'type': 'resource_key_handle'}
        if isinstance(value, list): return [project(item) for item in value]
        if type(value) in (str, bool, int) or value is None: return value
        if isinstance(value, Fraction): return {'exact_rational': [value.numerator, value.denominator]}
        raise InterfaceError('No declared coarse primitive output projection')
    return [project(value) for value in slots.values()]


def learn_typed_source(source, grade, oracle, *, proposal=None, trace=None):
    from .source_learning import (OracleUnavailable, candidate_views, coarse_and_metadata, original_view)
    from .engine import connector_output, decode_slots, source_text
    from .coverage import SourceLedger
    bundles = []
    ledger = SourceLedger.from_text(source_text(source))
    units = {c.id: ledger.text[c.start:c.end] for c in ledger.clauses}
    proposal = proposal or {}
    program = proposal.get('program', {})
    body = program.get('body', {})
    if program.get('kind') == 'connector':
        bundles.append((body.get('bindings', []), body.get('candidates', []), body))
    for interface in proposal.get('interfaces', []):
        bundles.append((interface['bindings'], [interface['graph']],
                        {'project': 'entailment_label' if source['dataset'] == 'SARA_v2_Binary' else 'identity'}))
    hypotheses, diagnostics = [], []
    for bindings, proposed, wrapper in bundles:
        try:
            slots, _ = decode_slots({'bindings': bindings}, set(units), units)
            for graph in candidates(slots, proposed):
                hypotheses.append({'graph': graph, 'bindings': bindings, 'wrapper': wrapper})
                if len(hypotheses) == 32:
                    break
        except (ValueError, TypeError, KeyError, InterfaceError) as exc:
            diagnostics.append(str(exc))
        if len(hypotheses) == 32:
            break
    unbound = {}
    def predict(h, view):
        try:
            variant = public_variant(source, grade, view)
            slots = bind_variant(source, variant, h['bindings'])
        except (ValueError, TypeError, KeyError, InterfaceError) as exc:
            unbound[(digest(h), digest(view))] = str(exc)
            return None
        try:
            value = Connector(h['graph']).execute(deepcopy(slots))
            return connector_output(value, h['wrapper'], slots)
        except (ValueError, TypeError, KeyError, InterfaceError):
            return None
    base = original_view(source, grade)
    remaining = candidate_views(source, grade)
    cached = oracle.cached_views()
    cached_keys = {digest(v) for v in cached}
    remaining = [v for v in remaining if digest(v) not in cached_keys]
    typed_views, coarse_views = {}, {}
    if bundles:
        for view in [base] + cached + remaining:
            try:
                merged = {}
                outputs = []
                variant = public_variant(source, grade, view)
                for bindings, _, _ in bundles:
                    bound = bind_variant(source, variant, bindings)
                    outputs.append(primitive_io(bound))
                    for field, values in typed_metadata(bound).items():
                        merged.setdefault(field, []).extend(values)
                typed_views[digest(view)] = merged
                coarse_views[digest(view)] = {'primitive_outputs': outputs}
            except (ValueError, TypeError, KeyError, InterfaceError):
                continue
    def observe_metadata(view):
        key = digest(view)
        return (coarse_views[key], typed_views[key]) if key in coarse_views else (None, None)
    target = grade['targets'] if source['dataset'] == 'OpenExempt' else grade['answer']
    coarse, metadata = observe_metadata(base)
    observations = [Observation(coarse, metadata, target, digest(base))] if coarse is not None else []
    initial = len(hypotheses)
    if initial == 0:
        # Recover already-paid evidence, but do not buy new labels when the
        # model supplied no executable primitive interface to test.
        remaining = []
    base_predictions = [predict(h, base) for h in hypotheses]
    retained = [h for h, prediction in zip(hypotheses, base_predictions) if digest(prediction) == digest(target)]
    queried, events = [], []
    for _ in range(4):
        ranked = []
        for view in remaining:
            c, m = observe_metadata(view)
            if c is None or coarse is None or digest(c) != digest(coarse) or digest(m) == digest(metadata):
                continue
            predictions = [predict(h, view) for h in retained]
            disagreements = sum(digest(a) != digest(b) for a, b in combinations(predictions, 2))
            ranked.append((-disagreements, digest(view), view, predictions))
        if cached:
            view = cached.pop(0)
            key = digest(view)
            predictions = [predict(h, view) for h in retained]
        elif not ranked:
            break
        else:
            _, key, view, predictions = min(ranked, key=lambda x: x[:2])
        remaining = [v for v in remaining if digest(v) != key]
        try:
            answer = oracle.query(view)
        except OracleUnavailable as exc:
            queried.append({'view': view, 'view_hash': key, 'answer': None,
                            'status': 'reference_failed', 'error': str(exc), 'view_slot_charged': True})
            continue
        c, m = observe_metadata(view)
        if c is not None:
            observations.append(Observation(c, m, answer, key))
        queried.append({'view': view, 'view_hash': key, 'answer': answer})
        events.append({'view_hash': key, 'before': [{'graph_hash': digest(h['graph']), 'prediction': p}
                       for h, p in zip(retained, predictions)], 'reference_answer': answer})
        retained = [h for h, p in zip(retained, predictions)
                    if (digest(h), key) in unbound or digest(p) == digest(answer)]
    refinement = refine(observations) if observations else Refinement('primitive_observation_unavailable', [], [])
    pattern = None
    incomplete = any((digest(h), v['view_hash']) in unbound for h in retained
                     for v in queried if v.get('status') != 'reference_failed')
    if refinement.status == 'identified_on_observed_collisions' and retained and not incomplete:
        graphs = {digest(parameterize_graph(h['graph'])): parameterize_graph(h['graph']) for h in retained}
        pattern = {'fields': list(refinement.minimal_field_sets[0]), 'graphs': list(graphs.values()),
                   'basis': 'observed_source_collisions', 'universal_semantic_equivalence_claim': False}
    status = 'typed_inputs_unavailable' if not bundles else 'typed_input_binding_failed' if initial == 0 else \
             'view_rebinding_unavailable' if incomplete else 'NO_VALID_CONNECTOR' if not retained else \
             'executed_typed_source_candidates'
    checks = [{'view_hash': digest(view), 'reference_answer': answer, 'prediction': predict(h, view)}
              for h in retained for view, answer in [(base, target)] +
              [(v['view'], v['answer']) for v in queried if v.get('status') != 'reference_failed']]
    checks = [check for check in checks if check['prediction'] is not None]
    if trace is not None:
        trace.update(source=source['key'], candidate_generator='typed_primitive_connector_enumeration',
            candidate_generator_invoked=True, primitive_bundles=len(bundles), initial_candidates=initial,
            base_predictions=base_predictions, retained_candidates=len(retained), events=events,
            selected_connector_semantics=checks, diagnostics=diagnostics,
            candidate_generation_status=status, selected_pattern=pattern)
        trace['typed_metadata_fields'] = sorted(typed_views.get(digest(base), {}))
        trace['retained_hypotheses'] = [{'graph': h['graph'], 'projection': h['wrapper'].get('project', 'identity')}
                                         for h in retained]
        trace['unbound_primitive_views'] = [{'hypothesis_hash': h, 'view_hash': v, 'reason': reason}
                                           for (h, v), reason in sorted(unbound.items())]
    failures = sum(v.get('status') == 'reference_failed' for v in queried)
    return {'status': 'reference_oracle_unresolved' if failures and pattern is None else refinement.status,
            **({'reference_failures': failures} if failures else {}),
            'oracle_views': queried, 'refinement': asdict(refinement), 'learned_pattern': pattern,
            'connector_candidates_generated': initial, 'connector_candidates_retained': len(retained),
            'connector_synthesis_status': status, 'candidate_generator_invoked': True,
            'schema_repair_needed': status in {'typed_inputs_unavailable', 'typed_input_binding_failed', 'NO_VALID_CONNECTOR'},
            'finite_candidate_pool_is_Omega': False}
