"""Cross-version parity harness for structlog.

Killer question for a logging library: does the configured processor chain
still RENDER THE SAME? structlog is imported by nearly every module here, and
a major bump can reorder keys, change how exceptions are folded in, or drop a
processor's output entirely — none of which any test asserts on, because tests
do not read log lines.

Renders a fixed set of events through the application's OWN chain (both the
json and text branches of utils/logging.py) and records the output. Timestamps
are the one genuinely variable part and are masked; everything else — key
order, level naming, exception formatting, unicode handling — is compared.

    venv/bin/python scripts/structlog_parity.py /tmp/sl_old.json
    probe/bin/python scripts/structlog_parity.py /tmp/sl_new.json
    diff /tmp/sl_old.json /tmp/sl_new.json
"""

import io
import json
import re
import sys
from importlib.metadata import version

import structlog

# Mask only what is genuinely non-deterministic. Anything else that moves is a
# real rendering change and must show up in the diff.
MASKS = [
    (re.compile(r'"timestamp":\s*"[^"]*"'), '"timestamp":"<TS>"'),
    (re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}[.,\d]*Z?"), "<TS>"),
    (re.compile(r'"pid":\s*\d+'), '"pid":<PID>'),
    (re.compile(r"pid=\d+"), "pid=<PID>"),
    (re.compile(r"0x[0-9a-f]+"), "0xADDR"),
    (re.compile(r'File "[^"]*"'), 'File "<PATH>"'),
    (re.compile(r"line \d+"), "line <N>"),
]


def mask(text):
    for pattern, repl in MASKS:
        text = pattern.sub(repl, text)
    return text


def render(processors):
    """Run the events through a chain and return the masked output lines."""
    out = io.StringIO()
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=out),
        cache_logger_on_first_use=False,
    )
    log = structlog.get_logger("parity")

    log.info("plain_event")
    log.info("with_fields", chat_id=-1001234567890, count=42, ratio=1.5, ok=True, missing=None)
    log.warning("unicode_event", title="ВелоПокатушки 🇺🇦")
    log.info("nested", payload={"a": [1, 2, None], "b": {"c": "d"}})
    log.bind(bound_key="bound_value").info("after_bind")
    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("with_exception")
    log.error("positional %s and %s", "one", "two")

    return [mask(line) for line in out.getvalue().splitlines()]


def chains():
    """Chains built from the application's OWN custom processors.

    add_app_context and ColoredConsoleRenderer are imported from
    tgstats.utils.logging rather than reproduced, so a change in how structlog
    invokes a custom processor shows up here. filter_by_level and
    add_logger_name are omitted only because they require the stdlib logger
    factory, which would make the output depend on logging config rather than
    on structlog itself.
    """
    from tgstats.utils.logging import ColoredConsoleRenderer, add_app_context

    common = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_app_context,
    ]
    return {
        "json": common + [structlog.processors.JSONRenderer()],
        "keyvalue": common + [structlog.processors.KeyValueRenderer(sort_keys=True)],
        "console": common + [structlog.dev.ConsoleRenderer(colors=False)],
        "app_colored": common + [ColoredConsoleRenderer()],
    }


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <out.json>")

    result = {name: render(chain) for name, chain in chains().items()}
    with open(sys.argv[1], "w") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)

    total = sum(len(v) for v in result.values())
    print(f"structlog {version('structlog')}: {total} rendered lines across {len(result)} chains")


if __name__ == "__main__":
    main()
