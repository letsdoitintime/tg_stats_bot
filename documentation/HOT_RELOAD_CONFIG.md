# Hot Reload Configuration Guide

## Overview

The plugin hot-reload system monitors files for changes and automatically reloads plugins without restarting the bot. This is fully configurable via `tgstats/plugins/plugins.yaml`.

## Configuration

### Location
`tgstats/plugins/plugins.yaml` - Global settings section

### Settings

```yaml
settings:
  # Enable/disable hot reload
  hot_reload: true
  
  # Check interval in seconds (how often to scan for changes)
  reload_check_interval: 3.0
  
  # File patterns to watch (glob-style)
  watch_patterns:
    - '*.py'      # Python source files
    - '*.yaml'    # YAML config files
    - '*.yml'     # Alternative YAML extension
    # - '*.json'  # Uncomment to watch JSON files
    # - '*'       # Uncomment to watch ALL files
  
  # Patterns to ignore (even if they match watch_patterns)
  ignore_patterns:
    - 'README.md'
    - '*.md'         # Ignore all markdown
    - '__pycache__'
    - '*.pyc'
    - '.git'
```

## What Gets Watched

### Automatic Detection

The system watches:
1. **Main config**: `tgstats/plugins/plugins.yaml` 
2. **Plugin entry files**: Top-level `.py` files or `__init__.py` in plugin packages
3. **All matching files inside plugin packages**: Recursively scans based on `watch_patterns`
4. **Per-plugin configs**: Files like `engagement/plugin.yaml`

### Examples

With default config (`*.py`, `*.yaml`, `*.yml`):
- ✅ `engagement/engagements.py` - triggers reload
- ✅ `engagement/plugin.yaml` - triggers reload  
- ✅ `heatmap/service.py` - triggers reload
- ✅ `plugins.yaml` - triggers reload
- ❌ `heatmap/README.md` - ignored (matches `*.md` ignore pattern)
- ❌ `engagement/__pycache__/` - ignored
- ❌ Any file starting with `_` - ignored

## Customization Examples

### Watch All Files
```yaml
watch_patterns:
  - '*'
```

### Watch Specific Types
```yaml
watch_patterns:
  - '*.py'
  - '*.json'
  - '*.txt'
  - 'config.*'  # Any file named config with any extension
```

### Ignore Additional Patterns
```yaml
ignore_patterns:
  - 'README.md'
  - '*.md'
  - '__pycache__'
  - '*.pyc'
  - '.git'
  - 'test_*.py'     # Ignore test files
  - '*.bak'         # Ignore backup files
  - '.vscode'       # Ignore editor configs
```

### Change Check Interval
```yaml
# Check every second (faster, more CPU)
reload_check_interval: 1.0

# Check every 10 seconds (slower, less CPU)
reload_check_interval: 10.0
```

## How It Works

1. **Initialization**: On startup, the manager scans all plugin directories and records modification times (`mtime`) for files matching `watch_patterns`

2. **Monitoring Loop**: Every `reload_check_interval` seconds:
   - Checks `mtime` of all tracked files
   - Detects new files matching `watch_patterns`
   - Skips files matching `ignore_patterns`

3. **Reload Trigger**: When changes detected:
   - Invalidates Python import caches
   - Removes plugin modules from `sys.modules`
   - Shuts down existing plugins
   - Reloads config files
   - Re-discovers and re-initializes all plugins
   - Re-registers command handlers

## Performance Considerations

### File Count
- **Low** (< 20 files): Check every 1-3 seconds
- **Medium** (20-50 files): Check every 3-5 seconds  
- **High** (> 50 files): Check every 5-10 seconds

### Watch Patterns
- More specific patterns = better performance
- Using `'*'` watches ALL files (slower)
- Exclude large directories in `ignore_patterns`

## Troubleshooting

### Changes Not Detected

1. **Check patterns**: Ensure file extension matches `watch_patterns`
```bash
# View current config
cat tgstats/plugins/plugins.yaml
```

2. **Check ignore list**: File might be in `ignore_patterns`

3. **View logs**: Search for detection events
```bash
tail -f logs/tgstats.log | grep plugin_files_changed
```

### Too Many Reloads

1. **Increase interval**: Set `reload_check_interval` higher
2. **Add ignore patterns**: Exclude temp/cache files
3. **Check editor auto-save**: Some editors save multiple times per second

### Performance Issues

1. **Reduce check frequency**: Increase `reload_check_interval`
2. **Narrow patterns**: Use specific extensions instead of `'*'`
3. **Add ignore patterns**: Exclude large directories

## Best Practices

### Development
```yaml
settings:
  hot_reload: true
  reload_check_interval: 2.0
  watch_patterns:
    - '*.py'
    - '*.yaml'
    - '*.yml'
```

### Production
```yaml
settings:
  hot_reload: false  # Disable for stability
```

### Testing New Plugins
```yaml
settings:
  hot_reload: true
  reload_check_interval: 1.0  # Fast iteration
  watch_patterns:
    - '*.py'
    - '*.yaml'
```

## Manual Reload

If hot-reload is disabled, restart the bot:
```bash
sudo supervisorctl restart tgstats-bot
```

## Log Events

Watch for these log entries:

```
hot_reload_started - Monitoring started
plugin_files_changed - Files modified/added
reloading_plugins - Starting reload
plugins_reloaded - Reload complete
plugin_config_loaded - Config reloaded
```

Example:
```
[INFO] plugin_files_changed count=2 files=['engagements.py', 'plugin.yaml']
[INFO] reloading_plugins
[INFO] plugins_reloaded count=3 plugins=['heatmap_command', 'word_cloud', 'engagement_scores']
```
