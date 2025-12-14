# Analytics Queries: Extended Telegram Fields

## Forward Analytics

### Most Forwarded Messages
```sql
-- Find messages that have been forwarded most often
SELECT 
    m.chat_id,
    m.msg_id,
    m.text_raw,
    COUNT(*) OVER (PARTITION BY m.forward_from_chat_id, m.forward_from_message_id) as times_forwarded,
    m.forward_from_chat_id as original_chat,
    m.forward_date as original_date
FROM messages m
WHERE m.forward_from_message_id IS NOT NULL
ORDER BY times_forwarded DESC
LIMIT 20;
```

### Forward Sources (Top Channels/Chats)
```sql
-- Which chats are most often forwarded from?
SELECT 
    c.title as source_chat,
    c.chat_id,
    COUNT(*) as forward_count,
    COUNT(DISTINCT m.chat_id) as forwarded_to_chats
FROM messages m
LEFT JOIN chats c ON c.chat_id = m.forward_from_chat_id
WHERE m.forward_from_chat_id IS NOT NULL
GROUP BY c.chat_id, c.title
ORDER BY forward_count DESC
LIMIT 20;
```

### Automatic Forwards (Channel → Group)
```sql
-- Track automatic forwards from linked channels
SELECT 
    m.chat_id,
    c.title as chat_title,
    m.forward_from_chat_id,
    COUNT(*) as auto_forward_count,
    DATE(m.date) as day
FROM messages m
JOIN chats c ON c.chat_id = m.chat_id
WHERE m.is_automatic_forward = true
GROUP BY m.chat_id, c.title, m.forward_from_chat_id, DATE(m.date)
ORDER BY day DESC, auto_forward_count DESC;
```

## Media Analytics

### Storage Analysis by Type
```sql
-- Total storage per media type
SELECT 
    media_type,
    COUNT(*) as file_count,
    pg_size_pretty(SUM(file_size)::bigint) as total_size,
    pg_size_pretty(AVG(file_size)::bigint) as avg_size,
    pg_size_pretty(MAX(file_size)::bigint) as max_size
FROM messages
WHERE file_size IS NOT NULL
GROUP BY media_type
ORDER BY SUM(file_size) DESC;
```

### Video Dimensions Distribution
```sql
-- Common video resolutions
SELECT 
    width || 'x' || height as resolution,
    COUNT(*) as count,
    pg_size_pretty(AVG(file_size)::bigint) as avg_size,
    AVG(duration) as avg_duration_sec
FROM messages
WHERE media_type IN ('video', 'video_note')
  AND width IS NOT NULL
  AND height IS NOT NULL
GROUP BY width, height
ORDER BY count DESC
LIMIT 20;
```

### Large Files Report
```sql
-- Messages with large files
SELECT 
    m.chat_id,
    c.title,
    m.msg_id,
    m.media_type,
    m.file_name,
    pg_size_pretty(m.file_size) as size,
    m.mime_type,
    m.date
FROM messages m
JOIN chats c ON c.chat_id = m.chat_id
WHERE m.file_size > 10485760  -- > 10 MB
ORDER BY m.file_size DESC
LIMIT 50;
```

### Photo vs Video Usage
```sql
-- Compare photo and video usage over time
SELECT 
    DATE(date) as day,
    COUNT(*) FILTER (WHERE media_type = 'photo') as photos,
    COUNT(*) FILTER (WHERE media_type = 'video') as videos,
    COUNT(*) FILTER (WHERE media_type = 'document') as documents
FROM messages
WHERE date > NOW() - INTERVAL '30 days'
GROUP BY DATE(date)
ORDER BY day DESC;
```

## Album/Media Group Analytics

### Album Statistics
```sql
-- Media groups (albums) with most items
SELECT 
    media_group_id,
    chat_id,
    COUNT(*) as items_in_album,
    MIN(date) as sent_at,
    STRING_AGG(media_type, ', ' ORDER BY msg_id) as media_types
FROM messages
WHERE media_group_id IS NOT NULL
GROUP BY media_group_id, chat_id
HAVING COUNT(*) > 1
ORDER BY items_in_album DESC
LIMIT 20;
```

### Album Composition
```sql
-- What types of media are in albums?
SELECT 
    COUNT(DISTINCT media_group_id) as album_count,
    STRING_AGG(DISTINCT media_type, '+' ORDER BY media_type) as type_combination
FROM messages
WHERE media_group_id IS NOT NULL
GROUP BY media_group_id
HAVING COUNT(*) > 1;
```

## Bot Analytics

