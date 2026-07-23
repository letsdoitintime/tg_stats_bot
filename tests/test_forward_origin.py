"""Forward metadata must actually be recorded.

Regression tests for silent data loss. Bot API 7.0 replaced the flat
forward_from / forward_from_chat / forward_from_message_id / forward_signature
/ forward_sender_name / forward_date attributes with a single `forward_origin`
object, and python-telegram-bot removed the old ones. The repository still read
the old names behind hasattr()/getattr() guards, so every field silently
resolved to None.

Production confirmed the cost before this fix: 0 of 107,089 messages had ANY
forward metadata — including 175 that is_automatic_forward marks as channel
auto-forwards, which are forwards by definition.

The guards are why nothing raised. These tests assert on the VALUES, so a
future rename fails loudly instead of quietly zeroing a column.
"""

from datetime import datetime, timezone

from telegram import Chat as TelegramChat
from telegram import (
    MessageOriginChannel,
    MessageOriginChat,
    MessageOriginHiddenUser,
    MessageOriginUser,
)
from telegram import User as TelegramUser

from tgstats.repositories.message_repository import extract_forward_origin

WHEN = datetime(2025, 1, 7, 12, 30, 0, tzinfo=timezone.utc)


class _Msg:
    """Minimal stand-in — extract_forward_origin only reads forward_origin."""

    def __init__(self, origin):
        self.forward_origin = origin


def test_no_forward_origin_yields_all_none():
    assert extract_forward_origin(_Msg(None)) == (None, None, None, None, None, None)

    class _Bare:
        pass

    # A message object without the attribute at all must not raise.
    assert extract_forward_origin(_Bare()) == (None, None, None, None, None, None)


def test_forward_from_visible_user():
    user = TelegramUser(id=4242, first_name="Fwd", is_bot=False)
    got = extract_forward_origin(_Msg(MessageOriginUser(date=WHEN, sender_user=user)))
    user_id, chat_id, msg_id, sig, sender_name, date = got

    assert user_id == 4242
    assert (chat_id, msg_id, sig, sender_name) == (None, None, None, None)
    # normalised to naive UTC, like every other datetime stored here
    assert date == datetime(2025, 1, 7, 12, 30, 0) and date.tzinfo is None


def test_forward_from_hidden_user_keeps_the_name():
    got = extract_forward_origin(
        _Msg(MessageOriginHiddenUser(date=WHEN, sender_user_name="Someone"))
    )
    user_id, chat_id, msg_id, sig, sender_name, date = got

    # The user hid their account: no id is available, only the display name.
    assert user_id is None
    assert sender_name == "Someone"
    assert date == datetime(2025, 1, 7, 12, 30, 0)


def test_forward_from_channel_records_chat_and_message_id():
    chat = TelegramChat(id=-1001, type="channel", title="Chan")
    got = extract_forward_origin(
        _Msg(MessageOriginChannel(date=WHEN, chat=chat, message_id=99, author_signature="Editor"))
    )
    user_id, chat_id, msg_id, sig, sender_name, date = got

    # message_id is what makes a channel forward linkable back to the source.
    assert (chat_id, msg_id, sig) == (-1001, 99, "Editor")
    assert user_id is None and sender_name is None


def test_forward_on_behalf_of_chat_uses_sender_chat():
    chat = TelegramChat(id=-2002, type="supergroup", title="Group")
    got = extract_forward_origin(
        _Msg(MessageOriginChat(date=WHEN, sender_chat=chat, author_signature="Admin"))
    )
    user_id, chat_id, msg_id, sig, sender_name, date = got

    # MessageOriginChat exposes `sender_chat`, not `chat` — both must land in
    # the same column, which is the easiest half of this mapping to miss.
    assert chat_id == -2002
    assert sig == "Admin"
    assert msg_id is None and user_id is None


class TestForwardMetadataIsPersisted:
    """End-to-end: the columns must actually be populated on the stored row.

    Testing extract_forward_origin() alone is not enough — the earlier bug was
    in the WIRING, not in any helper. A test that only exercises the helper
    would pass with create_from_telegram() still dropping every value.
    """

    async def test_channel_forward_lands_in_the_row(self, test_session):
        from conftest import make_tg_chat, make_tg_message, make_tg_user

        from tgstats.models import Chat, User
        from tgstats.repositories.factory import RepositoryFactory

        test_session.add_all(
            [
                Chat(chat_id=123, title="Test", type="supergroup"),
                User(user_id=456, first_name="Test"),
            ]
        )
        await test_session.commit()

        source = TelegramChat(id=-1009, type="channel", title="Source")
        message = make_tg_message(
            message_id=7,
            date=datetime(2025, 1, 7, 12, 0, tzinfo=timezone.utc),
            chat=make_tg_chat(id=123, title="Test", type="supergroup"),
            from_user=make_tg_user(id=456),
            forward_origin=MessageOriginChannel(
                date=WHEN, chat=source, message_id=99, author_signature="Editor"
            ),
        )

        repos = RepositoryFactory(test_session)
        stored = await repos.message.create_from_telegram(
            message,
            text_raw="hi",
            text_len=2,
            urls_cnt=0,
            emoji_cnt=0,
            media_type="text",
            has_media=False,
        )
        await test_session.commit()

        assert stored.forward_from_chat_id == -1009
        assert stored.forward_from_message_id == 99
        assert stored.forward_signature == "Editor"
        assert stored.forward_date == datetime(2025, 1, 7, 12, 30, 0)

    async def test_plain_message_stores_no_forward_metadata(self, test_session):
        from conftest import make_tg_chat, make_tg_message, make_tg_user

        from tgstats.models import Chat, User
        from tgstats.repositories.factory import RepositoryFactory

        test_session.add_all(
            [
                Chat(chat_id=124, title="T2", type="supergroup"),
                User(user_id=457, first_name="T2"),
            ]
        )
        await test_session.commit()

        message = make_tg_message(
            message_id=8,
            date=datetime(2025, 1, 7, 12, 0, tzinfo=timezone.utc),
            chat=make_tg_chat(id=124, title="T2", type="supergroup"),
            from_user=make_tg_user(id=457),
        )

        repos = RepositoryFactory(test_session)
        stored = await repos.message.create_from_telegram(
            message,
            text_raw="hi",
            text_len=2,
            urls_cnt=0,
            emoji_cnt=0,
            media_type="text",
            has_media=False,
        )
        await test_session.commit()

        assert stored.forward_from_chat_id is None
        assert stored.forward_from_user_id is None
        assert stored.forward_date is None
