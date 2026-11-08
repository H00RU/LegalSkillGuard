"""Check whether actual EOF delimiter errors admit a format-only recovery.

This audit changes no production parser, raw response, source record or ledger.
It adds only forced closing delimiters at EOF, never values or expressions.
"""
import ast
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import tokenize
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def guard(event, args):
    if event in {'socket.connect', 'socket.bind', 'socket.sendto', 'subprocess.Popen',
                 'os.system', 'os.posix_spawn', 'os.exec'}:
        raise RuntimeError('This offline audit cannot dispatch models or subprocesses')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = Path(args[0].decode() if isinstance(args[0], bytes) else args[0]).resolve()
        if path.name in {'dev.json', 'test.json'} and path.parent.name == 'grading_only':
            raise RuntimeError('Held-out labels are unavailable to this audit')


sys.addaudithook(guard)
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.pal_frontend import decode_pal_text, lower_pal
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.source_execution import assess_source
from legal_skill_guard.rr.source_program import compile_source


def closers_at_eof(code):
    stack = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type != tokenize.OP:
                continue
            if token.string in ('(', '[', '{'):
                stack.append(token.string)
            elif token.string in (')', ']', '}'):
                if not stack or {'(': ')', '[': ']', '{': '}'}[stack.pop()] != token.string:
                    return None
    except tokenize.TokenError as error:
        if error.args[0] != 'EOF in multi-line statement':
            return None
    if not stack:
        return None
    return ''.join({'(': ')', '[': ']', '{': '}'}[item] for item in reversed(stack))


def main():
    run_id = 'method_runtime_reference_v7_20261109'
    stage = ROOT / 'artifacts/rr_method_runtime_20261107' / run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(ROOT) == seal['files']
    public = {s['key']: s for s in json.loads((ROOT / 'data/packets/rr_v2/public_train.json').read_text())['sources']}
    library = SkillLibrary(stage='formal_train')
    rows = []
    examined = 0
    for position, sid in enumerate(seal['sources']['train'], 1):
        path = stage / 'build/sources' / (digest(sid) + '.json')
        if not path.exists():
            break
        record = json.loads(path.read_text())
        assert record['library_before_hash'] == digest(library.export())
        examined += 1
        for call in record['prediction']['calls']:
            error = call['analysis'].get('error') or {}
            if not isinstance(error, dict) or 'Incomplete or invalid Python source' not in error.get('error', ''):
                continue
            row = {'source_position': position, 'source': sid, 'step': call['step'],
                'original_error': error,
                'original_raw_sha256': hashlib.sha256(call['raw_content'].encode()).hexdigest(),
                'production_or_original_output_modified': False}
            try:
                code = decode_pal_text(call['raw_content'])
                closing = closers_at_eof(code)
                if not closing:
                    row['result'] = 'no_forced_delimiter_only_recovery'
                else:
                    candidate = code.rstrip() + closing + '\n'
                    row.update(appended_EOF_delimiters=closing, candidate_code=candidate)
                    tree = ast.parse(candidate)
                    last = tree.body[-1]
                    if not isinstance(last, ast.Assign) or len(last.targets) != 1 or not isinstance(last.targets[0], ast.Name) or last.targets[0].id != 'query':
                        raise ValueError('A missing query or later declaration cannot be supplied by this audit')
                    program, adaptations = lower_pal(public[sid], candidate)
                    compiled = compile_source(public[sid], program, library=library.export())
                    assessment = assess_source(compiled, compilation='answer_separating', seconds=0.1)
                    row.update(result='typed_after_EOF_delimiters_only',
                        assessment_status=assessment['status'], certificate_issued=bool(assessment.get('certificate')),
                        source_semantic_success_not_inferred=True)
            except (ValueError, TypeError, KeyError, SyntaxError, ValidationError) as exc:
                row.update(result='still_rejected_after_format_only_candidate',
                    error_type=type(exc).__name__,
                    error=exc.message if isinstance(exc, ValidationError) else str(exc))
            rows.append(row)
        if record['learning'].get('learned_pattern'):
            library.add(record['learning']['learned_pattern'], source=sid)
        for material in record.get('compiler_learning', {}).get('templates', []):
            library.add_compiler_template(material)
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'run_id': run_id,
        'prefix_sources_examined': examined, 'rows': rows,
        'typed_candidates': sum(r['result'] == 'typed_after_EOF_delimiters_only' for r in rows),
        'production_parser_changed': False, 'original_results_unchanged': True,
        'semantic_checks_relaxed': False, 'new_model_or_oracle_calls': 0,
        'DEV_or_TEST_labels_read': False, 'goal_complete': False}
    path = Path(__file__).with_name('reference_dangling_delimiters_v7_offline.json')
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
