#!/bin/bash
# ============================================================
# Agent House — VPS Bootstrap Script
# Run once on a fresh DigitalOcean Ubuntu 24 VPS
# Usage: bash bootstrap.sh
# ============================================================

set -e
BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
RESET="\033[0m"

info()    { echo -e "${GREEN}[✓]${RESET} $1"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $1"; }
section() { echo -e "\n${BOLD}━━━ $1 ━━━${RESET}"; }

section "System Update"
apt-get update -qq && apt-get upgrade -y -qq
info "System updated"

section "Core Dependencies"
apt-get install -y -qq \
  python3 python3-pip python3-venv \
  tmux git curl wget jq \
  build-essential
info "Core packages installed"

section "Node.js (for Claude Code CLI)"
if ! command -v node &>/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - -qq
  apt-get install -y -qq nodejs
  info "Node.js $(node --version) installed"
else
  info "Node.js already installed: $(node --version)"
fi

section "Claude Code CLI"
if ! command -v claude &>/dev/null; then
  npm install -g @anthropic-ai/claude-code
  info "Claude Code CLI installed"
else
  info "Claude Code CLI already installed"
fi

section "Directory Structure"
mkdir -p /opt/agent-bots/templates/{coding,research,marketing,trading}
mkdir -p /home/projects
chmod 755 /home/projects
info "Directories created"

section "Python Environment"
python3 -m venv /opt/agent-bots/venv
/opt/agent-bots/venv/bin/pip install -q --upgrade pip
/opt/agent-bots/venv/bin/pip install -q \
  python-telegram-bot==20.7 \
  watchdog==4.0.0 \
  aiofiles==23.2.1 \
  python-dateutil==2.8.2
info "Python venv ready at /opt/agent-bots/venv"

section "Core Config Files"

# providers.json — Claude Max only (no API keys needed)
cat > /opt/agent-bots/providers.json << 'EOF'
{
  "claude_max": {
    "type": "claude-max",
    "auth": "cli",
    "notes": "Authenticated via: claude login"
  },
  "claude_api_key": "",
  "openai_api_key": "",
  "gemini_api_key": "",
  "grok_api_key": ""
}
EOF
info "providers.json created"

# registry.json — starts empty
cat > /opt/agent-bots/registry.json << 'EOF'
{
  "projects": []
}
EOF
info "registry.json created"

# usage.json — starts zeroed
cat > /opt/agent-bots/usage.json << 'EOF'
{
  "sessions": [],
  "daily_totals": {},
  "alerts_fired": []
}
EOF
info "usage.json created"

section "Copying Agent House Files"
# Copy all scripts and bot files from current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/bot/"*.py /opt/agent-bots/
cp "$SCRIPT_DIR/scripts/"*.sh /opt/agent-bots/
cp -r "$SCRIPT_DIR/templates/"* /opt/agent-bots/templates/
chmod +x /opt/agent-bots/*.sh

info "Agent House files deployed"

section "Cron Job — Context Refresh"
CRON_JOB="*/20 * * * * /opt/agent-bots/context_refresh.sh >> /var/log/agent-house-refresh.log 2>&1"
(crontab -l 2>/dev/null | grep -v context_refresh; echo "$CRON_JOB") | crontab -
info "Context refresh cron set (every 20 min)"

section "Systemd Service — Telegram Bot"
cat > /etc/systemd/system/agent-house-bot.service << 'EOF'
[Unit]
Description=Agent House Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/agent-bots
ExecStart=/opt/agent-bots/venv/bin/python3 /opt/agent-bots/master_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
info "Systemd service created (not started yet — needs TELEGRAM_TOKEN)"

section "Log Files"
touch /var/log/agent-house-refresh.log
touch /var/log/agent-house-bot.log
info "Log files created"

section "Claude Login"
warn "You must authenticate Claude Code CLI before starting agents."
warn "Run:  claude login"
warn "This opens a browser — use SSH port forwarding or run on local machine first."

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD} Bootstrap complete!${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo "Next steps:"
echo "  1. claude login                          (authenticate Claude Max)"
echo "  2. Add TELEGRAM_TOKEN to master_bot.py"
echo "  3. systemctl enable --now agent-house-bot"
echo "  4. Run init.py on your LOCAL machine to create first project"
echo ""
