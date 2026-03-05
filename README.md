# Agent House

Agent House is a personal autonomous agent platform that lets you run multiple AI
agents across multiple projects, controlled entirely from a single Telegram bot.
Each project has a worker agent that does the work and a verifier agent that
reviews it. You act as the final human approver before any task is marked done.

# Agent House — Deployment Guide

## What's in this package

```
agent-house/
├── bootstrap.sh              ← Run on VPS first
├── init.py                   ← Run locally to create projects
├── agent-house-bot.service   ← systemd service (edit token/ID first)
├── bot/
│   ├── master_bot.py         ← Telegram bot
│   ├── agent_registry.py     ← Project management
│   ├── usage_tracker.py      ← Claude Max usage tracking
│   └── approval_handler.py   ← Watches for human review gates
├── scripts/
│   ├── worker_launcher.sh    ← Starts worker in tmux
│   ├── verifier_launcher.sh  ← Runs verifier
│   └── context_refresh.sh    ← 20-min refresh (runs via cron)
└── templates/
    ├── coding/CLAUDE.md
    ├── research/CLAUDE.md
    ├── marketing/CLAUDE.md
    └── trading/CLAUDE.md
```

---

## Step 1 — Upload to VPS

```bash
# From your local machine:
scp -r agent-house/ root@YOUR_VPS_IP:/tmp/agent-house
ssh root@YOUR_VPS_IP
```

## Step 2 — Run bootstrap on VPS

```bash
cd /tmp/agent-house
chmod +x bootstrap.sh scripts/*.sh
bash bootstrap.sh
```

This installs: Python 3, pip, tmux, git, Node.js, Claude Code CLI,
Python dependencies, and deploys all files to /opt/agent-bots/.

## Step 3 — Authenticate Claude Code CLI

```bash
# On VPS:
claude login
# Follow the browser link (copy to your local browser if needed)
```

## Step 4 — Create a Telegram bot

1. Message @BotFather on Telegram
2. Send `/newbot` and follow prompts
3. Copy the token it gives you

Get your Telegram user ID:

- Message @userinfobot on Telegram
- Copy the `Id:` value

## Step 5 — Configure the bot

```bash
# Edit the systemd service:
nano /etc/systemd/system/agent-house-bot.service

# Replace:
#   YOUR_BOT_TOKEN_HERE  →  your token from BotFather
#   YOUR_TELEGRAM_USER_ID  →  your numeric user ID

systemctl daemon-reload
systemctl enable --now agent-house-bot
systemctl status agent-house-bot
```

## Step 6 — Create your first project (local machine)

```bash
# On your local machine:
pip install paramiko

# Edit init.py — set VPS_HOST to your server IP
nano init.py

python3 init.py
# Follow the prompts
```

## Step 7 — Launch via Telegram

Open Telegram, find your bot, send:

```
/launch your-project-name
```

Then:

```
/status your-project-name
```

Watch it work:

```bash
# SSH into VPS and attach to worker session
tmux attach -t worker-your-project-name
# Detach: Ctrl+B then D
```

---

## Telegram Command Reference

| Command                     | What it does                 |
| --------------------------- | ---------------------------- |
| `/projects`                 | List all projects and status |
| `/launch <project>`         | Start worker agent           |
| `/stop <project>`           | Stop agents                  |
| `/stopall`                  | Kill all agents              |
| `/status <project>`         | Current task + agent health  |
| `/todo <project>`           | Show todo.txt                |
| `/inprogress <project>`     | Show current task            |
| `/log <project>`            | Show progress log            |
| `/approve <project>`        | Approve completed task       |
| `/reject <project> <notes>` | Send back with feedback      |
| `/usage`                    | Claude Max usage dashboard   |
| `@project do something`     | Send prompt to worker        |

---

## Troubleshooting

**Bot not responding:**

```bash
journalctl -u agent-house-bot -f
```

**Worker not starting:**

```bash
tmux list-sessions
/opt/agent-bots/worker_launcher.sh your-project
```

**Claude not authenticated:**

```bash
claude --version
claude login
```

**Check project registry:**

```bash
cat /opt/agent-bots/registry.json | python3 -m json.tool
```

**Check a project's control center:**

```bash
ls /home/projects/your-project/control-center/
cat /home/projects/your-project/control-center/in-progress.txt
```
