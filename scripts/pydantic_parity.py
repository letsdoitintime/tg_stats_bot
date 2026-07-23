"""Cross-version parity harness for pydantic and pydantic-settings.

Killer question for a validation library: do VALIDATION and COERCION
semantics still produce the same result -- same accepted values, same
rejected values, same error SHAPE, same coerced types? This app leans on
that in three places: the FastAPI response models in schemas/api.py (a
public wire contract -- two endpoints once returned HTTP 500 for months
because handler kwargs disagreed with these models), the "on"/"off" -> bool
coercion in schemas/commands.py, and the Settings validators in
core/config.py, whose error MESSAGES tests/test_bot_timeout_config.py
asserts on verbatim.

For every model in schemas/api.py and schemas/commands.py this records:
  - fields: name -> (annotation repr, required, default repr) -- a field
    silently becoming optional is a wire-contract change.
  - model_json_schema(), sorted.
  - one VALID construction's model_dump().
  - a table of named cases (invalid input AND coercion input side by side --
    an accepted case flipping to rejected, or vice versa, is exactly the
    regression this harness exists to catch). Each case records either the
    successful dump or the full ValidationError shape (type/loc/msg/input
    per error) -- never just "it raised".

Settings gets the same good/bad-kwargs treatment for every field_validator
and model_validator in core/config.py, plus a check of the deprecated
Field(..., env=...) style: still just a warning in 2.13, or has it become a
raised exception (a hard-stop, not a bump)?

Nothing here is masked as "noise": the four error keys captured (type, loc,
msg, input) are hand-picked and never include pydantic's own 'url' key, so
the one genuinely version-tied string pydantic emits (the errors.pydantic.dev
doc-link, which embeds the pydantic version) never enters the artifact. The
sole exception is the deprecation-warning text, captured verbatim because the
whole message is the point -- there the version segment in the embedded
migration-guide link IS masked, and that is the only masking this script does.

Never touches a real .env: BOT_TOKEN/DATABASE_URL are set to literals before
tgstats.core.config is even imported, because that module instantiates a
global `settings = Settings()` at import time (core/config.py:~181).

    venv/bin/python scripts/pydantic_parity.py /tmp/pyd_old.json
    /tmp/probe_pyd/bin/python scripts/pydantic_parity.py /tmp/pyd_new.json
    diff /tmp/pyd_old.json /tmp/pyd_new.json
"""

import inspect
import json
import os
import re
import sys
import warnings
from importlib.metadata import version
from pathlib import Path

# Make `import tgstats` resolve to THIS checkout. Without this, a script
# invoked as `venv/bin/python scripts/pydantic_parity.py` gets sys.path[0] =
# scripts/, tgstats isn't there, and Python falls through to whatever
# editable install sits in site-packages -- which can be a stale copy frozen
# at `pip install -e .` time, silently testing the wrong source entirely.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# core/config.py instantiates a module-level `settings = Settings()` on
# import. Set literals BEFORE that import runs so this script never reads a
# real .env -- these two values are never printed, only used to let the
# import succeed.
os.environ.setdefault("BOT_TOKEN", "parity_probe_dummy_token")
os.environ.setdefault("DATABASE_URL", "postgresql://parity-probe.invalid/unused")

from pydantic import BaseModel, ValidationError  # noqa: E402

# Field(..., env=...) and the class-based `Config` both warn at CLASS
# DEFINITION time -- i.e. once, while this import executes the `class
# Settings(BaseSettings):` body -- not on every Settings(...) instantiation.
# Capturing this later, around a call, would silently observe nothing:
# Settings is only ever defined once per process, so there is nothing left
# to warn about by the time any function below runs. Capture it here, at the
# only moment it actually happens.
with warnings.catch_warnings(record=True) as _CLASS_DEFINITION_WARNINGS:
    warnings.simplefilter("always")
    from tgstats.core.config import Settings  # noqa: E402
from tgstats.schemas import api, commands  # noqa: E402

