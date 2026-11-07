"""Measure complete original inputs with the actual serving tokenizer only."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.controls import ARMS
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_run import load_executor_lock
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.source_inference import _compiler_request


def main():
    root = Path(__file__).resolve().parents[2]
    cfg = json.loads((root / 'configs/rr_v2_preflight.json').read_text())
    manifest = json.loads((root / cfg['source_manifest']).read_text())
    path = root / 'data/packets/rr_v2/public_train.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest['packet_sha256']['public_train']
    packet = json.loads(path.read_text())
    assert packet['split'] == 'train' and not packet['contains_gold_or_reference_program']
    sources = {source['key']: source for source in packet['sources']}
    library_file = root / 'artifacts/rr_v2_formal_build_20261106/run_citation_fix/B8.frozen.json'
    frozen = json.loads(library_file.read_text())
    assert frozen['sha256'] == digest(frozen['content'])
    config = cfg['executor']
    load_executor_lock(root, config)
    executor = MethodExecutor(None, root / 'artifacts/rr_method_runtime_20261107/tokenizer_only', config)
    last = {}
    def measure(messages, *, thinking):
        assert thinking is False
        result = executor.tokenize(messages, thinking=False)
        last.update(result)
        return result
    before = science_files(root)
    rows = []
    for source_id in manifest['formal_train_order']:
        source = sources[source_id]
        messages, _, _ = _compiler_request(source, frozen['content'], ARMS['M11'], None, None,
            measure, config, False)
        rows.append({'source': source_id, 'dataset': source['dataset'], 'input_tokens': last['count'],
            'input_sha256': digest(messages)})
    assert len(rows) == 128 and before == science_files(root)
    receipt = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'rows': rows, 'files': before,
        'all_fit': True, 'maximum_input_tokens': max(row['input_tokens'] for row in rows),
        'input_budget': config['context_tokens'] - config['max_tokens'], 'reserved_output_tokens': config['max_tokens'],
        'scope': 'Original128 complete public sources and historical B8 menu for capacity only; actual OFF serving tokenizer, no source truncation, grading, generation or future-library injection into an experiment.',
        'capacity_check_library_file_sha256': hashlib.sha256(library_file.read_bytes()).hexdigest(),
        'source_bytes_unchanged': True, 'new_model_calls': 0, 'new_oracle_views': 0,
        'readiness': False}
    Path(__file__).with_name('source_code_input_budget_v2.json').write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + '\n')
    print(json.dumps({key: receipt[key] for key in ['all_fit', 'maximum_input_tokens', 'input_budget', 'new_model_calls']}))


if __name__ == '__main__':
    main()
