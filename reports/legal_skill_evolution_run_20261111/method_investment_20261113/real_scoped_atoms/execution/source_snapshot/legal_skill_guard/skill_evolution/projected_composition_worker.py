"""Isolated exhaustive output projection, with a real rule-subset witness."""
import json
import math
import resource
import sys
import time

import clingo


def main():
    request = json.load(sys.stdin)
    seconds = request['timeout_seconds']
    resource.setrlimit(resource.RLIMIT_CPU, (math.ceil(seconds) + 1, math.ceil(seconds) + 2))
    resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    started = time.monotonic()
    control = clingo.Control(['--warn=none', '--models=0', '--project=project'])
    control.add('base', [], request['program'])
    control.ground([('base', [])])
    models = []
    def on_model(model):
        models.append(sorted(map(str, model.symbols(shown=True))))
    with control.solve(on_model=on_model, async_=True) as handle:
        finished = handle.wait(max(0, seconds - (time.monotonic() - started)))
        if not finished:
            handle.cancel()
        result = handle.get()
    complete = finished and result.exhausted and not result.interrupted and not result.unknown
    print(json.dumps({'status': 'complete' if complete else 'timeout',
        'models': models, 'exhausted': result.exhausted,
        'seconds': time.monotonic() - started, 'clingo_version': clingo.__version__}))


if __name__ == '__main__':
    main()
