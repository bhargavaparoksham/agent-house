"""
master_bot.py
Agent House — Master Telegram Control Bot
All project control, task approval, and agent prompting via Telegram.
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, '/opt/agent-bots')

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_CHAT_ID  = int(os.environ.get("ADMIN_CHAT_ID", "0"))  # Your Telegram user ID

BOT_STATE_PATH  = "/opt/agent-bots/bot_state.json"
REGISTRY_PATH   = "/opt/agent-bots/registry.json"
PROJECTS_BASE   = "/home/projects"
SCRIPTS_DIR     = "/opt/agent-bots"

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_CHAT_ID


def load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def save_registry(reg: dict):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(reg, f, indent=2)


def get_project(name: str) -> Optional[dict]:
    reg = load_registry()
    for p in reg["projects"]:
        if p["name"] == name:
            return p
    return None


def update_project(name: str, updates: dict):
    reg = load_registry()
    for p in reg["projects"]:
        if p["name"] == name:
            p.update(updates)
    save_registry(reg)


def read_file(project: str, filename: str) -> str:
    path = Path(PROJECTS_BASE) / project / "control-center" / filename
    if path.exists():
        return path.read_text().strip()
    return f"(file not found: {filename})"


def write_file(project: str, filename: str, content: str):
    path = Path(PROJECTS_BASE) / project / "control-center" / filename
    path.write_text(content)


def run_script(script: str, *args) -> Tuple[int, str]:
    cmd = [f"{SCRIPTS_DIR}/{script}"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    return result.returncode, output.strip()


def tmux_send(session: str, message: str):
    subprocess.run(["tmux", "send-keys", "-t", session, message, "Enter"])


def session_alive(session: str) -> bool:
    r = subprocess.run(["tmux", "has-session", "-t", session],
                       capture_output=True)
    return r.returncode == 0


def load_bot_state() -> dict:
    if Path(BOT_STATE_PATH).exists():
        with open(BOT_STATE_PATH) as f:
            return json.load(f)
    return {"pending_approvals": {}}


def save_bot_state(state: dict):
    with open(BOT_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


async def require_admin(update: Update) -> bool:
    if not is_admin(update):
        await update.message.reply_text("⛔ Unauthorized.")
        return False
    return True


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🦾 *Agent House* is online.\n\n"
        "Commands:\n"
        "`/projects` — list all projects\n"
        "`/start <project>` — start agents\n"
        "`/stop <project>` — stop agents\n"
        "`/status <project>` — current state\n"
        "`/todo <project>` — pending tasks\n"
        "`/inprogress <project>` — active task\n"
        "`/log <project>` — progress log\n"
        "`/approve <project>` — approve task\n"
        "`/reject <project> <notes>` — reject task\n"
        "`/usage` — usage dashboard\n"
        "`@<project> <prompt>` — send prompt to worker",
        parse_mode="Markdown"
    )


async def cmd_projects(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    reg = load_registry()
    if not reg["projects"]:
        await update.message.reply_text("No projects yet. Run `init.py` locally.")
        return

    lines = []
    for p in reg["projects"]:
        status = p.get("status", "idle")
        icon = {"running": "🟢", "idle": "⚪", "paused": "🟡", "error": "🔴"}.get(status, "⚪")
        w_alive = "✓" if session_alive(f"worker-{p['name']}") else "✗"
        v_alive = "✓" if session_alive(f"verifier-{p['name']}") else "✗"
        lines.append(f"{icon} `{p['name']}` ({p['type']}) W:{w_alive} V:{v_alive}")

    await update.message.reply_text(
        "📂 *Projects*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )


async def cmd_start_project(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/start <project>`", parse_mode="Markdown")
        return

    project = args[0]
    p = get_project(project)
    if not p:
        await update.message.reply_text(f"❌ Project `{project}` not found.", parse_mode="Markdown")
        return

    await update.message.reply_text(f"🚀 Starting agents for `{project}`...", parse_mode="Markdown")

    # Launch worker
    rc, out = run_script("worker_launcher.sh", project)
    if rc != 0:
        await update.message.reply_text(f"❌ Worker failed:\n```{out[:400]}```", parse_mode="Markdown")
        return

    update_project(project, {"status": "running", "started_at": datetime.now().isoformat()})

    # Save chat_id for notifications
    state = load_bot_state()
    state["admin_chat_id"] = str(update.effective_chat.id)
    state["telegram_token"] = TELEGRAM_TOKEN
    save_bot_state(state)

    await update.message.reply_text(
        f"✅ Worker started for `{project}`\n"
        f"Session: `worker-{project}`\n\n"
        f"Verifier will auto-launch after task completion.",
        parse_mode="Markdown"
    )


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/stop <project>`", parse_mode="Markdown")
        return

    project = args[0]
    for role in ["worker", "verifier"]:
        session = f"{role}-{project}"
        if session_alive(session):
            subprocess.run(["tmux", "kill-session", "-t", session])

    update_project(project, {"status": "idle"})
    await update.message.reply_text(f"⛔ Agents stopped for `{project}`.", parse_mode="Markdown")


async def cmd_stopall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    reg = load_registry()
    stopped = []
    for p in reg["projects"]:
        name = p["name"]
        for role in ["worker", "verifier"]:
            session = f"{role}-{name}"
            if session_alive(session):
                subprocess.run(["tmux", "kill-session", "-t", session])
                stopped.append(session)
        update_project(name, {"status": "idle"})

    if stopped:
        await update.message.reply_text(f"⛔ Stopped: {', '.join(stopped)}")
    else:
        await update.message.reply_text("No active sessions found.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/status <project>`", parse_mode="Markdown")
        return

    project = args[0]
    p = get_project(project)
    if not p:
        await update.message.reply_text(f"❌ Project `{project}` not found.")
        return

    in_progress = read_file(project, "in-progress.txt") or "Nothing in progress"
    feedback = read_file(project, "feedback.txt")
    w_alive = "🟢 running" if session_alive(f"worker-{project}") else "🔴 stopped"
    v_alive = "🟢 running" if session_alive(f"verifier-{project}") else "⚪ idle"

    msg = (
        f"📊 *{project}* status\n\n"
        f"Worker: {w_alive}\n"
        f"Verifier: {v_alive}\n\n"
        f"*In Progress:*\n```\n{in_progress[:500]}\n```"
    )
    if feedback:
        msg += f"\n*Verifier Feedback:*\n```\n{feedback[:300]}\n```"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_todo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/todo <project>`", parse_mode="Markdown")
        return
    project = args[0]
    content = read_file(project, "todo.txt") or "(empty)"
    await update.message.reply_text(
        f"📋 *{project}* — todo.txt\n```\n{content[:1500]}\n```",
        parse_mode="Markdown"
    )


async def cmd_inprogress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/inprogress <project>`", parse_mode="Markdown")
        return
    project = args[0]
    content = read_file(project, "in-progress.txt") or "(empty)"
    await update.message.reply_text(
        f"🔵 *{project}* — in-progress.txt\n```\n{content[:1500]}\n```",
        parse_mode="Markdown"
    )


async def cmd_log(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/log <project>`", parse_mode="Markdown")
        return
    project = args[0]
    path = Path(PROJECTS_BASE) / project / "control-center" / "claude-progress.txt"
    if not path.exists():
        await update.message.reply_text("No progress log yet.")
        return
    lines = path.read_text().splitlines()
    tail = "\n".join(lines[-40:])
    await update.message.reply_text(
        f"📜 *{project}* — progress log (last 40 lines)\n```\n{tail[:1800]}\n```",
        parse_mode="Markdown"
    )


async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/approve <project>`", parse_mode="Markdown")
        return
    project = args[0]
    await _approve_task(update, project)


async def _approve_task(update: Update, project: str):
    from agent_registry import complete_task, get_active_task
    task = get_active_task(project) or "Unknown task"
    complete_task(project, summary=f"Approved via Telegram at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    update_project(project, {"status": "running"})

    await update.message.reply_text(
        f"✅ Task approved for `{project}`\n`{task}` → completed\n\n"
        f"Worker will pick next task from todo.txt.",
        parse_mode="Markdown"
    )

    # Restart worker for next task
    run_script("worker_launcher.sh", project)


async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: `/reject <project> <your feedback>`", parse_mode="Markdown")
        return
    project = args[0]
    notes = " ".join(args[1:])
    await _reject_task(update, project, notes)


async def _reject_task(update: Update, project: str, notes: str):
    # Write feedback and send back to worker
    existing = read_file(project, "feedback.txt")
    iteration = 1
    for line in existing.splitlines():
        if line.startswith("ITERATION:"):
            try:
                iteration = int(line.split(":")[1].strip()) + 1
            except:
                pass

    feedback = (
        f"ITERATION: {iteration}\n"
        f"VERDICT: needs-rework\n"
        f"ISSUES:\n  - {notes}\n"
        f"SUGGESTIONS:\n  - Address the above and resubmit\n"
        f"APPROVED-FOR-HUMAN: no\n"
    )
    write_file(project, "feedback.txt", feedback)

    # Update task status
    from agent_registry import set_task_status
    set_task_status(project, "working")

    # Restart worker with feedback
    run_script("worker_launcher.sh", project)

    await update.message.reply_text(
        f"🔄 Sent back to worker for `{project}`\nFeedback: _{notes}_",
        parse_mode="Markdown"
    )


async def cmd_usage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update): return
    from usage_tracker import get_usage_report
    report = get_usage_report()
    await update.message.reply_text(f"```\n{report}\n```", parse_mode="Markdown")


# ── @project prompt routing ───────────────────────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    text = update.message.text or ""

    # Check for @project routing: "@projectname do something"
    if text.startswith("@"):
        parts = text.split(" ", 1)
        project = parts[0][1:]  # strip @
        prompt = parts[1] if len(parts) > 1 else ""

        p = get_project(project)
        if not p:
            await update.message.reply_text(f"❌ Project `{project}` not found.", parse_mode="Markdown")
            return

        session = f"worker-{project}"
        if not session_alive(session):
            await update.message.reply_text(
                f"⚠️ Worker session for `{project}` is not running.\n"
                f"Start it with `/start {project}`", parse_mode="Markdown")
            return

        # Send prompt to running tmux session
        tmux_send(session, prompt)
        await update.message.reply_text(
            f"✉️ Sent to `{project}` worker:\n_{prompt}_",
            parse_mode="Markdown"
        )
        return

    # Check pending approvals
    state = load_bot_state()
    pending = state.get("pending_approvals", {})
    if pending:
        # Remind about pending approvals
        projects = list(pending.keys())
        await update.message.reply_text(
            f"⏳ Pending approvals: {', '.join(projects)}\n"
            f"Use `/approve <project>` or `/reject <project> <notes>`"
        )


# ── Callback: inline approval buttons ────────────────────────────────────────

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # format: "approve:project" or "reject:project" or "rework:project"

    if ":" not in data:
        return

    action, project = data.split(":", 1)

    if action == "approve":
        await _approve_task(update, project)
        await query.edit_message_text(f"✅ Approved: `{project}`", parse_mode="Markdown")

    elif action == "rework":
        await query.edit_message_text(
            f"Type your feedback:\n`/reject {project} <your notes>`",
            parse_mode="Markdown"
        )

    elif action == "reject":
        from agent_registry import get_active_task, set_task_status
        task = get_active_task(project) or "task"
        # Move back to todo
        todo_content = read_file(project, "todo.txt")
        write_file(project, "todo.txt", f"{task} [REJECTED]\n" + todo_content)
        write_file(project, "in-progress.txt", "")
        set_task_status(project, "")
        update_project(project, {"status": "idle"})
        await query.edit_message_text(f"❌ Task rejected for `{project}`. Moved back to todo.", parse_mode="Markdown")


# ── Pending approval checker ──────────────────────────────────────────────────

async def check_pending_approvals(ctx: ContextTypes.DEFAULT_TYPE):
    """Job that fires Telegram notifications for pending human reviews."""
    state = load_bot_state()
    pending = state.get("pending_approvals", {})
    if not pending:
        return

    for project, approval in list(pending.items()):
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{project}"),
                InlineKeyboardButton("🔄 Rework", callback_data=f"rework:{project}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject:{project}"),
            ]
        ])
        msg = approval.get("message", f"Task ready for review: {project}")
        try:
            await ctx.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=msg[:4000],
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"[bot] Failed to send approval notification: {e}")

        # Remove from pending
        del pending[project]

    state["pending_approvals"] = pending
    save_bot_state(state)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: Set TELEGRAM_TOKEN environment variable.")
        sys.exit(1)
    if ADMIN_CHAT_ID == 0:
        print("ERROR: Set ADMIN_CHAT_ID environment variable.")
        sys.exit(1)

    # Save config for approval_handler
    state = load_bot_state()
    state["telegram_token"] = TELEGRAM_TOKEN
    state["admin_chat_id"] = str(ADMIN_CHAT_ID)
    save_bot_state(state)

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("todo", cmd_todo))
    app.add_handler(CommandHandler("inprogress", cmd_inprogress))
    app.add_handler(CommandHandler("log", cmd_log))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("usage", cmd_usage))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("stopall", cmd_stopall))

    # Override /start for project (conflicts with bot /start)
    app.add_handler(CommandHandler("launch", cmd_start_project))  # /launch <project>

    # Inline callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Free-text (@project routing + pending alerts)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Pending approval checker — runs every 15 seconds
    app.job_queue.run_repeating(check_pending_approvals, interval=15, first=5)

    print(f"[bot] Agent House bot started. Admin: {ADMIN_CHAT_ID}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
