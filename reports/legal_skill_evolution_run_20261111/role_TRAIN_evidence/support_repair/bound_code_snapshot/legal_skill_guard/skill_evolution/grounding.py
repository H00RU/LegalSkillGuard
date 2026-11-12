"""Bind observed whitespace/separator transcription errors to exact source."""
from copy import deepcopy
import re

from .native import public_strings


def normalized_with_positions(text):
    output, positions = [], []
    for match in re.finditer(r'\s+|\S', text):
        token, start, end = match.group(), match.start(), match.end()
        if token.isspace():
            if output:output.append(' ');positions.append((start, end))
        else:
            # The observed failure is paid— (A) versus paid-\n (A).
            # Do not fold numeric ranges, minus signs or arbitrary punctuation.
            if (token in '-–—' and start > 0 and text[start - 1].isalpha()
                    and re.match(r'\s+\(', text[end:])):
                token = '-'
            output.append(token);positions.append((start, end))
    if output and output[-1] == ' ':output.pop();positions.pop()
    return ''.join(output), positions


def bind_transcribed_quotes(value, sources):
    """Only change origin.quote when one exact source substring is determined.

    Word/number edits, ellipses, summaries, unknown sources and ambiguous
    source spellings do not recover. Procedures, ports and legal values are
    never edited. The existing literal-grounding check still runs afterwards.
    """
    result, receipts = deepcopy(value), []

    def visit(node, path):
        if isinstance(node, dict):
            if set(node) == {'source_id', 'view_id', 'quote'} and isinstance(node['quote'], str):
                source = sources.get(node['source_id'])
                view = next((v for v in source['views'] if v['id'] == node['view_id']), None) if source else None
                texts = public_strings(view['public']) if view else []
                quote = node['quote']
                if not quote or any(quote in text for text in texts):return
                target, _ = normalized_with_positions(quote)
                if not target:return
                matches = {}
                for index, text in enumerate(texts):
                    normalized, positions = normalized_with_positions(text)
                    start = 0
                    while (start := normalized.find(target, start)) >= 0:
                        left, right = positions[start][0], positions[start + len(target) - 1][1]
                        literal = text[left:right]
                        matches.setdefault(literal, []).append({'public_string_index': index, 'start': left, 'end': right})
                        start += 1
                if len(matches) == 1:
                    literal, locations = next(iter(matches.items()))
                    node['quote'] = literal
                    receipts.append({'path': path, 'original_quote': quote, 'exact_source_quote': literal,
                        'source_id': node['source_id'], 'view_id': node['view_id'], 'locations': locations,
                        'adaptation': 'whitespace and observed letter-dash-before-parenthesis typography only'})
                return
            for key, child in node.items():visit(child, path + '.' + key)
        elif isinstance(node, list):
            for i, child in enumerate(node):visit(child, path + '[' + str(i) + ']')
    visit(result, 'skill')
    return result, receipts
