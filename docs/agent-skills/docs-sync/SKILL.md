---
name: zhihu-docs-sync
description: Use when updating README, README_EN, CONSTITUTION, AGENTS, install docs, command examples, or governance wording.
---

# Docs Sync

## Responsibilities

- `CONSTITUTION.md`: highest project identity, invariants, architecture guardrails, and quality gates.
- `AGENTS.md`: shared agent workflow and task reporting rules.
- `README.md` and `README_EN.md`: external user entry, quick start, concise command overview, and core value.
- `docs/agent-skills/`: task-specific project skills for future agents.

## Guardrails

Do not turn README into an internal manual. When details are agent-only, put them in `AGENTS.md` or an appropriate project skill.

## Validation

Run `python -m unittest -q tests.test_docs_sync tests.test_command_surface tests.test_install_contract` for docs or command wording edits.
