"""One shared factual read isolates a real missing-event grounding channel.

This is a controlled diagnostic on an existing development mother, not another
benchmark score or an independent strong-method evaluation. Each consumer gets
the same actual read; its remaining errors/uncertainties are kept unchanged.
"""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_temporal_contract_learning as study
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import checked_witnesses, execute_alternatives, kernel_execution
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import render_messages, decoder_schema


ROOT = study.ROOT
RUN = 'legal_skill_evolution_missing_event_read_20261114'
OUT = ROOT / 'artifacts' / RUN
SYSTEM = '''Read only the supplied current CASE FACTS, not the target statute or
its answer. Search the complete provided case text for a stated legal-separation
decree (divorce or separate maintenance). Return status=records only for actually
stated events and copy their factual details. Return status=none_stated when you
have read the finite current text and it contains no such statement; this means
textual absence only, not a real-world negative. Return unread if extraction is
unknown or failed. For none_stated/unread the value is null. Quote the actual
current case facts as the witness; do not invent a decree, missing end date or
legal conclusion. Return only factual JSON. No native answer labels.
'''


def main():
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = study.read(study.OUT / 'protocol.json')
        old_rows = study.read(study.OUT / 'scored_results.json')['rows']
        sid = next(s for s in p['learning_sources'] if s.split(':')[1].startswith('8175fcb9'))
        cases = study.read(study.direct.OUT / 'fixed_development_cases.json')
        pub = next(c['source']['views'][0]['public'] for c in cases if c['source']['key'] == sid)
        kernel = next(k for k in study.read(study.OUT / 'kernel_bank.json') if k['name'] == 'separate_return_itemization_gate')
        fields = json.loads(kernel['input_fields_json'])
        value_schema = study.direct.port_schema(fields['legal_separation_decrees'])
        value_schema['type'] = 'array'
        witness = {'type': 'array', 'items': record_schema({'field': {'type': 'string', 'enum': ['facts']}, 'quote': {'type': 'string'}})}
        schema = {'oneOf': [record_schema({'status': {'type': 'string', 'enum': [status]},
            'value': value_schema if status == 'records' else {'type': 'null'}, 'witnesses': witness})
            for status in ('records', 'none_stated', 'unread')]}
        jsonschema.Draft202012Validator.check_schema(schema)
        before = study.base.old.rows()
        assert not any(r[6] == 'reserved' for r in before)
        if not (OUT / 'protocol.json').exists():
            immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
            immutable_json(OUT / 'protocol.json', {'run_id': RUN, 'source': sid,
                'purpose': 'One shared source-text presence read; no forced favorable factual value',
                'same_read_to_all_three_consumers': True, 'full_method_comparison': False,
                'schema': schema, 'system': SYSTEM, 'facts_sha256': digest(pub['facts']),
                'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'no_TEST_or_future_mother_used': True, 'executor_profile': p['executor_profile']})
        bound = study.read(OUT / 'protocol.json')
        assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == bound['source_sha256']
        ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
            sources={'train': [sid], 'dev': [], 'test': []}, binding=digest(bound))
        response = FrozenExecutor(ledger, OUT, p['executor_profile']).generate(RUN + ':source_presence',
            source=sid, purpose='skill_actor', messages=render_messages(SYSTEM, {'facts': pub['facts']}, schema),
            thinking=False, schema=decoder_schema(schema)[0])
        assert response['finish_reason'] == 'stop'
        observed = json.loads(response['content']); jsonschema.validate(observed, schema)
        immutable_json(OUT / 'observation.json', observed)
        if observed['status'] != 'unread':
            checked_witnesses(observed['witnesses'], pub)
        results = []
        for arm in (*study.ARMS, 'DirectRead'):
            old = next(r for r in old_rows if r['source'] == sid and r['arm'] == arm)
            row = {'arm': arm, 'before_execution': old['execution'], 'original_observation': old['observation']}
            value = deepcopy(old['observation'])
            if observed['status'] == 'none_stated':
                if arm == 'ProgramGuided':
                    # The existing learned adapter already maps this exact
                    # factual channel to legal_separation_decrees. Empty-set
                    # projection changes no event semantics or other channel.
                    for view in value['views']:
                        view['decree_facts'] = []
                        view['witnesses'].extend(observed['witnesses'])
                elif arm == 'FreeHistory':
                    value['decree_evidence'] = []
                    value['decree_resolution'] = 'resolved'
                    value['witnesses'].extend(observed['witnesses'])
                else:
                    value['inputs']['legal_separation_decrees'] = []
                    value['witnesses'].extend(observed['witnesses'])
                if arm in study.ARMS:
                    contract = next(c for c in study.read(study.OUT / arm / 'teacher.json')['value']['contracts'] if c['kernel_name'] == kernel['name'])
                    grounded = study.apply(contract, kernel, pub, value)
                    row['grounded_after_same_read'] = grounded
                    row['after_execution'] = execute_alternatives(kernel, grounded)
                else:
                    row['after_execution'] = kernel_execution(kernel, {k: v for k, v in value['inputs'].items() if v is not None})
            else:
                # No special record-to-source-view transform is supplied here;
                # preserve unknown/nonempty observations without manufacturing
                # the empty case that this diagnostic is intended to inspect.
                row['after_execution'] = old['execution']
                row['diagnostic_update_not_applicable'] = True
            row['new_observation'] = observed
            results.append(row)
        immutable_json(OUT / 'result.json', {'source': sid, 'rows': results,
            'one_physical_read_shared_not_three_independent_model_results': True,
            'opaque_unresolved_checks_unchanged': True, 'original_frozen_results_not_replaced': True,
            'not_an_independent_contribution_or_full_method_comparison': True,
            'goal_complete': False})
        print(json.dumps({'observed': observed['status'], 'answers': {
            r['arm']: r['after_execution']['answer'] for r in results}}), flush=True)


if __name__ == '__main__':
    main()
