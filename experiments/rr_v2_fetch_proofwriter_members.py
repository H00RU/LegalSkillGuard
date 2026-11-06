"""Read just official OWA depth-5 members via HTTP ranges, verifying ZIP CRCs.

The already-running full archive download is left in place. The selected-member
hashes must later agree with that complete archive; no alternate corpus is used.
"""
from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json

ROOT = Path(__file__).resolve().parents[1]
URL = "https://aristo-data-public.s3.amazonaws.com/proofwriter/proofwriter-dataset-V2020.12.3.zip"
SIZE = 214185889
ETAG = '"abe79e94eb3205ff0978c88eeffaeedc-26"'


class OfficialRangeReader(io.RawIOBase):
    def __init__(self):
        self.position = 0
        full = ROOT / "data/cache/rr_v2/proofwriter-dataset-V2020.12.3.zip"
        self.prefix = full if full.exists() else ROOT / "data/cache/rr_v2/.proofwriter.download"

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else SIZE + offset
        if not 0 <= self.position <= SIZE:
            raise ValueError("Invalid archive seek")
        return self.position

    def tell(self):
        return self.position

    def read(self, size=-1):
        count = SIZE - self.position if size < 0 else min(size, SIZE - self.position)
        if count <= 0:
            return b""
        if self.prefix.exists() and self.prefix.stat().st_size >= self.position + count:
            with self.prefix.open("rb") as stream:
                stream.seek(self.position)
                data = stream.read(count)
        else:
            req = urllib.request.Request(URL, headers={
                "Range": f"bytes={self.position}-{self.position + count - 1}", "If-Match": ETAG})
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status != 206 or response.headers.get("ETag") != ETAG:
                    raise ValueError("Official archive identity/range response differs")
                data = response.read()
        if len(data) != count:
            raise ValueError("Incomplete official archive range")
        self.position += count
        return data


def main():
    destination = ROOT / "data/cache/rr_v2/ProofWriter"
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    with zipfile.ZipFile(OfficialRangeReader()) as archive:
        names = [f"proofwriter-dataset-V2020.12.3/OWA/depth-5/meta-{s}.jsonl"
                 for s in ("train", "dev", "test")]
        names += [n for n in archive.namelist() if Path(n).name.casefold() in {"license", "license.txt", "readme.md", "readme.txt"}]
        for name in names:
            target = destination / Path(name).name
            data = archive.read(name)  # ZipFile verifies the member CRC.
            if target.exists() and target.read_bytes() != data:
                raise ValueError("Existing official member differs")
            if not target.exists():
                with target.open("xb") as stream:
                    stream.write(data)
            files.append({"member": name, "sha256": hashlib.sha256(data).hexdigest(),
                          "bytes": len(data), "crc32": archive.getinfo(name).CRC})
            print(Path(name).name, len(data), flush=True)
    immutable_json(destination / "acquisition.json", {"url": URL, "archive_bytes": SIZE,
                    "etag": ETAG, "member_crc_verified": True, "files": files,
                    "full_archive_sha256_verification_pending": True})
    with (destination / "meta-train.jsonl").open() as stream:
        example = json.loads(stream.readline())
    print("training schema keys:", sorted(example))
    print("triple fields:", sorted(next(iter(example["triples"].values()))))
    print("question fields:", sorted(next(iter(example["questions"].values()))))


if __name__ == "__main__":
    main()
