"""One blind public-law initializer; comparisons live in the online main loop.

No cases/answers/trajectories, no 8B generation, no independent eval queue.
Historical drivers and cancelled controls remain in Git and dual archives.
"""
from __future__ import annotations

import argparse
import json
import signal
import traceback
from pathlib import Path

from experiments.openexempt_online import (
    ACTOR_SYSTEM,
    EXECUTABLE_GUIDANCE,
    PROGRAM_ACTOR_SYSTEM,
    Online,
    preserve,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.claim_execution import (
    answer_schema,
    execute_limit,
    law_blocks,
    operator_catalog,
)
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.publication import skill_record_schema
from legal_skill_guard.openexempt import FAMILIES, ROOT
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

STATIC_SYSTEM = (
    "Compile a strong, compact STATIC law-only skill library for frozen Qwen3-8B. "
    "You receive complete public benchmark statutes, generic task instructions and the "
    "ACTUAL actor interface only. No cases, training answers, actor trajectories, "
    "future observations or execution scores are supplied. Do not invent them. "
    "Prepare operational legal classification guidance and reusable EV ceiling operators "
    "that can be used before any experience. Historical skills are fallible, so state "
    "applicability and exceptions clearly. Do not force skill count/types. Cover the "
    "supplied jurisdictions, allowed-law boundaries, residual/specific exemptions, "
    "item versus aggregate caps and spouse rules as supported by the text. Operators "
    "are {id,citation,limit_expression}; keep only ONE active routine per citation "
    "in the entire bank. Internal IDs are provenance, not model-facing choices. "
    "A native null limit_expression calls that same citation's routine; a string "
    "is inline arithmetic. Combine N-dependent variants in one expression, or leave "
    "an uncommon variant to explicitly instructed inline calculation. "
    "Use ASCII skill/operator IDs, original citation strings, variables V (asset value) "
    "and N (public debtor count), finite numeric literals, min/max, +,-,*,/, and "
    "X if N==2 else Y; unlimited explicitly denotes no ceiling. Amounts spelled in "
    "English may be converted to normal numbers. The runtime executes arithmetic, "
    "NOT legal truth; do not rely on it to select eligibility or validate a ceiling. "
    "Both empty and skill actors can write identical inline arithmetic. Guidance "
    "has when/procedure/avoid_when/operators; scope keys are EC and/or EV. Operators "
    "require EV scope. Do not store format-example entities, vehicles, dollar answers, "
    "case IDs, answer tables or invented success claims. Statutory values are allowed. "
    "The complete library hard cap is4096 Qwen3-8B tokens, aim2500. This is one blind "
    "teacher compilation, no outcome-based retries, no tools or external information. "
    "Return only the requested bank JSON."
)


class Control:
    check = Online.check
    progress = Online.progress
    teacher_call = Online.teacher_call

    def __init__(self, config_path, action):
        self.cfg = read(config_path)
        frozen = read(config_path.with_suffix('.frozen.json'))
        if frozen['config_sha256'] != sha(config_path):
            raise ValueError('Frozen control config mismatch')
        self.bindings = {**frozen['files'], self.cfg['driver_path']: self.cfg['driver_sha256']}
        self.run_id = self.cfg['run_id'] + '_' + action
        self.out = ROOT/'runs'/self.run_id
        self.out.mkdir()  # Never overwrite a previous study.
        self.rows = read(ROOT/self.cfg['input_packet'])['rows']
        self.bank, self.native, self.teachers = [], [], []
        self.current_batch, self.teacher_attempts, self.stop = 0, 0, False
        self.meter = WireClient(self.cfg['generation'])
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, 'stop', True))
        self.check()

    def build(self):
        # Public law and generic contracts only; never serialize an entire row.
        original = self.rows[0]['components']['statutes']
        body = {'complete_public_statutes': original,
                'task_boundary': {'start_task_id': 2,
                    'given_public_prior': 'allowable jurisdictions already supplied; do not recompute',
                    'outputs': 'enumerate all eligible asset-law alternatives, not a final elected portfolio',
                    'EV': 'single asset-citation pairs independently, not aggregate allocation across assets'},
                'generic_contracts': {f: {k: next(r for r in self.rows if r['family'] == f)
                    ['components'][k] for k in ('instruction', 'meta_instruction')}
                    for f in FAMILIES},
                'actual_actor_systems': {'EC': ACTOR_SYSTEM, 'EV': PROGRAM_ACTOR_SYSTEM},
                'EV_empty_response_schema': answer_schema([]),
                'no_cases_targets_trajectories_or_future_feedback': True}
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['bank'],
                  'properties': {'bank': {'type': 'array', 'items': skill_record_schema(
                      FAMILIES, guidance_schema=EXECUTABLE_GUIDANCE)}}}
        self.bank = self.teacher_call('blind_static_compilation', STATIC_SYSTEM, body, schema)['bank']
        if len({s['id'] for s in self.bank}) != len(self.bank):
            raise ValueError('Duplicate static skill IDs')
        for skill in self.bank:
            if len(set(skill['hypothesis_ids'])) != len(skill['hypothesis_ids']):
                raise ValueError('Duplicate static scope')
            if skill['guidance']['operators'] and 'EV' not in skill['hypothesis_ids']:
                raise ValueError('EV operator needs EV scope')
        for operator in operator_catalog(self.bank).values():
            if operator['citation'] not in law_blocks(original):
                raise ValueError('Static operator citation absent from original public text')
            for marker in ('Debtor', 'Debtors'):
                execute_limit(operator['limit_expression'], f'X (hereinafter the {marker})')
        tokens = self.meter.token_count(text=json.dumps(self.bank, ensure_ascii=False,
                                                       separators=(',', ':')))
        if tokens > self.cfg['library_token_hard_cap']:
            raise ValueError(f'Complete static bank exceeds cap: {tokens}; no trimming/reroll')
        RunStore.immutable_json(self.out/'publication.json', {
            'at': now(), 'bank': self.bank, 'bank_sha256': csha(self.bank), 'tokens': tokens,
            'training_cases_seen': 0, 'teacher_responses': len(self.teachers),
            'teacher_attempts': self.teacher_attempts, 'native_generations': len(self.native),
            'no_cases_targets_trajectories_or_scores': True,
            'not_training_cost_matched_to_online_method': True})
        return {'status': 'blind_static_bank_compiled', 'tokens': tokens}

    def run(self):
        status = 'failed'
        try:
            result = self.build()
            status = result['status']
            RunStore.immutable_json(self.out/'completion.json', {
                'at': now(), **result, 'actual_native_calls': len(self.native),
                'actual_teacher_responses': len(self.teachers),
                'actual_teacher_attempts': self.teacher_attempts})
        except Exception as exc:
            RunStore.immutable_json(self.out/'failure.json', {
                'at': now(), 'error': repr(exc), 'traceback': traceback.format_exc(),
                'actual_native_calls': len(self.native), 'actual_teacher_responses': len(self.teachers),
                'actual_teacher_attempts': self.teacher_attempts})
            raise
        finally:
            self.progress('terminal', state=status)
            files = [str(p.relative_to(ROOT)) for p in self.out.rglob('*')
                     if p.is_file() and '/cache/' not in str(p)]
            receipt = preserve(self.run_id, 'actual-terminal', files)
            RunStore.immutable_json(self.out/'terminal_preservation.json', receipt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('build',))
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    Control(args.config.resolve(), args.action).run()


if __name__ == '__main__':
    main()
