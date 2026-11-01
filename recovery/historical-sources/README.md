# Historical frozen source and Git-history backups

This supplement preserves 121 original source-freeze archives and 67 original Git
bundles from the project's existing backup collection. These are retained in
addition to the complete current-workspace snapshot, because an older experiment
may refer to a source version that was later edited in the working directory.
Repeated hourly full-state archives are not duplicated here.

`historical_source_manifest.json` records every original filename, byte size,
SHA-256 digest and its stored file(s). One source archive exceeds the chosen
48-MiB volume size and is stored as two ordered parts; all other original files
are retained directly. Reassemble split files in the manifest's order and verify
the original hash before opening them. Original backup files remain unchanged.

All 62,706 regular source-archive members were read during credential-pattern
screening. The advertised commit heads of all Git bundles were also confirmed
present in the original Git object store, whose 5,475 blobs were screened before
upload. No account credentials or private keys are recovery materials.

The complete workspace archive already preserves the original `.git` store.
For an independent Git reconstruction, full bundles and delta bundles retain
their original prerequisite semantics; a delta bundle alone is not a full clone.
The manifest records local preparation. Remote completion and independent
re-download checks are certified separately in the final verification record.
