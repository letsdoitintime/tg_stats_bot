"""Cross-version parity harness for the `emoji` package.

Killer question: does is_emoji() classify any codepoint differently? This is a
DATA surface, not a helper — tgstats/utils/features.py:40 counts emoji per
message with is_emoji() and STORES the count, so the package's Unicode data
version is part of the analytics contract.

Run once under each venv, then diff:

    venv/bin/python scripts/emoji_parity.py /tmp/emoji_old.json
    probe/bin/python scripts/emoji_parity.py /tmp/emoji_new.json
    diff /tmp/emoji_old.json /tmp/emoji_new.json

features.py iterates per character, so per-codepoint iteration mirrors it exactly.
"""

import json
import sys
from importlib.metadata import version

import emoji


def classify():
    """Return sorted codepoints classified as emoji, plus any that raised."""
    hits = []
    errors = []
    for cp in range(0x0, 0x110000):
        if 0xD800 <= cp <= 0xDFFF:
            # Surrogates are not valid scalar values; chr() works but the
            # package is never handed them from real UTF-8 text.
            continue
        try:
            if emoji.is_emoji(chr(cp)):
                hits.append(cp)
        except Exception as exc:
            # Exceptions are results too — a codepoint that starts or stops
            # raising is a behaviour change. Kept in a separate list rather
            # than encoded as a negative, which collided with U+0000.
            errors.append([cp, type(exc).__name__])
    return hits, errors


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <out.json>")

    hits, errors = classify()
    # The package version deliberately does NOT go in the artifact — it goes to
    # stdout. Storing it would make the documented `diff` fail on every upgrade
    # even when classification is byte-identical, which is the one thing this
    # harness exists to detect.
    payload = {"count": len(hits), "codepoints": hits, "errors": errors}
    with open(sys.argv[1], "w") as handle:
        json.dump(payload, handle, indent=1)

    print(
        f"emoji {version('emoji')}: {len(hits)} codepoints classified as emoji"
        f"{f', {len(errors)} raised' if errors else ''}"
    )


if __name__ == "__main__":
    main()
