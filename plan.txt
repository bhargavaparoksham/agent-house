================================================================================
  AGENT HOUSE — PLAN
  Autonomous Multi-Agent Orchestration for Speedrunning Projects
  Built by Bhargav Aparoksham
  Version 1.0 | March 2026
================================================================================


────────────────────────────────────────────────────────────────────────────────
1. OVERVIEW
────────────────────────────────────────────────────────────────────────────────

Agent House is a personal autonomous agent platform that lets you run multiple AI
agents across multiple projects, controlled entirely from a single Telegram bot.
Each project has a worker agent that does the work and a verifier agent that
reviews it. You act as the final human approver before any task is marked done.

Core principles:
  - Google Drive is the human-readable source of truth
  - VPS is the working environment for all agents
  - Telegram is the only control interface you need
  - Every task requires human approval before completion
  - Context is refreshed every 20 minutes to maintain quality
  - Usage is tracked so you never hit limits unexpectedly


────────────────────────────────────────────────────────────────────────────────
2. INFRASTRUCTURE
────────────────────────────────────────────────────────────────────────────────

2.1 VPS (DigitalOcean)
  - Premium AMD, 8GB RAM, 4 vCPU (~$56/mo)
  - Ubuntu 24 LTS
  - Runs all agents, bots, and sync processes 24/7
  - tmux manages all agent sessions (persistent across SSH disconnects)
  - Location: /home/projects/[project-name]/

2.2 Google Drive
  - Human-readable mirror of all project state
  - Agents cannot write to Drive directly
  - A sync hook pushes VPS txt files → Drive after every agent write
  - You can open any project folder on your phone to see live status

2.3 GitHub
  - One repo per coding/solidity project
  - Auto-created during project init via GitHub API
  - Worker agent commits, creates branches, opens PRs
  - PRs are the deliverable for coding tasks (not merged until you approve)

2.4 Local Machine
  - Used only for project initialisation
  - You run init.py locally; it SSHes into VPS + calls Drive/GitHub APIs
  - Day-to-day control is entirely via Telegram


────────────────────────────────────────────────────────────────────────────────
3. PROJECT TYPES
────────────────────────────────────────────────────────────────────────────────

Four project types are supported. Each has a different folder structure,
template files, and agent behaviour.

3.1 CODING PROJECT
  - GitHub repo (auto-created, public or private)
  - Worker uses Claude Code CLI (Max plan) for full git/file/test tooling
  - Verifier uses Claude API (Opus) to review code quality
  - Tasks result in GitHub PRs
  - Foundry setup available for Solidity/DeFi projects
  - feature-list.json tracks all features with pass/fail status

3.2 RESEARCH PROJECT
  - No GitHub repo
  - Worker researches, writes, synthesises
  - Verifier checks accuracy, gaps, quality of reasoning
  - Tasks result in output documents in outputs/ folder
  - Supports web search via MCP

3.3 MARKETING PROJECT
  - No GitHub repo
  - Worker produces content: copy, campaigns, calendars, briefs
  - Verifier checks brand alignment, quality, completeness
  - Tasks result in content files in outputs/ folder

3.4 TRADING PROJECT
  - No GitHub repo
  - Worker researches trade setups, analyses market data, monitors
    on-chain activity, tracks positions, and produces trade briefs
  - Verifier reviews theses for logical consistency, risk/reward,
    and alignment with defined strategy rules
  - Supports web search + price data APIs via MCP
  - Tasks result in structured trade reports in outputs/ folder:
      -> trade-thesis/     per-trade research documents
      -> watchlist/        assets under monitoring with entry criteria
      -> journal/          post-trade review logs
      -> strategy/         evolving strategy rules and playbooks
  - trade-rules.txt in control-center defines hard rules the worker
    must never violate (position sizing, risk limits, allowed assets)
  - trade-rules.txt is read-only after init (chmod 444), same as CLAUDE.md
  - Agent does NOT execute trades. Output is research and recommendations
    only. All execution is manual by you.


────────────────────────────────────────────────────────────────────────────────
4. FOLDER STRUCTURE
────────────────────────────────────────────────────────────────────────────────