### Inline Bot Usage
```sql
-- Most popular inline bots
SELECT 
    u.username as bot_username,
    u.user_id as bot_id,
    COUNT(*) as messages_sent,
    COUNT(DISTINCT m.chat_id) as used_in_chats,
    COUNT(DISTINCT m.user_id) as users
FROM messages m
JOIN users u ON u.user_id = m.via_bot_id
WHERE m.via_bot_id IS NOT NULL
GROUP BY u.user_id, u.username
ORDER BY messages_sent DESC;
```

### Bot Usage Timeline
```sql
-- Inline bot usage over time
SELECT 
    DATE(date) as day,
    via_bot_id,
    COUNT(*) as uses
FROM messages
WHERE via_bot_id IS NOT NULL
  AND date > NOW() - INTERVAL '30 days'
GROUP BY DATE(date), via_bot_id
ORDER BY day DESC, uses DESC;
```

## Premium User Analytics

### Premium vs Regular User Activity
```sql
-- Compare premium and regular user engagement
SELECT 
    u.is_premium,
    COUNT(DISTINCT u.user_id) as user_count,
    COUNT(m.msg_id) as total_messages,
    ROUND(COUNT(m.msg_id)::numeric / COUNT(DISTINCT u.user_id), 2) as avg_msgs_per_user,
    COUNT(DISTINCT DATE(m.date)) as active_days
FROM users u
LEFT JOIN messages m ON m.user_id = u.user_id
WHERE m.date > NOW() - INTERVAL '30 days'
GROUP BY u.is_premium;
```

### Premium User Top Contributors
```sql
-- Most active premium users
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    COUNT(m.msg_id) as message_count,
    COUNT(DISTINCT m.chat_id) as chats_active_in
FROM users u
JOIN messages m ON m.user_id = u.user_id
WHERE u.is_premium = true
  AND m.date > NOW() - INTERVAL '30 days'
GROUP BY u.user_id, u.username, u.first_name
ORDER BY message_count DESC
LIMIT 20;
```

## Link Preview Analytics

### Most Shared Websites
```sql
-- Top domains being shared
SELECT 
    web_page_json->>'site_name' as site,
    COUNT(*) as shares,
    COUNT(DISTINCT chat_id) as shared_in_chats,
    COUNT(DISTINCT user_id) as shared_by_users
FROM messages
WHERE web_page_json IS NOT NULL
  AND date > NOW() - INTERVAL '30 days'
GROUP BY web_page_json->>'site_name'
ORDER BY shares DESC
LIMIT 20;
```

### Link Preview Types
```sql
-- Distribution of preview types
SELECT 
    web_page_json->>'type' as preview_type,
    COUNT(*) as count
FROM messages
WHERE web_page_json IS NOT NULL
GROUP BY web_page_json->>'type'
ORDER BY count DESC;
```

### Popular Articles
```sql
-- Most shared article URLs
SELECT 
    web_page_json->>'url' as url,
    web_page_json->>'title' as title,
    web_page_json->>'site_name' as site,
    COUNT(*) as shares
FROM messages
WHERE web_page_json IS NOT NULL
  AND web_page_json->>'type' = 'article'
GROUP BY web_page_json->>'url', web_page_json->>'title', web_page_json->>'site_name'
ORDER BY shares DESC
LIMIT 20;
```

## Chat Configuration Analytics

### Protected Content Analysis
```sql
-- Chats with content protection
SELECT 
    c.chat_id,
    c.title,
    c.type,
    c.has_protected_content,
    COUNT(m.msg_id) as message_count
FROM chats c
LEFT JOIN messages m ON m.chat_id = c.chat_id
WHERE c.has_protected_content = true
GROUP BY c.chat_id, c.title, c.type, c.has_protected_content
ORDER BY message_count DESC;
```

### Slow Mode Analysis
```sql
-- Chats using slow mode
SELECT 
    c.chat_id,
    c.title,
    c.slow_mode_delay,
    COUNT(m.msg_id) as messages_30d,
    COUNT(DISTINCT m.user_id) as active_users
FROM chats c
LEFT JOIN messages m ON m.chat_id = c.chat_id AND m.date > NOW() - INTERVAL '30 days'
WHERE c.slow_mode_delay IS NOT NULL
GROUP BY c.chat_id, c.title, c.slow_mode_delay
ORDER BY c.slow_mode_delay DESC;
```

### Auto-Delete Settings
```sql
-- Message auto-delete timers
SELECT 
    c.chat_id,
    c.title,
    c.message_auto_delete_time,
    c.message_auto_delete_time / 3600.0 as hours_until_delete
FROM chats
WHERE c.message_auto_delete_time IS NOT NULL
ORDER BY c.message_auto_delete_time;
```

