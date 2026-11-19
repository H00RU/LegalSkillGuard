"""Resume the bound use/license comparison using durable executor records."""

from pathlib import Path
import sqlite3

from experiments import convergence_revision5_cni_use_and_license as study
from legal_skill_guard.rr.checkpoint import immutable_json


def run():
    pointer = study.read(study.POINTER)
    out = study.ROOT / pointer['artifact_root']
    binding = study.read(out / 'binding.json')
    assert study.digest(binding) == out.name
    first = f'convergence-revision5-CNI-use-and-license-{out.name[:16]}:0:fixed'
    if (out / 'terminal.json').exists():
        return
    with sqlite3.connect(study.LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        role, status = db.execute('select role,status from calls where id=?', (first,)).fetchone()
        assert (role, status) == ('executor', 'completed')
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
    receipt = {'settled_original_call': first, 'original_binding_sha256': study.sha(out / 'binding.json'),
               'resume_source_sha256': study.sha(Path(__file__)),
               'scope': 'Remove only the runtime cache-hit flag from the client return value before archive equality. The runner independently verifies the full durable response and exact request.'}
    immutable_json(out / 'resume_transport_receipt.json', receipt)

    generate = study.FrozenExecutor.generate

    def durable_record(executor, *args, **kwargs):
        result = generate(executor, *args, **kwargs)
        assert type(result.get('cache_hit')) is bool
        return {k: v for k, v in result.items() if k != 'cache_hit'}

    study.FrozenExecutor.generate = durable_record
    try:
        study.run(True)
    finally:
        study.FrozenExecutor.generate = generate


if __name__ == '__main__':
    run()
