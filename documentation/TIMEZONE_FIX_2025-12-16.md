# Timezone Fix Applied - December 16, 2025

## Issue
Bot was crashing with `DataError: can't subtract offset-naive and offset-aware datetimes` when processing messages.

## Root Cause
After fixing `datetime.utcnow()` → `datetime.now(timezone.utc)`, we were inserting timezone-aware datetime objects into PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` columns, which expect naive datetimes.

## Solution
Convert timezone-aware datetimes to naive UTC before database operations by adding `.replace(tzinfo=None)`:

```python
# Before (causing errors)
"updated_at": datetime.now(timezone.utc),

# After (working)
"updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
```

## Files Fixed (4)
1. ✅ `tgstats/repositories/chat_repository.py`
2. ✅ `tgstats/repositories/user_repository.py`
3. ✅ `tgstats/repositories/membership_repository.py`
4. ✅ `tgstats/handlers/common.py`

## Status
✅ **Bot restarted successfully - no errors in logs**

## Technical Details

### Why This Approach?
- PostgreSQL columns are `TIMESTAMP WITHOUT TIME ZONE` (naive)
- We work with timezone-aware datetimes in Python (best practice)
- Convert to naive UTC only at database boundary
- All internal calculations remain timezone-aware

### Alternative Considered
Change database columns to `TIMESTAMP WITH TIME ZONE` - would require migration and could affect existing data/queries.

---

**Applied:** December 16, 2025, 13:45  
**Verification:** No errors after processing multiple messages
