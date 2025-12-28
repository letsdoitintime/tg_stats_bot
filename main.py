"""
Telegram Analytics Bot - Entry point

This is a simple entry point that runs the bot.
For development, you can run this file directly.
For production, use the module: python -m tgstats.bot_main
"""

if __name__ == "__main__":
    from tgstats.bot_main import main
    import asyncio

    asyncio.run(main())
