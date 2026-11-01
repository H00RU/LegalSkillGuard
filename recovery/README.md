# Full-project recovery archive

The complete local archive has passed its compression-checksum test: 222,521 files,
16,767,937,779 original file bytes, compressed to 2,876,429,131 bytes in 58 ordered
parts. Each part is at most 48 MiB. Upload is in progress; the later
`UPLOAD_VERIFIED.json` record, not this preparation note, will certify remote
completion and independent re-download verification.

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

## Verification and restoration after upload completes

Archive parts are under `recovery/full-project/`. `archive_manifest.json` records
their ordered names, byte sizes and SHA-256 digests. `files_manifest.json.gz`
records the individual archived-file hashes. The local-creation status in
`archive_manifest.json` is historical; remote upload status is recorded separately.

On Ubuntu, from a fresh clone of this branch:

```bash
cd recovery/full-project
sha256sum -c PARTS.SHA256
cat legal-skill-evolve-complete-20261101.tar.zst.part[0-9][0-9][0-9][0-9] | sha256sum
```

The combined hash must be
`d38510d3b7d7e34267897bd0274de3dfa4ee85bbe13d633fa6707adee3de7fa8`.
After all checks pass, extract into a new empty temporary directory:

```bash
legal_restore_directory=$(mktemp -d)
cat legal-skill-evolve-complete-20261101.tar.zst.part[0-9][0-9][0-9][0-9] | zstd --decompress --long=27 | tar --extract --no-same-owner --directory "$legal_restore_directory"
```

Never extract over an existing project. The `project/` archive prefix contains
the original scientific workspace. Other prefixes contain external research
worktree and writing-skill copies. The archive is a point-in-time snapshot;
later backup-navigation documents, including `PROJECT_MAP.md`, are also retained
as ordinary files in this GitHub branch.

Recreate the Python environment from `pyproject.toml` and `uv.lock`; restore model
weights separately from their recorded upstream identifiers. The archived Git
worktree metadata contains old absolute server paths: use a fresh clone of the
GitHub source branch for normal Git operations rather than activating old paths
without checking them. No restoration or training script is run automatically.
