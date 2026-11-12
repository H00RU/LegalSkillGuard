"""Zero-model execution control for the actually acquired text-consuming skills.

The program sees every original rule span, instead of model-selected spans.
This is a fixed-program execution comparison, not independent acquisition or
a replacement for actual READ validation. Native labels only grade outputs.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import source_spans, grade_view
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.runtime import execute_helper
from legal_skill_guard.skill_evolution.source_fragments import fragment_field

RUN = 'legal_skill_evolution_whole_source_control_20261112'
ARMS = ('Full', 'Lift+GenericJoint')
PRODUCER = 'nda_representative_exception_applicability'
CONSUMER = 'nda_disclosure_permission_consequence'


def read(path):return json.loads(path.read_text())


def counts(path):
    with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as db:
        return db.execute('select role,status,count(*) from calls group by role,status').fetchall()


def prepare(root):
    prior = root / 'artifacts/legal_skill_evolution_fragment_program_update_20261112'
    old = read(prior / 'protocol.json')['already_fixed_original_TRAIN_parents']
    public = root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    records = read(public)
    # Preserved file order, no native labels or new model outputs in selection.
    new = [s['key'] for s in records if s['dataset'] == 'ContractNLI' and s['key'] not in old][:3]
    if len(new) != 3:raise ValueError('Exactly three remaining original TRAIN parents required')
    libraries = {a: prior / 'postrun_audit' / (a + '_library.json') for a in ARMS}
    code = [Path(__file__).resolve(), root / 'legal_skill_guard/skill_evolution/runtime.py',
        root / 'legal_skill_guard/skill_evolution/objects.py', root / 'legal_skill_guard/skill_evolution/native.py',
        root / 'legal_skill_guard/skill_evolution/worker.py']
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'question': 'Does the frozen learned program need paid text selection, and does it transfer unchanged to the next three original TRAIN contracts?',
        'fixed_existing_parents': old, 'next_original_TRAIN_parents': new,
        'selection': 'First three remaining ContractNLI parents in the preserved TRAIN public file order, excluding the already-used four; fixed before scoring or changing the program.',
        'execution_control': 'Supply every exact original source_text sentence/span to the frozen procedure, using the same array type and sentence boundaries. This is an explicitly broader input execution control, not a claim that every span satisfies either narrow READ field question. No selection, role, rule or native label is inferred by the host.',
        'comparison_scope': 'Same actually acquired programs; not independent end-to-end acquisition, new learning, a new full matrix or held-out validation. Cost of inherited acquisitions remains charged.',
        'scoring': 'nda-5/7 use deterministic learned producer and consumer. Other two native views retain their preserved real fallback output; all four stay in the parent denominator. Missing historical fallback is an error, not a new dispatch or default.',
        'new_models_calls': 0, 'source_only_program_input': True,
        'public_TRAIN_sha256': hashlib.sha256(public.read_bytes()).hexdigest(),
        'libraries': {a: {'path': str(p.relative_to(root)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for a, p in libraries.items()},
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code}}
    folder = root / 'artifacts' / RUN;immutable_json(folder / 'protocol.json', protocol)
    return folder, protocol, {s['key']: s for s in records}


def graph(library, source, view):
    public = {'source_text': view['public']['source_text'],
              'sentence_spans': view['public']['sentence_spans']}
    spans = source_spans(public)
    if not spans or any(s['field'] != 'source_text' for s in spans):raise ValueError('Exact source-only spans required')
    full = [s['text'] for s in spans]
    producer, consumer = library.skills[PRODUCER], library.skills[CONSUMER]
    def premises(skill):
        bindings = {}
        for name, p in skill.premises.items():
            if p['mode'] == 'constant':bindings[name] = p['value'];continue
            reader = next(r for r in skill.reads if r['id'] == p['read_id'])
            if not fragment_field(reader['fields'][p['field']]):
                raise ValueError('This control cannot fill semantic-value reads')
            bindings[name] = full
        return bindings
    if set(producer.inputs) != {'current_question'} or producer.inputs['current_question']['mode'] != 'argument':
        raise ValueError('Keep the actual current two-helper graph')
    inputs = {'current_question': view['public']['question']}
    preliminary = execute_helper(producer, inputs, premises(producer))
    actual_inputs = {}
    for name, port in consumer.inputs.items():
        if port['mode'] == 'argument' and name == 'current_question':actual_inputs[name] = inputs[name]
        elif port['mode'] == 'skill' and port['skill_id'] == producer.id:
            if port['arguments'] != {'current_question': {'namespace': 'inputs', 'port': 'current_question'}}:
                raise ValueError('Actual argument binding changed')
            actual_inputs[name] = preliminary[port['field']]
        else:raise ValueError('The control does not fill unknown extra inputs')
    answer = execute_helper(consumer, actual_inputs, premises(consumer))['answer']
    return answer, {'exact_rule_spans': len(spans), 'exact_rule_text_characters': sum(len(s) for s in full),
        'producer_output': preliminary, 'consumer_inputs': actual_inputs, 'new_model_requests': 0,
        'evidence_note': 'Full source input control; these are not model-selected field values.'}


def run(root):
    folder = root / 'artifacts' / RUN
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    folder, protocol, records = prepare(root)
    for name, sha in protocol['code_sha256'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:raise ValueError('Bound code changed')
    prior = root / 'artifacts/legal_skill_evolution_fragment_program_update_20261112'
    actual = read(prior / 'completed.json')
    ledger = root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    before = counts(ledger)
    if any(status == 'reserved' for role, status, n in before):raise ValueError('Reconcile actual pending calls')
    libraries = {a: Library.load(root / p['path']) for a, p in protocol['libraries'].items()}
    for a, p in protocol['libraries'].items():
        if hashlib.sha256((root / p['path']).read_bytes()).hexdigest() != p['sha256']:raise ValueError('Frozen library changed')
    # This is the first load of grading in this experiment; selection is frozen.
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    old_fallbacks = {}
    for path in (root / 'artifacts/legal_skill_evolution_20261111/formal_v5/NoSkill').glob('initial_B*.json'):
        if path.stem not in {'initial_B' + str(i) for i in range(1, 9)}:continue
        for source in read(path)['results']:old_fallbacks[source['source']] = source
    outcomes = {}
    keys = protocol['fixed_existing_parents'] + protocol['next_original_TRAIN_parents']
    for arm, library in libraries.items():
        rows = []
        for key in keys:
            source = records[key]
            if key in protocol['fixed_existing_parents']:
                baseline = (actual['frozen_TRAIN_reuse'][arm] if key == protocol['fixed_existing_parents'][3] else
                    next(c['trace'] for c in actual['updates'][arm]['table']['mixed_version_table']
                         if c['mask'] == actual['updates'][arm]['selected_mask'] and c['source'] == key))
            else:baseline = old_fallbacks[key]
            inherited = {v['view']: v for v in baseline['views']}
            views = []
            for view in source['views']:
                if view['id'] in ('nda-5', 'nda-7'):
                    answer, event = graph(library, source, view)
                    score = grade_view(source['dataset'], view, grading[key][view['id']], answer, [])
                    views.append({'view': view['id'], 'answer': answer, 'score': score,
                        'core_executed_offline': True, 'fallback': False, 'full_source_binding': event})
                else:
                    old = inherited[view['id']]
                    views.append({'view': view['id'], 'answer': old['execution']['answer'], 'score': old['score'],
                        'core_executed_offline': False, 'fallback': True,
                        'fallback_evidence': 'Preserved actual direct output, no new model execution; not core success.'})
            rows.append({'source': key, 'group': 'existing_four' if key in protocol['fixed_existing_parents'] else 'next_three_original_TRAIN',
                'views': views, 'native_grade': sum(v['score']['grade'] for v in views) / len(views),
                'native_core_correct': sum(v['score']['correct'] and v['core_executed_offline'] for v in views),
                'fallback_views': sum(v['fallback'] for v in views),
                'prior_real_selected_program_or_NoSkill_grade': baseline['native_grade']})
        outcomes[arm] = rows
    after = counts(ledger);assert before == after
    result = {'protocol_hash': digest(protocol), 'completed_utc': datetime.now(timezone.utc).isoformat(),
        'outcomes': outcomes, 'new_model_requests': 0, 'ledger_before': before, 'ledger_after': after,
        'frozen_program_execution_control_only': True, 'independent_acquisition_not_compared': True,
        'source_selection_not_claimed_as_needed_or_learned_here': True,
        'no_new_DEV_TEST_full_training_or_paper': True, 'goal_complete': False}
    immutable_json(folder / 'completed.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('action', choices=['prepare', 'run']);a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    if a.action == 'prepare':
        folder, protocol, _ = prepare(root)
        print(json.dumps({'protocol': str(folder / 'protocol.json'), 'next_original_TRAIN_parents': protocol['next_original_TRAIN_parents'], 'new_model_requests': 0}))
    else:
        v = run(root)
        print(json.dumps({'new_model_requests': 0, 'rows': {a: [(s['source'].split(':')[1][:3], s['native_grade'], s['native_core_correct']) for s in rows] for a, rows in v['outcomes'].items()}}))
