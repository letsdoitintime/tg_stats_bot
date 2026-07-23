# 2026-07-22 — deps batch 0: manifest truth-up

Reconcile `requirements.txt` / `requirements-dev.txt` with the venv the services
actually run. **No installed production version changes.** This is a prerequisite
for any real dependency bump: until the manifest describes reality, bumping a pin
changes nothing that runs, and rebuilding from the manifest silently changes
everything that does.

## What was wrong

`requirements.txt` is the container deploy contract (`Dockerfile:16`). It was
last touched 2025-12-16 and the venv has drifted from it since.

> **Correction (found by the Codex bot review on PR #20).** An earlier draft of
> this doc claimed `install_requirements.sh` also installs from `requirements.txt`.
> It does not. `install_requirements.sh:23` branches on `pyproject.toml` *first*,
> and that file exists — so the script always runs `pip install -e .` /
> `pip install -e ".[dev]"` and never reads `requirements.txt` at all. The
> README's documented dev setup (`README.md:314`) takes the same path. See
> "The second manifest" below; the reconciliation was only half a fix until that
> was addressed.

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

- **`starlette` was unpinned.** Corrected after review — an earlier draft said
  "fastapi declares it with no upper bound", which is **false for the pinned
  version**: `fastapi 0.116.1` declares `starlette<0.48.0,>=0.40.0`. The pin is
  therefore redundant today. It earns its place forward: `fastapi 0.139.2`
  **dropped** that ceiling to a bare `starlette>=0.46.0` and resolves to
  `starlette 1.3.1`, a major. The pin does nothing until someone bumps fastapi,
  which is precisely when it is needed.
- **The six `opentelemetry-*` pins were unconditional but not installed.**
  `tgstats/utils/tracing.py:8-20` wraps the imports in `try/except ImportError`
  and sets `TRACING_AVAILABLE=False`. Also corrected after review: an earlier
  draft claimed a rebuild would "flip tracing **on**". It would not — **nothing
  in the repo imports that module**, so `TracingManager` is never constructed.
  Installing them adds six unused packages. Commenting them out is still right
  (they were pinned while absent, which is the drift being cleaned up), but the
  behaviour-change reasoning was wrong.
- **`tzdata` pinned `2024.2`, running `2025.2`** — a rebuild would have reverted
  a year of IANA timezone rules under a bot whose whole domain is per-timezone
  activity heatmaps.

`requirements-dev.txt` was stale throughout: `pytest-asyncio` pinned `0.24.*`
against `1.1.0` installed (a major), `isort` pinned `5.13.*` against `7.0.0`
(two majors). `aiosqlite` was **listed but missing from the venv**, which is why
57 tests failed at collection locally. Note the scope of that: it was a local
venv problem, not a manifest problem — CI installs fresh from this file, so CI
was never affected.

## What changed

- Every production pin moved to the version already running and proven in prod.
- `starlette==0.47.*` pinned explicitly, with a note to bump it *with* fastapi.
- The `opentelemetry-*` block commented out to match reality, with instructions
  to re-enable deliberately (all six together).
- Dev pins reconciled and `aiosqlite` installed into the venv. Eleven unused dev
  packages dropped — none installed, none imported anywhere in the repo (the
  `factory` references are the app's own `ServiceFactory`/`RepositoryFactory`).
  Corrected after review: an earlier draft said *thirteen*, including `isort`
  and `flake8`, and described all of them as "never installed". Both of those
  **are** installed (7.0.0 and 7.3.0), so they are pinned truthfully here
  instead of dropped. Verified the drops are CI-safe: `ci.yml:23` installs the
  lint tools directly and `ci.yml:87` runs pytest without `-n`.

## The second manifest — `pyproject.toml`

`pyproject.toml` duplicated the dependency list as open floors
(`fastapi>=0.100`, `structlog>=23.0`, `python-telegram-bot>=21.0`, …) **and was
missing nine runtime packages outright**. Because `install_requirements.sh`
prefers it, that was the path most people actually took. Measured with
`pip install --dry-run -e .` against the old file:

- **Installed every deferred major at once** — `fastapi 0.139.2`,
  **`starlette 1.3.1`**, `structlog 26.1.0`, `pydantic 2.13.4`, `psycopg 3.3.4`,
  `alembic 1.18.5`, `uvicorn 0.51.0`, `emoji 2.15.0`.
- **Omitted `redis`, `celery`, `prometheus-client`, `pyyaml`, `asyncpg`,
  `tzdata`, `jinja2`, `python-dateutil`, `httpx`.** `redis` and `celery` are
  imported in three modules each and `pyyaml` in one, so that environment could
  not start the bot.
- `[dev]` extras lacked `aiosqlite`, so a fresh dev env still failed test
  collection — the reconciled `requirements-dev.txt` never applied on this path.

Fixed by deleting the duplicate list rather than syncing it. `pyproject.toml`
now reads the pinned files, so there is exactly one source of truth and the two
install paths cannot diverge again:

```toml
dynamic = ["dependencies", "optional-dependencies"]

[tool.setuptools.dynamic]
dependencies = { file = ["requirements.txt"] }
optional-dependencies.dev = { file = ["requirements-dev.txt"] }
```

## Proof

```
$ venv/bin/pip install --dry-run -r requirements.txt -r requirements-dev.txt
✅ NO-OP — nothing to install or change
$ venv/bin/pip check
No broken requirements found.
```

And the pyproject path, which is the one the setup script and README use:

```
$ pip install --dry-run -e .        # was: fastapi 0.139.2 / starlette 1.3.1 / structlog 26.1.0,
                                    #      no redis, no celery, no prometheus-client
  fastapi-0.116.2  starlette-0.47.3  structlog-25.4.0  emoji-2.14.1
  redis-6.4.0  celery-5.5.3  prometheus-client  PyYAML-6.0.3  asyncpg-0.30.0  tzdata-2025.2

$ pip install --dry-run -e ".[dev]"
  aiosqlite-0.20.0  pytest-8.4.2  pytest-asyncio-1.1.1  pytest-cov-7.0.0  ruff  black  mypy
```

The commented-out `opentelemetry-*` lines are correctly ignored by setuptools,
so the tracing-stays-off property holds on this path too.

A no-op dry-run is the whole point: the manifest no longer downgrades anything,
so the rebuild path and the running services agree.

> ⚠️ **This stack must land as a unit.** That no-op was measured against the venv
> *before* batch 1 bumped prometheus-client and python-dotenv. Batch 1 advanced
> the venv, so the same command now reports
> `Would install prometheus_client-0.23.1 python-dotenv-1.1.1` — **merging and
> deploying this batch alone would downgrade those two packages.** Merge both,
> or neither. (Found by review; the split is for review attention, not for
> independent deployability.)

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
- Not *substantially* caused by dependency drift: pinning `pytest-asyncio` back
  to the manifest's `0.24.*` gives 41 failures vs 1.1.0's 42–43. The bulk of the
  failures is identical either way and is pre-existing app/test bugs. To be
  precise about the residue, though — that 1–2 test delta **is** a dependency
  effect (it moves within `test_caching.py`), so "not caused by drift" is right
  about the 40-odd, not about every last one.
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
