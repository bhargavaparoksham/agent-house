#!/bin/bash
# ============================================================
# worker_launcher.sh
# Starts a Claude Code worker session in a named tmux session.
# Usage: ./worker_launcher.sh <project_name>
# ============================================================

PROJECT="$1"
if [ -z "$PROJECT" ]; then
  echo "Usage: $0 <project_name>"
  exit 1
fi

PROJECT_DIR="/home/projects/$PROJECT"
CONTROL_DIR="$PROJECT_DIR/control-center"
SESSION_NAME="worker-$PROJECT"

# ── Validate project exists ──────────────────────────────────
if [ ! -d "$PROJECT_DIR" ]; then
  echo "ERROR: Project directory not found: $PROJECT_DIR"
  exit 1
fi

# ── Kill existing session if running ────────────────────────
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "Stopping existing worker session: $SESSION_NAME"
  tmux kill-session -t "$SESSION_NAME"
  sleep 1
fi

# ── Build opening context prompt ────────────────────────────
PROGRESS=$(tail -40 "$CONTROL_DIR/claude-progress.txt" 2>/dev/null || echo "No previous progress logged.")
IN_PROGRESS=$(cat "$CONTROL_DIR/in-progress.txt" 2>/dev/null || echo "Nothing in progress.")
TODO=$(cat "$CONTROL_DIR/todo.txt" 2>/dev/null || echo "No tasks in todo.")
FEEDBACK=$(cat "$CONTROL_DIR/feedback.txt" 2>/dev/null || echo "")

# Build opening prompt
OPENING_PROMPT="You are the WORKER agent for project: $PROJECT

CONTEXT HANDOFF
Read CLAUDE.md in this directory carefully — it contains your permanent instructions.

CURRENT STATE:
$(echo "$IN_PROGRESS")

RECENT PROGRESS LOG:
$(echo "$PROGRESS")

TODO LIST:
$(echo "$TODO")"

if [ -n "$FEEDBACK" ] && [ "$FEEDBACK" != "" ]; then
  OPENING_PROMPT="$OPENING_PROMPT

VERIFIER FEEDBACK (address this):
$(echo "$FEEDBACK")"
fi

OPENING_PROMPT="$OPENING_PROMPT

Begin by reading CLAUDE.md, then continue your work on the current task (or pick the next task from todo.txt if nothing is in progress). Update in-progress.txt and claude-progress.txt as you work."

# ── Write prompt to temp file ────────────────────────────────
PROMPT_FILE="/tmp/worker-prompt-$PROJECT.txt"
echo "$OPENING_PROMPT" > "$PROMPT_FILE"

# ── Start tmux session ───────────────────────────────────────
echo "Starting worker session: $SESSION_NAME"
tmux new-session -d -s "$SESSION_NAME" -x 220 -y 50

# Set working directory
tmux send-keys -t "$SESSION_NAME" "cd $PROJECT_DIR" Enter
sleep 0.5

# Launch Claude Code with context
tmux send-keys -t "$SESSION_NAME" "claude --dangerously-skip-permissions < $PROMPT_FILE" Enter

# ── Log session start ────────────────────────────────────────
/opt/agent-bots/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/agent-bots')
from usage_tracker import log_session_start
sid = log_session_start('$PROJECT', 'worker')
print(f'Session logged: {sid}')
# Write session ID for later reference
with open('/tmp/worker-session-id-$PROJECT.txt', 'w') as f:
    f.write(sid)
"

echo "Worker launched in tmux session: $SESSION_NAME"
echo "Attach with: tmux attach -t $SESSION_NAME"
