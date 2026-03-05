#!/bin/bash
# ============================================================
# context_refresh.sh
# Runs every 20 min via cron. For each running project,
# gracefully refreshes worker session with handoff context.
# ============================================================

LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')] context_refresh:"
REGISTRY="/opt/agent-bots/registry.json"

log() { echo "$LOG_PREFIX $1"; }

# Get all running projects
RUNNING_PROJECTS=$(/opt/agent-bots/venv/bin/python3 -c "
import json
with open('$REGISTRY') as f:
    reg = json.load(f)
for p in reg['projects']:
    if p.get('status') == 'running':
        print(p['name'])
" 2>/dev/null)

if [ -z "$RUNNING_PROJECTS" ]; then
  log "No running projects. Exiting."
  exit 0
fi

for PROJECT in $RUNNING_PROJECTS; do
  SESSION_NAME="worker-$PROJECT"
  CONTROL_DIR="/home/projects/$PROJECT/control-center"

  log "Refreshing: $PROJECT"

  # ── Check if worker session is actually alive ──────────────
  if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    log "Session $SESSION_NAME not found — relaunching"
    /opt/agent-bots/worker_launcher.sh "$PROJECT"
    continue
  fi

  # ── Send handoff summary request to running session ────────
  HANDOFF_MSG="
--- CONTEXT REFRESH (20-min checkpoint) ---
Before this session ends:
1. Write a summary of what you did to control-center/claude-progress.txt in the format:
   SESSION: $(date '+%Y-%m-%d %H:%M')-$(date -d '+20 minutes' '+%H:%M')
   TASK: [current task ID]
   DID: [what you completed]
   NEXT: [exactly what to do next]
   BLOCKERS: [any blockers, or None]
   FILES-CHANGED: [files you modified]
   ---
2. For coding projects: git commit any WIP changes with prefix [WIP]
3. Update STATUS in in-progress.txt
4. Then stop — a new session will continue your work.
"

  tmux send-keys -t "$SESSION_NAME" "$HANDOFF_MSG" Enter
  log "Handoff message sent to $SESSION_NAME"

  # ── Wait 60s for agent to write progress, then restart ─────
  sleep 60

  # Kill old session
  tmux kill-session -t "$SESSION_NAME" 2>/dev/null
  log "Killed session: $SESSION_NAME"

  # Check if task status warrants running verifier
  TASK_STATUS=$(/opt/agent-bots/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/agent-bots')
from agent_registry import get_task_status
print(get_task_status('$PROJECT') or 'working')
" 2>/dev/null)

  if [ "$TASK_STATUS" = "awaiting-review" ]; then
    log "Task awaiting review — launching verifier for $PROJECT"
    /opt/agent-bots/verifier_launcher.sh "$PROJECT"
  elif [ "$TASK_STATUS" = "awaiting-human" ]; then
    log "Task awaiting human approval — notifying via bot"
    /opt/agent-bots/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/agent-bots')
from approval_handler import notify_human_review
notify_human_review('$PROJECT')
" 2>/dev/null
  else
    # Restart worker with refreshed context
    sleep 2
    /opt/agent-bots/worker_launcher.sh "$PROJECT"
    log "Worker restarted for $PROJECT"
  fi

  # Log refresh
  /opt/agent-bots/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/agent-bots')
from usage_tracker import log_refresh
import os
sid_file = '/tmp/worker-session-id-$PROJECT.txt'
if os.path.exists(sid_file):
    with open(sid_file) as f:
        log_refresh(f.read().strip())
" 2>/dev/null

done

log "Refresh cycle complete."
