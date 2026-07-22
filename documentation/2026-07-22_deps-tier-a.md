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
"minor helper". Harness: `scripts/emoji_parity.py`.

## The two that did pass

**prometheus-client** — killer question: *what goes over the wire?* Built a
registry with the three metric types `tgstats/utils/metrics.py` actually uses
(Counter with labels, Gauge, Histogram), rendered `generate_latest()` on both
versions and diffed. 31 wire lines, identical, including the derived
`_total`/`_bucket`/`_sum`/`_count` series. Only `_created` timestamps differed;
those are wall-clock, so the harness canonicalizes the **value** but keeps the
line, so an added or removed series would still surface in the diff.

The canonicalizing regex was originally unanchored and silently rewrote `# TYPE`
and `# HELP` metadata too (`# TYPE tg_messages_created gauge` → `<WALLCLOCK>`),
which would have hidden a metric-type change. It is now anchored to a full metric
name and comment lines are skipped outright. The result above was **re-measured
with the corrected harness** against a dedicated 0.23.1 probe venv.

**python-dotenv** — killer question: *does it still parse the real config?* It is
not imported by `tgstats/` directly; it is reached through `pydantic-settings`,
which is what actually loads settings, so it sits on the config path. Parsed the
real `.env`, `.env.example`, and an 11-case syntax file (quoting, `${}`
interpolation, `export` keyword, multiline, inline comments, empty and
bare keys) on both versions. Identical.

The harness emits **only a key count and one aggregate digest per file** — no key
names, no per-value material. An earlier draft emitted per-key truncated SHA256
and claimed "secrets never stored"; review demonstrated that was false in
substance — 15 of 41 real values were recovered from a 25-word dictionary, and
the plaintext key names were themselves a secret inventory (`ADMIN_API_TOKEN`,
`BOT_TOKEN`). It also refuses to write its output anywhere inside the repo,
because there is no `.dockerignore` and `Dockerfile:33` is `COPY . .`.

## Suite gate

The suite is red and flaky at baseline, so the gate used here is *"no new failing
test ids"*, over the union of multiple runs on each side:

```
baseline union: 43 failing ids  (2 runs + 1 from batch 0)
after    union: 43 failing ids  (2 runs)
NEW failures introduced: none
```

`test_caching.py::TestCaching::test_cached_decorator_different_args` is known
flaky — it flips between identical runs — and is inside both unions.

**This gate is close to zero signal for these two packages, not merely "weaker
than green".** `grep -rE "prometheus|dotenv|generate_latest" tests/` returns no
hits. Both packages are exercised only transitively at import (config →
pydantic-settings → `dotenv_values`; `metrics.py` builds a registry), and
`generate_latest` — the actual wire surface — is never called by a test. "43 =
43" could not have caught an exposition regression. **The harnesses did all of
the verification work here**; the suite gate only shows nothing else broke.

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
