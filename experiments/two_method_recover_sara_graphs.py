"""Recover two paid plans on three already examined TRAIN sources.

References cover service participants only, not whole-case legal truth. These
three sources are permanently dictionary-development evidence, never channel
calibration or structural-holdout evidence. No native answer is read here.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
from itertools import product
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair, learn_dictionary
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/two_method_followthrough_20261116/recovered_service_graphs'
SCHEMA = 'source-grounded-service-participants-v1'

# Root-assistant source annotations of historical, already examined TRAIN.
# "recipient" means the named recipient of the service, not a legal finding
# that a person is an employer under any statute.
ANNOTATIONS = {
    '982d5316': [
        {'quote': 'Alice was paid $200 in 2017 for services performed in a hospital.',
         'worker': 'Alice', 'recipient': None}],
    '250fc5': [
        {'quote': 'Alice was paid $3200 in 2017 for services performed for Johns Hopkins University.',
         'worker': 'Alice', 'recipient': 'Johns Hopkins University'}],
    '6939': [
        {'quote': 'Alice has paid $3200 to Bob for domestic service done from Feb 1st, 2017 to Sep 2nd, 2017.',
         'worker': 'Bob', 'recipient': 'Alice'},
        {'quote': 'Bob has paid $4500 to Alice for work done from Apr 1st, 2017 to Sep 2nd, 2018.',
         'worker': 'Alice', 'recipient': 'Bob'}],
}


def graph_json(graph):
    return {'nodes': list(graph.nodes), 'schema': graph.schema, 'context': graph.context,
            'facts': [{'predicate': f.predicate, 'arguments': list(f.arguments), 'status': f.status}
                      for f in sorted(graph.facts)]}


def reference_graph(facts, annotations):
    names = {value for row in annotations for value in (row['worker'], row['recipient']) if value is not None}
    entity_map, counters, nodes = {}, defaultdict(int), []
    for name in sorted(names, key=facts.index):
        kind = 'organization' if name == 'Johns Hopkins University' else 'person'
        identity = kind + ':' + str(counters[kind])
        counters[kind] += 1
        entity_map[name] = identity
        nodes.append((identity, kind))
    triples, evidence = set(), []
    for index, row in enumerate(annotations):
        start = facts.index(row['quote'])
        event = 'service:' + str(index)
        nodes.append((event, 'service_event'))
        triples.add(Fact('service', (event,)))
        for role in ('worker', 'recipient'):
            value = row[role]
            triples.add(Fact(role, (event, entity_map[value] if value is not None else 'UNSPECIFIED'),
                             'stated' if value is not None else 'not_stated'))
        evidence.append({'event': event, 'field': 'facts', 'start': start,
                         'end': start + len(row['quote']), 'quote': row['quote']})
    return Graph(tuple(nodes), frozenset(triples), SCHEMA, 'service_participants'), entity_map, evidence


def observed_graphs(reference, observations, annotations, entity_map):
    records = observations['service_core']['records']
    if observations['service_core']['status'] != 'complete' or len(records) != len(annotations):
        return [], {'reason': 'The recovered reading does not complete this scoped event set'}
    keys = [r['source_key'] for r in records]
    if len(set(keys)) != len(keys):
        return [], {'reason': 'Duplicate model event anchors; do not manufacture distinct observed identities'}
    choices = []
    for record in records:
        # Alignment uses a source-local kind phrase, never the expected worker
        # or recipient. With one source event the type itself identifies it.
        kind = record.get('kind')
        compatible = [i for i, unit in enumerate(annotations)
                      if isinstance(kind, str) and kind and kind in unit['quote']]
        if len(annotations) == 1:
            compatible = [0]
        choices.append(compatible or list(range(len(annotations))))
    graphs, alignments = set(), []
    for assignment in product(*choices):
        if len(set(assignment)) != len(assignment):
            continue
        triples, nodes = set(), set(reference.nodes)
        for record, index in zip(records, assignment):
            event = 'service:' + str(index)
            triples.add(Fact('service', (event,)))
            for old, role in (('worker', 'worker'), ('employer', 'recipient')):
                value = record.get(old)
                if value is None:
                    identity, status = 'UNSPECIFIED', 'unknown'
                elif value in entity_map:
                    identity, status = entity_map[value], 'stated'
                else:
                    identity, status = 'unmatched:' + digest(value)[:12], 'stated'
                    nodes.add((identity, 'unresolved_entity'))
                triples.add(Fact(role, (event, identity), status))
        graphs.add(Graph(tuple(sorted(nodes)), frozenset(triples), SCHEMA, 'service_participants'))
        alignments.append(list(assignment))
    # Keep node order canonical on both sides; graph equality must not depend
    # on dictionary insertion order or a model's list ordering.
    return sorted(graphs, key=lambda g: digest(graph_json(g))), {'compatible_alignments': alignments,
            'alignment_uses_reference_role_values': False,
            'source_event_anchors_preserved': True, 'multiple_alignments_retained': len(alignments) > 1}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    index = json.loads((ROOT / 'artifacts/two_method_followthrough_20261116/reconciliation/assets.json').read_text())
    public = json.loads((ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json').read_text())
    selected = {s['key']: s for s in public if any(s['key'].split(':')[-1].startswith(k) for k in ANNOTATIONS)}
    assert len(selected) == 3 and all(s['split'] == 'train' for s in selected.values())
    db = sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True)
    times = dict(db.execute("SELECT id,reserved_at FROM calls WHERE status='completed'"))
    db.close()
    available = defaultdict(lambda: defaultdict(list))
    for row in index['raw_read_reconciliation']['physical_records']:
        if row['source'] not in selected or not row['model_revision_bound']:
            continue
        value = json.loads((ROOT / row['logical_artifact']).read_text()).get('value', {})
        if ('service_core' not in value or value['service_core'].get('status') != 'complete'
                or not value['service_core'].get('records')
                or any(not {'worker', 'employer', 'source_key'} <= set(r) for r in value['service_core']['records'])):
            continue
        key, version = row['source'], row['strict_reader_version']
        available[version][key].append(row)
    versions = sorted(v for v, values in available.items() if set(values) == set(selected))[:2]
    if len(versions) != 2:
        raise ValueError('No two complete immutable reader versions cover the three fixed development sources')
    recovered, dictionaries = [], []
    for version in versions:
        pairs = []
        for key, source in selected.items():
            facts = source['views'][0]['public']['facts']
            annotation = next(v for prefix, v in ANNOTATIONS.items() if key.split(':')[-1].startswith(prefix))
            reference, entity_map, evidence = reference_graph(facts, annotation)
            reference = Graph(tuple(sorted(reference.nodes)), reference.facts, reference.schema, reference.context)
            source_rows = sorted(available[version][key], key=lambda r: (times[r['physical_call_id']], r['physical_call_id']))
            for index_in_source, row in enumerate(source_rows):
                value = json.loads((ROOT / row['logical_artifact']).read_text())['value']
                candidates, alignment = observed_graphs(reference, value, annotation, entity_map)
                entry = {'source': key, 'role': 'dictionary_development_only',
                     'source_text_sha256': hashlib.sha256(facts.encode()).hexdigest(),
                     'reference_graph': graph_json(reference), 'source_evidence': evidence,
                     'observed_graph_alternatives': [graph_json(g) for g in candidates],
                     'reader_version': version, 'physical_call': row, 'alignment': alignment,
                     'reference_scope': ['service existence', 'service performer', 'named service recipient'],
                     'not_whole_case_gold': True, 'native_label_used': False,
                     'reference_checked_by': 'root assistant against complete public TRAIN facts',
                     'independent_annotation_claimed': False,
                     'original_nonrole_values_and_failures_preserved': row['logical_artifact'],
                     'earliest_representative_for_source_and_plan': index_in_source == 0}
                recovered.append(entry)
                if candidates:
                    pairs.append(Pair(key, reference, frozenset(candidates), version, 'development',
                                      str(OUT / 'source_checked_pairs.json') + ': source spans above'))
        dictionary = learn_dictionary(pairs)
        dictionaries.append({'version': version, 'development_sources': sorted(dictionary['development_sources']),
            'unmatched_sources': dictionary['unmatched_development_sources'],
            'edits': [{'id': edit.identity, 'variables': list(edit.variables), 'all_matches': edit.all_matches,
                       'before': [{'predicate': f.predicate, 'arguments': list(f.arguments), 'status': f.status} for f in edit.before],
                       'after': [{'predicate': f.predicate, 'arguments': list(f.arguments), 'status': f.status} for f in edit.after]}
                      for edit in dictionary['edits']]})
    report = {'pairs': recovered, 'dictionaries': dictionaries,
              'sources': sorted(selected), 'two_plan_versions': versions,
              'complete_scoped_pairs': sum(len(r['observed_graph_alternatives']) == 1 for r in recovered),
              'earliest_representative_pairs': sum(r['earliest_representative_for_source_and_plan'] for r in recovered),
              'new_model_calls': 0, 'channel_fitted': False,
              'pilot_or_transfer_efficacy_claimed': False,
              'must_exclude_from_future_channel_calibration_and_structural_holdout': sorted(selected)}
    (OUT / 'source_checked_pairs.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'source_mothers': len(selected), 'reader_versions': len(versions),
                      'complete_scoped_pairs': report['complete_scoped_pairs'],
                      'learned_edit_counts': [len(d['edits']) for d in dictionaries],
                      'channel_fitted': False, 'new_model_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
