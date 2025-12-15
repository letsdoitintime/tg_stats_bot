#!/bin/bash
# Monitor resource usage of TG Stats processes

echo "=== TG Stats Resource Monitor ==="
echo "Date: $(date)"
echo ""

echo "--- CPU & Memory Usage (TG Stats Processes) ---"
ps aux | grep -E "tgstats|celery" | grep -v grep | awk '{printf "%-50s CPU: %5s%%  MEM: %5s%%  RSS: %8s KB\n", substr($11,1,50), $3, $4, $6}'

echo ""
echo "--- Total System Load ---"
uptime

echo ""
echo "--- CPU Usage ---"
if command -v mpstat &> /dev/null; then
    mpstat 1 1 | tail -1
else
    top -bn1 | grep "Cpu(s)" | awk '{print "CPU: " $2 " user, " $4 " system, " $8 " idle"}'
fi

echo ""
echo "--- Memory Usage ---"
free -h | grep -E "Mem|Swap"

echo ""
echo "--- Top Memory Consumers ---"
ps aux --sort=-%mem | head -11 | awk 'NR==1 || /python|celery|postgres|redis/'

echo ""
echo "--- Top CPU Consumers ---"
ps aux --sort=-%cpu | head -11 | awk 'NR==1 || /python|celery|postgres|redis/'

echo ""
echo "--- Disk Usage ---"
df -h / | tail -1

echo ""
echo "--- PostgreSQL Stats ---"
if command -v psql &> /dev/null; then
    psql -U postgres -d tgstats -t -c "SELECT count(*) || ' active connections' FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null || echo "Cannot query PostgreSQL"
    psql -U postgres -d tgstats -t -c "SELECT pg_size_pretty(pg_database_size('tgstats')) || ' database size';" 2>/dev/null
else
    echo "psql not available"
fi

echo ""
echo "--- Redis Stats ---"
if command -v redis-cli &> /dev/null; then
    echo "Memory: $(redis-cli INFO memory 2>/dev/null | grep used_memory_human: | cut -d: -f2 || echo 'N/A')"
    echo "Connected clients: $(redis-cli INFO clients 2>/dev/null | grep connected_clients: | cut -d: -f2 || echo 'N/A')"
else
    echo "redis-cli not available"
fi

echo ""
echo "--- Network Connections ---"
netstat -an 2>/dev/null | grep ESTABLISHED | wc -l | awk '{print $1 " established connections"}'

echo ""
echo "=== End of Report ==="
