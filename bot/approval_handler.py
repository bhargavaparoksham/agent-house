"""
approval_handler.py
Watches in-progress.txt files for status changes.
When a task reaches awaiting-human, fires a Telegram notification.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, '/opt/agent-bots')

REGISTRY_PATH = "/opt/agent-bots/registry.json"
PROJECTS_BASE = "/home/projects"
BOT_STATE_PATH = "/opt/agent-bots/bot_state.json"


def load_bot_state() -> dict:
    if Path(BOT_STATE_PATH).exists():
        with open(BOT_STATE_PATH) as f:
            return json.load(f)
    return {"telegram_token": "", "admin_chat_id": "", "pending_approvals": {}}


def save_bot_state(state: dict):
    with open(BOT_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def get_running_projects() -> list:
    with open(REGISTRY_PATH) as f:
        reg = json.load(f)
    return [p for p in reg["projects"] if p.get("status") == "running"]


def get_task_status(project_name: str) -> str:
    path = Path(PROJECTS_BASE) / project_name / "control-center" / "in-progress.txt"
    if not path.exists():
        return ""
    for line in path.read_text().splitlines():
        if line.startswith("STATUS:"):
            return line.replace("STATUS:", "").strip()
    return ""


def get_feedback_verdict(project_name: str) -> str:
    path = Path(PROJECTS_BASE) / project_name / "control-center" / "feedback.txt"
    if not path.exists():
        return ""
    for line in path.read_text().splitlines():
        if line.startswith("VERDICT:"):
            return line.replace("VERDICT:", "").strip()
    return ""


def build_approval_message(project_name: str) -> str:
    base = Path(PROJECTS_BASE) / project_name / "control-center"

    in_progress = (base / "in-progress.txt").read_text() if (base / "in-progress.txt").exists() else "—"
    feedback = (base / "feedback.txt").read_text() if (base / "feedback.txt").exists() else "—"
    progress_tail = ""
    prog_path = base / "claude-progress.txt"
    if prog_path.exists():
        lines = prog_path.read_text().splitlines()
        progress_tail = "\n".join(lines[-15:])

    return (
        f"🔔 *Task Ready for Review*\n"
        f"Project: `{project_name}`\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"*Current Task:*\n```\n{in_progress[:600]}\n```\n\n"
        f"*Verifier Verdict:*\n```\n{feedback[:400]}\n```\n\n"
        f"*Recent Progress:*\n```\n{progress_tail[:400]}\n```"
    )


def notify_human_review(project_name: str):
    """Called by context_refresh.sh when status=awaiting-human."""
    state = load_bot_state()
    token = state.get("telegram_token", "")
    chat_id = state.get("admin_chat_id", "")
    if not token or not chat_id:
        print("No telegram config — cannot notify")
        return

    # Write to a pending file that the bot picks up
    pending = state.get("pending_approvals", {})
    pending[project_name] = {
        "project": project_name,
        "triggered_at": datetime.now().isoformat(),
        "message": build_approval_message(project_name)
    }
    state["pending_approvals"] = pending
    save_bot_state(state)
    print(f"Queued human review notification for: {project_name}")


class ApprovalWatcher:
    """Polls in-progress.txt files and queues notifications."""

    def __init__(self, poll_interval: int = 30):
        self.poll_interval = poll_interval
        self.last_statuses = {}

    def run(self):
        print(f"[approval_handler] Watching projects (poll={self.poll_interval}s)")
        while True:
            try:
                self._check_projects()
            except Exception as e:
                print(f"[approval_handler] Error: {e}")
            time.sleep(self.poll_interval)

    def _check_projects(self):
        try:
            projects = get_running_projects()
        except Exception:
            return

        for p in projects:
            name = p["name"]
            status = get_task_status(name)
            prev = self.last_statuses.get(name, "")

            if status != prev:
                print(f"[approval_handler] {name}: {prev} → {status}")
                self.last_statuses[name] = status

            if status == "awaiting-human" and prev != "awaiting-human":
                notify_human_review(name)


if __name__ == "__main__":
    watcher = ApprovalWatcher(poll_interval=30)
    watcher.run()
