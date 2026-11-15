"""Transport a colon-headed enumerated list as one existing source scope.

Only syntactic child markers are inspected. No legal action, trigger, party or
answer is assigned. Original unit IDs and complete child text are preserved.
The same pure function can be embedded in an acquired source program.
"""
import re


def shared_list_group(valid, index):
    uid, text = valid[index]
    group = text
    support = [uid]
    skip = 0
    if text.rstrip().endswith(':'):
        j = index + 1
        while j < len(valid):
            child_id, child = valid[j]
            if not re.match(r'^\s*(?:\([a-z0-9]+\)|\d+(?:\.\d+)+(?:\.)?)\s+', child.lower()):
                break
            group += ' ' + child
            support.append(child_id)
            skip += 1
            j += 1
    return [group, support, skip]