# The one genuinely version-tied string pydantic emits: its own version
# embedded in the migration-guide URL of a deprecation warning's message.
# Masked ONLY here, because this is the only place a whole message string is
# captured verbatim rather than hand-picked keys.
_VERSION_IN_URL = re.compile(r"errors\.pydantic\.dev/[^/]+/")


def _mask(text):
    return _VERSION_IN_URL.sub("errors.pydantic.dev/<VER>/", text)


def _models_in(module):
    """Every BaseModel subclass DEFINED IN this module (not imported into it)."""
    return {
        name: obj
        for name, obj in vars(module).items()
        if inspect.isclass(obj) and issubclass(obj, BaseModel) and obj.__module__ == module.__name__
    }


def field_summary(model_cls):
    """name -> [annotation repr, required, default repr].

    A field silently becoming optional, or a default silently changing
    type, is a wire-contract break that model_dump() of one valid instance
    would never reveal.
    """
    return {
        name: [repr(f.annotation), f.is_required(), repr(f.default)]
        for name, f in model_cls.model_fields.items()
    }


def _error_shape(exc):
    return {
        "error_count": len(exc.errors()),
        "errors": [
            {"type": e["type"], "loc": list(e["loc"]), "msg": e["msg"], "input": e.get("input")}
            for e in exc.errors()
        ],
    }


def try_construct(model_cls, kwargs):
    """Attempt construction; record success+dump or failure+error shape."""
    try:
        return {"ok": True, "dump": model_cls(**kwargs).model_dump()}
    except ValidationError as exc:
        return {"ok": False, **_error_shape(exc)}


def probe_model(model_cls, valid_kwargs, cases):
    return {
        "fields": field_summary(model_cls),
        "schema": model_cls.model_json_schema(),
        "valid": model_cls(**valid_kwargs).model_dump(),
        "cases": {name: try_construct(model_cls, kw) for name, kw in cases.items()},
    }


# ---------------------------------------------------------------------------
# schemas/api.py -- every model, valid kwargs + a table of named cases.
# ---------------------------------------------------------------------------

