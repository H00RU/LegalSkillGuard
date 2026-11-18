"""Retest the same disclosure readers with shared literal mention coordinates."""

import argparse
import json
import sqlite3

from experiments.convergence_cni_disclosure_probe import POINTER as PRIOR, SOURCE_REVIEWS
from experiments.convergence_maud_clause_probe import run
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_disclosure_relational as disclosure
from legal_skill_guard.paired_interfaces import indexed_relational_read as indexed
from legal_skill_guard.paired_interfaces.cni_disclosure_mentions import with_mentions
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.residual import encode
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

POINTER = HANDOFF / 'cni_disclosure_mentions_current.json'


def prepare():
    previous = ROOT / read(PRIOR)['artifact_root']
    binding = read(previous / 'binding.json')
    old_cases = read(previous / 'cases.json')
    terminal = read(previous / 'terminal.json')
    observations = terminal['observations']
    if (terminal['status'] != 'completed' or len(observations) != 8
            or any(row['correct_projections'] or row['production_errors'] for row in observations)
            or digest(old_cases) != binding['cases_sha256']):
        raise ValueError('Use the actual eight clean, failed paired readings')
    cases, checks = [], []
    for case in old_cases:
        source = case['public_source']
        prior_view = case['view']
        view = with_mentions(prior_view)
        mention_input = view['read_input']['participant_mentions']
        public = view['relational_public_source']
        text = public['source_text']
        for window in mention_input:
            first, last = public['indexed_ranges'][window['id']]
            for mention in window['mentions']:
                start, end = mention['start'], mention['end']
                if not first <= start < end <= last or mention['text'] != text[start:end]:
                    raise ValueError('A reader mention lost its exact public source binding')
        if ({key: value for key, value in view['read_input'].items() if key != 'participant_mentions'}
                != prior_view['read_input']):
            raise ValueError('A participant inventory cannot replace any original public information')
        anchor, group = SOURCE_REVIEWS[source['key'][-8:]]
        state = {'disclosure_actor': 'receiver', 'recipient_group': group, 'permission_force': 'allow'}
        for old, revised in zip(prior_view['plans'], view['plans'], strict=True):
            program = revised['relational_program']
            if (old['schema'] != revised['schema'] or old['relational_program'] != program
                    or old['reader_template_sha256'] == revised['reader_template_sha256']):
                raise ValueError('The repair must isolate the public grounding input and bind a new template')
            unit = program['units'][disclosure.UNIT]
            fields, _ = indexed.encoded_relations(unit['asset'])
            symbols = encode(unit['asset']['features'], state)
            wire = json.dumps('|'.join([anchor, *(indexed.symbol(symbols[key]) for key in fields)]))
            before = decode_response(source, prior_view, old, {'content': wire, 'finish_reason': 'stop'})
            after = decode_response(source, view, revised, {'content': wire, 'finish_reason': 'stop'})
            if before['production_errors'] or after['production_errors'] or before['native'] != after['native']:
                raise ValueError('The reader repair changed the certified consumer or native evidence')
            checks.append({'source_sha256': digest(source), 'plan': revised['name'],
                           'native_projection_equivalent': True, 'source_reference_available': group is not None})
        cases.append({**case, 'view': view})
    sources = set(binding['source_sha256']) | {
        'experiments/convergence_cni_mention_probe.py',
        'legal_skill_guard/paired_interfaces/cni_disclosure_mentions.py',
    }
    updated = {**binding, 'study_id': 'convergence_CNI_employee_disclosure_exact_mentions_v2',
               'source_sha256': {name: sha(ROOT / name) for name in sorted(sources)},
               'cases_sha256': digest(cases), 'prior_terminal_sha256': sha(previous / 'terminal.json'),
               'common_literal_participant_inventory': True,
               'interpretive_and_native_reference_not_in_reader_inputs': True}
    out = BASE / 'cni_disclosure_mention_probe' / digest(updated)
    immutable_json(out / 'binding.json', updated)
    immutable_json(out / 'cases.json', cases)
    immutable_json(out / 'reference_check.json', {'versioned_production_pairs': checks, 'new_requests': 0})
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    write_status(out, {'status': 'prepared', 'reader_cells': len(checks)}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def execute():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('An existing research request must settle first')
    run(POINTER)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else execute)()
