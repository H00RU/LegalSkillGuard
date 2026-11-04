# November 4 project recovery supplement

This is an additive update to the original full recovery backup on `backup/legal-skill-evolve-20261101`. Earlier commits, original recovery volumes and `main` are retained. The current paper is indexed in [GITHUB_LATEST.md](../../../GITHUB_LATEST.md).

## Contents

- Current regular project-file inventory: **209,982 files**, **12,704,544,737 bytes**, excluding reinstallable environments, Git internals, caches and credential files.
- New or byte-changed project files relative to the original November 1 full recovery manifest: **20,919 files**, **356,292,394 uncompressed bytes**.
- The incremental gzip-tar archive is **113,928,431 bytes** and is split into **three ordered volumes**, each at most 45 MiB.
- Combined archive SHA256: `7a1c523932bad8edcdc1104a3d5ba4f624bde6c9dff3afc0c6967e3cd7ce033a`.
- All **20,919** archived project-file members were decompressed and individually checked against their recorded SHA256 before upload.
- The current main-method 379-file and SkillCommit 648-file frozen bindings are covered and unchanged. They overlap; these are not 1,027 distinct files.

This overlay includes the current SkillCommit source/configuration, complete retained run and retired attempts, current paper exports, results and audit evidence. Unchanged older files remain recoverable from the original backup rather than being uploaded again. Account keys, model weights and reinstallable environments are not added by this update.

The archive snapshot predates this recovery README and the eventual upload receipt. Those delivery documents are stored directly in the branch and must not be claimed as members of the earlier snapshot.

## Files

- [Archive/volume hashes and scope](archive_manifest.json)
- [Pre-archive snapshot summary](snapshot_summary.json)
- [Changed-file SHA256 manifest](changed_files_manifest.json)
- [Compressed full current-file inventory](current_files_manifest.json.gz)
- [Ordered archive volumes](parts/)
- [Original recovery instructions](../../README.md)

## Recovery

First recover the original November 1 full project using the original instructions. Verify the three volume hashes, concatenate volumes in numeric order, and verify the combined SHA256 above. The resulting gzip-tar contains `project/` paths that overlay the recovered project and `metadata/` containing the snapshot inventories. Restore into a separate recovery directory and verify file hashes before using it as the active project.

The `missing_from_current_relative_to_old_project_manifest` list is descriptive, includes deliberately excluded categories, and is **not** an instruction to delete files. This backup does not delete old experiments or historical source. The original full backup remains the source for Git history and registered external worktrees; this update is not a new capture of every external runtime directory.

The current manuscript is v15. The separate quality review has not been applied to the manuscript, and no model, training, scoring or scientific-results changes were made for this upload.