API_MODELS = {
    "ChatSummary": (
        api.ChatSummary,
        dict(
            chat_id=-1001234567890, title="ВелоПокатушки 🇺🇦", msg_count_30d=150, avg_dau_30d=12.345
        ),
        {
            "missing_title": dict(chat_id=1, msg_count_30d=1, avg_dau_30d=1.0),
            "none_title_ok": dict(chat_id=1, title=None, msg_count_30d=1, avg_dau_30d=1.0),
            "coerce_int_like_string_chat_id": dict(
                chat_id="42", title="t", msg_count_30d=1, avg_dau_30d=1.0
            ),
            "coerce_whole_float_to_int": dict(
                chat_id=1, title="t", msg_count_30d=5.0, avg_dau_30d=1.0
            ),
            "reject_fractional_float_to_int": dict(
                chat_id=1, title="t", msg_count_30d=5.9, avg_dau_30d=1.0
            ),
            "reject_non_numeric_chat_id": dict(
                chat_id="not-an-int", title="t", msg_count_30d=1, avg_dau_30d=1.0
            ),
            "coerce_int_to_float": dict(chat_id=1, title="t", msg_count_30d=1, avg_dau_30d=7),
        },
    ),
    "ChatSettings": (
        api.ChatSettings,
        dict(
            chat_id=1,
            store_text=True,
            text_retention_days=30,
            metadata_retention_days=90,
            timezone="UTC",
            locale="en",
            capture_reactions=False,
        ),
        {
            "missing_store_text": dict(
                chat_id=1,
                text_retention_days=30,
                metadata_retention_days=90,
                timezone="UTC",
                locale="en",
                capture_reactions=False,
            ),
            "coerce_bool_from_string_true": dict(
                chat_id=1,
                store_text="true",
                text_retention_days=30,
                metadata_retention_days=90,
                timezone="UTC",
                locale="en",
                capture_reactions=False,
            ),
            "coerce_bool_from_int_1": dict(
                chat_id=1,
                store_text=True,
                text_retention_days=30,
                metadata_retention_days=90,
                timezone="UTC",
                locale="en",
                capture_reactions=1,
            ),
            "reject_ambiguous_bool_string": dict(
                chat_id=1,
                store_text="maybe",
                text_retention_days=30,
                metadata_retention_days=90,
                timezone="UTC",
                locale="en",
                capture_reactions=False,
            ),
        },
    ),
    "PeriodSummary": (
        api.PeriodSummary,
        dict(
            total_messages=1000,
            unique_users=50,
            avg_daily_users=12.5,
            new_users=5,
            left_users=2,
            start_date="2025-01-01",
            end_date="2025-01-31",
            days=31,
        ),
        {
            "missing_days": dict(
                total_messages=1000,
                unique_users=50,
                avg_daily_users=12.5,
                new_users=5,
                left_users=2,
                start_date="2025-01-01",
                end_date="2025-01-31",
            ),
            "coerce_numeric_string_total_messages": dict(
                total_messages="1000",
                unique_users=50,
                avg_daily_users=12.5,
                new_users=5,
                left_users=2,
                start_date="2025-01-01",
                end_date="2025-01-31",
                days=31,
            ),
            "reject_non_numeric_total_messages": dict(
                total_messages="a lot",
                unique_users=50,
                avg_daily_users=12.5,
                new_users=5,
                left_users=2,
                start_date="2025-01-01",
                end_date="2025-01-31",
                days=31,
            ),
        },
    ),
    "TimeseriesPoint": (
        api.TimeseriesPoint,
        dict(day="2025-01-07", value=42),
        {
            "missing_value": dict(day="2025-01-07"),
            "coerce_int_like_string_value": dict(day="2025-01-07", value="42"),
            "reject_non_numeric_value": dict(day="2025-01-07", value="forty-two"),
        },
    ),
    "UserStats": (
        api.UserStats,
        dict(
            user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name=None,
            msg_count=42,
            activity_percentage=13.5,
            active_days_ratio="10/30",
            last_message=None,
            days_since_joined=100,
            left=False,
        ),
        {
            "missing_username": dict(
                user_id=1,
                first_name=None,
                last_name=None,
                msg_count=1,
                activity_percentage=1.0,
                active_days_ratio="1/1",
                last_message=None,
                days_since_joined=None,
                left=False,
            ),
            "coerce_days_since_joined_string": dict(
                user_id=1,
                username=None,
                first_name=None,
                last_name=None,
                msg_count=1,
                activity_percentage=1.0,
                active_days_ratio="1/1",
                last_message=None,
                days_since_joined="15",
                left=False,
            ),
            "coerce_left_from_string_true": dict(
                user_id=1,
                username=None,
                first_name=None,
                last_name=None,
                msg_count=1,
                activity_percentage=1.0,
                active_days_ratio="1/1",
                last_message=None,
                days_since_joined=None,
                left="true",
            ),
            "reject_left_ambiguous": dict(
                user_id=1,
                username=None,
                first_name=None,
                last_name=None,
                msg_count=1,
                activity_percentage=1.0,
                active_days_ratio="1/1",
                last_message=None,
                days_since_joined=None,
                left="maybe",
            ),
        },
    ),
    "UserStatsResponse": (
        api.UserStatsResponse,
        dict(
            items=[
                dict(
                    user_id=1,
                    username=None,
                    first_name=None,
                    last_name=None,
                    msg_count=1,
                    activity_percentage=1.0,
                    active_days_ratio="1/1",
                    last_message=None,
                    days_since_joined=None,
                    left=False,
                )
            ],
            page=1,
            per_page=10,
            total=1,
            pages=1,
        ),
        {
            "empty_items_ok": dict(items=[], page=1, per_page=10, total=0, pages=0),
            "nested_invalid_item_shows_loc_path": dict(
                items=[
                    dict(
                        user_id=1,
                        username=None,
                        first_name=None,
                        last_name=None,
                        msg_count="not-an-int",
                        activity_percentage=1.0,
                        active_days_ratio="1/1",
                        last_message=None,
                        days_since_joined=None,
                        left=False,
                    )
                ],
                page=1,
                per_page=10,
                total=1,
                pages=1,
            ),
        },
    ),
    "RetentionPreviewRequest": (
        api.RetentionPreviewRequest,
        dict(chat_id=1),
        {
            "missing_chat_id": dict(),
            "coerce_int_like_string": dict(chat_id="555"),
        },
    ),
    "RetentionPreviewResponse": (
        api.RetentionPreviewResponse,
        dict(
            chat_id=1,
            text_retention_days=30,
            metadata_retention_days=90,
            store_text=True,
            text_removal_count=5,
            metadata_removal_count=10,
            reaction_removal_count=2,
            text_cutoff_date="2025-01-01",
            metadata_cutoff_date="2024-10-01",
        ),
        {
            "missing_store_text": dict(
                chat_id=1,
                text_retention_days=30,
                metadata_retention_days=90,
                text_removal_count=5,
                metadata_removal_count=10,
                reaction_removal_count=2,
                text_cutoff_date="2025-01-01",
                metadata_cutoff_date="2024-10-01",
            ),
            "coerce_bool_from_string_false": dict(
                chat_id=1,
                text_retention_days=30,
                metadata_retention_days=90,
                store_text="false",
                text_removal_count=5,
                metadata_removal_count=10,
                reaction_removal_count=2,
                text_cutoff_date="2025-01-01",
                metadata_cutoff_date="2024-10-01",
            ),
        },
    ),
}

