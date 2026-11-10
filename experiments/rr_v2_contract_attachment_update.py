"""Finite, TRAIN-only comparison of learned attachment update and free repair."""
import argparse
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.contract_attachment_update import assess, apply, select
from legal_skill_guard.rr.contract_compiler_runtime import check, run
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rr_method_redesign_20261109'
OLD = BASE / 'contract_compiler_induction_v1_20261110'
RUN = 'contract_attachment_update_v1_20261110'
STAGE = BASE / RUN
PROTOCOL = ROOT / 'reports/method_redesign_20261109/contract_attachment_update_protocol.md'
S = {'type': 'string'}
A = lambda item: {'type': 'array', 'items': item}
PRODUCTION = obj({'id': S, 'pattern': S,
    'kind': {'type': 'string', 'enum': ['permission', 'prohibition', 'obligation', 'no_breach', 'reference_only']},
    'action': {'type': 'string', 'enum': ['share', 'return_or_destroy', 'retain']},
    'condition_groups': A(S), 'reference_groups': A(S), 'clear_overrides': {'type': 'boolean'}})
SCHEMAS = {
    'minimum_attachment': obj({'productions': A(PRODUCTION), 'learned_operations': A(S), 'limitations': A(S)}),
    'ordinary_repair': obj({'code': S, 'learned_operations': A(S), 'limitations': A(S)})}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        return {t: db.execute('select * from ' + t + ' order by 1').fetchall() for t in ['calls', 'meta', 'oracle_views']}


