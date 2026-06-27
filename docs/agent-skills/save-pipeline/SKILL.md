---
name: zhihu-save-pipeline
description: Use when changing Markdown output, image downloading, SQLite writes, save contracts, or fetch workflow persistence behavior.
---

# Save Pipeline

## Boundaries

- `cli/save_pipeline.py` coordinates save runs and typed results.
- `core/converter.py` owns Markdown conversion.
- `core/media_downloader.py` owns image download behavior.
- `core/db.py` owns SQLite persistence and query contracts.
- Preserve local-first outputs: Markdown, images, and SQLite must remain directly user-owned files.

## Validation

Run `python -m unittest -q tests.test_save_pipeline tests.test_save_contracts tests.test_db_contract tests.test_workflow_service` for persistence changes.
