"""Reconcile exact requests and cold-replay the completed update comparison."""
import argparse
import ast
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

from experiments.rr_v2_contract_attachment_update import STAGE, ROOT, OLD, SCHEMAS, snapshot
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.contract_attachment_update import assess, apply, select
from legal_skill_guard.rr.contract_compiler_runtime import run
from legal_skill_guard.rr.coverage import digest

BACKUP = Path('/media/sangfor/vdb/legal-skill-backups/contract_attachment_update_20261110')


def read(path):
    return json.loads(path.read_text())


def close_only_outer_anchor(pattern):
    """The observed syntax repair only: one unclosed whole-pattern anchor.

    No inserted branch, lexical cue, capture, condition or semantic label.
    Refuse anything other than an otherwise balanced outer anchor at offset0.
    """
    try:
        re.compile(pattern)
        return pattern, False
    except re.error as e:
        if e.pos != 0 or not pattern.startswith('(?P<anchor>') or '(?#' in pattern or '(?x' in pattern:
            raise
    stack, escaped, char_class = [], False, False
    for i, char in enumerate(pattern):
        if escaped:
            escaped = False
            continue
        if char == '\\':
            escaped = True
            continue
        if char == '[':
            char_class = True
            continue
        if char == ']':
            char_class = False
            continue
        if char_class:
            continue
        if char == '(':
            stack.append(i)
        elif char == ')':
            if not stack:
                raise ValueError('Not an isolated missing outer-anchor closure')
            stack.pop()
    if stack != [0] or escaped or char_class:
        raise ValueError('Not an isolated missing outer-anchor closure')
    repaired = pattern + ')'
    re.compile(repaired)
    return repaired, True


