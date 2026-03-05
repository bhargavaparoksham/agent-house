"""
usage_tracker.py
Tracks Claude Max session usage, message estimates, and fires alerts.
Claude Max: 225 messages / 5-hour rolling window.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from typing import Tuple


# Claude Max limits
MAX_MESSAGES_5HR = 225
WARN_THRESHOLD = 0.80   # 80% → warning
PAUSE_THRESHOLD = 0.90  # 90% → pause agents


def load_usage() -> dict:
    if not Path(USAGE_PATH).exists():
        return {"sessions": [], "daily_totals": {}, "alerts_fired": []}
    with open(USAGE_PATH, "r") as f:
        return json.load(f)


def save_usage(data: dict):
    with open(USAGE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def log_session_start(project: str, role: str) -> str:
    """Log a new agent session. Returns session_id."""
    data = load_usage()
    session_id = f"{project}-{role}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    data["sessions"].append({
        "id": session_id,
        "project": project,
        "role": role,
        "provider": "claude-max",
        "started_at": datetime.now().isoformat(),
        "ended_at": None,
        "messages": 0,
        "refreshes": 0
    })
    save_usage(data)
    return session_id


def log_session_end(session_id: str, messages: int = 0):
    data = load_usage()
    for s in data["sessions"]:
        if s["id"] == session_id:
            s["ended_at"] = datetime.now().isoformat()
            s["messages"] = messages
            break
    save_usage(data)


def log_refresh(session_id: str):
    data = load_usage()
    for s in data["sessions"]:
        if s["id"] == session_id:
            s["refreshes"] = s.get("refreshes", 0) + 1
            break
    save_usage(data)


def increment_messages(session_id: str, count: int = 1):
    data = load_usage()
    for s in data["sessions"]:
        if s["id"] == session_id:
            s["messages"] = s.get("messages", 0) + count
            break
    save_usage(data)


def get_messages_last_5hr() -> int:
    """Estimate messages used in rolling 5-hour window across all sessions."""
    data = load_usage()
    cutoff = datetime.now() - timedelta(hours=5)
    total = 0
    for s in data["sessions"]:
        started = datetime.fromisoformat(s["started_at"])
        if started >= cutoff:
            total += s.get("messages", 0)
    return total


def get_window_reset_time() -> str:
    """Estimate when the oldest session in the 5hr window drops off."""
    data = load_usage()
    cutoff = datetime.now() - timedelta(hours=5)
    earliest = None
    for s in data["sessions"]:
        started = datetime.fromisoformat(s["started_at"])
        if started >= cutoff:
            if earliest is None or started < earliest:
                earliest = started
    if earliest:
        reset_at = earliest + timedelta(hours=5)
        delta = reset_at - datetime.now()
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes // 60}h {minutes % 60}m"
    return "unknown"


def get_active_sessions() -> list:
    data = load_usage()
    return [s for s in data["sessions"] if s["ended_at"] is None]


def get_usage_report() -> str:
    data = load_usage()
    used_5hr = get_messages_last_5hr()
    pct = used_5hr / MAX_MESSAGES_5HR
    reset_time = get_window_reset_time()

    # Per-project breakdown
    today = datetime.now().date().isoformat()
    project_counts = {}
    for s in data["sessions"]:
        if s["started_at"][:10] == today:
            key = f"{s['project']}-{s['role']}"
            project_counts[key] = project_counts.get(key, 0) + s.get("messages", 0)

    agent_lines = "\n".join(
        f"  {k:<30} {v} msgs"
        for k, v in sorted(project_counts.items())
    ) or "  No sessions today"

    bar_filled = int(pct * 20)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)

    return (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Usage — Claude Max\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"5-hr window:\n"
        f"  [{bar}] {pct*100:.0f}%\n"
        f"  {used_5hr}/{MAX_MESSAGES_5HR} messages\n"
        f"  Resets in {reset_time}\n"
        f"\nActive sessions: {len(get_active_sessions())}\n"
        f"\nPer agent (today):\n{agent_lines}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def check_limits() -> Tuple[bool, str]:
    """Returns (should_pause, alert_message). Empty message = no alert."""
    used = get_messages_last_5hr()
    pct = used / MAX_MESSAGES_5HR
    data = load_usage()

    if pct >= PAUSE_THRESHOLD:
        alert = (
            f"🔴 LIMIT ALERT: {used}/{MAX_MESSAGES_5HR} messages used "
            f"({pct*100:.0f}%). Auto-pausing agents. "
            f"Resets in {get_window_reset_time()}."
        )
        return True, alert
    elif pct >= WARN_THRESHOLD:
        alert = (
            f"🟡 USAGE WARNING: {used}/{MAX_MESSAGES_5HR} messages "
            f"({pct*100:.0f}%). Resets in {get_window_reset_time()}."
        )
        return False, alert

    return False, ""
