# v16 project update — 4 November 2026

This additive update follows the previously verified v15 backup commit
`7a3f91cf4080e91da037ba7036c580b7b080c0d9` on
`backup/legal-skill-evolve-20261101`. It preserves all parent files and earlier
recovery volumes. The original `main` branch and its user-supplied review report
are not overwritten.

- [Current paper and project navigation](../../../GITHUB_LATEST.md)
- [v16 upload report](../../../docs/reports/GITHUB_V16_UPLOAD_20261104.md)
- [Snapshot scope and immutable-source checks](snapshot_summary.json)
- [New or changed local project files](changed_files_manifest.json)
- [Compressed current regular-file inventory](current_files_manifest.json.gz)
- [Independent remote verification receipt](UPLOAD_VERIFIED.json)
- [Complete supplementary-data download and reassembly](../../../artifacts/research/manuscript_revision_astra_20261104/Supplementary_Data_1_20261104.zip.parts/README.md)

All new/changed regular project files are retained directly in the commit except
the oversized 283,983,284-byte ZIP, which is represented by its seven exact,
ordered volumes. Concatenating them reproduces SHA256
`415113bac94635988f94950569ccd098634ad46d2ff756069a6de1eec391ec0e`.
No original experiment record, score, model weight or manuscript result changes
as part of synchronization. Credential files, environments, model dependencies,
Git internals and caches are excluded. An unchanged file's prior inventory hash
is reused only when its byte size and nanosecond modification time match; every
changed Git blob is independently read back and SHA256-verified after pushing.

The inventories precede the final upload receipt and this navigation document;
those final delivery records are committed separately. Inventory differences are
not instructions to delete historical files. Restoring the complete historical
workspace still uses the original recovery volumes plus the existing November 4
overlay, followed by the new/changed files in this update and ZIP reassembly.
