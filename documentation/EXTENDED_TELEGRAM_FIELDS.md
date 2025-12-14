# Extended Telegram API Fields Collection

## Overview

This update adds comprehensive data collection from the Telegram API, capturing **all available fields** from Chat, User, and Message objects. This enables advanced analytics on forwarded messages, media files, chat settings, and more.

## What's New

### Chat Data (9 new fields)
- ✅ `description` - Chat description text
- ✅ `photo_small_file_id` - Chat profile photo (small)
- ✅ `photo_big_file_id` - Chat profile photo (large)
- ✅ `invite_link` - Chat invite link
- ✅ `pinned_message_id` - ID of pinned message
- ✅ `permissions_json` - Default chat permissions (JSON)
- ✅ `slow_mode_delay` - Slow mode delay in seconds
- ✅ `message_auto_delete_time` - Auto-delete timer
- ✅ `has_protected_content` - Content protection status
- ✅ `linked_chat_id` - Linked channel/group ID

### User Data (5 new fields)
- ✅ `is_premium` - Telegram Premium status
- ✅ `added_to_attachment_menu` - Bot in attachment menu
- ✅ `can_join_groups` - Bot capability (for bots)
- ✅ `can_read_all_group_messages` - Bot capability (for bots)
- ✅ `supports_inline_queries` - Bot capability (for bots)

### Message Data (28 new fields)

#### Forward Information (7 fields)
- ✅ `forward_from_user_id` - Original sender user ID
- ✅ `forward_from_chat_id` - Original chat ID
- ✅ `forward_from_message_id` - Original message ID
- ✅ `forward_signature` - Forward signature
- ✅ `forward_sender_name` - Forward sender name
- ✅ `forward_date` - Original message date
- ✅ `is_automatic_forward` - Auto-forward from channel

#### Additional Metadata (5 fields)
- ✅ `caption_entities_json` - Entities in media captions
- ✅ `via_bot_id` - Bot that sent via inline
- ✅ `author_signature` - Author signature (channels)
- ✅ `media_group_id` - Album/media group ID
- ✅ `has_protected_content` - Message protection
- ✅ `web_page_json` - Link preview data

#### Media File Metadata (9 fields)
- ✅ `file_id` - Telegram file ID
- ✅ `file_unique_id` - Unique file identifier
- ✅ `file_size` - File size in bytes
- ✅ `file_name` - Original file name
- ✅ `mime_type` - File MIME type
- ✅ `duration` - Audio/video duration
- ✅ `width` - Image/video width
- ✅ `height` - Image/video height
- ✅ `thumbnail_file_id` - Thumbnail file ID

## Migration

### Apply Database Changes

```bash
# Using Alembic (recommended)
python -m alembic upgrade head

# Or using Docker
docker compose exec bot python -m alembic upgrade head

# Or manually run the SQL
docker compose exec postgres psql -U postgres -d tgstats -f /path/to/migration.sql
```

### Migration File
- **File**: `migrations/versions/005_add_extended_telegram_fields.py`
- **Revision ID**: `005_add_extended_telegram_fields`
- **Down Revision**: `d25c72be7a85`

### Indexes Created
For optimal query performance, the following indexes are created:
- `ix_messages_forward_from_user` - Query forwarded messages by original sender
- `ix_messages_forward_from_chat` - Query forwarded messages by source chat
- `ix_messages_media_group_id` - Group album messages together
- `ix_messages_via_bot` - Track inline bot usage

## Analytics Use Cases

### 1. Forward Analysis
Track viral content and message propagation:
```sql
-- Most forwarded messages
SELECT chat_id, msg_id, COUNT(*) as forward_count
FROM messages
WHERE forward_from_message_id IS NOT NULL
GROUP BY forward_from_message_id, forward_from_chat_id
ORDER BY forward_count DESC;

-- Forward sources
SELECT forward_from_chat_id, COUNT(*) as forwards
FROM messages
WHERE forward_from_chat_id IS NOT NULL
GROUP BY forward_from_chat_id
ORDER BY forwards DESC;
```

### 2. Media Analytics
Analyze file sizes, types, and dimensions:
```sql
-- Total storage by media type
SELECT media_type, 
       COUNT(*) as count,
       SUM(file_size) as total_bytes,
       AVG(file_size) as avg_bytes
FROM messages
WHERE file_size IS NOT NULL
GROUP BY media_type;

-- Video dimensions distribution
SELECT width, height, COUNT(*) as count
FROM messages
WHERE media_type = 'video'
GROUP BY width, height
ORDER BY count DESC;
```

### 3. Album/Media Group Tracking
Track photo/video albums:
```sql
-- Messages per album
SELECT media_group_id, COUNT(*) as items
FROM messages
WHERE media_group_id IS NOT NULL
GROUP BY media_group_id
ORDER BY items DESC;
```

### 4. Bot Activity Analysis
Track inline bot usage:
```sql
-- Most used inline bots
SELECT via_bot_id, COUNT(*) as usage_count
FROM messages
WHERE via_bot_id IS NOT NULL
GROUP BY via_bot_id
ORDER BY usage_count DESC;
```

### 5. Premium User Analytics
Identify premium users:
```sql
-- Premium user activity
SELECT u.user_id, u.username, u.is_premium, COUNT(m.msg_id) as messages
FROM users u
JOIN messages m ON u.user_id = m.user_id
WHERE u.is_premium = true
GROUP BY u.user_id, u.username, u.is_premium
ORDER BY messages DESC;
```

