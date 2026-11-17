"""Evaluate the unchanged pure program over demanded finite input domains.

Unknown fields raise at access, before bool()/arithmetic can default them.
Branching enumerates declared possible values, never asserts an observed value.
"""
from copy import deepcopy
import json
import resource
import sys


class MissingInput(Exception):
    def __init__(self, path):
        self.path = tuple(path)


class TrackedDict(dict):
    def __init__(self, value, path=()):
        super().__init__(value)
        self.path = path

    def __getitem__(self, key):
        return tracked(super().__getitem__(key), (*self.path, key))

    def get(self, key, default=None):
        return self[key] if key in self else default


class TrackedList(list):
    def __init__(self, value, path):
        super().__init__(value)
        self.path = path

    def __getitem__(self, key):
        if not isinstance(key, int):
            raise ValueError('Partial evaluation requires explicit indexed array access')
        return tracked(super().__getitem__(key), (*self.path, key))

    def __iter__(self):
        return (self[index] for index in range(len(self)))


def tracked(value, path):
    if value is None:
        raise MissingInput(path)
    if isinstance(value, dict):
        return TrackedDict(value, path)
    if isinstance(value, list):
        return TrackedList(value, path)
    return value


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    request = json.load(sys.stdin)
    safe = {name: getattr(__import__('builtins'), name) for name in
        ('min', 'max', 'sum', 'len', 'abs', 'round', 'sorted', 'all', 'any', 'int', 'float',
         'bool', 'str', 'list', 'dict', 'range', 'enumerate', 'zip')}
    scope = {'__builtins__': safe}
    exec(compile(request['procedure'], '<unchanged-frozen-consumer>', 'exec'), scope)
    domains = {tuple(row['path']): row['values'] for row in request['domains']}
    stack, results, accessed, visited, reason = [request['inputs']], {}, set(), 0, None
    while stack:
        if visited >= request['max_worlds']:
            reason = 'Declared finite partial-evaluation work limit reached'
            break
        inputs = stack.pop()
        visited += 1
        try:
            result = scope['apply'](TrackedDict(inputs), request['premises'])
            key = json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False)
            results.setdefault(key, {'result': result, 'completion_witness': inputs})
            if len(results) > 1:
                reason = 'Different admissible completions change the frozen program result'
                break
        except MissingInput as error:
            accessed.add(error.path)
            values = domains.get(error.path)
            if not values:
                reason = 'A demanded input lacks an explicit finite domain: ' + repr(error.path)
                break
            for value in values:
                branch = deepcopy(inputs)
                parent = branch
                for key in error.path[:-1]:
                    parent = parent[key]
                parent[error.path[-1]] = value
                stack.append(branch)
    handled = reason is None and not stack and len(results) == 1
    values = list(results.values())
    print(json.dumps({'handled': handled, 'answer': values[0]['result']['answer'] if handled else None,
        'reason': reason, 'visited_partial_worlds': visited,
        'demanded_unknown_paths': [list(path) for path in sorted(accessed, key=repr)],
        'contrasting_or_representative_completions': values,
        'unknown_inputs_not_asserted_false': True,
        'unique_result_over_all_declared_completions': handled}, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
