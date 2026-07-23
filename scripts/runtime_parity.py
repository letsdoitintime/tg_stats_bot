"""Cross-version parity harness for python-telegram-bot and celery.

Killer questions:
  - telegram: python-telegram-bot objects are IMMUTABLE (assigning an
    attribute raises AttributeError -- tests/test_unit_of_work.py:47 already
    learned this the hard way for Chat.username). Does every attribute
    tgstats/repositories/{message,chat,user}_repository.py and
    tgstats/utils/features.py read still exist on a REAL constructor-built
    Message/Chat/User, with the same type, and is it still immutable the same
    way? A renamed/retyped/removed attribute would silently corrupt stored
    analytics -- the repos guard every optional read with getattr(..., default)
    or hasattr(), so nothing crashes, it just quietly starts storing the
    default instead of the real value.
  - celery: does a task still serialize to the same wire message (headers +
    body) and resolve to the same dotted name? celery_tasks.py's beat
    schedule and retry decorators are the config surface that must survive;
    kombu and billiard move WITH celery, so their versions are part of the
    contract too.

No network calls anywhere: telegram objects are built with their own
constructors (no Bot, no token, no HTTP client). The celery wire message is
captured through kombu's in-process `memory://` transport, which is a REAL
publish/consume round trip through a fake transport -- not a real broker, but
not task_always_eager either, so the actual message-protocol code path runs.

Run once per venv, then diff:

    venv/bin/python scripts/runtime_parity.py /tmp/rt_old.json
    probe/bin/python scripts/runtime_parity.py /tmp/rt_new.json
    diff /tmp/rt_old.json /tmp/rt_new.json

Version numbers are deliberately NOT written into the JSON (see the same
choice in emoji_parity.py) -- they go to stdout only, so a byte-identical
artifact stays byte-identical across a version bump instead of always
showing a version-string diff that hides the real signal.
"""

import inspect
import json
import sys
from datetime import datetime, timezone
from importlib.metadata import version as pkg_version

import telegram
from celery import Celery
from celery.schedules import crontab
from telegram.ext import ApplicationBuilder, Updater
from telegram.request import HTTPXRequest

# ---------------------------------------------------------------------------
# telegram: attribute lists sourced from tests/conftest.py's make_tg_chat /
# make_tg_message / make_tg_user builders (which enumerate every field the
# ORM writes) plus the direct attribute / getattr / hasattr reads in
# tgstats/repositories/{message,chat,user}_repository.py and
# tgstats/utils/features.py.
# ---------------------------------------------------------------------------

MESSAGE_ATTRS = [
    "message_id",
    "date",
    "edit_date",
    "text",
    "caption",
    "entities",
    "caption_entities",
    "chat",
    "from_user",
    "reply_to_message",
    "message_thread_id",
    "photo",
    "video",
    "audio",
    "voice",
    "document",
    "sticker",
    "animation",
    "video_note",
    "contact",
    "location",
    "venue",
    "poll",
    "dice",
    "game",
    "web_page",
    "forward_date",
    "forward_from",
    "forward_from_chat",
    "forward_from_message_id",
    "forward_signature",
    "forward_sender_name",
    "is_automatic_forward",
    "via_bot",
    "author_signature",
    "media_group_id",
    "has_protected_content",
]

CHAT_ATTRS = [
    "id",
    "title",
    "username",
    "type",
    "is_forum",
    "has_protected_content",
    "description",
    "photo",
    "permissions",
    "pinned_message",
    "invite_link",
    "slow_mode_delay",
    "message_auto_delete_time",
    "linked_chat_id",
    "sticker_set_name",
    "can_set_sticker_set",
]

USER_ATTRS = [
    "id",
    "username",
    "first_name",
    "last_name",
    "language_code",
    "is_bot",
    "is_premium",
    "added_to_attachment_menu",
    "can_join_groups",
    "can_read_all_group_messages",
    "supports_inline_queries",
]

# message_repository.py reads this same getattr-guarded set off whichever
# media object wins the elif chain (photo/video/document/audio/voice/
# video_note/animation/sticker), plus media_obj.thumbnail.file_id.
MEDIA_ATTRS = [
    "file_id",
    "file_unique_id",
    "file_size",
    "file_name",
    "mime_type",
    "duration",
    "width",
    "height",
    "thumbnail",
]