def prepare():
    if (STAGE / 'training_seal.json').exists():
        return read(STAGE / 'training_seal.json')
    previous = read(OLD / 'training_seal.json')
    public = {p['key']: p for p in read(ROOT / 'data/packets/rr_v2/public_train.json')['sources']}
    excluded = {5, 10, 15, 20, 111, 115}
    ordinals = [i for i, key in enumerate(previous['sources']['train'], 1)
                if key.startswith('ContractNLI:') and i not in excluded][:4]
    assert ordinals == [109, 110, 112, 113]
    plan = {'selection': 'First four original TRAIN ContractNLI ordinals outside the current six repair mothers',
            'ordinals': ordinals, 'fixed_before_new_program_generation_and_source_execution': True,
            'native_queries_labels_pairs_added': 0,
            'sources': [{'ordinal': i, 'source': previous['sources']['train'][i-1],
                        'group': public[previous['sources']['train'][i-1]]['group'],
                        'document_sha256': hashlib.sha256(public[previous['sources']['train'][i-1]]['public']['document'].encode()).hexdigest()}
                       for i in ordinals]}
    immutable_json(STAGE / 'source_only_reuse_plan.json', plan)
    code = read(OLD / 'ordinary_program_learned.json')['physical_response']['value']['code']
    wrapper = code + '\n\ndef infer(document, query):\n    return _compile_graph(document)\n'
    materials = []
    for i in [5, 10, 111, 115, 15, 20]:
        key = previous['sources']['train'][i-1]
        document = public[key]['public']['document']
        graph_entry = run(wrapper, document, [None])[0]
        assert 'error' not in graph_entry, graph_entry
        examples = next((r['examples'] for r in previous['training'] if r['training_document'] == 'p'+str(i)), [])
        materials.append({'key': 'p'+str(i), 'source': key, 'document': document,
                          'graph': graph_entry['value'], 'examples': examples})
    feedback = [
        {'id': 'reference_qualified_prohibition', 'key': 'p15', 'anchor_contains': 'Except as provided herein, Volunteer is prohibited',
         'kind': 'prohibition', 'action': 'share', 'head_contains': 'prohibited', 'behavior_contains': 'disclosing',
         'reference_contains': 'Except as provided herein', 'condition_contains': '',
         'forbidden_effects_on_anchor': ['permission'],
         'explanation': 'This survival clause prohibits conduct subject to exceptions elsewhere; it is not itself an authorization. Do not claim the entire contract lacks a consent exception.'},
        {'id': 'negated_breach_with_conditional_disclosure', 'key': 'p20', 'anchor_contains': 'shall not have breached any obligation under this Agreement',
         'kind': 'no_breach', 'action': 'share', 'head_contains': 'not have breached', 'behavior_contains': 'disclosed',
         'reference_contains': '', 'condition_contains': 'if the Confidential Information is disclosed',
         'forbidden_effects_on_anchor': ['permission', 'prohibition', 'obligation'],
         'explanation': 'The negated main predicate is breach; disclosure is embedded in a condition. Preserve the no-breach consequence and its source condition. Do not infer permission or a disclosure prohibition.'}]
    common = (
        'Update a learned reusable legal-source parser on the supplied TRAIN feedback. This is an update-isolation comparison, '
        'not independent acquisition from scratch. Both arms start from the SAME independently acquired ordinary program and source graphs. '
        'The full originals, eight earlier native annotated TRAIN examples, initial program/graphs, and two source-semantic corrections are identical for both arms. '
        'Learn reusable attachment patterns from text, not document identifiers, company names, complete stored source strings or label lookups. '
        'No DEV, TEST or unseen source text is supplied. Preserve the eight earlier native TRAIN results. '
        'Common legal decomposition (already present in SG-DT, not a proposed innovation): identify the core normative predicate; '
        'distinguish conditions from legal effects; an exception reference without replacement consequence creates no permission. '
        'No-breach is not automatically permission and must remain a separate consequence. Negation can govern breach rather than the embedded conduct. '
        'The update returns source attachments: {start:int,end:int,quote:string,head:string,behavior:string,kind,action,conditions:[string],references:[string],clear_overrides:bool}. '
        'Every string field except kind/action must be an exact substring of the anchor quote; start/end are Python source character offsets of that quote. '
        'kind is permission|prohibition|obligation|no_breach|reference_only; action is share|return_or_destroy|retain. '
        'The shared rewriter is supplied in full. It changes only existing graph claims whose source quote contains the attachment anchor and whose action matches. '
        'Matching records must agree on meaning, otherwise the claim remains an explicit ambiguity residual. '
        'Non-conduct consequences are preserved as residuals, without converting them to permissions or native absence. '
        'Conduct updates preserve original recipients/triggers, set the source-qualified head/conditions/references and clear priority only if requested. '
        'Do not treat arbitrary missing annotations as proof of absence. Unchanged parts of the learned parser remain available. '
        'Both arms may use regex, ordinary Python helper functions, arbitrary parsing or the supplied named-capture representation. '
        'The ordinary repair is allowed to implement the same grammar/selection scheme; it is not restricted to keywords. '
        'The source feedback is positive as well as negative: deleting all norms or returning [] does not satisfy it. '
        'All semantic corrections are TRAIN supervision, not new native hypothesis labels. Do not fabricate new legal cases or feedback. '
        'No tools, imports, classes, lambda, exceptions, annotations/defaults/decorators, filesystem, network or private environment. '
        'Available re methods/flags and safe builtins are those of the supplied original runtime. Do not run tools. Return only the requested JSON. ')
    systems = {
        'minimum_attachment': common +
        'Propose a FINITE BANK of 1..8 reusable attachment productions, including alternatives only where there is a real ambiguity. '
        'Each regex uses named groups anchor (whole clause), head (core normative predicate), behavior (conduct phrase). '
        'condition_groups and reference_groups name any additional captured groups; omit absent names from those lists. '
        'Regex runs over the new full document using re.I|re.S. Exact captures are assembled by the shared production_code, which is supplied. '
        'The deterministic learner selects the smallest consistent subset of this bank by (number of productions, serialized UTF-8 bytes, canonical IDs). '
        'Consistency requires both source-semantic corrections and the eight old native TRAIN outcomes. No held-out data participates in selection. '
        'This is finite constraint selection, not a universal correctness oracle. Return productions, learned_operations, limitations. ',
        'ordinary_repair': common +
        'Independently learn the strongest unrestricted ordinary Python repair infer(document,query), called with query=None, returning the attachment list. '
        'You may use any reusable parser/regex/grammar, named-capture construction, helper functions, or literal constants supported by the supplied runtime. '
        'There is no requirement to use a different representation from the candidate. Choose your own guards and attachment logic using all the same feedback. '
        'The SAME shared graph rewriter and TRAIN checks will evaluate your program. Return code, learned_operations, limitations. '}
    paths = ['experiments/rr_v2_contract_attachment_update.py', 'legal_skill_guard/rr/contract_attachment_update.py',
             'legal_skill_guard/rr/contract_compiler_runtime.py', 'legal_skill_guard/rr/contract_scope_learning.py',
             'legal_skill_guard/rr/method_client.py', 'legal_skill_guard/rr/method_ledger.py', 'legal_skill_guard/rr/client.py']
    files = {p: sha(ROOT / p) for p in paths}
    user = json.dumps({'training_materials': materials, 'source_semantic_feedback': feedback, 'initial_learned_program': code,
                       'common_update_runtime': (ROOT / paths[1]).read_text(),
                       'common_bounded_program_runtime': (ROOT / paths[2]).read_text()}, ensure_ascii=False)
    seal = {'run_id': RUN, 'config': previous['config'], 'sources': previous['sources'],
            'source_ids': [m['source'] for m in materials], 'documents': materials, 'feedback': feedback,
            'initial_program': code, 'initial_program_sha256': hashlib.sha256(code.encode()).hexdigest(),
            'systems': systems, 'user': user, 'schemas': SCHEMAS, 'files': files,
            'binding': {'code_hash': digest(files), 'config_hash': digest(previous['config'])},
            'protocol_sha256': sha(PROTOCOL), 'shared_initial_program_update_isolation_not_fresh_acquisition': True,
            'DEV_text_labels_loaded': False, 'source_only_reuse_plan_sha256': sha(STAGE / 'source_only_reuse_plan.json'),
            'goal_complete': False}
    assert all(strict_output_schema_issues(x) == [] for x in SCHEMAS.values())
    assert not assess('def infer(document, query):\n    return []\n', materials, feedback)['passed']
    immutable_json(STAGE / 'training_seal.json', seal)
    for path in paths:
        p = STAGE / 'frozen' / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes((ROOT / path).read_bytes())
    return seal


