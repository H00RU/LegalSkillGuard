"""Run real acquired compiler examples and shared-asset ablations, zero calls.

The separate candidate acquisition timed out. Do not relabel the successful
free-control proposal as a fresh independent method proposal. This isolates
compiler learning/execution from a shared actual acquisition only.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.span_compiler import (compile_grounded_examples,
    learn_grammar, grammar_cost)
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot
from experiments.legal_skill_evolution_span_compiler import read, warm_base, evaluate_source


def run(root):
    original = root / 'artifacts/legal_skill_evolution_span_compiler_20261112'
    folder = root / 'artifacts/legal_skill_evolution_span_compiler_offline_v2_20261112'
    folder.mkdir(exist_ok=True)
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    old = read(original / 'protocol.json')
    proposal = original / 'FreeStrongControl/teacher.json';spec = read(proposal)['value']
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution*.py'))
    paths += [Path(__file__).resolve(), root / 'experiments/legal_skill_evolution_span_compiler.py']
    protocol = {'same_goal': True, 'goal_complete': False,
        'comparison_type': 'Shared actual FreeStrongControl acquisition; not an independent method-vs-control acquisition comparison.',
        'acquisition_protocol_hash': digest(old), 'proposal_sha256': hashlib.sha256(proposal.read_bytes()).hexdigest(),
        'teacher_sources': old['teacher_sources'], 'history': old['history'], 'trigger': old['trigger'],
        'frozen_TRAIN_probes': old['frozen_TRAIN_probes'],
        'repair': 'Use unique joint nonoverlap and reject ambiguous examples. Raw slots retain demonstrated source forms, so actor capture cannot cross paragraphs and condition capture cannot swallow a role-list suffix. Scope phrases remain protected and gaps cannot introduce protected operators. The acquired semantic procedure is unchanged.',
        'source_and_slot_words_case_punctuation_unchanged': True,
        'new_model_calls': 0, 'regressions_passed': 136,
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
    immutable_json(folder / 'protocol.json', protocol)
    ledger = root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    before = physical_snapshot(ledger)
    if any(x.get('reserved', 0) for x in before.values()):raise ValueError('Physical model call still pending')
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    materials = {k: public[k]['views'][0]['public']['source_text'] for k in old['teacher_sources']}
    seeds, rejected = compile_grounded_examples(spec, materials)
    immutable_json(folder / 'grounding_receipt.json', {'initial_annotations': len(spec['seeds']),
        'grounded_productions': len(seeds), 'rejected': rejected, 'learned_rules': seeds})
    base = warm_base(root, old);cache = {};source_cache = {}
    def source_result(rules, key):
        identity = digest({'rules': rules, 'source': key})
        if identity not in source_cache:
            source_cache[identity] = evaluate_source(spec, rules, public[key], grading[key], base[key], None, cache)
        return source_cache[identity]
    def score(rules):return {k: source_result(rules, k)['native_grade'] for k in old['teacher_sources']}
    guided, log = learn_grammar(spec, seeds, score, native_feedback=True)
    blind, blind_log = learn_grammar(spec, seeds, score, native_feedback=False)
    variants = {'NativeGuided': guided, 'NoMerge': seeds, 'NoNativeFeedback': blind}
    calibration, updates = {}, {}
    for name, rules in variants.items():
        calibration[name] = {k: source_result(rules, k) for k in old['teacher_sources']}
        gain = sum(calibration[name][k]['native_grade'] - base[k]['native_grade'] for k in old['trigger']) / len(old['trigger'])
        history = all(calibration[name][k]['native_grade'] >= base[k]['native_grade'] for k in old['history'])
        updates[name] = {'strict_trigger_gain': gain, 'history_nonregression': history,
            'accepted_by_numeric_gate': gain > 0 and history, 'grammar_cost': grammar_cost(rules),
            'source_rules': len(rules), 'merged_rules': sum(bool(r['merged_from']) for r in rules)}
        immutable_json(folder / name / 'frozen_skill.json', {'spec': spec, 'rules': rules, 'update': updates[name],
            'before_probe_executions': True, 'before_probe_labels_used_for_updates': True,
            'shared_acquisition_not_independent_method_credit': True})
    probes = {name: [source_result(rules, k) for k in old['frozen_TRAIN_probes']] for name, rules in variants.items()}
    result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'protocol_hash': digest(protocol),
        'comparison_type': protocol['comparison_type'], 'rejected_annotations': rejected,
        'calibration': calibration, 'frozen_TRAIN_probes': probes, 'updates': updates,
        'native_guided_merge_log': log, 'unguided_merge_log': blind_log,
        'warm_base_grades': {k: base[k]['native_grade'] for k in old['teacher_sources'] + old['frozen_TRAIN_probes']},
        'deterministic_procedure_cache_entries': len(cache), 'ledger_before': before,
        'ledger_after': physical_snapshot(ledger), 'new_physical_calls': 0,
        'source_semantic_review_pending': True, 'goal_complete': False}
    assert result['ledger_before'] == result['ledger_after']
    immutable_json(folder / 'completed.json', result)
    return result


if __name__ == '__main__':
    x = run(Path(__file__).resolve().parents[1])
    print(json.dumps({'updates': x['updates'], 'merge_attempts': len(x['native_guided_merge_log']),
        'probe_core': {a: [(r['core_views'], r['native_core_correct']) for r in rows] for a, rows in x['frozen_TRAIN_probes'].items()},
        'ledger': x['ledger_after']}))