# One constructor call per media type in message_repository.py's elif chain --
# only the fields each real type accepts are kept (filtered dynamically).
MEDIA_CTOR_KWARGS = {
    "PhotoSize": dict(
        file_id="photo1", file_unique_id="uphoto1", width=1280, height=720, file_size=204800
    ),
    "Video": dict(
        file_id="vid1",
        file_unique_id="uvid1",
        width=640,
        height=480,
        duration=12,
        mime_type="video/mp4",
        file_size=1048576,
        file_name="clip.mp4",
    ),
    "Document": dict(
        file_id="doc1",
        file_unique_id="udoc1",
        file_name="report.pdf",
        mime_type="application/pdf",
        file_size=51200,
    ),
    "Audio": dict(
        file_id="aud1",
        file_unique_id="uaud1",
        duration=180,
        mime_type="audio/mpeg",
        file_size=3145728,
        file_name="song.mp3",
    ),
    "Voice": dict(
        file_id="voi1", file_unique_id="uvoi1", duration=5, mime_type="audio/ogg", file_size=8192
    ),
    "VideoNote": dict(
        file_id="vn1", file_unique_id="uvn1", length=240, duration=8, file_size=131072
    ),
    "Animation": dict(
        file_id="anim1",
        file_unique_id="uanim1",
        width=320,
        height=240,
        duration=3,
        file_name="fun.gif",
        mime_type="video/mp4",
        file_size=65536,
    ),
    "Sticker": dict(
        file_id="stick1",
        file_unique_id="ustick1",
        width=512,
        height=512,
        is_animated=False,
        is_video=False,
        type="regular",
        file_size=16384,
    ),
}


def _accepted_params(cls):
    """Constructor parameter names cls.__init__ actually accepts (minus self)."""
    return set(inspect.signature(cls.__init__).parameters) - {"self"}


def _full_slots(cls):
    """Every __slots__ entry across the class's MRO, in first-seen order.

    PTB objects are slotted end to end (Chat.__slots__ is literally empty --
    its instance attributes live on _ChatBase further up the MRO), so this is
    the only way to see the real, complete attribute surface rather than just
    __init__'s parameter list.
    """
    seen = []
    for klass in cls.__mro__:
        for slot in getattr(klass, "__slots__", ()):
            if slot not in seen:
                seen.append(slot)
    return sorted(seen)


def _filtered(desired, accepted):
    return {k: v for k, v in desired.items() if k in accepted}


def _probe_attrs(instance, attrs, accepted_params):
    """For each attr: does it exist, what type, and is it settable."""
    out = {}
    for name in attrs:
        entry = {"in_constructor_params": name in accepted_params}
        try:
            value = getattr(instance, name)
            entry["exists"] = True
            entry["type"] = type(value).__name__
            entry["repr"] = repr(value)[:200]
        except AttributeError as exc:
            entry["exists"] = False
            entry["type"] = None
            entry["repr"] = None
            entry["get_error"] = str(exc)
        try:
            # Self-assignment: writes back whatever is already there (or None
            # for an absent attribute), so this never invents new data -- it
            # only asks "does the class let me write here at all."
            setattr(instance, name, getattr(instance, name, None))
            entry["settable"] = True
            entry["set_error"] = None
        except AttributeError as exc:
            entry["settable"] = False
            entry["set_error"] = str(exc)
        out[name] = entry
    return out


def build_user():
    accepted = _accepted_params(telegram.User)
    desired = dict(
        id=123456789,
        first_name="Test",
        is_bot=False,
        last_name="User",
        username="testuser",
        language_code="en",
        is_premium=False,
        added_to_attachment_menu=False,
        can_join_groups=True,
        can_read_all_group_messages=False,
        supports_inline_queries=False,
    )
    return telegram.User(**_filtered(desired, accepted)), accepted


def build_chat():
    accepted = _accepted_params(telegram.Chat)
    desired = dict(
        id=-1001234567890, type="supergroup", title="Test Chat", username="testchat", is_forum=False
    )
    return telegram.Chat(**_filtered(desired, accepted)), accepted


