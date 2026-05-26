---
name: zhihu-command-surface
description: Use when changing or auditing zhihu CLI commands, help text, README command examples, or the bare zhihu and zhihu interactive entrypoint semantics.
---

# Command Surface

## Public Surface

The expected command set is `fetch`, `creator`, `monitor`, `query`, `interactive`, `config`, and `check`. Batch behavior belongs to `fetch --file`; do not reintroduce a standalone `batch` command unless governance and tests change together.

## Guardrails

- Bare `zhihu` and `zhihu interactive` launch the Textual TUI.
- Keep `cli/app.py` handlers thin; orchestration should stay in `cli/workflow_service.py`.
- Keep README examples concise and aligned with Typer commands.
- Update `tests/test_command_surface.py` when changing commands or documented command snippets.

## Validation

Run `python cli/app.py --help`, each command `--help`, and `python -m unittest -q tests.test_command_surface`.
