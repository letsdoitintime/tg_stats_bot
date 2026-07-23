"""Cross-version parity harness for prometheus_client.

Killer question: what goes over the WIRE? The Python API can be unchanged while
the /metrics exposition format moves under a scraper.

Run once under each venv, then diff:

    venv/bin/python scripts/prom_parity.py /tmp/prom_old.txt
    probe/bin/python scripts/prom_parity.py /tmp/prom_new.txt
    diff /tmp/prom_old.txt /tmp/prom_new.txt

Covers the three metric types tgstats/utils/metrics.py uses.
"""

import re
import sys
from importlib.metadata import version

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

# Only the VALUE of a `_created` sample is wall-clock and needs canonicalizing.
# Anchored at line start and matched against a full metric name so `# HELP` and
# `# TYPE` metadata survive untouched — the previous unanchored `_created.*` also
# rewrote "# TYPE tg_messages_created gauge" to "<WALLCLOCK>", which would have
# hidden a real type change. Comment lines are skipped outright as well.
CREATED_SAMPLE = re.compile(r"^([A-Za-z_:][A-Za-z0-9_:]*_created(?:\{[^}]*\})?) .*$")


def canonicalize(line):
    """Blank the wall-clock value of a _created sample, keeping the line itself."""
    if line.startswith("#"):
        return line
    return CREATED_SAMPLE.sub(r"\1 <WALLCLOCK>", line)


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <out.txt>")

    registry = CollectorRegistry()
    counter = Counter("tg_messages_total", "msgs", ["chat"], registry=registry)
    counter.labels(chat="1").inc(3)
    Gauge("tg_active_users", "users", registry=registry).set(42)
    Histogram("tg_req_seconds", "latency", registry=registry).observe(0.25)

    lines = [canonicalize(ln) for ln in generate_latest(registry).decode().splitlines()]
    with open(sys.argv[1], "w") as handle:
        handle.write("\n".join(lines) + "\n")

    print(f"prometheus_client {version('prometheus_client')}: {len(lines)} wire lines")


if __name__ == "__main__":
    main()
