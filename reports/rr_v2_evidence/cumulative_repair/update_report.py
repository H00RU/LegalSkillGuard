"""Read-only ledger/source audit, writing unbound reporting artifacts only."""
import datetime
import hashlib
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    offline_count = int(re.search(r'(\d+) passed', (ROOT / 'reports/rr_v2_evidence/offline_latest.txt').read_text())[1])
    backend_cases = sum(r['decoder_cases'] for r in read(OUT / 'backend_precheck.json')['records'])
    db = sqlite3.connect(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute('SELECT * FROM calls ORDER BY rowid')]
    for r in rows:
        r['result'] = json.loads(r['result']) if r['result'] else {}
    executor = [r for r in rows if r['role'] == 'executor']
    teachers = [r for r in rows if r['role'] == 'teacher']
    pending = [r['id'] for r in rows if r['status'] == 'reserved']
    baseline = sqlite3.connect(ROOT / 'artifacts/rr_v2_preflight/preserved_before_cumulative_repair/research_ledger.sqlite3')
    current_plain = sqlite3.connect(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    old_rows = baseline.execute('SELECT * FROM calls ORDER BY rowid').fetchall()
    kept = all(current_plain.execute('SELECT * FROM calls WHERE id=?', (r[0],)).fetchone() == r for r in old_rows)
    old_meta = baseline.execute('SELECT * FROM meta').fetchall()
    meta_kept = all(current_plain.execute('SELECT value FROM meta WHERE key=?', (k,)).fetchone() == (v,) for k, v in old_meta)
    oracle_kept = baseline.execute('SELECT * FROM oracle_views ORDER BY source,view_hash').fetchall() == current_plain.execute('SELECT * FROM oracle_views ORDER BY source,view_hash').fetchall()
    assert kept and meta_kept and oracle_kept
    outcomes = {k.removeprefix('repair_outcome:'): json.loads(v) for k, v in
                db.execute("SELECT * FROM meta WHERE key LIKE 'repair_outcome:%'")}
    new = []
    for physical, r in enumerate(executor, 1):
        if physical <= 85:
            continue
        v = outcomes.get(r['id'], {})
        new.append({'physical_request': physical, 'call_id': r['id'], 'source': r['source'],
                    'status': r['status'], 'request_hash': r['request_hash'],
                    'revision': r['id'].split(':')[1], 'usage': r['result'].get('usage'),
                    'elapsed_seconds': r['result'].get('elapsed_seconds'), 'finish_reason': r['result'].get('finish_reason'),
                    'pass': v.get('pass', False), 'reason': v.get('reason', 'pending'),
                    'typed_schema_pass': v.get('typed_schema_pass', False),
                    'model_IR_executed': v.get('model_IR_executed', False),
                    'program_native_score': v.get('program_native_score'),
                    'source_grounding': v.get('source_grounding'), 'artifact_directory': r['result'].get('artifact_directory')})
    old_sources = read(ROOT / 'reports/rr_v2_evidence/strict_contract_round2/source_outcomes.json')['all_fixed20_source_outcomes']
    sources = []
    for index, old in enumerate(old_sources):
        relevant = [c for c in new if c['source'] == old['source']]
        passed = [c for c in relevant if c['pass']]
        latest = relevant[-1] if relevant else None
        target = old['dataset'] in {'OpenExempt', 'RuleArena_Airline', 'SARA_v2_Binary'}
        status = '修复验证通过' if passed else '验证运行中' if latest and latest['status'] == 'reserved' else '已验证，仍未解决' if latest else ('额度内未验证' if len(executor) >= 96 else '本次尚未验证') if target else \
                 '公开Horn后端已验证' if old['independent_public_Horn_backend_verified'] else '原生fallback已有记录，无形式认证'
        sources.append({'source_index': index, 'source': old['source'], 'dataset': old['dataset'],
                        'status': status, 'original_native_source_correct': old['old_native_source_correct'],
                        'original_program_status': old['old_final_program_status'],
                        'independent_public_horn': old['independent_public_Horn_backend_verified'],
                        'repair_pass': bool(passed), 'new_request_numbers': [c['physical_request'] for c in relevant],
                        'latest_reason': latest['reason'] if latest else None,
                        'latest_model_IR_executed': latest['model_IR_executed'] if latest else False})
    def usage(r):
        return (r['result'].get('invocation', {}).get('usage') if r['role'] == 'teacher' else r['result'].get('usage')) or {}
    def totals(calls):
        return {'physical_requests': len(calls),
                'prompt_tokens': sum(usage(r).get('prompt_tokens', usage(r).get('input_tokens', 0)) for r in calls),
                'completion_tokens': sum(usage(r).get('completion_tokens', usage(r).get('output_tokens', 0)) for r in calls),
                'elapsed_seconds': sum(r['result'].get('elapsed_seconds', 0) for r in calls),
                'usage_missing_requests': sum(not usage(r) for r in calls)}
    cost = {'executor_all': totals(executor), 'executor_after85': totals(executor[85:]), 'teacher': totals(teachers),
            'incremental_executor_api_cash_usd': 0, 'gpu_cost_usd': None, 'teacher_cash_usd': None,
            'cash_basis': 'existing local executor has no per-request API invoice; GPU monetary cost unpriced; teacher billing unavailable'}
    summary = {'captured_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'executor_used': len(executor), 'executor_cumulative_max': 96, 'executor_global_hard_max': 100,
               'remaining_authorized_requests': max(0, 96-len(executor)), 'teacher_used': len(teachers), 'teacher_max': 2,
               'pending': pending, 'baseline87_rows_preserved': kept, 'old_meta_preserved': meta_kept,
               'oracle_rows_unchanged': oracle_kept, 'oracle_rows': db.execute('SELECT count(*) FROM oracle_views').fetchone()[0],
               'repair_success_sources': [s['source'] for s in sources if s['repair_pass']],
               'tested_unresolved_sources': [s['source'] for s in sources if s['status'] == '已验证，仍未解决'],
               'affected_sources_not_validated': [s['source'] for s in sources if s['status'] in {'本次尚未验证', '额度内未验证'}],
               'fixed20_source_status': sources, 'calls': new, 'cost': cost,
               'formal_training_ready': False, 'goal_complete': False, 'main_training_started': False,
               'formal_evaluation_started': False, 'paper_started': False,
               'frozen_library_file_sha256': hashlib.sha256((ROOT / 'artifacts/rr_v2_preflight/oracle_guard/partial_library.frozen.json').read_bytes()).hexdigest()}
    save(OUT / 'summary.json', summary)
    save(OUT / 'requests.json', {'calls': new, 'cost': cost})
    save(OUT / 'source_status.json', {'sources': sources})
    lines = ['# LegalSkillGuard RR-v2 当前检查报告', '',
             '完整goal未完成，正式训练尚未就绪。当前结果仅属于原固定20个TRAIN来源的修复预检；未启动主训练、正式评测、冻结测试或论文。', '',
             f"账本executor **{len(executor)}/96**（全局100硬上限），teacher **{len(teachers)}/2**；新增{len(new)}次，剩余{max(0,96-len(executor))}次，待结算{len(pending)}次。失败和重试均计数，客户端及底层自动重试为0。旧87行（85 executor+2 teacher）、旧meta和50条oracle记录核验不变。", '',
             '用户已取消旧修复轮数和首错停止限制。失败来源重试须有具体修改及离线证据；修复验证通过后，同版本可继续未完成固定来源，不新增来源、种子或测试标签。授权及工程边界见docs/rr_v2/cumulative_repair_authorization.json。', '',
             '## 契约修复证据', '',
             '原36条输出经47处可逆格式适配仍为0条可执行IR：缺query、缺分支、截断或明确unsupported；未补造语义。第85条暴露布尔操作数及source node契约不一致；第86条暴露金额作对象键，第87条暴露无界嵌套和截断。原文、真实失败回归、前后契约与修改依据均保留。', '',
             f'实现提交：d3a3803（类型/节点及账本），28eceb4（16层AST），7a01fce（原任务），2aafb3d（字面量），29d37f3（闭合输入），9d11dcc（原生字段类型），ca06ff3（解码正则引号边界），a00ce55（资产键唯一性）。当前{offline_count}项网络阻断离线检查、12来源共{backend_cases}个实际token解码用例通过。第94条实际非法JSON在旧xgrammar语法中被接受为前缀，新语法明确拒绝。闭合输入修复仅在已有四个输入均通过逐字溯源的原OE来源上真实验证，未推广成全训练已就绪的结论。采样、thinking ON、模型与seed45保持原定设置。', '',
             '证据：`reports/rr_v2_evidence/cumulative_repair/contract_audit.json`、`revision_v2_audit.json`、`backend_precheck.json`；实际请求及验证：`artifacts/rr_v2_preflight/cumulative_repair/`。每次请求保留request/wire/result与validation；自第二版起另存字节级wire_request。', '',
             '## 本次物理请求', '', '| 累计序号 | 来源 | 版本 | 结果 | token | 秒 |', '|---|---|---|---|---:|---:|']
    for c in new:
        usage = c['usage'] or {}
        tokens = usage.get('total_tokens', 0)
        lines.append(f"| {c['physical_request']} | {c['source']} | {c['revision']} | {c['reason']} | {tokens} | {c['elapsed_seconds'] or 0:.3f} |")
    lines += ['', '通过只指：严格schema、类型、实际程序执行、公开来源溯源、该程序输出的原固定TRAIN语义检查全部成立。单独模型答案、fallback正确或JSON可解析均不算修复成功。', '',
              '## 原固定20来源状态', '', '| 序号 | 来源 | 当前状态 | 新请求序号 |', '|---|---|---|---|']
    for s in sources:
        lines.append(f"| {s['source_index']} | {s['source']} | {s['status']} | {','.join(map(str,s['new_request_numbers']))} |")
    lines += ['', '## 实际费用及验收', '',
              f"本次新增executor token：{cost['executor_after85']['prompt_tokens']}输入 + {cost['executor_after85']['completion_tokens']}输出；请求耗时合计{cost['executor_after85']['elapsed_seconds']:.3f}秒。全部executor token：{cost['executor_all']['prompt_tokens']}输入 + {cost['executor_all']['completion_tokens']}输出。", '',
              f"本地executor新增API现金支出$0；GPU货币成本未定价，不能称总计算免费。teacher未新增；原两次中的成功调用已知{cost['teacher']['prompt_tokens']}输入、{cost['teacher']['completion_tokens']}输出token，另一次失败usage及实际账单金额不可得。逐次费用和未知量见requests.json。", '',
              '最终结果：11次新增物理请求用完，6次返回可执行模型IR，但完整闸门成功来源为0；3个受影响来源已验证仍未解决，9个未进入修复后正常来源预检阶段。第96条通过schema、类型、执行和原生字段格式，EC/EV完整匹配均false，查询引用未由其已链接规则行支持，故不改判通过。4个原PW来源仅有独立公开Horn后端证据，4个CNLI来源仅有原生fallback记录，均不能算本轮模型IR修复成功。', '',
              '无网络实际恢复命中11条新请求缓存，当前v8完整验证结果按持久化JSON值精确重算一致；没有调用、账本行或oracle增加。原账本87行、旧meta及50条oracle不变。账本完整副本上的额外请求被Cumulative96拒绝。证据：actual_restore_verified.json、hard_cap_verified.json。', '',
              '完整goal仍未达到：受影响来源整体语义预检未通过，当前20来源完整训练链条没有通过当前版本验收；正式入口兼容凭据仍属旧9eb阶段，不能作为当前4ccc版本就绪证明。闭合输入只在当前定点修复支路验证，未声称通用训练二次解析均已接入或有效。完整原需求逐项状态见docs/rr_v2/requirements_status.json。', '',
              '精确复现：使用保存的对应revision源码及seal；当前入口`python -m experiments.rr_v2_cumulative_repair`，不重启旧thinking/pilot。离线：`python -m experiments.rr_v2_offline`。原始数据/配置与版本绑定见各revision/seal.json。']
    report = ROOT / 'reports/legalskillguard_rr_v2_implementation_check_report.md'
    historical = OUT / 'report_before_cumulative_repair.md'
    if not historical.exists():
        historical.write_text(report.read_text())
    report.write_text('\n'.join(lines) + '\n')
    print(json.dumps({k: summary[k] for k in ['executor_used','remaining_authorized_requests','teacher_used','pending','repair_success_sources']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
