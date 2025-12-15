#!/bin/bash
# Quick emergency script to immediately limit resources

echo "=== Emergency Resource Limiter ==="
echo "Applying immediate resource restrictions..."
echo ""

# 1. Reduce all Python bot process priorities
echo "1. Reducing process priorities..."
AFFECTED=0
for pid in $(pgrep -f "python.*TelegramBots" | grep -v grep); do
    if [ -n "$pid" ]; then
        # Set nice to 15 (lower priority)
        renice -n 15 -p $pid > /dev/null 2>&1
        
        # Set I/O priority to idle (if ionice available)
        if command -v ionice &> /dev/null; then
            ionice -c 3 -p $pid > /dev/null 2>&1
        fi
        
        AFFECTED=$((AFFECTED + 1))
    fi
done
echo "   ✅ Adjusted priority for $AFFECTED processes"

# 2. Apply CPU limits using cpulimit (if available)
if command -v cpulimit &> /dev/null; then
    echo "2. Applying CPU limits..."
    
    # Kill existing cpulimit processes
    pkill cpulimit > /dev/null 2>&1
    
    # Limit Chat_Stats bot
    for pid in $(pgrep -f "tgstats.bot_main"); do
        if [ -n "$pid" ]; then
            cpulimit -p $pid -l 50 -b > /dev/null 2>&1
            echo "   ✅ Limited bot_main (PID $pid) to 50% CPU"
        fi
    done
    
    # Limit Celery workers
    for pid in $(pgrep -f "celery.*worker"); do
        if [ -n "$pid" ]; then
            cpulimit -p $pid -l 40 -b > /dev/null 2>&1
            echo "   ✅ Limited celery worker (PID $pid) to 40% CPU"
        fi
    done
else
    echo "2. ⚠️  cpulimit not installed - run: sudo apt install cpulimit"
fi

# 3. Check for runaway processes (using > 90% CPU)
echo "3. Checking for runaway processes..."
RUNAWAY=$(ps aux | awk '{if ($3 > 90.0) print $2,$11}' | grep python | head -5)
if [ -n "$RUNAWAY" ]; then
    echo "   ⚠️  WARNING: High CPU processes detected:"
    echo "$RUNAWAY" | while read pid cmd; do
        echo "      PID $pid: $cmd ($(ps aux | grep "^root.*$pid" | awk '{print $3}')% CPU)"
    done
    echo ""
    read -p "   Kill these processes? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$RUNAWAY" | awk '{print $1}' | xargs sudo kill -9
        echo "   ✅ Processes killed"
    fi
else
    echo "   ✅ No runaway processes found"
fi

# 4. Check memory usage
echo "4. Checking memory usage..."
MEM_PERCENT=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
echo "   Memory usage: $MEM_PERCENT%"

if [ $MEM_PERCENT -gt 80 ]; then
    echo "   ⚠️  HIGH MEMORY USAGE!"
    echo "   Top memory consumers:"
    ps aux --sort=-%mem | head -6 | awk 'NR>1 {printf "      %5s%% %s\n", $4, $11}'
    
    # Suggest restarting services
    echo ""
    read -p "   Restart TG Stats services to clear memory? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v supervisorctl &> /dev/null; then
            supervisorctl restart tgstats:*
            echo "   ✅ Services restarted via Supervisor"
        elif command -v systemctl &> /dev/null; then
            systemctl restart tgstats-bot tgstats-celery tgstats-celery-beat
            echo "   ✅ Services restarted via systemd"
        else
            echo "   ⚠️  Could not find service manager"
        fi
    fi
fi

# 5. Check system load
echo "5. Checking system load..."
LOAD=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
echo "   Current load: $LOAD"

# 6. Check disk space
echo "6. Checking disk space..."
DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
echo "   Disk usage: $DISK_USAGE%"

if [ $DISK_USAGE -gt 85 ]; then
    echo "   ⚠️  LOW DISK SPACE!"
    echo "   Consider cleaning logs:"
    echo "      find /TelegramBots/*/logs -name '*.log' -mtime +7 -delete"
fi

# 7. PostgreSQL optimization
echo "7. Checking PostgreSQL connections..."
if command -v psql &> /dev/null; then
    PG_CONNS=$(psql -U postgres -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null | xargs)
    if [ -n "$PG_CONNS" ]; then
        echo "   Active connections: $PG_CONNS"
        
        # Kill old idle connections
        KILLED=$(psql -U postgres -t -c "
            SELECT count(*) FROM pg_stat_activity 
            WHERE state = 'idle' 
            AND state_change < now() - interval '10 minutes';
        " 2>/dev/null | xargs)
        
        if [ "$KILLED" -gt 0 ]; then
            psql -U postgres -c "
                SELECT pg_terminate_backend(pid) 
                FROM pg_stat_activity 
                WHERE state = 'idle' 
                AND state_change < now() - interval '10 minutes';
            " > /dev/null 2>&1
            echo "   ✅ Killed $KILLED idle connections"
        fi
    fi
fi

echo ""
echo "=== Summary ==="
echo "✅ Process priorities adjusted"
echo "✅ CPU limits applied (if cpulimit available)"
echo "✅ System health checked"
echo ""
echo "Current status:"
echo "   Load: $LOAD"
echo "   Memory: $MEM_PERCENT%"
echo "   Disk: $DISK_USAGE%"
echo ""
echo "Monitor with: ./scripts/monitor_resources.sh"
echo "View logs: tail -f /var/log/tgstats_emergency.log"
echo ""
