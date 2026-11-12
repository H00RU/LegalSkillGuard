"""Isolated pure text/record execution, shared by compiler and free control."""
import json
import re
import resource
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    request = json.load(sys.stdin)
    import builtins
    names = ('min', 'max', 'sum', 'len', 'abs', 'round', 'sorted', 'all', 'any',
        'int', 'float', 'bool', 'str', 'list', 'dict', 'set', 'tuple', 'range',
        'enumerate', 'zip', 'isinstance', 'ValueError', 'KeyError', 'TypeError')
    scope = {'__builtins__': {n: getattr(builtins, n) for n in names}, 're': re}
    exec(compile(request['procedure'], '<learned-source-procedure>', 'exec'), scope)
    value = scope['apply'](request['inputs'], request['premises'])
    body = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(body) > 1024 * 1024:raise ValueError('Oversized learned result')
    sys.stdout.write(body)


if __name__ == '__main__':main()
