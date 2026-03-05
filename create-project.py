#!/usr/bin/env python3
"""
create-project.py — Agent House Project Init Wizard
Run this on your LOCAL machine.
It SSHes into your VPS and creates the full project structure.

Usage: python3 create-project.py
Requirements: pip install paramiko
pip install python-dotenv
Make sure to set VPS_HOST and VPS_USER in a .env file or export them in your environment. Example .env:
VPS_HOST=your.vps.ip.address
VPS_USER=root
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Config — edit these ───────────────────────────────────────────────────────
VPS_HOST = os.environ.get("VPS_HOST", "")
VPS_USER = os.environ.get("VPS_USER", "root")
VPS_SSH_KEY = "~/.ssh/id_rsa"     # path to your SSH private key
# ─────────────────────────────────────────────────────────────────────────────

PROJECTS_BASE = "/home/projects"
REGISTRY_PATH = "/opt/agent-bots/registry.json"
TEMPLATES_BASE = "/opt/agent-bots/templates"

try:
    import paramiko
except ImportError:
    print("Installing paramiko...")
    subprocess.run([sys.executable, "-m", "pip", "install", "paramiko"], check=True)
    import paramiko


def ssh_connect() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key_path = os.path.expanduser(VPS_SSH_KEY)
    client.connect(VPS_HOST, username=VPS_USER, password=input("SSH password: "))
    print(f"✓ Connected to {VPS_HOST}")
    return client


def run(client: paramiko.SSHClient, cmd: str, check=True) -> str:
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    exit_code = stdout.channel.recv_exit_status()
    if check and exit_code != 0 and err:
        print(f"  [stderr] {err}")
    return out


def write_remote(client: paramiko.SSHClient, path: str, content: str):
    """Write content to a remote file via heredoc."""
    import base64
    encoded = base64.b64encode(content.encode()).decode()
    run(client, f"echo '{encoded}' | base64 -d > {path}")


def prompt(question: str, default: str = "") -> str:
    if default:
        answer = input(f"  {question} [{default}]: ").strip()
        return answer if answer else default
    answer = input(f"  {question}: ").strip()
    return answer


def prompt_choice(question: str, choices: list) -> str:
    print(f"  {question}")
    for i, c in enumerate(choices, 1):
        print(f"    {i}. {c}")
    while True:
        answer = input(f"  Choice [1-{len(choices)}]: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        print("  Invalid choice.")


def main():
    print("\n" + "="*60)
    print("  AGENT HOUSE — Project Init Wizard")
    print("="*60 + "\n")

    # ── Gather project config ─────────────────────────────────
    print("Project Details:")
    name = prompt("Project name (lowercase, hyphens)", "my-project")
    name = name.lower().replace(" ", "-")

    project_type = prompt_choice("Project type", ["coding", "research", "marketing", "trading"])
    description = prompt("One-line description")

    stack = ""
    if project_type == "coding":
        stack = prompt("Tech stack", "Solidity, Foundry, Base")

    print("\nAgent Setup (both Claude Max — no API key needed):")
    print("  Worker:   Claude Max CLI (Sonnet)")
    print("  Verifier: Claude Max CLI (Opus)")

    print("\nLong-term Goals (press Enter twice when done):")
    goals = []
    while True:
        g = input(f"  Goal {len(goals)+1} (or Enter to finish): ").strip()
        if not g:
            break
        goals.append(g)

    print("\nFirst tasks for todo.txt (press Enter twice when done):")
    tasks = []
    task_num = 1
    while True:
        t = input(f"  [TASK-{task_num:03d}] (or Enter to finish): ").strip()
        if not t:
            break
        tasks.append(f"[TASK-{task_num:03d}] {t}")
        task_num += 1

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "-"*50)
    print(f"  Name:        {name}")
    print(f"  Type:        {project_type}")
    print(f"  Description: {description}")
    if stack:
        print(f"  Stack:       {stack}")
    print(f"  Goals:       {len(goals)}")
    print(f"  Tasks:       {len(tasks)}")
    print("-"*50)
    confirm = input("\nCreate project? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    # ── Connect to VPS ────────────────────────────────────────
    print(f"\nConnecting to {VPS_HOST}...")
    client = ssh_connect()

    # ── Create directory structure ────────────────────────────
    project_dir = f"{PROJECTS_BASE}/{name}"
    dirs = [
        f"{project_dir}/control-center",
        f"{project_dir}/outputs",
    ]
    if project_type == "coding":
        dirs.append(f"{project_dir}/codebase")
    if project_type == "trading":
        for sub in ["trade-thesis", "watchlist", "journal", "strategy"]:
            dirs.append(f"{project_dir}/outputs/{sub}")

    for d in dirs:
        run(client, f"mkdir -p {d}")
    print(f"✓ Directory structure created: {project_dir}")

    # ── Copy CLAUDE.md template ───────────────────────────────
    created_at = datetime.now().strftime("%Y-%m-%d")
    claude_md_src = run(client, f"cat {TEMPLATES_BASE}/{project_type}/CLAUDE.md")
    claude_md = (
        claude_md_src
        .replace("{{PROJECT_NAME}}", name)
        .replace("{{DESCRIPTION}}", description)
        .replace("{{STACK}}", stack)
        .replace("{{CREATED_AT}}", created_at)
    )
    write_remote(client, f"{project_dir}/control-center/CLAUDE.md", claude_md)
    run(client, f"chmod 444 {project_dir}/control-center/CLAUDE.md")
    print("✓ CLAUDE.md created (read-only)")

    # ── longterm-plan.txt ─────────────────────────────────────
    plan_content = f"# Long-term Plan — {name}\nCreated: {created_at}\n\n"
    plan_content += "## Goals\n"
    for i, g in enumerate(goals, 1):
        plan_content += f"{i}. {g}\n"
    plan_content += "\n## Milestones\n(Add milestones as the project evolves)\n"
    write_remote(client, f"{project_dir}/control-center/longterm-plan.txt", plan_content)
    print("✓ longterm-plan.txt created")

    # ── todo.txt ──────────────────────────────────────────────
    todo_content = "\n".join(tasks) + "\n" if tasks else "(No tasks yet)\n"
    write_remote(client, f"{project_dir}/control-center/todo.txt", todo_content)
    print("✓ todo.txt created")

    # ── Empty control files ───────────────────────────────────
    for fname in ["in-progress.txt", "completed-tasks.txt", "claude-progress.txt", "feedback.txt"]:
        write_remote(client, f"{project_dir}/control-center/{fname}", "")
    print("✓ Control files initialized")

    # ── feature-list.json (coding only) ──────────────────────
    if project_type == "coding":
        feature_list = []
        for i, t in enumerate(tasks, 1):
            feature_list.append({
                "id": f"F{i:03d}",
                "category": "functional",
                "description": t.split("] ", 1)[-1] if "] " in t else t,
                "steps": ["Implement", "Test", "Review"],
                "passes": False
            })
        write_remote(client,
            f"{project_dir}/control-center/feature-list.json",
            json.dumps(feature_list, indent=2)
        )
        print("✓ feature-list.json created")

    # ── trade-rules.txt (trading only) ───────────────────────
    if project_type == "trading":
        trade_rules = (
            "# Trade Rules — READ ONLY\n"
            "# These rules cannot be violated by the agent.\n\n"
            "POSITION_SIZING: Max 5% of portfolio per trade\n"
            "RISK_LIMIT: Max 2% loss per trade\n"
            "ALLOWED_ASSETS: BTC, ETH, SOL (add others manually)\n"
            "NO_LEVERAGE: Agent may not recommend leveraged positions\n"
            "EXECUTION: Agent does NOT execute trades. Research only.\n"
        )
        write_remote(client, f"{project_dir}/control-center/trade-rules.txt", trade_rules)
        run(client, f"chmod 444 {project_dir}/control-center/trade-rules.txt")
        print("✓ trade-rules.txt created (read-only)")

    # ── .mcp.json ─────────────────────────────────────────────
    mcp_config = {"mcpServers": {}}
    if project_type in ["research", "trading"]:
        mcp_config["mcpServers"]["web_search"] = {
            "command": "claude",
            "args": ["mcp", "serve", "web-search"],
            "env": {}
        }
    write_remote(client, f"{project_dir}/.mcp.json", json.dumps(mcp_config, indent=2))
    print("✓ .mcp.json created")

    # ── Register in registry.json ─────────────────────────────
    reg_json = run(client, f"cat {REGISTRY_PATH}")
    try:
        registry = json.loads(reg_json)
    except:
        registry = {"projects": []}

    registry["projects"] = [p for p in registry["projects"] if p["name"] != name]
    registry["projects"].append({
        "name": name,
        "type": project_type,
        "description": description,
        "stack": stack,
        "worker": {"provider": "claude-max", "model": "sonnet"},
        "verifier": {"provider": "claude-max", "model": "opus"},
        "status": "idle",
        "created_at": created_at,
        "worker_session": f"worker-{name}",
        "verifier_session": f"verifier-{name}"
    })
    write_remote(client, REGISTRY_PATH, json.dumps(registry, indent=2))
    print("✓ Registered in registry.json")

    # ── Git init (coding only) ────────────────────────────────
    if project_type == "coding":
        run(client, f"cd {project_dir}/codebase && git init && git commit --allow-empty -m 'init: Agent House project setup'")
        print("✓ Git repo initialized in codebase/")

    client.close()

    # ── Done ──────────────────────────────────────────────────
    print("\n" + "="*60)
    print(f"  ✅ Project '{name}' created!")
    print("="*60)
    print(f"\nProject dir: {project_dir}")
    print(f"\nNext steps:")
    print(f"  1. Make sure claude is logged in on VPS: ssh {VPS_USER}@{VPS_HOST} 'claude login'")
    print(f"  2. In Telegram, send: /launch {name}")
    print(f"  3. Watch it work: ssh {VPS_USER}@{VPS_HOST} 'tmux attach -t worker-{name}'")
    print()


if __name__ == "__main__":
    main()
