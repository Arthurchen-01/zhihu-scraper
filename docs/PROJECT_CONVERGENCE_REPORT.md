# Project Convergence Report

Date: 2026-05-26

This report records the current convergence state before showing the project externally. It is intentionally practical: what is clean, what is still messy, and what remains before a stable MVP handoff.

## Current State

- `main` is the only local branch.
- Historical local branches have been absorbed into `main` history with merge commits while preserving the current `main` file tree.
- Remote feature/history branches have been removed after `main` was pushed.
- The public command surface is `fetch`, `query`, `config`, and `check`.
- Bare `zhihu` shows CLI help.
- The repository now has project-local agent skills in `docs/agent-skills/`.

## Confusion Checklist

P0: No immediate structural breakage found.

- No `core -> cli` reverse import was found.
- `references/` is not imported by runtime code.
- Tests and command surface still pass after branch convergence.

P1: Showcase exports should remain local-only.

- `examples/outputs/` is now a local temporary showcase area ignored by Git.
- Keep generated Markdown and image exports in `data/` or local ignored example folders.
- If a future example must be committed, reduce it to a small hand-written fixture.

P1: The local working tree can look noisy after running the tool.

- `.venv/`, `.local/`, `.pytest_cache/`, `__pycache__/`, `data/zhihu.db`, and `data/entries/` are ignored.
- This is not currently a Git pollution issue, but it is still a presentation issue when browsing the folder locally.

P2: `config.yaml` is both tracked default config and runtime-writeable state.

- `core/config_runtime.py` can update root `config.yaml`.
- This can make the repository dirty after config changes.
- A cleaner future contract is to keep tracked defaults separate from local runtime config.

P2: Save orchestration lives under `core/`.

- `core/save_pipeline.py` coordinates scraper, converter, image download, and SQLite writes.
- It works, but its responsibility is closer to application/core archive writing than pure CLI.
- Do not move it casually; mark this as a future boundary cleanup only when touching save behavior.

P2: `cli/app.py` is still large enough to require discipline.

- It should remain a command router and validation layer.
- New workflow logic should go into `cli/workflow_service.py` or `core/` depending on ownership.

P3: `references/skills/` broadens repository scope.

- It is useful as a reference library, but not part of runtime delivery.
- Official future-agent workflow should prefer `docs/agent-skills/`.

## MVP Status

MVP is close for a local-first archive demo, but not a general-purpose crawler product.

Achieved:

- CLI automation path.
- Markdown, image, and SQLite local output contract.
- Query command for local archive value.
- Tests guarding docs, command surface, install contract, config, save pipeline, scraper payloads, and workflow service.

Still missing for a polished external demo:

- A short demo script that avoids relying on live Zhihu network behavior.
- A clearer story for `config.yaml` versus local mutable config.
- A small demo fixture if external reviews still need a no-network sample.

Estimated remaining effort:

- Demo-ready polish: 0.5 to 1 day.
- Cleaner runtime config split: 1 to 2 days.
- Moving save orchestration out of `cli/`: 1 to 2 days, only worth doing if save behavior changes.
- Broader crawler reliability: not in scope for the current freeze.
