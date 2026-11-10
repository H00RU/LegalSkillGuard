"""One conservative adjunct view for a punctuation-root parser failure.

The removed source span is retained verbatim as an unresolved qualification.
This is common preprocessing, not a learned law or a new benchmark example.
"""
from pathlib import Path
import hashlib
import json
import sys

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.predicate_norm_learning import action
from legal_skill_guard.rr import predicate_norm_learning


def views(raw):
    out, trace = [], []
    for u in raw['results']:
        ts = u['tokens'];candidates = []
        for modal in ts:
            if modal['tag'] != 'MD' or ts[modal['head']]['pos'] != 'PUNCT':continue
            next_modal = next((t['i'] for t in ts if t['i'] > modal['i'] and t['tag'] == 'MD'), len(ts))
            conduct = [t for t in ts if modal['i'] < t['i'] < next_modal and action(t['text']) is not None]
            if len(conduct) != 1:continue
            target = conduct[0]
            commas = [t for t in ts if modal['i'] < t['i'] < target['i'] and t['text'] == ',']
            if len(commas) < 2 or commas[0]['i'] != modal['i'] + 1:continue
            first, last = commas[0], commas[-1]
            intro = ts[first['i'] + 1]['text'].casefold()
            if intro not in {'upon', 'if', 'when', 'after', 'before', 'unless', 'notwithstanding'}:continue
            start = last['end']
            while start < len(u['text']) and u['text'][start].isspace():start += 1
            prefix = u['text'][:first['start']]
            text = prefix + ' ' + u['text'][start:]
            removed = u['text'][first['end']:last['start']].strip()
            candidates.append({'key': u['key'], 'source': u['source'], 'text': text, 'focus': text,
                'original_text': u['text'], 'original_focus': u['focus'],
                'segments': [{'view_start': 0, 'view_end': len(prefix), 'original_start': 0},
                             {'view_start': len(prefix) + 1, 'view_end': len(text), 'original_start': start}],
                'unparsed_source_qualification': removed,
                'basis': 'Auxiliary attached to punctuation, immediately following comma adjunct, exactly one public conduct before next modal',
                'no_normative_operator_or_missing_role_supplied': True})
        if len(candidates) == 1:out.append(candidates[0])
        trace.append({'key': u['key'], 'candidate_views': len(candidates),
                      'accepted_for_common_reparse': len(candidates) == 1})
    return {'units': out, 'trace': trace, 'not_new_sources_or_native_examples': True,
            'removed_conditions_not_discarded_or_assumed_true': True}


def main():
    source, output = map(Path, sys.argv[1:3])
    raw = json.loads(source.read_text());value = views(raw)
    value['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    value['script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    value['action_routing_module_sha256'] = hashlib.sha256(Path(predicate_norm_learning.__file__).read_bytes()).hexdigest()
    immutable_json(output, value)
    print(json.dumps({'source_views': len(value['units']), 'trace': value['trace'], 'new_executor_teacher_calls': 0}))


if __name__ == '__main__':
    main()