def build_message(chat, user):
    accepted = _accepted_params(telegram.Message)
    now = datetime(2025, 1, 20, 12, 0, tzinfo=timezone.utc)
    desired = dict(
        message_id=1,
        date=now,
        chat=chat,
        from_user=user,
        text="Test message",
        caption=None,
        entities=(),
        caption_entities=(),
        edit_date=None,
        is_automatic_forward=False,
        has_protected_content=False,
        message_thread_id=None,
        via_bot=None,
        author_signature=None,
        media_group_id=None,
        reply_to_message=None,
        photo=(),
        video=None,
        audio=None,
        voice=None,
        document=None,
        sticker=None,
        animation=None,
        video_note=None,
        contact=None,
        location=None,
        venue=None,
        poll=None,
        dice=None,
        game=None,
        # Bot API 7.0 replaced these with forward_origin; kept here so the
        # probe records (for both versions) that they are NOT accepted.
        forward_date=None,
        forward_from=None,
        forward_from_chat=None,
        forward_from_message_id=None,
        forward_signature=None,
        forward_sender_name=None,
        web_page=None,
    )
    return telegram.Message(**_filtered(desired, accepted)), accepted


def immutability_probe(chat):
    """The exact exception tests rely on (tests/test_unit_of_work.py:47)."""
    try:
        chat.username = "changed"
        return {"raised": False, "type": None, "message": None}
    except Exception as exc:
        return {"raised": True, "type": type(exc).__name__, "message": str(exc)}


def photo_max_probe():
    """Locks in message_repository.py's `max(tg_message.photo, key=...)` idiom."""
    accepted = _accepted_params(telegram.PhotoSize)
    small = telegram.PhotoSize(
        **_filtered(
            dict(file_id="small", file_unique_id="usmall", width=90, height=90, file_size=1000),
            accepted,
        )
    )
    large = telegram.PhotoSize(
        **_filtered(
            dict(
                file_id="large", file_unique_id="ularge", width=1280, height=1280, file_size=204800
            ),
            accepted,
        )
    )
    winner = max((small, large), key=lambda p: p.file_size or 0)
    return {"winner_file_id": winner.file_id, "matches_largest": winner.file_id == "large"}


def media_types_probe():
    out = {}
    for name, kwargs in MEDIA_CTOR_KWARGS.items():
        cls = getattr(telegram, name)
        accepted = _accepted_params(cls)
        instance = cls(**_filtered(kwargs, accepted))
        out[name] = _probe_attrs(instance, MEDIA_ATTRS, accepted)
    return out


def entities_probe(user):
    accepted = _accepted_params(telegram.MessageEntity)
    plain = telegram.MessageEntity(**_filtered(dict(type="url", offset=0, length=4), accepted))
    with_user = telegram.MessageEntity(
        **_filtered(dict(type="text_mention", offset=0, length=4, user=user), accepted)
    )
    attrs = ["type", "offset", "length", "url", "user", "language"]
    return {
        "plain": _probe_attrs(plain, attrs, accepted),
        "with_user": _probe_attrs(with_user, attrs, accepted),
        "user_to_dict_keys": sorted(with_user.user.to_dict().keys()) if with_user.user else None,
    }


def polling_signatures():
    """tgstats/bot_main.py's polling setup (HTTPXRequest, get_updates_request,
    Updater.start_polling) is untouched by this task, but a renamed kwarg here
    would break the SAME timeout config the task must not modify."""

    def params(fn):
        return list(inspect.signature(fn).parameters.keys())

    return {
        "HTTPXRequest.__init__": params(HTTPXRequest.__init__),
        "ApplicationBuilder.get_updates_request": params(ApplicationBuilder.get_updates_request),
        "Updater.start_polling": params(Updater.start_polling),
    }


