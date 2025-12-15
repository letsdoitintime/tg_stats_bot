# Plugin System - Quick Reference

## 🎯 New Structure (Simplified!)

```
tgstats/plugins/
├── __init__.py
├── base.py              # Base plugin classes
├── manager.py           # Plugin loader with hot reload
├── plugins.yaml         # Plugin configuration
├── word_cloud.py        # Example: Statistics plugin
├── heatmap_command.py   # Example: Command plugin
└── examples/            # Templates and examples
    ├── command_template.py
    ├── statistics_template.py
    └── top_users.py
```

## ✨ What's New

### 1. Single `plugins/` Folder
- No more `enabled/` and `disabled/` subfolders
- All plugins in one place
- Cleaner structure

### 2. Disable with Underscore
```bash
# Disable a plugin - just add underscore prefix
mv word_cloud.py _word_cloud.py

# Enable again
mv _word_cloud.py word_cloud.py
```

### 3. YAML Configuration
```yaml
# plugins/plugins.yaml
plugins:
  word_cloud:
    enabled: true
    config:
      default_days: 30
  
  heatmap_command:
    enabled: false  # Disabled in config

settings:
  hot_reload: true              # Auto-reload on changes
  reload_check_interval: 3.0    # Check every 3 seconds
```

### 4. Hot Reload! 🔥
- Edit plugin files - changes apply automatically
- No bot restart needed
- Monitors Python files and folders
- 3-second default check interval

### 5. Complex Plugins (Folders)
```
plugins/
├── my_complex_plugin/
│   ├── __init__.py       # Plugin class here
│   ├── utils.py
│   ├── models.py
│   └── config.py
```

Folder plugins work too! Just needs `__init__.py` with plugin class.

## 🚀 Quick Start

### Create Simple Plugin

1. **Copy template:**
   ```bash
   cp tgstats/plugins/examples/command_template.py tgstats/plugins/my_plugin.py
   ```

2. **Edit `my_plugin.py`:**
   ```python
   class MyPlugin(CommandPlugin):
       @property
       def metadata(self):
           return PluginMetadata(
               name="my_plugin",
               version="1.0.0",
               description="My awesome plugin",
               author="Me"
           )
       
       def get_commands(self):
           return {'hello': self._hello}
       
       def get_command_descriptions(self):
           return {'hello': 'Say hello'}
       
       async def _hello(self, update, context):
           await update.message.reply_text("Hello!")
   ```

3. **Watch it load automatically!** (if hot reload is enabled)
   - Check logs: `tail -f logs/tgstats.log | grep plugin`
   - Use `/hello` in your group

### Disable Plugin

**Method 1: Rename with underscore**
```bash
mv my_plugin.py _my_plugin.py
```

**Method 2: YAML config**
```yaml
plugins:
  my_plugin:
    enabled: false
```

**Method 3: Runtime** (programmatic)
```python
plugin_manager.disable_plugin("my_plugin")
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Enable/disable entire plugin system
ENABLE_PLUGINS=true

# Additional plugin directories (optional)
PLUGIN_DIRECTORIES=/custom/plugins,/another/path
```

### YAML Config (plugins.yaml)
```yaml
plugins:
  my_plugin:
    enabled: true
    config:
      # Plugin-specific settings
      api_key: "xxx"
      timeout: 30

settings:
  hot_reload: true
  reload_check_interval: 3.0
```

Access config in plugin:
```python
class MyPlugin(CommandPlugin):
    async def initialize(self, app):
        # Access plugin-specific config
        api_key = getattr(self, '_config', {}).get('api_key')
```

## 📊 Model Attributes Reference

**Important!** Use correct model attributes:

### Message Model
```python
# ✅ Correct
Message.date          # Not created_at!
Message.text_raw      # Not text!
Message.msg_id        # Not id!
Message.chat_id       # ✓
Message.user_id       # ✓

# ❌ Wrong
Message.created_at    # Doesn't exist
Message.text          # Doesn't exist
Message.id            # Doesn't exist
```

### User Model
```python
# ✅ Correct
User.user_id          # Primary key
User.username
User.first_name
User.last_name
```

### Chat Model
```python
# ✅ Correct
Chat.chat_id          # Primary key
Chat.title
Chat.username
Chat.created_at       # ✓ This one has it
```

## 🔥 Hot Reload Details

### What Triggers Reload?
- File modification (save)
- New plugin file added
- Plugin folder changes

### What Gets Reloaded?
- All plugins shutdown gracefully
- Configuration reloaded from YAML
- All plugins reinitialized
- Commands re-registered

### What's NOT Reloaded?
- Core bot code (bot_main.py, handlers/, etc.)
- Database models
- Configuration (settings from .env)

### Monitoring Logs
```bash
# Watch reload activity
tail -f logs/tgstats.log | grep -E "plugin|reload"

# You'll see:
# plugin_files_changed - Files modified
# reloading_plugins - Starting reload
# plugins_reloaded - Complete
```

## 📁 Plugin File Rules

### Loaded:
- ✅ `plugin_name.py` - Python files
- ✅ `plugin_folder/` - Folders with `__init__.py`

### Ignored:
- ❌ `_disabled.py` - Underscore prefix
- ❌ `__init__.py` - Special files
- ❌ `__pycache__/` - Python cache
- ❌ `base.py`, `manager.py` - System files
- ❌ `plugins.yaml` - Config file

## 🎨 Plugin Ideas

**Easy:**
- `/stats` - Show chat statistics
- `/random` - Random message
- `/count` - Count specific words

**Medium:**
- Export to CSV/JSON
- Activity reports
- User rankings

**Advanced:**
- Sentiment analysis
- ML predictions
- External API integrations

## 🐛 Troubleshooting

### Plugin Not Loading

**Check logs:**
```bash
grep "my_plugin" logs/tgstats.log
```

**Common issues:**
1. File starts with `_`
2. Disabled in YAML (`enabled: false`)
3. Syntax error in plugin
4. Missing dependencies

### Hot Reload Not Working

1. Check `hot_reload: true` in plugins.yaml
2. Wait for check interval (default 3s)
3. Check logs for errors

### Command Not Showing

1. Plugin loaded? Check logs
2. Command registered? Look for `command_registered`
3. Try in group chat (some commands are group-only)
4. Check for name conflicts

## 📖 Full Documentation

- **Complete Guide:** `documentation/PLUGIN_SYSTEM.md`
- **Quick Start:** `documentation/PLUGIN_QUICK_START.md`
- **Examples:** `tgstats/plugins/examples/`

---

**Made changes? They'll reload automatically! 🔥**
