"""Isolated execution of an already AST-checked, JSON-only skill helper."""
import json
import resource
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    request = json.load(sys.stdin)
    safe = {name: getattr(__import__('builtins'), name) for name in
            ('min', 'max', 'sum', 'len', 'abs', 'round', 'sorted', 'all', 'any', 'int', 'float', 'bool',
             'str', 'list', 'dict', 'range', 'enumerate', 'zip')}
    scope = {'__builtins__': safe}
    exec(compile(request['procedure'], '<learned-skill>', 'exec'), scope)
    value = scope['apply'](request['inputs'], request['premises'])
    body = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(body) > 1024 * 1024:
        raise ValueError('Skill output exceeds the execution transport limit')
    sys.stdout.write(body)


if __name__ == '__main__':
    main()