def telegram_probe():
    user, user_accepted = build_user()
    chat, chat_accepted = build_chat()
    message, message_accepted = build_message(chat, user)

    return {
        "full_attribute_surface": {
            "Message": _full_slots(telegram.Message),
            "Chat": _full_slots(telegram.Chat),
            "User": _full_slots(telegram.User),
            # Not the runtime type message.chat ever is (that's Chat) -- kept
            # for context, since it is where the CHAT_ATTRS extended fields
            # (description/photo/permissions/...) actually live.
            "ChatFullInfo": _full_slots(telegram.ChatFullInfo),
        },
        "checked": {
            "Message": _probe_attrs(message, MESSAGE_ATTRS, message_accepted),
            "Chat": _probe_attrs(chat, CHAT_ATTRS, chat_accepted),
            "User": _probe_attrs(user, USER_ATTRS, user_accepted),
        },
        "immutability_probe_chat_username": immutability_probe(chat),
        "photo_max_probe": photo_max_probe(),
        "media_types": media_types_probe(),
        "entities": entities_probe(user),
        "polling_signatures": polling_signatures(),
    }


# ---------------------------------------------------------------------------
# celery: config mirrors tgstats/celery_tasks.py's celery_app.conf.update(...)
# (lines 52-77) and its two @celery_app.task(...) decorators, LITERALLY --
# not imported, because importing celery_tasks.py calls
# check_timescaledb_available() (a live DB connection) at module level and
# needs tgstats.core.config.settings (BOT_TOKEN/DATABASE_URL), neither of
# which this harness may touch. Update this block by hand if celery_tasks.py's
# config changes.
# ---------------------------------------------------------------------------

CELERY_CONF = dict(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # tgstats/core/constants.py TASK_TIME_LIMIT
    task_soft_time_limit=25 * 60,  # TASK_SOFT_TIME_LIMIT
    worker_prefetch_multiplier=1,  # WORKER_PREFETCH_MULTIPLIER
    worker_max_tasks_per_child=1000,  # WORKER_MAX_TASKS_PER_CHILD
    worker_max_memory_per_child=512000,
    worker_disable_rate_limits=False,
    task_default_priority=5,
    task_inherit_parent_priority=True,
    result_expires=3600,
    result_compression="gzip",
    worker_pool_restarts=True,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
)

# tgstats/core/config.py Settings field defaults. CELERY_TASK_MAX_RETRIES /
# CELERY_TASK_RETRY_DELAY env vars can override these in a real deployment;
# the harness only needs A fixed value to prove the retry-decorator SHAPE
# still works, not to mirror whatever the live environment happens to set.
RETRY_KWARGS = {"max_retries": 3, "countdown": 60}

BEAT_SCHEDULE = {
    "refresh-chat-daily-mv": {
        "task": "tgstats.celery_tasks.refresh_materialized_view",
        "schedule": crontab(minute="*/10"),
        "args": ("chat_daily_mv",),
        "options": {"jitter": True, "max_retries": 3},
    },
    "refresh-user-chat-daily-mv": {
        "task": "tgstats.celery_tasks.refresh_materialized_view",
        "schedule": crontab(minute="*/10"),
        "args": ("user_chat_daily_mv",),
        "options": {"jitter": True, "max_retries": 3},
    },
    "refresh-chat-hourly-heatmap-mv": {
        "task": "tgstats.celery_tasks.refresh_materialized_view",
        "schedule": crontab(minute="*/10"),
        "args": ("chat_hourly_heatmap_mv",),
        "options": {"jitter": True, "max_retries": 3},
    },
}

# Fixed so the wire capture is reproducible; id/root_id/correlation_id all
# derive from this. origin/reply_to/delivery_tag are still host- or
# connection-specific and get masked in _canon_message regardless.
FIXED_TASK_ID = "00000000-0000-0000-0000-000000000000"

TASK_NAMES = (
    "tgstats.celery_tasks.refresh_materialized_view",
    "tgstats.celery_tasks.retention_preview",
)


