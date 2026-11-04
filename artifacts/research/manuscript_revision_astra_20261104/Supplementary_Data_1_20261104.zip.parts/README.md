# Supplementary Data 1 — complete download

The original ZIP is 283,983,284 bytes, so GitHub stores it as seven ordered,
losslessly split volumes. Download **all seven parts** below, together with
[`parts_manifest.json`](parts_manifest.json), into one directory. The PDF and
Word manuscripts are separate, directly viewable files in the
[v16 manuscript directory](../../manuscript_review_20261030/utility_v6_astra_revision_v16_delivery_20261104/).

1. [Part 001](Supplementary_Data_1_20261104.zip.part-001)
2. [Part 002](Supplementary_Data_1_20261104.zip.part-002)
3. [Part 003](Supplementary_Data_1_20261104.zip.part-003)
4. [Part 004](Supplementary_Data_1_20261104.zip.part-004)
5. [Part 005](Supplementary_Data_1_20261104.zip.part-005)
6. [Part 006](Supplementary_Data_1_20261104.zip.part-006)
7. [Part 007](Supplementary_Data_1_20261104.zip.part-007)

Each of the first six parts is 45 MiB; the last is smaller. Use GitHub's
**Download raw file** button for each binary, or clone this branch. Reassemble
and verify with Python 3 from the download directory:

```python
import hashlib
import json
from pathlib import Path

manifest = json.loads(Path('parts_manifest.json').read_text())
digest = hashlib.sha256()
with Path(manifest['original_filename']).open('xb') as output:
    for part in manifest['parts']:
        data = Path(part['name']).read_bytes()
        assert len(data) == part['bytes']
        assert hashlib.sha256(data).hexdigest() == part['sha256']
        output.write(data)
        digest.update(data)
assert digest.hexdigest() == manifest['sha256']
print('Complete ZIP verified:', digest.hexdigest())
```

The reconstructed ZIP's SHA256 is
`415113bac94635988f94950569ccd098634ad46d2ff756069a6de1eec391ec0e`.
Extract it into a new directory and follow the included
`artifacts/research/manuscript_revision_astra_20261104/SUPPLEMENT_README.md`.
The archive contains the complete B1/B8 libraries, original predictions, scorer,
source/configuration bindings and offline reproduction scripts. It requires no
new model call for score and interval checks. The source ZIP and all scientific
results are unchanged by this upload split.
