"""Audit the existing fixed study; never dispatch, tune, or open unfinished TEST.

Experimental completion and evidence for the two contributions are separate.
This report does not set Goal status or impose a new effect-size threshold.
"""
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_formal import ARMS, PROFILE, schedule
from legal_skill_guard.skill_evolution.objects import Library, digest, coupled_blocks
from legal_skill_guard.skill_evolution.teacher_transport import unpack
from reports.legal_skill_evolution_run_20261111.native_statistics import summarize

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def actual_executor_metadata(db, prefix):
    """Transport facts only; a normal stop is not semantic correctness."""
    statuses, finishes = Counter(), Counter()
    off, missing, reasoning = 0, 0, 0
    for status, raw in db.execute('select status,result from calls where role=\'executor\' and id like ?', (prefix + '%',)):
        statuses[status] += 1
        if status != 'completed':continue
        value = json.loads(raw)
        finishes[str(value.get('finish_reason'))] += 1
        off += value.get('thinking_requested') is False
        missing += 'thinking_requested' not in value
        reasoning += bool(value.get('reasoning_content'))
    return {'physical_statuses': dict(statuses), 'completed_finish_reasons': dict(finishes),
        'completed_OFF_flags': off, 'completed_missing_thinking_flag': missing,
        'completed_nonempty_reasoning_content': reasoning,
        'completed_response_OFF_consistent': off == statuses['completed'] and reasoning == 0,
        'normal_stop_is_not_semantic_or_method_evidence': True}


def teacher_delivery(profile, formal):
    """Check actual settled inputs, rather than infer dispatch from a prompt."""
    profiles = [profile] + [load(ROOT / p) for p in profile['exact_replay_profiles']]
    roots = {p['run_id']: ROOT / p['artifacts'] for p in profiles}
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        settled = {}
        origin = json.loads(db.execute("select value from meta where key='spec'").fetchone()[0])
        policies = {key.split(':', 1)[1]: json.loads(raw) for key, raw in db.execute(
            "select key,value from meta where key like 'external_legal_skill_policy:%'")}
        for identity, request_hash, raw in db.execute("select id,request_hash,result from calls where role='teacher' and status='completed'"):
            value = json.loads(raw)
            if value.get('request_sha256'):
                settled[value['request_sha256']] = identity, request_hash, value
    rows = []
    for arm in ARMS:
        for path in sorted((formal / arm).glob('teacher_B[1-8].json')):
            reply = load(path)
            identity, request_hash, physical = settled[reply['request_sha256']]
            if reply['value'] != physical['value'] or reply['source_ids'] != physical['source_ids']:
                raise ValueError('Teacher input audit does not match the settled response')
            request_path = roots[identity.split(':')[0]] / 'calls' / digest(identity) / 'request.json'
            request = load(request_path)
            if digest({'request': request, 'origin_spec': origin,
                       'policy': policies[identity.split(':')[0]]}) != request_hash:
                raise ValueError('Actual teacher request differs from the continuous physical ledger')
            task = json.loads(request['user_prompt'])
            if task.get('encoding') == 'lossless_shared_JSON_values_v1':
                task = unpack(task)
            batch = int(path.stem.split('_B')[1])
            old = Library.load(formal / arm / f'B{batch - 1}.json')
            expected = {s.id: [list(b) for b in coupled_blocks(s)
                if all(s.premises[n]['mode'] == 'constant' for n in b)] for s in old.skills.values()}
            if task['source_premise_block_candidates'] != expected or digest(task['library']) != digest(
                    {k: asdict(s) for k, s in old.skills.items()}):
                raise ValueError('Actual teacher input omitted or changed a library/Lift candidate')
            rows.append({'arm': arm, 'batch': batch, 'physical_id': identity,
                'request_path': str(request_path.relative_to(ROOT)), 'request_file_sha256': sha(request_path),
                'request_hash_matches_continuous_ledger': True,
                'supplied_constant_blocks': sum(map(len, expected.values())),
                'supplied_dependency_ports': sum(p['mode'] == 'skill' for s in old.skills.values() for p in s.inputs.values()),
                'supplied_learned_patterns': len(task['learned_patterns']),
                'proposed_operations': dict(Counter(r['operation'] for b in reply['value']['blocks'] for r in b['revisions'])),
                'actual_library_and_candidates_match': True})
    return {'settled_teacher_inputs_checked': len(rows),
        'requests_with_supplied_constant_blocks': sum(r['supplied_constant_blocks'] > 0 for r in rows),
        'requests_with_supplied_dependency_ports': sum(r['supplied_dependency_ports'] > 0 for r in rows),
        'requests_with_supplied_learned_patterns': sum(r['supplied_learned_patterns'] > 0 for r in rows),
        'by_arm': {arm: {'settled_requests': sum(r['arm'] == arm for r in rows),
            'requests_with_constant_blocks': sum(r['arm'] == arm and r['supplied_constant_blocks'] > 0 for r in rows)}
            for arm in ARMS if arm != 'NoSkill'},
        'candidate_blocks_are_opportunities_not_validated_legal_gold': True,
        'new_model_calls': 0, 'rows': rows}


