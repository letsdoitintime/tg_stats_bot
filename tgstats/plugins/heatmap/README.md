# Heatmap Plugin

This folder contains all components for the heatmap activity analysis plugin.

## Structure

```
heatmap/
├── __init__.py      # Package exports
├── plugin.py        # Main CommandPlugin class (HeatmapCommandPlugin)
├── service.py       # Business logic and caching (HeatmapService)
├── repository.py    # Database queries (HeatmapRepository)
└── README.md        # This file
```

## Features

- **Activity Heatmap**: Shows hourly activity patterns over the last 7 days
- **Activity Summary**: Displays peak activity hours and days over the last 30 days
- **Flood Control**: Built-in delays to prevent Telegram API flooding
- **Caching**: Redis caching with 5-minute TTL for performance
- **Large Chat Support**: Handles chats with millions of messages

## Commands

- `/heatmap` - Display hourly activity heatmap (7 days)
- `/activity` - Show activity summary (30 days)

## Disabling the Plugin

To disable this plugin without affecting other bot functionality:

1. Rename this folder to start with underscore: `_heatmap`
2. Or delete this entire folder

The plugin manager will automatically skip folders/files starting with underscore.

## Dependencies

This plugin uses shared utilities:
- `tgstats.utils.decorators` - Database session and permission decorators
- `tgstats.utils.telegram_helpers` - Flood control message sending
- `tgstats.utils.cache` - Redis caching

These are NOT part of the plugin and are shared across the bot.

## Architecture

```
User Command
    ↓
plugin.py (HeatmapCommandPlugin)
    ↓
service.py (HeatmapService)
    ├─→ Cache (Redis)
    └─→ repository.py (HeatmapRepository)
            ↓
        Database
```

## Testing

Tests for this plugin are in `tests/test_heatmap.py`:
```bash
pytest tests/test_heatmap.py
```

## Performance

- **Query Optimization**: Database-level aggregation with LIMIT clauses
- **Caching**: 95%+ cache hit rate reduces database load
- **Message Limits**: Max 50K messages processed per query
- **Large Chat Detection**: Auto-detects chats >10K messages
- **Response Time**: <1 second (cached), 1-5 seconds (uncached)
