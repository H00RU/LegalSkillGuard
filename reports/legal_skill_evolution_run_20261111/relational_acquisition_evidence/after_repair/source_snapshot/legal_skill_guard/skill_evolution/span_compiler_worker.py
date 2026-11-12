"""Isolated pure text/record execution, shared by compiler and free control."""
import json
import re
import resource
import sys


class SourceValues(dict):
    """Unknown source fields cannot silently become defaults or absence."""
    def __init__(self, values, unresolved):
        super().__init__(values)
        self.unresolved = set(unresolved)

    def check(self, key):
        if key in self.unresolved:raise ValueError('Unresolved source field accessed: ' + key)

    def __getitem__(self, key):
        self.check(key);return super().__getitem__(key)

    def get(self, key, default=None):
        self.check(key);return super().get(key, default)

    def __contains__(self, key):
        self.check(key);return super().__contains__(key)

    def whole(self):
        if self.unresolved:raise ValueError('Whole-map observation of unresolved source values')

    def __iter__(self):
        self.whole();return super().__iter__()

    def __len__(self):
        self.whole();return super().__len__()

    def keys(self):
        self.whole();return super().keys()

    def values(self):
        self.whole();return super().values()

    def items(self):
        self.whole();return super().items()

    def __repr__(self):
        self.whole();return super().__repr__()

    __str__ = __repr__

    def pop(self, key, *default):
        self.check(key);return super().pop(key, *default)

    def __setitem__(self, key, value):
        self.check(key);return super().__setitem__(key, value)

    def update(self, values):
        for key in values:self.check(key)
        return super().update(values)


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    request = json.load(sys.stdin)
    for record in request['premises'].get('records', []):
        if record.get('unresolved_fields'):
            record['values'] = SourceValues(record['values'], record['unresolved_fields'])
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
