---
name: zhihu-tui-maintenance
description: Use when modifying the Textual TUI workbench, language selector, queue/history/retry states, TUI runner, or bare zhihu interactive behavior.
---

# TUI Maintenance

## Guardrails

- Bare `zhihu` and `zhihu interactive` should continue to launch the recommended Textual TUI.
- Keep user-facing workflow in `cli/tui/`; shared execution should go through `cli/workflow_service.py` or the TUI runner bridge.
- Preserve first-run language selection, queue visibility, recent results, and failed-run retry.
- TUI should not import private helpers from `cli/app.py`.

## Validation

Run `python -m unittest -q tests.test_tui_rebuild tests.test_command_surface`, then smoke `python cli/app.py interactive --help`.