def build():
    profile = load(PROFILE)
    formal = ROOT / profile['artifacts']
    frozen = ROOT / 'artifacts/legal_skill_evolution_20261111/frozen_test_v1'
    evidence = {}

    def cite(path):
        if path.exists():
            evidence[str(path.relative_to(ROOT))] = sha(path)

    cite(PROFILE)
    binding = load(formal / 'execution_manifest.json')
    bad_bindings = [p for p, expected in {**binding['code'], **binding['data'],
        str(PROFILE.relative_to(ROOT)): binding['profile_sha256']}.items()
        if not (ROOT / p).exists() or sha(ROOT / p) != expected]
    cite(formal / 'execution_manifest.json')
    manifest_path = ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json'
    manifest = load(manifest_path)
    expected_sources = [r['source_key'] for b in manifest['source_sequence'] for r in b['sources']]
    if len(expected_sources) != 128 or len(set(expected_sources)) != 128:
        raise ValueError('The fixed TRAIN manifest no longer identifies 128 unique sources')
    cite(manifest_path)
    updates, accepted, rows = [], Counter(), []
    for arm in ARMS:
        initials = sorted((formal / arm).glob('initial_B[1-8].json'))
        seen = [r['source'] for p in initials for r in load(p)['results']]
        if seen != expected_sources[:len(seen)]:
            raise ValueError('TRAIN parent order differs from the fixed sequence in arm ' + arm)
        if Library.load(formal / arm / 'B0.json').skills:
            raise ValueError('A formal arm did not start from an empty library')
        for path in initials:
            point = load(path)
            batch = point['binding']['batch']
            expected = expected_sources[(batch - 1) * 16:batch * 16]
            previous = Library.load(formal / arm / f'B{batch - 1}.json')
            if point['binding']['source_ids'] != expected or point['binding']['library_hash'] != previous.hash:
                raise ValueError('A first attempt changed its registered batch or old library')
        libraries = sorted((formal / arm).glob('B[0-8].json'))
        latest = libraries[-1]
        library = Library.load(latest)
        cite(latest)
        arm_updates = sorted((formal / arm).glob('update_B[1-8].json'))
        for path in arm_updates:
            update = load(path)
            before = Library.load(formal / arm / ('B' + str(update['batch'] - 1) + '.json'))
            after = Library.load(formal / arm / ('B' + str(update['batch']) + '.json'))
            if update['old_library_hash'] != before.hash or update['new_library_hash'] != after.hash:
                raise ValueError('A recorded update differs from its actual library chain')
            updates.append(update)
            cite(path)
            if update['selected_candidate'] is None:
                continue
            candidate_path = formal / arm / ('B' + str(update['batch']) + '_candidates') / (str(update['selected_candidate']) + '.json')
            candidate = load(candidate_path)
            if candidate['selected_mask'] != update['selected_mask']:
                raise ValueError('Accepted update and actual candidate mask differ')
            accepted.update(r['operation'] for i, r in enumerate(candidate['revisions'])
                            if update['selected_mask'] & (1 << i))
            cite(candidate_path)
        rows.append({'arm': arm, 'completed_initial_batches': len(initials),
            'independent_TRAIN_parents': len(seen), 'completed_updates': len(arm_updates),
            'latest_library_batch': int(latest.stem[1:]), 'skill_count': len(library.skills),
            'revision_pattern_count': len(library.revision_patterns),
            'actual_dependency_ports': sum(p['mode'] == 'skill' for s in library.skills.values()
                                           for p in s.inputs.values())})
    expected_dev = [(arm, batch) for action, arm, batch in schedule() if action == 'dev']
    dev = [load(formal / 'dev' / a / f'B{b}.json') for a, b in expected_dev
           if (formal / 'dev' / a / f'B{b}.json').exists()]
    for point in dev:
        library = Library.load(formal / point['arm'] / ('B' + str(point['batch']) + '.json'))
        if library.hash != point['library_hash']:
            raise ValueError('A DEV point differs from its registered library')
    train_done = formal / 'training_DEV_completed.json'
    formal_complete = train_done.exists() and len(updates) == 48 and len(dev) == 42 and all(
        r['completed_initial_batches'] == 8 and r['independent_TRAIN_parents'] == 128 for r in rows)
    cite(train_done)
    mechanism = load(REPORT / 'formal_mechanism_inventory.json')
    cite(REPORT / 'formal_mechanism_inventory.json')
    patterns = sum(r['revision_pattern_count'] for r in rows)
    transplants = mechanism['actual_pattern_transplant_candidates']
    inventory_updates = len(mechanism['library_inventory'])
    test_done = frozen / 'TEST_completed.json'
    test_complete = test_done.exists()
    test_results, contrasts, transfer = {}, {}, None
    frozen_changed = []
    # No prepared TEST, predictions, annotations or results are read before the
    # complete fixed matrix exists. Analysis cannot feed back into that run.
    if test_complete:
        receipt = load(test_done)
        if (receipt['systems'], receipt['independent_parents_per_dataset'],
                receipt['native_views_per_system']) != (7, 32, 352):
            raise ValueError('Frozen completion receipt differs from the fixed study')
        for relative, expected in receipt['result_file_sha256'].items():
            path = frozen / relative
            if sha(path) != expected:
                raise ValueError('Completed TEST result changed: ' + relative)
            cite(path)
        freeze = load(frozen / 'freeze_manifest.json')
        frozen_profile_path = ROOT / 'configs/legal_skill_evolution_frozen_v1_20261111.json'
        frozen_profile = load(frozen_profile_path)
        if sha(frozen_profile_path) != freeze['profile_sha256'] or digest({k: v for k, v in freeze.items()
                if k != 'profile_sha256'}) != frozen_profile['freeze']['artifact_sha256']:
            raise ValueError('Frozen profile and artifact fingerprints differ')
        if receipt['freeze_artifact_sha256'] != frozen_profile['freeze']['artifact_sha256']:
            raise ValueError('TEST completion belongs to another freeze')
        expected_test = frozen_profile['source_ids']['test']
        frozen_changed = [p for p, expected in {**freeze['code'], **freeze['data']}.items()
                          if not (ROOT / p).exists() or sha(ROOT / p) != expected]
        for arm in ARMS:
            test_results[arm] = load(frozen / (arm + '_native_summary.json'))
            parents = [load(p) for p in sorted((frozen / 'predictions' / arm).glob('*.json'))]
            if len(parents) != 160 or len({p['source'] for p in parents}) != 160:
                raise ValueError('A completed TEST arm lacks the fixed independent parents')
            by_key = {p['source']: p for p in parents}
            if set(by_key) != set(expected_test) or any(p['library_hash'] != freeze['B8_hashes'][arm]
                                                       for p in parents):
                raise ValueError('A completed TEST arm differs from its frozen source/library identities')
            parents = [by_key[key] for key in expected_test]
            actual = summarize(parents)
            # Source rows have the original runtime ordering in the published
            # summary; compare identity-keyed rows and the order-free metrics.
            reported = test_results[arm]['metrics']
            if ({r['source']: r for r in actual['source_rows']} !=
                    {r['source']: r for r in reported['source_rows']} or
                    {k: v for k, v in actual.items() if k != 'source_rows'} !=
                    {k: v for k, v in reported.items() if k != 'source_rows'}):
                raise ValueError('A native TEST summary differs from actual parent results')
            if any(v['parent_count'] != 32 for v in actual['datasets'].values()) or sum(
                v['path_counts']['native_views'] for v in actual['datasets'].values()) != 352:
                raise ValueError('A completed TEST arm differs from the registered native counts')
        contrasts = load(frozen / 'primary_four_contrasts.json')
        cite(test_done)
        cite(frozen / 'freeze_manifest.json')
        if (frozen / 'transfer/completed.json').exists():
            done = load(frozen / 'transfer/completed.json')
            for relative, expected in done['result_sha256'].items():
                path = frozen / 'transfer' / relative
                if sha(path) != expected:
                    raise ValueError('Completed registered transfer result changed')
                cite(path)
            transfer = load(frozen / 'transfer/summary.json')
            cite(frozen / 'transfer/completed.json')
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        statuses = {role: dict(db.execute('select status,count(*) from calls where role=? group by status', (role,)))
                    for role in ('executor', 'teacher')}
        forbidden_teachers = db.execute("select count(*) from calls where role='teacher' and id like 'legal_skill_evolution_frozen_%'").fetchone()[0]
        transport = {phase: actual_executor_metadata(db, prefix) for phase, prefix in (
            ('formal', 'legal_skill_evolution_formal_'),
            ('frozen', 'legal_skill_evolution_frozen_v1_20261111:'))}
    lift_status = ('not_supported_in_fixed_study' if formal_complete else 'incomplete') if not accepted['lift'] else 'trace_review_required'
    corev_status = ('not_supported_in_fixed_study' if formal_complete else 'incomplete') if not patterns or not transplants else 'trace_review_required'
    strong = {arm: contrasts.get(arm) for arm in ('Lift+GenericJoint', 'AllPorts+CoRev')}
    benefit = 'incomplete'
    if test_complete:
        benefit = ('not_supported_against_both_strong_controls' if any(
            v['equal_dataset_macro_difference'] <= 0 for v in strong.values())
            else 'effect_and_registered_uncertainty_review_required')
    requirements = {
        'fixed_model_thinking_OFF_no_parameter_training': {
            'status': 'verified_configuration_and_observed_response_flags' if (
                not profile['executor']['enable_thinking'] and not profile['model_parameter_updates'] and
                all(row['completed_response_OFF_consistent'] for row in transport.values())) else 'contradicted',
            'base_weight_receipt': 'artifacts/legal_skill_evolution_20261111/base_model_verified.json',
            'actual_response_transport': transport},
        'formal_bound_code_data_profile': {'status': 'verified' if not bad_bindings else 'contradicted', 'changed_paths': bad_bindings},
        '128_TRAIN_8_batches_48_updates_42_DEV_points': {'status': 'verified' if formal_complete else 'incomplete',
            'settled_learning_updates': len(updates), 'settled_DEV_points': len(dev)},
        'B8_fixed_seven_system_five_dataset_TEST': {'status': 'verified' if test_complete and not frozen_changed else 'contradicted' if frozen_changed else 'incomplete',
            'changed_frozen_paths': frozen_changed},
        'registered_foreign_skill_mask_contrast': {'status': 'verified' if transfer is not None else 'incomplete'},
        'Lift_independent_cross_parent_mechanism': {'status': lift_status, 'accepted_dedicated_lift_operations': accepted['lift']},
        'CoRev_independent_cross_parent_mechanism': {'status': corev_status,
            'latest_patterns_across_arms': patterns, 'observed_pattern_generated_candidates': len(transplants),
            'inventory_update_count': inventory_updates, 'current_update_count': len(updates)},
        'actual_meaningful_gain_over_strong_controls': {'status': benefit,
            'registered_TEST_contrasts': strong,
            'no_new_effect_size_or_zero_fallback_threshold_added': True},
        'no_teacher_during_frozen_evaluation': {'status': 'contradicted' if forbidden_teachers else 'verified_so_far', 'physical_teacher_calls': forbidden_teachers},
    }
    return {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'goal_status': 'active', 'goal_complete': False,
        'not_a_new_protocol_or_authorization': True,
        'automatic_Goal_completion_enabled': False,
        'requirements': requirements, 'arm_state': rows,
        'accepted_operation_counts_independently_recounted': dict(accepted),
        'actual_teacher_mechanism_delivery': teacher_delivery(profile, formal),
        'latest_DEV_by_arm': {arm: max((d for d in dev if d['arm'] == arm), key=lambda d: d['batch'])['equal_dataset_macro']
                              for arm in ARMS if any(d['arm'] == arm for d in dev)},
        'TEST_native_summaries': test_results, 'all_four_registered_TEST_contrasts': contrasts,
        'registered_transfer_summary': transfer, 'continuous_physical_ledger_statuses': statuses,
        'unknown_cash_invoices_are_not_imputed': True,
        'evidence_sha256': evidence,
        'interpretation': 'Experimental completion, ordinary skill acquisition gains, and independent Lift/CoRev benefits are separate claims. Zero observed mechanism events do not invalidate an algorithm universally, but cannot substantiate its claimed benefit in this fixed study. No extra sources, training epochs, TEST tuning, or success threshold are introduced.'}


