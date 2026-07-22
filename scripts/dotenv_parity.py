"""Cross-version parity harness for python-dotenv.

Killer question: does the new version parse the REAL .env identically?

Run once under each venv, then diff the two output files:

    venv/bin/python scripts/dotenv_parity.py /tmp/dot_old.json .env
    probe/bin/python scripts/dotenv_parity.py /tmp/dot_new.json .env
    diff /tmp/dot_old.json /tmp/dot_new.json

Output contains NO key names and NO value material — only a per-file key count
and one aggregate digest over the whole canonicalized parse. That is enough for
a go/no-go; if a digest differs, re-run by hand locally where the values are
already in the clear.

An earlier version emitted per-key truncated digests. Review showed that was
recoverable: 15 of 41 real values fell to a 25-word dictionary attack, and the
plaintext key names alone (ADMIN_API_TOKEN, BOT_TOKEN, ...) were a secret
inventory. Do not reintroduce per-key output for a file that holds secrets.
"""

import hashlib
import json
import os
import sys
from importlib.metadata import version

from dotenv import dotenv_values

# Refuse to write anywhere inside the working tree. The repo has no .dockerignore
# and the Dockerfile does `COPY . .`, so an output file dropped in the repo root
# gets committed by `git add -A` and baked into the image.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_file(path):
    """Return key count and one aggregate digest for a single env file."""
    try:
        values = dotenv_values(path)
    except Exception as exc:
        # Type name only — an exception message can embed raw file bytes
        # (UnicodeDecodeError quotes the offending slice).
        return {"error": type(exc).__name__}

    # Canonical serialization: sorted and length-prefixed, so key/value
    # boundaries cannot be forged by a value that contains the separator.
    parts = []
    for key in sorted(values):
        raw = values[key]
        val = "\x00NONE" if raw is None else raw
        parts.append(f"{len(key)}:{key}={len(val)}:{val}")
    blob = "\n".join(parts).encode()

    return {"keys": len(values), "digest": hashlib.sha256(blob).hexdigest()}


def main():
    if len(sys.argv) < 3:
        sys.exit(f"usage: {sys.argv[0]} <out.json OUTSIDE the repo> <env-file>...")

    out_path = os.path.abspath(sys.argv[1])
    if os.path.commonpath([out_path, REPO_ROOT]) == REPO_ROOT:
        sys.exit(f"refusing to write inside the repo ({REPO_ROOT}) - use /tmp")

    result = {path: digest_file(path) for path in sys.argv[2:]}
    with open(out_path, "w") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)

    summary = ", ".join(f"{p}={r.get('keys', r.get('error'))}" for p, r in result.items())
    print(f"python-dotenv {version('python-dotenv')}: {summary}")


if __name__ == "__main__":
    main()