# ---------------------------------------------------------------------------
# schemas/commands.py -- both models share the same "on"/"off" -> bool
# validator verbatim, so they share the same coercion sweep.
# ---------------------------------------------------------------------------

BOOL_COERCION_INPUTS = [
    "on",
    "off",
    "true",
    "false",
    "1",
    "0",
    "enabled",
    "disabled",
    "yes",
    "no",
    "ON",
    "Enabled",
    "maybe",
    True,
    False,
    2,
    1.0,
    None,
]


def _bool_command_cases():
    return {f"input_{v!r}": {"enabled": v} for v in BOOL_COERCION_INPUTS}


COMMAND_MODELS = {
    "SetTextCommand": (commands.SetTextCommand, dict(enabled=True), _bool_command_cases()),
    "SetReactionsCommand": (
        commands.SetReactionsCommand,
        dict(enabled=True),
        _bool_command_cases(),
    ),
}


# ---------------------------------------------------------------------------
# core/config.py Settings -- every field_validator and model_validator,
# plus the exact case tests/test_bot_timeout_config.py asserts wording on.
# ---------------------------------------------------------------------------

SETTINGS_BASE = {
    "bot_token": "dummy_token_for_parity_probe",
    "database_url": "postgresql://parity-probe.invalid/unused",
}

