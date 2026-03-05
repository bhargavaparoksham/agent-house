"""
agent_registry.py
Manages the project registry — reading, writing, and querying project configs.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

REGISTRY_PATH = "/opt/agent-bots/registry.json"
PROJECTS_BASE = "/home/projects"


def load_registry() -> dict:
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)


def save_registry(registry: dict):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def get_project(name: str) -> Optional[dict]:
    registry = load_registry()
    for p in registry["projects"]:
        if p["name"] == name:
            return p
    return None


def list_projects() -> list:
    return load_registry()["projects"]


def register_project(config: dict):
    registry = load_registry()
    # Remove existing if re-registering
    registry["projects"] = [p for p in registry["projects"] if p["name"] != config["name"]]
    config["created_at"] = datetime.now().isoformat()
    config["status"] = "idle"
    registry["projects"].append(config)
    save_registry(registry)


def update_project_status(name: str, status: str):
    """status: idle | running | paused | error"""
    registry = load_registry()
    for p in registry["projects"]:
        if p["name"] == name:
            p["status"] = status
            p["status_updated"] = datetime.now().isoformat()
    save_registry(registry)


def project_path(name: str) -> Path:
    return Path(PROJECTS_BASE) / name


def control_center_path(name: str) -> Path:
    return project_path(name) / "control-center"


def read_control_file(project_name: str, filename: str) -> str:
    path = control_center_path(project_name) / filename
    if path.exists():
        return path.read_text()
    return ""


def write_control_file(project_name: str, filename: str, content: str):
    path = control_center_path(project_name) / filename
    path.write_text(content)


def append_control_file(project_name: str, filename: str, content: str):
    path = control_center_path(project_name) / filename
    with open(path, "a") as f:
        f.write(content + "\n")


def get_active_task(project_name: str) -> Optional[str]:
    content = read_control_file(project_name, "in-progress.txt")
    if not content.strip():
        return None
    for line in content.splitlines():
        if line.startswith("TASK:"):
            return line.replace("TASK:", "").strip()
    return None


def get_task_status(project_name: str) -> Optional[str]:
    content = read_control_file(project_name, "in-progress.txt")
    for line in content.splitlines():
        if line.startswith("STATUS:"):
            return line.replace("STATUS:", "").strip()
    return None


def set_task_status(project_name: str, status: str):
    """Update STATUS field in in-progress.txt"""
    path = control_center_path(project_name) / "in-progress.txt"
    if not path.exists():
        return
    content = path.read_text()
    lines = content.splitlines()
    updated = []
    for line in lines:
        if line.startswith("STATUS:"):
            updated.append(f"STATUS: {status}")
        else:
            updated.append(line)
    path.write_text("\n".join(updated))


def get_todo_tasks(project_name: str) -> list:
    content = read_control_file(project_name, "todo.txt")
    tasks = []
    for line in content.splitlines():
        line = line.strip()
        if line and line.startswith("[TASK-"):
            tasks.append(line)
    return tasks


def complete_task(project_name: str, summary: str, approved_by: str = "human"):
    """Move current in-progress task to completed-tasks.txt"""
    in_progress = read_control_file(project_name, "in-progress.txt")
    task_line = ""
    for line in in_progress.splitlines():
        if line.startswith("TASK:"):
            task_line = line.replace("TASK:", "").strip()
            break

    entry = f"""[{task_line}]
COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M')}
APPROVED-BY: {approved_by}
SUMMARY: {summary}
---"""
    append_control_file(project_name, "completed-tasks.txt", entry)
    write_control_file(project_name, "in-progress.txt", "")
    write_control_file(project_name, "feedback.txt", "")


def format_project_status(name: str) -> str:
    p = get_project(name)
    if not p:
        return f"❌ Project '{name}' not found"

    task = get_active_task(name) or "—"
    status = get_task_status(name) or p.get("status", "idle")
    worker = p.get("worker_session", "—")
    verifier = p.get("verifier_session", "—")

    status_icon = {
        "running": "🟢", "idle": "⚪", "paused": "🟡", "error": "🔴",
        "working": "🔵", "awaiting-review": "🟡", "awaiting-human": "🟠"
    }.get(status, "⚪")

    return (
        f"━━━ {name} ━━━\n"
        f"{status_icon} Status: {status}\n"
        f"📋 Task: {task}\n"
        f"🤖 Worker: {worker}\n"
        f"🔍 Verifier: {verifier}\n"
        f"📂 Type: {p.get('type', '—')}"
    )