4.1 Google Drive Structure

  Google Drive/
  └── AgentHouse/
      ├── _registry.json                  ← master list of all projects
      ├── _usage.json                     ← global usage tracking
      └── projects/
          ├── [project-name]/
          │   ├── control-center/
          │   │   ├── CLAUDE.md           ← read-only after init (chmod 444)
          │   │   ├── longterm-plan.txt   ← high level goals, never auto-edited
          │   │   ├── todo.txt            ← pending tasks
          │   │   ├── in-progress.txt     ← active task + subtasks + status
          │   │   ├── completed-tasks.txt ← approved, done tasks
          │   │   ├── claude-progress.txt ← session-by-session agent log
          │   │   ├── feature-list.json   ← coding projects only
          │   │   └── feedback.txt        ← verifier writes, worker reads
          │   └── outputs/
          │       ├── [coding]   PRs documented here, final build notes
          │       ├── [research] final reports, summaries, PDFs
          │       ├── [marketing] copy files, calendars, campaign briefs
          │       └── [trading]  trade-thesis/, watchlist/, journal/, strategy/

4.2 VPS Structure (mirrors Drive)

  /home/projects/
  └── [project-name]/
      ├── control-center/                 ← synced from Drive on agent start
      │   ├── CLAUDE.md        (chmod 444, uneditable by agent)
      │   ├── longterm-plan.txt
      │   ├── todo.txt
      │   ├── in-progress.txt
      │   ├── completed-tasks.txt
      │   ├── claude-progress.txt
      │   ├── feature-list.json
      │   └── feedback.txt
      ├── codebase/                       ← git repo (coding projects only)
      │   └── [all project code]
      ├── outputs/                        ← research/marketing deliverables
      └── .mcp.json                       ← MCP server config

  /opt/agent-bots/
  ├── providers.json                      ← all API keys, global
  ├── registry.json                       ← all project configs
  ├── usage.json                          ← live usage tracking
  ├── master_bot.py                       ← Telegram control bot
  ├── worker_launcher.sh                  ← starts worker for a project
  ├── verifier_launcher.sh                ← starts verifier for a project
  ├── context_refresh.sh                  ← 20-min refresh cycle manager
  ├── sync_to_drive.sh                    ← pushes txt files to Drive
  └── venv/                              ← Python environment


────────────────────────────────────────────────────────────────────────────────
5. CONTROL CENTER FILES — DETAILED
────────────────────────────────────────────────────────────────────────────────

CLAUDE.md (READ-ONLY after init, chmod 444)
  The permanent brain of the project. Claude reads this every session.
  Contains: project description, stack, rules, what Claude can/cannot do,
  git conventions, testing requirements, approval rules, and escalation
  triggers. Never auto-edited. You edit it manually when project direction
  changes.

longterm-plan.txt
  High-level goals and milestones. Written by you at init, updated by you
  when direction changes. Agents read it for context but cannot modify it.

todo.txt
  List of pending tasks. Format:
    [TASK-001] Implement deposit() function
    [TASK-002] Write invariant tests for AssetPool
    [TASK-003] Research IFSCA sandbox eligibility criteria
  Tasks are written by you (or agent with your approval).

in-progress.txt
  The currently active task. When a task is picked up from todo.txt it
  moves here. Format:
    TASK: [TASK-001] Implement deposit() function
    STATUS: working | awaiting-review | awaiting-human
    ITERATION: 2/3
    SUBTASKS:
      [x] Write function signature
      [x] Implement transfer logic
      [ ] Write unit tests
      [ ] End-to-end test
    LAST-ACTION: Added ERC20 transfer call, tests pending
    BLOCKED: no

completed-tasks.txt
  Tasks approved by you. Append-only log. Format:
    [TASK-001] Implement deposit() function
    COMPLETED: 2026-03-05 14:32
    APPROVED-BY: human
    SUMMARY: Deposit function implemented with reentrancy guard, 12 tests passing
    PR: https://github.com/org/repo/pull/14
    ---

claude-progress.txt
  Written by agent at the end of every session and after every refresh.
  This is how a new session knows what the previous session did.
  Format:
    SESSION: 2026-03-05 14:00-14:20
    TASK: [TASK-001]
    DID: Implemented deposit function, added reentrancy guard
    NEXT: Write unit tests for edge cases
    BLOCKERS: None
    FILES-CHANGED: contracts/Vault.sol, test/Vault.t.sol
    ---

