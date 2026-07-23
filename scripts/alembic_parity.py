"""Cross-version parity harness for alembic.

Killer question for alembic: does it still resolve the SAME revision graph
and produce the SAME SQL for THIS project's migrations? Not "does it
import". Migrations run on deploy -- supervisor's tgstats-migrations program
runs `alembic upgrade head` (see /etc/supervisor/conf.d/tgstats-bot.conf) --
so a change in how revisions are discovered, ordered, or rendered to SQL is
a change to what actually lands on a live database.

NO DATABASE WRITE IS EVER ISSUED. Every revision's SQL is produced with
alembic's own offline mode (`--sql`), the same mechanism `alembic upgrade
head --sql` uses: alembic never opens a connection in that mode, it only
uses the configured URL to pick a dialect for rendering DDL text. FAKE_URL
below is never contacted.

Two of this project's migrations complicate "just diff the SQL":
  - 004_create_aggregates.py branches on whether TimescaleDB is installed,
    checked via `connection.execute(...).fetchone()`. Offline, that mock
    connection has no real answer, so the check always comes back falsy and
    the migration deterministically renders its PostgreSQL-fallback branch
    (the *_mv materialized views) -- worth recording explicitly, since that
    is the only branch offline mode will ever exercise, in any version.
  - 006_add_indexes_and_soft_deletes.py calls sa.inspect(op.get_bind())
    unconditionally, with no try/except around it. A mock connection is not
    inspectable, so this migration CANNOT render offline in any alembic
    version -- it raises NoInspectionAvailable every time. That is recorded
    as an error for that revision rather than SQL text; parity for it means
    both versions raise the identical error, not that both produce DDL.

Records the full revision graph (down_revision, branch_labels, the base ->
head order `upgrade head` would apply), the resolved head(s), the per
-revision offline SQL (or exception, per above), and any warnings seen while
loading or rendering the scripts. Canonicalizes only the one genuinely
variable thing that could otherwise leak here: each venv's own absolute
install path.

    venv/bin/python scripts/alembic_parity.py /tmp/al_old.json
    /tmp/probe_alembic/bin/python scripts/alembic_parity.py /tmp/al_new.json
    diff /tmp/al_old.json /tmp/al_new.json
"""

import io
import json
import os
import sys
import warnings
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent

# Offline mode never connects -- this only selects the dialect used to render
# DDL. Hardcoded (not read from .env/DATABASE_URL) so both venvs render the
# identical dialect regardless of local .env contents, and no credential ever
# reaches the output artifact.
FAKE_URL = "postgresql+psycopg://parity:parity@localhost/parity"


def canon(text):
    """Mask each venv's own install path -- the one thing guaranteed to differ."""
    return text.replace(sys.prefix, "<VENV>")


def build_config():
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", FAKE_URL)
    return cfg


def revision_graph(script):
    """base -> head order: the order `upgrade head` applies revisions in."""
    revs = list(script.walk_revisions(base="base", head="heads"))
    revs.reverse()
    graph = [
        {
            "revision": r.revision,
            "down_revision": r.down_revision,
            "branch_labels": sorted(r.branch_labels) if r.branch_labels else [],
        }
        for r in revs
    ]
    return graph, [r.revision for r in revs]


def offline_sql(cfg, graph):
    """One `--sql` range per revision (down_revision:revision) -- no DB write.

    Isolated per revision (rather than one base:head sweep) so a migration
    that can't render offline (006, see module docstring) doesn't blank out
    every revision after it -- each range only replays that one revision's
    upgrade(), regardless of what precedes it in the chain.
    """
    down_of = {g["revision"]: g["down_revision"] for g in graph}
    results = {}
    for rev, down in down_of.items():
        rng = f"{down or 'base'}:{rev}"
        sql_buf, log_buf = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(sql_buf), redirect_stderr(log_buf):
                command.upgrade(cfg, rng, sql=True)
            entry = {"ok": True, "sql": canon(sql_buf.getvalue())}
        except Exception as exc:
            # Deliberately broad: record and compare ANY failure mode a
            # revision hits offline (see 006 in the module docstring),
            # rather than only the ones anticipated up front.
            entry = {
                "ok": False,
                "error": canon(f"{type(exc).__module__}.{type(exc).__name__}: {exc}"),
            }
        noisy = [
            canon(line)
            for line in log_buf.getvalue().splitlines()
            if line.strip() and not line.strip().startswith("INFO")
        ]
        if noisy:
            entry["log_non_info"] = noisy
        results[rev] = entry
    return results


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <out.json>")

    # Settings() (tgstats.core.config) is built as a module-level side effect
    # of env.py's `from tgstats.models import *` and has two required fields
    # with no default. Values are inert placeholders: nothing here reaches the
    # DDL alembic renders, which is driven entirely by FAKE_URL via the
    # alembic Config object above. Forced (not setdefault) so a real .env
    # sitting in cwd can never leak into this run or its output.
    os.environ["BOT_TOKEN"] = "0:PARITY"
    os.environ["DATABASE_URL"] = FAKE_URL

    cfg = build_config()

    load_log = io.StringIO()
    with warnings.catch_warnings(record=True) as caught, redirect_stderr(load_log):
        warnings.simplefilter("always")
        script = ScriptDirectory.from_config(cfg)
        graph, order = revision_graph(script)
        heads = sorted(script.get_heads())
        bases = sorted(script.get_bases())
        sql = offline_sql(cfg, graph)

    py_warnings = [canon(f"{w.category.__name__}: {w.message}") for w in caught]
    load_warnings = [canon(line) for line in load_log.getvalue().splitlines() if line.strip()]

    import alembic
    import sqlalchemy

    out = {
        "versions": {"alembic": alembic.__version__, "sqlalchemy": sqlalchemy.__version__},
        "bases": bases,
        "heads": heads,
        "graph": graph,
        "upgrade_order": order,
        "offline_sql": sql,
        "warnings": py_warnings + load_warnings,
    }
    with open(sys.argv[1], "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)

    rendered = sum(1 for v in sql.values() if v["ok"])
    print(
        f"alembic {alembic.__version__} | sqlalchemy {sqlalchemy.__version__}: "
        f"{len(order)} revisions, head={heads[0] if len(heads) == 1 else heads}, "
        f"{rendered}/{len(order)} rendered offline SQL, {len(out['warnings'])} warning(s)"
    )


if __name__ == "__main__":
    main()
