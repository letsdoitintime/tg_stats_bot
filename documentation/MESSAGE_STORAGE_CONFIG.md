# Message Text Storage Configuration

## 🔍 Issue Investigation Results

### Problem Identified
- **Root Cause**: Default `store_text = False` when no group settings exist
- **Impact**: Message metadata was stored (length, URLs, emojis) but raw text was NULL
- **Affected Records**: 9 total messages, only 4 had text content stored

### Solutions Implemented

#### ✅ **Solution 1: Changed Default Behavior**
Modified two files to default to storing text:

1. **`tgstats/handlers/messages.py`** (Line 49):
   ```python
   # Changed from: store_text = group_settings.store_text if group_settings else False
   store_text = group_settings.store_text if group_settings else True  # Default to True
   ```

2. **`tgstats/handlers/commands.py`** (Line 67):
   ```python
   # Changed from: "store_text": False,
   "store_text": True,  # Changed to True by default
   ```

#### ⚙️ **Solution 2: Bot Commands Available**
For fine-grained control, use these Telegram commands:

```
/setup              # Initialize group analytics (creates settings)
/set_text on        # Enable text storage
/set_text off       # Disable text storage  
/settings           # View current group settings
```

## 📊 Current Status

### Database Statistics
- **Total Messages**: 9
- **Messages with Text**: 4 (after fix)
- **Recent Messages**: Now storing full text content

### Text Storage Behavior
- **New Messages**: ✅ Raw text stored by default
- **Metadata Always Stored**: text_len, urls_cnt, emoji_cnt, media_type
- **Admin Control**: Group admins can toggle with `/set_text on|off`

### Database Schema - Messages Table
```sql
-- Key fields related to text storage:
text_raw          VARCHAR(4000)  -- Raw message text (NULL when disabled)
text_len          INTEGER        -- Text length (always stored)
urls_cnt          INTEGER        -- URL count (always stored)  
emoji_cnt         INTEGER        -- Emoji count (always stored)
media_type        VARCHAR(50)    -- Message type (always stored)
```

## 🎯 Verification

### Test Results
```sql
-- Latest messages with text content:
SELECT msg_id, text_raw, text_len, media_type FROM messages ORDER BY msg_id DESC LIMIT 3;

 msg_id | text_raw | text_len | media_type 
--------+----------+----------+------------
    198 | Bbbhj    |        5 | text
    197 | Hey      |        3 | text
    196 | Skills   |        6 | text
```

### Configuration Check
```bash
# Check if bot is processing and storing text:
./status.sh

# Connect to database:
/opt/homebrew/opt/postgresql@16/bin/psql -h localhost -p 5433 -U andrew -d tgstats
```

## 🔐 Privacy & Control

### Text Storage Options
1. **Enabled (Default)**: Full message content stored for analytics
2. **Disabled**: Only metadata stored (length, URLs, emojis, media type)
3. **Configurable**: Per-group settings via bot commands

### Data Retention
- **Text Retention**: 90 days (configurable)
- **Metadata Retention**: 365 days (configurable)
- **Admin Control**: Group administrators can modify settings

---

**✅ Issue Resolved**: New messages now store raw text content by default while maintaining admin control over text storage settings.
