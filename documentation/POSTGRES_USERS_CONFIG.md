# PostgreSQL Users Configuration for tgstats Database

## Database Users Summary

### 1. User: `andrew`
- **Username**: `andrew`
- **Password**: `andrew_secure_password_2025`
- **Database**: `tgstats`
- **Permissions**: Full access to tgstats database (same as tgstats_user)

### 2. User: `tgstats_user`
- **Username**: `tgstats_user` 
- **Password**: `your_secure_password_here`
- **Database**: `tgstats`
- **Permissions**: Full access to tgstats database

### 3. User: `postgres` (Superuser)
- **Username**: `postgres`
- **Database**: All databases
- **Permissions**: Superuser (full system access)

## Remote Access Configuration

Both `andrew` and `tgstats_user` can connect from:
- **Remote IP**: 45.128.218.94
- **Local connections**: 127.0.0.1, ::1, localhost

## Connection Examples

### For user 'andrew':
```bash
# Local connection
psql -h localhost -p 5432 -U andrew -d tgstats

# Remote connection (from 45.128.218.94)
psql -h YOUR_SERVER_IP -p 5432 -U andrew -d tgstats

# Connection string
postgresql+psycopg://andrew:andrew_secure_password_2025@localhost:5432/tgstats
```

### For user 'tgstats_user':
```bash
# Local connection
psql -h localhost -p 5432 -U tgstats_user -d tgstats

# Remote connection (from 45.128.218.94)
psql -h YOUR_SERVER_IP -p 5432 -U tgstats_user -d tgstats

# Connection string
postgresql+psycopg://tgstats_user:your_secure_password_here@localhost:5432/tgstats
```

## Current .env Configuration
```properties
DATABASE_URL=postgresql+psycopg://andrew:andrew_secure_password_2025@localhost:5432/tgstats
```

## User Management Commands

### Change password for andrew:
```sql
sudo -u postgres psql -c "ALTER USER andrew PASSWORD 'new_password_here';"
```

### Change password for tgstats_user:
```sql
sudo -u postgres psql -c "ALTER USER tgstats_user PASSWORD 'new_password_here';"
```

### View user privileges:
```sql
sudo -u postgres psql tgstats -c "\dp"
```

### List all users:
```sql
sudo -u postgres psql -c "\du"
```

## Security Notes

1. **Both users have identical permissions** on the tgstats database
2. **Both users can connect remotely** from IP 45.128.218.94
3. **Authentication uses SCRAM-SHA-256** encryption
4. **Passwords should be changed** to something more secure
5. **Firewall rules allow** both users to connect

## Switching Between Users

To switch your application to use `tgstats_user` instead of `andrew`, simply update the .env file:

```properties
DATABASE_URL=postgresql+psycopg://tgstats_user:your_secure_password_here@localhost:5432/tgstats
```

## Backup User Access

Having two users with the same permissions provides:
- **Redundancy**: If one user has issues, use the other
- **Role separation**: Use different users for different applications/purposes
- **Security**: Can rotate passwords independently
