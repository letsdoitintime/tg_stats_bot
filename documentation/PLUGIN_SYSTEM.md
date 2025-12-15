# Plugin System Documentation

The Telegram Stats Bot includes a flexible plugin system that allows you to extend functionality without modifying core code.

## 📋 Table of Contents

- [Overview](#overview)
- [Plugin Types](#plugin-types)
- [Creating Plugins](#creating-plugins)
- [Built-in Examples](#built-in-examples)
- [Configuration](#configuration)
- [API Reference](#api-reference)

---

## Overview

The plugin system allows you to:

- ✅ Add new bot commands
- ✅ Create custom statistics/analytics
- ✅ Process messages with custom logic
- ✅ Extend bot services
- ✅ All without modifying core bot code!

### Architecture

```
tgstats/
├── plugins/
│   ├── __init__.py
│   ├── base.py              # Base plugin classes
│   ├── manager.py           # Plugin loader & manager
│   └── enabled/             # Place your plugins here!
│       ├── word_cloud.py
│       └── heatmap_command.py
```

---

## Plugin Types

### 1. CommandPlugin

Add new bot commands like `/mystats`, `/export`, etc.

**Use Cases:**
- Custom command handlers
- Admin utilities
- Data export commands

### 2. StatisticsPlugin

Generate custom analytics and statistics.

**Use Cases:**
- Word clouds
- Sentiment analysis
- Custom metrics
- Trend analysis

### 3. HandlerPlugin

Process all messages/reactions with custom logic.

**Use Cases:**
- Real-time filtering
- Content moderation
- Auto-responses
- Custom event tracking

### 4. ServicePlugin

Extend bot services with new business logic.

**Use Cases:**
- Data exporters
- Report generators
- Integration services

---

## Creating Plugins

### Quick Start

1. Create a new file in `tgstats/plugins/enabled/`
2. Import base classes from `..base`
3. Implement required methods
4. Restart the bot!

### Example: Simple Command Plugin

```python
"""my_plugin.py - Example command plugin"""

from typing import Dict, Callable
from telegram import Update
from telegram.ext import Application, ContextTypes
from ..base import CommandPlugin, PluginMetadata


class MyCommandPlugin(CommandPlugin):
    """My custom command plugin."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_commands",
            version="1.0.0",
            description="My custom commands",
            author="Your Name",
            dependencies=[]  # List Python packages needed
        )
    
    async def initialize(self, app: Application) -> None:
        """Called when plugin loads."""
        self._logger.info("My plugin initialized!")
    
    async def shutdown(self) -> None:
        """Called when bot shuts down."""
        self._logger.info("My plugin shutting down")
    
    def get_commands(self) -> Dict[str, Callable]:
        """Return command handlers."""
        return {
            'mycommand': self._my_command_handler,
        }
    
    def get_command_descriptions(self) -> Dict[str, str]:
        """Return command descriptions for help."""
        return {
            'mycommand': 'Does something cool',
        }
    
    async def _my_command_handler(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /mycommand."""
        await update.message.reply_text("Hello from my plugin!")
```

### Example: Statistics Plugin

```python
"""sentiment_plugin.py - Sentiment analysis"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import Application
from ..base import StatisticsPlugin, PluginMetadata


class SentimentPlugin(StatisticsPlugin):
    """Analyze message sentiment."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="sentiment_analysis",
            version="1.0.0",
            description="Analyzes message sentiment",
            author="Your Name",
            dependencies=['textblob']  # pip install textblob
        )
    
    async def initialize(self, app: Application) -> None:
        from textblob import TextBlob
        self.TextBlob = TextBlob
        self._logger.info("Sentiment plugin ready")
    
    async def shutdown(self) -> None:
        pass
    
    def get_stat_name(self) -> str:
        return "sentiment"
    
    def get_stat_description(self) -> str:
        return "Message sentiment analysis (positive/negative)"
    
    async def calculate_stats(
        self,
        session: AsyncSession,
        chat_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Calculate sentiment statistics."""
        # Query messages from database
        # Analyze sentiment
        # Return results
        
        return {
            'positive_messages': 120,
            'negative_messages': 30,
            'neutral_messages': 150,
            'average_sentiment': 0.15,
        }
```

---

## Built-in Examples

### Word Cloud Plugin (`word_cloud.py`)

Generates word frequency statistics for word cloud visualization.

**Features:**
- Configurable stopwords
- Minimum word length filtering
- Date range support
- Returns top N words

**Usage via API:**
```python
# In your code or API endpoint
from tgstats.plugins import PluginManager

plugin_manager = PluginManager()
await plugin_manager.load_plugins()

word_cloud_plugin = plugin_manager.get_plugin("word_cloud")
stats = await word_cloud_plugin.calculate_stats(
    session=session,
    chat_id=123456,
    days=30,
    top_n=100
)
```

### Heatmap Command Plugin (`heatmap_command.py`)

Adds `/heatmap` and `/activity` commands to visualize message activity.

**Commands:**
- `/heatmap` - ASCII heatmap showing activity by hour/day
- `/activity` - Summary of most active times

**Features:**
- 7-day activity heatmap
- Day of week analysis
- Hourly breakdown
- ASCII visualization in chat

---

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Enable/disable plugin system
ENABLE_PLUGINS=true

# Additional plugin directories (comma-separated)
PLUGIN_DIRECTORIES=/path/to/custom/plugins,/another/path
```

### Disabling Plugins

**Option 1: Disable system-wide**
```bash
ENABLE_PLUGINS=false
```

**Option 2: Move plugin file**
```bash
# Move out of enabled directory
mv tgstats/plugins/enabled/my_plugin.py tgstats/plugins/disabled/
```

**Option 3: Runtime disable**
```python
plugin_manager.disable_plugin("plugin_name")
```

---

## API Reference

### Base Classes

#### `BasePlugin`

Base class for all plugins.

**Properties:**
- `metadata` - Plugin metadata (name, version, description)
- `enabled` - Whether plugin is active

**Methods:**
- `initialize(app)` - Called on plugin load
- `shutdown()` - Called on bot shutdown
- `enable()` - Enable the plugin
- `disable()` - Disable the plugin

#### `CommandPlugin`

Adds new bot commands.

**Abstract Methods:**
- `get_commands()` - Returns dict of command_name -> handler
- `get_command_descriptions()` - Returns dict of command_name -> description

#### `StatisticsPlugin`

Provides custom analytics.

**Abstract Methods:**
- `calculate_stats(session, chat_id, **kwargs)` - Calculate statistics
- `get_stat_name()` - Return statistic name/key
- `get_stat_description()` - Return human-readable description

#### `HandlerPlugin`

Processes updates in real-time.

**Methods:**
- `process_message(update, context, session)` - Process each message
- `process_reaction(update, context, session)` - Process reactions (optional)
- `process_edited_message(update, context, session)` - Process edits (optional)

#### `ServicePlugin`

Extends bot services.

**Abstract Methods:**
- `execute(session, *args, **kwargs)` - Execute service logic
- `get_service_name()` - Return service identifier

---

### PluginManager

#### Methods

**`discover_plugins()`**
- Scans plugin directories
- Returns list of plugin classes

**`load_plugins()`**
- Instantiates discovered plugins
- Checks dependencies
- Registers in appropriate categories

**`initialize_plugins(app)`**
- Calls `initialize()` on each plugin
- Passes Application instance

**`register_command_plugins(app)`**
- Registers all CommandPlugin handlers
- Adds to Telegram Application

**`get_plugin(name)`**
- Returns plugin by name
- Returns None if not found

**`get_statistics_plugins()`**
- Returns dict of enabled StatisticsPlugin instances

**`list_plugins()`**
- Returns metadata for all plugins

**`enable_plugin(name)` / `disable_plugin(name)`**
- Enable/disable plugin at runtime

---

## Advanced Topics

### Plugin Dependencies

Declare Python package dependencies:

```python
@property
def metadata(self) -> PluginMetadata:
    return PluginMetadata(
        name="my_plugin",
        version="1.0.0",
        description="...",
        author="...",
        dependencies=['pandas', 'numpy', 'scikit-learn']
    )
```

The PluginManager will:
1. Check if dependencies are installed
2. Skip plugin if dependencies missing
3. Log a warning

### Accessing Database

All plugin methods receive a `session` parameter:

```python
async def calculate_stats(self, session: AsyncSession, chat_id: int, **kwargs):
    from sqlalchemy import select
    from tgstats.models import Message
    
    query = select(Message).where(Message.chat_id == chat_id)
    result = await session.execute(query)
    messages = result.scalars().all()
    
    # Process messages...
```

### Using Bot Services

Import and use existing services:

```python
from tgstats.services import ChatService, MessageService

async def my_method(self, session: AsyncSession):
    chat_service = ChatService(session)
    settings = await chat_service.get_chat_settings(chat_id)
```

### Error Handling

Plugins have built-in logging:

```python
try:
    # Your code
    result = await some_operation()
except Exception as e:
    self._logger.error(
        "operation_failed",
        error=str(e),
        exc_info=True
    )
    raise
```

---

## Best Practices

### ✅ DO:
- Use descriptive plugin names
- Add proper error handling
- Log important events
- Clean up resources in `shutdown()`
- Test plugins thoroughly
- Document your plugin's functionality

### ❌ DON'T:
- Modify core bot files
- Use blocking operations
- Forget to handle exceptions
- Hard-code configuration values
- Leave debug statements in production

---

## Plugin Ideas

Here are some ideas for plugins you could create:

### Statistics Plugins
- **Sentiment Analysis** - Analyze message tone
- **Topic Modeling** - Identify conversation topics
- **Network Analysis** - User interaction graphs
- **Language Detection** - Multi-language stats
- **Media Analysis** - Photo/video usage stats

### Command Plugins
- **Export Commands** - Export data to CSV/JSON/Excel
- **Report Generator** - Daily/weekly summaries
- **Moderator Tools** - Ban/mute based on rules
- **Quiz Bot** - Interactive group games
- **Reminder Bot** - Schedule messages

### Handler Plugins
- **Auto Moderator** - Content filtering
- **Spam Detector** - Identify spam patterns
- **Link Tracker** - Track shared URLs
- **Keyword Alerts** - Notify on keywords
- **Translation** - Auto-translate messages

### Service Plugins
- **Backup Service** - Export all data
- **Integration Service** - Connect to external APIs
- **Notification Service** - Send alerts
- **Analytics Dashboard** - Generate HTML reports

---

## Troubleshooting

### Plugin Not Loading

**Check logs:**
```bash
tail -f logs/tgstats.log | grep -i plugin
```

**Common issues:**
1. Syntax errors in plugin file
2. Missing dependencies
3. File not in `enabled/` directory
4. Wrong class inheritance

### Commands Not Working

1. Verify plugin is loaded: Check logs for "plugin_loaded"
2. Check command registration: Look for "command_registered"
3. Test in group chat (some commands are group-only)

### Performance Issues

- Use async/await properly
- Avoid blocking operations
- Add database indexes for queries
- Limit query results
- Cache expensive calculations

---

## Contributing

Have a great plugin idea? Consider:

1. Creating the plugin
2. Testing it thoroughly
3. Documenting usage
4. Sharing with the community!

---

## Support

- **Issues:** Open a GitHub issue
- **Questions:** Check documentation
- **Examples:** See `tgstats/plugins/enabled/`

---

**Happy Plugin Development! 🚀**
