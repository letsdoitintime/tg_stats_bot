"""Webhook router for Telegram updates."""

from typing import Dict

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from telegram import Update
from telegram.ext import Application

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/tg", tags=["webhook"])

# Global variable to store the bot application
bot_app: Application = None


def set_bot_application(application: Application) -> None:
    """Set the bot application instance for webhook handling."""
    global bot_app
    bot_app = application


def get_bot_application() -> Application:
    """Get the bot application instance."""
    if bot_app is None:
        raise HTTPException(status_code=500, detail="Bot application not initialized")
    return bot_app


@router.post("/webhook")
async def telegram_webhook(
    request: Request, bot_application: Application = Depends(get_bot_application)
) -> Dict[str, str]:
    """Telegram webhook endpoint."""
    try:
        update_data = await request.json()
        logger.debug("Received webhook update", update_data=update_data)

        update = Update.de_json(update_data, bot_application.bot)
        if update is None:
            logger.warning("Could not parse update from webhook data")
            raise HTTPException(status_code=400, detail="Invalid update data")

        await bot_application.process_update(update)
        return {"status": "ok"}

    except Exception as e:
        logger.error("Error processing webhook update", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing update")


@router.post("/webhook")
async def telegram_webhook(
    request: Request, bot_application: Application = Depends(get_bot_application)
) -> Dict[str, str]:
    """Telegram webhook endpoint."""
    try:
        update_data = await request.json()
        logger.debug("Received webhook update", extra={"update_data": update_data})

        update = Update.de_json(update_data, bot_application.bot)
        if update is None:
            logger.warning("Could not parse update from webhook data")
            raise HTTPException(status_code=400, detail="Invalid update data")

        await bot_application.process_update(update)
        return {"status": "ok"}

    except Exception as e:
        logger.error("Error processing webhook update", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing update")


@router.get("/healthz")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "tg-stats-bot"}
