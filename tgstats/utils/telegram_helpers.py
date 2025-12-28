"""Telegram message sending utilities with flood control."""

import asyncio

from telegram import Update
from telegram.error import RetryAfter, TimedOut, NetworkError
import structlog

logger = structlog.get_logger(__name__)


async def send_message_with_retry(
    update: Update, text: str, max_retries: int = 3, delay_before_send: float = 0.0, **kwargs
) -> bool:
    """
    Send a message with automatic retry on flood control errors.

    This utility helps prevent Telegram API flooding by:
    1. Adding configurable delays before sending
    2. Automatically retrying on RetryAfter errors
    3. Using exponential backoff for network errors

    Args:
        update: Telegram update object
        text: Message text to send
        max_retries: Maximum number of retry attempts
        delay_before_send: Delay in seconds before sending (prevents flooding)
        **kwargs: Additional arguments for reply_text (parse_mode, etc.)

    Returns:
        True if message sent successfully, False otherwise

    Example:
        ```python
        # Send with 0.5 second delay to prevent flooding
        success = await send_message_with_retry(
            update,
            "Hello!",
            delay_before_send=0.5,
            parse_mode="Markdown"
        )
        ```
    """
    if not update.message:
        logger.warning("send_message_no_message_object")
        return False

    # Add delay before sending to prevent flooding
    if delay_before_send > 0:
        await asyncio.sleep(delay_before_send)

    for attempt in range(max_retries):
        try:
            await update.message.reply_text(text, **kwargs)
            logger.debug(
                "message_sent",
                chat_id=update.effective_chat.id if update.effective_chat else None,
                text_length=len(text),
            )
            return True

        except RetryAfter as e:
            retry_after = e.retry_after

            # Bound check for retry_after to prevent unreasonably long waits
            if retry_after > 300:  # Max 5 minutes
                logger.error(
                    "flood_control_excessive_wait",
                    chat_id=update.effective_chat.id if update.effective_chat else None,
                    retry_after=retry_after,
                )
                return False

            logger.warning(
                "flood_control_hit",
                chat_id=update.effective_chat.id if update.effective_chat else None,
                retry_after=retry_after,
                attempt=attempt + 1,
                max_retries=max_retries,
            )

            if attempt < max_retries - 1:
                # Wait for the Telegram-specified time plus a small buffer
                await asyncio.sleep(retry_after + 1)
            else:
                logger.error(
                    "flood_control_max_retries_exceeded",
                    chat_id=update.effective_chat.id if update.effective_chat else None,
                )
                return False

        except (TimedOut, NetworkError) as e:
            logger.warning(
                "network_error_retry",
                error=str(e),
                error_type=type(e).__name__,
                attempt=attempt + 1,
                max_retries=max_retries,
            )

            if attempt < max_retries - 1:
                # Exponential backoff: 2^attempt seconds
                backoff_time = 2**attempt
                await asyncio.sleep(backoff_time)
            else:
                logger.error("network_error_max_retries_exceeded", error=str(e))
                return False

        except Exception as e:
            logger.error(
                "message_send_unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return False

    return False


async def send_multiple_messages_with_delay(
    update: Update, messages: list[str], delay_between: float = 0.5, **kwargs
) -> int:
    """
    Send multiple messages with delays between them to prevent flooding.

    Args:
        update: Telegram update object
        messages: List of message texts to send
        delay_between: Delay in seconds between messages
        **kwargs: Additional arguments for reply_text

    Returns:
        Number of messages successfully sent

    Example:
        ```python
        messages = ["Message 1", "Message 2", "Message 3"]
        sent = await send_multiple_messages_with_delay(
            update,
            messages,
            delay_between=1.0
        )
        print(f"Sent {sent}/{len(messages)} messages")
        ```
    """
    sent_count = 0

    for i, text in enumerate(messages):
        # First message has no delay, subsequent messages have configured delay
        delay = 0 if i == 0 else delay_between

        success = await send_message_with_retry(update, text, delay_before_send=delay, **kwargs)

        if success:
            sent_count += 1
        else:
            logger.warning(
                "message_send_failed_in_batch", message_index=i, total_messages=len(messages)
            )

    logger.info(
        "batch_messages_sent",
        sent=sent_count,
        total=len(messages),
        success_rate=f"{sent_count/len(messages)*100:.1f}%" if messages else "N/A",
    )

    return sent_count


async def send_long_message(
    update: Update,
    text: str,
    max_length: int = 4096,
    split_marker: str = "\n\n---\n\n",
    delay_between: float = 0.5,
    **kwargs,
) -> int:
    """
    Send a long message, splitting it if necessary.

    Telegram has a 4096 character limit per message. This function
    automatically splits long messages and sends them with delays.

    Args:
        update: Telegram update object
        text: Message text (can be longer than Telegram limit)
        max_length: Maximum characters per message (default: 4096)
        split_marker: Text to insert between split messages
        delay_between: Delay between split messages
        **kwargs: Additional arguments for reply_text

    Returns:
        Number of message parts successfully sent

    Example:
        ```python
        long_text = "..." * 10000  # Very long text
        parts = await send_long_message(
            update,
            long_text,
            max_length=4096,
            delay_between=1.0
        )
        ```
    """
    if len(text) <= max_length:
        # Single message
        success = await send_message_with_retry(update, text, **kwargs)
        return 1 if success else 0

    # Split into multiple messages
    messages = []
    current = ""

    # Try to split on newlines for better readability
    paragraphs = text.split("\n")

    for para in paragraphs:
        # If single paragraph is too long, force split
        if len(para) > max_length:
            if current:
                messages.append(current)
                current = ""

            # Split long paragraph into chunks
            for i in range(0, len(para), max_length):
                messages.append(para[i : i + max_length])
            continue

        # Try to add paragraph to current message
        test = current + "\n" + para if current else para

        if len(test) > max_length:
            # Current message is full, start new one
            messages.append(current)
            current = para
        else:
            current = test

    # Add remaining text
    if current:
        messages.append(current)

    # Add split markers except for last message
    for i in range(len(messages) - 1):
        messages[i] += split_marker

    logger.info(
        "long_message_split", original_length=len(text), parts=len(messages), max_length=max_length
    )

    # Send all parts with delays
    return await send_multiple_messages_with_delay(
        update, messages, delay_between=delay_between, **kwargs
    )
