#!/bin/bash
# Emergency script to throttle resources when server is overloaded

# Configuration
LOAD_THRESHOLD=1.5  # Adjust based on your CPU cores (e.g., 2 cores = 1.5)
LOG_FILE="/var/log/tgstats_emergency.log"

# Get number of CPU cores
CPU_CORES=$(nproc)

# Get current load (1-minute average)
CURRENT_LOAD=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')

# Log current state
echo "[$(date)] Load: $CURRENT_LOAD | Threshold: $LOAD_THRESHOLD | CPUs: $CPU_CORES" >> "$LOG_FILE"

# Check if bc is available for floating point comparison
if ! command -v bc &> /dev/null; then
    echo "[$(date)] WARNING: bc not installed, using integer comparison" >> "$LOG_FILE"
    # Fallback to integer comparison
    CURRENT_LOAD_INT=${CURRENT_LOAD%.*}
    THRESHOLD_INT=${LOAD_THRESHOLD%.*}
    
    if [ "$CURRENT_LOAD_INT" -gt "$THRESHOLD_INT" ]; then
        HIGH_LOAD=1
    else
        HIGH_LOAD=0
    fi
else
    # Use bc for precise comparison
    HIGH_LOAD=$(echo "$CURRENT_LOAD > $LOAD_THRESHOLD" | bc -l)
fi

if [ "$HIGH_LOAD" -eq 1 ]; then
    echo "[$(date)] ⚠️ HIGH LOAD DETECTED! Applying throttling..." >> "$LOG_FILE"
    
    # Method 1: Reduce process priorities (nice)
    echo "[$(date)] Adjusting process priorities..." >> "$LOG_FILE"
    for pid in $(pgrep -f "tgstats|celery" | grep -v "grep"); do
        if [ -n "$pid" ]; then
            # Increase nice value (lower priority)
            renice -n 15 -p "$pid" >> "$LOG_FILE" 2>&1
            
            # Set idle I/O priority (requires ionice)
            if command -v ionice &> /dev/null; then
                ionice -c 3 -p "$pid" >> "$LOG_FILE" 2>&1
            fi
        fi
    done
    
    # Method 2: Limit CPU using cpulimit (if installed)
    if command -v cpulimit &> /dev/null; then
        echo "[$(date)] Applying CPU limits..." >> "$LOG_FILE"
        for pid in $(pgrep -f "tgstats.bot_main"); do
            # Limit to 50% of one core
            cpulimit -p "$pid" -l 50 -b >> "$LOG_FILE" 2>&1
        done
        
        for pid in $(pgrep -f "celery.*worker"); do
            # Limit to 40% of one core
            cpulimit -p "$pid" -l 40 -b >> "$LOG_FILE" 2>&1
        done
    fi
    
    # Method 3: Restart Celery workers to clear any stuck tasks
    if command -v supervisorctl &> /dev/null; then
        CELERY_STATUS=$(supervisorctl status | grep tgstats-celery | grep RUNNING)
        if [ -n "$CELERY_STATUS" ]; then
            echo "[$(date)] Restarting Celery workers..." >> "$LOG_FILE"
            supervisorctl restart tgstats:tgstats-celery >> "$LOG_FILE" 2>&1
        fi
    fi
    
    # Method 4: Check for zombie/defunct processes
    ZOMBIE_COUNT=$(ps aux | grep -E "defunct|zombie" | grep -v grep | wc -l)
    if [ "$ZOMBIE_COUNT" -gt 0 ]; then
        echo "[$(date)] Found $ZOMBIE_COUNT zombie processes" >> "$LOG_FILE"
    fi
    
    echo "[$(date)] ✅ Throttling applied" >> "$LOG_FILE"
    
    # Send alert if mail is configured
    if command -v mail &> /dev/null && [ -n "$ADMIN_EMAIL" ]; then
        echo "High load detected on $(hostname): $CURRENT_LOAD" | mail -s "TG Stats High Load Alert" "$ADMIN_EMAIL"
    fi
    
else
    echo "[$(date)] ✅ Load is normal ($CURRENT_LOAD <= $LOAD_THRESHOLD)" >> "$LOG_FILE"
    
    # Restore normal priorities if they were changed
    for pid in $(pgrep -f "tgstats|celery" | grep -v "grep"); do
        if [ -n "$pid" ]; then
            # Check current nice value
            CURRENT_NICE=$(ps -o nice= -p "$pid" 2>/dev/null)
            if [ "$CURRENT_NICE" -gt 5 ]; then
                # Restore to normal priority
                renice -n 5 -p "$pid" >> "$LOG_FILE" 2>&1
            fi
        fi
    done
    
    # Kill any running cpulimit processes
    if command -v cpulimit &> /dev/null; then
        pkill cpulimit 2>/dev/null
    fi
fi

# Cleanup: Keep log file under 10MB
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$LOG_SIZE" -gt 10485760 ]; then
        echo "[$(date)] Rotating log file (size: $LOG_SIZE bytes)" >> "$LOG_FILE"
        mv "$LOG_FILE" "${LOG_FILE}.old"
    fi
fi