def learn(arm):
    output = STAGE / (arm + '_learned.json')
    if output.exists():
        print(json.dumps({'existing': True, 'arm': arm, 'no_redispatch': True}))
        return
    seal = prepare()
    for p, h in seal['files'].items():
        assert sha(ROOT / p) == h, p
    ledger = MethodLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        binding=seal['binding'], sources=seal['sources'], authorization_hash=seal['protocol_sha256'],
        question='Does minimum consistent selection of learned, source-anchored attachment productions repair legal normative-head acquisition more reliably or cheaply than independent unrestricted program repair from the same initial learned parser and exactly the same TRAIN feedback? Four pre-fixed original TRAIN mothers are reserved for source-only reuse, without new native pairs or labels; DEV stays sealed.')
    wire = MethodTeacher(ledger, STAGE, seal['config']['teacher']).summarize(RUN + ':train:' + arm,
        source_ids=seal['source_ids'], system_prompt=seal['systems'][arm], user_prompt=seal['user'], output_schema=seal['schemas'][arm])
    result = {'arm': arm, 'physical_response': wire, 'goal_complete': False,
              'shared_seed_update_isolation_not_fresh_acquisition': True}
    started = time.monotonic()
    try:
        value = wire['value']
        if arm == 'minimum_attachment':
            update = select(value['productions'], seal['documents'], seal['feedback'])
        else:
            check(value['code'])
            training = assess(value['code'], seal['documents'], seal['feedback'])
            update = {'code': value['code'], 'training': training, 'accepted': training['passed']}
        result.update(value=value, update=update, accepted=update['accepted'])
    except Exception as e:
        result.update(accepted=False, error=type(e).__name__ + ': ' + str(e))
    result['selection_and_replay_seconds'] = time.monotonic() - started
    immutable_json(output, result)
    print(json.dumps({'arm': arm, 'accepted': result['accepted'], 'error': result.get('error'),
                      'selection_and_replay_seconds': result['selection_and_replay_seconds'], 'goal_complete': False}), flush=True)


def source_reuse():
    output = STAGE / 'frozen_source_only_reuse.json'
    if output.exists():
        print(json.dumps({'existing': True, 'no_model_or_source_rerun': True}))
        return
    seal = prepare()
    for p, h in seal['files'].items():
        assert sha(ROOT / p) == h, p
    arms = {arm: read(STAGE / (arm + '_learned.json')) for arm in SCHEMAS}
    # Save both outputs, acceptance/rejection and every learned byte BEFORE
    # opening the four reserved source texts for execution or interpretation.
    freeze = {'learned_sha256': {a: sha(STAGE / (a+'_learned.json')) for a in arms},
              'files': seal['files'], 'scoring': 'Full claimed source-attachment/support-chain review; no native questions/labels',
              'no_model_retry_from_reuse_feedback': True, 'DEV_sealed': True}
    immutable_json(STAGE / 'reuse_freeze.json', freeze)
    before = snapshot()
    pub = {p['key']: p for p in read(ROOT / 'data/packets/rr_v2/public_train.json')['sources']}
    wrapper = seal['initial_program'] + '\n\ndef infer(document, query):\n    return _compile_graph(document)\n'
    rows = []
    for selected in read(STAGE / 'source_only_reuse_plan.json')['sources']:
        document = pub[selected['source']]['public']['document']
        assert hashlib.sha256(document.encode()).hexdigest() == selected['document_sha256']
        initial = run(wrapper, document, [None])[0]
        row = {**selected, 'document': document, 'initial_graph_entry': initial, 'arms': {}, 'native_question_not_executed': True}
        if 'error' not in initial:
            for arm, learned in arms.items():
                # Failed training fit is retained; do not silently substitute
                # the initial program or pretend that failure is a fallback.
                code = learned.get('update', {}).get('code')
                if code is None:
                    row['arms'][arm] = {'not_executed': True, 'reason': 'No accepted consistent production subset'}
                    continue
                try:
                    row['arms'][arm] = {'trained_update_accepted': learned['accepted'], **apply(code, document, initial['value'])}
                except Exception as e:
                    row['arms'][arm] = {'error': type(e).__name__ + ': ' + str(e)}
        rows.append(row)
    assert before == snapshot()
    immutable_json(output, {'results': rows, 'freeze_sha256': sha(STAGE / 'reuse_freeze.json'),
                            'new_model_calls': 0, 'new_native_pairs_or_labels': 0, 'ledger_unchanged': True})
    print(json.dumps({'original_TRAIN_mothers': len(rows), 'native_queries_or_labels': 0, 'new_model_calls': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'minimum_attachment', 'ordinary_repair', 'reuse'])
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
        print(json.dumps({'prepared': True, 'new_model_calls': 0, 'DEV_sealed': True}))
    elif args.action == 'reuse':
        source_reuse()
    else:
        learn(args.action)