SETTINGS_CASES = {
    "minimal_required": dict(),
    "custom_bot_timeouts": dict(
        bot_read_timeout=60.0,
        bot_write_timeout=20.0,
        bot_connect_timeout=25.0,
        bot_get_updates_timeout=40,
        bot_get_updates_read_timeout=60.0,
        bot_poll_interval=1.0,
        bot_bootstrap_retries=5,
    ),
    "webhook_mode_with_url": dict(mode="webhook", webhook_url="https://example.invalid/hook"),
    "boundary_just_above_valid": dict(
        bot_get_updates_timeout=30, bot_get_updates_read_timeout=40.1
    ),
    "log_level_lowercase_coerced": dict(log_level="debug"),
    "string_typed_env_style_values": dict(
        db_pool_size="15",
        bot_read_timeout="12.5",
        log_to_file="false",
        enable_cache="true",
        cache_ttl="120",
    ),
    "bootstrap_retries_zero": dict(bot_bootstrap_retries=0),
    "poll_interval_half": dict(bot_poll_interval=0.5),
    "invalid_mode": dict(mode="not_a_mode"),
    "invalid_log_level": dict(log_level="NOPE"),
    "invalid_log_format": dict(log_format="xml"),
    "invalid_environment": dict(environment="nope"),
    "non_positive_db_pool_size": dict(db_pool_size=0),
    "negative_db_max_overflow": dict(db_max_overflow=-1),
    "non_positive_bot_connection_pool": dict(bot_connection_pool_size=0),
    "webhook_missing_url": dict(mode="webhook"),
    "db_pool_size_too_big": dict(db_pool_size=51),
    "db_max_overflow_too_big": dict(db_max_overflow=101),
    # The exact case tests/test_bot_timeout_config.py::test_invalid_get_updates_timeout_too_low
    # asserts the message of, verbatim ("must be greater than").
    "get_updates_timeout_too_low": dict(
        bot_get_updates_timeout=30, bot_get_updates_read_timeout=35.0
    ),
    # Exact boundary (30 + 10 == 40) must still fail -- the validator is
    # strictly "greater than", not ">=".
    "get_updates_timeout_exact_boundary": dict(
        bot_get_updates_timeout=30, bot_get_updates_read_timeout=40.0
    ),
}


def try_settings(overrides, use_base=True):
    kwargs = {**SETTINGS_BASE, **overrides} if use_base else dict(overrides)
    try:
        return {"ok": True, "dump": Settings(**kwargs).model_dump()}
    except ValidationError as exc:
        return {"ok": False, **_error_shape(exc)}


def settings_cases():
    result = {"missing_required_fields": try_settings({}, use_base=False)}
    result.update({name: try_settings(kw) for name, kw in SETTINGS_CASES.items()})
    return result


def settings_field_env_deprecation_report():
    """Is Field(..., env=...) still just a warning in this version?

    HARD-STOP if this dict is empty while the field count above main() is
    unchanged: that would mean the warnings vanished. HARD-STOP of a
    different kind if the import at the top of this file already crashed
    instead of printing a version line at all -- that means the deprecation
    escalated to a raised exception, a migration rather than a bump.
    """
    by_message = {}
    for w in _CLASS_DEFINITION_WARNINGS:
        key = f"{w.category.__name__}: {_mask(str(w.message))}"
        by_message[key] = by_message.get(key, 0) + 1
    return by_message


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <out.json>")

    # Prove every model in both files is actually covered above, not just
    # the ones this script's author remembered to type out by hand.
    actual_api = set(_models_in(api))
    actual_cmd = set(_models_in(commands))
    missing_api = actual_api - set(API_MODELS)
    missing_cmd = actual_cmd - set(COMMAND_MODELS)
    if missing_api or missing_cmd:
        sys.exit(
            f"uncovered models -- api.py: {missing_api or 'none'}, "
            f"commands.py: {missing_cmd or 'none'}"
        )

    result = {
        "api": {
            name: probe_model(cls, valid, cases) for name, (cls, valid, cases) in API_MODELS.items()
        },
        "commands": {
            name: probe_model(cls, valid, cases)
            for name, (cls, valid, cases) in COMMAND_MODELS.items()
        },
        "settings": settings_cases(),
        "settings_field_env_deprecation": settings_field_env_deprecation_report(),
    }

    with open(sys.argv[1], "w") as handle:
        json.dump(result, handle, indent=1, sort_keys=True, default=str)

    n_models = len(API_MODELS) + len(COMMAND_MODELS)
    n_cases = sum(len(c) for _, _, c in API_MODELS.values())
    n_cases += sum(len(c) for _, _, c in COMMAND_MODELS.values())
    n_cases += len(SETTINGS_CASES) + 1  # +1 for missing_required_fields
    print(
        f"pydantic {version('pydantic')} | pydantic-settings {version('pydantic-settings')}: "
        f"{n_models} models, {n_cases} cases"
    )


if __name__ == "__main__":
    main()
