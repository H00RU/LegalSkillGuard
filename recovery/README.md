# Complete project recovery backup

The backup was uploaded to `H00RU/LegalSkillGuard`, branch
`backup/legal-skill-evolve-20261101`, and checked again from an independent GitHub
download. The original `main` branch is unchanged. No force-push was used.

## Contents and verification records

- Browsable source and current/historical entry points: [PROJECT_MAP.md](../PROJECT_MAP.md).
- Full workspace: `full-project/`, 58 ordered parts, 222,521 original file records,
  16,767,937,779 original file bytes, 2,876,429,131 compressed archive bytes.
- Historical sources: `historical-sources/`, 121 original source-freeze archives
  and 67 Git bundles, totalling 518,133,015 original archive/bundle bytes.
- [Final upload verification](UPLOAD_VERIFIED.json): remote commits, source/paper
  checks, independent verification of the historical supplement and preservation
  of the old main branch.
- [Full-workspace restore-stream verification](REMOTE_CONTENT_VERIFIED.json):
  all 58 remotely downloaded parts and all 222,521 archived-file records checked.
- [Exact frozen-source coverage](FROZEN_SOURCE_COVERAGE.json): every bound file
  in the current main, both controls and TEST is covered (379/379/382/549).

`archive_manifest.json` and `historical_source_manifest.json` record their local
preparation times. Their historical preparation-status fields are not the final
upload status; the later verification records above certify remote completion.

The workspace archive retains code, Git history/object storage, datasets and
ignored packets/cache, all existing runs including unfavorable outcomes, raw
teacher/native requests and responses, learned libraries, scoring records,
figures, manuscripts and registered research worktrees. The brother's writing
skills and the used Nature-writing skill are included. Research worktrees under
`.venv` are retained separately from disposable environment packages.

Not included: account credentials, private keys, external model weights, or
reinstallable Python environment folders and bytecode/test/lint caches. This is
a research-project backup, not an image of the entire server.

## Check and restore

From a fresh clone of this branch on Ubuntu:

```bash
cd recovery/full-project
sha256sum -c PARTS.SHA256
cat legal-skill-evolve-complete-20261101.tar.zst.part[0-9][0-9][0-9][0-9] | sha256sum
```

The combined archive SHA-256 must be
`d38510d3b7d7e34267897bd0274de3dfa4ee85bbe13d633fa6707adee3de7fa8`.
After all checks pass, extract into a new empty directory:

```bash
legal_restore_directory=$(mktemp -d)
cat legal-skill-evolve-complete-20261101.tar.zst.part[0-9][0-9][0-9][0-9] | zstd --decompress --long=27 | tar --extract --no-same-owner --directory "$legal_restore_directory"
```

Do not extract over an existing checkout. `project/` contains the original
workspace; other prefixes retain external worktrees and writing skills. The
snapshot is point-in-time. Later navigation and backup reports are also retained
as ordinary files in this source branch.

Recreate dependencies from `pyproject.toml`, `uv.lock` and
`ops/inference-requirements.txt`; obtain external model weights separately.
Create the runtime environment in a separate directory or a fresh code clone.
Do not remove or recreate the archived `project/.venv` tree: it contains preserved
research worktrees, not the excluded Python environment packages.
Archived Git worktree metadata contains old absolute paths. Use a fresh clone
for normal Git operations and inspect old paths before reconnecting historical
worktrees. No archived code, restored training or model service is automatically
executed by the verification process.
