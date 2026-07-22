"""Parity harness: does emoji.is_emoji() classify any codepoint differently?
Mirrors tgstats/utils/features.py:40, which stores the resulting count."""
import sys, json, emoji
hits = []
for cp in range(0x0, 0x110000):
    if 0xD800 <= cp <= 0xDFFF:      # surrogates: not valid scalars
        continue
    ch = chr(cp)
    try:
        if emoji.is_emoji(ch):
            hits.append(cp)
    except Exception:
        hits.append(-cp)            # exceptions are results too
out = {"version": emoji.__version__, "count": len(hits), "cps": hits}
json.dump(out, open(sys.argv[1], "w"))
print(f"emoji {emoji.__version__}: {len(hits)} codepoints classified as emoji")
