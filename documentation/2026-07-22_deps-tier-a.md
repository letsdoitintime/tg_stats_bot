# 2026-07-22 — deps batch 1: tier A

Two packages. Both proven by a cross-version behavioural check, because this
project's test suite cannot serve as the gate (see the batch 0 doc: it is red
and partly nondeterministic before any change).

| package | from | to | proof |
|---|---|---|---|
| prometheus-client | 0.23.1 | 0.25.0 | `/metrics` exposition byte-identical |
| python-dotenv | 1.1.1 | 1.2.2 | real `.env` + edge-case syntax parse-identical |

## Why only two

The scan proposed eight packages as tier A. Six were escalated on contact, per
the skill's own rule that a bump inherits the risk of the surface it touches:

- **asyncpg, psycopg** — DB drivers. Tier B: type adaptation must round-trip
  (Decimal/date/JSON, both directions) before these move.
- **celery** — broker wire contract, and it moves with `kombu`/`billiard`.
- **pydantic-settings** — config validation; belongs with the pydantic bump.
- **tzdata 2025.2 → 2026.3** — IANA rule data under a bot whose entire product
  is per-timezone activity heatmaps. Data surface → tier C.
- **emoji 2.14.1 → 2.15.0** — see below. The scan called it tier A; it is not.

## emoji is not a helper bump — it changes stored data

`tgstats/utils/features.py:40` counts emoji per message with `emoji.is_emoji()`
and **stores the count**. So the emoji package's Unicode data version is part of
the analytics contract, not an implementation detail.

Parity harness over every valid codepoint (`0x0`–`0x10FFFF`, surrogates skipped,
exceptions captured as results) on both versions:

```
emoji 2.14.1: 1393 codepoints classified as emoji
emoji 2.15.0: 1400 codepoints classified as emoji

ADDED in 2.15.0 (7):  U+1F6D8  U+1FA8A  U+1FA8E  U+1FAC8  U+1FACD  U+1FAEA  U+1FAEF
REMOVED: none
```

A green suite would have waved this through; the same message re-processed after
the bump yields a different `emoji_cnt`. The change is benign in shape —
**append-only**, so no historical count can drop, and the seven additions are
Unicode 17 emoji that will start appearing in real messages regardless. But it is
a data change and should land knowingly, in its own batch, not smuggled in as a
"minor helper". Harness: `scratchpad/emoji_parity.py`.

## The two that did pass

**prometheus-client** — killer question: *what goes over the wire?* Built a
registry with the three metric types `tgstats/utils/metrics.py` actually uses
(Counter with labels, Gauge, Histogram), rendered `generate_latest()` on both
versions and diffed. 31 wire lines, identical, including the derived
`_total`/`_bucket`/`_sum`/`_count` series. Only `_created` timestamps differed;
those are wall-clock, so the harness canonicalizes the **value** but keeps the
line, so an added or removed series would still surface in the diff.

**python-dotenv** — killer question: *does it still parse the real config?* It is
not imported by `tgstats/` directly; it is reached through `pydantic-settings`,
which is what actually loads settings, so it sits on the config path. Parsed the
real `.env`, `.env.example`, and an 11-case syntax file (quoting, `${}`
interpolation, `export` keyword, multiline, inline comments, empty and
bare keys) on both versions. Identical. Secrets were never printed or stored —
the harness compares key names and SHA256 digests of values only.

## Suite gate

The suite is red and flaky at baseline, so the gate used here is *"no new failing
test ids"*, over the union of multiple runs on each side:

```
baseline union: 43 failing ids  (2 runs + 1 from batch 0)
after    union: 43 failing ids  (2 runs)
NEW failures introduced: none
```

`test_caching.py::TestCaching::test_cached_decorator_different_args` is known
flaky — it flips between identical runs — and is inside both unions. This gate is
weaker than green and should be stated on the PR.

## Harnesses (re-run these on the next bump of each package)

`scripts/emoji_parity.py`, `scripts/prom_parity.py`, `scripts/dotenv_parity.py`.
Each takes an output path, is run once under the old venv and once under a probe
venv holding the candidate version, and the two outputs are diffed. They pass on
the old version too, which is the point — they guard the *next* upgrade, not just
this one.

```bash
venv/bin/python scripts/prom_parity.py old.txt && probe/bin/python scripts/prom_parity.py new.txt && diff old.txt new.txt
```

## Rollback

`git revert` the pin commit, then
`venv/bin/pip install -r requirements.txt` to bring the venv back in step.
Neither package is on a data-migration path, so no data rollback is involved.
