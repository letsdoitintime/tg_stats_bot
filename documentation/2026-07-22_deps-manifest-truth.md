# 2026-07-22 — deps batch 0: manifest truth-up

Reconcile `requirements.txt` / `requirements-dev.txt` with the venv the services
actually run. **No installed production version changes.** This is a prerequisite
for any real dependency bump: until the manifest describes reality, bumping a pin
changes nothing that runs, and rebuilding from the manifest silently changes
everything that does.

## What was wrong

`requirements.txt` is the deploy contract — `Dockerfile:16` and
`install_requirements.sh:29` both `pip install -r requirements.txt`. It was last
touched 2025-12-16 and the venv has drifted from it since.

`pip install --dry-run -r requirements.txt` against the running venv proved a
rebuild would **downgrade nine production libraries**:

| package | manifest pin (old) | actually running | rebuild would install |
|---|---|---|---|
| redis | `5.2.*` | **6.4.0** | 5.2.1 — *major downgrade* |
| structlog | `24.4.*` | **25.4.0** | 24.4.0 — *major downgrade* |
| alembic | `1.13.*` | **1.16.4** | 1.13.3 |
| psycopg[binary] | `3.1.*` | **3.2.9** | 3.1.20 |
| pydantic | `2.10.*` | **2.11.7** | 2.10.6 |
| pydantic-settings | `2.7.*` | **2.10.1** | 2.7.1 |
| fastapi | `0.115.*` | **0.116.1** | 0.115.14 |
| uvicorn | `0.32.*` | **0.35.0** | 0.32.1 |
| celery | `5.4.*` | **5.5.3** | 5.4.0 |

Also wrong, same file:

- **`starlette` was unpinned.** `fastapi` declares it with no upper bound, so the
  framework major was never reproducible. Verified: `fastapi==0.139.2` pulls
  `starlette==1.3.1` — a major jump from the 0.47.3 in production.
- **The six `opentelemetry-*` pins were unconditional but not installed.**
  `tgstats/utils/tracing.py:8-20` wraps the imports in `try/except ImportError`
  and sets `TRACING_AVAILABLE=False`, which is the current production state. A
  rebuild would have installed them and flipped tracing **on** — a silent
  runtime behaviour change, not just a version change.
- **`tzdata` pinned `2024.2`, running `2025.2`** — a rebuild would have reverted
  a year of IANA timezone rules under a bot whose whole domain is per-timezone
  activity heatmaps.

`requirements-dev.txt` was fiction end to end: every pin stale, `pytest-asyncio`
pinned `0.24.*` against `1.1.0` installed (a major), and **`aiosqlite` listed but
never installed** — which is why 57 tests could not even be collected.

## What changed

- Every production pin moved to the version already running and proven in prod.
- `starlette==0.47.*` pinned explicitly, with a note to bump it *with* fastapi.
- The `opentelemetry-*` block commented out to match reality, with instructions
  to re-enable deliberately (all six together).
- Dev pins reconciled; `aiosqlite` installed; thirteen listed-but-never-installed
  and unused dev packages dropped (nothing in `tests/` imports them — the
  `factory` references are the app's own `ServiceFactory`/`RepositoryFactory`).

## Proof

```
$ venv/bin/pip install --dry-run -r requirements.txt -r requirements-dev.txt
✅ NO-OP — nothing to install or change
$ venv/bin/pip check
No broken requirements found.
```

A no-op dry-run is the whole point: the manifest now reproduces the running venv
byte-for-byte, so the rebuild path and the running services agree.

Test suite: `19 failed + 57 collection errors` → `41–43 failed, 177–179 passed`.
The improvement is entirely from installing `aiosqlite`; no production library
moved. The remaining failures are pre-existing and unrelated (see below).

## Test suite is NOT a usable upgrade gate yet

The skill's tier-A gate is "full suite green on old and new". **It cannot be met
here — the suite is red before any change**, and it is also nondeterministic:

- 42–43 stable failures, and `test_caching.py::TestCaching::test_cached_decorator_different_args`
  flips between three identical runs.
- Failures are order-dependent: `test_repositories.py::TestChatRepository::test_get_by_chat_id`
  passes alone and fails in the full run — the in-memory SQLite state leaks
  between tests.
- Verified **not** caused by dependency drift: pinning `pytest-asyncio` back to
  the manifest's `0.24.*` gives 41 failures vs 1.1.0's 42–43. Same suite, same
  problem. These are pre-existing app/test bugs.
- Example of a real one, not a dep issue: `tgstats/web/date_utils.py:50,60`
  computes `end - timedelta(days=30)` then `days = (end - start).days + 1`,
  yielding **31** where `test_step2.py:21` asserts 30.

Until that is fixed, the only honest gate for a bump in this project is
*"no new failing test ids versus the recorded baseline"*, treating the one flaky
test as known. That is weaker than green and should be said out loud on any PR.

## Rollback

Nothing installed changed except the addition of `aiosqlite` (test-only, not
imported by `tgstats/`). To revert: `git revert` the pin commit. Freeze snapshot
of the pre-change venv was taken before any work.

## Not done here (deliberately)

Every actual version bump. The 17 outstanding are tiered in the batch report;
tier B items each need a cross-version behavioural proof, and the framework
group (fastapi + starlette + uvicorn) must move as one.
