"""Normalize the handoff packet, validate manifests and write reproducibility hashes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
plan_url = 'https://github.com/H00RU/LegalSkillGuard/blob/docs/legal-semantic-learning-20261110/reports/legal_semantic_learning_20261110/PLAN.md'

for name in ('method1_design.md', 'method1_foundation.md'):
    path = ROOT / name
    text = path.read_text(encoding='utf-8')
    text = text.replace('../legal_deterministic_validation_20261110/SERVER_SYNC.md', 'SERVER_EVIDENCE.md')
    text = text.replace('../legal_research_reframe_20261110/data_plan.md', 'data_feasibility.md')
    text = text.replace('新增机制仍是**依赖闭合的源暴露监督＋开放语义差分生成**', '新增机制是**共享内容与多角色视图分解＋联合角色差分学习**')
    path.write_text(text, encoding='utf-8', newline='\n')

protocol_path = ROOT / 'protocol.json'
protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
protocol['methods']['M1']['name'] = 'shared_semantic_fragment_delta_acquisition'
protocol['methods']['M1']['core_supervision'] = 'content_once_plus_source_preserved_multi_role_view_deltas'
protocol['methods']['M1']['same_shared_representation_AST_edit_control'] = True
protocol['metrics']['secondary'] = list(dict.fromkeys(protocol['metrics']['secondary'] + ['source_role_set_recall', 'duplicate_payload_inconsistency']))
protocol_path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

goal_path = ROOT / 'SERVER_GOAL.md'
goal = goal_path.read_text(encoding='utf-8')
goal = goal.replace('发送下面一段。`PLAN_LINK` 替换为本报告包的固定提交链接；同目录配置、方法、查新和数据清单从方案内进入。', '发送下面一段。同目录配置、方法、查新和数据清单从方案内进入；用户收到的交付消息另提供固定提交链接。')
goal = goal.replace('PLAN_LINK', plan_url).replace('M1 源差分获取', 'M1 共享语义差分获取')
goal_path.write_text(goal, encoding='utf-8', newline='\n')

manifest = json.loads((ROOT / protocol['data']['manifest']).read_text(encoding='utf-8'))
rows = manifest['items']
assert len(rows) == 448
for split, count in [('train', 256), ('dev', 64), ('test', 128)]:
    assert sum(r['split'] == split for r in rows) == count
for field in ('item_id', 'full_article_sha256', 'target_sha256'):
    assert len({r[field] for r in rows}) == 448
family_splits = {}
family_counts = {}
for r in rows:
    family_splits.setdefault(r['family_id'], set()).add(r['split'])
    family_counts[r['family_id']] = family_counts.get(r['family_id'], 0) + 1
assert all(len(v) == 1 for v in family_splits.values())
assert max(family_counts.values()) <= 16
for path in ROOT.rglob('*.json'):
    json.loads(path.read_bytes())
for path in ROOT.rglob('*'):
    if path.is_file() and path.suffix in {'.md', '.json', '.py', '.txt'}:
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))

data_dir=ROOT/'data_manifest'
data_hashes=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(data_dir.glob('*.json'))]
(data_dir/'SHA256SUMS.txt').write_text('\n'.join(data_hashes)+'\n', encoding='utf-8', newline='\n')
hashes = []
for path in sorted(ROOT.rglob('*')):
    if path.is_file() and path != ROOT/'SHA256SUMS.txt' and '__pycache__' not in path.parts:
        hashes.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.relative_to(ROOT).as_posix())
(ROOT / 'SHA256SUMS.txt').write_text('\n'.join(hashes) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'files_hashed': len(hashes), 'manifest_sources': len(rows), 'source_families': len(family_splits), 'checks': 'passed'}))