### Chat Permissions Overview
```sql
-- Restrictive chats
SELECT 
    c.chat_id,
    c.title,
    c.permissions_json->>'can_send_messages' as can_send_msg,
    c.permissions_json->>'can_send_media_messages' as can_send_media,
    c.permissions_json->>'can_send_polls' as can_send_polls,
    c.permissions_json->>'can_change_info' as can_change_info
FROM chats c
WHERE c.permissions_json IS NOT NULL
  AND (
    (c.permissions_json->>'can_send_messages')::boolean = false
    OR (c.permissions_json->>'can_send_media_messages')::boolean = false
  );
```

## Combined Analytics

### Viral Content Detection
```sql
-- Messages with high engagement (forwards + reactions)
SELECT 
    m.chat_id,
    c.title,
    m.msg_id,
    LEFT(m.text_raw, 100) as preview,
    COUNT(DISTINCT m2.msg_id) as forward_count,
    COUNT(DISTINCT r.reaction_id) as reaction_count,
    (COUNT(DISTINCT m2.msg_id) + COUNT(DISTINCT r.reaction_id)) as engagement_score
FROM messages m
JOIN chats c ON c.chat_id = m.chat_id
LEFT JOIN messages m2 ON m2.forward_from_chat_id = m.chat_id 
    AND m2.forward_from_message_id = m.msg_id
LEFT JOIN reactions r ON r.chat_id = m.chat_id AND r.msg_id = m.msg_id
WHERE m.date > NOW() - INTERVAL '7 days'
GROUP BY m.chat_id, c.title, m.msg_id, m.text_raw
HAVING COUNT(DISTINCT m2.msg_id) > 0 OR COUNT(DISTINCT r.reaction_id) > 0
ORDER BY engagement_score DESC
LIMIT 30;
```

### Content Type Breakdown by Chat
```sql
-- Comprehensive content analysis per chat
SELECT 
    c.chat_id,
    c.title,
    COUNT(*) as total_messages,
    COUNT(*) FILTER (WHERE m.forward_from_message_id IS NOT NULL) as forwards,
    COUNT(*) FILTER (WHERE m.has_media) as media_messages,
    COUNT(*) FILTER (WHERE m.media_group_id IS NOT NULL) as album_messages,
    COUNT(*) FILTER (WHERE m.web_page_json IS NOT NULL) as link_previews,
    COUNT(*) FILTER (WHERE m.via_bot_id IS NOT NULL) as via_bot,
    pg_size_pretty(SUM(m.file_size)::bigint) as total_storage
FROM chats c
LEFT JOIN messages m ON m.chat_id = c.chat_id
WHERE m.date > NOW() - INTERVAL '30 days'
GROUP BY c.chat_id, c.title
ORDER BY total_messages DESC;
```

### User Content Patterns
```sql
-- What kind of content do users send?
SELECT 
    u.user_id,
    u.username,
    COUNT(*) as total_messages,
    COUNT(*) FILTER (WHERE m.text_len > 0) as text_messages,
    COUNT(*) FILTER (WHERE m.has_media) as media_messages,
    COUNT(*) FILTER (WHERE m.forward_from_message_id IS NOT NULL) as forwards,
    ROUND(AVG(m.text_len), 0) as avg_text_length,
    COUNT(DISTINCT m.media_type) as unique_media_types
FROM users u
JOIN messages m ON m.user_id = u.user_id
WHERE m.date > NOW() - INTERVAL '30 days'
GROUP BY u.user_id, u.username
HAVING COUNT(*) > 10
ORDER BY total_messages DESC
LIMIT 30;
```

## Performance Queries

### Index Usage Check
```sql
-- Verify new indexes are being used
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE indexname IN (
    'ix_messages_forward_from_user',
    'ix_messages_forward_from_chat',
    'ix_messages_media_group_id',
    'ix_messages_via_bot'
)
ORDER BY idx_scan DESC;
```

### Storage Analysis
```sql
-- Table sizes with new fields
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('chats', 'users', 'messages')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Tips

1. **Use indexes**: All new forward and media group queries use indexed columns
2. **Filter by date**: Always add date ranges for better performance
3. **Use COUNT FILTER**: More efficient than multiple subqueries
4. **JSON fields**: Access with `->` for objects, `->>` for text
5. **Nulls**: Remember all new fields are nullable, use COALESCE if needed

## Example API Queries

These SQL queries can be exposed via FastAPI endpoints. See `tgstats/web/app.py` for examples.
