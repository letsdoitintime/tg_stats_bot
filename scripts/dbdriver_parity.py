"""Cross-version parity harness for the database drivers.

Killer question for a DB driver: does type adaptation still ROUND-TRIP? A
driver can import cleanly, pass every query test, and still hand back a
Decimal as a float or drop a timezone — silently changing stored analytics.

Writes one row of every type the schema actually uses into a TEMP table (so
production data is never touched), reads it back, and records the Python type
and repr of each value. Run once per venv, then diff:

    venv/bin/python scripts/dbdriver_parity.py /tmp/db_old.json
    probe/bin/python scripts/dbdriver_parity.py /tmp/db_new.json
    diff /tmp/db_old.json /tmp/db_new.json

Both directions matter: the INSERT exercises adaptation, the SELECT exercises
result conversion.
"""

import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine, text

from tgstats.core.config import settings

CASES = {
    "int": 42,
    "bigint": 10**15,
    "float": 1.5,
    "numeric": Decimal("17.1612903225806452"),  # avg_dau_30d comes back like this
    "bool_true": True,
    "bool_false": False,
    "text": "ВелоПокатушки 🇺🇦",  # non-ASCII + emoji, as real titles are
    "date": date(2025, 1, 7),
    "naive_ts": datetime(2025, 1, 7, 23, 59, 59, 999999),
    "aware_ts": datetime(2025, 1, 7, 23, 59, 59, 999999, tzinfo=timezone.utc),
    "west_ts": datetime(2025, 1, 7, 23, 59, 59, tzinfo=timezone(timedelta(hours=-8))),
    "json": {"a": [1, 2.5, None], "b": {"c": "ünicode"}},
    "none": None,
}

DDL = """
CREATE TEMP TABLE parity_probe (
    k text PRIMARY KEY, i bigint, f double precision, n numeric,
    b boolean, t text, d date, ts timestamp, tstz timestamptz, j jsonb
)
"""


def canon(value):
    """Type name + repr — a Decimal arriving as float MUST show up in the diff."""
    return [type(value).__name__, repr(value)]


async def _async_roundtrip():
    """Same round-trip through asyncpg — the driver the BOT actually writes with.

    The sync psycopg path above is what the web API uses; proving one says
    nothing about the other, and they have completely separate type codecs.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    url = settings.database_url
    if "+asyncpg" not in url:
        url = url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url)

    result = {}
    async with engine.begin() as conn:
        await conn.execute(text(DDL))
        for key, value in CASES.items():
            if isinstance(value, datetime):
                col = "tstz" if value.tzinfo else "ts"
            elif isinstance(value, date):
                col = "d"
            elif isinstance(value, dict):
                col = "j"
            else:
                col = {int: "i", float: "f", Decimal: "n", bool: "b", str: "t", type(None): "t"}[
                    type(value)
                ]
            if col == "j":
                await conn.execute(
                    text(f"INSERT INTO parity_probe (k, {col}) VALUES (:k, CAST(:v AS jsonb))"),
                    {"k": key, "v": json.dumps(value)},
                )
            else:
                await conn.execute(
                    text(f"INSERT INTO parity_probe (k, {col}) VALUES (:k, :v)"),
                    {"k": key, "v": value},
                )
            got = (
                await conn.execute(text(f"SELECT {col} FROM parity_probe WHERE k = :k"), {"k": key})
            ).scalar()
            result[key] = {"sent": canon(value), "got": canon(got)}
    await engine.dispose()
    return result


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <out.json>")

    url = settings.database_url.replace("+asyncpg", "+psycopg")
    url = url.replace("postgresql://", "postgresql+psycopg://")
    engine = create_engine(url)

    out = {}
    with engine.begin() as conn:
        conn.execute(text(DDL))
        for key, value in CASES.items():
            col = {
                int: "i",
                float: "f",
                Decimal: "n",
                bool: "b",
                str: "t",
                date: "d",
                datetime: "ts",
                dict: "j",
                type(None): "t",
            }[type(value)]
            # date must be checked before datetime (datetime subclasses date)
            if isinstance(value, datetime):
                col = "tstz" if value.tzinfo else "ts"
            elif isinstance(value, date):
                col = "d"
            if isinstance(value, dict):
                conn.execute(
                    text(f"INSERT INTO parity_probe (k, {col}) VALUES (:k, CAST(:v AS jsonb))"),
                    {"k": key, "v": json.dumps(value)},
                )
            else:
                conn.execute(
                    text(f"INSERT INTO parity_probe (k, {col}) VALUES (:k, :v)"),
                    {"k": key, "v": value},
                )
            got = conn.execute(
                text(f"SELECT {col} FROM parity_probe WHERE k = :k"), {"k": key}
            ).scalar()
            out[key] = {"sent": canon(value), "got": canon(got)}

    out_async = asyncio.run(_async_roundtrip())
    out = {"sync_psycopg": out, "async_asyncpg": out_async}

    import sqlalchemy

    versions = {"sqlalchemy": sqlalchemy.__version__}
    for mod in ("psycopg", "asyncpg"):
        try:
            versions[mod] = __import__(mod).__version__
        except Exception:
            versions[mod] = "absent"

    with open(sys.argv[1], "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(
        " | ".join(f"{k} {v}" for k, v in versions.items())
        + f": {len(out['sync_psycopg'])} sync + {len(out['async_asyncpg'])} async types"
    )


if __name__ == "__main__":
    main()
