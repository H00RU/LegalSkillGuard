"""Isolated batch execution of one previously validated frozen pure consumer."""
import json
import resource
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    request = json.load(sys.stdin)
    if len(request['calls']) > 20000:
        raise ValueError('The declared finite module exceeds this batch execution limit')
    safe = {name: getattr(__import__('builtins'), name) for name in
            ('min', 'max', 'sum', 'len', 'abs', 'round', 'sorted', 'all', 'any', 'int', 'float', 'bool',
             'str', 'list', 'dict', 'range', 'enumerate', 'zip')}
    scope = {'__builtins__': safe}
    exec(compile(request['procedure'], '<fixed-audited-consumer>', 'exec'), scope)
    values = [scope['apply'](call['inputs'], request['premises']) for call in request['calls']]
    body = json.dumps(values, ensure_ascii=False, allow_nan=False)
    if len(body) > 32 * 1024 * 1024:
        raise ValueError('Consumer table exceeds the finite execution transport')
    sys.stdout.write(body)


if __name__ == '__main__':
    main()
