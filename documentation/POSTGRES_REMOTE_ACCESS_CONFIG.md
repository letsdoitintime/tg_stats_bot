# PostgreSQL Remote Access Configuration for tgstats Database

## Summary
Your PostgreSQL database is now configured to accept connections from:
- **Remote IP**: 45.128.218.94
- **Local connections**: localhost, 127.0.0.1, ::1
- **Database**: tgstats
- **Port**: 5432 (standard PostgreSQL port)

## Database User Configuration

### Created User
- **Username**: `tgstats_user`
- **Password**: `your_secure_password_here` (⚠️ **CHANGE THIS PASSWORD!**)
- **Permissions**: Full access to `tgstats` database

### To change the password:
```sql
sudo -u postgres psql -c "ALTER USER tgstats_user PASSWORD 'your_new_secure_password';"
```

## Connection Details

### Local Connection:
```bash
psql -h localhost -p 5432 -U tgstats_user -d tgstats
```

### Remote Connection (from 45.128.218.94):
```bash
psql -h YOUR_SERVER_IP -p 5432 -U tgstats_user -d tgstats
```

### Application Connection String:
```
postgresql+psycopg://tgstats_user:your_secure_password_here@localhost:5432/tgstats
```

## Security Configuration

### Firewall Rules (UFW):
- ✅ SSH access (port 22) - allowed from anywhere
- ✅ PostgreSQL (port 5432) - allowed from specific IP (45.128.218.94)
- ✅ PostgreSQL (port 5432) - allowed locally
- ✅ Default deny incoming, allow outgoing

### PostgreSQL Authentication:
- Uses SCRAM-SHA-256 encryption for passwords
- Peer authentication for local Unix socket connections
- No trust authentication (more secure)

## Configuration Files Modified:

### 1. `/etc/postgresql/16/main/postgresql.conf`
```ini
listen_addresses = '*'
```

### 2. `/etc/postgresql/16/main/pg_hba.conf`
Added rules:
```
# Specific rules for tgstats database
host    tgstats         tgstats_user    45.128.218.94/32        scram-sha-256
host    tgstats         tgstats_user    127.0.0.1/32           scram-sha-256
host    tgstats         tgstats_user    ::1/128                scram-sha-256

# Allow postgres superuser from local connections only
host    tgstats         postgres        127.0.0.1/32           scram-sha-256
host    tgstats         postgres        ::1/128                scram-sha-256
```

### 3. `.env` file updated:
```properties
DATABASE_URL=postgresql+psycopg://tgstats_user:your_secure_password_here@localhost:5432/tgstats
```

## Testing Connection

### Local test:
```bash
psql -h localhost -p 5432 -U tgstats_user -d tgstats -c "SELECT current_database(), current_user;"
```

### Remote test (from 45.128.218.94):
```bash
psql -h YOUR_SERVER_IP -p 5432 -U tgstats_user -d tgstats -c "SELECT current_database(), current_user;"
```

## Important Security Notes:

1. **Change the default password** immediately:
   ```sql
   sudo -u postgres psql -c "ALTER USER tgstats_user PASSWORD 'your_strong_password_here';"
   ```

2. **Update your .env file** with the new password

3. **Firewall is enabled** - only the specified IP can access PostgreSQL remotely

4. **Monitor connections**:
   ```bash
   sudo tail -f /var/log/postgresql/postgresql-16-main.log
   ```

5. **Backup configuration**:
   - Original pg_hba.conf backed up to: `/etc/postgresql/16/main/pg_hba.conf.backup`

## Additional Recommendations:

1. **SSL/TLS**: Consider enabling SSL for encrypted connections
2. **Regular backups**: Set up automated database backups
3. **Monitoring**: Monitor failed connection attempts
4. **IP restrictions**: Keep the allowed IP list minimal
5. **Password rotation**: Change passwords regularly

## Troubleshooting:

### Check PostgreSQL status:
```bash
sudo systemctl status postgresql
```

### Check if PostgreSQL is listening:
```bash
sudo netstat -tlnp | grep :5432
```

### Check firewall rules:
```bash
sudo ufw status numbered
```

### Reload PostgreSQL config:
```bash
sudo systemctl reload postgresql
```

### View PostgreSQL logs:
```bash
sudo tail -f /var/log/postgresql/postgresql-16-main.log
```
