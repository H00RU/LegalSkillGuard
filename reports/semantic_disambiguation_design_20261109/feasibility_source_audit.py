"""Read-only audit of previously published TRAIN responses; no model requests."""
import collections
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'outputs/audit_final_repo/artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109'
out = {'code_snapshot': '6c2f2a5dce7e9e78c6aae6ccc000a3eb769f99c2',
       'latest_report_snapshot': 'ced5c965e85103d80242b28852b29a1637696e5c',
       'counting': 'Sources with at least one observed error, nonexclusive; not the true semantic error prevalence',
       'source_status': {}, 'error_sources': {}}
with (ROOT / 'outputs/efficacy_source_states.csv').open(encoding='utf-8') as handle:
    rows = list(csv.DictReader(handle))
for split in ('TRAIN', 'DEV'):
    stats = collections.defaultdict(collections.Counter)
    for row in rows:
        if row['partition'] == split:
            stats[row['source'].split(':')[0]][row['original_program_status']] += 1
    out['source_status'][split] = {k: dict(v) for k, v in stats.items()}
stats = collections.defaultdict(collections.Counter)
for file in sorted((RUN / 'build/sources').glob('*.json')):
    record = json.loads(file.read_text(encoding='utf-8'))
    seen = set()
    for call in record['calls']:
        error = call.get('analysis', {}).get('error')
        message = error.get('error', str(error)) if isinstance(error, dict) else str(error or '')
        if not message:
            continue
        if 'Public literal grounding failed' in message:
            kind = 'literal_grounding'
        elif 'exact source quote' in message or 'verbatim fact evidence' in message:
            kind = 'verbatim_quote'
        elif 'trailing source IDs' in message:
            kind = 'missing_source_annotation'
        elif 'single ==' in message:
            kind = 'unsupported_comparison'
        elif 'Incomplete or invalid Python' in message:
            kind = 'invalid_python'
        elif 'Duplicate declaration' in message:
            kind = 'duplicate_name'
        else:
            kind = 'other'
        seen.add(kind)
    for kind in seen:
        stats[record['dataset']][kind] += 1
out['error_sources'] = {k: dict(v) for k, v in stats.items()}
(Path(__file__).parent / 'feasibility_source_audit.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False, indent=2))
