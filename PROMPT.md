# SRE Agent Building Loop

## Goal
Complete SRE Agent development to MVP release state.

## Context
- Read: IMPLEMENTATION_PLAN.md, AGENTS.md
- Project: ~/workspace/agent/projects/sre-agent
- Tech Stack: Python 3.11, FastAPI, React, TypeScript

## Current Status
- Backend: 5,358 lines Python ✅
- Frontend: 1,057 lines TypeScript ✅
- Tests: 100 passed ✅

## Rules
1. Pick the highest priority incomplete task from IMPLEMENTATION_PLAN.md
2. Investigate relevant code before changing
3. Implement the task
4. Run: `source .venv/bin/activate && ruff check . --fix && pytest tests/`
5. If tests pass: commit with clear message, mark task done in IMPLEMENTATION_PLAN.md
6. If tests fail: try to fix (max 3 attempts), then notify
7. Push to GitHub after each commit

## Notifications
When you need input or finish, use:
```bash
openclaw gateway wake --text "PREFIX: message" --mode now
```

Prefixes:
- `ERROR:` - Tests failing after 3 attempts
- `BLOCKED:` - Missing dependency or unclear spec
- `PROGRESS:` - Major milestone complete
- `DONE:` - All tasks complete

## Completion
When all tasks are done, add to IMPLEMENTATION_PLAN.md: `STATUS: COMPLETE`
Then notify with: `openclaw gateway wake --text "DONE: All tasks complete" --mode now`