def build_celery_app():
    app = Celery(
        "tgstats",
        broker="memory://",  # in-process kombu transport -- never a real broker
        backend="cache+memory://",
    )
    app.conf.update(**CELERY_CONF)
    app.conf.beat_schedule = dict(BEAT_SCHEDULE)

    @app.task(
        bind=True,
        name="tgstats.celery_tasks.refresh_materialized_view",
        autoretry_for=(Exception,),
        retry_kwargs=RETRY_KWARGS,
        retry_backoff=True,
        retry_jitter=True,
    )
    def refresh_materialized_view(self, view_name):
        return {"view_name": view_name}

    @app.task(
        bind=True,
        name="tgstats.celery_tasks.retention_preview",
        autoretry_for=(Exception,),
        retry_kwargs=RETRY_KWARGS,
        retry_backoff=True,
        retry_jitter=True,
    )
    def retention_preview(self, chat_id):
        return {"chat_id": chat_id}

    return app


def conf_roundtrip(app):
    """Read every configured key back off app.conf -- catches a renamed or
    silently-dropped celery setting between versions."""
    return {key: repr(getattr(app.conf, key)) for key in CELERY_CONF}


def beat_schedule_shape(app):
    out = {}
    for key, entry in app.conf.beat_schedule.items():
        schedule = entry["schedule"]
        out[key] = {
            "task": entry["task"],
            "schedule_repr": repr(schedule),
            "schedule_minute": sorted(schedule.minute),
            "args": list(entry["args"]),
            "options": entry["options"],
        }
    return out


def task_registration(app):
    out = {}
    for name in TASK_NAMES:
        task = app.tasks[name]
        out[name] = {
            "registered": name in app.tasks,
            "autoretry_for": [c.__name__ for c in task.autoretry_for],
            "retry_kwargs": task.retry_kwargs,
            "retry_backoff": task.retry_backoff,
            "retry_jitter": task.retry_jitter,
            "max_retries": task.max_retries,
            "track_started": task.track_started,
            "time_limit": task.time_limit,
            "soft_time_limit": task.soft_time_limit,
        }
    return out


_MASKED_HEADERS = {"origin"}
_MASKED_PROPERTIES = {"reply_to", "delivery_tag"}


def _canon_message(msg):
    headers = dict(msg.headers)
    for key in _MASKED_HEADERS:
        if key in headers:
            headers[key] = "<MASKED>"
    properties = dict(msg.properties)
    for key in _MASKED_PROPERTIES:
        if key in properties:
            properties[key] = "<MASKED>"
    properties.pop("delivery_info", None)  # duplicate of msg.delivery_info below
    return {
        "headers": headers,
        "properties": properties,
        "delivery_info": msg.delivery_info,
        "content_type": msg.content_type,
        "content_encoding": msg.content_encoding,
        "body": json.loads(msg.body),
    }


def send_and_capture(app, task_name, args):
    """Publish through kombu's in-process memory:// transport and read back
    exactly what the broker received -- no real broker, but a real publish."""
    task = app.tasks[task_name]
    task.apply_async(args=args, task_id=FIXED_TASK_ID)
    with app.connection_for_read() as conn:
        queue = conn.SimpleQueue("celery")
        try:
            msg = queue.get(block=True, timeout=5)
            captured = _canon_message(msg)
            msg.ack()
        finally:
            queue.close()
    return captured


def celery_probe():
    app = build_celery_app()
    return {
        "conf_roundtrip": conf_roundtrip(app),
        "beat_schedule": beat_schedule_shape(app),
        "task_registration": task_registration(app),
        "serialized_messages": {
            "refresh_materialized_view": send_and_capture(
                app, "tgstats.celery_tasks.refresh_materialized_view", ("chat_daily_mv",)
            ),
            "retention_preview": send_and_capture(
                app, "tgstats.celery_tasks.retention_preview", (123456,)
            ),
        },
    }


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <out.json>")

    payload = {"telegram": telegram_probe(), "celery": celery_probe()}
    with open(sys.argv[1], "w") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)

    attr_count = sum(len(v) for v in payload["telegram"]["checked"].values())
    msg_count = len(payload["celery"]["serialized_messages"])
    versions = " | ".join(
        f"{name} {pkg_version(dist)}"
        for name, dist in (
            ("ptb", "python-telegram-bot"),
            ("celery", "celery"),
            ("kombu", "kombu"),
            ("billiard", "billiard"),
        )
    )
    print(f"{versions}: {attr_count} telegram attrs checked, {msg_count} celery messages captured")


if __name__ == "__main__":
    main()
