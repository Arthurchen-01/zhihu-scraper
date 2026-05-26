---
name: zhihu-freeze-maintenance
description: Use when maintaining this repository after v3.0.1-final, deciding scope, rejecting broad rewrites, or preparing a small stabilization change.
---

# Freeze Maintenance

## Workflow

1. Read `CONSTITUTION.md` and `AGENTS.md` first.
2. Treat `v3.0.1-final` as a maintenance freeze: preserve existing local-first behavior before adding scope.
3. Prefer small closed-loop fixes for install, docs, command surface, local data readability, and clear bugs.
4. Do not expand supported Zhihu surfaces unless the user explicitly asks and tests/docs can cover the new contract.
5. Record unresolved ambiguity in the task report instead of adding duplicate docs or placeholder modules.

## Default Validation

Run the smallest relevant unittest slice plus command smoke checks when touching commands, config, install, TUI, or docs.
