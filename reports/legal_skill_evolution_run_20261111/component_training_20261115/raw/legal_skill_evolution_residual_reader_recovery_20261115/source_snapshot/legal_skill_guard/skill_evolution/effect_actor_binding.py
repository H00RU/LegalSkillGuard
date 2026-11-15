"""Source-literal actor inputs owned by individual legal effects.

This shared bridge fixes a representation constraint; it is not a learned skill
or a certificate that an extracted phrase has the intended legal meaning.
"""
from .source_python import execute
from .source_term_interface import validate_value


EFFECTS = {'disposal_obligation', 'retention_permission', 'retention_prohibition'}


def bind(spec, queries, units, observations):
    """Keep literal actor observations tied to their actual query and source unit."""
    windows = {q['id']: q['unit_ids'] for q in queries}
    texts = {u['id']: u['text'] for u in units}
    bindings = {}
    for row in observations:
        qid, effect = row['query_id'], row['effect']
        if qid not in windows or not qid.endswith('_role') or effect not in EFFECTS:
            raise ValueError('Unknown current effect/query binding')
        prefix = qid[:-len('role')]
        group = bindings.setdefault(prefix, {})
        if effect in group:
            raise ValueError('Duplicate actor observation for one effect')
        uid, phrase = row['unit_id'], row['phrase']
        if uid not in windows[qid] or uid not in texts:
            raise ValueError('Actor evidence outside the actual query window')
        if not isinstance(phrase, str) or (phrase and phrase not in texts[uid]):
            raise ValueError('Actor phrase is not verbatim current-source evidence')
        # Empty observations remain unknown. Another effect's actor is never used.
        group[effect] = (validate_value(spec, 'Participant', ['named_recipient', phrase])
                         if phrase else None)
    return bindings


def finish(bundle, text, units, answers, observations):
    planned = execute(bundle['program'], {'phase': 'plan', 'source_text': text,
                                        'source_spans': units, 'semantic_answers': []})
    bindings = bind(bundle['spec'], planned['queries'], units, observations)
    return execute(bundle['program'], {'phase': 'finish', 'source_text': text,
                                      'source_spans': units, 'semantic_answers': answers,
                                      'effect_actor_bindings': bindings})
