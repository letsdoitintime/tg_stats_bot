# DBeaver Connection Guide for PostgreSQL (User: andrew)

## Connection Details

### 📋 **Connection Information:**
- **Server Host/IP**: `95.216.202.228` (Your server's public IP)
- **Port**: `5432`
- **Database**: `tgstats`
- **Username**: `andrew`
- **Password**: `andrew_secure_password_2025`

---

## 🔧 **Step-by-Step DBeaver Setup:**

### 1. **Create New Connection**
1. Open DBeaver
2. Click on "New Database Connection" (plug icon) or go to `Database` → `New Database Connection`
3. Select **PostgreSQL** from the list
4. Click **Next**

### 2. **Configure Connection Settings**

#### **Main Tab:**
- **Server Host**: `95.216.202.228`
- **Port**: `5432`
- **Database**: `tgstats`
- **Username**: `andrew`
- **Password**: `andrew_secure_password_2025`
- **Save password**: ✅ (recommended)

#### **SSL Tab (Optional but Recommended):**
- **Use SSL**: Disabled (for now, as we haven't configured SSL)
- If you want to enable SSL later, we can configure that

#### **Advanced Tab (Optional):**
- **Connection name**: `TG Stats - Andrew` (or any name you prefer)
- **Connection folder**: You can organize connections in folders

### 3. **Test Connection**
1. Click **Test Connection** button
2. If successful, you should see "Connected" message
3. If it fails, check the troubleshooting section below

### 4. **Save and Connect**
1. Click **Finish** to save the connection
2. Double-click on the connection to connect
3. You should now see the `tgstats` database structure

---

## 🌐 **Alternative Connection Methods:**

### **Local Connection (if connecting from the same server):**
- **Server Host**: `localhost` or `127.0.0.1`
- **Port**: `5432`
- **Database**: `tgstats`
- **Username**: `andrew`
- **Password**: `andrew_secure_password_2025`

### **Connection URL Format:**
```
jdbc:postgresql://95.216.202.228:5432/tgstats
```

---

## 🔍 **Verification Steps:**

### **After Connecting Successfully:**
1. **Check Current User**:
   ```sql
   SELECT current_user, current_database();
   ```
   Should return: `andrew | tgstats`

2. **List Tables**:
   ```sql
   \dt
   ```
   Or use DBeaver's database navigator

3. **Check Permissions**:
   ```sql
   SELECT table_name, privilege_type 
   FROM information_schema.table_privileges 
   WHERE grantee = 'andrew';
   ```

---

## 🚨 **Troubleshooting:**

### **Common Issues and Solutions:**

#### **1. Connection Timeout/Refused**
- ✅ **Check**: Firewall allows connection from your IP
- ✅ **Check**: PostgreSQL is running: `sudo systemctl status postgresql`
- ✅ **Check**: PostgreSQL is listening: `sudo netstat -tlnp | grep :5432`

#### **2. Authentication Failed**
- ✅ **Check**: Username and password are correct
- ✅ **Check**: User exists: `sudo -u postgres psql -c "\du"`
- ✅ **Reset password**: `sudo -u postgres psql -c "ALTER USER andrew PASSWORD 'new_password';"`

#### **3. Database Not Found**
- ✅ **Check**: Database exists: `sudo -u postgres psql -c "\l" | grep tgstats`

#### **4. Permission Denied**
- ✅ **Check**: User has access to database
- ✅ **Grant access**: `sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE tgstats TO andrew;"`

---

## 🔒 **Security Notes:**

1. **IP Restrictions**: Connection is allowed only from `45.128.218.94`
   - If connecting from a different IP, contact admin to add your IP to firewall rules

2. **Password Security**: 
   - Consider changing the default password
   - Use strong passwords in production

3. **SSL Encryption**: 
   - Currently disabled for simplicity
   - Can be enabled for production use

---

## 📝 **Useful SQL Commands in DBeaver:**

### **Database Information:**
```sql
-- Current connection info
SELECT current_user, current_database(), inet_server_addr(), inet_server_port();

-- Database size
SELECT pg_database_size('tgstats') / 1024 / 1024 AS size_mb;

-- List all tables
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';

-- Table row counts
SELECT 
    schemaname,
    tablename,
    n_tup_ins - n_tup_del AS row_count
FROM pg_stat_user_tables;
```

### **User Permissions:**
```sql
-- Check user privileges
SELECT * FROM information_schema.table_privileges WHERE grantee = 'andrew';

-- Check role memberships
SELECT * FROM pg_roles WHERE rolname = 'andrew';
```

---

## 🔄 **Connection String for Other Tools:**

### **Standard PostgreSQL Connection String:**
```
postgresql://andrew:andrew_secure_password_2025@95.216.202.228:5432/tgstats
```

### **For Python Applications:**
```python
DATABASE_URL = "postgresql+psycopg://andrew:andrew_secure_password_2025@95.216.202.228:5432/tgstats"
```

### **For JDBC:**
```
jdbc:postgresql://95.216.202.228:5432/tgstats
```

---

## 🆘 **Support Commands:**

If you need to make changes from the server side:

### **Add New IP to Firewall:**
```bash
sudo ufw allow from YOUR_NEW_IP to any port 5432
```

### **Change User Password:**
```bash
sudo -u postgres psql -c "ALTER USER andrew PASSWORD 'new_password';"
```

### **Check Connection Logs:**
```bash
sudo tail -f /var/log/postgresql/postgresql-16-main.log
```
