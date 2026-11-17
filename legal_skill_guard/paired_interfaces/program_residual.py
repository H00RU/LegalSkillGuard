"""Exact residual programs under explicitly supplied public context values.

Only replace static reads of declared context fields, and prune closed Boolean
branches. Remaining factual values, unknowns, arithmetic and outputs are kept.
No observed source, prediction, expected answer or grading input is accepted.
"""
import ast
from copy import deepcopy

from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure


def static_input_fields(tree):
    parents = {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    fields = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or node.id != 'inputs' or not isinstance(node.ctx, ast.Load):
            continue
        parent = parents[id(node)]
        if (not isinstance(parent, ast.Subscript) or parent.value is not node
                or not isinstance(parent.ctx, ast.Load)
                or not isinstance(parent.slice, ast.Constant) or not isinstance(parent.slice.value, str)):
            raise ValueError('Exact input slicing requires nonescaping static input-field reads')
        fields.add(parent.slice.value)
    return fields


def closed_value(node):
    """Evaluate only immutable constants and pure Boolean/comparison syntax."""
    if isinstance(node, ast.Constant) and type(node.value) in (str, int, float, bool, type(None)):
        return True, node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        known, value = closed_value(node.operand)
        return (True, not value) if known else (False, None)
    if isinstance(node, ast.BoolOp):
        values = [closed_value(value) for value in node.values]
        if not all(known for known, value in values):
            return False, None
        values = [value for known, value in values]
        result = values[0]
        for value in values[1:]:
            result = (result and value) if isinstance(node.op, ast.And) else (result or value)
        return True, result
    if isinstance(node, ast.Compare):
        values = [closed_value(value) for value in [node.left, *node.comparators]]
        if not all(known for known, value in values):
            return False, None
        values = [value for known, value in values]
        comparisons = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b,
                       ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
                       ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b}
        if any(type(op) not in comparisons for op in node.ops):
            return False, None
        try:
            return True, all(comparisons[type(op)](a, b)
                             for a, op, b in zip(values, node.ops, values[1:]))
        except TypeError:
            return False, None
    return False, None


def specialize(procedure, context, *, allowed_context_fields):
    validate_procedure(procedure)
    if (not context or not set(context) <= set(allowed_context_fields)
            or any(type(value) not in (str, int, bool, type(None)) for value in context.values())):
        raise ValueError('Declare only permitted scalar public context values')
    original = ast.parse(procedure)
    if any(isinstance(node, (ast.Is, ast.IsNot)) for node in ast.walk(original)):
        raise ValueError('Value specialization does not certify observable object identity')
    fields = static_input_fields(original)
    if not set(context) <= fields:
        raise ValueError('A supplied public context field is not read by the frozen program')
    pruning = []

    class Residual(ast.NodeTransformer):
        def visit_Subscript(self, node):
            if (isinstance(node.value, ast.Name) and node.value.id == 'inputs'
                    and isinstance(node.slice, ast.Constant) and node.slice.value in context):
                return ast.copy_location(ast.Constant(value=context[node.slice.value]), node)
            return self.generic_visit(node)

        def visit_If(self, node):
            test = self.visit(node.test)
            known, value = closed_value(test)
            if known:
                pruning.append({'original_line': node.lineno, 'test_after_context_substitution': ast.unparse(test),
                                'selected_branch': 'body' if value else 'orelse'})
                result = []
                for statement in node.body if value else node.orelse:
                    transformed = self.visit(statement)
                    result.extend(transformed if isinstance(transformed, list) else [transformed])
                return result
            node.test = test
            node.body = self._statements(node.body) or [ast.Pass()]
            node.orelse = self._statements(node.orelse)
            return node

        def _statements(self, statements):
            result = []
            for statement in statements:
                value = self.visit(statement)
                result.extend(value if isinstance(value, list) else [value])
            return result

    tree = ast.fix_missing_locations(Residual().visit(deepcopy(original)))
    residual = ast.unparse(tree) + '\n'
    validate_procedure(residual)
    remaining = static_input_fields(tree)
    return {'procedure': residual, 'public_context': context, 'input_fields': sorted(remaining),
        'removed_noncontext_fields': sorted(fields - set(context) - remaining),
        'certificate': {'kind': 'static_context_substitution_and_closed_branch_pruning_v1',
            'original_program_sha256': digest(procedure), 'residual_program_sha256': digest(residual),
            'original_input_fields': sorted(fields), 'residual_input_fields': sorted(remaining),
            'pruned_branches': pruning, 'noncontext_facts_or_arithmetic_rewritten': False,
            'all_outputs_preserved_on_declared_context': True,
            'all_finite_asset_array_lengths_and_numeric_values_preserved': True,
            'source_semantics_or_model_accuracy_certified': False}}