feature-list.json (coding projects only)
  Structured list of all features with pass/fail status. Agents update
  only the "passes" field. They cannot add or remove features.
  Example:
    {
      "id": "F001",
      "category": "functional",
      "description": "User can deposit ERC20 tokens",
      "steps": ["Call deposit()", "Check balance updated", "Check event emitted"],
      "passes": false
    }

feedback.txt
  Written by verifier after reviewing worker output. Worker reads this
  before each new iteration. Cleared after human approval.
  Format:
    ITERATION: 2
    VERDICT: needs-rework | approved | escalate-to-human
    ISSUES:
      - Missing reentrancy guard on withdraw()
      - Test coverage below 80%
      - Gas optimisation possible in loop at line 45
    SUGGESTIONS:
      - Use OpenZeppelin ReentrancyGuard
      - Add fuzz tests for amount parameter
    APPROVED-FOR-HUMAN: no


────────────────────────────────────────────────────────────────────────────────
6. AGENT CONFIGURATION
────────────────────────────────────────────────────────────────────────────────

6.1 Providers Supported

  Provider      Auth type         Agent runtime
  ──────────────────────────────────────────────────────────────
  claude-max    Max plan login    Claude Code CLI (tmux session)
  claude-api    API key           Claude Code CLI (--api-key flag)
  chatgpt       OpenAI API key    Python wrapper → OpenAI API
  gemini        Gemini API key    Python wrapper → Google AI API
  grok          xAI API key       Python wrapper → xAI API

  Note: ChatGPT Plus, X Premium+ and Gemini Advanced subscriptions
  cannot be used by agents. Only API keys work for non-Claude providers.

6.2 Per-Project Agent Assignment

  Each project has two agents: worker and verifier.
  Assigned at init, changeable via /setmodel command.

  Recommended defaults:
    Worker:   Claude Max plan, Sonnet  (full CLI, git, file tools)
    Verifier: Claude API key, Opus     (reviews output, cheaper per task)

  Any combination is valid:
    Worker:   Gemini API, gemini-2.0-flash
    Verifier: Claude API, Opus

6.3 Global API Key Storage

  Stored in /opt/agent-bots/providers.json on VPS.
  Set once during init, editable via Telegram /setkey command.
  Never stored per-project (projects reference global keys).

  {
    "claude_api_key": "sk-ant-...",
    "openai_api_key": "sk-...",
    "gemini_api_key": "AIza...",
    "grok_api_key": "xai-..."
  }


────────────────────────────────────────────────────────────────────────────────
7. THE DUAL-AGENT TASK LOOP
────────────────────────────────────────────────────────────────────────────────

This is how every task moves from todo to completed.

  STEP 1 — Task pickup
    Worker reads todo.txt, picks highest priority task
    Moves task from todo.txt → in-progress.txt (status: working)
    Reads CLAUDE.md + claude-progress.txt + feature-list.json for context

  STEP 2 — Worker implements
    Worker works on the task in subtask increments
    Commits code/writes files after each subtask (coding: git commit)
    Updates in-progress.txt subtask checkboxes as it goes
    Updates claude-progress.txt at the end of each 20-min session

  STEP 3 — Verifier reviews
    Triggered automatically after worker marks subtasks complete
    Verifier reads worker output + in-progress.txt
    Writes verdict to feedback.txt:
      needs-rework → worker reads feedback, iterates (max 3 rounds)
      approved     → escalates to human review
      escalate     → goes straight to human (major issue found)

  STEP 4 — Worker iterates (if needed)
    Worker reads feedback.txt, addresses each issue
    Max 3 worker/verifier iterations per task
    If still unresolved after 3 rounds → escalate to human automatically

  STEP 5 — Human review (you)
    Telegram bot sends you:
      - Task summary
      - What was built/written
      - Verifier's final verdict
      - For coding: PR link + test results
      - Inline buttons: ✅ Approve | 🔄 Rework | ❌ Reject
    You tap Approve → task moves to completed-tasks.txt
    You tap Rework → you type feedback → back to worker
    You tap Reject → task goes back to todo.txt with your notes

  STEP 6 — Completion
    Coding:    PR is marked ready for merge (you merge manually)
    Research:  Final doc moved to outputs/ folder + synced to Drive
    Marketing: Final content moved to outputs/ folder + synced to Drive
    Trading:   Trade thesis/journal entry moved to outputs/ + synced to Drive
    Worker picks next task from todo.txt


