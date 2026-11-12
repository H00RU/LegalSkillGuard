"""Bounded source-premise candidates from observable local record construction."""
import ast


def local_record_blocks(procedure, premise_names):
    """Infer candidates, never legal truth, from nonterminal record use-defs.

    A final output dictionary is not a coupling edge. Ambiguous assignments
    are not followed. The result names existing ports and never creates a
    rule, value, source interpretation or reading question.
    """
    tree = ast.parse(procedure)
    parents = {id(c): n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    definitions = {}
    stores = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stores[node.id] = stores.get(node.id, 0) + 1
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            definitions.setdefault(node.targets[0].id, []).append(node.value)

    def dependencies(node, visiting=frozenset()):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == 'premises' and isinstance(node.slice, ast.Constant)
                and node.slice.value in premise_names):
            return {node.slice.value}
        if isinstance(node, ast.Name):
            if (node.id in visiting or stores.get(node.id) != 1
                    or len(definitions.get(node.id, [])) != 1):return set()
            return dependencies(definitions[node.id][0], visiting | {node.id})
        result = set()
        for child in ast.iter_child_nodes(node):result.update(dependencies(child, visiting))
        return result

    records = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict) or isinstance(parents.get(id(node)), ast.Return):continue
        ports = dependencies(node)
        if 1 < len(ports) <= 3:
            records.append({'ports': sorted(ports), 'record_site': [node.lineno, node.col_offset]})
    result = {}
    for index, record in enumerate(records):
        reached, frontier = set(), {index}
        for _ in range(3):
            reached.update(frontier)
            names = frozenset(p for i in reached for p in records[i]['ports'])
            if 1 < len(names) <= 3:
                key = tuple(sorted(names))
                sites = {tuple(records[i]['record_site']) for i in reached}
                result.setdefault(key, set()).update(sites)
            frontier = {j for i in frontier for j, other in enumerate(records)
                        if set(records[i]['ports']) & set(other['ports'])} - reached
            if not frontier:break
    return [{'ports': list(key), 'record_sites': [list(s) for s in sorted(sites)],
             'evidence_kind': 'local record use-def candidate; requires native feedback validation'}
            for key, sites in sorted(result.items(), key=lambda item: (len(item[0]), item[0]))]
