# API Usage Examples

Complete examples for using the TG Stats Bot REST API.

## Table of Contents

- [Authentication](#authentication)
- [Chat Management](#chat-management)
- [Analytics Endpoints](#analytics-endpoints)
- [Statistics Queries](#statistics-queries)
- [Advanced Examples](#advanced-examples)
- [Error Handling](#error-handling)

---

## Authentication

All API requests require authentication via the `X-Admin-Token` header.

### Setting Up Authentication

**1. Configure admin token in `.env`:**
```env
ADMIN_API_TOKEN=your_secret_token_here_use_a_long_random_string
```

**2. Include token in requests:**
```bash
curl -H "X-Admin-Token: your_secret_token_here" \
     http://localhost:8000/api/chats
```

### Python Example

```python
import requests

API_BASE = "http://localhost:8000"
ADMIN_TOKEN = "your_secret_token_here"

headers = {
    "X-Admin-Token": ADMIN_TOKEN,
    "Content-Type": "application/json"
}

response = requests.get(f"{API_BASE}/api/chats", headers=headers)
print(response.json())
```

---

## Chat Management

### List All Chats

Get all chats with 30-day statistics summary.

**Request:**
```bash
curl -H "X-Admin-Token: token" \
     http://localhost:8000/api/chats
```

**Response:**
```json
{
  "chats": [
    {
      "chat_id": -1001234567890,
      "title": "My Awesome Group",
      "username": "mygroup",
      "type": "supergroup",
      "message_count_30d": 1523,
      "active_users_30d": 45,
      "avg_messages_per_day": 50.7
    }
  ],
  "total": 1
}
```

### Get Chat Settings

**Request:**
```bash
curl -H "X-Admin-Token: token" \
     http://localhost:8000/api/chats/-1001234567890/settings
```

**Response:**
```json
{
  "chat_id": -1001234567890,
  "store_text": true,
  "capture_reactions": true,
  "timezone": "Europe/Sofia",
  "retention_days": 90,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-20T15:45:00Z"
}
```

### Get Chat Summary

Get summary statistics for a specific time period.

**Request:**
```bash
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/summary?from=2025-01-01&to=2025-01-31"
```

**Response:**
```json
{
  "chat_id": -1001234567890,
  "period": {
    "from": "2025-01-01",
    "to": "2025-01-31"
  },
  "total_messages": 1234,
  "unique_users": 45,
  "avg_messages_per_day": 39.8,
  "avg_messages_per_user": 27.4,
  "peak_day": "2025-01-15",
  "peak_messages": 87,
  "media_messages": 156,
  "text_messages": 1078
}
```

---

## Analytics Endpoints

### Time Series Data

Get messages or DAU (daily active users) over time.

**Request - Messages:**
```bash
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/timeseries?metric=messages&from=2025-01-01&to=2025-01-31"
```

**Response:**
```json
{
  "chat_id": -1001234567890,
  "metric": "messages",
  "period": {
    "from": "2025-01-01",
    "to": "2025-01-31"
  },
  "timezone": "Europe/Sofia",
  "data": [
    {
      "date": "2025-01-01",
      "value": 45
    },
    {
      "date": "2025-01-02",
      "value": 52
    }
  ]
}
```

**Request - Daily Active Users:**
```bash
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/timeseries?metric=dau&from=2025-01-01&to=2025-01-31"
```

### Activity Heatmap

Get 7-day × 24-hour activity heatmap.

**Request:**
```bash
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/heatmap?from=2025-01-01&to=2025-01-31"
```

**Response:**
```json
{
  "chat_id": -1001234567890,
  "period": {
    "from": "2025-01-01",
    "to": "2025-01-31"
  },
  "timezone": "Europe/Sofia",
  "heatmap": [
    {
      "day_of_week": 0,
      "hour": 0,
      "message_count": 12
    },
    {
      "day_of_week": 0,
      "hour": 1,
      "message_count": 5
    }
  ]
}
```

**Days mapping:**
- 0 = Monday
- 1 = Tuesday
- 2 = Wednesday
- 3 = Thursday
- 4 = Friday
- 5 = Saturday
- 6 = Sunday

### User Statistics

Get user statistics with pagination and sorting.

**Request:**
```bash
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/users?sort=messages&order=desc&page=1&per_page=25"
```

**Query Parameters:**
- `sort`: Sort field - `messages`, `activity`, `joined`, `username`
- `order`: Sort order - `asc`, `desc`
- `search`: Search by username (partial match)
- `left`: Filter by membership status - `true` (left users only), `false` (active only)
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 25, max: 100)

**Response:**
```json
{
  "chat_id": -1001234567890,
  "users": [
    {
      "user_id": 123456789,
      "username": "john_doe",
      "first_name": "John",
      "last_name": "Doe",
      "message_count": 234,
      "last_message_date": "2025-01-30T18:45:00Z",
      "joined_date": "2024-12-01T10:00:00Z",
      "left_date": null,
      "is_admin": true,
      "status": "member"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 25,
    "total": 45,
    "pages": 2
  }
}
```

---

## Statistics Queries

### Top Active Users

```bash
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/users?sort=messages&order=desc&per_page=10"
```

### Recently Joined Users

```bash
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/users?sort=joined&order=desc&per_page=10"
```

### Users Who Left

```bash
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/users?left=true&sort=left&order=desc"
```

### Search Users by Username

```bash
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/users?search=john"
```

---

## Advanced Examples

### Python - Complete Analytics Dashboard

```python
import requests
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt

class TGStatsClient:
    """Client for TG Stats Bot API."""
    
    def __init__(self, base_url: str, admin_token: str):
        self.base_url = base_url
        self.headers = {
            "X-Admin-Token": admin_token,
            "Content-Type": "application/json"
        }
    
    def get_chats(self):
        """Get all chats."""
        response = requests.get(
            f"{self.base_url}/api/chats",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_timeseries(self, chat_id: int, metric: str, from_date: str, to_date: str):
        """Get timeseries data."""
        response = requests.get(
            f"{self.base_url}/api/chats/{chat_id}/timeseries",
            headers=self.headers,
            params={
                "metric": metric,
                "from": from_date,
                "to": to_date
            }
        )
        response.raise_for_status()
        return response.json()
    
    def get_users(self, chat_id: int, **kwargs):
        """Get user statistics."""
        response = requests.get(
            f"{self.base_url}/api/chats/{chat_id}/users",
            headers=self.headers,
            params=kwargs
        )
        response.raise_for_status()
        return response.json()


# Usage example
client = TGStatsClient(
    base_url="http://localhost:8000",
    admin_token="your_token_here"
)

# Get chats
chats = client.get_chats()
chat_id = chats["chats"][0]["chat_id"]

# Get last 30 days of messages
to_date = datetime.now().date()
from_date = to_date - timedelta(days=30)

data = client.get_timeseries(
    chat_id=chat_id,
    metric="messages",
    from_date=from_date.isoformat(),
    to_date=to_date.isoformat()
)

# Create DataFrame and plot
df = pd.DataFrame(data["data"])
df["date"] = pd.to_datetime(df["date"])
df.set_index("date", inplace=True)

plt.figure(figsize=(12, 6))
plt.plot(df.index, df["value"], marker='o')
plt.title(f"Messages Over Time - {chats['chats'][0]['title']}")
plt.xlabel("Date")
plt.ylabel("Messages")
plt.grid(True, alpha=0.3)
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("messages_chart.png")
print("Chart saved to messages_chart.png")
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

class TGStatsClient {
    constructor(baseUrl, adminToken) {
        this.baseUrl = baseUrl;
        this.headers = {
            'X-Admin-Token': adminToken,
            'Content-Type': 'application/json'
        };
    }

    async getChats() {
        const response = await axios.get(
            `${this.baseUrl}/api/chats`,
            { headers: this.headers }
        );
        return response.data;
    }

    async getTimeseries(chatId, metric, fromDate, toDate) {
        const response = await axios.get(
            `${this.baseUrl}/api/chats/${chatId}/timeseries`,
            {
                headers: this.headers,
                params: { metric, from: fromDate, to: toDate }
            }
        );
        return response.data;
    }

    async getUsers(chatId, options = {}) {
        const response = await axios.get(
            `${this.baseUrl}/api/chats/${chatId}/users`,
            {
                headers: this.headers,
                params: options
            }
        );
        return response.data;
    }
}

// Usage
async function main() {
    const client = new TGStatsClient(
        'http://localhost:8000',
        'your_token_here'
    );

    // Get all chats
    const chats = await client.getChats();
    console.log('Chats:', chats);

    // Get user statistics
    const chatId = chats.chats[0].chat_id;
    const users = await client.getUsers(chatId, {
        sort: 'messages',
        order: 'desc',
        per_page: 10
    });
    console.log('Top users:', users);
}

main().catch(console.error);
```

### Shell Script - Daily Report

```bash
#!/bin/bash
# daily_report.sh - Generate daily analytics report

API_BASE="http://localhost:8000"
ADMIN_TOKEN="your_token_here"
CHAT_ID="-1001234567890"

# Get yesterday's date
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)
TODAY=$(date +%Y-%m-%d)

echo "=== Daily Report for $YESTERDAY ==="
echo

# Get summary
curl -s -H "X-Admin-Token: $ADMIN_TOKEN" \
     "$API_BASE/api/chats/$CHAT_ID/summary?from=$YESTERDAY&to=$TODAY" \
     | jq '{
         total_messages,
         unique_users,
         avg_messages_per_user,
         media_messages
     }'

echo
echo "=== Top 5 Active Users ==="
echo

curl -s -H "X-Admin-Token: $ADMIN_TOKEN" \
     "$API_BASE/api/chats/$CHAT_ID/users?sort=messages&order=desc&per_page=5" \
     | jq '.users[] | {username, message_count}'
```

---

## Error Handling

### Common HTTP Status Codes

- **200 OK**: Request successful
- **400 Bad Request**: Invalid parameters
- **401 Unauthorized**: Missing or invalid admin token
- **404 Not Found**: Chat or resource not found
- **422 Unprocessable Entity**: Validation error
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid date format",
    "details": {
      "field": "from",
      "expected": "YYYY-MM-DD"
    }
  }
}
```

### Python Error Handling

```python
import requests
from requests.exceptions import HTTPError

def safe_api_call(url, headers):
    """Make API call with error handling."""
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    
    except HTTPError as e:
        if e.response.status_code == 401:
            print("Authentication failed. Check your admin token.")
        elif e.response.status_code == 404:
            print("Resource not found.")
        elif e.response.status_code == 422:
            error_data = e.response.json()
            print(f"Validation error: {error_data.get('error', {}).get('message')}")
        else:
            print(f"HTTP error: {e}")
        return None
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
```

---

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **Default limits**: 100 requests per minute per IP
- **Burst limit**: 10 requests per second

**Rate limit headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1643723400
```

**When rate limited:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "retry_after": 30
  }
}
```

---

## Best Practices

1. **Cache responses** when appropriate (e.g., chat settings)
2. **Use pagination** for large datasets
3. **Handle errors gracefully** with retries for transient failures
4. **Respect rate limits** - implement exponential backoff
5. **Use query parameters** to filter data at the API level
6. **Store admin token securely** - never commit to version control
7. **Use timezone-aware dates** matching the chat's timezone setting

---

## Additional Resources

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Health Check**: http://localhost:8000/healthz
- **OpenAPI Spec**: http://localhost:8000/openapi.json

For questions or issues, check the main repository documentation or create an issue.
