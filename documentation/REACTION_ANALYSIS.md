# Telegram Reactions Analysis

## Current Status: ❌ NOT IMPLEMENTED

The bot currently **does not track reactions** despite having the infrastructure partially in place.

## What We Found

### ✅ Database Support
- `GroupSettings` model has `capture_reactions: bool` field (defaults to `False`)
- This setting is displayed in `/setup` and `/settings` commands
- Database schema supports the flag but no reactions table exists

### ❌ Missing Components

#### 1. No Reaction Model
The database has no table to store actual reaction data. We need a `Reaction` model like:
```python
class Reaction(Base):
    __tablename__ = "reactions"
    
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.chat_id"), primary_key=True)
    msg_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), primary_key=True)
    reaction_type: Mapped[str] = mapped_column(String(100), primary_key=True)  # emoji or custom
    is_big: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
```

#### 2. No Reaction Handlers
The bot has no handlers registered for:
- `MessageReactionHandler` (available in python-telegram-bot v22.3)
- `Update.message_reaction` events
- `Update.message_reaction_count` events

#### 3. No Logging
No structured logging for reaction events

## Implementation Plan

### Step 1: Create Reaction Model
- Add `Reaction` model to `models.py`
- Create Alembic migration
- Add relationships to other models

### Step 2: Add Reaction Handlers
- Import `MessageReactionHandler` from `telegram.ext`
- Create reaction handling functions in new `handlers/reactions.py`
- Register handlers in `bot_main.py`

### Step 3: Add Admin Controls
- Add `/set_reactions on|off` command
- Update settings display
- Respect `capture_reactions` setting

### Step 4: Analytics Integration
- Add reaction counts to message analytics
- Track reaction trends over time
- Popular emoji analysis

## Telegram Library Support

### Available in python-telegram-bot v22.3:
- ✅ `MessageReactionHandler`
- ✅ `Update.message_reaction` 
- ✅ `Update.message_reaction_count`
- ✅ `MessageReactionUpdated` objects

### Reaction Data Structure:
```python
# update.message_reaction contains:
MessageReactionUpdated(
    chat=Chat,
    message_id=int,
    user=User,  # None for anonymous
    actor_chat=Chat,  # For anonymous channels
    date=datetime,
    old_reaction=[ReactionType],  # Previous reactions
    new_reaction=[ReactionType]   # Current reactions
)
```

## Database Queries We Could Enable

With reactions implemented, we could query:
```sql
-- Most reacted messages
SELECT m.text_raw, COUNT(r.reaction_type) as reaction_count
FROM messages m
JOIN reactions r ON m.chat_id = r.chat_id AND m.msg_id = r.msg_id
WHERE r.removed_at IS NULL
GROUP BY m.chat_id, m.msg_id, m.text_raw
ORDER BY reaction_count DESC;

-- Popular emoji by chat
SELECT r.reaction_type, COUNT(*) as usage_count
FROM reactions r
WHERE r.chat_id = ? AND r.removed_at IS NULL
GROUP BY r.reaction_type
ORDER BY usage_count DESC;

-- User reaction behavior
SELECT u.first_name, COUNT(r.reaction_type) as reactions_given
FROM users u
JOIN reactions r ON u.user_id = r.user_id  
WHERE r.chat_id = ? AND r.removed_at IS NULL
GROUP BY u.user_id, u.first_name
ORDER BY reactions_given DESC;
```

## Current Settings Display

The bot already shows "Capture Reactions: ❌ Disabled" in settings, but this does nothing since:
1. No handlers are registered for reaction events
2. No database table exists to store reactions
3. No migration has been created

## Next Steps

1. **Immediate**: Create the reactions database model
2. **Short-term**: Implement basic reaction capture
3. **Medium-term**: Add reaction analytics and admin controls
4. **Long-term**: Advanced reaction insights and reporting

## Privacy Considerations

Reactions can be tracked per-user, so we should:
- Respect the `capture_reactions` setting
- Consider anonymizing reaction data
- Allow data retention policies for reactions
- Follow GDPR compliance for user data
