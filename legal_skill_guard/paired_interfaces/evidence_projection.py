"""Project read evidence without importing training or model actors."""
import re


def source_evidence(result, graph, identities, units, public):
    """Project the actual read's used quotes to supplied CNI sentence IDs."""
    if 'sentence_spans' not in public:
        return []
    by_id, by_unit = {identities[n['id']]: n for n in graph['nodes']}, {u['id']: u for u in units}
    spans = []
    for identity in result.get('used_nodes', []):
        node = by_id.get(identity)
        if node is None:
            continue
        unit = by_unit[node['unit_id']]
        positions = [m.start() for m in re.finditer(re.escape(node['quote']), unit['text'])]
        if unit['field'] == 'source_text' and len(positions) == 1:
            start = unit['start'] + positions[0]
            spans.append((start, start + len(node['quote'])))
    return sorted({i for i, (a, b) in enumerate(public['sentence_spans'])
                   if any(start < b and end > a for start, end in spans)})
