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

### 1. The heatmap API returned every day's data under the wrong label

`tgstats/web/date_utils.py` — `rotate_heatmap_rows` computed
`local_dt.isoweekday() % 7`, which yields **Sunday=0, Monday=1**. Its own
docstring said 0=Monday, and the response returns the matrix beside
`["Monday", ..., "Sunday"]` (`routers/analytics.py:180`). So row 0, labelled
"Monday", held Sunday's traffic, and every other row was shifted by one day.

Fixed to `local_dt.weekday()` (0=Monday..6=Sunday).

**Scope — corrected after review.** An earlier draft claimed the shipped web
dashboard was affected, citing the Mon–Sun axis in `chat_detail.html`. That is
wrong. The template requests `/internal/chats/{id}/...`
(`chat_detail.html:297`), which is `tgstats/web/app.py:296` — a *different*
endpoint with its own rotation (`app.py:340`, `(dow + 6) % 7`) that was already
correct.

`rotate_heatmap_rows` has exactly **one** caller: `routers/analytics.py:177`,
serving the token-authenticated `/api/chats/{id}/heatmap`. The blast radius is
that API, not the UI. The bug and the fix are real; the impact was overstated.

Two other heatmap paths exist and are deliberately untouched: the bot's own in
`plugins/heatmap/` (self-consistent Sunday-first, `["Sun", "Mon", ...]` fed by
the SQL ISODOW to dow conversion), and `app.py`'s UI endpoint above.

**Noted in passing, pre-existing and NOT fixed here:** `app.py:310` computes a
timezone and never applies it to the heatmap query, so the UI heatmap is UTC
while the API one is timezone-rotated. The two "Monday" columns still disagree
with each other. Worth its own change.

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
  lengths are 67 and 55, so not that either). Now the correct literals.
- `capture_reactions` asserted `True`, `store_text` asserted `False` — both the
  opposite of the product defaults. Now the correct literals, **not** the
  constants: `setup_chat` builds the row *from* those constants
  (`chat_repository.py:157,162`), so asserting against them is a tautology.
  An intermediate version of this branch did exactly that, and review proved
  it — flipping `DEFAULT_STORE_TEXT` left all 221 tests passing. Both defaults
  are now also pinned in `test_new_architecture.py::test_constants_exist`,
  where nothing had pinned them before.
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

  **Known divergence, found by review:** SQLite has no timestamp type, so
  `hour_bucket` comes back as TEXT where Postgres `DATE_TRUNC` yields a
  timestamp. The plugin path (`plugins/heatmap/repository.py`) CASTs and
  string-compares its way past this, which is what the heatmap tests exercise;
  `rotate_heatmap_rows` would raise `TypeError` on a TEXT bucket. So the
  weekday fix is covered by `test_step2.py` against real `datetime` tuples
  (4 tests, mutation-proven), **not** through the stand-in view. Everything
  else — the ISODOW mapping, `hour`, `msg_cnt`, `unique_users`, the cutoff
  filter — was verified to match the migration column for column.
- **Flakiness is gone.** Its source was `cache_manager`, a module-level singleton
  holding a Redis client bound to whichever event loop created it, with keys
  surviving between tests. An autouse fixture rebinds and clears it.
- **The suite is hermetic.** Two caching tests needed a live Redis and lacked
  the `pytest.skip` guard their siblings had, so on a runner without Redis the
  suite was red on arrival — fatal for something being pitched as a gate.
  Verified: `221 passed` with Redis, `217 passed, 4 skipped` with
  `ENABLE_CACHE=false`.

## Verification

Three consecutive full runs: `221 passed`, no variation.

Mutation-tested rather than assumed — reverting a fix must fail a test:

| reverted fix | result |
|---|---|
| `weekday()` → `isoweekday() % 7` | 4 tests fail ✅ |
| chat upsert `refresh=True` | **220 passed — unguarded** ❌ → guard added |
| user upsert `refresh=True` | 1 test fails ✅ |
| `timedelta(days=29)` → `30` | 1 test fails ✅ |
| `to_date` → midnight | 1 test fails ✅ |
| dep-resolver in-degree inversion | 2 tests fail ✅ |
| `plugin_dirs=[]` guard | 2 tests fail ✅ |
| flip `DEFAULT_STORE_TEXT` | **221 passed — tautology** ❌ → literals restored |

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
