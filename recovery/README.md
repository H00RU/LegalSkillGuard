# Full-project recovery archive

Archive preparation is in progress. Do not treat this initial source commit as
proof that the full archive has already reached GitHub. The completed manifest
and upload-verification record will identify the actual archived files and commits.

## Scope

The recovery snapshot includes the current project's code, Git object/history
store, data (including ignored packets/cache), all current and unsuccessful runs,
teacher/native requests and responses, publications, learned libraries, evaluation
records, figures, manuscripts and research notes. Registered research worktrees
are also retained, including those stored inside the local `.venv` directory.
The brother's writing skills and the used Nature-writing skill are copied separately.

Excluded: reinstallable Python environments, bytecode/test/lint caches, external
model-weight directories, account tokens and private keys. The archive is not a
machine image and does not claim to back up every directory on the server.

## Restoration after upload completes

Archive parts will be under `recovery/full-project/`. Their ordered names, byte
sizes and SHA-256 digests will be recorded in the manifest. First verify every
part and concatenate in the manifest's order; verify the combined archive hash
before decompressing. Extract only into a newly created empty directory, never
over an existing project. The `project/` archive prefix contains the original
scientific workspace. Other prefixes contain external research-worktree and
writing-skill copies.

Recreate the Python environment from `pyproject.toml` and `uv.lock`; restore model
weights separately from their recorded upstream identifiers. The archived Git
worktree metadata contains old absolute server paths: use a fresh clone of the
GitHub source branch for normal Git operations rather than activating old paths
without checking them. No restoration or training script is run automatically.
