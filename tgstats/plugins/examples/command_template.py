"""
Template for creating a new command plugin.

Copy this file to ../enabled/ and customize it for your needs.
"""

from typing import Dict, Callable

from telegram import Update
from telegram.ext import Application, ContextTypes

from ..base import CommandPlugin, PluginMetadata


class MyCommandPlugin(CommandPlugin):
    """
    TODO: Add your plugin description here.

    This plugin adds the following commands:
    - /mycommand - Does something
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_command_plugin",  # TODO: Change this
            version="1.0.0",
            description="TODO: Describe what your plugin does",
            author="Your Name",  # TODO: Add your name
            dependencies=[],  # TODO: Add Python packages if needed
        )

    async def initialize(self, app: Application) -> None:
        """
        Initialize the plugin.

        This is called once when the bot starts.
        Use this to:
        - Load configuration
        - Initialize external connections
        - Set up resources
        """
        self._logger.info("my_command_plugin_initialized")

        # TODO: Add initialization logic here
        # Example:
        # self.config = load_config()
        # self.api_client = SomeAPIClient()

    async def shutdown(self) -> None:
        """
        Shutdown the plugin gracefully.

        This is called when the bot stops.
        Use this to:
        - Close connections
        - Save state
        - Clean up resources
        """
        self._logger.info("my_command_plugin_shutdown")

        # TODO: Add cleanup logic here
        # Example:
        # await self.api_client.close()

    def get_commands(self) -> Dict[str, Callable]:
        """
        Return command handlers.

        Returns a dict mapping command names to handler functions.
        Command names should NOT include the leading slash.
        """
        return {
            "mycommand": self._my_command_handler,
            # TODO: Add more commands here
            # 'anothercommand': self._another_command_handler,
        }

    def get_command_descriptions(self) -> Dict[str, str]:
        """
        Return command descriptions for help text.

        These descriptions will be shown in /help and other help messages.
        """
        return {
            "mycommand": "TODO: Describe what this command does",
            # TODO: Add descriptions for all commands
        }

    async def _my_command_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /mycommand command.

        Args:
            update: The Telegram update
            context: The context from python-telegram-bot
        """
        if not update.message or not update.effective_chat:
            return

        # TODO: Implement your command logic here

        # Example: Simple reply
        await update.message.reply_text("Hello! This is my custom command.")

        # Example: Get arguments
        # args = context.args  # List of arguments after the command
        # if not args:
        #     await update.message.reply_text("Usage: /mycommand <arg1> <arg2>")
        #     return

        # Example: Check if in group
        # from tgstats.enums import ChatType
        # if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        #     await update.message.reply_text("This command only works in groups.")
        #     return

        # Example: Query database
        # from tgstats.db import async_session
        # from tgstats.services import ChatService
        #
        # async with async_session() as session:
        #     service = ChatService(session)
        #     settings = await service.get_chat_settings(update.effective_chat.id)
        #
        #     if not settings:
        #         await update.message.reply_text("Please run /setup first!")
        #         return

        # Example: Format response
        # response = f"""
        # **Results:**
        # • Item 1: Value 1
        # • Item 2: Value 2
        # """
        # await update.message.reply_text(response, parse_mode="Markdown")
