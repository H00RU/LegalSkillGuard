"""Index prior prompt/packet exposure, including studies before this ledger.

Only hashes and counts leave this audit. Historical annotation strings are not
printed or used to choose candidates; prospective stock is excluded entirely.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

from legal_skill_guard.skill_evolution.teacher_transport import unpack, unpack_programs
from legal_skill_guard.skill_evolution.observation_teacher_transport import unpack_task

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/two_method_followthrough_20261116/exposure'
INPUT_NAMES = {'request.json', 'wire_request.json', 'teacher_task.json',
               'public_train.json', 'public_dev.json', 'public_test.json', 'input_packet.json'}
SOURCE_KEY = re.compile(r'^(?:OpenExempt|SARA_v2_Binary|ContractNLI|RuleArena_Airline|MAUD):[0-9a-f]{64}$')


def normalized_hash(text):
    return hashlib.sha256(' '.join(text.split()).encode()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    roots = ['artifacts', 'history', 'data/packets']
    engineering = Path('/media/sangfor/vdb/legal-skill-backups/workspace_unification_20261112/former_engineering_worktree')
    if engineering.is_dir():
        roots.append(str(engineering))
    listing = subprocess.run(['rg', '--files', '-uuu', *roots],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    paths = sorted(p for p in listing if Path(p).name in INPUT_NAMES
                   and 'two_method_followthrough_20261116' not in p)
    strings, keys, seen_files, failures, files = set(), set(), set(), [], []
    decoded = 0
    def walk(node, depth=0):
        nonlocal decoded
        if depth > 100:
            raise ValueError('Historical request exceeds the bounded decoding depth')
        if isinstance(node, dict):
            if node.get('program_encoding') == 'exact_python_and_source_segments_v2':
                walk(unpack_programs(node), depth + 1)
                decoded += 1
                return
            if node.get('observation_schema_encoding') == 'canonical_JSON_schema_AST_v1':
                walk(unpack_task(node), depth + 1)
                decoded += 1
                return
            if node.get('encoding') in ('lossless_shared_JSON_values_v2', 'lossless_shared_JSON_values_v3'):
                walk(unpack(node), depth + 1)
                decoded += 1
                return
            for key, value in node.items():
                if isinstance(key, str) and SOURCE_KEY.fullmatch(key):
                    keys.add(key)
                if key == 'body_b64' and isinstance(value, str):
                    try:
                        walk(json.loads(base64.b64decode(value)), depth + 1)
                    except (ValueError, UnicodeError):
                        pass
                else:
                    walk(value, depth + 1)
        elif isinstance(node, list):
            if node and all(isinstance(value, dict) and isinstance(value.get('text'), str) for value in node):
                grouped = {}
                for i, value in enumerate(node):
                    grouped.setdefault(value.get('field', 'source_text'), []).append(
                        (value.get('start', value.get('id', i)), value['text']))
                for values in grouped.values():
                    strings.add(normalized_hash(' '.join(text for i, text in sorted(values))))
            for value in node:
                walk(value, depth + 1)
        elif isinstance(node, str):
            if SOURCE_KEY.fullmatch(node):
                keys.add(node)
            if len(node) >= 32:
                strings.add(normalized_hash(node))
            body = node.strip()
            if len(body) > 32 and body[:1] in ('{', '['):
                try:
                    parsed = json.loads(body)
                except (ValueError, RecursionError):
                    return
                if isinstance(parsed, (dict, list)):
                    decoded += 1
                    walk(parsed, depth + 1)
    started = time.monotonic()
    for index, name in enumerate(paths, 1):
        path = ROOT / name
        payload = path.read_bytes()
        h = hashlib.sha256(payload).hexdigest()
        files.append({'path': name, 'sha256': h, 'bytes': len(payload)})
        if h not in seen_files:
            seen_files.add(h)
            try:
                walk(json.loads(payload))
            except (ValueError, TypeError, RecursionError) as error:
                failures.append({'path': name, 'error': type(error).__name__ + ': ' + str(error)[:200]})
        if index % 5000 == 0:
            print(json.dumps({'historical_inputs_scanned': index, 'unique_files': len(seen_files),
                              'normalized_text_hashes': len(strings), 'decode_failures': len(failures)}), flush=True)
    result = {'scope': 'Existing project, in-project histories and the documented read-only former engineering archive',
              'roots': roots,
              'input_files': files, 'unique_file_hashes': len(seen_files),
              'normalized_text_hashes': sorted(strings), 'source_keys': sorted(keys),
              'nested_encodings_decoded': decoded, 'failures': failures,
              'elapsed_seconds': time.monotonic() - started,
              'prospective_inventory_excluded': True,
              'labels_printed_or_used_for_selection': False, 'new_model_calls': 0,
              'boundary': 'This conservative prompt/packet index supplements the continuous ledger; source/template isolation must still be checked when assigning splits.'}
    (OUT / 'historical_exposure_index.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'historical_inputs_scanned': len(paths), 'unique_files': len(seen_files),
                      'normalized_text_hashes': len(strings), 'source_keys': len(keys),
                      'decode_failures': len(failures), 'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    main()
