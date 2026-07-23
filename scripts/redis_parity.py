"""Cross-version parity harness for the redis client.

Killer question for a MAJOR client bump: what actually goes over the wire, and
did any API get removed? A client can import cleanly and still change how
values are serialized, how scan_iter paginates, how connection URLs are
parsed, or how errors are typed -- and cache.py's except blocks catch broad
exception classes, so a reparented exception would silently change which
handler fires.

Covers both redis surfaces this app has:
  - the cache (tgstats/utils/cache.py): json.dumps -> setex -> get ->
    json.loads for every value shape it stores, the TTL setex relies on, and
    the scan_iter/delete pattern invalidate_pattern relies on.
  - the exception hierarchy and from_url(...) parsing cache.py's __init__ and
    except blocks depend on.

Talks to a REAL, local Redis using a dedicated "parity:" key prefix and
deletes every key it creates, including on failure.

Standalone: needs only the `redis` package, not the tgstats app, so it runs
unmodified in a throwaway probe venv.

    venv/bin/python scripts/redis_parity.py /tmp/redis_old.json
    /tmp/probe_redis/bin/python scripts/redis_parity.py /tmp/redis_new.json
    diff /tmp/redis_old.json /tmp/redis_new.json
"""

import asyncio
import json
import os
import sys
import warnings
from importlib.metadata import version

import redis
import redis.asyncio as aredis
import redis.exceptions as rexc

PREFIX = "parity:"

# Same default tgstats.core.config.Settings.redis_url falls back to, and the
# same env var CI/tests set it from -- so from_url() parses the exact URL
# shape the app actually uses, without importing the app's settings.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# The exact kwargs CacheManager.__init__ passes to redis.from_url (cache.py:30-36).
CLIENT_KWARGS = dict(
    encoding="utf-8",
    decode_responses=False,
    socket_connect_timeout=5,
    socket_timeout=5,
)

# Every value shape CacheManager.set() actually round-trips through
# json.dumps/json.loads (cache.py:66,49).
CASES = {
    "dict": {"data": "test"},
    "list": [1, 2, 3, "four"],
    "nested_dict": {"a": [1, 2.5, None], "b": {"c": "ünicode"}},
    "str_unicode_emoji": "ВелоПокатушки 🇺🇦",
    "int": 42,
    "float": 1.5,
    "bool_true": True,
    "bool_false": False,
    "none": None,
}


def canon(value):
    """Type name + repr -- a dict returning as a str MUST show in the diff."""
    return [type(value).__name__, repr(value)]


async def cache_surface():
    """Mirror CacheManager exactly (cache.py:41-104): round-trip every value
    shape, then the TTL and scan_iter/delete invalidate_pattern relies on.

    Every warning raised during the calls is recorded, so a new deprecation on
    a method cache.py actually calls shows up in the diff, not just silently
    in a test run's stderr.
    """
    r = aredis.from_url(REDIS_URL, **CLIENT_KWARGS)
    created = (
        [f"{PREFIX}{name}" for name in CASES]
        + [f"{PREFIX}ttl_probe"]
        + [f"{PREFIX}scan:{i}" for i in range(5)]
    )

    out = {"roundtrip": {}}
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")

            for name, value in CASES.items():
                key = f"{PREFIX}{name}"
                serialized = json.dumps(value)
                await r.setex(key, 60, serialized)
                raw = await r.get(key)
                got = json.loads(raw)
                out["roundtrip"][name] = {
                    "sent": canon(value),
                    "raw_get_type": type(raw).__name__,
                    "got": canon(got),
                }

            # TTL behaviour: setex then ttl must be in the expected range.
            ttl_key = f"{PREFIX}ttl_probe"
            await r.setex(ttl_key, 60, json.dumps("x"))
            ttl = await r.ttl(ttl_key)
            out["ttl_in_expected_range"] = 0 < ttl <= 60

            # scan_iter / delete over a pattern -- invalidate_pattern's mechanism.
            for i in range(5):
                await r.setex(f"{PREFIX}scan:{i}", 60, json.dumps(i))
            found = [k async for k in r.scan_iter(match=f"{PREFIX}scan:*")]
            out["scan_iter_found"] = sorted(k.decode() for k in found)
            out["scan_iter_key_type"] = type(found[0]).__name__ if found else None
            out["scan_iter_deleted_count"] = await r.delete(*found) if found else 0

            out["warnings"] = sorted(f"{w.category.__name__}: {w.message}" for w in caught)
    finally:
        existing = [k for k in created if await r.exists(k)]
        if existing:
            await r.delete(*existing)
        await r.aclose()

    return out


async def triggered_exceptions():
    """Not just the static __mro__ below -- actually provoke a ConnectionError
    and a ResponseError against real sockets/commands, so a version that
    reparents or reroutes either one shows up as a real behavioural change,
    not just a class-table difference.
    """
    out = {}

    # ConnectionError: nothing is listening on this port.
    unreachable = aredis.from_url(
        "redis://127.0.0.1:1/0", socket_connect_timeout=1, socket_timeout=1
    )
    try:
        await unreachable.ping()
        out["connect_refused"] = {"raised": None}
    except Exception as e:
        out["connect_refused"] = {
            "raised": type(e).__name__,
            "mro": [c.__name__ for c in type(e).__mro__],
        }
    finally:
        await unreachable.aclose()

    # ResponseError: a list op against a key holding a string (WRONGTYPE).
    r = aredis.from_url(REDIS_URL, **CLIENT_KWARGS)
    key = f"{PREFIX}wrongtype"
    try:
        await r.set(key, "a_string_value")
        try:
            await r.lpush(key, "x")
            out["wrongtype"] = {"raised": None}
        except Exception as e:
            out["wrongtype"] = {
                "raised": type(e).__name__,
                "mro": [c.__name__ for c in type(e).__mro__],
            }
    finally:
        await r.delete(key)
        await r.aclose()

    return out


def exception_hierarchy():
    """Full __mro__ names -- cache.py's except blocks catch by class, so a
    reparented exception changes which handler fires."""
    names = ["RedisError", "ConnectionError", "TimeoutError", "ResponseError"]
    return {name: [c.__name__ for c in getattr(rexc, name).__mro__] for name in names}


def url_parsing():
    """redis.from_url with the exact kwargs cache.py passes (cache.py:30-36).
    Records host/port/db plus every OTHER kwarg key the client derived, so a
    version that adds new connection defaults shows up too. A password is
    never recorded, even though this URL has none.
    """
    r = redis.from_url(REDIS_URL, **CLIENT_KWARGS)
    kwargs = r.connection_pool.connection_kwargs
    simple = {}
    for k, v in kwargs.items():
        if k == "password":
            continue
        simple[k] = v if isinstance(v, (str, int, float, bool, type(None))) else type(v).__name__
    return {
        "host": kwargs.get("host"),
        "port": kwargs.get("port"),
        "db": kwargs.get("db"),
        "all_kwarg_keys": sorted(k for k in kwargs if k != "password"),
        "kwargs": simple,
    }


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <out.json>")

    result = {
        "cache_surface": asyncio.run(cache_surface()),
        "triggered_exceptions": asyncio.run(triggered_exceptions()),
        "exception_hierarchy": exception_hierarchy(),
        "url_parsing": url_parsing(),
    }

    with open(sys.argv[1], "w") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)

    print(f"redis {version('redis')}: cache roundtrip + exception hierarchy + URL parsing")


if __name__ == "__main__":
    main()