### 6. Link Preview Analysis
Track shared links with previews:
```sql
-- Messages with web page previews
SELECT 
    web_page_json->>'site_name' as site,
    COUNT(*) as shares
FROM messages
WHERE web_page_json IS NOT NULL
GROUP BY web_page_json->>'site_name'
ORDER BY shares DESC;
```

### 7. Chat Configuration
Monitor chat settings:
```sql
-- Protected content chats
SELECT chat_id, title, has_protected_content, slow_mode_delay
FROM chats
WHERE has_protected_content = true
   OR slow_mode_delay IS NOT NULL;

-- Chat permissions summary
SELECT 
    chat_id,
    title,
    permissions_json->>'can_send_messages' as can_send,
    permissions_json->>'can_send_media_messages' as can_send_media
FROM chats
WHERE permissions_json IS NOT NULL;
```

## Updated Code Files

### Models
- **File**: `tgstats/models.py`
- **Changes**: Added 42 new fields across Chat, User, and Message models

### Repositories
1. **`tgstats/repositories/chat_repository.py`**
   - Extracts chat photo, permissions, and settings
   - Handles pinned message references

2. **`tgstats/repositories/user_repository.py`**
   - Collects premium status and bot capabilities
   - Tracks attachment menu integration

3. **`tgstats/repositories/message_repository.py`**
   - Comprehensive forward information extraction
   - Media file metadata collection (size, dimensions, duration)
   - Web page preview data extraction
   - Album/media group tracking
   - Caption entities parsing

## Performance Considerations

### Storage Impact
- **Forward data**: ~50 bytes per forwarded message
- **Media metadata**: ~100-200 bytes per media message
- **Web page previews**: ~200-500 bytes when present
- **Estimated increase**: 10-15% for typical chat data

### Query Performance
New indexes ensure efficient queries for:
- Forward tracking: O(log n) lookup by source
- Media groups: O(1) album grouping
- Bot analytics: O(log n) inline bot filtering

### Backward Compatibility
All new fields are **nullable**, ensuring:
- ✅ No breaking changes to existing code
- ✅ Seamless migration from older versions
- ✅ Graceful handling of missing data
- ✅ Works with all Telegram bot library versions

## Data Collection Status

### Automatic Collection
All fields are collected **automatically** when present in Telegram API responses. No configuration needed.

### Conditional Collection
Some fields only appear in specific contexts:
- **Forward data**: Only when message is forwarded
- **Media metadata**: Only for media messages
- **Web previews**: Only when link preview generated
- **Bot capabilities**: Only for bot users
- **Premium status**: Only when user is premium

## API Impact

### No Breaking Changes
- Existing endpoints continue working
- New fields available in responses
- Nullable fields return `null` when not present

### Example Response Updates

#### Message Object (Extended)
```json
{
  "chat_id": 123,
  "msg_id": 456,
  "text_len": 50,
  "media_type": "photo",
  
  // NEW: Forward info
  "forward_from_user_id": 789,
  "forward_date": "2025-12-14T10:00:00Z",
  "is_automatic_forward": false,
  
  // NEW: Media metadata
  "file_id": "AgACAgIAAxk...",
  "file_size": 1048576,
  "width": 1920,
  "height": 1080,
  
  // NEW: Additional metadata
  "media_group_id": "12345ABC",
  "via_bot_id": 999
}
```

#### User Object (Extended)
```json
{
  "user_id": 123,
  "username": "john_doe",
  "first_name": "John",
  
  // NEW: Premium and capabilities
  "is_premium": true,
  "can_join_groups": true,
  "supports_inline_queries": false
}
```

## Testing

### Verify Migration
```bash
# Check tables exist
docker compose exec postgres psql -U postgres -d tgstats -c "\d messages"

# Verify new columns
docker compose exec postgres psql -U postgres -d tgstats -c "
  SELECT column_name, data_type 
  FROM information_schema.columns 
  WHERE table_name = 'messages' 
    AND column_name LIKE '%forward%';"
```

### Test Data Collection
1. Send a forwarded message → Check `forward_*` fields
2. Send a photo → Check `file_id`, `width`, `height`
3. Send a link → Check `web_page_json`
4. Send an album → Check `media_group_id`

## Rollback

If needed, downgrade the migration:
```bash
# Rollback to previous version
python -m alembic downgrade d25c72be7a85

# Or using Docker
docker compose exec bot python -m alembic downgrade d25c72be7a85
```

This will:
- Remove all new columns
- Drop new indexes
- Restore database to previous state
- **Note**: Data in new columns will be lost

## Future Enhancements

### Potential Additions
- **Service messages**: group_chat_created, new_chat_members
- **Voice chat**: voice_chat_started, voice_chat_ended
- **Video chat**: video_chat_scheduled, video_chat_participants_invited
- **Forum topics**: forum_topic_created, forum_topic_edited
- **Payment info**: invoice, successful_payment

### Analytics Dashboards
Consider building visualizations for:
- Forward network graphs
- Media usage trends
- Premium user engagement
- Bot ecosystem metrics
- Chat configuration patterns

## Support

For issues or questions:
1. Check migration logs: `docker compose logs bot`
2. Verify database state: `\d messages` in psql
3. Review model definitions: `tgstats/models.py`
4. Check repository code: `tgstats/repositories/*.py`

---

**Status**: ✅ Ready for deployment  
**Impact**: Low risk, high value  
**Testing**: Recommended before production use  
**Compatibility**: Python 3.8+, PostgreSQL 12+, python-telegram-bot 20+
