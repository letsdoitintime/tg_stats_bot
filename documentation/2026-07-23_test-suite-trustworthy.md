# 2026-07-23 — making the test suite a usable gate

The suite was red before any change (43 failures) and nondeterministic, so it
could not gate a dependency upgrade or anything else. It is now **221 passing,
0 failing, identical across repeated runs**.

The important part is not the number. Roughly a third of those failures were
**real bugs the tests had been correctly reporting all along** — the suite was
red for good reason, and had been ignored long enough that the signal was lost.
Each failure was triaged as "the test is wrong" or "the app is wrong" before
anything was touched.

## App bugs the tests were right about

### 1. The web heatmap displayed every day's data under the wrong label

`tgstats/web/date_utils.py` — `rotate_heatmap_rows` computed
`local_dt.isoweekday() % 7`, which yields **Sunday=0, Monday=1**. Its own
docstring said 0=Monday, the API returns the matrix beside
`["Monday", ..., "Sunday"]` (`routers/analytics.py`), and the template renders a
Mon–Sun axis (`chat_detail.html`). So row 0, labelled "Monday", held Sunday's
traffic, and every other row was shifted by one day.

Fixed to `local_dt.weekday()` (0=Monday..6=Sunday).

The bot's own heatmap in `plugins/heatmap/` uses a *separate*, self-consistent
Sunday-first convention (`["Sun", "Mon", ...]` with dow from SQL) and is
deliberately untouched.

### 2. An explicit date range silently dropped its last day

`parse_period` parsed `to_date` to `00:00:00`, so "1 Jan to 7 Jan" returned data
for 1–6 Jan. Now end-of-day.

### 3. The default window spanned 31 days while reporting 30

`end - timedelta(days=30)` with an inclusive day count. Now `days=29`, so the
window matches the number it reports.

### 4. Upserts returned stale objects

`ON CONFLICT DO UPDATE` writes as raw DML that the ORM does not observe, so the
`select` that followed handed back the identity-map copy with its **old**
attribute values. Demonstrated directly: database `'New Title'`, returned object
`'Old Title'`.

Effect: a renamed chat — or a user who changed their username — kept the old
value for the rest of the session. `get_by_chat_id` / `get_by_user_id` now take
`refresh=`, used at the post-upsert reads, plus the same fix in the deprecated
`handlers/common.py` helpers.

### 5. Plugin dependency resolution was inverted (earlier commit)

`resolve_dependencies` built Kahn's in-degrees by counting **dependents**
instead of dependencies, so any plugin declaring a dependency produced a false
`"Circular dependency detected"`. Dormant only because all three shipped plugins
declare `dependencies=[]`. Also `PluginManager(plugin_dirs=[])` raised
IndexError, and the error message rendered a bare `set` — hash order, so the
same failure worded itself differently between restarts.

## Test-side defects

Tests that could never have passed, independent of the app:

- **`test_session_operational_error_handling`** — `get_session()` yields inside
  its `try/except`, so it only observes exceptions thrown *into* the generator;
  the test called `session.execute()` in its own frame. It also patched
  `tgstats.db.async_session` without ever attaching the mock it built.
- **`test_connection_pool_events_are_registered`** — `event.contains(target, id)`
  is not a valid signature; it raised `TypeError` rather than checking anything.
- **`test_process_reaction_added`** — asserted `len()` on the return of a method
  declared `-> None`, and never enabled `capture_reactions`, so the method
  returned early before doing any work.
- **`test_timescale_vs_postgres_branching`** — patched a name that does not exist
  on that module, then `pass`. It would have passed with the branching entirely
  broken. Now asserts the branch reaches the generated SQL.

Stale or simply wrong expectations:

- `text_len` hardcoded 63 and 54 for strings of 61 and 52 characters (byte
  lengths are 67 and 55, so not that either). Now bound to `len(...)`.
- `capture_reactions` asserted `True`, `store_text` asserted `False` — both the
  opposite of the product defaults. Now bound to the constants.
- APIs that never existed: `ChatService.update_settings`,
  `UserRepository.get_or_create_user`, `MembershipRepository.get_or_create`,
  `Message.message_id` (the column is `msg_id`), `process_message(msg, chat, user)`.
- `telegram.Chat` is immutable; assigning `.username` raises.

## Infrastructure

- **`Mock` auto-attributes were the single biggest cause.** A bare `Mock()`
  invents every attribute, so SQLAlchemy `Boolean` columns received Mock objects
  and `getattr(obj, name, default)` never fell back to its default. `MagicMock`
  was worse: `.photo` is truthy but iterates empty, so `max()` raised on a shape
  real Telegram cannot produce. Shared `make_tg_chat` / `make_tg_user` /
  `make_tg_message` builders in `conftest.py` give every mapped column a real,
  correctly typed value.
- **`chat_hourly_heatmap_mv`** lives in migration 004, and `create_all()` only
  builds mapped tables, so it was absent under SQLite. `conftest.py` now creates
  a SQLite stand-in. Only the view *definition* is re-expressed — the query
  under test is the production one, unchanged.
- **Flakiness is gone.** Its source was `cache_manager`, a module-level singleton
  holding a Redis client bound to whichever event loop created it, with keys
  surviving between tests. An autouse fixture rebinds and clears it.

## Verification

Three consecutive full runs: `221 passed`, no variation.

Mutation-tested rather than assumed — reverting a fix must fail a test:

| reverted fix | result |
|---|---|
| `weekday()` → `isoweekday() % 7` | 4 tests fail ✅ |
| chat upsert `refresh=True` | **220 passed — unguarded** ❌ |
| user upsert `refresh=True` | 1 test fails ✅ |

That gap is why `test_upsert_returns_updated_values_for_loaded_chat` exists: a
live bug had been fixed with nothing to stop it returning. With it, both
mutations now fail exactly one test.

## What this unblocks

The 13 remaining tier B/C dependency bumps. Each still needs its own
cross-version proof — a green suite is not evidence for those — but "no new
failing test ids", the weak gate used in PRs #20/#21, can now be the real one.

## Not done

- The repo-wide lint debt: `black --check .` reports 11 files and
  `isort --check-only .` 2, all pre-existing and none of them touched here.
  CI's lint job is red on `main` independently of this work.
- `regex=` → `pattern=` in `routers/analytics.py` (deprecated in FastAPI, still
  functional — verified against 0.139.2).