def main():
    result = build()
    path = REPORT / 'fixed_study_completion_audit.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    lines = ['# 固定实验与方法验收核对', '',
        'Goal active、未完成。下列核对复用原方案，不新增验收门槛，不调用模型。', '',
        '| 原要求 | 当前证据状态 |', '|---|---|']
    for key, value in result['requirements'].items():
        lines.append(f"| {key} | {value['status']} |")
    lines += ['', '## 实际学习状态', '',
        '| 臂 | 初答母来源 | 已结算更新 | 技能 | 依赖端口 | 修订模式 |', '|---|---:|---:|---:|---:|---:|']
    for row in result['arm_state']:
        lines.append('| {arm} | {independent_TRAIN_parents} | {completed_updates} | {skill_count} | {actual_dependency_ports} | {revision_pattern_count} |'.format(**row))
    delivery = result['actual_teacher_mechanism_delivery']
    lines += ['', '## 真实教师输入核对', '',
        f"逐项核对{delivery['settled_teacher_inputs_checked']}个已结算教师请求的原始输入、账本请求哈希及批初库；其中{delivery['requests_with_supplied_constant_blocks']}次包含非空固定前提候选块，{delivery['requests_with_supplied_dependency_ports']}次包含技能依赖端口，{delivery['requests_with_supplied_learned_patterns']}次包含已学修订模式。候选块只表示有位置可提议，不代表该案一定需要或能够受益于Lift。分臂计数见JSON。"]
    lines += ['', '通过类型与执行、普通程序获取/修补的收益、专门Lift/CoRev的独立作用分开报告。回退不算核心机制成功。若完整固定实验仍无机制事件，不把跑完队列或DEV涨分替代双贡献验收，也不追加来源或修改TEST追分。', '',
        '完整数值、四项注册差值、账本状态和证据哈希见[JSON核对](fixed_study_completion_audit.json)；曲线及费用见[现有执行报告](README.md)。', '']
    (REPORT / 'FIXED_STUDY_COMPLETION_AUDIT.md').write_text('\n'.join(lines))
    print(json.dumps({'formal_updates': result['requirements']['128_TRAIN_8_batches_48_updates_42_DEV_points']['settled_learning_updates'],
        'TEST_complete': bool(result['TEST_native_summaries']), 'goal_complete': False, 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
