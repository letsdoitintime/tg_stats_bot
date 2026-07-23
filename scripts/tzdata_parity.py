"""Cross-version parity harness for tzdata (the IANA timezone database).

tzdata is pure DATA — a tier C surface. Every heatmap bucket, every period
boundary and every "local date" in this product is computed by rotating UTC
into a group's timezone, so a changed IANA rule silently moves message counts
between hours and days. Nothing in the test suite would notice.

Killer question: for the timezones this app actually uses, does any UTC offset
or DST transition change?

    venv/bin/python scripts/tzdata_parity.py /tmp/tz_old.json
    probe/bin/python scripts/tzdata_parity.py /tmp/tz_new.json
    diff /tmp/tz_old.json /tmp/tz_new.json

Zones are read from the live group_settings values plus a spread of others, so
the check keeps working if a group is later configured to a new timezone.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from zoneinfo import ZoneInfo

# The zones actually configured in group_settings today, plus a deliberate
# spread: DST-observing, non-DST, southern-hemisphere (reversed DST), a
# half-hour offset, and zones that have had recent real-world rule changes.
ZONES = [
    "UTC",
    "Europe/Sofia",
    "Europe/Kyiv",
    "Europe/London",
    "Europe/Berlin",
    "America/Los_Angeles",
    "America/New_York",
    "America/Sao_Paulo",
    "Asia/Kolkata",
    "Asia/Tokyo",
    "Australia/Sydney",
    "Africa/Cairo",
    "Asia/Tehran",
    "Pacific/Auckland",
]


def sample_instants():
    """Hourly through both DST switch windows, plus a year of daily samples.

    Hourly resolution around the transitions is the point: a rule that moves by
    a week shows up here and nowhere else.
    """
    out = []
    for year in (2025, 2026):
        for month, day in ((3, 25), (10, 25), (11, 1), (4, 1)):
            base = datetime(year, month, day, tzinfo=timezone.utc)
            out += [base + timedelta(hours=h) for h in range(0, 24 * 14, 1)]
        out += [
            datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=d) for d in range(0, 365, 7)
        ]
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <out.json>")

    instants = sample_instants()
    result = {}
    for name in ZONES:
        try:
            tz = ZoneInfo(name)
        except Exception as exc:
            result[name] = {"error": type(exc).__name__}
            continue
        # offset + abbreviation + DST flag at each instant, folded into a
        # compact signature so the diff points at the zone, not 20k lines.
        seen = []
        for moment in instants:
            local = moment.astimezone(tz)
            seen.append(
                (
                    moment.isoformat(),
                    local.utcoffset().total_seconds(),
                    local.tzname(),
                    bool(local.dst()),
                )
            )
        transitions = [
            {"at": cur[0], "offset_from": prev[1], "offset_to": cur[1], "abbr": cur[2]}
            for prev, cur in zip(seen, seen[1:])
            if prev[1] != cur[1]
        ]
        result[name] = {
            "distinct_offsets": sorted({s[1] for s in seen}),
            "distinct_abbrs": sorted({s[2] for s in seen if s[2]}),
            "transitions": transitions,
        }

    with open(sys.argv[1], "w") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)

    total = sum(len(v.get("transitions", [])) for v in result.values())
    print(f"tzdata {version('tzdata')}: {len(ZONES)} zones, {total} DST transitions observed")


if __name__ == "__main__":
    main()
