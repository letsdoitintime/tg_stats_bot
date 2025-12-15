# Plugin System Quick Start

## 🚀 Quick Setup

### 1. Enable Plugins (Already Enabled!)

Plugins are enabled by default. To disable:
```bash
# In .env
ENABLE_PLUGINS=false
```

### 2. Create Your Plugin

Copy a template:
```bash
# For commands
cp tgstats/plugins/examples/command_template.py tgstats/plugins/enabled/my_plugin.py

# For statistics
cp tgstats/plugins/examples/statistics_template.py tgstats/plugins/enabled/my_stats.py
```

### 3. Edit and Customize

Open your new plugin file and:
- Change the plugin name
- Add your logic
- Implement the required methods

### 4. Restart Bot

```bash
# If using systemd
sudo systemctl restart tgstats-bot

# If running manually
python -m tgstats.bot_main
```

### 5. Test It!

Your new commands will be available immediately!

---

## 📦 Built-in Plugins

### Word Cloud (`enabled/word_cloud.py`)
- **Type:** Statistics
- **Purpose:** Generate word frequency data
- **Usage:** Via API only (no commands)

### Heatmap (`enabled/heatmap_command.py`)
- **Type:** Command
- **Commands:** `/heatmap`, `/activity`
- **Purpose:** Show activity patterns

---

## 🎯 Plugin Types Cheat Sheet

| Type | Use When | Examples |
|------|----------|----------|
| **CommandPlugin** | Adding bot commands | `/export`, `/mystats`, `/report` |
| **StatisticsPlugin** | Calculating metrics | Sentiment, word clouds, trends |
| **HandlerPlugin** | Processing all messages | Filtering, moderation, tracking |
| **ServicePlugin** | Background services | Exporters, integrations, jobs |

---

## 📝 Minimal Examples

### Command Plugin (10 lines)

```python
from telegram import Update
from telegram.ext import ContextTypes, Application
from ..base import CommandPlugin, PluginMetadata

class HelloPlugin(CommandPlugin):
    @property
    def metadata(self):
        return PluginMetadata(name="hello", version="1.0.0",
                            description="Says hello", author="Me")
    
    async def initialize(self, app: Application): pass
    async def shutdown(self): pass
    
    def get_commands(self):
        return {'hello': lambda u, c: u.message.reply_text("Hello!")}
    
    def get_command_descriptions(self):
        return {'hello': 'Says hello'}
```

### Statistics Plugin (15 lines)

```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import Application
from ..base import StatisticsPlugin, PluginMetadata
from ...models import Message

class MessageCountPlugin(StatisticsPlugin):
    @property
    def metadata(self):
        return PluginMetadata(name="msg_count", version="1.0.0",
                            description="Count messages", author="Me")
    
    async def initialize(self, app: Application): pass
    async def shutdown(self): pass
    def get_stat_name(self): return "message_count"
    def get_stat_description(self): return "Total messages"
    
    async def calculate_stats(self, session: AsyncSession, chat_id: int, **kwargs):
        result = await session.execute(
            select(func.count(Message.id)).where(Message.chat_id == chat_id)
        )
        return {'total': result.scalar()}
```

---

## 🔧 Common Patterns

### Get Chat Settings

```python
from tgstats.services import ChatService

async with async_session() as session:
    service = ChatService(session)
    settings = await service.get_chat_settings(chat_id)
```

### Query Messages

```python
from sqlalchemy import select
from tgstats.models import Message
from datetime import datetime, timedelta

thirty_days_ago = datetime.utcnow() - timedelta(days=30)
query = select(Message).where(
    Message.chat_id == chat_id,
    Message.created_at >= thirty_days_ago
)
result = await session.execute(query)
messages = result.scalars().all()
```

### Group-Only Commands

```python
from tgstats.enums import ChatType

if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
    await update.message.reply_text("Group only!")
    return
```

---

## 🐛 Debugging

### View Logs

```bash
# Watch logs in real-time
tail -f logs/tgstats.log | grep -i plugin

# Search for specific plugin
grep "my_plugin" logs/tgstats.log
```

### Check Plugin Status

Logs will show:
- `discovered_plugin` - Found your plugin file
- `plugin_loaded` - Successfully loaded
- `plugin_initialized` - Ready to use
- `command_registered` - Command available

### Common Issues

**Plugin not loading:**
- Check file is in `enabled/` directory
- Check for syntax errors
- Check class inherits from correct base class

**Command not working:**
- Verify command name (no slash in dict)
- Check logs for `command_registered`
- Test with different users/groups

---

## 📚 Full Documentation

See `PLUGIN_SYSTEM.md` for complete documentation:
- API reference
- Advanced topics
- Best practices
- More examples

---

## 💡 Plugin Ideas

**Easy:**
- Daily summary command
- Random message picker
- Emoji counter

**Medium:**
- Export to CSV/JSON
- User statistics
- Message search

**Advanced:**
- Sentiment analysis
- Topic modeling
- ML-based predictions

---

## 🎓 Examples to Learn From

1. **Word Cloud** (`enabled/word_cloud.py`)
   - Statistics plugin
   - Database queries
   - Data processing

2. **Heatmap** (`enabled/heatmap_command.py`)
   - Command plugin
   - Complex queries
   - Text visualization

3. **Top Users** (`examples/top_users.py`)
   - Combined command + statistics
   - Join queries
   - Formatted output

---

Ready to create your first plugin? Copy a template and start coding! 🚀
