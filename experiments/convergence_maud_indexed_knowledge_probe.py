"""Matched transport revision after the MAUD Knowledge Definition comparison."""

import argparse
import json
import re
import sqlite3

from experiments.convergence_maud_clause_probe import BASE, HANDOFF, LEDGER, ROOT, read, sha, run
from experiments.convergence_maud_knowledge_probe import POINTER as QUOTE_PROBE
from legal_skill_guard.paired_interfaces import indexed_relational_read as indexed
from legal_skill_guard.paired_interfaces import maud_knowledge_relational as knowledge
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.residual import encode
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

POINTER = HANDOFF / 'maud_indexed_knowledge_probe_current.json'
RECOVERY = HANDOFF / 'maud_factorized_knowledge_recovery_current.json'


def recoverable_sources():
    state = read(POINTER)
    previous = ROOT / state['artifact_root']
    binding = read(previous / 'binding.json')
    if state['status'] != 'interrupted_or_failed' or not (previous / 'source_snapshot').is_dir():
        raise ValueError('Recovery requires a settled and archived transport failure')
    cases = read(previous / 'cases.json')
    if digest(cases) != binding['cases_sha256']:
        raise ValueError('The original indexed input binding changed')
    reads = [read(path) for path in (previous / 'comparison_rows').glob('*.json')]
    done = {source for source in {row['source'] for row in reads}
            if len({row['plan'] for row in reads if row['source'] == source}) == 2}
    remaining = [case for case in cases if case['public_source']['key'] not in done]
    if len(remaining) != 1 or len(reads) != 6:
        raise ValueError('Only the uncompleted source pair can be recovered')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        failed = db.execute(
            "select source,status,result from calls where id like ? and status='failed'",
            ('convergence-maud-clause-' + digest(binding)[:16] + ':%',)).fetchall()
        observed = [db.execute("select source,status from calls where id=?", (row['physical_call_id'],)).fetchone()
                    for row in reads]
    if (len(failed) != 1 or failed[0][0] != remaining[0]['public_source']['key']
            or 'TimeoutError' not in failed[0][2]
            or any(record != (row['source'], 'completed') for record, row in zip(observed, reads))):
        raise ValueError('The ledger does not support a transport-only recovery')
    return remaining[0]['public_source']['key'], {
        'prior_scalar_binding_sha256': digest(binding),
        'reused_complete_source_pairs': len(done),
        'retained_physical_response_ids': sorted(row['physical_call_id'] for row in reads),
        'recovery_changes_output_language': False,
    }


def prepare(*, complete_remaining=False):
    prior = ROOT / read(QUOTE_PROBE)['artifact_root']
    if not (prior / 'terminal.json').exists():
        raise ValueError('Preserve the settled quote-based comparison before preparing new wires')
    previous = read(prior / 'binding.json')
    cases = read(prior / 'cases.json')
    if digest(cases) != previous['cases_sha256'] or len(cases) != 4:
        raise ValueError('The locked MAUD cohort changed')
    recovery = {}
    pointer = POINTER
    if complete_remaining:
        source, recovery = recoverable_sources()
        cases = [case for case in cases if case['public_source']['key'] == source]
        pointer = RECOVERY
    references = []
    for case in cases:
        source = case['public_source']
        view = case['view'] = indexed.reformat(case['view'], factorized=complete_remaining)
        text = view['relational_public_source']['source_text']
        for plan in view['plans']:
            program = plan['relational_program']
            binding = plan['indexed_evidence_binding']
            # Independent TRAIN evidence is for the reference check only.
            span = next(anchor for anchor, (start, end) in binding['spans'].items()
                        if re.search(r'after\s+reasonable\s+inquiry', text[start:end], re.I))
            _, unit = indexed.indexed_unit(program)
            fields, _ = indexed.encoded_relations(unit['asset'])
            supported = encode(unit['asset']['features'], {
                'qualification_target': 'target_definition', 'inquiry_effect': 'required',
                'explicit_actual_restriction': None,
            })
            code = '|'.join([span, *(indexed.symbol(supported[name]) for name in fields)])
            response = {'content': json.dumps(code), 'finish_reason': 'stop'}
            result = decode_response(source, view, plan, response)
            answer = result['native'][knowledge.TASK]['answer']
            if result['production_errors'] or answer != case['expected_local_projection'][knowledge.TASK]:
                raise ValueError('Indexed reference did not preserve the exact native consumer')
            references.append({'source': source['key'], 'plan': plan['name'],
                               'indexed_reference_decodes': True, 'gold_used_in_reader': False})
    paths = set(previous['source_sha256']) | {
        'experiments/convergence_maud_indexed_knowledge_probe.py',
        'legal_skill_guard/paired_interfaces/indexed_relational_read.py',
    }
    binding = {
        **previous,
        'study_id': ('convergence_MAUD_knowledge_factorized_timeout_recovery' if complete_remaining
                     else 'convergence_MAUD_knowledge_indexed_native_01'),
        'source_sha256': {name: sha(ROOT / name) for name in sorted(paths)},
        'cases_sha256': digest(cases), 'quote_based_result_sha256': sha(prior / 'terminal.json'),
        'same_transport_repair_in_fixed_and_synthesized_arms': True,
        'source_partition_uses_native_label_or_audit_answer': False,
        **recovery,
    }
    family = 'maud_factorized_knowledge_recovery' if complete_remaining else 'maud_indexed_knowledge_probe'
    out = BASE / family / digest(binding)
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0, 'reused_terminal': True}), flush=True)
        return
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'cases.json', cases)
    immutable_json(out / 'reference_check.json', references)
    state = {'artifact_root': str(out.relative_to(ROOT)), 'status': 'prepared', 'reader_cells': len(references)}
    temporary = pointer.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.replace(pointer)
    print(json.dumps(state), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    parser.add_argument('--complete-remaining', action='store_true')
    args = parser.parse_args()
    if args.phase == 'prepare':
        prepare(complete_remaining=args.complete_remaining)
    else:
        run(RECOVERY if args.complete_remaining else POINTER)
