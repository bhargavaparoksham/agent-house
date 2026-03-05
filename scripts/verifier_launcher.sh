#!/bin/bash
# ============================================================
# verifier_launcher.sh
# Runs Claude Code in non-interactive mode to review worker output.
# Writes structured verdict to feedback.txt.
# Usage: ./verifier_launcher.sh <project_name>
# ============================================================

PROJECT="$1"
if [ -z "$PROJECT" ]; then
  echo "Usage: $0 <project_name>"
  exit 1
fi

PROJECT_DIR="/home/projects/$PROJECT"
CONTROL_DIR="$PROJECT_DIR/control-center"
SESSION_NAME="verifier-$PROJECT"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "ERROR: Project directory not found: $PROJECT_DIR"
  exit 1
fi

# ── Kill existing verifier session if running ───────────────
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "$SESSION_NAME"
  sleep 1
fi

# ── Gather context for verifier ─────────────────────────────
CLAUDE_MD=$(cat "$CONTROL_DIR/CLAUDE.md" 2>/dev/null || echo "")
IN_PROGRESS=$(cat "$CONTROL_DIR/in-progress.txt" 2>/dev/null || echo "")
PROGRESS_LOG=$(tail -30 "$CONTROL_DIR/claude-progress.txt" 2>/dev/null || echo "")

# Get project type from registry
PROJECT_TYPE=$(/opt/agent-bots/venv/bin/python3 -c "
import json
with open('/opt/agent-bots/registry.json') as f:
    reg = json.load(f)
for p in reg['projects']:
    if p['name'] == '$PROJECT':
        print(p.get('type', 'research'))
        break
" 2>/dev/null || echo "research")

# ── Build verifier prompt ────────────────────────────────────
VERIFIER_PROMPT="You are the VERIFIER agent for project: $PROJECT (type: $PROJECT_TYPE)

Your job is to review the worker's output and write a structured verdict to control-center/feedback.txt.

=== PROJECT RULES (CLAUDE.md) ===
$CLAUDE_MD

=== CURRENT TASK (in-progress.txt) ===
$IN_PROGRESS

=== WORKER'S PROGRESS LOG ===
$PROGRESS_LOG

=== YOUR TASK ===
Review the worker's output carefully. Check:
1. Does it fulfil the task requirements in CLAUDE.md?
2. For coding: Are there tests? Is the code secure and clean?
3. For research: Is it accurate, complete, well-sourced?
4. For marketing: Is it on-brand and complete?
5. For trading: Does it respect trade-rules.txt?

Then write your verdict to control-center/feedback.txt in EXACTLY this format:

ITERATION: [current iteration number, check feedback.txt for previous]
VERDICT: needs-rework OR approved OR escalate-to-human
ISSUES:
  - [list each issue, or 'None' if approved]
SUGGESTIONS:
  - [concrete fixes, or 'None' if approved]
APPROVED-FOR-HUMAN: yes OR no

Write ONLY the feedback.txt content above. Do not produce any other output. After writing feedback.txt, stop."

# ── Write prompt to temp file ────────────────────────────────
VERIFIER_PROMPT_FILE="/tmp/verifier-prompt-$PROJECT.txt"
echo "$VERIFIER_PROMPT" > "$VERIFIER_PROMPT_FILE"

# ── Run verifier in tmux session ─────────────────────────────
echo "Starting verifier session: $SESSION_NAME"
tmux new-session -d -s "$SESSION_NAME" -x 220 -y 50
tmux send-keys -t "$SESSION_NAME" "cd $PROJECT_DIR" Enter
sleep 0.5
tmux send-keys -t "$SESSION_NAME" "claude --dangerously-skip-permissions -p \"$(cat $VERIFIER_PROMPT_FILE)\"" Enter

# ── Log session ──────────────────────────────────────────────
/opt/agent-bots/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/agent-bots')
from usage_tracker import log_session_start
log_session_start('$PROJECT', 'verifier')
"

echo "Verifier launched in session: $SESSION_NAME"
echo "Watch feedback.txt for verdict:"
echo "  watch cat $CONTROL_DIR/feedback.txt"