def repair_and_reuse():
    """Apply the identical syntax adapter to both arms, then freeze reuse."""
    before = snapshot()
    seal = read(STAGE/'training_seal.json')
    state, repairs = {}, []
    for arm in SCHEMAS:
        raw = read(STAGE/(arm+'_learned.json'))
        started = time.monotonic()
        if arm == 'minimum_attachment':
            productions = json.loads(json.dumps(raw['value']['productions']))
            for production in productions:
                old = production['pattern']
                production['pattern'], changed = close_only_outer_anchor(old)
                if changed:
                    repairs.append({'arm':arm, 'id':production['id'], 'original':old, 'repaired':production['pattern']})
            update = select(productions, seal['documents'], seal['feedback'])
        else:
            tree = ast.parse(raw['value']['code'])
            replacements = []
            # The real response uses module-level literal regex constants.
            # Do not alter other strings or synthesize function body logic.
            for node in tree.body:
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                    continue
                old = node.value.value
                if not old.startswith('(?P<anchor>'):
                    continue
                fixed, changed = close_only_outer_anchor(old)
                if changed:
                    replacements.append((node.value.lineno, node.value.col_offset, node.value.end_lineno, node.value.end_col_offset, repr(fixed)))
                    repairs.append({'arm':arm, 'id':node.targets[0].id, 'original':old, 'repaired':fixed,
                                    'change':'Append only the missing closing parenthesis of the outer named anchor at offset0'})
            lines = raw['value']['code'].splitlines(keepends=True)
            for line, col, end_line, end_col, value in sorted(replacements, reverse=True):
                assert line == end_line, 'The observed literal occupies one source line'
                lines[line-1] = lines[line-1][:col] + value + lines[line-1][end_col:]
            code = ''.join(lines)
            checked = ast.parse(code)
            allowed = ast.parse(raw['value']['code'])
            for node in allowed.body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and node.value.value.startswith('(?P<anchor>'):
                    node.value.value = close_only_outer_anchor(node.value.value)[0]
            assert ast.dump(checked) == ast.dump(allowed)
            training = assess(code, seal['documents'], seal['feedback'])
            update = {'code':code, 'training':training, 'accepted':training['passed']}
        state[arm] = {'accepted':update['accepted'], 'update':update, 'raw_learned_sha256':hashlib.sha256((STAGE/(arm+'_learned.json')).read_bytes()).hexdigest(),
                      'common_syntax_repair_and_replay_seconds':time.monotonic()-started}
    immutable_json(STAGE/'current_update_state.json', {'arms':state, 'common_repairs':repairs,
                   'model_calls_for_repair':0, 'raw_outputs_unchanged':True, 'semantic_rules_conditions_branches_added_by_adapter':False})
    freeze = {'current_update_state_sha256':hashlib.sha256((STAGE/'current_update_state.json').read_bytes()).hexdigest(),
              'training_seal_sha256':hashlib.sha256((STAGE/'training_seal.json').read_bytes()).hexdigest(),
              'audit_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'source_only_reuse_plan_sha256':hashlib.sha256((STAGE/'source_only_reuse_plan.json').read_bytes()).hexdigest(),
              'scoring':'Review every emitted attachment and changed source support chain in the four fixed full originals; record misses separately, without native NLI questions or labels',
              'no_learning_or_retries_from_reuse_feedback':True, 'DEV_sealed':True}
    immutable_json(STAGE/'reuse_freeze.json', freeze)
    public = {p['key']:p for p in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    wrapper = seal['initial_program'] + '\n\ndef infer(document, query):\n    return _compile_graph(document)\n'
    rows = []
    for selected in read(STAGE/'source_only_reuse_plan.json')['sources']:
        document = public[selected['source']]['public']['document']
        assert hashlib.sha256(document.encode()).hexdigest() == selected['document_sha256']
        initial = run(wrapper, document, [None])[0]
        row = {**selected, 'document':document, 'initial_graph_entry':initial, 'arms':{}, 'native_question_not_executed':True}
        for arm, learned in state.items():
            code = learned['update'].get('code')
            if code is None or 'value' not in initial:
                row['arms'][arm] = {'not_executed':True,'reason':'No executable update or initial graph'}
                continue
            try:
                row['arms'][arm] = {'trained_update_accepted':learned['accepted'], **apply(code,document,initial['value'])}
            except Exception as e:
                row['arms'][arm] = {'error':type(e).__name__+': '+str(e)}
        rows.append(row)
    assert before == snapshot()
    immutable_json(STAGE/'frozen_source_only_reuse.json', {'results':rows, 'freeze_sha256':hashlib.sha256((STAGE/'reuse_freeze.json').read_bytes()).hexdigest(),
                   'new_model_calls':0,'new_native_pairs_or_labels':0,'ledger_unchanged':True})
    print(json.dumps({'common_repairs':len(repairs),'accepted':{a:x['accepted'] for a,x in state.items()},'source_only_mothers':4,'new_model_calls':0}))


def main():
    current = snapshot()
    with sqlite3.connect('file:'+str(BACKUP/'ledger.before.sqlite3')+'?mode=ro', uri=True) as db:
        before = {t: db.execute('select * from '+t+' order by 1').fetchall() for t in current}
    assert all(row in current[t] for t in before for row in before[t])
    added = {t: [r for r in current[t] if r not in before[t]] for t in current}
    assert len(added['calls']) == 2 and len(added['meta']) == 1 and not added['oracle_views']
    assert all(r[1] == 'teacher' and r[6] == 'completed' for r in added['calls'])
    assert not [r for r in current['calls'] if r[6] == 'reserved']
    seal = read(STAGE/'training_seal.json')
    for p, h in seal['files'].items():
        assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h, p
    arms = {}
    current_state = read(STAGE/'current_update_state.json')
    for arm in SCHEMAS:
        raw = read(STAGE/(arm+'_learned.json'))
        repaired = current_state['arms'][arm]
        update = repaired['update']
        code = update.get('code')
        replay = None if code is None else assess(code, seal['documents'], seal['feedback'])
        assert replay is None or replay == update['training']
        constraints = [] if replay is None else replay['constraints']
        native = [x for x in constraints if ':nda-' in x['constraint']]
        source = [x for x in constraints if x['constraint'] in {f['id'] for f in seal['feedback']}]
        wire = raw['physical_response']
        usage = wire['invocation']['usage']
        arms[arm] = {'initial_raw_accepted': raw['accepted'], 'accepted': repaired['accepted'], 'error': raw.get('error'),
                     'native_TRAIN_executed': len(native), 'native_TRAIN_correct': sum(x['passed'] for x in native),
                     'native_TRAIN_n': 8, 'native_TRAIN_mothers': 4, 'native_TRAIN_fallback': 0,
                     'source_corrections_satisfied': sum(x['passed'] for x in source), 'source_corrections_n': 2,
                     'constraints': constraints, 'cold_replay_equal': replay is None or replay == update['training'],
                     'proposed_productions': len(raw.get('value', {}).get('productions', [])) if arm == 'minimum_attachment' else None,
                     'selected_productions': len(update.get('productions', [])) if arm == 'minimum_attachment' else None,
                     'subsets_examined': len(update.get('selection_trace', [])) if arm == 'minimum_attachment' else None,
                     'selection_and_replay_seconds': raw['selection_and_replay_seconds'],
                     'common_syntax_repair_and_replay_seconds':repaired['common_syntax_repair_and_replay_seconds'],
                     'usage': usage, 'elapsed_seconds': wire['elapsed_seconds'],
                     'input_plus_output_tokens': usage['input_tokens'] + usage['output_tokens'],
                     'actual_invoice_usd': None, 'provider_internal_retries_observable': False}
    reuse = read(STAGE/'frozen_source_only_reuse.json')
    replayed = []
    for row in reuse['results']:
        small = {'ordinal': row['ordinal'], 'arms': {}}
        for arm, original in row['arms'].items():
            code = current_state['arms'][arm]['update'].get('code')
            if code is None:
                small['arms'][arm] = original
                continue
            new = apply(code, row['document'], row['initial_graph_entry']['value'])
            assert all(new[k] == original[k] for k in new)
            small['arms'][arm] = {'attachment_count': len(new['attachments']),
                'rewritten_or_removed_claim_count': len(new['changes']), 'residual_count': len(new['residuals']),
                'cold_replay_equal': True}
        replayed.append(small)
    names = ('id','role','purpose','bucket','source','request_hash','status','reserved_at','result')
    calls = [dict(zip(names, row)) for row in added['calls']]
    for call in calls:
        call['result'] = json.loads(call['result'])
    delta = {'before_rows': {t: len(v) for t,v in before.items()},
             'after_rows': {t: len(v) for t,v in current.items()},
             'all_prior_rows_byte_value_preserved': True, 'new_calls': calls,
             'new_meta': added['meta'], 'new_oracle_views': [], 'pending': 0}
    immutable_json(STAGE/'request_ledger_delta.json', delta)
    previous_stages = [ROOT/'artifacts/rr_method_redesign_20261109/contract_scope_acquisition_v1_20261110', OLD]
    prior_cost = {'input_plus_output_tokens': 0, 'elapsed_seconds': 0.0}
    for folder, files in [(previous_stages[0], ['source_scope_learned.json','ordinary_cache_learned.json']),
                          (OLD, ['scope_compiler_learned.json','ordinary_program_learned.json'])]:
        # Earlier per-contract acquisitions use different artifact names; the
        # verified preceding report is the authority for their total cost.
        if folder == OLD:
            for name in files:
                w = read(folder/name)['physical_response'];u = w['invocation']['usage']
                prior_cost['input_plus_output_tokens'] += u['input_tokens'] + u['output_tokens']
                prior_cost['elapsed_seconds'] += w['elapsed_seconds']
    prev_acq = read(ROOT/'reports/method_redesign_20261109/contract_scope_acquisition_results.json')
    for a in prev_acq['arms'].values():
        prior_cost['input_plus_output_tokens'] += a['usage']['input_tokens'] + a['usage']['output_tokens']
        prior_cost['elapsed_seconds'] += a['elapsed_seconds']
    update_cost = {'input_plus_output_tokens': sum(a['input_plus_output_tokens'] for a in arms.values()),
                   'elapsed_seconds': sum(a['elapsed_seconds'] for a in arms.values())}
    seed_wire = read(OLD/'ordinary_program_learned.json')['physical_response']
    seed_usage = seed_wire['invocation']['usage']
    out = {'counts_total': {r: sum(x[1] == r for x in current['calls']) for r in ['executor','teacher']},
           'pending': 0, 'new_charged_attempts': {'executor': 0, 'teacher': 2}, 'new_native_label_views': 0,
           'ledger_rows': {t:len(v) for t,v in current.items()}, 'ledger_logical_sha256': digest(current),
           'all_prior_ledger_rows_preserved': True, 'arms': arms, 'source_only_reuse': replayed,
           'common_syntax_repairs':current_state['common_repairs'],'new_model_calls_for_syntax_repair':0,
           'source_only_reuse_native_pairs_predictions_or_labels': 0, 'new_model_calls_for_reuse': 0,
           'comparison_type': 'shared_seed_update_isolation_not_independent_end_to_end_acquisition',
           'initial_program_acquisition_cost': {'usage': seed_usage, 'elapsed_seconds': seed_wire['elapsed_seconds'],
                'actual_project_counted_once': True, 'end_to_end_arm_cost_accounts_must_each_include_this_seed': True},
           'current_update_cost': update_cost,
           'research_line_cost_since_12_pair_authorization': {
                'teacher_calls': 6, 'input_plus_output_tokens': prior_cost['input_plus_output_tokens']+update_cost['input_plus_output_tokens'],
                'elapsed_seconds': prior_cost['elapsed_seconds']+update_cost['elapsed_seconds'],
                'actual_cash_invoice_usd': None, 'GPU_allocation_usd': None},
           'executor_thinking_OFF_unchanged': True, 'teacher_configuration_unchanged': True,
           'DEV_started': False, 'DEV_native_labels_opened': False, 'TEST_started': False,
           'full_training_started': False, 'paper_started': False,
           'first_contribution_established': False, 'two_contributions_established': False, 'goal_complete': False}
    assert current == snapshot()
    immutable_json(ROOT/'reports/method_redesign_20261109/contract_attachment_update_results.json', out)
    if not (BACKUP/'ledger.after.sqlite3').exists():
        with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as src, sqlite3.connect(BACKUP/'ledger.after.sqlite3') as dst:
            src.backup(dst)
    print(json.dumps({'counts_total':out['counts_total'], 'arms': {a:{k:v for k,v in x.items() if k in ['accepted','native_TRAIN_correct','source_corrections_satisfied']} for a,x in arms.items()},
                      'source_only_reuse':replayed, 'new_native_pairs':0, 'goal_complete':False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repair-and-reuse', action='store_true')
    args = parser.parse_args()
    if args.repair_and_reuse:
        repair_and_reuse()
    else:
        main()
