#!/usr/bin/env python3
"""
Log viewer utility for TGStats Bot.

Usage:
    python scripts/view_logs.py              # View last 50 lines
    python scripts/view_logs.py -n 100       # View last 100 lines
    python scripts/view_logs.py --follow     # Follow logs in real-time
    python scripts/view_logs.py --level ERROR # Filter by level
    python scripts/view_logs.py --search "message processing" # Search logs
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path


def parse_log_line(line: str) -> dict:
    """Parse a log line (JSON or text format)."""
    line = line.strip()
    if not line:
        return None

    # Try JSON format first
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        # Text format - parse manually
        # Format: timestamp [LEVEL] logger - message key=value
        parts = line.split(None, 3)
        if len(parts) >= 3:
            return {
                "timestamp": parts[0] + " " + parts[1] if len(parts) > 1 else parts[0],
                "level": parts[2].strip("[]") if len(parts) > 2 else "INFO",
                "message": parts[3] if len(parts) > 3 else "",
            }
    return {"message": line, "level": "INFO"}


def colorize(text: str, color_code: str) -> str:
    """Colorize text for terminal output."""
    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "gray": "\033[90m",
        "reset": "\033[0m",
    }
    return f"{colors.get(color_code, '')}{text}{colors['reset']}"


def format_log_entry(entry: dict, colorize_output: bool = True) -> str:
    """Format a log entry for display."""
    if not entry:
        return ""

    level = entry.get("level", "INFO").upper()
    timestamp = entry.get("timestamp", "")
    message = entry.get("event", entry.get("message", ""))
    logger_name = entry.get("logger", "")

    # Level colors
    level_colors = {
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "magenta",
    }

    if colorize_output:
        level_str = colorize(f"[{level:8}]", level_colors.get(level, "reset"))
        timestamp_str = colorize(timestamp, "gray")
        logger_str = colorize(logger_name, "blue") if logger_name else ""
    else:
        level_str = f"[{level:8}]"
        timestamp_str = timestamp
        logger_str = logger_name

    # Build output line
    parts = [timestamp_str, level_str]
    if logger_str:
        parts.append(logger_str)
    parts.append(message)

    # Add extra fields
    skip_keys = {"timestamp", "level", "event", "message", "logger", "log_level", "app", "pid"}
    extras = {k: v for k, v in entry.items() if k not in skip_keys}
    if extras:
        extra_str = " ".join(f"{k}={v}" for k, v in extras.items())
        if colorize_output:
            extra_str = colorize(extra_str, "gray")
        parts.append(extra_str)

    return " ".join(parts)


def view_logs(
    log_file: Path,
    num_lines: int = 50,
    follow: bool = False,
    level_filter: str = None,
    search: str = None,
    colorize_output: bool = True,
):
    """View log file with optional filtering."""
    if not log_file.exists():
        print(f"Log file not found: {log_file}", file=sys.stderr)
        return

    if follow:
        # Follow mode - tail -f style
        print(f"Following {log_file} (Ctrl+C to stop)...")
        print("-" * 80)

        with open(log_file, "r") as f:
            # Go to end of file
            f.seek(0, 2)

            try:
                while True:
                    line = f.readline()
                    if line:
                        entry = parse_log_line(line)
                        if entry:
                            if (
                                level_filter
                                and entry.get("level", "").upper() != level_filter.upper()
                            ):
                                continue
                            if search and search.lower() not in str(entry).lower():
                                continue
                            print(format_log_entry(entry, colorize_output))
                    else:
                        time.sleep(0.1)
            except KeyboardInterrupt:
                print("\nStopped following logs")
    else:
        # View last N lines
        with open(log_file, "r") as f:
            lines = f.readlines()

        # Apply filters and show last N lines
        filtered_lines = []
        for line in lines:
            entry = parse_log_line(line)
            if entry:
                if level_filter and entry.get("level", "").upper() != level_filter.upper():
                    continue
                if search and search.lower() not in str(entry).lower():
                    continue
                filtered_lines.append(entry)

        # Show last N
        display_lines = filtered_lines[-num_lines:]

        print(f"Showing last {len(display_lines)} lines from {log_file}")
        print("-" * 80)
        for entry in display_lines:
            print(format_log_entry(entry, colorize_output))


def main():
    parser = argparse.ArgumentParser(description="View TGStats bot logs")
    parser.add_argument(
        "-f", "--file", default="logs/tgstats.log", help="Log file path (default: logs/tgstats.log)"
    )
    parser.add_argument(
        "-n", "--lines", type=int, default=50, help="Number of lines to show (default: 50)"
    )
    parser.add_argument(
        "--follow", action="store_true", help="Follow log file in real-time (like tail -f)"
    )
    parser.add_argument(
        "--level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Filter by log level",
    )
    parser.add_argument("-s", "--search", help="Search for text in logs")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = parser.parse_args()

    log_file = Path(args.file)

    view_logs(
        log_file=log_file,
        num_lines=args.lines,
        follow=args.follow,
        level_filter=args.level,
        search=args.search,
        colorize_output=not args.no_color,
    )


if __name__ == "__main__":
    main()
