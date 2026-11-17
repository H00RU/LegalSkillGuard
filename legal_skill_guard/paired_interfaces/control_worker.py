"""Isolated composition worker; neural predicates use an explicit JSON RPC."""
import json
import re
import resource
import sys

from legal_skill_guard.paired_interfaces.control_programs import BUILTINS, validate_program


def main():
    message = json.loads(sys.stdin.readline())
    program, inputs = message['program'], message['inputs']
    validate_program(program)
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    safe = {name: getattr(__import__('builtins'), name) for name in BUILTINS}
    extractors = {}
    for item in program['extractors']:
        scope = {'__builtins__': safe, 're': re}
        exec(compile(item['code'], '<control-extractor>', 'exec'), scope)
        extractors[item['id']] = scope['extract']
    sequence = 0
    def callback(kind, identity, value):
        nonlocal sequence
        event = {'type': kind, 'sequence': sequence,
                 'predicate_id' if kind == 'predicate' else 'tool_id': identity, 'input': value}
        sys.stdout.write(json.dumps(event, ensure_ascii=False) + '\n'); sys.stdout.flush()
        sequence += 1
        reply = json.loads(sys.stdin.readline())
        return reply['value']
    def predict(identity, value):
        return callback('predicate', identity, value)
    def apply_legal(identity, value):
        return callback('legal_tool', identity, value)
    scope = {'__builtins__': safe, 're': re, 'apply_legal': apply_legal}
    exec(compile(program['composition'], '<control-composition>', 'exec'), scope)
    answer = scope['compose'](inputs, predict, extractors)
    sys.stdout.write(json.dumps({'type': 'result', 'answer': answer}, ensure_ascii=False) + '\n')
    sys.stdout.flush()


if __name__ == '__main__':
    main()
