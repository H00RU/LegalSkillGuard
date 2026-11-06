"""Recheck saved ContractNLI responses against wire schema and parser; read only."""
import json
from pathlib import Path

import jsonschema

from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.engine import analyze, proposal_schema

root = Path(__file__).resolve().parents[3]
data = PreflightData(root, root / 'reports/rr_v2_evidence/data_manifest.json')
rows = []
for item in json.loads((root / 'reports/rr_v2_evidence/semantic_preflight/source_status.json').read_text()):
    if item['dataset'] != 'ContractNLI':
        continue
    source = data.public(item['source'])
    record = json.loads((root / item['source_record']).read_text())
    raw = record['calls'][-1]['raw_content']
    proposal = json.loads(raw)
    jsonschema.validate(proposal, proposal_schema(source['dataset'], source=source))
    parsed = analyze(source, raw)
    rows.append({'index': item['index'], 'source': item['source'], 'wire_schema_accepts': True,
                 'program_kind': proposal['program']['kind'], 'interfaces': proposal['interfaces'],
                 'parser_program_status': parsed['program_status'],
                 'parser_diagnostics': parsed['diagnostics'], 'native_answer': parsed['answer']})
(root / 'reports/rr_v2_evidence/readiness_review/contract_mismatch.json').write_text(
    json.dumps({'new_model_calls': 0, 'records': rows}, ensure_ascii=False, indent=2) + '\n')
assert sum(x['parser_program_status'] == 'parse_failure' for x in rows) == 3
assert rows[-1]['parser_program_status'] == 'unsupported_no_certificate'
print('4 saved responses accepted by wire schema; 3 rejected by parser; no model calls')
