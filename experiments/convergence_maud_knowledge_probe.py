"""Matched M1 comparison on all four locked MAUD Knowledge Definition tasks."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from experiments.convergence_maud_clause_probe import BASE, HANDOFF, ROOT, read, run
from legal_skill_guard.paired_interfaces import maud_knowledge_relational as knowledge
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.residual import encode
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

POINTER = HANDOFF / 'maud_knowledge_probe_current.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_native_chain(source, view, plan, quote):
    unit = 'operative_knowledge_definition'
    fields = {'qualification_target': 'target_definition', 'inquiry_effect': 'required',
              'explicit_actual_restriction': None}
    features = plan['relational_program']['units'][unit]['asset']['features']
    raw = {unit: {'status': 'complete', 'evidence': [{'field': 'source_text', 'quote': quote}],
                  'observation': {'source_anchor': unit, 'relations': encode(features, fields)}}}
    result = decode_response(source, view, plan, {'content': json.dumps(raw), 'finish_reason': 'stop'})
    if result['production_errors']:
        raise ValueError('Knowledge reference failed production decode')
    return result['native'][knowledge.TASK]['answer']


def prepare():
    b0 = ROOT / read(HANDOFF / 'pilot_b0_current.json')['artifact_root']
    if not (b0 / 'terminal.json').exists():
        raise ValueError('The fixed pilot baseline must settle before deriving this repair')
    locked = read(b0 / 'public_TRAIN_pilot.json')
    normalized = ROOT / read(HANDOFF / 'normalized_inputs_current.json')['artifact_root']
    grading = normalized / 'train/CNI_MAUD_grading_only.json'
    golds = read(grading)
    cases = []
    reference_rows = []
    for source in (row for row in locked if row['dataset'] == 'MAUD'):
        selected, view = knowledge.build(source)
        public = selected['views'][0]['public']['source_text']
        # These four audited TRAIN excerpts contain explicit operative inquiry.
        # Verify the public phrase first, then score independently using native
        # labels. A missing phrase is an audit failure, never source exclusion.
        audit = re.search(r'after\s+reasonable\s+inquiry', public, re.I)
        if not audit:
            raise ValueError('A previously identified TRAIN inquiry anchor is no longer present')
        quote = audit.group()
        answer = [check_native_chain(selected, view, plan, quote) for plan in view['plans']]
        gold = golds[source['key']][knowledge.TASK]['answer']
        if answer != [gold] * len(answer):
            raise ValueError('The preserved source reference disagrees with the native scoring chain')
        reference_rows.append({'source': source['key'], 'inquiry_quote_sha256': hashlib.sha256(quote.encode()).hexdigest(),
                               'reference_matches': len(answer), 'gold_used_in_reader': False})
        cases.append({'public_source': selected, 'view': view, 'expected_local_projection': {knowledge.TASK: gold}})
    if len(cases) != 4:
        raise ValueError('The four fixed MAUD mothers must all participate')
    paths = [
        'experiments/convergence_maud_knowledge_probe.py',
        'experiments/convergence_maud_clause_probe.py',
        'legal_skill_guard/paired_interfaces/maud_knowledge_relational.py',
        'legal_skill_guard/paired_interfaces/relational_program.py',
        'legal_skill_guard/paired_interfaces/residual.py',
        'legal_skill_guard/paired_interfaces/formal_actors.py',
        'legal_skill_guard/paired_interfaces/production_decode.py',
        'legal_skill_guard/skill_evolution/clients.py',
        'legal_skill_guard/skill_evolution/ledger.py',
        'legal_skill_guard/rr/client.py',
    ]
    binding = {
        'study_id': 'convergence_MAUD_knowledge_native_01',
        'source_sha256': {name: sha(ROOT / name) for name in paths},
        'source_gold_sha256': sha(grading), 'B0_result_sha256': sha(b0 / 'terminal.json'),
        'cases_sha256': digest(cases),
        'executor': read(HANDOFF / 'executor_readiness.json')['executor_config'],
        'full_native_question_scored': True,
        'scope': 'entire native knowledge-definition task, separate from other MAUD tasks',
    }
    out = BASE / 'maud_knowledge_probe' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'cases.json', cases)
    immutable_json(out / 'reference_check.json', reference_rows)
    state = {'artifact_root': str(out.relative_to(ROOT)), 'status': 'prepared', 'reader_cells': len(cases) * 2}
    POINTER.write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps(state), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    args = parser.parse_args()
    prepare() if args.phase == 'prepare' else run(POINTER)