────────────────────────────────────────────────────────────────────────────────
8. CONTEXT REFRESH CYCLE
────────────────────────────────────────────────────────────────────────────────

Every 20 minutes each active agent is refreshed to prevent context
degradation. This is managed by context_refresh.sh running as a cron job.

  T+00:00  Agent session starts
           → reads CLAUDE.md + claude-progress.txt + in-progress.txt
           → begins work on current task

  T+00:20  Refresh fires
           → agent writes summary to claude-progress.txt
           → coding: commits any in-progress changes with [WIP] prefix
           → tmux session killed cleanly
           → new session starts immediately
           → opening context injected:

             "CONTEXT HANDOFF
              Previous session: 2026-03-05 14:00-14:20
              Task: [TASK-001] Implement deposit()
              Last action: Added transfer logic, tests pending
              Next step: Write unit tests for edge cases
              Blockers: None
              Read control-center/claude-progress.txt for full history."

           → agent continues exactly where previous session left off

  T+00:40  Next refresh...

The 20-minute window is a default. It can be adjusted per project
in the project registry (e.g. research projects may use 30 minutes).


────────────────────────────────────────────────────────────────────────────────
9. HUMAN-IN-THE-LOOP GATES
────────────────────────────────────────────────────────────────────────────────

There are four points where the agent pauses and waits for you.

GATE 1 — Task plan approval (before starting any task)
  Agent writes what it plans to do before touching any files.
  You approve or modify via Telegram before it begins.
  Bypass option: /autopilot [project] skips gate 1 for trusted agents.

