"""Fetch only pinned public data bytes listed in an acquisition catalog."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def acquire(catalog: dict) -> list[dict]:
    receipts = []
    for entry in catalog["artifacts"]:
        target = (ROOT / entry["destination"]).resolve()
        if not target.is_relative_to(ROOT / "data/cache"):
            raise ValueError("Raw artifact destination must be within this worktree cache")
        if not entry["url"].startswith("https://") or len(entry["sha256"]) != 64:
            raise ValueError("HTTPS URL and pinned SHA256 are required")
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("Existing raw artifact differs; never replace it silently")
            receipts.append({"destination": entry["destination"], "status": "verified_existing"})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=target.parent, prefix=".acquire-")
        h = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as out, urllib.request.urlopen(entry["url"], timeout=30) as response:
                while block := response.read(1024 * 1024):
                    h.update(block)
                    out.write(block)
                out.flush()
                os.fsync(out.fileno())
            if h.hexdigest() != entry["sha256"]:
                raise ValueError("Downloaded raw artifact SHA256 mismatch")
            os.link(temp, target)
            receipts.append({"destination": entry["destination"], "status": "downloaded_verified"})
        finally:
            os.unlink(temp)
    return receipts


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m experiments.rr_v2_acquire CATALOG.json")
    print(json.dumps(acquire(json.loads(Path(sys.argv[1]).read_text())), indent=2))