GATE 2 — Ambiguous decision pause (during work)
  Triggers defined in CLAUDE.md. Examples:
    - Modifying any file matching contracts/*.sol
    - Adding a new dependency
    - Database schema changes
    - Making changes touching 5+ files
    - Confidence below 90%
  Agent writes question to in-progress.txt and waits.
  Bot notifies you. You reply via Telegram. Agent resumes.

GATE 3 — Task completion approval (after worker+verifier loop)
  After max 3 iterations, bot sends you task summary.
  Inline buttons: ✅ Approve | 🔄 Rework | ❌ Reject
  Approve → completed-tasks.txt
  Rework  → back to worker with your notes
  Reject  → back to todo.txt

GATE 4 — Error escalation (when stuck)
  After 3 failed iterations OR unresolvable blocker:
  Agent stops, commits current state to a branch,
  sends you a full error report via Telegram.
  You provide guidance or take over.


────────────────────────────────────────────────────────────────────────────────
10. USAGE TRACKING
────────────────────────────────────────────────────────────────────────────────

10.1 What Is Tracked

  Claude Max plan:
    - Message count per agent per session
    - Messages in last 5 hours (vs 225 limit)
    - Session count today
    - Estimated Opus hours used this week (vs 15-35hr limit)

  Claude API / ChatGPT / Gemini / Grok:
    - Input tokens per session
    - Output tokens per session
    - Estimated cost in USD
    - Daily and monthly totals

  All providers:
    - Session start/end times
    - Context refresh count
    - Agent (worker vs verifier)
    - Project name

10.2 Stored In

  /opt/agent-bots/usage.json   (live, updated in real time)
  Google Drive/AgentHouse/_usage.json  (synced daily)

10.3 Alerts

  80% of 5-hour window used  → Telegram warning, agents keep running
  90% of 5-hour window used  → Telegram alert, auto-pause all agents
  Opus weekly limit estimate  → Telegram warning when ~70% used
  API spend > $20/day         → Telegram alert

10.4 /usage Commands

  /usage              → global dashboard across all agents
  /usage [project]    → per-project breakdown
  /usage today        → today's totals only

  Example output:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━
    📊 Usage — Today
    ━━━━━━━━━━━━━━━━━━━━━━━━━━
    Claude Max 5-hr window:
      87/225 msgs used (39%)
      Resets in 3h 14m

    Opus weekly estimate:
      ~4.2hr used / 15-35hr cap

    API spend today:
      Claude API:  $1.20
      ChatGPT:     $0.45
      Gemini:      $0.12
      Total:       $1.77

    Per agent:
      solidity-worker    42 msgs
      research-worker    31 msgs
      marketing-worker   14 msgs
    ━━━━━━━━━━━━━━━━━━━━━━━━━━


────────────────────────────────────────────────────────────────────────────────
11. MASTER TELEGRAM BOT — FULL COMMAND MAP
────────────────────────────────────────────────────────────────────────────────

── Project Control ───────────────────────────────────────────────
  /projects                   list all projects + status
  /start [project]            start worker + verifier agents
  /stop [project]             stop both agents, save state
  /stopall                    kill all agents instantly
  /pauseall                   pause all, preserve state
  /resumeall                  resume all from saved state
  /status [project]           current task, last update, agent health
  /restart [project]          restart both agents

── Task Management ───────────────────────────────────────────────
  /todo [project]             show todo.txt
  /inprogress [project]       show current task + subtask status
  /log [project]              last 30 lines of claude-progress.txt
  /approve [project]          approve awaiting-human task
  /reject [project] [notes]   reject with feedback → back to worker
  /rework [project] [notes]   send back to worker with notes

── Agent Prompting ───────────────────────────────────────────────
  @[project] [prompt]         send prompt to worker agent
  Examples:
    @solidity fix reentrancy bug in Vault.sol
    @research summarise IFSCA sandbox eligibility
    @marketing write Q2 campaign brief for Own Finance

── Usage & Limits ────────────────────────────────────────────────
  /usage                      global usage dashboard
  /usage [project]            per-project usage breakdown
  /setkey [provider] [key]    update an API key

── Project Init ──────────────────────────────────────────────────
  /newproject                 launch interactive init wizard

── Model Control ─────────────────────────────────────────────────
  /setmodel [project] [role] [provider] [model]
  Example: /setmodel solidity worker claude-api opus

── Config ────────────────────────────────────────────────────────
  /autopilot [project] [on/off]   toggle gate 1 plan approval
  /refreshrate [project] [mins]   change context refresh interval


────────────────────────────────────────────────────────────────────────────────
12. PROJECT INITIALISATION FLOW
────────────────────────────────────────────────────────────────────────────────

Run locally: python init.py

  Step 1 — You answer prompts:
    Project name?               → own-finance-solidity
    Project type?               → coding / research / marketing
    Description?                → ERC20 tokenized equity on Base using Dinari
    Worker provider + model?    → claude-max / sonnet
    Verifier provider + model?  → claude-api / opus
    GitHub visibility?          → private  (coding only)
    First 3 longterm goals?     → [you type them]

  Step 2 — Script runs automatically:
    ✅ Creates GitHub repo via API (coding only)
    ✅ Creates Drive folder structure via Google Drive MCP
    ✅ Writes all template files with your inputs
    ✅ Sets CLAUDE.md to read-only (chmod 444)
    ✅ Creates VPS directory structure over SSH
    ✅ Clones GitHub repo into codebase/ (coding only)
    ✅ Installs Foundry if solidity project
    ✅ Registers project in _registry.json
    ✅ Confirms via terminal + sends Telegram message

  Step 3 — You can immediately:
    /start [project-name] in Telegram to launch agents
    @[project] give me an overview of the first task to begin


────────────────────────────────────────────────────────────────────────────────
13. BUILD PLAN — PHASES
────────────────────────────────────────────────────────────────────────────────

PHASE 1 — Foundation (build first)
  providers.py          provider registry, key management, API key storage
  usage_tracker.py      message count + token count per provider + alerts
  agent_registry.py     project config, read/write _registry.json
  drive_sync.sh         hook: after any .txt write on VPS → push to Drive

PHASE 2 — Init System
  init.py               interactive wizard: GitHub + Drive + VPS setup
  templates/
    coding/             CLAUDE.md, todo.txt, feature-list.json, feedback.txt
    research/           CLAUDE.md, todo.txt, research-brief.txt, feedback.txt
    marketing/          CLAUDE.md, todo.txt, content-calendar.txt, feedback.txt
    trading/            CLAUDE.md, todo.txt, trade-rules.txt, feedback.txt

PHASE 3 — Agent Runtime
  worker_launcher.sh    starts worker with correct provider + opening context
  verifier_launcher.sh  starts verifier, loads feedback loop prompt
  context_refresh.sh    cron-based 20-min refresh with handoff summary
  approval_handler.py   watches in-progress.txt, triggers human gate 3+4

PHASE 4 — Master Bot
  master_bot.py         all Telegram commands + inline approval buttons
  Integrates phases 1-3 into unified command interface

PHASE 5 — Usage Dashboard
  usage_dashboard.py    formats /usage reports for Telegram
  daily_report.sh       pushes daily usage summary to Drive
  alert_manager.py      fires Telegram alerts at 80%/90% thresholds


────────────────────────────────────────────────────────────────────────────────
14. DESIGN DECISIONS & RATIONALE
────────────────────────────────────────────────────────────────────────────────

Why VPS over local machine?
  Local machine sleeps, disconnects, restarts. VPS runs 24/7.
  Agents can work overnight and you wake up to completed tasks.

Why tmux instead of Docker?
  Simpler, less overhead, easy to attach and watch live.
  Docker adds complexity without meaningful isolation for 2-3 agents.

Why Claude Code CLI for Claude, not API wrapper?
  Claude Code CLI has built-in context compaction, git tooling,
  subagents, hooks, and checkpoints. Using raw API loses all of that.
  For GPT/Gemini/Grok there is no equivalent CLI, so Python wrapper
  is the only option.

Why Worker=Max plan, Verifier=API key?
  Worker needs full filesystem, git, and tool access → CLI.
  Verifier only reads output and writes feedback → cheaper API call.
  Saves Max plan quota for the heavy lifting.

Why feedback.txt instead of direct agent communication?
  Agents run in separate tmux sessions. They can't talk directly.
  A shared file is simple, transparent, and you can read it anytime.

Why chmod 444 on CLAUDE.md?
  Prevents agent from modifying its own instructions.
  You are always in control of the agent's behaviour.

Why JSON for feature-list, txt for everything else?
  Agents are less likely to accidentally overwrite or restructure JSON.
  Plain txt is human-readable and easy for you to edit directly.

Why 20-minute context refresh?
  Beyond ~20 minutes of agentic work, context quality degrades.
  Fresh sessions with a clear handoff summary outperform long degraded
  sessions. This is Anthropic's own recommendation from their
  long-running agent research.

Why single Telegram bot, not per-project bots?
  You plan to run 2-3 agents max. A single bot with @project routing
  is cleaner than juggling 6+ bot chats. Less cognitive overhead.


────────────────────────────────────────────────────────────────────────────────
15. LIMITATIONS & KNOWN CONSTRAINTS
────────────────────────────────────────────────────────────────────────────────

- Claude Max plan: 225 messages / 5-hour window, shared across all agents
  If 2 agents run simultaneously, budget ~110 messages each per window.

- Claude Opus weekly cap: ~15-35 hours. Verifier using Opus for every
  task review will consume this faster than expected. Monitor /usage weekly.

- Drive sync is one-way (VPS → Drive). You cannot edit files in Drive
  and have them sync back to VPS automatically. Edit VPS files directly
  or via Telegram /rework commands.

- Non-Claude agents (GPT, Gemini, Grok) via Python wrapper do not have
  native file/git tools. They are suitable for research and marketing
  projects but not recommended as workers on coding projects.

- Init script requires local machine to have Python 3.10+, SSH access
  to VPS, and Google account authenticated for Drive MCP.

- Context refresh loses the conversation thread. The handoff summary
  is a best-effort reconstruction, not a perfect memory. For complex
  multi-day tasks, keep CLAUDE.md and claude-progress.txt detailed.


────────────────────────────────────────────────────────────────────────────────
  END OF DOCUMENT — AGENT HOUSE v1.0
  Built by Bhargav Aparoksham
  Next step: Build Phase 1 (providers.py, usage_tracker.py,
  agent_registry.py, drive_sync.sh)
================================================================================
